#!/usr/bin/env python3
"""
OAuth 인증 에이전트
라우터 에이전트가 자동으로 OAuth 인증을 처리할 수 있도록 도와주는 에이전트
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OAuthAuthAgent:
    """OAuth 인증 에이전트"""
    
    def __init__(self):
        """초기화"""
        self.oauth_config = {
            "gmail": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback"),
                "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "scopes": ["openid", "profile", "email", "https://www.googleapis.com/auth/gmail.readonly"]
            },
            "microsoft": {
                "client_id": os.getenv("MICROSOFT_CLIENT_ID"),
                "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET"),
                "redirect_uri": os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback?provider=microsoft"),
                "auth_url": f"https://login.microsoftonline.com/{os.getenv('MICROSOFT_TENANT_ID', 'common')}/oauth2/v2.0/authorize",
                "token_url": f"https://login.microsoftonline.com/{os.getenv('MICROSOFT_TENANT_ID', 'common')}/oauth2/v2.0/token",
                "scopes": ["openid", "profile", "email", "Mail.ReadWrite", "offline_access"]
            }
        }
        
        # 인증 상태 저장 (실제로는 데이터베이스나 Redis 사용 권장)
        self.auth_sessions = {}
        self.active_tokens = {}
    
    def check_auth_required(self, provider: str, cookies: str = None) -> Dict[str, Any]:
        """인증이 필요한지 확인 (쿠키에서 토큰 확인)"""
        try:
            print(f"🍪 OAuth Auth Agent에서 쿠키 확인: {cookies[:100] if cookies else 'None'}...")
            
            # 쿠키에서 토큰 추출
            access_token = None
            refresh_token = None
            
            if cookies:
                # 쿠키 파싱
                cookie_dict = {}
                for cookie in cookies.split(';'):
                    if '=' in cookie:
                        key, value = cookie.strip().split('=', 1)
                        cookie_dict[key] = value
                
                print(f"🍪 파싱된 쿠키: {cookie_dict}")
                
                access_token = cookie_dict.get(f"{provider}_access_token")
                refresh_token = cookie_dict.get(f"{provider}_refresh_token")
                
                print(f"🍪 {provider}_access_token: {access_token[:20] if access_token else 'None'}...")
                print(f"🍪 {provider}_refresh_token: {refresh_token[:20] if refresh_token else 'None'}...")
            
            # 메모리에서도 확인 (백업)
            if provider in self.active_tokens:
                token_info = self.active_tokens[provider]
                if datetime.now() < token_info.get("expires_at", datetime.now()):
                    access_token = token_info.get("access_token")
                    refresh_token = token_info.get("refresh_token")
            
            # 토큰이 있으면 인증 완료
            if access_token:
                logger.info(f"✅ {provider.upper()} 인증 상태: 인증 완료 (토큰 존재)")
                return {
                    "auth_required": False,
                    "message": f"{provider.upper()} 인증이 이미 완료되었습니다.",
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }
            
            logger.info(f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 필요합니다.")
            return {
                "auth_required": True,
                "message": f"{provider.upper()} 인증이 필요합니다.",
                "provider": provider
            }
            
        except Exception as e:
            logger.error(f"❌ 인증 상태 확인 실패: {e}")
            return {
                "auth_required": True,
                "message": f"인증 상태 확인 중 오류가 발생했습니다: {e}",
                "provider": provider
            }
    
    def generate_auth_url(self, provider: str) -> Dict[str, Any]:
        """OAuth 인증 URL 생성"""
        try:
            if provider not in self.oauth_config:
                return {
                    "success": False,
                    "error": f"지원하지 않는 제공자: {provider}"
                }
            
            import secrets
            # 현재 로그인된 사용자 이메일 가져오기
            try:
                from auth_client import auth_client
                if auth_client.is_logged_in():
                    user_info = auth_client.get_user_info()
                    user_email = user_info.get('email', 'unknown@example.com')
                else:
                    user_email = 'unknown@example.com'
            except:
                user_email = 'unknown@example.com'
            
            # 이메일을 state에 포함
            state = f"email_{user_email}_{secrets.token_urlsafe(16)}"
            print(f"🍪 OAuth URL 생성: user_email={user_email}, state={state}")
            
            # 세션 저장
            self.auth_sessions[state] = {
                "provider": provider,
                "created_at": datetime.now(),
                "status": "pending"
            }
            
            config = self.oauth_config[provider]
            
            # URL 인코딩을 위한 urllib.parse 사용
            from urllib.parse import urlencode
            
            params = {
                'client_id': config['client_id'],
                'redirect_uri': config['redirect_uri'],
                'scope': ' '.join(config['scopes']),
                'response_type': 'code',
                'access_type': 'offline',
                'prompt': 'consent',
                'state': state
            }
            
            auth_url = f"{config['auth_url']}?{urlencode(params)}"
            
            logger.info(f"🔐 {provider.upper()} OAuth 인증 URL 생성: {state}")
            
            return {
                "success": True,
                "auth_url": auth_url,
                "state": state,
                "provider": provider,
                "message": f"{provider.upper()} OAuth 인증 URL이 생성되었습니다. 브라우저에서 이 URL을 열어 인증을 완료하세요."
            }
            
        except Exception as e:
            logger.error(f"❌ {provider.upper()} OAuth URL 생성 실패: {e}")
            return {
                "success": False,
                "error": f"OAuth URL 생성 실패: {e}"
            }
    
    def process_callback(self, provider: str, code: str, state: str) -> Dict[str, Any]:
        """OAuth 콜백 처리"""
        try:
            if state not in self.auth_sessions:
                return {
                    "success": False,
                    "error": "Invalid state token"
                }
            
            session = self.auth_sessions[state]
            if session["provider"] != provider:
                return {
                    "success": False,
                    "error": "Provider mismatch"
                }
            
            # 세션 정리
            del self.auth_sessions[state]
            
            if provider not in self.oauth_config:
                return {
                    "success": False,
                    "error": f"지원하지 않는 제공자: {provider}"
                }
            
            config = self.oauth_config[provider]
            
            # 토큰 교환
            import requests
            token_data = {
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
            }
            
            if provider == "microsoft":
                token_data["scope"] = " ".join(config["scopes"])
            
            response = requests.post(config["token_url"], data=token_data)
            response.raise_for_status()
            token_response = response.json()
            
            access_token = token_response.get("access_token")
            refresh_token = token_response.get("refresh_token")
            
            if not access_token:
                return {
                    "success": False,
                    "error": "Failed to get access token"
                }
            
            # 토큰 저장
            self.active_tokens[provider] = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": datetime.now() + timedelta(hours=1),  # 1시간 후 만료
                "created_at": datetime.now()
            }
            
            logger.info(f"✅ {provider.upper()} OAuth 인증 완료")
            
            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "provider": provider,
                "message": f"{provider.upper()} OAuth 인증이 완료되었습니다. 이제 이메일 서비스를 사용할 수 있습니다."
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 토큰 교환 실패: {e}")
            return {
                "success": False,
                "error": f"Token exchange failed: {e}"
            }
        except Exception as e:
            logger.error(f"❌ OAuth 콜백 처리 실패: {e}")
            return {
                "success": False,
                "error": f"Callback processing failed: {e}"
            }
    
    def refresh_token(self, provider: str) -> Dict[str, Any]:
        """토큰 재발급"""
        try:
            if provider not in self.active_tokens:
                return {
                    "success": False,
                    "error": f"{provider.upper()} 토큰이 없습니다. 다시 인증해주세요."
                }
            
            token_info = self.active_tokens[provider]
            refresh_token = token_info.get("refresh_token")
            
            if not refresh_token:
                return {
                    "success": False,
                    "error": f"{provider.upper()} refresh token이 없습니다. 다시 인증해주세요."
                }
            
            config = self.oauth_config[provider]
            
            # 토큰 재발급
            import requests
            token_data = {
                "refresh_token": refresh_token,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "grant_type": "refresh_token",
            }
            
            if provider == "microsoft":
                token_data["scope"] = " ".join(config["scopes"])
            
            response = requests.post(config["token_url"], data=token_data)
            response.raise_for_status()
            token_response = response.json()
            
            new_access_token = token_response.get("access_token")
            new_refresh_token = token_response.get("refresh_token", refresh_token)
            
            if not new_access_token:
                return {
                    "success": False,
                    "error": "Failed to get new access token"
                }
            
            # 토큰 업데이트
            self.active_tokens[provider] = {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": datetime.now() + timedelta(hours=1),
                "created_at": datetime.now()
            }
            
            logger.info(f"✅ {provider.upper()} 토큰 재발급 완료")
            
            return {
                "success": True,
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "provider": provider,
                "message": f"{provider.upper()} 토큰이 성공적으로 재발급되었습니다."
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 토큰 재발급 실패: {e}")
            return {
                "success": False,
                "error": f"Token refresh failed: {e}"
            }
        except Exception as e:
            logger.error(f"❌ 토큰 재발급 실패: {e}")
            return {
                "success": False,
                "error": f"Refresh failed: {e}"
            }
    
    def get_access_token(self, provider: str) -> Optional[str]:
        """현재 활성 access_token 반환"""
        if provider in self.active_tokens:
            token_info = self.active_tokens[provider]
            if datetime.now() < token_info.get("expires_at", datetime.now()):
                return token_info.get("access_token")
        return None
    
    def get_auth_status(self, provider: str) -> Dict[str, Any]:
        """인증 상태 확인"""
        try:
            has_token = provider in self.active_tokens
            is_valid = False
            access_token = None
            
            if has_token:
                token_info = self.active_tokens[provider]
                is_valid = datetime.now() < token_info.get("expires_at", datetime.now())
                if is_valid:
                    access_token = token_info.get("access_token")
            
            return {
                "provider": provider,
                "authenticated": has_token and is_valid,
                "has_token": has_token,
                "is_valid": is_valid,
                "access_token": access_token,
                "message": f"{provider.upper()} 인증 상태: {'인증됨' if (has_token and is_valid) else '인증되지 않음'}"
            }
            
        except Exception as e:
            logger.error(f"❌ 인증 상태 확인 실패: {e}")
            return {
                "provider": provider,
                "authenticated": False,
                "error": f"Status check failed: {e}"
            }

# 전역 인스턴스
oauth_agent = OAuthAuthAgent()

def get_oauth_agent() -> OAuthAuthAgent:
    """OAuth 인증 에이전트 인스턴스 반환"""
    return oauth_agent
