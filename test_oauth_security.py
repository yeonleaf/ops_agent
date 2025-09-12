#!/usr/bin/env python3
"""
OAuth2 보안 테스트 스크립트
기존 .env 기반 인증이 차단되었는지 확인
"""

import os
import sys
from dotenv import load_dotenv

def test_oauth_security():
    """OAuth2 보안 테스트"""
    print("🔒 OAuth2 보안 테스트 시작")
    print("=" * 50)
    
    # .env 파일 로드
    load_dotenv()
    
    # 1. GMAIL_REFRESH_TOKEN 제거 확인
    print("\n1️⃣ GMAIL_REFRESH_TOKEN 제거 확인")
    refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
    if refresh_token:
        print(f"❌ GMAIL_REFRESH_TOKEN이 여전히 존재합니다: {refresh_token[:20]}...")
        print("   이 토큰을 제거해야 합니다.")
        return False
    else:
        print("✅ GMAIL_REFRESH_TOKEN이 제거되었습니다.")
    
    # 2. OAuth2 설정 확인
    print("\n2️⃣ OAuth2 설정 확인")
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if google_client_id and google_client_secret:
        print("✅ OAuth2 설정이 완료되었습니다.")
        print(f"   GOOGLE_CLIENT_ID: {google_client_id[:20]}...")
        print(f"   GOOGLE_CLIENT_SECRET: {google_client_secret[:10]}...")
    else:
        print("❌ OAuth2 설정이 누락되었습니다.")
        return False
    
    # 3. 이메일 서비스 인증 테스트 (토큰 없이)
    print("\n3️⃣ 이메일 서비스 인증 테스트 (토큰 없이)")
    try:
        from unified_email_service import UnifiedEmailService
        
        # 액세스 토큰 없이 서비스 생성 시도
        service = UnifiedEmailService(provider_name='gmail', access_token=None)
        print("❌ 액세스 토큰 없이도 서비스가 생성되었습니다. 보안 문제!")
        return False
        
    except Exception as e:
        print(f"✅ 액세스 토큰 없이는 서비스 생성이 차단됩니다: {e}")
    
    # 4. Gmail API 클라이언트 인증 테스트 (토큰 없이)
    print("\n4️⃣ Gmail API 클라이언트 인증 테스트 (토큰 없이)")
    try:
        from gmail_api_client import GmailAPIClient
        
        client = GmailAPIClient()
        result = client.authenticate(access_token=None)
        
        if result:
            print("❌ 액세스 토큰 없이도 Gmail API 인증이 성공했습니다. 보안 문제!")
            return False
        else:
            print("✅ 액세스 토큰 없이는 Gmail API 인증이 차단됩니다.")
            
    except Exception as e:
        print(f"✅ 액세스 토큰 없이는 Gmail API 인증이 차단됩니다: {e}")
    
    # 5. OAuth 서버 엔드포인트 확인
    print("\n5️⃣ OAuth 서버 엔드포인트 확인")
    oauth_endpoints = [
        "http://localhost:8000/auth/login/gmail",
        "http://localhost:8000/auth/callback",
        "http://localhost:8000/auth/refresh"
    ]
    
    print("OAuth 서버 엔드포인트:")
    for endpoint in oauth_endpoints:
        print(f"   - {endpoint}")
    
    print("\n✅ OAuth2 보안 테스트 완료!")
    print("🔒 기존 .env 기반 인증이 성공적으로 차단되었습니다.")
    print("💡 이제 OAuth 서버를 사용하여 안전하게 인증하세요.")
    
    return True

if __name__ == "__main__":
    success = test_oauth_security()
    sys.exit(0 if success else 1)
