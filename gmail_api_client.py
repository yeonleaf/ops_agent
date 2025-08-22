#!/usr/bin/env python3
"""
실제 Gmail API 클라이언트
Google API를 사용하여 Gmail에서 메일을 가져옵니다.
"""

import os
import base64
import email
from typing import List, Dict, Any, Optional
from datetime import datetime
import streamlit as st

# Google API 클라이언트
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API 스코프
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly'
]

class GmailAPIClient:
    """실제 Gmail API를 사용하는 클라이언트"""
    
    def __init__(self):
        self.service = None
        self.creds = None
        
    def authenticate(self):
        """Gmail API 인증"""
        try:
            # 환경변수에서 인증 정보 가져오기
            client_id = os.getenv('GMAIL_CLIENT_ID')
            client_secret = os.getenv('GMAIL_CLIENT_SECRET')
            refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
            
            if not all([client_id, client_secret, refresh_token]):
                st.error("Gmail 인증 정보가 .env 파일에 설정되지 않았습니다.")
                return False
            
            # Credentials 객체 생성
            self.creds = Credentials(
                None,  # access_token은 자동 갱신됨
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            # 토큰 갱신
            if self.creds.expired:
                self.creds.refresh(Request())
            
            # Gmail API 서비스 생성
            self.service = build('gmail', 'v1', credentials=self.creds)
            return True
            
        except Exception as e:
            st.error(f"Gmail 인증 실패: {str(e)}")
            return False
    
    def get_unread_emails(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """안읽은 메일 가져오기"""
        if not self.service:
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
            emails = []
            
            for message in messages:
                email_data = self.get_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            st.error(f"Gmail API 오류: {error}")
            return []
        except Exception as e:
            st.error(f"메일 가져오기 실패: {str(e)}")
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """메일 상세 정보 가져오기"""
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            # 헤더 정보 추출
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 없음')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # 메일 본문 추출
            body = self.extract_email_body(message['payload'])
            
            # 라벨 정보
            labels = message.get('labelIds', [])
            
            return {
                'id': message_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'body': body,
                'labels': labels,
                'unread': 'UNREAD' in labels
            }
            
        except Exception as e:
            st.error(f"메일 상세 정보 가져오기 실패: {str(e)}")
            return None
    
    def extract_email_body(self, payload: Dict[str, Any]) -> str:
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
    
    def get_all_emails(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """모든 메일을 가져옵니다 (읽은 메일 + 안 읽은 메일)"""
        if not self.service:
            if not self.authenticate():
                return []
        
        try:
            # 모든 메일 가져오기 (라벨 제한 없음)
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                email_data = self.get_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            st.error(f"Gmail API 오류: {error}")
            return []
        except Exception as e:
            st.error(f"메일 가져오기 실패: {str(e)}")
            return []

    def search_emails(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Gmail 검색 쿼리로 메일 검색"""
        if not self.service:
            if not self.authenticate():
                return []
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                email_data = self.get_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            st.error(f"Gmail 검색 오류: {error}")
            return []
        except Exception as e:
            st.error(f"메일 검색 실패: {str(e)}")
            return []

    def get_emails_with_query(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Gmail 검색 쿼리로 메일 검색 (search_emails의 별칭)"""
        return self.search_emails(query, max_results)

# Gmail API 클라이언트 인스턴스
gmail_client = GmailAPIClient()

def get_gmail_client() -> GmailAPIClient:
    """Gmail API 클라이언트 반환"""
    return gmail_client 