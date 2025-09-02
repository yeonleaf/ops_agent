#!/usr/bin/env python3
"""
실시간 업데이트를 위한 스레드 기반 시스템
"""

import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

class RealTimeUpdater:
    """실시간 상태 업데이트를 위한 클래스"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status_file = f"logs/{session_id}/current_status.json"
        self.is_running = False
        self.update_thread = None
        self.callback = None
        
    def start_monitoring(self, callback=None):
        """상태 모니터링 시작"""
        self.callback = callback
        self.is_running = True
        self.update_thread = threading.Thread(target=self._monitor_status)
        self.update_thread.daemon = True
        self.update_thread.start()
        
    def stop_monitoring(self):
        """상태 모니터링 중지"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
    
    def _monitor_status(self):
        """상태 파일을 모니터링하는 스레드"""
        last_modified = 0
        
        while self.is_running:
            try:
                if os.path.exists(self.status_file):
                    # 파일 수정 시간 확인
                    current_modified = os.path.getmtime(self.status_file)
                    
                    if current_modified > last_modified:
                        # 파일이 변경되었으면 읽기
                        with open(self.status_file, 'r', encoding='utf-8') as f:
                            status_data = json.load(f)
                        
                        last_modified = current_modified
                        
                        # 콜백 함수 호출
                        if self.callback:
                            self.callback(status_data)
                        
                        # 완료 상태면 모니터링 중지
                        if status_data.get('status') == '완료':
                            self.is_running = False
                            break
                
                time.sleep(0.5)  # 0.5초마다 확인
                
            except Exception as e:
                print(f"상태 모니터링 오류: {e}")
                time.sleep(1)

class StreamlitRealTimeUpdater:
    """Streamlit용 실시간 업데이터"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.updater = RealTimeUpdater(session_id)
        self.status_container = None
        self.last_status = None
        
    def create_status_display(self, st):
        """상태 표시 컨테이너 생성"""
        self.status_container = st.empty()
        return self.status_container
    
    def update_display(self, status_data: Dict[str, Any]):
        """상태 표시 업데이트"""
        if not self.status_container:
            return
            
        status = status_data.get('status', '')
        step = status_data.get('step', '')
        message = status_data.get('message', '')
        timestamp = status_data.get('timestamp', '')
        
        # 상태가 변경되었을 때만 업데이트
        if status != self.last_status:
            self.last_status = status
            
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
    
    def start(self):
        """실시간 업데이트 시작"""
        self.updater.start_monitoring(callback=self.update_display)
    
    def stop(self):
        """실시간 업데이트 중지"""
        self.updater.stop_monitoring()
