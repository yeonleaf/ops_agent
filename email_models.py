#!/usr/bin/env python3
"""
통일된 이메일 데이터 모델
Gmail API와 Microsoft Graph API의 데이터를 통일된 형식으로 변환
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class EmailPriority(str, Enum):
    """이메일 우선순위"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    
    def __str__(self):
        return self.value

class EmailStatus(str, Enum):
    """이메일 상태"""
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"
    DELED = "deleted"
    
    def __str__(self):
        return self.value

class EmailMessage(BaseModel):
    """통일된 이메일 메시지 모델"""
    
    # 기본 식별 정보
    id: str = Field(..., description="이메일 고유 ID")
    message_id: Optional[str] = Field(None, description="원본 메시지 ID (헤더)")
    
    # 발신자 정보
    sender: str = Field(..., description="발신자 이메일 주소")
    sender_name: Optional[str] = Field(None, description="발신자 이름")
    
    # 수신자 정보
    recipients: List[str] = Field(default_factory=list, description="수신자 이메일 주소 목록")
    cc: List[str] = Field(default_factory=list, description="참조 이메일 주소 목록")
    bcc: List[str] = Field(default_factory=list, description="숨은참조 이메일 주소 목록")
    
    # 이메일 내용
    subject: str = Field(..., description="이메일 제목")
    body: Optional[str] = Field(None, description="이메일 본문 (텍스트)")
    body_html: Optional[str] = Field(None, description="이메일 본문 (HTML)")
    
    # 메타데이터
    received_date: datetime = Field(..., description="수신 일시")
    sent_date: Optional[datetime] = Field(None, description="발송 일시")
    
    # 상태 정보
    is_read: bool = Field(default=False, description="읽음 여부")
    is_important: bool = Field(default=False, description="중요 여부")
    is_starred: bool = Field(default=False, description="별표 여부")
    
    # 라벨/카테고리
    labels: List[str] = Field(default_factory=list, description="라벨 목록")
    categories: List[str] = Field(default_factory=list, description="카테고리 목록")
    
    # 첨부파일
    has_attachments: bool = Field(default=False, description="첨부파일 존재 여부")
    attachment_count: int = Field(default=0, description="첨부파일 개수")
    
    # 우선순위
    priority: EmailPriority = Field(default=EmailPriority.NORMAL, description="우선순위")
    
    # 상태
    status: EmailStatus = Field(default=EmailStatus.UNREAD, description="이메일 상태")
    
    # 원본 데이터 (디버깅용)
    raw_data: Optional[Dict[str, Any]] = Field(None, description="원본 API 응답 데이터")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class EmailSearchResult(BaseModel):
    """이메일 검색 결과"""
    messages: List[EmailMessage] = Field(default_factory=list, description="검색된 이메일 목록")
    total_count: int = Field(default=0, description="전체 검색 결과 수")
    next_page_token: Optional[str] = Field(None, description="다음 페이지 토큰")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True

class EmailProviderConfig(BaseModel):
    """이메일 제공자 설정"""
    provider_type: str = Field(..., description="제공자 타입 (gmail, graph)")
    client_id: str = Field(..., description="클라이언트 ID")
    client_secret: str = Field(..., description="클라이언트 시크릿")
    refresh_token: Optional[str] = Field(None, description="리프레시 토큰")
    access_token: Optional[str] = Field(None, description="액세스 토큰")
    tenant_id: Optional[str] = Field(None, description="테넌트 ID (Microsoft Graph용)")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True

class EmailProviderStatus(BaseModel):
    """이메일 제공자 상태"""
    is_connected: bool = Field(..., description="연결 상태")
    provider_type: str = Field(..., description="제공자 타입")
    message: str = Field(..., description="상태 메시지")
    email_count: Optional[int] = Field(None, description="이메일 개수")
    last_sync: Optional[datetime] = Field(None, description="마지막 동기화 시간")
    
    class Config:
        """Pydantic 설정"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        } 