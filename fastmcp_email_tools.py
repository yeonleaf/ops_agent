#!/usr/bin/env python3
"""
FastMCP 기반 이메일 서비스 도구들
unified_email_service.py의 주요 함수들을 FastMCP Tool로 변환
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# FastMCP import
from fastmcp import FastMCP

# 환경 변수 로드
load_dotenv()

# 기존 모듈들 import
from email_provider import create_provider, get_available_providers, get_default_provider
from email_models import EmailMessage, EmailSearchResult, EmailPriority
from memory_based_ticket_processor import MemoryBasedTicketProcessorTool
from gmail_api_client import get_gmail_client
from vector_db_models import VectorDBManager
from memory_based_ticket_processor import create_memory_based_ticket_processor

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("EmailService")

# TicketCreationStatus enum 정의
class TicketCreationStatus(str):
    """티켓 생성 상태"""
    SHOULD_CREATE = "should_create"      # 티켓 생성해야 함
    ALREADY_EXISTS = "already_exists"    # 이미 티켓이 존재함
    NO_TICKET_NEEDED = "no_ticket_needed"  # 티켓 생성 불필요

@mcp.tool()
def get_raw_emails(provider_name: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    사용자의 특정 조건에 맞는 순수 이메일 목록을 반환합니다.
    
    이 도구는 Gmail, Outlook 등 다양한 이메일 제공자에서 필터링된 이메일 목록을 가져옵니다.
    필터 조건에는 읽음 상태, 발신자, 제목, 첨부파일 여부, 날짜 범위 등이 포함될 수 있습니다.
    
    Args:
        provider_name (str): 이메일 제공자 이름 (예: "gmail", "outlook")
        filters (Dict[str, Any]): 이메일 필터 조건
            - is_read (bool): 읽음 상태 (True: 읽은 메일, False: 안 읽은 메일)
            - sender (str): 발신자 필터
            - subject (str): 제목 필터
            - has_attachments (bool): 첨부파일 여부
            - date_after (str): 시작 날짜 (YYYY-MM-DD 형식)
            - date_before (str): 종료 날짜 (YYYY-MM-DD 형식)
            - limit (int): 최대 결과 수 (기본값: 100)
    
    Returns:
        List[Dict[str, Any]]: 이메일 목록
            각 이메일은 다음 정보를 포함합니다:
            - id: 이메일 ID
            - subject: 제목
            - sender: 발신자
            - body: 내용
            - received_date: 수신 날짜
            - is_read: 읽음 상태
            - priority: 우선순위
            - has_attachments: 첨부파일 여부
    """
    try:
        from unified_email_service import UnifiedEmailService
        service = UnifiedEmailService(provider_name)
        emails = service.fetch_emails(filters)
        
        # EmailMessage 객체를 딕셔너리로 변환
        email_list = []
        for email in emails:
            email_dict = email.model_dump()
            email_list.append({
                'id': email_dict.get('id'),
                'subject': email_dict.get('subject'),
                'sender': email_dict.get('sender'),
                'body': email_dict.get('body'),
                'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                'is_read': email_dict.get('is_read'),
                'priority': email_dict.get('priority'),
                'has_attachments': email_dict.get('has_attachments')
            })
        
        logging.info(f"✅ {len(email_list)}개 이메일 조회 완료")
        return email_list
        
    except Exception as e:
        logging.error(f"❌ 이메일 조회 실패: {str(e)}")
        return []

@mcp.tool()
def process_emails_with_ticket_logic(provider_name: str, user_query: str = None) -> Dict[str, Any]:
    """
    안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다.
    
    이 도구는 다음 단계로 작동합니다:
    1. 안 읽은 메일 가져오기
    2. LLM 기반 업무용 메일 필터링
    3. 유사 메일 검색 및 LLM 기반 레이블 추천
    4. 새로운 티켓 생성
    5. 기존 티켓과 새로운 티켓 합치기
    
    Args:
        provider_name (str): 이메일 제공자 이름 (예: "gmail", "outlook")
        user_query (str, optional): 사용자 쿼리 (티켓 생성 시 참고용)
    
    Returns:
        Dict[str, Any]: 처리 결과
            - display_mode (str): 표시 모드 ("tickets", "no_emails", "error")
            - tickets (List[Dict]): 티켓 목록
            - new_tickets_created (int): 새로 생성된 티켓 수
            - existing_tickets_found (int): 기존 티켓 수
            - summary (Dict): 요약 정보
            - message (str): 결과 메시지
    """
    try:
        from unified_email_service import process_emails_with_ticket_logic as original_function
        result = original_function(provider_name, user_query)
        
        logging.info(f"✅ 티켓 처리 완료: 새로운 {result.get('new_tickets_created', 0)}개, 기존 {result.get('existing_tickets_found', 0)}개")
        return result
        
    except Exception as e:
        logging.error(f"❌ 티켓 처리 실패: {str(e)}")
        return {
            'display_mode': 'error',
            'message': f'티켓 처리 중 오류가 발생했습니다: {str(e)}',
            'tickets': [],
            'new_tickets_created': 0,
            'existing_tickets_found': 0
        }

@mcp.tool()
def get_email_provider_status(provider_name: str = None) -> Dict[str, Any]:
    """
    이메일 제공자의 연결 상태와 설정 정보를 확인합니다.
    
    이 도구는 지정된 이메일 제공자(Gmail, Outlook 등)의 연결 상태, 인증 상태,
    사용 가능한 기능 등을 확인하여 시스템 상태를 점검합니다.
    
    Args:
        provider_name (str, optional): 확인할 이메일 제공자 이름
            - None: 기본 제공자 사용
            - "gmail": Gmail 제공자
            - "outlook": Outlook 제공자
    
    Returns:
        Dict[str, Any]: 제공자 상태 정보
            - provider_name (str): 제공자 이름
            - is_connected (bool): 연결 상태
            - is_authenticated (bool): 인증 상태
            - available_features (List[str]): 사용 가능한 기능 목록
            - error_message (str, optional): 오류 메시지
    """
    try:
        from unified_email_service import get_email_provider_status as original_function
        status = original_function(provider_name)
        
        logging.info(f"✅ 이메일 제공자 상태 확인 완료: {status.get('provider_name', 'Unknown')}")
        return status
        
    except Exception as e:
        logging.error(f"❌ 이메일 제공자 상태 확인 실패: {str(e)}")
        return {
            'provider_name': provider_name or 'Unknown',
            'is_connected': False,
            'is_authenticated': False,
            'available_features': [],
            'error_message': str(e)
        }

@mcp.tool()
def get_mail_content_by_id(message_id: str) -> Optional[Dict[str, Any]]:
    """
    VectorDB에서 message_id로 메일 상세 내용을 조회합니다.
    
    이 도구는 VectorDB에 저장된 특정 메일의 상세 정보를 조회합니다.
    메일의 원본 내용, 정제된 내용, 요약, 핵심 포인트 등의 정보를 제공합니다.
    
    Args:
        message_id (str): 조회할 메일의 고유 ID
    
    Returns:
        Optional[Dict[str, Any]]: 메일 상세 정보
            - message_id (str): 메일 ID
            - subject (str): 제목
            - sender (str): 발신자
            - body (str): 원본 내용
            - refined_content (str): 정제된 내용
            - content_summary (str): 내용 요약
            - key_points (List[str]): 핵심 포인트
            - received_datetime (str): 수신 시간
            - has_attachment (bool): 첨부파일 여부
            - status (str): 상태
        None: 메일을 찾을 수 없는 경우
    """
    try:
        from unified_email_service import get_mail_content_by_id as original_function
        result = original_function(message_id)
        
        if result:
            logging.info(f"✅ 메일 내용 조회 완료: {message_id}")
        else:
            logging.warning(f"⚠️ 메일을 찾을 수 없음: {message_id}")
        
        return result
        
    except Exception as e:
        logging.error(f"❌ 메일 내용 조회 실패: {str(e)}")
        return None

def create_ticket_from_single_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    단일 이메일을 티켓으로 변환하는 함수입니다.
    
    이 도구는 하나의 이메일을 받아서 Jira 티켓으로 변환합니다.
    Memory-Based 학습 시스템을 사용하여 이메일의 내용을 분석하고,
    적절한 우선순위, 레이블, 티켓 타입을 자동으로 결정합니다.
    
    Args:
        email_data (Dict[str, Any]): 이메일 데이터
            - id (str): 이메일 ID
            - subject (str): 제목
            - sender (str): 발신자
            - body (str): 내용
            - received_date (str, optional): 수신 날짜
            - is_read (bool, optional): 읽음 상태
    
    Returns:
        Dict[str, Any]: 생성된 티켓 정보
            - ticket_id (int): 생성된 티켓 ID
            - title (str): 티켓 제목
            - description (str): 티켓 설명
            - status (str): 티켓 상태
            - priority (str): 우선순위
            - type (str): 티켓 타입
            - reporter (str): 보고자
            - labels (List[str]): 레이블 목록
            - created_at (str): 생성 시간
            - message_id (str): 원본 메일 ID
            - memory_based_decision (bool): Memory-Based 시스템 사용 여부
            - ai_reasoning (str): AI 판단 근거
    """
    try:
        from unified_email_service import create_ticket_from_single_email as original_function
        result = original_function(email_data)
        
        logging.info(f"✅ 단일 이메일 티켓 생성 완료: {result.get('ticket_id', 'N/A')}")
        return result
        
    except Exception as e:
        logging.error(f"❌ 단일 이메일 티켓 생성 실패: {str(e)}")
        return {
            'ticket_id': None,
            'title': email_data.get('subject', '제목 없음'),
            'description': email_data.get('body', '내용 없음'),
            'status': 'error',
            'priority': 'Medium',
            'type': 'Task',
            'reporter': email_data.get('sender', '알 수 없음'),
            'labels': ['error'],
            'created_at': datetime.now().isoformat(),
            'message_id': email_data.get('id', ''),
            'memory_based_decision': False,
            'error_message': str(e)
        }

@mcp.tool()
def fetch_emails_sync(provider_name: str, use_classifier: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """
    동기적으로 이메일을 가져와서 티켓 형태로 변환하여 반환합니다.
    
    이 도구는 지정된 이메일 제공자에서 이메일을 가져와서
    티켓 형태의 데이터 구조로 변환하여 반환합니다.
    분류기 사용 여부를 선택할 수 있으며, 최대 결과 수를 제한할 수 있습니다.
    
    Args:
        provider_name (str): 이메일 제공자 이름 (예: "gmail", "outlook")
        use_classifier (bool): 분류기 사용 여부 (기본값: False)
        max_results (int): 최대 결과 수 (기본값: 50)
    
    Returns:
        Dict[str, Any]: 이메일 데이터와 메타데이터
            - tickets (List[Dict]): 티켓 형태로 변환된 이메일 목록
            - summary (Dict): 요약 정보
                - reason (str): 처리 이유
                - total_emails (int): 총 이메일 수
                - applied_filters (Dict): 적용된 필터
    """
    try:
        from unified_email_service import fetch_emails_sync as original_function
        result = original_function(provider_name, use_classifier, max_results)
        
        logging.info(f"✅ 동기 이메일 조회 완료: {result.get('summary', {}).get('total_emails', 0)}개")
        return result
        
    except Exception as e:
        logging.error(f"❌ 동기 이메일 조회 실패: {str(e)}")
        return {
            'tickets': [],
            'summary': {
                'reason': f'이메일 조회 중 오류가 발생했습니다: {str(e)}',
                'total_emails': 0,
                'applied_filters': {}
            }
        }

# FastMCP 앱 실행을 위한 메인 함수
def run_fastmcp_server():
    """FastMCP 서버 실행"""
    mcp.run()

if __name__ == "__main__":
    run_fastmcp_server()
