#!/usr/bin/env python3
"""
FastMCP 기반 이메일 서비스 서버
기존 mcp_server.py를 FastMCP 애플리케이션으로 교체
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# FastMCP import
from fastmcp import FastMCP

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("EmailServiceServer")

# 이메일 도구들 import
from fastmcp_email_tools import (
    get_raw_emails,
    process_emails_with_ticket_logic,
    get_email_provider_status,
    get_mail_content_by_id,
    create_ticket_from_single_email,
    fetch_emails_sync
)

# 이메일 에이전트 import
from fastmcp_email_agent import email_agent

# 도구들을 FastMCP에 등록
@mcp.tool()
def get_raw_emails_tool(provider_name: str, filters: Dict[str, Any]) -> list:
    """사용자의 특정 조건에 맞는 순수 이메일 목록을 반환합니다."""
    return get_raw_emails(provider_name, filters)

@mcp.tool()
def process_emails_with_ticket_logic_tool(provider_name: str, user_query: str = None) -> Dict[str, Any]:
    """안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다."""
    return process_emails_with_ticket_logic(provider_name, user_query)

@mcp.tool()
def get_email_provider_status_tool(provider_name: str = None) -> Dict[str, Any]:
    """이메일 제공자의 연결 상태와 설정 정보를 확인합니다."""
    return get_email_provider_status(provider_name)

@mcp.tool()
def get_mail_content_by_id_tool(message_id: str) -> Optional[Dict[str, Any]]:
    """VectorDB에서 message_id로 메일 상세 내용을 조회합니다."""
    return get_mail_content_by_id(message_id)

@mcp.tool()
def create_ticket_from_single_email_tool(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """단일 이메일을 티켓으로 변환하는 함수입니다."""
    return create_ticket_from_single_email(email_data)

@mcp.tool()
def fetch_emails_sync_tool(provider_name: str, use_classifier: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """동기적으로 이메일을 가져와서 티켓 형태로 변환하여 반환합니다."""
    return fetch_emails_sync(provider_name, use_classifier, max_results)

# 에이전트를 FastMCP 도구로 등록
@mcp.tool()
def email_agent_tool(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    이메일 관리 및 티켓 생성 전문 AI 어시스턴트
    
    사용자의 이메일 관련 요청을 이해하고 적절한 도구를 선택하여 실행합니다.
    
    Args:
        user_query (str): 사용자의 요청 또는 질문
        context (Optional[Dict[str, Any]]): 추가 컨텍스트 정보
    
    Returns:
        Dict[str, Any]: 처리 결과
            - success (bool): 처리 성공 여부
            - message (str): 응답 메시지
            - data (Any): 처리된 데이터
            - tools_used (List[str]): 사용된 도구 목록
            - error (str, optional): 오류 메시지
    """
    return email_agent(user_query, context)

# 추가 유틸리티 도구들
@mcp.tool()
def get_available_providers() -> list:
    """
    사용 가능한 이메일 제공자 목록을 반환합니다.
    
    Returns:
        list: 사용 가능한 이메일 제공자 목록
    """
    try:
        from email_provider import get_available_providers as original_function
        providers = original_function()
        logging.info(f"✅ 사용 가능한 이메일 제공자: {providers}")
        return providers
    except Exception as e:
        logging.error(f"❌ 이메일 제공자 목록 조회 실패: {str(e)}")
        return []

@mcp.tool()
def get_default_provider() -> str:
    """
    기본 이메일 제공자를 반환합니다.
    
    Returns:
        str: 기본 이메일 제공자 이름
    """
    try:
        from email_provider import get_default_provider as original_function
        provider = original_function()
        logging.info(f"✅ 기본 이메일 제공자: {provider}")
        return provider
    except Exception as e:
        logging.error(f"❌ 기본 이메일 제공자 조회 실패: {str(e)}")
        return "gmail"

@mcp.tool()
def test_work_related_filtering() -> Dict[str, Any]:
    """
    테스트용 업무 관련 메일 필터링 기능을 실행합니다.
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_work_related_filtering as original_function
        result = original_function()
        logging.info(f"✅ 업무 관련 메일 필터링 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 업무 관련 메일 필터링 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_email_fetch_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 메일 조회 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_email_fetch_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 메일 조회 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 메일 조회 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_ticket_creation_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 티켓 생성 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_ticket_creation_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 티켓 생성 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 티켓 생성 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# 서버 상태 확인 도구
@mcp.tool()
def get_server_status() -> Dict[str, Any]:
    """
    FastMCP 서버의 상태를 확인합니다.
    
    Returns:
        Dict[str, Any]: 서버 상태 정보
    """
    try:
        import psutil
        import platform
        
        # 시스템 정보 수집
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage('/').percent
        }
        
        # 환경 변수 확인
        env_vars = {
            'AZURE_OPENAI_ENDPOINT': bool(os.getenv('AZURE_OPENAI_ENDPOINT')),
            'AZURE_OPENAI_API_KEY': bool(os.getenv('AZURE_OPENAI_API_KEY')),
            'AZURE_OPENAI_DEPLOYMENT_NAME': bool(os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')),
            'AZURE_OPENAI_API_VERSION': bool(os.getenv('AZURE_OPENAI_API_VERSION'))
        }
        
        logging.info("✅ 서버 상태 확인 완료")
        
        return {
            'status': 'healthy',
            'system_info': system_info,
            'environment_variables': env_vars,
            'timestamp': str(os.path.getmtime(__file__))
        }
        
    except Exception as e:
        logging.error(f"❌ 서버 상태 확인 실패: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': str(os.path.getmtime(__file__))
        }

# FastMCP 앱 실행을 위한 메인 함수
def run_fastmcp_server():
    """FastMCP 서버 실행"""
    logging.info("🚀 FastMCP 이메일 서비스 서버 시작")
    logging.info("📧 등록된 도구들:")
    logging.info("  - get_raw_emails_tool")
    logging.info("  - process_emails_with_ticket_logic_tool")
    logging.info("  - get_email_provider_status_tool")
    logging.info("  - get_mail_content_by_id_tool")
    logging.info("  - create_ticket_from_single_email_tool")
    logging.info("  - fetch_emails_sync_tool")
    logging.info("  - email_agent_tool")
    logging.info("  - get_available_providers")
    logging.info("  - get_default_provider")
    logging.info("  - test_work_related_filtering")
    logging.info("  - test_email_fetch_logic")
    logging.info("  - test_ticket_creation_logic")
    logging.info("  - get_server_status")
    
    mcp.run()

if __name__ == "__main__":
    run_fastmcp_server()
