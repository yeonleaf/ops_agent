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
    
    def authenticate(self, cookies: str = None) -> bool:
        """Gmail API 인증 - OAuth2 액세스 토큰 필수"""
        try:
            access_token = None
            
            # 1. 설정에서 토큰 확인 (우선순위)
            if self.config.access_token:
                access_token = self.config.access_token
                print(f"⚙️ 설정에서 Gmail 토큰 사용: {access_token[:20]}...")
            
            # 2. 쿠키에서 토큰 추출 시도 (백업)
            elif cookies:
                cookie_dict = {}
                for cookie in cookies.split(';'):
                    if '=' in cookie:
                        key, value = cookie.strip().split('=', 1)
                        cookie_dict[key] = value
                
                access_token = cookie_dict.get("gmail_access_token")
                print(f"🍪 쿠키에서 Gmail 토큰 추출: {'성공' if access_token else '실패'}")
            
            # 3. 토큰이 있으면 인증 시도
            if access_token:
                self.creds = Credentials(token=access_token)
                self.service = build('gmail', 'v1', credentials=self.creds)
                self.is_authenticated = True
                print(f"✅ Gmail API 인증 성공 (토큰: {access_token[:20]}...)")
                return True
            
            # 레거시 refresh_token 방식 (경고와 함께)
            if self.config.refresh_token:
                print("⚠️ 레거시 refresh_token 방식 사용 중. OAuth2 서버 사용을 권장합니다.")
                self.creds = Credentials(
                    None,  # access_token은 자동 갱신됨
                    refresh_token=self.config.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret,
                    scopes=self.scopes
                )
            else:
                print("❌ OAuth2 인증이 필요합니다. 액세스 토큰을 제공하거나 OAuth 서버를 사용하세요.")
                print("💡 OAuth 서버 사용: http://localhost:8000/auth/login/gmail")
                return False
            
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
            # 토큰 만료 시 refresh 시도
            if error.resp.status == 401:  # Unauthorized
                print("🍪 Gmail API 토큰 만료 - refresh 시도")
                try:
                    from auth_client import auth_client
                    from gmail_provider import refresh_gmail_token
                    
                    # DB에서 refresh_token으로 새로운 access_token 발급
                    refresh_result = refresh_gmail_token()
                    if refresh_result.get("success"):
                        print("🍪 토큰 refresh 성공 - 재시도")
                        # 새로운 토큰으로 재인증
                        self.access_token = refresh_result.get("access_token")
                        self.is_authenticated = False  # 재인증 필요
                        
                        if self.authenticate():
                            # 재시도
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
                        else:
                            print("🍪 토큰 refresh 후 재인증 실패")
                    else:
                        print("🍪 토큰 refresh 실패")
                except Exception as refresh_error:
                    print(f"🍪 토큰 refresh 중 오류: {refresh_error}")
            
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
            # 토큰 만료 시 refresh 시도
            if error.resp.status == 401:  # Unauthorized
                print("🍪 Gmail API 토큰 만료 - refresh 시도")
                try:
                    from auth_client import auth_client
                    from gmail_provider import refresh_gmail_token
                    
                    # DB에서 refresh_token으로 새로운 access_token 발급
                    refresh_result = refresh_gmail_token()
                    if refresh_result.get("success"):
                        print("🍪 토큰 refresh 성공 - 재시도")
                        # 새로운 토큰으로 재인증
                        self.access_token = refresh_result.get("access_token")
                        self.is_authenticated = False  # 재인증 필요
                        
                        if self.authenticate():
                            # 재시도
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
                        else:
                            print("🍪 토큰 refresh 후 재인증 실패")
                    else:
                        print("🍪 토큰 refresh 실패")
                except Exception as refresh_error:
                    print(f"🍪 토큰 refresh 중 오류: {refresh_error}")
            
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
            
        except HttpError as error:
            # 토큰 만료 시 refresh 시도
            if error.resp.status == 401:  # Unauthorized
                print("🍪 Gmail API 토큰 만료 - refresh 시도")
                try:
                    from auth_client import auth_client
                    from gmail_provider import refresh_gmail_token
                    
                    # DB에서 refresh_token으로 새로운 access_token 발급
                    refresh_result = refresh_gmail_token()
                    if refresh_result.get("success"):
                        print("🍪 토큰 refresh 성공 - 재시도")
                        # 새로운 토큰으로 재인증
                        self.access_token = refresh_result.get("access_token")
                        self.is_authenticated = False  # 재인증 필요
                        
                        if self.authenticate():
                            # 재시도
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
                        else:
                            print("🍪 토큰 refresh 후 재인증 실패")
                    else:
                        print("🍪 토큰 refresh 실패")
                except Exception as refresh_error:
                    print(f"🍪 토큰 refresh 중 오류: {refresh_error}")
            
            st.error(f"Gmail API 오류: {error}")
            return None
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


def refresh_gmail_token() -> Dict[str, Any]:
    """DB에 저장된 refresh_token으로 access_token 재발급"""
    try:
        print("🔄 refresh_gmail_token 시작")
        print("🍪 auth_client import 시도")
        try:
            from auth_client import auth_client
            print("🍪 auth_client import 성공")
        except Exception as import_error:
            print(f"❌ auth_client import 실패: {import_error}")
            return {"success": False, "message": f"auth_client import 실패: {str(import_error)}"}
        
        # 사용자가 로그인되어 있는지 확인
        print("🍪 auth_client.is_logged_in() 호출 시작")
        try:
            is_logged_in = auth_client.is_logged_in()
            print(f"🍪 로그인 상태: {is_logged_in}")
        except Exception as login_error:
            print(f"❌ 로그인 상태 확인 중 오류: {login_error}")
            return {"success": False, "message": f"로그인 상태 확인 실패: {str(login_error)}"}
        
        if not is_logged_in:
            print("❌ 사용자가 로그인되지 않음")
            return {"success": False, "message": "사용자가 로그인되지 않음"}
        
        # 현재 사용자 정보 가져오기
        print("🍪 auth_client.get_current_user() 호출 시작")
        try:
            user_info = auth_client.get_current_user()
            print(f"🍪 사용자 정보: {user_info}")
            print(f"🍪 사용자 정보 타입: {type(user_info)}")
        except Exception as user_error:
            print(f"❌ 사용자 정보 조회 중 오류: {user_error}")
            return {"success": False, "message": f"사용자 정보 조회 실패: {str(user_error)}"}
        
        if not user_info or 'email' not in user_info or 'user_id' not in user_info:
            print("❌ 사용자 정보를 가져올 수 없음")
            print(f"🍪 user_info: {user_info}")
            print(f"🍪 email 키 존재: {'email' in user_info if user_info else False}")
            print(f"🍪 user_id 키 존재: {'user_id' in user_info if user_info else False}")
            return {"success": False, "message": "사용자 정보를 가져올 수 없음"}
        
        # DB에서 직접 Google 연동 정보 조회
        print(f"🔍 DB에서 사용자 조회: {user_info['email']}")
        try:
            from database_models import DatabaseManager
            print("🍪 DatabaseManager import 성공")
            db_manager = DatabaseManager()
            print("🍪 DatabaseManager 인스턴스 생성 성공")
            user = db_manager.get_user_by_email(user_info['email'])
            print(f"🍪 DB 사용자 정보: {user}")
            print(f"🍪 사용자 정보 타입: {type(user)}")
            if user:
                print(f"🍪 사용자 ID: {user.id}")
                print(f"🍪 사용자 이메일: {user.email}")
                print(f"🍪 google_refresh_token: {user.google_refresh_token}")
            else:
                print("❌ DB에서 사용자 정보를 찾을 수 없음")
        except Exception as db_error:
            print(f"❌ DB 조회 중 오류: {db_error}")
            return {"success": False, "message": f"DB 조회 실패: {str(db_error)}"}
        
        if not user or not user.google_refresh_token:  # google_refresh_token이 없음
            print("❌ DB에 Google 토큰이 없음")
            print("ℹ️ Gmail 기능을 사용하려면 OAuth 인증이 필요합니다.")
            print("ℹ️ 사이드바의 'Gmail 로그인' 버튼을 클릭하세요.")
            return {"success": False, "message": "DB에 Google 토큰이 없음", "needs_oauth": True}
        
        # 토큰 가져오기 (POC 모드: 암호화 비활성화)
        print("🔓 POC 모드: 토큰을 그대로 사용")
        print(f"🍪 저장된 토큰 (처음 50자): {user.google_refresh_token[:50] if user.google_refresh_token else 'None'}")
        
        # POC 모드에서는 토큰을 그대로 사용
        refresh_token = user.google_refresh_token
        print(f"🍪 사용할 refresh_token: {refresh_token[:20]}..." if refresh_token else "None")
        
        if not refresh_token:
            print("❌ DB에서 refresh_token을 가져올 수 없음")
            return {"success": False, "message": "DB에서 refresh_token을 가져올 수 없음"}
        
        # Google OAuth2 클라이언트 설정
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        print(f"🔑 OAuth 설정 확인:")
        print(f"  - CLIENT_ID: {client_id[:10]}..." if client_id else "  - CLIENT_ID: None")
        print(f"  - CLIENT_SECRET: {'설정됨' if client_secret else 'None'}")
        print(f"  - REFRESH_TOKEN 길이: {len(refresh_token) if refresh_token else 0}")
        
        if not all([client_id, client_secret, refresh_token]):
            print("❌ OAuth 설정이 불완전함")
            return {"success": False, "message": "Gmail OAuth 설정이 불완전함"}
        
        # refresh_token으로 access_token 재발급
        print("🔄 Google Credentials 객체 생성 중...")
        try:
            credentials = Credentials(
                token=None,  # access_token은 None으로 시작
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret
            )
            print("✅ Credentials 객체 생성 성공")
        except Exception as cred_error:
            print(f"❌ Credentials 객체 생성 실패: {cred_error}")
            return {"success": False, "message": f"Credentials 생성 실패: {str(cred_error)}"}
        
        # 토큰 갱신
        print("🔄 토큰 갱신 시도...")
        try:
            from google.auth.transport.requests import Request
            request = Request()
            print("📡 Google API로 토큰 갱신 요청 전송...")
            credentials.refresh(request)
            print("✅ 토큰 갱신 성공!")
            print(f"🎯 새로운 access_token: {credentials.token[:20]}..." if credentials.token else "None")
            print(f"🎯 새로운 refresh_token: {credentials.refresh_token[:20]}..." if credentials.refresh_token else "None")
        except Exception as refresh_error:
            print(f"❌ 토큰 갱신 실패: {refresh_error}")
            print(f"❌ 에러 타입: {type(refresh_error).__name__}")
            
            # 더 구체적인 에러 정보
            if hasattr(refresh_error, 'response'):
                print(f"📡 HTTP 응답 상태: {refresh_error.response.status_code if refresh_error.response else 'None'}")
                if refresh_error.response:
                    try:
                        error_details = refresh_error.response.json()
                        print(f"📡 에러 상세: {error_details}")
                    except:
                        print(f"📡 에러 텍스트: {refresh_error.response.text}")
            
            # invalid_grant 에러인 경우 토큰 만료로 처리
            if 'invalid_grant' in str(refresh_error).lower():
                print("🔄 토큰 만료 감지: 재인증 필요")
                
                # 만료된 토큰을 DB에서 제거
                try:
                    from fastmcp_server import db_manager
                    db_manager.update_user_google_token(user[0], None)  # user[0]는 user_id
                    print("🗑️ 만료된 refresh_token을 DB에서 제거했습니다")
                except Exception as cleanup_error:
                    print(f"⚠️ 토큰 정리 중 오류: {cleanup_error}")
                
                print("ℹ️ Gmail 기능을 사용하려면 OAuth 재인증이 필요합니다.")
                print("ℹ️ 사이드바의 'Gmail 로그인' 버튼을 클릭하세요.")
                
                return {
                    "success": False, 
                    "message": "refresh_token이 만료되어 OAuth 재인증이 필요합니다",
                    "needs_oauth": True,
                    "error_type": "token_expired"
                }
            
            return {"success": False, "message": f"토큰 갱신 실패: {str(refresh_error)}"}
        
        # 새로운 refresh_token을 DB에 저장 (POC: 암호화 비활성화)
        try:
            from fastmcp_server import db_manager
            # POC 모드: 토큰을 평문으로 저장
            db_manager.update_user_google_token(user[0], credentials.refresh_token)
            print(f"✅ 새로운 refresh_token이 DB에 저장되었습니다 (평문)")
        except Exception as e:
            print(f"⚠️ refresh_token DB 저장 중 오류: {e}")
        
        return {
            "success": True,
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_in": 3600  # 1시간
        }
        
    except Exception as e:
        return {"success": False, "message": f"토큰 재발급 실패: {str(e)}"} 