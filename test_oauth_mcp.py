#!/usr/bin/env python3
"""
OAuth MCP 툴 테스트 스크립트
"""

import os
import requests
import secrets
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# OAuth 설정
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback?provider=google")

def test_oauth_login_gmail():
    """Gmail OAuth 로그인 URL 생성 테스트"""
    try:
        # 상태 토큰 생성 (CSRF 보호)
        state = secrets.token_urlsafe(32)
        
        # Gmail OAuth URL 생성
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"scope=openid profile email https://www.googleapis.com/auth/gmail.readonly&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state={state}"
        )
        
        print("🔐 Gmail OAuth 로그인 URL 생성 테스트:")
        print(f"✅ 성공: True")
        print(f"🔗 인증 URL: {auth_url}")
        print(f"🔑 상태 토큰: {state}")
        print(f"📧 제공자: gmail")
        print(f"💬 메시지: Gmail OAuth 로그인 URL이 생성되었습니다. 브라우저에서 이 URL을 열어 인증을 완료하세요.")
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state,
            "provider": "gmail",
            "message": "Gmail OAuth 로그인 URL이 생성되었습니다. 브라우저에서 이 URL을 열어 인증을 완료하세요."
        }
        
    except Exception as e:
        print(f"❌ Gmail 로그인 URL 생성 실패: {e}")
        return {
            "success": False,
            "error": f"Gmail 로그인 URL 생성 실패: {e}"
        }

def test_oauth_callback(provider: str, code: str, state: str):
    """OAuth 콜백 처리 테스트"""
    try:
        if not code or not provider:
            return {
                "success": False,
                "error": "Missing code or provider"
            }
        
        access_token = None
        refresh_token = None
        
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        else:
            return {
                "success": False,
                "error": "Unsupported OAuth provider"
            }
        
        # 토큰 교환
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        
        if not access_token:
            return {
                "success": False,
                "error": "Failed to get access token"
            }
        
        print(f"✅ OAuth 콜백 성공: {provider}")
        print(f"🔑 Access Token: {access_token[:20]}...")
        print(f"🔄 Refresh Token: {refresh_token[:20] if refresh_token else 'None'}...")
        
        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "provider": provider,
            "message": f"{provider.upper()} OAuth 인증이 완료되었습니다. 이제 이메일 서비스를 사용할 수 있습니다."
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 토큰 교환 실패: {e}")
        return {
            "success": False,
            "error": f"Token exchange failed: {e}"
        }
    except Exception as e:
        print(f"❌ OAuth 콜백 실패: {e}")
        return {
            "success": False,
            "error": f"Callback failed: {e}"
        }

if __name__ == "__main__":
    print("🚀 OAuth MCP 툴 테스트 시작")
    print("=" * 50)
    
    # 1. Gmail 로그인 URL 생성 테스트
    print("\n1️⃣ Gmail OAuth 로그인 URL 생성 테스트")
    result = test_oauth_login_gmail()
    
    if result["success"]:
        print("\n✅ Gmail OAuth 로그인 URL 생성 성공!")
        print(f"🔗 브라우저에서 이 URL을 열어 인증을 완료하세요:")
        print(f"   {result['auth_url']}")
    else:
        print(f"\n❌ Gmail OAuth 로그인 URL 생성 실패: {result['error']}")
    
    print("\n" + "=" * 50)
    print("🎉 OAuth MCP 툴 테스트 완료!")
    print("\n💡 사용 방법:")
    print("1. 위의 Gmail OAuth URL을 브라우저에서 열기")
    print("2. Google 계정으로 로그인 및 권한 승인")
    print("3. authorization_code를 받아서 oauth_callback 함수로 전달")
    print("4. access_token과 refresh_token을 받아서 이메일 서비스 사용")
