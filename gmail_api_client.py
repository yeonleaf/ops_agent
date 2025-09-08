#!/usr/bin/env python3
"""
실제 Gmail API 클라이언트
Google API를 사용하여 Gmail에서 메일을 가져옵니다.
자동 토큰 갱신 및 재발급 기능 포함
"""

import os
import base64
import email
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Google API 클라이언트
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests

# Gmail API 스코프
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly'
]

class GmailAPIClient:
    """실제 Gmail API를 사용하는 클라이언트 - 자동 토큰 갱신 기능 포함"""
    
    def __init__(self):
        self.service = None
        self.creds = None
        self.token_file = "gmail_tokens.json"
        self.last_token_refresh = None
        self.token_refresh_attempts = 0
        self.max_refresh_attempts = 3
        self.last_refresh_attempt_time = None
        self.min_refresh_interval = 30  # 최소 30초 간격
        
        # API 호출 캐싱
        self._cache = {}
        self._cache_ttl = 60  # 60초 캐시 유지
    
    def _get_cache_key(self, method: str, **kwargs) -> str:
        """캐시 키 생성"""
        import hashlib
        key_data = f"{method}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 검사"""
        if cache_key not in self._cache:
            return False
        
        cache_time, _ = self._cache[cache_key]
        return (datetime.now() - cache_time).total_seconds() < self._cache_ttl
    
    def _get_from_cache(self, cache_key: str):
        """캐시에서 데이터 가져오기"""
        if self._is_cache_valid(cache_key):
            _, data = self._cache[cache_key]
            print(f"📦 캐시에서 데이터 반환: {cache_key[:8]}...")
            return data
        return None
    
    def _save_to_cache(self, cache_key: str, data):
        """캐시에 데이터 저장"""
        self._cache[cache_key] = (datetime.now(), data)
        print(f"💾 캐시에 데이터 저장: {cache_key[:8]}...")
        
    def authenticate(self, force_refresh: bool = False):
        """Gmail API 인증 - 자동 토큰 갱신 포함"""
        try:
            # 저장된 토큰 파일 확인
            if not force_refresh and self._load_saved_tokens():
                if self._is_token_valid():
                    print("✅ 저장된 토큰 사용")
                    return self._build_service()
            
            # 환경변수에서 인증 정보 가져오기
            client_id = os.getenv('GMAIL_CLIENT_ID')
            client_secret = os.getenv('GMAIL_CLIENT_SECRET')
            refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
            
            if not all([client_id, client_secret, refresh_token]):
                print("❌ Gmail 인증 정보가 .env 파일에 설정되지 않았습니다.")
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
            
            # 토큰 갱신 시도
            if self._refresh_token():
                # 토큰 저장
                self._save_tokens()
                return self._build_service()
            else:
                # 토큰 갱신 실패 시 재발급 시도
                return self._request_new_tokens(client_id, client_secret)
            
        except Exception as e:
            print(f"❌ Gmail 인증 실패: {str(e)}")
            return False
    
    def _load_saved_tokens(self) -> bool:
        """저장된 토큰 파일 로드"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                
                # Credentials 객체 재생성
                self.creds = Credentials(
                    token_data.get('access_token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=SCOPES,
                    expiry=datetime.fromisoformat(token_data.get('expiry')) if token_data.get('expiry') else None
                )
                
                self.last_token_refresh = datetime.now()
                return True
                
        except Exception as e:
            print(f"저장된 토큰 로드 실패: {e}")
        
        return False
    
    def _save_tokens(self):
        """현재 토큰을 파일에 저장"""
        try:
            if self.creds:
                token_data = {
                    'access_token': self.creds.token,
                    'refresh_token': self.creds.refresh_token,
                    'client_id': self.creds.client_id,
                    'client_secret': self.creds.client_secret,
                    'scopes': self.creds.scopes,
                    'expiry': self.creds.expiry.isoformat() if self.creds.expiry else None,
                    'last_refresh': datetime.now().isoformat()
                }
                
                with open(self.token_file, 'w') as f:
                    json.dump(token_data, f, indent=2)
                
                print("✅ 토큰 저장 완료")
                
        except Exception as e:
            print(f"토큰 저장 실패: {e}")
    
    def _is_token_valid(self) -> bool:
        """토큰이 유효한지 확인"""
        try:
            if not self.creds:
                return False
            
            # 만료 시간 확인
            if self.creds.expired:
                return False
            
            # API 호출 테스트
            test_service = build('gmail', 'v1', credentials=self.creds)
            test_service.users().getProfile(userId='me').execute()
            
            return True
            
        except Exception as e:
            print(f"토큰 유효성 검사 실패: {e}")
            return False
    
    def _refresh_token(self) -> bool:
        """토큰 갱신 시도"""
        try:
            if not self.creds:
                return False
            
            # 갱신 시도 횟수 제한
            if self.token_refresh_attempts >= self.max_refresh_attempts:
                print(f"❌ 토큰 갱신 시도 횟수 초과 ({self.max_refresh_attempts}회)")
                return False
            
            self.token_refresh_attempts += 1
            print(f"🔄 토큰 갱신 시도 {self.token_refresh_attempts}/{self.max_refresh_attempts}")
            
            # 토큰 갱신
            self.creds.refresh(Request())
            self.last_token_refresh = datetime.now()
            self.last_refresh_attempt_time = datetime.now()
            self.token_refresh_attempts = 0  # 성공 시 카운터 리셋
            
            # 토큰 갱신 후 상태 확인
            if self.creds.expired:
                print("⚠️ 토큰 갱신 후에도 만료 상태입니다. 재시도가 필요할 수 있습니다.")
                return False
            
            print("✅ 토큰 갱신 성공")
            return True
            
        except Exception as e:
            print(f"❌ 토큰 갱신 실패: {e}")
            return False
    
    def _request_new_tokens(self, client_id: str, client_secret: str) -> bool:
        """새로운 토큰 발급 요청 (자동 OAuth + .env 업데이트)"""
        try:
            print("🆕 새로운 토큰 발급 시도")
            print("📝 Gmail 계정 재인증이 필요합니다.")
            print("💡 자동 OAuth 인증을 시작합니다...")
            print()
            
            # 자동 OAuth 인증 사용
            from oauth_local_server import get_oauth_auth_code
            
            # 토큰 정보 획득 (인증 코드 + 토큰 교환 포함)
            token_info = get_oauth_auth_code(
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            if token_info and token_info.get('access_token'):
                try:
                    # 수동으로 Credentials 객체 생성
                    from google.oauth2.credentials import Credentials
                    from datetime import datetime, timedelta
                    
                    # 토큰 만료 시간 계산
                    expires_in = token_info.get('expires_in', 3600)
                    expiry = datetime.now() + timedelta(seconds=expires_in)
                    
                    # Credentials 객체 생성
                    self.creds = Credentials(
                        token=token_info.get('access_token'),
                        refresh_token=token_info.get('refresh_token'),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=client_id,
                        client_secret=client_secret,
                        scopes=SCOPES,
                        expiry=expiry
                    )
                    
                    # 새 토큰을 .env 파일에 자동 저장 (반드시 성공해야 함)
                    refresh_token = token_info.get('refresh_token')
                    if refresh_token:
                        print(f"🔄 새로운 리프레시 토큰 획득: {refresh_token[:20]}...")
                        
                        # .env 파일 강제 업데이트
                        if self._force_update_env_refresh_token(refresh_token):
                            print("✅ .env 파일 강제 업데이트 성공!")
                            
                            # 새 토큰 저장
                            self._save_tokens()
                            self.token_refresh_attempts = 0
                            
                            print("✅ 새로운 토큰 발급 성공!")
                            print("💾 .env 파일의 리프레시 토큰이 자동으로 업데이트되었습니다.")
                            print("🔄 이제 새로운 토큰으로 Gmail API를 사용할 수 있습니다.")
                            
                            # 환경 변수 즉시 리로드
                            self._reload_env_variables()
                            
                            return self._build_service()
                        else:
                            print("❌ .env 파일 업데이트 실패 - 토큰 발급을 중단합니다.")
                            return False
                    else:
                        print("❌ 리프레시 토큰을 찾을 수 없습니다.")
                        return False
                    
                except Exception as e:
                    print(f"❌ Credentials 객체 생성 실패: {e}")
                    return False
            else:
                print("❌ 토큰 정보를 가져올 수 없습니다.")
                return False
                
        except Exception as e:
            print(f"❌ 새 토큰 발급 실패: {e}")
            print("💡 Google Cloud Console 설정을 확인해주세요.")
            return False

    def _update_env_refresh_token(self, new_refresh_token: str) -> bool:
        """새로운 리프레시 토큰을 .env 파일에 자동 저장 (강화된 버전)"""
        try:
            import os
            import re
            
            # .env 파일 경로
            env_file_path = '.env'
            
            print(f"💾 .env 파일 업데이트 시작: {env_file_path}")
            
            if not os.path.exists(env_file_path):
                print("⚠️  .env 파일이 존재하지 않습니다. 새로 생성합니다.")
                if self._create_env_file(env_file_path, new_refresh_token):
                    print("✅ 새 .env 파일 생성 완료")
                    return True
                else:
                    print("❌ 새 .env 파일 생성 실패")
                    return False
            
            # .env 파일 읽기
            try:
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                print("✅ .env 파일 읽기 성공")
            except Exception as e:
                print(f"❌ .env 파일 읽기 실패: {e}")
                return False
            
            # 기존 GMAIL_REFRESH_TOKEN 찾기 및 교체
            if 'GMAIL_REFRESH_TOKEN=' in content:
                print("🔄 기존 GMAIL_REFRESH_TOKEN을 새 값으로 교체합니다.")
                # 기존 값 교체 (정규식으로 정확한 매칭)
                new_content = re.sub(
                    r'GMAIL_REFRESH_TOKEN=.*?(?:\n|$)',
                    f'GMAIL_REFRESH_TOKEN={new_refresh_token}',
                    content,
                    flags=re.MULTILINE
                )
            else:
                print("➕ GMAIL_REFRESH_TOKEN을 새로 추가합니다.")
                # 새로 추가 (파일 끝에 추가)
                new_content = content.rstrip() + f'\nGMAIL_REFRESH_TOKEN={new_refresh_token}\n'
            
            # .env 파일 업데이트
            try:
                with open(env_file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print("✅ .env 파일 쓰기 성공")
            except Exception as e:
                print(f"❌ .env 파일 쓰기 실패: {e}")
                return False
            
            # 업데이트 확인
            try:
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    updated_content = f.read()
                if f'GMAIL_REFRESH_TOKEN={new_refresh_token}' in updated_content:
                    print(f"✅ .env 파일 업데이트 검증 완료: GMAIL_REFRESH_TOKEN={new_refresh_token[:20]}...")
                    return True
                else:
                    print("❌ .env 파일 업데이트 검증 실패")
                    return False
            except Exception as e:
                print(f"❌ .env 파일 검증 실패: {e}")
                return False
            
        except Exception as e:
            print(f"❌ .env 파일 업데이트 중 예외 발생: {e}")
            return False
    
    def _create_env_file(self, env_file_path: str, refresh_token: str) -> bool:
        """새 .env 파일 생성 (강화된 버전)"""
        try:
            import os
            
            print(f"📝 새 .env 파일 생성 시작: {env_file_path}")
            
            # 환경 변수 수집
            env_vars = {
                'GMAIL_CLIENT_ID': os.getenv('GMAIL_CLIENT_ID', ''),
                'GMAIL_CLIENT_SECRET': os.getenv('GMAIL_CLIENT_SECRET', ''),
                'GMAIL_REFRESH_TOKEN': refresh_token,
                'AZURE_OPENAI_API_KEY': os.getenv('AZURE_OPENAI_API_KEY', ''),
                'AZURE_OPENAI_ENDPOINT': os.getenv('AZURE_OPENAI_ENDPOINT', ''),
                'AZURE_OPENAI_API_VERSION': os.getenv('AZURE_OPENAI_API_VERSION', ''),
                'AZURE_OPENAI_DEPLOYMENT_NAME': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', '')
            }
            
            # .env 파일 내용 생성
            env_content = "# Gmail API 설정\n"
            env_content += f"GMAIL_CLIENT_ID={env_vars['GMAIL_CLIENT_ID']}\n"
            env_content += f"GMAIL_CLIENT_SECRET={env_vars['GMAIL_CLIENT_SECRET']}\n"
            env_content += f"GMAIL_REFRESH_TOKEN={env_vars['GMAIL_REFRESH_TOKEN']}\n\n"
            env_content += "# Azure OpenAI 설정\n"
            env_content += f"AZURE_OPENAI_API_KEY={env_vars['AZURE_OPENAI_API_KEY']}\n"
            env_content += f"AZURE_OPENAI_ENDPOINT={env_vars['AZURE_OPENAI_ENDPOINT']}\n"
            env_content += f"AZURE_OPENAI_API_VERSION={env_vars['AZURE_OPENAI_API_VERSION']}\n"
            env_content += f"AZURE_OPENAI_DEPLOYMENT_NAME={env_vars['AZURE_OPENAI_DEPLOYMENT_NAME']}\n"
            
            # .env 파일 쓰기
            try:
                with open(env_file_path, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                print("✅ .env 파일 쓰기 성공")
            except Exception as e:
                print(f"❌ .env 파일 쓰기 실패: {e}")
                return False
            
            # 생성된 파일 검증
            try:
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    created_content = f.read()
                
                # 필수 값들이 포함되어 있는지 확인
                required_keys = ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN']
                missing_keys = [key for key in required_keys if f'{key}=' not in created_content]
                
                if not missing_keys:
                    print("✅ .env 파일 생성 검증 완료")
                    print(f"📊 생성된 환경 변수: {len(env_vars)}개")
                    return True
                else:
                    print(f"❌ .env 파일 검증 실패 - 누락된 키: {missing_keys}")
                    return False
                    
            except Exception as e:
                print(f"❌ .env 파일 검증 실패: {e}")
                return False
            
        except Exception as e:
            print(f"❌ .env 파일 생성 중 예외 발생: {e}")
            return False

    def _force_update_env_refresh_token(self, new_refresh_token: str) -> bool:
        """새로운 리프레시 토큰을 .env 파일에 강제로 업데이트"""
        try:
            import os
            import re
            
            print(f"💾 .env 파일 강제 업데이트 시작: {new_refresh_token[:20]}...")
            
            # .env 파일 경로
            env_file_path = '.env'
            
            # 1단계: 기존 .env 파일 백업
            backup_path = f'.env.backup.{int(time.time())}'
            if os.path.exists(env_file_path):
                try:
                    import shutil
                    shutil.copy2(env_file_path, backup_path)
                    print(f"✅ 기존 .env 파일 백업 완료: {backup_path}")
                except Exception as e:
                    print(f"⚠️  백업 실패 (계속 진행): {e}")
            
            # 2단계: 새 .env 파일 생성 (기존 파일 덮어쓰기)
            try:
                # 현재 환경 변수 수집
                current_env_vars = {
                    'GMAIL_CLIENT_ID': os.getenv('GMAIL_CLIENT_ID', ''),
                    'GMAIL_CLIENT_SECRET': os.getenv('GMAIL_CLIENT_SECRET', ''),
                    'GMAIL_REFRESH_TOKEN': new_refresh_token,
                    'AZURE_OPENAI_API_KEY': os.getenv('AZURE_OPENAI_API_KEY', ''),
                    'AZURE_OPENAI_ENDPOINT': os.getenv('AZURE_OPENAI_ENDPOINT', ''),
                    'AZURE_OPENAI_API_VERSION': os.getenv('AZURE_OPENAI_API_VERSION', ''),
                    'AZURE_OPENAI_DEPLOYMENT_NAME': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', '')
                }
                
                # .env 파일 내용 생성
                env_content = "# Gmail API 설정\n"
                env_content += f"GMAIL_CLIENT_ID={current_env_vars['GMAIL_CLIENT_ID']}\n"
                env_content += f"GMAIL_CLIENT_SECRET={current_env_vars['GMAIL_CLIENT_SECRET']}\n"
                env_content += f"GMAIL_REFRESH_TOKEN={current_env_vars['GMAIL_REFRESH_TOKEN']}\n\n"
                env_content += "# Azure OpenAI 설정\n"
                env_content += f"AZURE_OPENAI_API_KEY={current_env_vars['AZURE_OPENAI_API_KEY']}\n"
                env_content += f"AZURE_OPENAI_ENDPOINT={current_env_vars['AZURE_OPENAI_ENDPOINT']}\n"
                env_content += f"AZURE_OPENAI_API_VERSION={current_env_vars['AZURE_OPENAI_API_VERSION']}\n"
                env_content += f"AZURE_OPENAI_DEPLOYMENT_NAME={current_env_vars['AZURE_OPENAI_DEPLOYMENT_NAME']}\n"
                
                # .env 파일 강제 쓰기
                with open(env_file_path, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                
                print("✅ .env 파일 강제 쓰기 완료")
                
            except Exception as e:
                print(f"❌ .env 파일 강제 쓰기 실패: {e}")
                return False
            
            # 3단계: 업데이트 검증
            try:
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    updated_content = f.read()
                
                # 필수 값들이 포함되어 있는지 확인
                required_keys = ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN']
                missing_keys = [key for key in required_keys if f'{key}=' not in updated_content]
                
                if not missing_keys and f'GMAIL_REFRESH_TOKEN={new_refresh_token}' in updated_content:
                    print("✅ .env 파일 강제 업데이트 검증 완료")
                    print(f"📊 업데이트된 환경 변수: {len(current_env_vars)}개")
                    print(f"🔄 새로운 리프레시 토큰: {new_refresh_token[:20]}...")
                    return True
                else:
                    print(f"❌ .env 파일 검증 실패 - 누락된 키: {missing_keys}")
                    return False
                    
            except Exception as e:
                print(f"❌ .env 파일 검증 실패: {e}")
                return False
            
        except Exception as e:
            print(f"❌ .env 파일 강제 업데이트 중 예외 발생: {e}")
            return False

    def _reload_env_variables(self) -> None:
        """환경 변수를 즉시 리로드"""
        try:
            import os
            from dotenv import load_dotenv
            
            print("🔄 환경 변수 즉시 리로드 중...")
            
            # .env 파일 다시 로드
            load_dotenv(override=True)
            
            # GMAIL_REFRESH_TOKEN 확인
            new_token = os.getenv('GMAIL_REFRESH_TOKEN')
            if new_token:
                print(f"✅ 환경 변수 리로드 완료: GMAIL_REFRESH_TOKEN={new_token[:20]}...")
            else:
                print("⚠️  환경 변수 리로드 후에도 GMAIL_REFRESH_TOKEN을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"⚠️  환경 변수 리로드 실패: {e}")
    
    def _build_service(self) -> bool:
        """Gmail API 서비스 빌드"""
        try:
            if self.creds:
                self.service = build('gmail', 'v1', credentials=self.creds)
                return True
        except Exception as e:
            print(f"서비스 빌드 실패: {e}")
        
        return False
    
    def _auto_refresh_if_needed(self):
        """필요시 자동 토큰 갱신"""
        try:
            if not self.creds:
                return False
            
            # 최근 갱신 시도 시간 확인 (무한 루프 방지)
            now = datetime.now()
            if (self.last_refresh_attempt_time and 
                (now - self.last_refresh_attempt_time).total_seconds() < self.min_refresh_interval):
                print("⏳ 토큰 갱신 간격이 너무 짧습니다. 잠시 대기...")
                return True
            
            # 토큰이 만료되었거나 곧 만료될 예정인 경우
            if self.creds.expired or (self.creds.expiry and 
                self.creds.expiry - datetime.now() < timedelta(minutes=5)):
                
                print("🔄 토큰 만료 임박, 자동 갱신 시도")
                self.last_refresh_attempt_time = now
                
                if self._refresh_token():
                    self._save_tokens()
                    print("✅ 토큰 저장 완료")
                    return True
                else:
                    print("❌ 자동 토큰 갱신 실패")
                    return False
            
            return True
            
        except Exception as e:
            print(f"자동 토큰 갱신 오류: {e}")
            return False
    
    def get_unread_emails(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """안읽은 메일 가져오기"""
        # 캐시 확인
        cache_key = self._get_cache_key("get_unread_emails", max_results=max_results)
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        if not self.service:
            if not self.authenticate():
                return []
        
        # 자동 토큰 갱신 확인
        if not self._auto_refresh_if_needed():
            if not self.authenticate(force_refresh=True):
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
            
            # 캐시에 저장
            self._save_to_cache(cache_key, emails)
            return emails
            
        except HttpError as error:
            if error.resp.status == 401:  # 인증 오류
                print("🔐 인증 오류 발생, 토큰 재발급 시도")
                if self.authenticate(force_refresh=True):
                    # 재귀 호출 대신 현재 요청 재시도
                    try:
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
                        
                        # 캐시에 저장
                        self._save_to_cache(cache_key, emails)
                        return emails
                    except Exception as retry_error:
                        print(f"❌ 재시도 실패: {retry_error}")
                        return []
                else:
                    print("❌ Gmail 인증 실패")
                    return []
            else:
                print(f"❌ Gmail API 오류: {error}")
                return []
        except Exception as e:
            print(f"❌ 메일 가져오기 실패: {str(e)}")
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """메일 상세 정보 가져오기"""
        try:
            # 자동 토큰 갱신 확인
            if not self._auto_refresh_if_needed():
                if not self.authenticate(force_refresh=True):
                    return None
            
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
            
        except HttpError as error:
            if error.resp.status == 401:  # 인증 오류
                print("🔐 인증 오류 발생, 토큰 재발급 시도")
                if self.authenticate(force_refresh=True):
                    return self.get_email_details(message_id)  # 재귀 호출
                else:
                    print("❌ Gmail 인증 실패")
                    return None
            else:
                print(f"❌ 메일 상세 정보 가져오기 실패: {error}")
                return None
        except Exception as e:
            print(f"❌ 메일 상세 정보 가져오기 실패: {str(e)}")
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
        
        # 자동 토큰 갱신 확인
        if not self._auto_refresh_if_needed():
            if not self.authenticate(force_refresh=True):
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
            if error.resp.status == 401:  # 인증 오류
                print("🔐 인증 오류 발생, 토큰 재발급 시도")
                if self.authenticate(force_refresh=True):
                    # 재귀 호출 대신 현재 요청 재시도
                    try:
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
                    except Exception as retry_error:
                        print(f"❌ 재시도 실패: {retry_error}")
                        return []
                else:
                    print("❌ Gmail 인증 실패")
                    return []
            else:
                print(f"❌ Gmail API 오류: {error}")
                return []
        except Exception as e:
            print(f"❌ 메일 가져오기 실패: {str(e)}")
            return []

    def search_emails(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Gmail 검색 쿼리로 메일 검색"""
        if not self.service:
            if not self.authenticate():
                return []
        
        # 자동 토큰 갱신 확인
        if not self._auto_refresh_if_needed():
            if not self.authenticate(force_refresh=True):
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
            if error.resp.status == 401:  # 인증 오류
                print("🔐 인증 오류 발생, 토큰 재발급 시도")
                if self.authenticate(force_refresh=True):
                    # 재귀 호출 대신 현재 요청 재시도
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
                    except Exception as retry_error:
                        print(f"❌ 재시도 실패: {retry_error}")
                        return []
                else:
                    print("❌ Gmail 인증 실패")
                    return []
            else:
                print(f"❌ Gmail 검색 오류: {error}")
                return []
        except Exception as e:
            print(f"❌ 메일 검색 실패: {str(e)}")
            return []

    def get_emails_with_query(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Gmail 검색 쿼리로 메일 검색 (search_emails의 별칭)"""
        return self.search_emails(query, max_results)
    
    def get_token_status(self) -> Dict[str, Any]:
        """현재 토큰 상태 정보 반환"""
        try:
            if not self.creds:
                return {
                    "status": "not_authenticated",
                    "message": "인증되지 않음"
                }
            
            # 토큰 유효성 확인
            is_valid = self._is_token_valid()
            
            status_info = {
                "status": "valid" if is_valid else "expired",
                "has_credentials": bool(self.creds),
                "has_refresh_token": bool(self.creds.refresh_token),
                "expiry": self.creds.expiry.isoformat() if self.creds.expiry else None,
                "last_refresh": self.last_token_refresh.isoformat() if self.last_token_refresh else None,
                "refresh_attempts": self.token_refresh_attempts,
                "max_refresh_attempts": self.max_refresh_attempts
            }
            
            if not is_valid:
                status_info["message"] = "토큰이 만료되었습니다. 자동 갱신을 시도하거나 재인증이 필요합니다."
            else:
                status_info["message"] = "토큰이 유효합니다."
            
            return status_info
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"토큰 상태 확인 오류: {str(e)}"
            }
    
    def force_token_refresh(self) -> bool:
        """강제로 토큰 갱신 시도"""
        try:
            print("🔄 강제 토큰 갱신 시도")
            if self._refresh_token():
                self._save_tokens()
                return True
            else:
                print("❌ 강제 토큰 갱신 실패")
                return False
        except Exception as e:
            print(f"강제 토큰 갱신 오류: {e}")
            return False

# Gmail API 클라이언트 인스턴스
gmail_client = GmailAPIClient()

def get_gmail_client() -> GmailAPIClient:
    """Gmail API 클라이언트 반환"""
    return gmail_client 