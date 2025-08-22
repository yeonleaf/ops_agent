#!/usr/bin/env python3
"""
Microsoft Graph API 제공자 구현
Microsoft Graph API를 사용하여 Outlook 이메일을 가져오고 관리
"""

import os
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime
import streamlit as st

from email_provider import EmailProvider
from email_models import (
    EmailMessage, 
    EmailSearchResult, 
    EmailProviderConfig, 
    EmailProviderStatus,
    EmailPriority,
    EmailStatus
)

class GraphApiProvider(EmailProvider):
    """Microsoft Graph API 제공자"""
    
    def __init__(self, config: EmailProviderConfig):
        """초기화"""
        super().__init__(config)
        self.access_token = None
        self.base_url = "https://graph.microsoft.com/v1.0"
        
        # Microsoft Graph API 스코프
        self.scopes = [
            'https://graph.microsoft.com/Mail.Read',
            'https://graph.microsoft.com/Mail.ReadWrite'
        ]
    
    def authenticate(self) -> bool:
        """Microsoft Graph API 인증"""
        try:
            # 액세스 토큰이 있으면 사용
            if self.config.access_token:
                self.access_token = self.config.access_token
                self.is_authenticated = True
                return True
            
            # 리프레시 토큰으로 새 액세스 토큰 획득
            if self.config.refresh_token:
                token_response = self._get_access_token_from_refresh()
                if token_response:
                    self.access_token = token_response
                    self.is_authenticated = True
                    return True
            
            st.error("Microsoft Graph API 인증에 필요한 토큰이 없습니다.")
            return False
            
        except Exception as e:
            st.error(f"Microsoft Graph API 인증 실패: {str(e)}")
            self.is_authenticated = False
            return False
    
    def _get_access_token_from_refresh(self) -> Optional[str]:
        """리프레시 토큰으로 액세스 토큰 획득"""
        try:
            token_url = f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token"
            
            data = {
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': self.config.refresh_token,
                'scope': ' '.join(self.scopes)
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get('access_token')
            
        except Exception as e:
            st.error(f"액세스 토큰 획득 실패: {str(e)}")
            return None
    
    def get_unread_emails(self, max_results: int = 50) -> List[EmailMessage]:
        """안읽은 이메일 가져오기"""
        if not self.is_authenticated:
            if not self.authenticate():
                return []
        
        try:
            # 안읽은 메일 검색
            url = f"{self.base_url}/me/messages"
            params = {
                '$filter': 'isRead eq false',
                '$top': max_results,
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,importance,hasAttachments,body,bodyPreview'
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            messages = data.get('value', [])
            email_messages = []
            
            for message in messages:
                email_data = self._convert_graph_message_to_email(message)
                if email_data:
                    email_messages.append(email_data)
            
            self.last_sync = datetime.now()
            return email_messages
            
        except Exception as e:
            st.error(f"메일 가져오기 실패: {str(e)}")
            return []
    
    def search_emails(self, query: str, max_results: int = 50) -> EmailSearchResult:
        """Microsoft Graph 검색 쿼리로 메일 검색"""
        if not self.is_authenticated:
            if not self.authenticate():
                return EmailSearchResult()
        
        try:
            # 메일 검색
            url = f"{self.base_url}/me/messages"
            params = {
                '$search': f'"{query}"',
                '$top': max_results,
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,importance,hasAttachments,body,bodyPreview'
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            messages = data.get('value', [])
            email_messages = []
            
            for message in messages:
                email_data = self._convert_graph_message_to_email(message)
                if email_data:
                    email_messages.append(email_data)
            
            self.last_sync = datetime.now()
            
            return EmailSearchResult(
                messages=email_messages,
                total_count=len(email_messages),
                next_page_token=data.get('@odata.nextLink')
            )
            
        except Exception as e:
            st.error(f"메일 검색 실패: {str(e)}")
            return EmailSearchResult()
    
    def get_email_by_id(self, email_id: str) -> Optional[EmailMessage]:
        """ID로 이메일 가져오기"""
        if not self.is_authenticated:
            if not self.authenticate():
                return None
        
        try:
            url = f"{self.base_url}/me/messages/{email_id}"
            params = {
                '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,importance,hasAttachments,body,bodyPreview'
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            message = response.json()
            return self._convert_graph_message_to_email(message)
            
        except Exception as e:
            st.error(f"메일 상세 정보 가져오기 실패: {str(e)}")
            return None
    
    def mark_as_read(self, email_id: str) -> bool:
        """이메일을 읽음으로 표시"""
        if not self.is_authenticated:
            if not self.authenticate():
                return False
        
        try:
            url = f"{self.base_url}/me/messages/{email_id}"
            data = {
                'isRead': True
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.patch(url, json=data, headers=headers)
            response.raise_for_status()
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
            url = f"{self.base_url}/me/messages/{email_id}"
            data = {
                'isRead': False
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.patch(url, json=data, headers=headers)
            response.raise_for_status()
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
                        provider_type='graph',
                        message="인증 실패"
                    )
            
            # 연결 테스트
            unread_count = len(self.get_unread_emails(max_results=1))
            
            return EmailProviderStatus(
                is_connected=True,
                provider_type='graph',
                message=f"연결됨 (안읽은 메일: {unread_count}개)",
                email_count=unread_count,
                last_sync=self.last_sync
            )
            
        except Exception as e:
            return EmailProviderStatus(
                is_connected=False,
                provider_type='graph',
                message=f"연결 오류: {str(e)}"
            )
    
    def _convert_graph_message_to_email(self, graph_message: Dict[str, Any]) -> Optional[EmailMessage]:
        """Microsoft Graph 메시지를 EmailMessage로 변환"""
        try:
            # 기본 정보
            email_id = graph_message.get('id', '')
            subject = graph_message.get('subject', '제목 없음')
            
            # 발신자 정보
            from_info = graph_message.get('from', {})
            sender_email = from_info.get('emailAddress', {}).get('address', '발신자 없음')
            sender_name = from_info.get('emailAddress', {}).get('name')
            
            # 수신자 정보
            to_recipients = graph_message.get('toRecipients', [])
            recipients = [
                recipient.get('emailAddress', {}).get('address', '')
                for recipient in to_recipients
                if recipient.get('emailAddress', {}).get('address')
            ]
            
            cc_recipients = graph_message.get('ccRecipients', [])
            cc_list = [
                recipient.get('emailAddress', {}).get('address', '')
                for recipient in cc_recipients
                if recipient.get('emailAddress', {}).get('address')
            ]
            
            # 날짜 정보
            received_date = self._parse_datetime(graph_message.get('receivedDateTime', ''))
            
            # 본문 정보
            body = graph_message.get('bodyPreview', '메일 내용을 읽을 수 없습니다.')
            body_html = graph_message.get('body', {}).get('content', '')
            
            # 상태 정보
            is_read = graph_message.get('isRead', False)
            has_attachments = graph_message.get('hasAttachments', False)
            
            # 우선순위
            importance = graph_message.get('importance', 'normal')
            priority_map = {
                'high': EmailPriority.HIGH,
                'normal': EmailPriority.NORMAL,
                'low': EmailPriority.LOW
            }
            priority = priority_map.get(importance.lower(), EmailPriority.NORMAL)
            
            # 상태
            status = EmailStatus.READ if is_read else EmailStatus.UNREAD
            
            return EmailMessage(
                id=email_id,
                sender=sender_email,
                sender_name=sender_name,
                recipients=recipients,
                cc=cc_list,
                subject=subject,
                body=body,
                body_html=body_html,
                received_date=received_date,
                is_read=is_read,
                has_attachments=has_attachments,
                attachment_count=0,  # Graph API에서는 별도로 계산 필요
                priority=priority,
                status=status,
                raw_data=graph_message
            )
            
        except Exception as e:
            st.error(f"메시지 변환 실패: {str(e)}")
            return None 