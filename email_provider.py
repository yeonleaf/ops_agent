#!/usr/bin/env python3
"""
이메일 제공자 추상화 계층
Gmail API와 Microsoft Graph API를 통일된 인터페이스로 추상화
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from dotenv import load_dotenv

from email_models import (
    EmailMessage, 
    EmailSearchResult, 
    EmailProviderConfig, 
    EmailProviderStatus
)

# 환경변수 로드
load_dotenv()

class EmailProvider(ABC):
    """이메일 제공자 추상 기본 클래스"""
    
    def __init__(self, config: EmailProviderConfig):
        """초기화"""
        self.config = config
        self.is_authenticated = False
        self.last_sync = None
    
    @abstractmethod
    def authenticate(self) -> bool:
        """인증 수행"""
        pass
    
    @abstractmethod
    def get_unread_emails(self, max_results: int = 50) -> List[EmailMessage]:
        """안읽은 이메일 가져오기"""
        pass
    
    @abstractmethod
    def search_emails(self, query: str, max_results: int = 50) -> EmailSearchResult:
        """이메일 검색"""
        pass
    
    @abstractmethod
    def get_email_by_id(self, email_id: str) -> Optional[EmailMessage]:
        """ID로 이메일 가져오기"""
        pass
    
    @abstractmethod
    def mark_as_read(self, email_id: str) -> bool:
        """이메일을 읽음으로 표시"""
        pass
    
    @abstractmethod
    def mark_as_unread(self, email_id: str) -> bool:
        """이메일을 안읽음으로 표시"""
        pass
    
    @abstractmethod
    def get_provider_status(self) -> EmailProviderStatus:
        """제공자 상태 확인"""
        pass
    
    def _parse_datetime(self, date_string: str) -> datetime:
        """날짜 문자열을 datetime으로 파싱"""
        try:
            # 다양한 날짜 형식 지원
            from dateutil import parser
            return parser.parse(date_string)
        except:
            # 기본값
            return datetime.now()
    
    def _extract_email_address(self, email_string: str) -> str:
        """이메일 문자열에서 주소만 추출"""
        import re
        # "Name <email@domain.com>" 형식에서 email@domain.com 추출
        match = re.search(r'<(.+?)>', email_string)
        if match:
            return match.group(1)
        return email_string.strip()
    
    def _extract_name_from_email(self, email_string: str) -> Optional[str]:
        """이메일 문자열에서 이름 추출"""
        import re
        # "Name <email@domain.com>" 형식에서 Name 추출
        match = re.search(r'^(.+?)\s*<', email_string)
        if match:
            return match.group(1).strip()
        return None

def create_provider(provider_name: str = None, access_token: str = None) -> EmailProvider:
    """
    이메일 제공자 팩토리 함수 - OAuth2 액세스 토큰 필수
    
    Args:
        provider_name: 제공자 이름 ('gmail', 'graph', None)
                      None인 경우 환경변수에서 자동 감지
        access_token: OAuth2 액세스 토큰 (필수)
    
    Returns:
        EmailProvider 인스턴스
    
    Raises:
        ValueError: 지원하지 않는 제공자 또는 설정 누락
    """
    
    # 제공자 이름이 지정되지 않은 경우 환경변수에서 감지
    if provider_name is None:
        provider_name = os.getenv('EMAIL_PROVIDER', 'gmail').lower()
    
    # Gmail 제공자 생성
    if provider_name == 'gmail':
        config = EmailProviderConfig(
            provider_type='gmail',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),  # OAuth2 서버용 변수명 사용
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),  # OAuth2 서버용 변수명 사용
            access_token=access_token,  # OAuth2 액세스 토큰 사용
            refresh_token=os.getenv('GMAIL_REFRESH_TOKEN')  # 레거시 지원
        )
        
        # OAuth2 액세스 토큰이 없으면 강제 차단
        if not access_token and not config.refresh_token:
            print("❌ OAuth2 인증이 필요합니다. 액세스 토큰을 제공하거나 OAuth 서버를 사용하세요.")
            print("💡 OAuth 서버 사용: http://localhost:8000/auth/login/gmail")
            raise ValueError("OAuth2 인증이 필요합니다. 액세스 토큰을 제공하거나 OAuth 서버를 사용하세요.")
        
        from gmail_provider import GmailProvider
        return GmailProvider(config)
    
    # Microsoft Graph 제공자 생성
    elif provider_name == 'graph':
        config = EmailProviderConfig(
            provider_type='graph',
            client_id=os.getenv('GRAPH_CLIENT_ID'),
            client_secret=os.getenv('GRAPH_CLIENT_SECRET'),
            refresh_token=os.getenv('GRAPH_REFRESH_TOKEN'),
            tenant_id=os.getenv('GRAPH_TENANT_ID')
        )
        
        if not all([config.client_id, config.client_secret, config.refresh_token, config.tenant_id]):
            raise ValueError("Microsoft Graph 설정이 누락되었습니다. GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_REFRESH_TOKEN, GRAPH_TENANT_ID를 확인해주세요.")
        
        from graph_provider import GraphApiProvider
        return GraphApiProvider(config)
    
    else:
        raise ValueError(f"지원하지 않는 이메일 제공자입니다: {provider_name}. 'gmail' 또는 'graph'를 사용해주세요.")

def get_available_providers() -> List[str]:
    """사용 가능한 이메일 제공자 목록 반환"""
    providers = []
    
    # Gmail 제공자 확인
    if all([
        os.getenv('GMAIL_CLIENT_ID'),
        os.getenv('GMAIL_CLIENT_SECRET'),
        os.getenv('GMAIL_REFRESH_TOKEN')
    ]):
        providers.append('gmail')
    
    # Microsoft Graph 제공자 확인
    if all([
        os.getenv('GRAPH_CLIENT_ID'),
        os.getenv('GRAPH_CLIENT_SECRET'),
        os.getenv('GRAPH_REFRESH_TOKEN'),
        os.getenv('GRAPH_TENANT_ID')
    ]):
        providers.append('graph')
    
    return providers

def get_default_provider() -> str:
    """기본 이메일 제공자 반환"""
    available = get_available_providers()
    if not available:
        return 'gmail'  # 기본값
    
    # 환경변수에서 기본값 확인
    default = os.getenv('EMAIL_PROVIDER', 'gmail').lower()
    if default in available:
        return default
    
    # 첫 번째 사용 가능한 제공자 반환
    return available[0] 