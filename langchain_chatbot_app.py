#!/usr/bin/env python3
"""
LangChain 에이전트와 규칙 기반 도구를 결합한 AI 메일 조회 챗봇 (최종 최적화 버전)
"""

import streamlit as st
import json
import os
import sys
import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# LangChain 관련 import
from langchain_core.tools import BaseTool
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler

# 환경 변수 로딩 (가장 먼저 실행)
load_dotenv()

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

# --- 1. 단계별 로그 관리자 클래스 ---

class StepLogger:
    """단계별 로그 파일 기록 클래스"""
    
    def __init__(self, session_id: str, chat_id: str):
        self.session_id = session_id
        self.chat_id = chat_id
        self.log_dir = f"logs/{session_id}/{chat_id}"
        self.step_counter = 0
        
        # 로그 디렉토리 생성 (더 안전한 방식)
        try:
            # logs 디렉토리 생성
            os.makedirs("logs", exist_ok=True)
            
            # session 디렉토리 생성
            session_dir = f"logs/{session_id}"
            os.makedirs(session_dir, exist_ok=True)
            
            # chat 디렉토리 생성
            os.makedirs(self.log_dir, exist_ok=True)
            
            print(f"📁 로그 디렉토리 생성 완료: {self.log_dir}")
            
            # 디렉토리 존재 확인
            if os.path.exists(self.log_dir):
                print(f"✅ 디렉토리 확인됨: {self.log_dir}")
            else:
                print(f"❌ 디렉토리 생성 실패: {self.log_dir}")
                
        except Exception as e:
            print(f"❌ 로그 디렉토리 생성 오류: {e}")
            # 현재 작업 디렉토리 출력
            print(f"현재 작업 디렉토리: {os.getcwd()}")
            print(f"로그 디렉토리 경로: {os.path.abspath(self.log_dir)}")
    
    def log_step(self, step_name: str, content: dict):
        """단계별 로그 파일 생성"""
        self.step_counter += 1
        step_number = f"{self.step_counter:02d}"
        filename = f"{step_number}_{step_name}.json"
        filepath = os.path.join(self.log_dir, filename)
        
        # UUID를 문자열로 변환하는 함수
        def convert_uuid_to_str(obj):
            if hasattr(obj, '__str__'):
                return str(obj)
            return obj
        
        # 재귀적으로 딕셔너리의 모든 값을 변환
        def convert_dict_values(data):
            if isinstance(data, dict):
                return {key: convert_dict_values(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [convert_dict_values(item) for item in data]
            else:
                return convert_uuid_to_str(data)
        
        # 타임스탬프 추가
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "step_number": self.step_counter,
            "step_name": step_name,
            "content": convert_dict_values(content)
        }
        
        try:
            # 디렉토리가 존재하는지 확인하고 필요시 생성
            if not os.path.exists(self.log_dir):
                print(f"⚠️ 로그 디렉토리가 없습니다. 다시 생성합니다: {self.log_dir}")
                os.makedirs(self.log_dir, exist_ok=True)
            
            # 파일 쓰기
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            print(f"📝 로그 파일 생성: {filename}")
            
        except Exception as e:
            print(f"❌ 로그 파일 생성 실패: {e}")
            print(f"   상세 오류: {type(e).__name__}: {str(e)}")
            print(f"   로그 디렉토리: {self.log_dir}")
            print(f"   파일 경로: {filepath}")
            print(f"   현재 작업 디렉토리: {os.getcwd()}")
            
            # 디렉토리 정보 출력
            try:
                if os.path.exists("logs"):
                    print(f"   logs 디렉토리 존재: {os.listdir('logs')}")
                else:
                    print("   logs 디렉토리가 존재하지 않습니다.")
            except Exception as dir_e:
                print(f"   디렉토리 확인 오류: {dir_e}")
    
    def get_log_files(self) -> List[Dict[str, Any]]:
        """로그 파일들을 순서대로 읽어서 반환"""
        log_files = []
        
        try:
            if not os.path.exists(self.log_dir):
                return log_files
            
            # JSON 파일들을 순서대로 읽기
            json_files = [f for f in os.listdir(self.log_dir) if f.endswith('.json')]
            json_files.sort()  # 파일명 순서대로 정렬
            
            for filename in json_files:
                filepath = os.path.join(self.log_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        log_data = json.load(f)
                    log_files.append(log_data)
                except Exception as e:
                    print(f"❌ 로그 파일 읽기 실패 {filename}: {e}")
            
            return log_files
        except Exception as e:
            print(f"❌ 로그 파일 목록 조회 실패: {e}")
            return log_files

# --- 2. LangChain 콜백 핸들러 ---

class FileLoggingCallbackHandler(BaseCallbackHandler):
    """LangChain 이벤트를 파일로 로깅하는 콜백 핸들러"""
    
    def __init__(self, step_logger: StepLogger):
        self.step_logger = step_logger
    
    def _update_status_file(self, status: str, step: str, message: str):
        """상태를 파일에 저장하여 실시간 업데이트"""
        try:
            status_data = {
                "status": status,
                "step": step,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # 세션별 상태 파일 경로
            session_id = self.step_logger.session_id
            status_file = f"logs/{session_id}/current_status.json"
            
            # 디렉토리 생성 (더 안전한 방식)
            try:
                # logs 디렉토리 생성
                os.makedirs("logs", exist_ok=True)
                
                # session 디렉토리 생성
                session_dir = f"logs/{session_id}"
                os.makedirs(session_dir, exist_ok=True)
                
                # 상태 파일에 저장
                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump(status_data, f, ensure_ascii=False, indent=2)
                    
            except Exception as dir_e:
                print(f"❌ 디렉토리 생성 실패: {dir_e}")
                print(f"   세션 ID: {session_id}")
                print(f"   상태 파일 경로: {status_file}")
                print(f"   현재 작업 디렉토리: {os.getcwd()}")
                
        except Exception as e:
            print(f"❌ 상태 파일 업데이트 실패: {e}")
            print(f"   상세 오류: {type(e).__name__}: {str(e)}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """LLM 시작 시 호출"""
        content = {
            "event_type": "llm_start",
            "prompts": prompts,
            "kwargs": kwargs
        }
        self.step_logger.log_step("llm_start", content)
        
        # 실시간 상태 업데이트 (파일 기반)
        self._update_status_file(
            status="LLM 분석 중",
            step="AI가 요청을 분석하고 있습니다...",
            message="🤖 LLM 분석 시작"
        )
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """도구 시작 시 호출"""
        tool_name = serialized.get("name", "unknown")
        content = {
            "event_type": "tool_start",
            "tool_name": tool_name,
            "input_str": input_str,
            "kwargs": kwargs
        }
        self.step_logger.log_step("tool_start", content)
        
        # 실시간 상태 업데이트 (파일 기반)
        self._update_status_file(
            status="도구 실행 중",
            step=f"🔧 {tool_name} 도구 실행 중...",
            message=f"🔧 {tool_name} 도구 실행 시작"
        )
    
    def on_tool_end(self, output: str, **kwargs):
        """도구 종료 시 호출"""
        content = {
            "event_type": "tool_end",
            "output": output,
            "kwargs": kwargs
        }
        self.step_logger.log_step("tool_end", content)
        
        # 실시간 상태 업데이트 (파일 기반)
        self._update_status_file(
            status="도구 완료",
            step="✅ 도구 실행 완료",
            message="✅ 도구 실행 완료"
        )
    
    def on_agent_finish(self, output: str, **kwargs):
        """에이전트 종료 시 호출"""
        content = {
            "event_type": "agent_finish",
            "output": output,
            "kwargs": kwargs
        }
        self.step_logger.log_step("agent_finish", content)
        
        # 실시간 상태 업데이트 (파일 기반)
        self._update_status_file(
            status="완료",
            step="🎯 처리 완료",
            message="🎯 에이전트 처리 완료"
        )

# Gmail OAuth 토큰 갱신 시스템 초기화
def initialize_gmail_oauth():
    """Gmail OAuth 토큰 갱신 시스템 초기화"""
    try:
        from gmail_api_client import GmailAPIClient
        
        print("🔐 Gmail OAuth 시스템 초기화 중...")
        
        # Gmail API 클라이언트 생성 및 인증 상태 확인
        client = GmailAPIClient()
        
        # 토큰 유효성 확인 (만료된 경우 자동 OAuth 시작)
        if client.authenticate():
            print("✅ Gmail OAuth 시스템 초기화 완료")
            return True
        else:
            print("⚠️  Gmail OAuth 시스템 초기화 실패 - 수동 인증이 필요할 수 있습니다.")
            return False
            
    except Exception as e:
        print(f"⚠️  Gmail OAuth 시스템 초기화 중 오류: {e}")
        return False

# Gmail OAuth 시스템 초기화 실행
print("🚀 Gmail OAuth 토큰 갱신 시스템 초기화 시작...")
gmail_oauth_ready = initialize_gmail_oauth()

# 로컬 모듈 import
from mail_list_ui import create_mail_list_ui, create_mail_list_with_sidebar
from enhanced_ticket_ui import (
    display_ticket_list_with_sidebar, 
    clear_ticket_selection, 
    add_ai_recommendation_to_history,
    display_ticket_detail,
    add_label_to_ticket,
    delete_label_from_ticket
)
from unified_email_service import (
    get_email_provider_status, 
    get_available_providers, 
    get_default_provider, 
    EmailMessage, 
    process_emails_with_ticket_logic, 
    get_raw_emails,
    test_ticket_creation_logic,
    test_email_fetch_logic,
    test_work_related_filtering
)

# Memory-Based Ticket Processor Tool import
from memory_based_ticket_processor import create_memory_based_ticket_processor

# 파일 처리 및 임베딩 관련 import
from module.file_processor_refactored import FileProcessor
from pathlib import Path
import tempfile
import shutil

# --- 1. 로그 및 파서 함수 (기존과 동일, 안정성 강화) ---

def safe_format_string(template: str, **kwargs) -> str:
    """안전한 문자열 포맷팅을 위한 헬퍼 함수"""
    try:
        # 중괄호를 이스케이프하여 안전하게 처리
        escaped_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                escaped_kwargs[key] = value.replace('{', '{{').replace('}', '}}')
            else:
                escaped_kwargs[key] = value
        return template.format(**escaped_kwargs)
    except Exception as e:
        logging.error(f"문자열 포맷팅 오류: {e}")
        # 오류 발생 시 원본 템플릿 반환
        return template

# logging 설정
import logging
import os

# 기존 로거 핸들러 제거 (중복 방지)
for handler in logging.getLogger().handlers[:]:
    logging.getLogger().removeHandler(handler)

# 현재 시간으로 로그 파일명 생성
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"debug_logs_{timestamp}.txt"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        logging.FileHandler(log_filename, mode='w', encoding='utf-8')  # 파일 출력 (새 파일)
    ]
)

print(f"✅ 로깅 시스템 초기화 완료 - 로그 파일: {log_filename}")
print(f"📁 현재 디렉토리: {os.getcwd()}")
print(f"🔍 로그 파일 경로: {os.path.abspath(log_filename)}")

def detect_file_type_by_content(file_path: str) -> str:
    """
    파일 내용을 기반으로 실제 파일 형식을 감지
    
    Args:
        file_path: 파일 경로
        
    Returns:
        감지된 파일 형식 (확장자 포함)
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)  # 처음 8바이트 읽기
            
            # 파일 형식별 매직 넘버 확인
            if header.startswith(b'PK\x03\x04'):
                # ZIP 기반 파일들 - 내부 구조로 구분
                try:
                    import zipfile
                    with zipfile.ZipFile(file_path, 'r') as zip_file:
                        file_list = zip_file.namelist()
                        
                        # PPTX 확인
                        if any('ppt/' in name for name in file_list):
                            return '.pptx'
                        # DOCX 확인  
                        elif any('word/' in name for name in file_list):
                            return '.docx'
                        # XLSX 확인
                        elif any('xl/' in name for name in file_list):
                            return '.xlsx'
                        else:
                            return '.zip'  # 일반 ZIP 파일
                except:
                    return '.zip'
                    
            elif header.startswith(b'%PDF'):
                return '.pdf'
            elif header.startswith(b'SCDS'):
                return '.scds'  # SCDS 바이너리 파일
            elif header.startswith(b'\x53\x43\x44\x53'):  # SCDS in hex: 53 43 44 53
                return '.scds'  # SCDS 바이너리 파일
            elif header.startswith(b'\xff\xfe') or header.startswith(b'\xfe\xff'):
                return '.txt'  # 유니코드 텍스트
            elif header.startswith(b'\xef\xbb\xbf'):
                return '.txt'  # UTF-8 BOM 텍스트
            elif all(32 <= b <= 126 or b in [9, 10, 13] for b in header):
                return '.txt'  # 일반 텍스트
            else:
                return '.bin'  # 바이너리 파일
                
    except Exception as e:
        return '.unknown'

def embed_and_store_chunks(chunks: List[Dict[str, Any]], file_name: str, file_content: bytes, 
                          processing_duration: float) -> Dict[str, Any]:
    """
    텍스트 청크를 임베딩하고 벡터 데이터베이스에 저장
    
    Args:
        chunks: FileProcessor가 반환한 청크 리스트
        file_name: 원본 파일명
        file_content: 파일 내용 (바이트)
        processing_duration: 처리 소요 시간 (초)
        
    Returns:
        저장 결과 요약
    """
    try:
        # SystemInfoVectorDBManager 초기화
        if 'system_info_db' not in st.session_state:
            from vector_db_models import SystemInfoVectorDBManager
            st.session_state.system_info_db = SystemInfoVectorDBManager()
        
        # 벡터DB에 저장
        db_result = st.session_state.system_info_db.save_file_chunks(
            chunks=chunks,
            file_content=file_content,
            file_name=file_name,
            processing_duration=processing_duration
        )
        
        if db_result["success"]:
            # 중복 파일인 경우
            if db_result.get("duplicate", False):
                return {
                    "success": True,
                    "file_name": file_name,
                    "total_chunks": 0,
                    "total_elements": 0,
                    "total_text_length": 0,
                    "architectures": [],
                    "vision_analysis_count": 0,
                    "duplicate": True,
                    "file_hash": db_result.get("file_hash", ""),
                    "message": db_result["message"]
                }
            
            # 새로 저장된 경우
            total_chunks = len(chunks)
            total_elements = sum(len(chunk.get('metadata', {}).get('elements', [])) for chunk in chunks)
            total_text_length = sum(len(chunk.get('text_chunk_to_embed', '')) for chunk in chunks)
            
            # 아키텍처 정보 수집
            architectures = set()
            vision_analysis_count = 0
            
            for chunk in chunks:
                metadata = chunk.get('metadata', {})
                architecture = metadata.get('architecture', 'unknown')
                architectures.add(architecture)
                
                if metadata.get('vision_analysis', False):
                    vision_analysis_count += 1
            
            return {
                "success": True,
                "file_name": file_name,
                "total_chunks": total_chunks,
                "total_elements": total_elements,
                "total_text_length": total_text_length,
                "architectures": list(architectures),
                "vision_analysis_count": vision_analysis_count,
                "duplicate": False,
                "file_hash": db_result.get("file_hash", ""),
                "chunks_saved": db_result.get("chunks_saved", 0),
                "message": db_result["message"]
            }
        else:
            # 벡터DB 저장 실패
            return {
                "success": False,
                "file_name": file_name,
                "error": db_result.get("error", "알 수 없는 오류"),
                "message": db_result["message"]
            }
        
    except Exception as e:
        return {
            "success": False,
            "file_name": file_name,
            "error": str(e),
            "message": f"❌ {file_name} 처리 중 오류 발생: {str(e)}"
        }

def determine_ui_mode(query: str, response_data: Dict[str, Any]) -> str:
    """쿼리와 응답 데이터를 기반으로 UI 모드를 결정합니다."""
    query_lower = query.lower()
    display_mode = response_data.get('display_mode', '')
    
    # 버튼 리스트가 필요한 키워드들
    button_list_keywords = [
        "목록", "리스트", "조회", "보여줘", "확인", "찾아줘",
        "티켓", "메일", "전체", "생성되어 있는", "이미"
    ]
    
    # 텍스트만 필요한 키워드들  
    text_only_keywords = [
        "요약", "통계", "개수", "몇 개", "상태", "정보"
    ]
    
    # 1. 명시적으로 텍스트만 요청하는 경우
    text_score = sum(1 for kw in text_only_keywords if kw in query_lower)
    if text_score > 0:
        return "text_only"
    
    # 2. 메일이나 티켓 리스트를 요청하는 경우
    button_score = sum(1 for kw in button_list_keywords if kw in query_lower)
    
    # 3. display_mode가 mail_list이고 버튼 관련 키워드가 있으면 버튼 리스트
    if display_mode == 'mail_list' and button_score >= 2:
        return "button_list"
    
    # 4. 티켓 관련 요청이면 기본적으로 버튼 리스트
    if display_mode == 'tickets' or "티켓" in query_lower:
        return "button_list"
    
    # 5. 기본값은 텍스트
    return "text_only"

def parse_query_to_parameters(query: str) -> Dict[str, Any]:
    """LLM을 사용하여 사용자 쿼리를 분석하여 실행 파라미터 딕셔너리를 생성합니다."""
    logging.info(safe_format_string("LLM 쿼리 파싱 시작: '{query}'", query=query))
    
    # session_state 상태 확인
    logging.info(safe_format_string("session_state.llm 존재 여부: {llm_exists}", llm_exists='llm' in st.session_state))
    if 'llm' in st.session_state:
        logging.info(safe_format_string("session_state.llm 값: {llm_value}", llm_value=st.session_state.llm))
    
    try:
        # LLM이 사용 가능한 경우 LLM 기반 파싱 사용
        if 'llm' in st.session_state and st.session_state.llm:
            logging.info("LLM 기반 파싱 시도 중...")
            result = _parse_query_with_llm(query)
            logging.info(safe_format_string("LLM 파싱 성공: {result}", result=result))
            return result
        else:
            logging.warning("LLM이 사용 불가능하여 규칙 기반 파싱으로 대체")
            result = _parse_query_with_rules(query)
            logging.info(safe_format_string("규칙 기반 파싱 결과: {result}", result=result))
            return result
    except Exception as e:
        logging.error(safe_format_string("LLM 쿼리 파싱 실패, 규칙 기반으로 대체: {error}", error=str(e)))
        result = _parse_query_with_rules(query)
        logging.info(safe_format_string("Fallback 규칙 기반 파싱 결과: {result}", result=result))
        return result

def _parse_query_with_llm_direct(query: str, llm) -> Dict[str, Any]:
    """LLM 인스턴스를 직접 받아서 쿼리를 파싱합니다 (ViewingAgent용)"""
    try:
        
        # LLM에게 전달할 시스템 프롬프트
        system_prompt = """당신은 Gmail API 쿼리 생성 전문가입니다.
사용자의 자연어 요청을 Gmail API 파라미터로 변환해주세요.

지원하는 필터:
- is_read: true/false (읽은 메일/안 읽은 메일)
- sender: 발신자 이메일 또는 도메인
- subject: 제목에 포함된 키워드
- has_attachments: true/false (첨부파일 유무)
- limit: 가져올 메일 개수
- date_after: 특정 날짜 이후 (YYYY-MM-DD)
- date_before: 특정 날짜 이전 (YYYY-MM-DD)

지원하는 액션:
- view: 메일 조회
- classify: 메일 분류 및 티켓 생성
- process_tickets: 티켓 처리

응답은 반드시 다음 JSON 형식으로만 해주세요:
{
    "action": "view",
    "filters": {
        "is_read": false,
        "limit": 10
    }
}"""

        # 사용자 쿼리
        user_message = safe_format_string("다음 요청을 Gmail API 파라미터로 변환해주세요: {query}", query=query)
        
        # LLM 호출
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        response_content = response.content
        
        logging.info(safe_format_string("LLM 응답: {response_content}", response_content=response_content))
        
        # JSON 파싱 시도
        try:
            # JSON 블록 추출 (```json ... ``` 형태일 수 있음)
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                if json_end != -1:
                    response_content = response_content[json_start:json_end].strip()
            
            # JSON 파싱
            params = json.loads(response_content)
            
            # 필수 필드 검증
            if 'action' not in params:
                params['action'] = 'view'
            if 'filters' not in params:
                params['filters'] = {}
                
            logging.info(safe_format_string("LLM 파싱 결과: {params}", params=params))
            return params
            
        except json.JSONDecodeError as e:
            logging.error(safe_format_string("LLM 응답 JSON 파싱 실패: {error}", error=str(e)))
            logging.error(safe_format_string("응답 내용: {response_content}", response_content=response_content))
            raise e
            
    except Exception as e:
        logging.error(safe_format_string("LLM 쿼리 파싱 오류: {error}", error=str(e)))
        raise e

def _parse_query_with_rules(query: str) -> Dict[str, Any]:
    """규칙 기반 쿼리 파싱 (LLM 실패 시 대체용)"""
    logging.info(safe_format_string("규칙 기반 쿼리 파싱 시작: '{query}'", query=query))
    query_lower = query.lower()
    params = {'action': 'view', 'filters': {}}

    view_keywords = ["보여줘", "찾아줘", "조회", "목록", "리스트", "보기", "확인"]
    process_keywords = ["처리", "분류", "업무", "티켓", "작업", "정리해줘"]
    
    view_score = sum(1 for kw in view_keywords if kw in query_lower)
    process_score = sum(1 for kw in process_keywords if kw in query_lower)
    
    if '개' in query_lower and re.search(r'\d+', query):
        view_score += 2

    # "티켓" 키워드가 있으면 먼저 분류 후 티켓 처리
    if "티켓" in query_lower:
        params['action'] = 'classify'
    elif process_score > view_score:
        params['action'] = 'process_tickets'

    # 안 읽은 메일 관련 키워드 (공백 유무 상관없이)
    unread_keywords = ["안읽은", "안 읽은", "새로운", "새 메일", "읽지 않은", "읽지않은"]
    read_keywords = ["읽은", "읽은 메일", "읽음"]
    
    # 디버깅: 키워드 매칭 확인
    matched_unread = [kw for kw in unread_keywords if kw in query_lower]
    matched_read = [kw for kw in read_keywords if kw in query_lower]
    
    logging.info(safe_format_string("쿼리: '{query}' -> 소문자: '{query_lower}'", query=query, query_lower=query_lower))
    logging.info(safe_format_string("안 읽은 키워드 매칭 시도: {unread_keywords}", unread_keywords=unread_keywords))
    logging.info(safe_format_string("읽은 키워드 매칭 시도: {read_keywords}", read_keywords=read_keywords))
    logging.info(safe_format_string("매칭된 안 읽은 키워드: {matched_unread}", matched_unread=matched_unread))
    logging.info(safe_format_string("매칭된 읽은 키워드: {matched_read}", matched_read=matched_read))
    
    if matched_unread:
        params['filters']['is_read'] = False
        logging.info("✅ 안 읽은 메일로 설정: is_read=False")
    elif matched_read:
        params['filters']['is_read'] = True
        logging.info("✅ 읽은 메일로 설정: is_read=True")
    else:
        logging.info("⚠️ 읽음 상태 관련 키워드가 없음 - 기본값 사용")
    
    if match := re.search(r'(\d+)개', query):
        params['filters']['limit'] = int(match.group(1))

    logging.info(safe_format_string("규칙 기반 파싱 결과: {params}", params=params))
    return params

def handle_mail_query(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    파라미터 딕셔너리를 기반으로 메일 쿼리를 처리하는 통합 함수
    """
    action = params.get('action', 'view')
    filters = params.get('filters', {})
    provider = st.session_state.get('email_provider', get_default_provider())
    
    logging.info(safe_format_string("메일 쿼리 핸들러 실행: action='{action}', filters={filters}", action=action, filters=filters))

    try:
        if action == 'view_mails':
            # 단순 메일 조회는 get_raw_emails 함수를 호출합니다.
            logging.info(safe_format_string("view_mails 액션: get_raw_emails 호출 - provider={provider}, filters={filters}", provider=provider, filters=filters))
            emails = get_raw_emails(provider, filters)
            if emails:
                # EmailMessage 객체를 JSON 직렬화 가능한 딕셔너리로 변환
                mail_list = []
                for email in emails:
                    email_dict = email.model_dump()
                    mail_list.append({
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    })
                return {'display_mode': 'mail_list', 'mail_list': mail_list}
            else:
                return {'display_mode': 'no_emails', 'message': '조건에 맞는 메일이 없습니다.'}
        
        elif action == 'view_tickets':
            # 기존 티켓 조회 (이미 생성된 티켓 목록)
            logging.info(f"view_tickets 액션: 기존 티켓 조회")
            try:
                from sqlite_ticket_models import SQLiteTicketManager
                ticket_manager = SQLiteTicketManager()
                # pending 상태인 티켓만 조회
                existing_tickets = ticket_manager.get_tickets_by_status('pending')
                
                if existing_tickets:
                    # Ticket 객체를 딕셔너리로 변환
                    ticket_list = []
                    for ticket in existing_tickets:
                        ticket_dict = {
                            'ticket_id': ticket.ticket_id,
                            'message_id': ticket.original_message_id,  # message_id 추가
                            'title': ticket.title,
                            'status': ticket.status,
                            'priority': ticket.priority,
                            'labels': ticket.labels,  # ticket_type 대신 labels 사용
                            'reporter': ticket.reporter,
                            'description': ticket.description,  # description 추가
                            'created_at': ticket.created_at,
                            'updated_at': ticket.updated_at
                        }
                        ticket_list.append(ticket_dict)
                    
                    logging.info(f"기존 티켓 {len(ticket_list)}개 조회 완료")
                    return {'display_mode': 'tickets', 'tickets': ticket_list, 'message': f'기존 티켓 {len(ticket_list)}개를 조회했습니다.'}
                else:
                    logging.info("기존 티켓이 없습니다.")
                    return {'display_mode': 'no_tickets', 'message': '생성된 티켓이 없습니다.', 'tickets': []}
                    
            except Exception as e:
                logging.error(f"기존 티켓 조회 오류: {str(e)}")
                return {'display_mode': 'error', 'message': f'기존 티켓 조회 중 오류가 발생했습니다: {str(e)}', 'tickets': []}
        
        elif action == 'view':
            # 기존 view 액션과의 호환성을 위한 fallback
            logging.info(f"view 액션 (fallback): get_raw_emails 호출")
            emails = get_raw_emails(provider, filters)
            if emails:
                mail_list = []
                for email in emails:
                    email_dict = email.model_dump()
                    mail_list.append({
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    })
                return {'display_mode': 'mail_list', 'mail_list': mail_list}
            else:
                return {'display_mode': 'no_emails', 'message': '조건에 맞는 메일이 없습니다.'}
        
        elif action == 'classify':
            # 메일 분류는 get_raw_emails로 메일을 가져온 후 분류 로직 적용
            emails = get_raw_emails(provider, filters)
            if emails:
                # EmailMessage 객체를 JSON 직렬화 가능한 딕셔너리로 변환
                mail_list = []
                work_related_emails = []
                
                for email in emails:
                    email_dict = email.model_dump()
                    mail_data = {
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    }
                    mail_list.append(mail_data)
                    
                    # 업무 관련 메일인지 확인 (간단한 키워드 기반 필터링)
                    subject_lower = email_dict.get('subject', '').lower()
                    body_lower = email_dict.get('body', '').lower()
                    
                    work_keywords = ['업무', '회사', '프로젝트', '회의', '보고서', '개발', '코딩', '버그', '이슈', '배포', '테스트', '코드', '시스템', '서버', '데이터베이스', 'api', '웹', '앱', '소프트웨어', '프로그램', '기술', '인프라', '클라우드', '보안', '백업', '모니터링', '로그', '성능', '최적화', '업그레이드', '마이그레이션', '통합', '연동', '동기화', '백업', '복구', '장애', '오류', '에러', '문제', '해결', '지원', '문의', '요청', '제안', '검토', '승인', '결재', '계약', '협력', '파트너', '고객', '사용자', '관리자', '운영', '유지보수', '개선', '개발', '설계', '구현', '테스트', '배포', '운영', '모니터링', '백업', '복구', '보안', '인증', '권한', '접근', '로그', '감사', '준수', '정책', '절차', '가이드', '매뉴얼', '문서', '코드', '소스', '버전', '커밋', '브랜치', '머지', '풀리퀘스트', '코드리뷰', '테스트', 'qa', '품질', '성능', '보안', '접근성', '사용성', '호환성', '확장성', '안정성', '신뢰성', '가용성', '복구성', '백업', '동기화', '백업', '복구', '장애', '오류', '에러', '문제', '해결', '지원', '문의', '요청', '제안', '검토', '승인', '결재', '계약', '협력', '파트너', '고객', '사용자', '관리자', '운영', '유지보수', '개선', '개발', '설계', '구현', '테스트', '배포', '운영', '모니터링', '백업', '복구', '보안', '인증', '권한', '접근', '로그', '감사', '준수', '정책', '절차', '가이드', '매뉴얼', '문서', '코드', '소스', '버전', '커밋', '브랜치', '머지', '풀리퀘스트', '코드리뷰', '테스트', 'qa', '품질', '성능', '보안', '접근성', '사용성', '호환성', '확장성', '안정성', '신뢰성', '가용성', '복구성']
                    
                    # 업무 관련 키워드가 있거나, 특정 도메인이 아닌 경우 업무 관련으로 간주
                    is_work_related = any(keyword in subject_lower or keyword in body_lower for keyword in work_keywords)
                    
                    # 개인/스팸 메일 도메인 제외
                    personal_domains = ['@gmail.com', '@naver.com', '@daum.net', '@hotmail.com', '@outlook.com', '@yahoo.com']
                    sender_domain = email_dict.get('sender', '').lower()
                    is_personal = any(domain in sender_domain for domain in personal_domains)
                    
                    if is_work_related and not is_personal:
                        work_related_emails.append(mail_data)
                
                # 업무 관련 메일이 있으면 티켓 처리 진행
                if work_related_emails:
                    # 티켓 처리 로직 실행 (이미 import됨)
                    try:
                        logging.info(safe_format_string("티켓 처리 시작: 업무 관련 메일 {count}개", count=len(work_related_emails)))
                        
                        ticket_result = process_emails_with_ticket_logic(provider, user_query=str(params))
                        logging.info(safe_format_string("티켓 처리 결과: {result}", result=ticket_result))
                        
                        # 티켓 결과 검증
                        if not ticket_result.get('tickets'):
                            logging.warning(safe_format_string("경고: 티켓 결과에 tickets 배열이 없음: {result}", result=ticket_result))
                        
                        # 티켓 결과에 분류 정보 추가
                        ticket_result['classification_info'] = safe_format_string('업무 관련 메일 {count}개를 티켓으로 처리했습니다.', count=len(work_related_emails))
                        ticket_result['work_related_count'] = len(work_related_emails)
                        ticket_result['total_emails'] = len(mail_list)
                        
                        logging.info(safe_format_string("최종 반환 결과: {result}", result=ticket_result))
                        return ticket_result
                    except Exception as e:
                        logging.error(safe_format_string("티켓 처리 중 오류: {error}", error=e))
                        import traceback
                        logging.error(safe_format_string("오류 상세: {traceback}", traceback=traceback.format_exc()))
                        return {
                            'display_mode': 'classified_mail_list',
                            'mail_list': work_related_emails,
                            'classification_info': safe_format_string('업무 관련 메일 {count}개를 찾았지만 티켓 처리 중 오류가 발생했습니다.', count=len(work_related_emails)),
                            'error': str(e)
                        }
                else:
                    # 업무 관련 메일이 없는 경우
                    return {
                        'display_mode': 'classified_mail_list',
                        'mail_list': mail_list,
                        'classification_info': '업무 관련 메일이 없습니다. 모든 메일을 단순 조회로 표시합니다.',
                        'work_related_count': 0,
                        'total_emails': len(mail_list)
                    }
            else:
                return {'display_mode': 'no_emails', 'message': '분류할 메일이 없습니다.'}
        
        elif action == 'process_tickets':
            # 티켓 처리는 process_emails_with_ticket_logic 함수를 호출합니다.
            logging.info(safe_format_string("process_tickets 액션 시작: provider={provider}, params={params}", provider=provider, params=params))
            
            try:
                logging.info("🔍 process_emails_with_ticket_logic 함수 호출 시작...")
                logging.info(f"🔍 호출 파라미터: provider={provider}, user_query={str(params)}")
                
                # 함수가 실제로 존재하는지 확인
                logging.info(f"🔍 process_emails_with_ticket_logic 함수 객체: {process_emails_with_ticket_logic}")
                logging.info(f"🔍 함수 타입: {type(process_emails_with_ticket_logic)}")
                
                response_data = process_emails_with_ticket_logic(provider, user_query=str(params))
                logging.info(safe_format_string("process_emails_with_ticket_logic 결과: {response_data}", response_data=response_data))
                
                # 티켓 결과 검증
                if response_data.get('display_mode') == 'tickets':
                    tickets_count = len(response_data.get('tickets', []))
                    logging.info(safe_format_string("process_tickets - 티켓 개수: {count}", count=tickets_count))
                    if tickets_count == 0:
                        logging.warning(safe_format_string("process_tickets - 경고: 티켓이 0개입니다. 전체 결과: {response_data}", response_data=response_data))
                
                return response_data
            except Exception as e:
                logging.error(safe_format_string("process_tickets 액션 오류: {error}", error=e))
                import traceback
                logging.error(safe_format_string("오류 상세: {traceback}", traceback=traceback.format_exc()))
                raise
            
    except Exception as e:
        logging.error(f"handle_mail_query 오류: {e}")
        st.error(f"메일 처리 중 오류가 발생했습니다: {str(e)}")
        return {'display_mode': 'error', 'message': f'처리 중 오류가 발생했습니다.'}

# --- 2. 새로운 LangChain 도구 정의 ---

class ViewEmailsTool(BaseTool):
    """단순 이메일 조회 및 필터링을 위한 LangChain 도구"""
    name: str = "view_emails_tool"
    description: str = """단순 이메일 조회 및 필터링을 위한 도구입니다. 
    
    사용해야 하는 경우:
    - "안 읽은 메일 3개 보여줘"
    - "읽은 메일 목록"
    - "특정 발신자 메일 조회"
    - "최근 메일 5개"
    - "메일 리스트"
    - "이메일 확인"
    
    이 도구는 메일을 조회하고 표시하는 것만 담당하며, 티켓 생성이나 분류는 수행하지 않습니다."""
    
    def _run(self, query: str) -> str:
        """메일 조회만 수행하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(safe_format_string("ViewEmailsTool 실행: {query}", query=query))
            params = parse_query_to_parameters(query)
            logging.info(safe_format_string("파싱된 파라미터: {params}", params=params))
            
            # view 액션만 처리
            if params.get('action') != 'view':
                return json.dumps({"error": "이 도구는 메일 조회만 가능합니다."}, ensure_ascii=False)
            
            result_data = handle_mail_query(params)
            logging.info(safe_format_string("핸들러 실행 결과: {result_data}", result_data=result_data))
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(safe_format_string("세션에 직접 저장 완료: {latest_response}", latest_response=st.session_state.get('latest_response') is not None))
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(safe_format_string("반환할 JSON: {json_result}", json_result=json_result))
            return json_result
        except Exception as e:
            error_msg = safe_format_string("ViewEmailsTool 실행 오류: {error}", error=e)
            logging.error(error_msg)
            return json.dumps({"error": error_msg}, ensure_ascii=False)

class ClassifyEmailsTool(BaseTool):
    """이메일 조회 및 내부 분류기 실행을 위한 LangChain 도구"""
    name: str = "classify_emails_tool"
    description: str = """이메일을 조회하고 내부 분류기를 실행하여 업무 관련성을 판단하는 도구입니다.
    
    사용해야 하는 경우:
    - "업무 메일 분류해줘"
    - "중요한 메일 찾아줘"
    - "메일을 분류해서 보여줘"
    - "업무 관련 메일만"
    - "메일 우선순위 정해줘"
    
    이 도구는 메일을 조회하고 분류하지만, 티켓 생성은 수행하지 않습니다."""
    
    def _run(self, query: str) -> str:
        """메일 조회 및 분류를 수행하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(safe_format_string("ClassifyEmailsTool 실행 시작: {query}", query=query))
            params = parse_query_to_parameters(query)
            logging.info(safe_format_string("파싱된 파라미터: {params}", params=params))
            
            # classify 액션으로 변경
            params['action'] = 'classify'
            logging.info(safe_format_string("액션 강제 설정: {action}", action=params['action']))
            
            logging.info("handle_mail_query 호출 시작")
            result_data = handle_mail_query(params)
            logging.info(safe_format_string("핸들러 실행 결과: {result_data}", result_data=result_data))
            
            # 티켓 결과 검증
            if result_data.get('display_mode') == 'tickets':
                tickets_count = len(result_data.get('tickets', []))
                logging.info(safe_format_string("티켓 개수 확인: {count}", count=tickets_count))
                if tickets_count == 0:
                    logging.warning(safe_format_string("경고: 티켓이 0개입니다. 전체 결과: {result_data}", result_data=result_data))
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            logging.info(safe_format_string("UI 모드 결정: {ui_mode}", ui_mode=ui_mode))
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(safe_format_string("세션에 직접 저장 완료: {latest_response}", latest_response=st.session_state.get('latest_response') is not None))
                logging.info(safe_format_string("세션에 저장된 데이터: {latest_response}", latest_response=st.session_state.get('latest_response')))
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(safe_format_string("ClassifyEmailsTool 최종 반환: {json_result}", json_result=json_result))
            return json_result
        except Exception as e:
            error_msg = safe_format_string("ClassifyEmailsTool 실행 오류: {error}", error=e)
            logging.error(error_msg)
            import traceback
            logging.error(safe_format_string("오류 상세: {traceback}", traceback=traceback.format_exc()))
            return json.dumps({"error": error_msg}, ensure_ascii=False)

def convert_datetime_to_iso(data):
    """datetime 객체를 ISO 문자열로 변환하여 JSON 직렬화 가능하게 만듭니다."""
    if isinstance(data, dict):
        return {key: convert_datetime_to_iso(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_iso(item) for item in data]
    elif hasattr(data, 'isoformat'):  # datetime 객체
        return data.isoformat()
    elif hasattr(data, 'strftime'):  # date 객체
        return data.strftime('%Y-%m-%d')
    else:
        return data

class ProcessTicketsTool(BaseTool):
    """이메일 조회, 티켓 생성/조회 등 전체 티켓 워크플로우를 처리하는 LangChain 도구"""
    name: str = "process_tickets_tool"
    description: str = """이메일을 조회하고 티켓 생성/조회 등 전체 티켓 워크플로우를 처리하는 도구입니다.
    
    사용해야 하는 경우:
    - "티켓 생성해줘"
    - "업무 메일을 티켓으로 만들어줘"
    - "기존 티켓 목록 조회"
    - "오늘 처리할 티켓"
    - "티켓 워크플로우 실행"
    - "메일을 티켓으로 변환"
    
    이 도구는 메일 조회부터 티켓 생성까지 전체 프로세스를 담당합니다."""
    
    def _determine_action_with_llm(self, query: str) -> str:
        """LLM을 사용하여 사용자 요청의 의도를 파악하고 적절한 액션을 결정합니다."""
        try:
            # LLM이 사용 가능한 경우 LLM 기반 판단
            if 'llm' in st.session_state and st.session_state.llm:
                return self._determine_action_with_llm_internal(query)
            else:
                logging.warning("LLM이 사용 불가능하여 기본 규칙 기반 판단으로 대체")
                return self._determine_action_with_rules(query)
        except Exception as e:
            logging.error(safe_format_string("LLM 액션 결정 실패, 규칙 기반으로 대체: {error}", error=str(e)))
            return self._determine_action_with_rules(query)
    
    def _determine_action_with_llm_internal(self, query: str) -> str:
        """LLM을 사용하여 액션을 결정합니다."""
        try:
            llm = st.session_state.llm
            
            system_prompt = """당신은 사용자 요청을 분석하여 적절한 액션을 결정하는 전문가입니다.

지원하는 액션:
1. view_mails: 단순 메일 조회 (필터링, 검색, 목록 등)
2. view_tickets: 기존 티켓 조회 (이미 생성된 티켓 목록)
3. process_tickets: 새로운 티켓 생성 및 업무 처리

판단 기준:
- "메일 보여줘", "이메일 조회", "안 읽은 메일" → view_mails
- "기존 티켓 목록", "생성된 티켓 보여줘", "이미 있는 티켓" → view_tickets  
- "새로운 티켓 생성", "업무 메일을 티켓으로", "메일을 티켓으로 변환" → process_tickets
- "오늘 받은 메일 중 중요한 것만" → view_mails (메일 필터링)
- "업무 관련 메일을 티켓으로 변환" → process_tickets

JSON 형식으로만 응답:
{
    "action": "view_mails|view_tickets|process_tickets",
    "reasoning": "선택 이유",
    "query_type": "mail_query|ticket_query|ticket_creation"
}"""

            user_message = safe_format_string("다음 요청을 분석하여 적절한 액션을 결정해주세요: {query}", query=query)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
            
            response = llm.invoke(messages)
            response_content = response.content
            
            logging.info(safe_format_string("LLM 액션 결정 응답: {response_content}", response_content=response_content))
            
            # JSON 파싱
            try:
                if "```json" in response_content:
                    json_start = response_content.find("```json") + 7
                    json_end = response_content.find("```", json_start)
                    if json_end != -1:
                        response_content = response_content[json_start:json_end].strip()
                
                result = json.loads(response_content)
                action = result.get('action', 'view_mails')
                reasoning = result.get('reasoning', '')
                
                logging.info(safe_format_string("LLM 액션 결정 결과: {action}, 이유: {reasoning}", action=action, reasoning=reasoning))
                return action
                
            except json.JSONDecodeError as e:
                logging.error(safe_format_string("LLM 응답 JSON 파싱 실패: {error}", error=str(e)))
                raise e
                
        except Exception as e:
            logging.error(safe_format_string("LLM 액션 결정 오류: {error}", error=str(e)))
            raise e
    
    def _determine_action_with_rules(self, query: str) -> str:
        """규칙 기반으로 액션을 결정합니다 (LLM 실패 시 대체용)"""
        query_lower = query.lower()
        
        # 기존 티켓 조회 키워드
        ticket_view_keywords = ["이미 생성된", "기존", "생성된", "있는", "티켓 목록", "티켓 리스트"]
        if any(keyword in query_lower for keyword in ticket_view_keywords):
            return 'view_tickets'
        
        # 새로운 티켓 생성 키워드
        ticket_creation_keywords = ["새로운", "생성", "만들어줘", "변환", "업무 메일을 티켓으로"]
        if any(keyword in query_lower for keyword in ticket_creation_keywords):
            return 'process_tickets'
        
        # 기본값: 메일 조회
        return 'view_mails'
    
    def _run(self, query: str) -> str:
        """전체 티켓 워크플로우를 처리하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(safe_format_string("ProcessTicketsTool 실행: {query}", query=query))
            params = parse_query_to_parameters(query)
            logging.info(safe_format_string("파싱된 파라미터: {params}", params=params))
            
            # LLM을 사용하여 액션 결정
            params['action'] = self._determine_action_with_llm(query)
            logging.info(safe_format_string("ProcessTicketsTool에서 LLM 기반 액션 결정: {action}", action=params['action']))
            result_data = handle_mail_query(params)
            logging.info(safe_format_string("핸들러 실행 결과: {result_data}", result_data=result_data))
            
            # 티켓 결과 검증
            if result_data.get('display_mode') == 'tickets':
                tickets_count = len(result_data.get('tickets', []))
                logging.info(safe_format_string("ProcessTicketsTool - 티켓 개수 확인: {count}", count=tickets_count))
                if tickets_count == 0:
                    logging.warning(safe_format_string("ProcessTicketsTool - 경고: 티켓이 0개입니다. 전체 결과: {result_data}", result_data=result_data))
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(safe_format_string("세션에 직접 저장 완료: {latest_response}", latest_response=st.session_state.get('latest_response') is not None))
            
            # datetime 객체를 JSON 직렬화 가능하게 변환
            result_data = convert_datetime_to_iso(result_data)
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(safe_format_string("반환할 JSON: {json_result}", json_result=json_result))
            return json_result
        except Exception as e:
            error_msg = safe_format_string("ProcessTicketsTool 실행 오류: {error}", error=e)
            logging.error(error_msg)
            return json.dumps({"error": error_msg}, ensure_ascii=False)

# --- 3. Streamlit 앱 메인 로직 ---

def init_session_state():
    """세션 상태 변수들을 초기화합니다."""
    # 새로운 세션 ID 생성 (앱 시작 시 또는 대화 초기화 시)
    new_session_id = f"session_{str(uuid.uuid4())[:12]}"
    
    # 기존 세션 폴더가 있으면 삭제
    if 'session_id' in st.session_state:
        old_session_id = st.session_state.session_id
        old_session_path = f"logs/{old_session_id}"
        if os.path.exists(old_session_path):
            try:
                import shutil
                shutil.rmtree(old_session_path)
                print(f"🗑️ 기존 세션 폴더 삭제: {old_session_path}")
            except Exception as e:
                print(f"⚠️ 기존 세션 폴더 삭제 실패: {e}")
    
    defaults = {
        'main_agent': None,
        'messages': [],
        'latest_response': None,
        'email_provider': get_default_provider(),
        'email_connected': False,
        'session_id': new_session_id,  # 세션 ID 추가
        'chat_counter': 0,  # 채팅 카운터 추가
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    print(f"🆔 새로운 세션 생성: {new_session_id}")

def create_main_agent():
    """LLM과 도구를 사용하여 메인 에이전트를 생성합니다."""
    try:
        # --- 1. 환경 변수 로드 및 검증 (가장 중요!) ---
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        # 필수 변수들이 모두 로드되었는지 확인
        if not all([api_key, api_version, azure_endpoint, deployment_name]):
            missing_vars = [var for var, val in locals().items() if not val]
            st.error(safe_format_string("필수 환경변수가 누락되었습니다: {missing_vars}. .env 파일을 확인해주세요.", missing_vars=', '.join(missing_vars)))
            return None
            
        # .env 파일에 불필요한 공백이나 '/'가 들어가는 것을 방지
        clean_endpoint = azure_endpoint.strip().rstrip('/')

        # --- 2. Streamlit UI에 현재 설정값 출력 (디버깅용) ---
        st.info("🔧 현재 적용된 Azure OpenAI 설정:")
        st.text(safe_format_string("   - ENDPOINT: {endpoint}", endpoint=clean_endpoint))
        st.text(safe_format_string("   - DEPLOYMENT_NAME: {deployment_name}", deployment_name=deployment_name))
        st.text(safe_format_string("   - API_VERSION: {api_version}", api_version=api_version))
        
        # --- 3. AzureChatOpenAI 초기화 (표준 방식) ---
        # 라이브러리가 clean_endpoint를 기반으로 전체 URL을 만들도록 위임합니다.
        llm = AzureChatOpenAI(
            azure_endpoint=clean_endpoint,
            deployment_name=deployment_name,
            api_key=api_key,
            api_version=api_version,
            temperature=0
        )
        st.success("✅ AzureChatOpenAI 초기화 성공")
        
        # LLM을 session_state에 저장 (쿼리 파싱에서 사용)
        st.session_state.llm = llm
        logging.info("LLM이 session_state에 저장되었습니다.")

        tools = [
            ViewEmailsTool(),
            ClassifyEmailsTool(),
            ProcessTicketsTool(),
            create_memory_based_ticket_processor()
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 사용자의 요청을 분석하여 가장 적절한 전문 도구를 선택하는 유능한 AI 어시스턴트입니다.

🚨 **도구 선택 규칙:**
사용자의 요청에 따라 다음 네 가지 도구 중 하나를 선택해야 합니다:

1. **view_emails_tool**: 단순 메일 조회 및 필터링
   - "안 읽은 메일 보여줘", "메일 목록", "특정 발신자 메일" 등

2. **classify_emails_tool**: 메일 분류 및 업무 관련성 판단
   - "업무 메일 분류", "중요한 메일 찾기", "메일 우선순위" 등

3. **process_tickets_tool**: 전체 티켓 워크플로우
   - "티켓 생성", "기존 티켓 조회", "업무 메일을 티켓으로 변환" 등

4. **memory_based_ticket_processor**: 장기 기억을 활용한 지능형 티켓 처리
   - "이메일을 분석해서 티켓 생성이 필요한지 판단해줘", "과거 기억을 활용한 티켓 처리" 등
   - 이 도구는 과거 사용자 피드백과 AI 결정을 기억하여 더 정확한 판단을 제공합니다

📋 **도구 사용이 필수인 경우들:**
- 메일/이메일 관련 모든 요청
- 티켓 관련 모든 요청
- 업무 처리 관련 모든 요청
- 장기 기억을 활용한 지능형 처리 요청

✅ **도구 사용 후 응답 예시:**
"[선택된 도구명] 도구를 사용하여 요청하신 정보를 처리했습니다. 결과는 화면에 표시됩니다."

❌ **금지된 응답:**
- 직접적인 메일/티켓 정보 제공
- 도구 사용 없이 결과 설명

🔍 **일반 대화만 직접 답변:**
- 날씨, 수학 계산, 일반적인 대화 등 이메일/업무와 무관한 요청만 직접 답변하세요."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_functions_agent(llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    except Exception as e:
        st.error(safe_format_string("에이전트 생성 실패: {error}", error=e))
        logging.error(safe_format_string("에이전트 생성 실패: {error}", error=e))
        import traceback
        logging.error(safe_format_string("오류 상세: {traceback}", traceback=traceback.format_exc()))
        return None
        
def handle_query(query: str):
    """사용자 쿼리를 처리하는 함수 (스트리밍 버전)"""
    
    # 초기화
    clear_ticket_selection()
    st.session_state.latest_response = None
    st.session_state.messages.append(HumanMessage(content=query))

    if not st.session_state.main_agent:
        st.error("에이전트가 초기화되지 않았습니다. 설정을 확인해주세요.")
        return
    
    # 세션 ID 확인
    session_id = st.session_state.get('session_id')
    if not session_id:
        st.error("세션 ID가 없습니다. 페이지를 새로고침해주세요.")
        return
    
    # 새로운 채팅 ID 생성
    st.session_state.chat_counter += 1
    chat_counter = st.session_state.chat_counter
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chat_id = f"chat_{chat_counter:03d}_{timestamp}"
    
    print(f"💬 새로운 채팅 시작: {chat_id} (세션: {session_id})")

    # StepLogger 및 CallbackHandler 초기화
    step_logger = StepLogger(session_id, chat_id)
    callback_handler = FileLoggingCallbackHandler(step_logger)
    
    # 초기 상태를 파일에 저장
    callback_handler._update_status_file(
        status="시작",
        step="초기화 중...",
        message="🔄 처리 시작"
    )
    
    # 실시간 출력을 위한 placeholder 생성
    output_placeholder = st.empty()
    status_placeholder = st.empty()
    
    try:
        # 에이전트 스트리밍 실행
        chat_history = st.session_state.messages[:-1]  # 현재 입력을 제외한 히스토리
        current_output = ""
        tool_output_str = None
        final_response = None
        
        # 스트리밍 처리
        for chunk in st.session_state.main_agent.stream({
            "input": query,
            "chat_history": chat_history
        }, config={'callbacks': [callback_handler]}):
            
            # 실시간 상태 업데이트
            if "intermediate_steps" in chunk:
                # 중간 단계 결과 처리
                steps = chunk["intermediate_steps"]
                if steps:
                    latest_step = steps[-1]
                    if len(latest_step) >= 2:
                        tool_output_str = latest_step[1]
                        # 도구 실행 결과를 실시간으로 표시
                        with status_placeholder.container():
                            st.info(f"🔧 도구 실행 중: {latest_step[0]}")
                            if isinstance(tool_output_str, str) and len(tool_output_str) > 100:
                                st.text_area("도구 결과", tool_output_str[:500] + "...", height=100, disabled=True)
                            else:
                                st.text_area("도구 결과", str(tool_output_str), height=100, disabled=True)
            
            # 출력 내용 실시간 업데이트
            if "output" in chunk:
                current_output += chunk["output"]
                final_response = chunk
                
                # 실시간으로 출력 내용 표시
                with output_placeholder.container():
                    st.markdown("### 🤖 AI 응답 (실시간)")
                    st.markdown(current_output)
                    
                    # 처리 중임을 나타내는 인디케이터
                    if not chunk.get("end", False):
                        st.info("🔄 처리 중...")
        
        # 최종 결과 처리
        if tool_output_str:
            logging.info(safe_format_string("도구 실행 결과: {tool_output_str}", tool_output_str=tool_output_str))
            try:
                response_data = json.loads(tool_output_str)
                
                # UI 모드 결정 및 저장
                ui_mode = determine_ui_mode(query, response_data)
                response_data['ui_mode'] = ui_mode
                st.session_state.latest_response = response_data
                
                logging.info(safe_format_string("UI 모드 결정: {ui_mode}, display_mode: {display_mode}", ui_mode=ui_mode, display_mode=response_data.get('display_mode')))
                logging.info(safe_format_string("latest_response 설정 완료: {latest_response}", latest_response=st.session_state.get('latest_response') is not None))
                
                # 화면에 표시될 최종 AI 답변 생성
                final_message = final_response.get("output", "결과를 확인해주세요.") if final_response else "결과를 확인해주세요."
                st.session_state.messages.append(AIMessage(content=final_message))
                
                # 최종 완료 상태 표시
                with status_placeholder.container():
                    st.success("✅ 처리 완료!")
                    
            except json.JSONDecodeError as e:
                logging.error(safe_format_string("JSON 파싱 오류: {error}, tool_output_str: {tool_output_str}", error=e, tool_output_str=tool_output_str))
                st.error(safe_format_string("응답 데이터 파싱 오류: {error}", error=e))
            except Exception as e:
                logging.error(safe_format_string("응답 처리 오류: {error}", error=e))
                st.error(safe_format_string("응답 처리 중 오류 발생: {error}", error=e))
        else:
            logging.info(safe_format_string("도구가 사용되지 않음. LLM 직접 응답: {output}", output=final_response.get('output') if final_response else "없음"))
            # 도구를 사용하지 않은 일반 답변
            final_message = final_response.get("output", "응답을 생성할 수 없습니다.") if final_response else "응답을 생성할 수 없습니다."
            st.session_state.messages.append(AIMessage(content=final_message))
            
            # 최종 완료 상태 표시
            with status_placeholder.container():
                st.success("✅ 처리 완료!")

    except Exception as e:
        error_msg = safe_format_string("처리 중 오류 발생: {error}", error=e)
        st.error(error_msg)
        logging.error(error_msg)
        st.session_state.messages.append(AIMessage(content=error_msg))
        
        # 오류 상태를 파일에 저장
        callback_handler._update_status_file(
            status="오류",
            step=f"오류 발생: {str(e)}",
            message="❌ 처리 중 오류가 발생했습니다"
        )
        
        # 오류 상태 표시
        with status_placeholder.container():
            st.error("❌ 처리 중 오류가 발생했습니다")

def main():
    """메인 애플리케이션 함수"""
    # 환경변수 확인 및 설정 (.env 파일에서 자동 로드됨)
    required_env_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", 
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        st.error(safe_format_string("필수 환경변수가 설정되지 않았습니다: {missing_vars}", missing_vars=', '.join(missing_vars)))
        st.info("프로젝트 루트의 .env 파일을 확인해주세요.")
        return
    
    init_session_state()

    st.title("🤖 AI 메일 어시스턴트")
    
    with st.sidebar:
        st.header("🔗 연결 설정")
        provider = st.session_state.email_provider
        if st.session_state.email_connected:
            st.success(safe_format_string("✅ {provider} 연결됨", provider=provider.upper()))
        else:
            st.error(safe_format_string("❌ {provider} 미연결", provider=provider.upper()))
            if st.button("이메일 연결"):
                status = get_email_provider_status(provider)
                st.session_state.email_connected = status.get('is_connected', False)
                st.rerun()
        
        st.markdown("---")
        st.header("🚀 빠른 액션")
        quick_actions = [
            ("안읽은 메일 3개 보여줘", "view"),
            ("오늘 처리할 티켓 목록", "process_tickets")
        ]
        for label, _ in quick_actions:
            if st.button(label, use_container_width=True, disabled=not st.session_state.email_connected):
                handle_query(label)

        if st.button("🗑️ 대화 초기화", use_container_width=True):
            init_session_state() # 모든 상태 초기화
            st.rerun()
        
        # 디버깅 섹션 추가
        st.markdown("---")
        st.subheader("🔍 디버깅 도구")
        
        # add_label_to_ticket 함수 테스트
        if st.button("🧪 add_label_to_ticket 함수 테스트"):
            st.write("🔍 add_label_to_ticket 함수 테스트 시작...")
            try:
                # 함수가 import되었는지 확인
                st.write(f"🔍 enhanced_ticket_ui에서 import된 함수들:")
                st.write(f"  - add_label_to_ticket: {add_label_to_ticket}")
                st.write(f"  - delete_label_from_ticket: {delete_label_from_ticket}")
                
                # 함수 타입 확인
                st.write(f"🔍 add_label_to_ticket 타입: {type(add_label_to_ticket)}")
                
                # 간단한 테스트 호출 (ticket_id=1, label="테스트")
                st.write("🔍 테스트 함수 호출 시도...")
                test_result = add_label_to_ticket(1, "테스트레이블")
                st.write(f"🔍 테스트 결과: {test_result}")
                
            except Exception as e:
                st.error(f"❌ 테스트 중 오류: {str(e)}")
                import traceback
                st.write(f"🔍 오류 상세: {traceback.format_exc()}")
        
        # delete_label_from_ticket 함수 테스트 추가
        if st.button("🧪 delete_label_from_ticket 함수 테스트"):
            st.write("🔍 delete_label_from_ticket 함수 테스트 시작...")
            try:
                # 함수가 import되었는지 확인
                st.write(f"🔍 delete_label_from_ticket 함수 상태:")
                st.write(f"  - 함수 객체: {delete_label_from_ticket}")
                st.write(f"  - 함수 타입: {type(delete_label_from_ticket)}")
                st.write(f"  - 함수 호출 가능: {callable(delete_label_from_ticket)}")
                
                # 간단한 테스트 호출 (ticket_id=1, label="테스트레이블")
                st.write("🔍 테스트 함수 호출 시도...")
                test_result = delete_label_from_ticket(1, "테스트레이블")
                st.write(f"🔍 테스트 결과: {test_result}")
                
            except Exception as e:
                st.error(f"❌ 테스트 중 오류: {str(e)}")
                import traceback
                st.write(f"🔍 오류 상세: {traceback.format_exc()}")
        
        # 현재 세션 상태 확인
        if st.button("📊 세션 상태 확인"):
            st.write("🔍 현재 세션 상태:")
            for key, value in st.session_state.items():
                if key != 'messages':  # messages는 너무 길어서 제외
                    st.write(f"  - {key}: {value}")
        
        # enhanced_ticket_ui 모듈 상태 확인
        if st.button("🔧 모듈 상태 확인"):
            st.write("🔍 enhanced_ticket_ui 모듈 상태:")
            try:
                import enhanced_ticket_ui
                st.write(f"  - 모듈 로드됨: {enhanced_ticket_ui}")
                st.write(f"  - add_label_to_ticket 함수: {getattr(enhanced_ticket_ui, 'add_label_to_ticket', '없음')}")
                st.write(f"  - delete_label_from_ticket 함수: {getattr(enhanced_ticket_ui, 'add_label_to_ticket', '없음')}")
            except Exception as e:
                st.error(f"❌ 모듈 확인 중 오류: {str(e)}")
        
        # 테스트용 티켓 생성 버튼 추가
        if st.button("🧪 테스트 티켓 생성"):
            st.write("🧪 테스트 티켓 생성 시작...")
            try:
                # test_ticket_creation_logic 함수 호출
                test_result = test_ticket_creation_logic("gmail")
                st.write(f"🧪 테스트 결과: {test_result}")
                
                if test_result.get('success'):
                    st.success(f"✅ 테스트 티켓 생성 성공! ID: {test_result.get('ticket_id')}")
                else:
                    st.error(f"❌ 테스트 티켓 생성 실패: {test_result.get('message', '알 수 없는 오류')}")
                    
            except Exception as e:
                st.error(f"❌ 테스트 티켓 생성 중 오류: {str(e)}")
                import traceback
                st.write(f"🔍 오류 상세: {traceback.format_exc()}")
        
        # 테스트용 메일 조회 버튼 추가
        if st.button("🧪 테스트 메일 조회"):
            st.write("🧪 테스트 메일 조회 시작...")
            try:
                # test_email_fetch_logic 함수 호출
                test_result = test_email_fetch_logic("gmail")
                st.write(f"🧪 테스트 결과: {test_result}")
                
                if test_result.get('success'):
                    if test_result.get('email_count', 0) > 0:
                        st.success(f"✅ 테스트 메일 조회 성공! {test_result.get('email_count')}개 메일 발견")
                        st.write(f"🔍 첫 번째 메일: {test_result.get('first_email')}")
                    else:
                        st.info(f"ℹ️ 테스트 메일 조회 성공! 안 읽은 메일이 없습니다")
                else:
                    st.error(f"❌ 테스트 메일 조회 실패: {test_result.get('error', '알 수 없는 오류')}")
                    
            except Exception as e:
                st.error(f"❌ 테스트 메일 조회 중 오류: {str(e)}")
                import traceback
                st.write(f"🔍 오류 상세: {traceback.format_exc()}")
        
        # 테스트용 업무 관련 메일 필터링 버튼 추가
        if st.button("🧪 테스트 업무 관련 메일 필터링"):
            st.write("🧪 테스트 업무 관련 메일 필터링 시작...")
            try:
                # test_work_related_filtering 함수 호출
                test_result = test_work_related_filtering()
                st.write(f"🧪 테스트 결과: {test_result}")
                
                if test_result.get('success'):
                    st.success(f"✅ 테스트 필터링 성공! {test_result.get('message')}")
                    st.write(f"🔍 총 메일: {test_result.get('total_emails')}개")
                    st.write(f"🔍 업무 관련: {test_result.get('work_related_count')}개")
                else:
                    st.error(f"❌ 테스트 필터링 실패: {test_result.get('error', '알 수 없는 오류')}")
                    
            except Exception as e:
                st.error(f"❌ 테스트 필터링 중 오류: {str(e)}")
                import traceback
                st.write(f"🔍 오류 상세: {traceback.format_exc()}")

    # 에이전트 초기화 (한 번만 실행)
    if st.session_state.main_agent is None:
        st.session_state.main_agent = create_main_agent()

    # --- 메인 페이지 ---
    
    # 탭 구조로 UI 분리
    tab1, tab2, tab3 = st.tabs(["🤖 AI 챗봇", "📎 첨부파일 임베더", "🎫 Jira 연동"])
    
    # 탭 1: AI 챗봇
    with tab1:
        # 세션 정보 표시
        session_id = st.session_state.get('session_id', 'N/A')
        chat_counter = st.session_state.get('chat_counter', 0)
        st.info(f"🆔 **현재 세션**: {session_id} | 💬 **채팅 수**: {chat_counter}")
        
        # 자동 리프레시 설정 (실시간 업데이트를 위해)
        session_id = st.session_state.get('session_id')
        if session_id:
            status_file = f"logs/{session_id}/current_status.json"
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                    
                    # 완료 상태가 아니면 자동 새로고침
                    if status_data.get('status') != "완료":
                        # 자동 새로고침을 위한 JavaScript 코드
                        st.markdown("""
                        <script>
                        // 2초마다 자동 새로고침
                        setTimeout(function() {
                            window.location.reload();
                        }, 2000);
                        </script>
                        """, unsafe_allow_html=True)
                        
                        # 또는 Streamlit의 자동 새로고침
                        st.markdown("🔄 **자동 새로고침 중... (2초마다)**")
                        
                except Exception as e:
                    pass
        
        # 1. 채팅 기록 표시
        for message in st.session_state.messages:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(message.content)

        # 2. 실시간 처리 상태 표시
        session_id = st.session_state.get('session_id')
        if session_id:
            status_file = f"logs/{session_id}/current_status.json"
            
            # 상태 파일이 존재하면 읽어서 표시
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                    
                    status = status_data.get('status', '')
                    step = status_data.get('step', '')
                    message = status_data.get('message', '')
                    timestamp = status_data.get('timestamp', '')
                    
                    # 완료 상태가 아니면 실시간 상태 표시
                    if status != "완료":
                        with st.container():
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
                            elif status == "오류":
                                st.error(f"❌ {step}")
                            
                            # 타임스탬프 표시
                            if timestamp:
                                time_str = timestamp[11:19] if len(timestamp) > 19 else timestamp
                                st.caption(f"🕐 {time_str}")
                            
                            # 메시지 표시
                            if message:
                                st.text(f"📝 {message}")
                            
                            # 실시간 업데이트 안내
                            st.markdown("---")
                            st.markdown("""
                            **💡 실시간 진행상황을 보려면:**
                            - **F5** 키를 눌러 새로고침하세요
                            - 또는 아래 **새로고침 버튼**을 클릭하세요
                            """)
                            
                            # 새로고침 버튼과 자동 새로고침 옵션
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                if st.button("🔄 수동 새로고침", key="refresh_status"):
                                    st.rerun()
                            
                            with col2:
                                if st.checkbox("🔄 자동 새로고침 (3초마다)", key="auto_refresh"):
                                    st.markdown("""
                                    <script>
                                    setTimeout(function() {
                                        window.location.reload();
                                    }, 3000);
                                    </script>
                                    """, unsafe_allow_html=True)
                                    st.info("자동 새로고침이 활성화되었습니다.")
                    
                    # 완료 상태면 상태 파일 삭제
                    elif status == "완료":
                        try:
                            os.remove(status_file)
                        except:
                            pass
                            
                except Exception as e:
                    st.error(f"상태 파일 읽기 오류: {e}")

        # 3. 채팅 입력
        if prompt := st.chat_input("메시지를 입력하세요..."):
            # 실시간 상태 표시를 위한 컨테이너 생성
            status_placeholder = st.empty()
            
            # 처리 시작 상태 표시
            with status_placeholder.container():
                st.markdown("### 🔄 실시간 처리 상태")
                st.info("🔄 처리를 시작합니다...")
                try:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    st.caption(f"🕐 {current_time}")
                except Exception as e:
                    st.caption("🕐 시간 표시 오류")
                    print(f"시간 표시 오류: {e}")
                
                # 자동 새로고침 안내
                st.markdown("""
                **💡 실시간 진행상황을 보려면:**
                - 브라우저에서 **F5** 키를 눌러 새로고침하세요
                - 또는 **새로고침 버튼**을 클릭하세요
                """)
                
                # 새로고침 버튼
                col1, col2 = st.columns([1, 2])
                with col1:
                    if st.button("🔄 수동 새로고침", key="manual_refresh"):
                        st.rerun()
                with col2:
                    if st.checkbox("🔄 자동 새로고침 (3초마다)", key="auto_refresh"):
                        st.markdown("""
                        <script>
                        setTimeout(function() {
                            window.location.reload();
                        }, 3000);
                        </script>
                        """, unsafe_allow_html=True)
                        st.info("자동 새로고침이 활성화되었습니다.")
            
            # 실제 처리 실행
            handle_query(prompt)

        # 4. 최신 응답 데이터가 있으면 UI 컴포넌트 렌더링
        st.markdown("---")
        st.subheader("🔍 디버깅 정보")
        
        # 세션 상태 확인
        st.write("**세션 상태:**")
        st.write(safe_format_string("- latest_response 존재: {latest_response}", latest_response=st.session_state.get('latest_response') is not None))
        st.write(safe_format_string("- messages 개수: {count}", count=len(st.session_state.get('messages', []))))
        
        if response_data := st.session_state.get('latest_response'):
            display_mode = response_data.get('display_mode')
            ui_mode = response_data.get('ui_mode', 'text_only')
            
            st.success(safe_format_string("✅ 응답 데이터 발견: display_mode={display_mode}, ui_mode={ui_mode}", display_mode=display_mode, ui_mode=ui_mode))
            st.json(response_data)
            
            if display_mode == 'tickets':
                if ui_mode == 'button_list':
                    # enhanced_ticket_ui의 함수 사용
                    display_ticket_list_with_sidebar(response_data.get('tickets', []), 'button_list')
                else:
                    # enhanced_ticket_ui의 테이블 형태 사용
                    display_ticket_list_with_sidebar(response_data.get('tickets', []), 'table')

                # 업무용이 아닌 메일 표시 추가
                non_work_emails = response_data.get('non_work_emails', [])
                if non_work_emails:
                    st.markdown("---")
                    from non_work_emails_ui import display_non_work_emails
                    display_non_work_emails(non_work_emails)
                
                # 선택된 티켓이 있으면 상세 정보 표시
                if 'selected_ticket' in st.session_state and st.session_state.selected_ticket:
                    st.markdown("---")
                    # enhanced_ticket_ui의 display_ticket_detail 함수 사용
                    display_ticket_detail(st.session_state.selected_ticket)
                    
                    # 추가: 레이블 관리 기능 직접 구현
                    st.markdown("---")
                    st.subheader("🏷️ 레이블 관리 (직접 구현)")
                    
                    # 현재 티켓 정보
                    current_ticket = st.session_state.selected_ticket
                    ticket_id = current_ticket.get('id') or current_ticket.get('ticket_id')
                    
                    if ticket_id:
                        # 새 레이블 추가
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            new_label = st.text_input("새 레이블 입력", key=f"new_label_{ticket_id}")
                        with col2:
                            if st.button("레이블 추가", key=f"add_label_{ticket_id}"):
                                st.write("🔍 버튼 클릭됨! 함수 호출 시작...")
                                print(f"🔍 langchain_chatbot_app.py에서 레이블 추가 버튼 클릭됨: ticket_id={ticket_id}")
                                
                                if new_label and new_label.strip():
                                    st.write(f"🔍 입력된 레이블: '{new_label.strip()}'")
                                    print(f"🔍 입력된 레이블: '{new_label.strip()}'")
                                    
                                    try:
                                        st.write("🔍 add_label_to_ticket 함수 호출 중...")
                                        print(f"🔍 add_label_to_ticket 함수 호출 시작: ticket_id={ticket_id}, label='{new_label.strip()}'")
                                        
                                        # add_label_to_ticket 함수 직접 호출
                                        success = add_label_to_ticket(int(ticket_id), new_label.strip())
                                        
                                        st.write(f"🔍 함수 호출 결과: {success}")
                                        print(f"🔍 add_label_to_ticket 함수 호출 결과: {success}")
                                        
                                        if success:
                                            st.success(f"레이블 '{new_label.strip()}' 추가 완료!")
                                            st.session_state.refresh_trigger += 1
                                            st.write("🔍 refresh_trigger 증가됨")
                                        else:
                                            st.error("레이블 추가 실패")
                                    except Exception as e:
                                        st.error(f"레이블 추가 중 오류: {str(e)}")
                                        st.write(f"🔍 오류 상세: {str(e)}")
                                        print(f"❌ 레이블 추가 중 오류: {str(e)}")
                                        import traceback
                                        print(f"❌ 오류 상세: {traceback.format_exc()}")
                                else:
                                    st.warning("레이블을 입력해주세요")
                                    st.write("🔍 레이블이 입력되지 않음")
                        
                        # 현재 레이블 표시 및 삭제 기능
                        st.write("**현재 레이블:**")
                        
                        # 테스트용 간단한 삭제 버튼 추가
                        st.write("🔍 **테스트용 삭제 버튼:**")
                        if st.button("🧪 테스트 삭제 (ticket_id=1, label='테스트')", key="test_delete_button"):
                            st.write("🔍 테스트 삭제 버튼 클릭됨!")
                            try:
                                test_result = delete_label_from_ticket(1, "테스트")
                                st.write(f"🔍 테스트 삭제 결과: {test_result}")
                            except Exception as e:
                                st.error(f"❌ 테스트 삭제 오류: {str(e)}")
                        
                        st.write("---")
                        try:
                            from sqlite_ticket_models import SQLiteTicketManager
                            from datetime import datetime
                            ticket_manager = SQLiteTicketManager()
                            current_ticket_obj = ticket_manager.get_ticket_by_id(int(ticket_id))
                            
                            if current_ticket_obj and current_ticket_obj.labels:
                                st.write(f"🔍 총 {len(current_ticket_obj.labels)}개의 레이블 발견")
                                for idx, label in enumerate(current_ticket_obj.labels):
                                    st.write(f"🔍 레이블 {idx}: '{label}' 처리 중...")
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(f"🏷️ {label}")
                                    with col2:
                                        # 간단한 키로 삭제 버튼 생성
                                        delete_button_key = f"del_{ticket_id}_{idx}"
                                        st.write(f"🔍 삭제 버튼 키: {delete_button_key}")
                                        st.write(f"🔍 버튼 생성 시도...")
                                        
                                        if st.button("🗑️ 삭제", key=delete_button_key, type="secondary"):
                                            st.write("🔍 🗑️ 삭제 버튼 클릭됨!")
                                            st.write(f"🔍 삭제할 레이블: '{label}'")
                                            st.write(f"🔍 티켓 ID: {ticket_id}")
                                            print(f"🔍 langchain_chatbot_app.py에서 레이블 삭제 버튼 클릭됨: ticket_id={ticket_id}, label='{label}'")
                                            
                                            # 함수 존재 확인
                                            st.write("🔍 delete_label_from_ticket 함수 확인:")
                                            st.write(f"  - 함수 객체: {delete_label_from_ticket}")
                                            st.write(f"  - 함수 타입: {type(delete_label_from_ticket)}")
                                            st.write(f"  - 함수 호출 가능: {callable(delete_label_from_ticket)}")
                                            
                                            try:
                                                # delete_label_from_ticket 함수 직접 호출
                                                success = delete_label_from_ticket(int(ticket_id), label)
                                                
                                                st.write(f"🔍 삭제 함수 호출 결과: {success}")
                                                print(f"🔍 delete_label_from_ticket 함수 호출 결과: {success}")
                                                
                                                if success:
                                                    st.success(f"레이블 '{label}' 삭제 완료!")
                                                    st.session_state.refresh_trigger += 1
                                                    st.write("🔍 refresh_trigger 증가됨")
                                                else:
                                                    st.error("레이블 삭제 실패")
                                            except Exception as e:
                                                st.error(f"레이블 삭제 중 오류: {str(e)}")
                                                st.write(f"🔍 오류 상세: {str(e)}")
                                                print(f"❌ 레이블 삭제 중 오류: {str(e)}")
                                                import traceback
                                                print(f"❌ 오류 상세: {traceback.format_exc()}")
                            else:
                                st.info("설정된 레이블이 없습니다")
                        except Exception as e:
                            st.warning(f"레이블 로드 실패: {str(e)}")
                        
            elif display_mode == 'mail_list':
                if ui_mode == 'button_list':
                    create_mail_list_with_sidebar(response_data.get('mail_list', []), "요청하신 메일 목록")
                else:
                    create_mail_list_ui(response_data.get('mail_list', []), "요청하신 메일 목록")
                    
            elif display_mode in ['no_emails', 'error']:
                st.info(response_data.get('message', '알 수 없는 응답입니다.'))
        else:
            st.info("🔍 디버깅: latest_response가 없습니다.")
    
    # 탭 2: 첨부파일 임베더
    with tab2:
        st.header("📎 첨부파일 임베더")
        st.markdown("문서 파일을 업로드하면 AI가 분석하고 벡터 데이터베이스에 저장합니다.")
        
        # 파일 업로더
        uploaded_files = st.file_uploader(
            "문서 파일을 선택하세요",
            type=['docx', 'pptx', 'pdf', 'xlsx', 'txt', 'md', 'csv', 'scds', 'xml'],
            accept_multiple_files=True,
            help="여러 파일을 동시에 선택할 수 있습니다. 파일이 손상되지 않았는지 확인해주세요."
        )
        
        # 파일 업로드 가이드
        with st.expander("📋 파일 업로드 가이드"):
            st.markdown("""
            **지원 파일 형식:**
            - **문서**: DOCX, PPTX, PDF
            - **스프레드시트**: XLSX, CSV  
            - **텍스트**: TXT, MD
            - **데이터**: XML (JIRA RSS, 일반 XML)
            - **바이너리**: SCDS (System Configuration Data Set)
            
            **주의사항:**
            - 파일이 손상되지 않았는지 확인
            - 파일 크기는 100MB 이하 권장
            - 한글 파일명 지원
            - 파일 업로드 후 크기가 0이 아닌지 확인
            """)
            
            st.warning("""
            **문제 해결:**
            - 파일이 손상된 경우: 원본 파일을 다시 다운로드
            - 업로드 실패 시: 브라우저 새로고침 후 재시도
            - 큰 파일: 네트워크 연결 상태 확인
            """)
        
        # 벡터DB 관리 기능
        st.markdown("---")
        st.subheader("🗄️ 벡터DB 관리")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 벡터DB 통계 조회", use_container_width=True):
                try:
                    if 'system_info_db' not in st.session_state:
                        from vector_db_models import SystemInfoVectorDBManager
                        st.session_state.system_info_db = SystemInfoVectorDBManager()
                    
                    stats = st.session_state.system_info_db.get_collection_stats()
                    
                    if "error" not in stats:
                        st.success("✅ 벡터DB 통계 조회 성공!")
                        
                        # 통계 표시 (안전한 키 접근)
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("총 청크 수", stats.get('total_chunks', 0))
                        with col_b:
                            st.metric("총 파일 수", stats.get('total_files', 0))
                        with col_c:
                            st.metric("컬렉션명", stats.get('collection_name', 'system_info'))
                        
                        # 파일 타입별 통계
                        file_types = stats.get('file_types', {})
                        if file_types:
                            st.subheader("📁 파일 타입별 통계")
                            for file_type, count in file_types.items():
                                st.info(safe_format_string("• {file_type}: {count}개 청크", file_type=file_type, count=count))
                    else:
                        st.error(safe_format_string("❌ 벡터DB 통계 조회 실패: {error}", error=stats['error']))
                except Exception as e:
                    st.error(safe_format_string("❌ 벡터DB 통계 조회 중 오류: {error}", error=str(e)))
        
        with col2:
            if st.button("🗑️ 벡터DB 초기화", use_container_width=True, type="secondary"):
                try:
                    if 'system_info_db' in st.session_state:
                        st.session_state.system_info_db.reset_collection()
                        st.success("✅ 벡터DB가 초기화되었습니다!")
                    else:
                        st.warning("⚠️ 벡터DB가 초기화되지 않았습니다.")
                except Exception as e:
                    st.error(safe_format_string("❌ 벡터DB 초기화 중 오류: {error}", error=str(e)))
        
        # 벡터DB 검색 기능
        st.markdown("---")
        st.subheader("🔍 벡터DB 검색")
        
        search_query = st.text_input("검색어를 입력하세요", placeholder="예: 시스템 아키텍처, UI 설계...")
        search_file_type = st.selectbox(
            "파일 타입 필터 (선택사항)",
            ["전체", "pptx", "docx", "pdf", "xlsx", "txt", "md", "csv", "scds"]
        )
        
        if st.button("🔍 검색 시작", use_container_width=True) and search_query:
            try:
                if 'system_info_db' not in st.session_state:
                    from vector_db_models import SystemInfoVectorDBManager
                    st.session_state.system_info_db = SystemInfoVectorDBManager()
                
                # 파일 타입 필터 적용
                file_type_filter = None if search_file_type == "전체" else search_file_type
                
                search_results = st.session_state.system_info_db.search_similar_chunks(
                    query=search_query,
                    n_results=10,
                    file_type=file_type_filter
                )
                
                if search_results:
                    st.success(safe_format_string("✅ 검색 완료! {count}개 결과를 찾았습니다.", count=len(search_results)))
                    
                    # 검색 결과 표시
                    for i, result in enumerate(search_results, 1):
                        with st.expander(safe_format_string("🔍 검색 결과 {i}", i=i)):
                            metadata = result['metadata']
                            st.write(safe_format_string("**파일명:** {file_name}", file_name=metadata.get('file_name', '알 수 없음')))
                            st.write(safe_format_string("**섹션:** {section_title}", section_title=metadata.get('section_title', '제목 없음')))
                            st.write(safe_format_string("**파일 타입:** {file_type}", file_type=metadata.get('file_type', '알 수 없음')))
                            st.write(safe_format_string("**아키텍처:** {architecture}", architecture=metadata.get('architecture', 'unknown')))
                            
                            # 유사도 점수
                            similarity = result.get('similarity_score', 0)
                            if similarity is not None:
                                st.progress(similarity)
                                st.write(safe_format_string("**유사도:** {similarity:.3f}", similarity=similarity))
                            
                            # 텍스트 내용
                            text_content = result['text_content']
                            if text_content:
                                st.text_area("📝 내용", text_content, height=100, disabled=True)
                else:
                    st.info("🔍 검색 결과가 없습니다.")
                    
            except Exception as e:
                st.error(safe_format_string("❌ 검색 중 오류 발생: {error}", error=str(e)))
        
        if uploaded_files:
            st.success(safe_format_string("✅ {count}개 파일이 업로드되었습니다.", count=len(uploaded_files)))
            
            # 파일 목록 표시
            st.subheader("📋 업로드된 파일 목록")
            for i, file in enumerate(uploaded_files, 1):
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.write(safe_format_string("**{i}. {name}**", i=i, name=file.name))
                with col2:
                    st.write(safe_format_string("크기: {size:.1f} KB", size=file.size / 1024))
                with col3:
                    st.write(safe_format_string("타입: {type}", type=file.type))
                with col4:
                    # 파일 상태 표시
                    if file.size > 0:
                        st.success("✅ 정상")
                    else:
                        st.error("❌ 빈 파일")
            
            # 파일 검증 요약
            valid_files = [f for f in uploaded_files if f.size > 0]
            if len(valid_files) != len(uploaded_files):
                st.warning(safe_format_string("⚠️ {count}개 파일이 비어있습니다.", count=len(uploaded_files) - len(valid_files)))
                st.info("빈 파일은 처리에서 제외됩니다.")
            
            # 분석 및 임베딩 시작 버튼
            if st.button("🚀 분석 및 임베딩 시작", type="primary", use_container_width=True):
                if 'file_processor' not in st.session_state:
                    st.session_state.file_processor = FileProcessor()
                
                # 결과를 저장할 리스트
                processing_results = []
                
                # 유효한 파일만 처리 (빈 파일 제외)
                valid_files = [f for f in uploaded_files if f.size > 0]
                if len(valid_files) == 0:
                    st.error("❌ 처리할 수 있는 파일이 없습니다. 모든 파일이 비어있습니다.")
                    return
                
                st.info(safe_format_string("📊 {count}개 유효한 파일을 처리합니다.", count=len(valid_files)))
                
                # 각 파일 처리
                for file in valid_files:
                    # 임시 디렉토리 생성 및 파일 저장
                    temp_dir = tempfile.mkdtemp()
                    try:
                        # 원본 파일 확장자 유지
                        file_ext = Path(file.name).suffix.lower()
                        temp_file_path = os.path.join(temp_dir, safe_format_string("uploaded_file{ext}", ext=file_ext))
                        
                        # 파일 내용을 임시 파일에 저장
                        with open(temp_file_path, 'wb') as f:
                            f.write(file.getvalue())
                        
                        # 파일 존재 확인
                        if not os.path.exists(temp_file_path):
                            raise Exception(safe_format_string("임시 파일 생성 실패: {path}", path=temp_file_path))
                        
                        # 파일 크기 확인
                        file_size = os.path.getsize(temp_file_path)
                        if file_size == 0:
                            raise Exception("업로드된 파일이 비어있습니다")
                        
                        st.info(safe_format_string("📁 임시 파일 생성: {path} (크기: {size} bytes)", path=temp_file_path, size=file_size))
                        
                        # 실제 파일 형식 감지
                        detected_type = detect_file_type_by_content(temp_file_path)
                        st.info(safe_format_string("🔍 감지된 실제 파일 형식: {type}", type=detected_type))
                        
                        # 확장자와 실제 형식이 다른 경우 경고
                        if detected_type != file_ext:
                            st.warning(safe_format_string("⚠️  파일 확장자({ext})와 실제 형식({type})이 다릅니다!", ext=file_ext, type=detected_type))
                            st.info(safe_format_string("💡 파일을 {type} 확장자로 다시 업로드하거나, 원본 파일을 확인해주세요.", type=detected_type))
                        
                        # 파일 타입별 추가 검증
                        if file_ext == '.pptx':
                            # PPTX 파일 헤더 검증
                            with open(temp_file_path, 'rb') as f:
                                header = f.read(4)
                                if header != b'PK\x03\x04':
                                    # 더 자세한 오류 정보 제공
                                    st.error("❌ PPTX 파일 헤더 검증 실패")
                                    st.error(safe_format_string("예상: PK 03 04, 실제: {header}", header=' '.join(safe_format_string('{b:02x}', b=b) for b in header)))
                                    
                                    # 파일 내용 일부 확인
                                    f.seek(0)
                                    first_32_bytes = f.read(32)
                                    st.error(safe_format_string("파일 시작 부분: {bytes}", bytes=' '.join(safe_format_string('{b:02x}', b=b) for b in first_32_bytes)))
                                    
                                    # 파일 형식 추측 시도
                                    st.info("🔍 파일 형식 추측 중...")
                                    f.seek(0)
                                    full_header = f.read(64)
                                    
                                    # 다양한 파일 형식 확인
                                    if full_header.startswith(b'%PDF'):
                                        st.warning("💡 이 파일은 PDF 파일로 보입니다. 확장자를 .pdf로 변경해주세요.")
                                    elif full_header.startswith(b'\xff\xfe') or full_header.startswith(b'\xfe\xff'):
                                        st.warning("💡 이 파일은 유니코드 텍스트 파일로 보입니다.")
                                    elif full_header.startswith(b'\xef\xbb\xbf'):
                                        st.warning("💡 이 파일은 UTF-8 BOM 텍스트 파일로 보입니다.")
                                    elif all(32 <= b <= 126 or b in [9, 10, 13] for b in full_header[:32]):
                                        st.warning("💡 이 파일은 일반 텍스트 파일로 보입니다.")
                                    else:
                                        st.warning("💡 이 파일은 알 수 없는 바이너리 파일입니다.")
                                    
                                    # 파일 크기 정보
                                    file_size = os.path.getsize(temp_file_path)
                                    st.info(safe_format_string("📏 파일 크기: {size:,} bytes ({size_kb:.1f} KB)", size=file_size, size_kb=file_size/1024))
                                    
                                    raise Exception("올바른 PPTX 파일이 아닙니다 (ZIP 헤더 없음). 파일이 손상되었거나 다른 형식일 수 있습니다.")
                            st.info("✅ PPTX 파일 헤더 검증 완료")
                        
                        elif file_ext == '.docx':
                            # DOCX 파일 헤더 검증
                            with open(temp_file_path, 'rb') as f:
                                header = f.read(4)
                                if header != b'PK\x03\x04':
                                    st.error("❌ DOCX 파일 헤더 검증 실패")
                                    st.error(safe_format_string("예상: PK 03 04, 실제: {header}", header=' '.join(safe_format_string('{b:02x}', b=b) for b in header)))
                                    
                                    # 파일 형식 추측
                                    f.seek(0)
                                    full_header = f.read(64)
                                    if full_header.startswith(b'%PDF'):
                                        st.warning("💡 이 파일은 PDF 파일로 보입니다. 확장자를 .pdf로 변경해주세요.")
                                    elif full_header.startswith(b'\x50\x4b\x03\x04'):
                                        st.warning("💡 이 파일은 PPTX 파일로 보입니다. 확장자를 .pptx로 변경해주세요.")
                                    
                                    raise Exception("올바른 DOCX 파일이 아닙니다 (ZIP 헤더 없음). 파일이 손상되었거나 다른 형식일 수 있습니다.")
                            st.info("✅ DOCX 파일 헤더 검증 완료")
                        
                        elif file_ext == '.pdf':
                            # PDF 파일 헤더 검증
                            with open(temp_file_path, 'rb') as f:
                                header = f.read(4)
                                if header != b'%PDF':
                                    st.error("❌ PDF 파일 헤더 검증 실패")
                                    st.error(safe_format_string("예상: %PDF, 실제: {header}", header=' '.join(safe_format_string('{b:02x}', b=b) for b in header)))
                                    
                                    # 파일 형식 추측
                                    f.seek(0)
                                    full_header = f.read(64)
                                    if full_header.startswith(b'PK\x03\x04'):
                                        st.warning("💡 이 파일은 Office 문서(PPTX/DOCX/XLSX)로 보입니다. 확장자를 확인해주세요.")
                                    
                                    raise Exception("올바른 PDF 파일이 아닙니다 (PDF 헤더 없음). 파일이 손상되었거나 다른 형식일 수 있습니다.")
                            st.info("✅ PDF 파일 헤더 검증 완료")
                        
                        # 파일 처리
                        import time
                        start_time = time.time()
                        
                        with st.spinner(safe_format_string("📄 {name} 처리 중...", name=file.name)):
                            st.info(safe_format_string("🔍 FileProcessor 시작: {path}", path=temp_file_path))
                            
                            # 실제 형식에 따라 처리 방식 결정
                            if detected_type != file_ext:
                                st.info(safe_format_string("🔄 실제 형식({type})에 맞춰 처리 방식을 조정합니다.", type=detected_type))
                                
                                # 임시로 올바른 확장자로 파일 복사
                                corrected_file_path = temp_file_path.replace(file_ext, detected_type)
                                import shutil
                                shutil.copy2(temp_file_path, corrected_file_path)
                                st.info(safe_format_string("📝 수정된 파일 경로: {path}", path=corrected_file_path))
                                
                                # 수정된 파일로 처리
                                try:
                                    result = st.session_state.file_processor.process_file(corrected_file_path)
                                    st.info(safe_format_string("✅ FileProcessor 완료 (수정된 형식): {count}개 청크", count=len(result.get('chunks', [])) if result else 0))
                                except Exception as proc_error:
                                    st.error(safe_format_string("❌ FileProcessor 오류 (수정된 형식): {error}", error=str(proc_error)))
                                    raise proc_error
                            else:
                                # 원래 확장자로 처리
                                try:
                                    result = st.session_state.file_processor.process_file(temp_file_path)
                                    st.info(safe_format_string("✅ FileProcessor 완료: {count}개 청크", count=len(result.get('chunks', [])) if result else 0))
                                except Exception as proc_error:
                                    st.error(safe_format_string("❌ FileProcessor 오류: {error}", error=str(proc_error)))
                                    raise proc_error
                        
                        # 처리 시간 계산
                        processing_duration = time.time() - start_time
                        st.info(safe_format_string("⏱️ 파일 처리 소요 시간: {duration:.2f}초", duration=processing_duration))
                        
                        # 결과 처리 로직
                        if result and not result.get("error"):
                            # 임베딩 및 저장
                            chunks = result.get('chunks', [])
                            embed_result = embed_and_store_chunks(chunks, file.name, file.getvalue(), processing_duration)
                            
                            if embed_result["success"]:
                                # 중복 파일인 경우
                                if embed_result.get("duplicate", False):
                                    st.success(embed_result["message"])
                                    st.info(safe_format_string("🔍 파일 해시: {hash}", hash=embed_result.get('file_hash', '')[:16]))
                                else:
                                    st.success(embed_result["message"])
                                
                                # 결과 상세 정보를 expander로 표시
                                with st.expander(safe_format_string("📊 {name} 처리 결과 상세보기", name=file.name)):
                                    st.json(result)
                                    
                                    # 요약 정보
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("총 청크 수", embed_result["total_chunks"])
                                    with col2:
                                        st.metric("총 요소 수", embed_result["total_elements"])
                                    with col3:
                                        st.metric("텍스트 길이", embed_result["total_text_length"])
                                    
                                    # 아키텍처 정보
                                    st.subheader("🏗️ 처리 아키텍처")
                                    for arch in embed_result["architectures"]:
                                        st.info(safe_format_string("• {arch}", arch=arch))
                                    
                                    if embed_result["vision_analysis_count"] > 0:
                                        st.success(safe_format_string("👁️ Vision 분석 적용: {count}개 청크", count=embed_result['vision_analysis_count']))
                                    
                                    # 청크별 상세 정보
                                    st.subheader("📝 청크별 상세 정보")
                                    for i, chunk in enumerate(chunks, 1):
                                        with st.expander(safe_format_string("청크 {i}", i=i)):
                                            metadata = chunk.get('metadata', {})
                                            st.write(safe_format_string("**아키텍처:** {architecture}", architecture=metadata.get('architecture', 'unknown')))
                                            st.write(safe_format_string("**처리 방법:** {method}", method=metadata.get('processing_method', 'unknown')))
                                            st.write(safe_format_string("**Vision 분석:** {vision}", vision=metadata.get('vision_analysis', False)))
                                            st.write(safe_format_string("**요소 개수:** {count}", count=metadata.get('element_count', 0)))
                                            
                                            # text_chunk_to_embed 미리보기
                                            text_content = chunk.get('text_chunk_to_embed', '')
                                            if text_content:
                                                st.text_area(safe_format_string("📝 청크 {i} 내용", i=i), text_content, height=100, disabled=True)
                                            else:
                                                st.info("텍스트 내용이 없습니다 (단순 변환 방식)")
                                            
                                            # 요소 정보
                                            elements = metadata.get('elements', [])
                                            if elements:
                                                st.write("**요소 정보:**")
                                                for j, element in enumerate(elements[:5], 1):  # 처음 5개만 표시
                                                    st.write(safe_format_string("  {j}. {type}: {content}...", j=j, type=element.get('element_type', 'unknown'), content=str(element.get('content', ''))[:100]))
                                                if len(elements) > 5:
                                                    st.write(safe_format_string("  ... 외 {count}개", count=len(elements) - 5))
                                
                                processing_results.append({
                                    "file_name": file.name,
                                    "success": True,
                                    "result": embed_result
                                })
                            
                            else:
                                st.error(embed_result["message"])
                                processing_results.append({
                                    "file_name": file.name,
                                    "success": False,
                                    "error": embed_result.get("error", "알 수 없는 오류")
                                })
                        
                        else:
                            error_msg = result.get('message', '알 수 없는 오류') if result else '파일 처리 실패'
                            st.error(safe_format_string("❌ {name} 처리 실패: {error}", name=file.name, error=error_msg))
                            processing_results.append({
                                "file_name": file.name,
                                "success": False,
                                "error": error_msg
                            })
                    
                    except Exception as e:
                        st.error(safe_format_string("❌ {name} 처리 중 오류 발생: {error}", name=file.name, error=str(e)))
                        processing_results.append({
                            "file_name": file.name,
                            "success": False,
                            "error": str(e)
                        })
                    
                    finally:
                        # 임시 디렉토리 정리
                        try:
                            import shutil
                            shutil.rmtree(temp_dir)
                            st.success(safe_format_string("✅ {name} 임시 파일 정리 완료", name=file.name))
                        except Exception as cleanup_error:
                            st.warning(safe_format_string("⚠️  임시 파일 정리 실패: {error}", error=cleanup_error))
                
                # 전체 처리 결과 요약
                if processing_results:
                    st.markdown("---")
                    st.subheader("📊 전체 처리 결과 요약")
                    
                    successful = sum(1 for r in processing_results if r["success"])
                    total = len(processing_results)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("성공", successful)
                    with col2:
                        st.metric("실패", total - successful)
                    
                    if successful == total:
                        st.success("🎉 모든 파일이 성공적으로 처리되었습니다!")
                    elif successful > 0:
                        st.warning(safe_format_string("⚠️ {successful}/{total}개 파일이 성공적으로 처리되었습니다.", successful=successful, total=total))
                    else:
                        st.error("❌ 모든 파일 처리에 실패했습니다.")
                    
                    # 실패한 파일 목록
                    failed_files = [r for r in processing_results if not r["success"]]
                    if failed_files:
                        st.subheader("❌ 실패한 파일들")
                        for failed in failed_files:
                            st.error(safe_format_string("• {name}: {error}", name=failed['file_name'], error=failed['error']))
                    
                    # 벡터DB 통계 표시
                    if successful > 0:
                        st.markdown("---")
                        st.subheader("🗄️ 벡터DB 상태")
                        
                        try:
                            if 'system_info_db' in st.session_state:
                                stats = st.session_state.system_info_db.get_collection_stats()
                                
                                if "error" not in stats:
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("총 청크 수", stats['total_chunks'])
                                    with col2:
                                        st.metric("총 파일 수", stats['total_files'])
                                    with col3:
                                        st.metric("컬렉션명", stats.get('collection_name', 'system_info'))
                                    
                                    # 파일 타입별 통계
                                    if stats['file_types']:
                                        st.subheader("📁 파일 타입별 통계")
                                        for file_type, count in stats['file_types'].items():
                                            st.info(f"• {file_type}: {count}개 청크")
                                else:
                                    st.error(f"벡터DB 통계 조회 실패: {stats['error']}")
                            else:
                                st.info("벡터DB가 초기화되지 않았습니다.")
                        except Exception as e:
                            st.warning(f"벡터DB 통계 조회 중 오류: {str(e)}")
        else:
            st.info("📁 문서 파일을 업로드해주세요. 지원 형식: DOCX, PPTX, PDF, XLSX, TXT, MD, CSV")
    
    # 탭 3: Jira 연동
    with tab3:
        st.header("🎫 Jira 연동")
        st.markdown("Jira 프로젝트의 티켓 데이터를 벡터 데이터베이스에 동기화합니다.")
        
        # Jira 연결 상태 확인
        try:
            from jira_connector import JiraConnector
            from dotenv import load_dotenv
            
            # .env 파일 로드
            load_dotenv()
            
            # 환경 변수에서 Jira 설정 확인
            jira_url = os.getenv('JIRA_API_ENDPOINT', '').replace('/rest/api/2/', '')
            jira_email = os.getenv('JIRA_USER_EMAIL')
            jira_token = os.getenv('JIRA_API_TOKEN')
            
            if all([jira_url, jira_email, jira_token]):
                st.success("✅ .env 파일에서 Jira 설정을 자동으로 읽어왔습니다!")
                
                # 현재 설정 정보 표시
                with st.expander("🔍 현재 Jira 설정 정보"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Jira URL:** {jira_url}")
                        st.info(f"**사용자 이메일:** {jira_email}")
                    with col2:
                        st.info(f"**API 토큰:** {jira_token[:10]}...")
                        st.info("**상태:** 설정 완료")
                
                # 자동 동기화 버튼
                if st.button("🚀 자동 Jira 동기화 시작", use_container_width=True, type="primary"):
                    try:
                        with st.spinner("🔄 Jira 데이터 동기화 중..."):
                            # JiraConnector 인스턴스 생성 (인자 없이 자동 설정)
                            connector = JiraConnector()
                            
                            # 동기화 실행
                            sync_result = connector.sync_jira()
                            
                            if sync_result["success"]:
                                st.success(sync_result["message"])
                                
                                # 동기화 결과 상세 표시
                                with st.expander("📊 동기화 결과 상세보기"):
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("처리된 티켓", sync_result["tickets_processed"])
                                    with col2:
                                        st.metric("발견된 티켓", sync_result["total_tickets_found"])
                                    with col3:
                                        st.metric("동기화 시간", f"{sync_result['sync_duration']:.2f}초")
                                    
                                    # 동기화 정보
                                    st.subheader("🕒 동기화 정보")
                                    st.info(f"**시작 시간:** {sync_result['start_time']}")
                                    st.info(f"**완료 시간:** {sync_result['end_time']}")
                                    st.info(f"**마지막 동기화:** {sync_result['last_sync_time']}")
                                    
                                    # 성공 메시지
                                    if sync_result["tickets_processed"] > 0:
                                        st.success(f"🎉 {sync_result['tickets_processed']}개 티켓이 성공적으로 동기화되었습니다!")
                                    else:
                                        st.info("ℹ️ 동기화할 새로운 티켓이 없습니다.")
                                
                                # Jira 연결 상태 업데이트
                                st.session_state.jira_connected = True
                                
                            else:
                                st.error(sync_result["message"])
                                st.error(f"❌ 동기화 실패: {sync_result.get('error', '알 수 없는 오류')}")
                        
                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Jira 동기화 중 오류 발생: {error_msg}")
                        
                        # 에러 유형별 특별한 안내
                        if "429" in error_msg or "Rate Limit" in error_msg:
                            st.error("🚫 Rate Limit 초과!")
                            st.info("💡 Jira API 요청 한도를 초과했습니다.")
                            st.info("💡 해결 방법:")
                            st.info("1. 잠시 후 다시 시도해주세요 (자동으로 재시도됩니다)")
                            st.info("2. 대량의 티켓이 있는 경우 배치 크기를 줄여주세요")
                            st.info("3. 동기화 주기를 늘려주세요")
                            
                            # 자동 재시도 안내
                            st.warning("🔄 자동 재시도가 활성화되어 있습니다. 잠시 후 다시 시도해보세요.")
                            
                        elif "401" in error_msg or "Unauthorized" in error_msg:
                            st.error("🔐 인증 오류가 발생했습니다!")
                            st.info("💡 해결 방법:")
                            st.info("1. Jira API 토큰이 만료되었을 수 있습니다.")
                            st.info("2. [Atlassian 계정 설정](https://id.atlassian.com/manage-profile/security/api-tokens)에서 새 토큰을 생성하세요.")
                            st.info("3. .env 파일의 JIRA_API_TOKEN을 새 토큰으로 업데이트하세요.")
                            st.info("4. Jira 계정에 해당 프로젝트에 대한 접근 권한이 있는지 확인하세요.")
                            
                        elif "403" in error_msg or "권한 부족" in error_msg:
                            st.error("🚫 권한 부족!")
                            st.info("💡 Jira 프로젝트에 대한 접근 권한이 없습니다.")
                            st.info("💡 해결 방법:")
                            st.info("1. Jira 계정에 해당 프로젝트에 대한 읽기 권한이 있는지 확인하세요")
                            st.info("2. 프로젝트 관리자에게 권한 요청을 하세요")
                            st.info("3. API 토큰이 올바른 권한을 가지고 있는지 확인하세요")
                            
                        else:
                            st.info("💡 .env 파일의 Jira 설정을 확인해주세요.")
                            st.info("💡 네트워크 연결 상태를 확인해주세요.")
                
                # 수동 설정 옵션
                st.markdown("---")
                st.subheader("⚙️ 수동 설정 (선택사항)")
                st.info("기본 설정 외에 다른 Jira 인스턴스를 사용하려면 아래 폼을 사용하세요.")
                
            else:
                st.warning("⚠️ .env 파일에 Jira 설정이 완전하지 않습니다.")
                st.info("아래 폼을 통해 수동으로 Jira 연결 정보를 입력해주세요.")
            
        except ImportError:
            st.error("❌ Jira 라이브러리가 설치되지 않았습니다. `pip install jira` 명령으로 설치해주세요.")
            return
        
        # Gmail OAuth 상태 표시
        st.subheader("🔐 Gmail OAuth 상태")
        
        if gmail_oauth_ready:
            st.success("✅ Gmail OAuth 시스템이 정상적으로 초기화되었습니다.")
            st.info("💡 토큰이 만료되면 자동으로 OAuth 인증이 시작됩니다.")
            
            # Gmail 토큰 강제 갱신 버튼
            if st.button("🔄 Gmail 토큰 강제 갱신", type="secondary"):
                try:
                    with st.spinner("🔄 Gmail OAuth 토큰 갱신 중..."):
                        from gmail_api_client import GmailAPIClient
                        client = GmailAPIClient()
                        
                        if client.authenticate(force_refresh=True):
                            st.success("✅ Gmail 토큰 갱신 성공!")
                            st.info("💡 새로운 토큰으로 Gmail API를 사용할 수 있습니다.")
                            st.rerun()  # 페이지 새로고침
                        else:
                            st.error("❌ Gmail 토큰 갱신 실패")
                            
                except Exception as e:
                    st.error(f"❌ Gmail 토큰 갱신 중 오류: {e}")
        else:
            st.warning("⚠️  Gmail OAuth 시스템 초기화에 실패했습니다.")
            st.info("💡 Gmail API를 사용하려면 수동으로 인증을 진행해주세요.")
            
            # 수동 Gmail 인증 버튼
            if st.button("🔐 수동 Gmail 인증", type="secondary"):
                try:
                    with st.spinner("🔄 수동 Gmail 인증 진행 중..."):
                        from gmail_api_client import GmailAPIClient
                        client = GmailAPIClient()
                        
                        if client.authenticate(force_refresh=True):
                            st.success("✅ 수동 Gmail 인증 성공!")
                            st.info("💡 새로운 토큰으로 Gmail API를 사용할 수 있습니다.")
                            st.rerun()  # 페이지 새로고침
                        else:
                            st.error("❌ 수동 Gmail 인증 실패")
                            
                except Exception as e:
                    st.error(f"❌ 수동 Gmail 인증 중 오류: {e}")
        
        st.divider()
        
        # 수동 Jira 연동 정보 입력 폼
        with st.form("jira_connection_form"):
            st.subheader("🔗 수동 Jira 연결 정보")
            
            manual_jira_url = st.text_input(
                "Jira URL", 
                placeholder="https://your-domain.atlassian.net",
                help="Jira 서버의 URL을 입력하세요 (예: https://company.atlassian.net)",
                key="manual_jira_url"
            )
            
            manual_jira_email = st.text_input(
                "이메일 주소",
                placeholder="your-email@company.com",
                help="Jira 계정의 이메일 주소를 입력하세요",
                key="manual_jira_email"
            )
            
            manual_jira_token = st.text_input(
                "API 토큰",
                type="password",
                placeholder="API 토큰을 입력하세요",
                help="Jira API 토큰을 입력하세요. Atlassian 계정 설정에서 생성할 수 있습니다.",
                key="manual_jira_token"
            )
            
            # 폼 제출 버튼
            submit_button = st.form_submit_button("🚀 수동 Jira 동기화 시작", use_container_width=True)
            
            if submit_button:
                if not all([manual_jira_url, manual_jira_email, manual_jira_token]):
                    st.error("❌ 모든 필드를 입력해주세요.")
                else:
                    try:
                        # JiraConnector import 및 인스턴스 생성
                        with st.spinner("🔄 수동 Jira 데이터 동기화 중..."):
                            # JiraConnector 인스턴스 생성 (수동 설정)
                            connector = JiraConnector(
                                url=manual_jira_url,
                                email=manual_jira_email,
                                token=manual_jira_token
                            )
                            
                            # 동기화 실행
                            sync_result = connector.sync_jira()
                            
                            if sync_result["success"]:
                                st.success(sync_result["message"])
                                
                                # 동기화 결과 상세 표시
                                with st.expander("📊 수동 동기화 결과 상세보기"):
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("처리된 티켓", sync_result["tickets_processed"])
                                    with col2:
                                        st.metric("발견된 티켓", sync_result["total_tickets_found"])
                                    with col3:
                                        st.metric("동기화 시간", f"{sync_result['sync_duration']:.2f}초")
                                    
                                    # 동기화 정보
                                    st.subheader("🕒 동기화 정보")
                                    st.info(f"**시작 시간:** {sync_result['start_time']}")
                                    st.info(f"**완료 시간:** {sync_result['end_time']}")
                                    st.info(f"**마지막 동기화:** {sync_result['last_sync_time']}")
                                    
                                    # 성공 메시지
                                    if sync_result["tickets_processed"] > 0:
                                        st.success(f"🎉 {sync_result['tickets_processed']}개 티켓이 성공적으로 동기화되었습니다!")
                                    else:
                                        st.info("ℹ️ 동기화할 새로운 티켓이 없습니다.")
                                
                                # Jira 연결 상태 업데이트
                                st.session_state.jira_connected = True
                                
                            else:
                                st.error(sync_result["message"])
                                st.error(f"❌ 동기화 실패: {sync_result.get('error', '알 수 없는 오류')}")
                        
                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Jira 동기화 중 오류 발생: {error_msg}")
                        
                        # 에러 유형별 특별한 안내
                        if "429" in error_msg or "Rate Limit" in error_msg:
                            st.error("🚫 Rate Limit 초과!")
                            st.info("💡 Jira API 요청 한도를 초과했습니다.")
                            st.info("💡 해결 방법:")
                            st.info("1. 잠시 후 다시 시도해주세요 (자동으로 재시도됩니다)")
                            st.info("2. 대량의 티켓이 있는 경우 배치 크기를 줄여주세요")
                            st.info("3. 동기화 주기를 늘려주세요")
                            
                        elif "401" in error_msg or "Unauthorized" in error_msg:
                            st.error("🔐 인증 오류가 발생했습니다!")
                            st.info("💡 해결 방법:")
                            st.info("1. Jira URL이 올바른지 확인하세요")
                            st.info("2. 이메일 주소가 정확한지 확인하세요")
                            st.info("3. API 토큰이 유효한지 확인하세요")
                            
                        elif "403" in error_msg or "권한 부족" in error_msg:
                            st.error("🚫 권한 부족!")
                            st.info("💡 Jira 프로젝트에 대한 접근 권한이 없습니다.")
                            st.info("💡 해결 방법:")
                            st.info("1. Jira 계정에 해당 프로젝트에 대한 읽기 권한이 있는지 확인하세요")
                            st.info("2. 프로젝트 관리자에게 권한 요청을 하세요")
                            
                        else:
                            st.info("💡 Jira URL, 이메일, API 토큰이 올바른지 확인해주세요.")
                            st.info("💡 네트워크 연결 상태를 확인해주세요.")
        
        # Jira 연동 가이드
        with st.expander("📚 Jira 연동 가이드"):
            st.markdown("""
            ### 🔑 API 토큰 생성 방법
            1. [Atlassian 계정 설정](https://id.atlassian.com/manage-profile/security/api-tokens)에 접속
            2. "API 토큰" 섹션에서 "토큰 생성" 클릭
            3. 토큰 이름 입력 (예: "Streamlit Jira Sync")
            4. 생성된 토큰을 복사하여 위 폼에 입력
            
            ### 📋 동기화되는 데이터
            - **티켓 요약**: 제목과 설명
            - **상태 정보**: 현재 상태, 우선순위, 담당자
            - **코멘트**: 최신 3개 코멘트
            - **메타데이터**: 생성/수정 시간, 보고자 등
            
            ### ⚠️ 주의사항
            - API 토큰은 안전하게 보관하세요
            - 대량의 티켓이 있는 경우 동기화에 시간이 걸릴 수 있습니다
            - 동기화는 마지막 동기화 이후 변경된 티켓만 처리합니다
            
            ### 🚫 Rate Limiting & Backoff 전략
            - **자동 재시도**: 429 에러 시 최대 5회까지 자동 재시도
            - **지능적 대기**: 에러 유형에 따른 적응적 대기 시간 (4초~60초)
            - **Rate Limiting**: 검색 100/분, 일반 1000/분 제한 자동 적용
            - **배치 처리**: 대량 티켓 처리 시 자동으로 적절한 간격 유지
            """)
        
        # Jira 벡터DB 검색 기능
        st.markdown("---")
        st.subheader("🔍 Jira 티켓 검색")
        
        jira_search_query = st.text_input(
            "Jira 티켓 검색어",
            placeholder="예: 버그 수정, 기능 개발...",
            key="jira_search"
        )
        
        if st.button("🔍 Jira 검색 시작", use_container_width=True) and jira_search_query:
            try:
                if 'system_info_db' not in st.session_state:
                    from vector_db_models import SystemInfoVectorDBManager
                    st.session_state.system_info_db = SystemInfoVectorDBManager()
                
                # jira_info 컬렉션에서 검색
                search_results = st.session_state.system_info_db.search_similar_chunks(
                    query=jira_search_query,
                    n_results=10
                )
                
                if search_results:
                    st.success(f"✅ Jira 검색 완료! {len(search_results)}개 결과를 찾았습니다.")
                    
                    # 검색 결과 표시
                    for i, result in enumerate(search_results, 1):
                        with st.expander(f"🎫 Jira 티켓 {i}"):
                            metadata = result['metadata']
                            st.write(f"**티켓 키:** {metadata.get('ticket_key', '알 수 없음')}")
                            st.write(f"**요약:** {metadata.get('summary', '제목 없음')}")
                            st.write(f"**상태:** {metadata.get('status', '알 수 없음')}")
                            st.write(f"**우선순위:** {metadata.get('priority', '알 수 없음')}")
                            st.write(f"**담당자:** {metadata.get('assignee', '알 수 없음')}")
                            
                            # 유사도 점수
                            similarity = result.get('similarity_score', 0)
                            if similarity is not None:
                                st.progress(similarity)
                                st.write(f"**유사도:** {similarity:.3f}")
                            
                            # 티켓 내용
                            text_content = result['text_content']
                            if text_content:
                                st.text_area(f"📝 티켓 내용", text_content, height=150, disabled=True)
                else:
                    st.info("🔍 Jira 검색 결과가 없습니다.")
                    
            except Exception as e:
                st.error(f"❌ Jira 검색 중 오류 발생: {str(e)}")

    # 3. 사용자 입력 처리
    if prompt := st.chat_input("메일에 대해 무엇이든 물어보세요..."):
        if st.session_state.email_connected:
            handle_query(prompt)
        else:
            st.warning("먼저 사이드바에서 이메일 연결을 해주세요.")

if __name__ == "__main__":
    main()