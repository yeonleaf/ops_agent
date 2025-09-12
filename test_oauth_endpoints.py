#!/usr/bin/env python3
"""
OAuth 엔드포인트 테스트 스크립트
"""

import requests
import json
import time
from typing import Dict, Any

# 서버 설정
OAUTH_SERVER_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8505"

def test_oauth_endpoints():
    """OAuth 엔드포인트 테스트"""
    print("🧪 OAuth 엔드포인트 테스트 시작")
    print("=" * 50)
    
    # 1. 루트 엔드포인트 테스트
    print("1️⃣ 루트 엔드포인트 테스트")
    try:
        response = requests.get(f"{OAUTH_SERVER_URL}/")
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 응답: {response.json()}")
    except Exception as e:
        print(f"❌ 실패: {e}")
    
    print()
    
    # 2. 인증 상태 확인 (인증 전)
    print("2️⃣ 인증 상태 확인 (인증 전)")
    try:
        response = requests.get(f"{OAUTH_SERVER_URL}/auth/status")
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 응답: {response.json()}")
    except Exception as e:
        print(f"❌ 실패: {e}")
    
    print()
    
    # 3. Gmail 로그인 URL 생성
    print("3️⃣ Gmail 로그인 URL 생성")
    try:
        response = requests.get(f"{OAUTH_SERVER_URL}/auth/login/gmail", allow_redirects=False)
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 리디렉션 URL: {response.headers.get('Location', 'N/A')}")
    except Exception as e:
        print(f"❌ 실패: {e}")
    
    print()
    
    # 4. Outlook 로그인 URL 생성
    print("4️⃣ Outlook 로그인 URL 생성")
    try:
        response = requests.get(f"{OAUTH_SERVER_URL}/auth/login/outlook", allow_redirects=False)
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 리디렉션 URL: {response.headers.get('Location', 'N/A')}")
    except Exception as e:
        print(f"❌ 실패: {e}")
    
    print()
    
    # 5. MCP 서버 상태 확인
    print("5️⃣ MCP 서버 상태 확인")
    try:
        response = requests.get(f"{MCP_SERVER_URL}/health")
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 응답: {response.json()}")
    except Exception as e:
        print(f"❌ 실패: {e}")
    
    print()
    
    # 6. MCP 서버 루트 엔드포인트
    print("6️⃣ MCP 서버 루트 엔드포인트")
    try:
        response = requests.get(f"{MCP_SERVER_URL}/")
        print(f"✅ 상태 코드: {response.status_code}")
        print(f"✅ 응답: {response.json()}")
    except Exception as e:
        print(f"❌ 실패: {e}")

def test_oauth_flow():
    """OAuth 플로우 테스트 (수동)"""
    print("\n🔄 OAuth 플로우 테스트 (수동)")
    print("=" * 50)
    
    print("1. 브라우저에서 다음 URL을 열어 Gmail 로그인을 테스트하세요:")
    print(f"   {OAUTH_SERVER_URL}/auth/login/gmail")
    print()
    
    print("2. Gmail 로그인 후 콜백 URL을 확인하세요:")
    print(f"   {OAUTH_SERVER_URL}/auth/callback?code=...&state=...")
    print()
    
    print("3. 브라우저 개발자 도구에서 쿠키를 확인하세요:")
    print("   - session_id (HttpOnly)")
    print("   - refresh_token (HttpOnly)")
    print()
    
    print("4. Streamlit 앱에서 이메일 서비스를 테스트하세요:")
    print("   http://localhost:8501")

def test_token_refresh():
    """토큰 재발급 테스트 (수동)"""
    print("\n🔄 토큰 재발급 테스트 (수동)")
    print("=" * 50)
    
    print("1. 먼저 OAuth 로그인을 완료하세요")
    print("2. 브라우저 개발자 도구에서 쿠키를 복사하세요")
    print("3. 다음 명령어로 토큰 재발급을 테스트하세요:")
    print()
    print("curl -X POST http://localhost:8000/auth/refresh \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"provider\": \"gmail\"}' \\")
    print("  -H 'Cookie: session_id=YOUR_SESSION_ID; refresh_token=YOUR_REFRESH_TOKEN'")

def main():
    """메인 함수"""
    print("🚀 OAuth 서비스 테스트 도구")
    print("=" * 50)
    
    # 서버가 실행 중인지 확인
    try:
        response = requests.get(f"{OAUTH_SERVER_URL}/", timeout=5)
        print("✅ OAuth 서버가 실행 중입니다")
    except:
        print("❌ OAuth 서버가 실행되지 않았습니다")
        print("먼저 다음 명령어로 서버를 시작하세요:")
        print("python oauth_auth_server.py")
        return
    
    try:
        response = requests.get(f"{MCP_SERVER_URL}/health", timeout=5)
        print("✅ MCP 서버가 실행 중입니다")
    except:
        print("❌ MCP 서버가 실행되지 않았습니다")
        print("먼저 다음 명령어로 서버를 시작하세요:")
        print("python secure_mcp_server.py")
        return
    
    print()
    
    # 엔드포인트 테스트 실행
    test_oauth_endpoints()
    
    # 수동 테스트 안내
    test_oauth_flow()
    test_token_refresh()
    
    print("\n✅ 테스트 완료!")

if __name__ == "__main__":
    main()
