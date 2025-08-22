#!/usr/bin/env python3
"""
Gmail API 제공자 구현
Google Gmail API를 사용하여 이메일을 가져오고 관리
"""

import os
import base64
import email
from typing import List, Optional, Dict, Any
from datetime import datetime
import streamlit as st

# Google API 클라이언트
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email_provider import EmailProvider
from email_models import (
    EmailMessage, 
    EmailSearchResult, 
    EmailProviderConfig, 
    EmailProviderStatus,
    EmailPriority,
    EmailStatus
)

class GmailProvider(EmailProvider):
    """Gmail API 제공자"""
    
    def __init__(self, config: EmailProviderConfig):
        """초기화"""
        super().__init__(config)
        self.service = None
        self.creds = None
        
        # Gmail API 스코프
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly'
        ]
    
    def authenticate(self) -> bool:
        """Gmail API 인증"""
        try:
            # Credentials 객체 생성
            self.creds = Credentials(
                None,  # access_token은 자동 갱신됨
                refresh_token=self.config.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scopes=self.scopes
            )
            
            # 토큰 갱신
            if self.creds.expired:
                self.creds.refresh(Request())
            
            # Gmail API 서비스 생성
            self.service = build('gmail', 'v1', credentials=self.creds)
            self.is_authenticated = True
            return True
            
        except Exception as e:
            st.error(f"Gmail 인증 실패: {str(e)}")
            self.is_authenticated = False
            return False
    
    def get_unread_emails(self, max_results: int = 50) -> List[EmailMessage]:
        """안읽은 이메일 가져오기"""
        if not self.is_authenticated:
            if not self.authenticate():
                return []
        
        try:
            # 안읽은 메일 검색
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['UNREAD'],
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            email_messages = []
            
            for message in messages:
                email_data = self.get_email_by_id(message['id'])
                if email_data:
                    email_messages.append(email_data)
            
            self.last_sync = datetime.now()
            return email_messages
            
        except HttpError as error:
            st.error(f"Gmail API 오류: {error}")
            return []
        except Exception as e:
            st.error(f"메일 가져오기 실패: {str(e)}")
            return []
    
    def search_emails(self, query: str, max_results: int = 50) -> EmailSearchResult:
        """Gmail 검색 쿼리로 메일 검색"""
        if not self.is_authenticated:
            if not self.authenticate():
                return EmailSearchResult()
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            email_messages = []
            
            for message in messages:
                email_data = self.get_email_by_id(message['id'])
                if email_data:
                    email_messages.append(email_data)
            
            self.last_sync = datetime.now()
            
            return EmailSearchResult(
                messages=email_messages,
                total_count=len(email_messages),
                next_page_token=results.get('nextPageToken')
            )
            
        except HttpError as error:
            st.error(f"Gmail 검색 오류: {error}")
            return EmailSearchResult()
        except Exception as e:
            st.error(f"메일 검색 실패: {str(e)}")
            return EmailSearchResult()
    
    def get_email_by_id(self, email_id: str) -> Optional[EmailMessage]:
        """ID로 이메일 가져오기"""
        if not self.is_authenticated:
            if not self.authenticate():
                return None
        
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            # 헤더 정보 추출
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 없음')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            to = next((h['value'] for h in headers if h['name'] == 'To'), '')
            cc = next((h['value'] for h in headers if h['name'] == 'Cc'), '')
            
            # 메일 본문 추출
            body = self._extract_email_body(message['payload'])
            
            # 라벨 정보
            labels = message.get('labelIds', [])
            
            # 우선순위 결정
            priority = EmailPriority.NORMAL
            if 'IMPORTANT' in labels:
                priority = EmailPriority.HIGH
            elif 'CATEGORY_PROMOTIONS' in labels:
                priority = EmailPriority.LOW
            
            # 상태 결정
            status = EmailStatus.UNREAD if 'UNREAD' in labels else EmailStatus.READ
            
            # 발신자 정보 파싱
            sender_email = self._extract_email_address(sender)
            sender_name = self._extract_name_from_email(sender)
            
            # 수신자 정보 파싱
            recipients = [self._extract_email_address(addr.strip()) for addr in to.split(',') if addr.strip()]
            cc_list = [self._extract_email_address(addr.strip()) for addr in cc.split(',') if addr.strip()]
            
            # 첨부파일 확인
            has_attachments = 'parts' in message['payload'] and any(
                part.get('filename') for part in message['payload']['parts']
            )
            attachment_count = len([
                part for part in message['payload'].get('parts', [])
                if part.get('filename')
            ]) if 'parts' in message['payload'] else 0
            
            return EmailMessage(
                id=email_id,
                message_id=message.get('threadId'),
                sender=sender_email,
                sender_name=sender_name,
                recipients=recipients,
                cc=cc_list,
                subject=subject,
                body=body,
                received_date=self._parse_datetime(date),
                is_read='UNREAD' not in labels,
                is_important='IMPORTANT' in labels,
                is_starred='STARRED' in labels,
                labels=labels,
                has_attachments=has_attachments,
                attachment_count=attachment_count,
                priority=priority,
                status=status,
                raw_data=message
            )
            
        except Exception as e:
            st.error(f"메일 상세 정보 가져오기 실패: {str(e)}")
            return None
    
    def mark_as_read(self, email_id: str) -> bool:
        """이메일을 읽음으로 표시"""
        if not self.is_authenticated:
            if not self.authenticate():
                return False
        
        try:
            # UNREAD 라벨 제거
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
            
        except Exception as e:
            st.error(f"읽음 표시 실패: {str(e)}")
            return False
    
    def mark_as_unread(self, email_id: str) -> bool:
        """이메일을 안읽음으로 표시"""
        if not self.is_authenticated:
            if not self.authenticate():
                return False
        
        try:
            # UNREAD 라벨 추가
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
            return True
            
        except Exception as e:
            st.error(f"안읽음 표시 실패: {str(e)}")
            return False
    
    def get_provider_status(self) -> EmailProviderStatus:
        """제공자 상태 확인"""
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return EmailProviderStatus(
                        is_connected=False,
                        provider_type='gmail',
                        message="인증 실패"
                    )
            
            # 연결 테스트
            unread_count = len(self.get_unread_emails(max_results=1))
            
            return EmailProviderStatus(
                is_connected=True,
                provider_type='gmail',
                message=f"연결됨 (안읽은 메일: {unread_count}개)",
                email_count=unread_count,
                last_sync=self.last_sync
            )
            
        except Exception as e:
            return EmailProviderStatus(
                is_connected=False,
                provider_type='gmail',
                message=f"연결 오류: {str(e)}"
            )
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """메일 본문 추출"""
        try:
            if 'parts' in payload:
                # 멀티파트 메일
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                    elif part['mimeType'] == 'text/html':
                        data = part['body']['data']
                        return base64.urlsafe_b64decode(data).decode('utf-8')
            else:
                # 단일 파트 메일
                if payload['mimeType'] == 'text/plain':
                    data = payload['body']['data']
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                elif payload['mimeType'] == 'text/html':
                    data = payload['body']['data']
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            
            return "메일 내용을 읽을 수 없습니다."
            
        except Exception as e:
            return f"메일 내용 추출 실패: {str(e)}" 