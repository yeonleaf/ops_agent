#!/usr/bin/env python3
"""
비동기 처리를 위한 모듈
"""

import asyncio
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import streamlit as st

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

class AsyncProcessor:
    """비동기 처리를 위한 클래스"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status_file = f"logs/{session_id}/current_status.json"
        self.is_processing = False
        self.processing_thread = None
        self.callback = None
        
    def start_processing(self, task_func: Callable, callback: Callable = None):
        """비동기 처리 시작"""
        self.callback = callback
        self.is_processing = True
        
        # 별도 스레드에서 처리
        self.processing_thread = threading.Thread(
            target=self._run_task,
            args=(task_func,)
        )
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def _run_task(self, task_func: Callable):
        """별도 스레드에서 태스크 실행"""
        try:
            # 초기 상태 설정
            self._update_status("시작", "처리를 시작합니다...", "🔄 처리 시작")
            
            # 태스크 실행
            result = task_func()
            
            # 완료 상태 설정
            self._update_status("완료", "처리가 완료되었습니다.", "🎯 처리 완료")
            
            # 콜백 호출
            if self.callback:
                self.callback(result)
                
        except Exception as e:
            # 오류 상태 설정
            self._update_status("오류", f"오류가 발생했습니다: {str(e)}", "❌ 처리 오류")
            
        finally:
            self.is_processing = False
    
    def _update_status(self, status: str, step: str, message: str):
        """상태 파일 업데이트"""
        try:
            status_data = {
                "status": status,
                "step": step,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            
            # 상태 파일에 저장
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"❌ 상태 파일 업데이트 실패: {e}")
    
    def stop_processing(self):
        """처리 중지"""
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1)
    
    def is_running(self) -> bool:
        """처리 중인지 확인"""
        return self.is_processing

class StreamlitAsyncProcessor:
    """Streamlit용 비동기 프로세서"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.processor = AsyncProcessor(session_id)
        self.status_container = None
        
    def create_status_display(self, st):
        """상태 표시 컨테이너 생성"""
        self.status_container = st.empty()
        return self.status_container
    
    def start_processing(self, task_func: Callable, st):
        """비동기 처리 시작"""
        # 상태 표시 컨테이너 생성
        self.create_status_display(st)
        
        # 처리 시작
        self.processor.start_processing(task_func, callback=self._on_complete)
        
        # 실시간 상태 모니터링 시작
        self._start_status_monitoring(st)
    
    def _start_status_monitoring(self, st):
        """상태 모니터링 시작"""
        def monitor_status():
            while self.processor.is_running():
                try:
                    if os.path.exists(self.processor.status_file):
                        with open(self.processor.status_file, 'r', encoding='utf-8') as f:
                            status_data = json.load(f)
                        
                        # UI 업데이트
                        self._update_display(status_data)
                        
                        # 완료 상태면 종료
                        if status_data.get('status') == '완료':
                            break
                    
                    time.sleep(0.5)  # 0.5초마다 확인
                    
                except Exception as e:
                    print(f"상태 모니터링 오류: {e}")
                    time.sleep(1)
        
        # 별도 스레드에서 모니터링
        monitor_thread = threading.Thread(target=monitor_status)
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def _update_display(self, status_data: Dict[str, Any]):
        """상태 표시 업데이트"""
        if not self.status_container:
            return
            
        status = status_data.get('status', '')
        step = status_data.get('step', '')
        message = status_data.get('message', '')
        timestamp = status_data.get('timestamp', '')
        
        with self.status_container.container():
            import streamlit as st
            
            st.markdown("### 🔄 실시간 처리 상태")
            
            # 현재 상태 표시
            if status == "시작":
                st.info(f"🔄 {step}")
            elif status == "LLM 분석 중":
                st.info(f"🤖 {step}")
            elif status == "도구 실행 중":
                st.info(f"🔧 {step}")
            elif status == "도구 완료":
                st.success(f"✅ {step}")
            elif status == "완료":
                st.success(f"🎯 {step}")
            elif status == "오류":
                st.error(f"❌ {step}")
            
            # 타임스탬프 표시
            if timestamp:
                time_str = timestamp[11:19] if len(timestamp) > 19 else timestamp
                st.caption(f"🕐 {time_str}")
            
            # 메시지 표시
            if message:
                st.text(f"📝 {message}")
            
            # 새로고침 버튼
            if st.button("🔄 상태 새로고침", key=f"refresh_{self.session_id}"):
                st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
    
    def _on_complete(self, result):
        """처리 완료 시 호출"""
        print(f"✅ 비동기 처리 완료: {result}")
    
    def stop(self):
        """처리 중지"""
        self.processor.stop_processing()
