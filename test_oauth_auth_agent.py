#!/usr/bin/env python3
"""
OAuth 인증 에이전트 테스트 스크립트
"""

import os
from dotenv import load_dotenv
from oauth_auth_agent import get_oauth_agent

# 환경 변수 로드
load_dotenv()

def test_oauth_auth_agent():
    """OAuth 인증 에이전트 테스트"""
    print("🚀 OAuth 인증 에이전트 테스트 시작")
    print("=" * 50)
    
    # OAuth 에이전트 가져오기
    oauth_agent = get_oauth_agent()
    
    # 1. 인증 상태 확인 테스트
    print("\n1️⃣ 인증 상태 확인 테스트")
    result = oauth_agent.check_auth_required("gmail")
    print(f"Gmail 인증 필요: {result['auth_required']}")
    print(f"메시지: {result['message']}")
    
    # 2. OAuth 로그인 URL 생성 테스트
    print("\n2️⃣ OAuth 로그인 URL 생성 테스트")
    result = oauth_agent.generate_auth_url("gmail")
    if result["success"]:
        print(f"✅ Gmail OAuth URL 생성 성공!")
        print(f"🔗 인증 URL: {result['auth_url']}")
        print(f"🔑 상태 토큰: {result['state']}")
        print(f"💬 메시지: {result['message']}")
    else:
        print(f"❌ Gmail OAuth URL 생성 실패: {result['error']}")
    
    # 3. Microsoft OAuth URL 생성 테스트
    print("\n3️⃣ Microsoft OAuth URL 생성 테스트")
    result = oauth_agent.generate_auth_url("microsoft")
    if result["success"]:
        print(f"✅ Microsoft OAuth URL 생성 성공!")
        print(f"🔗 인증 URL: {result['auth_url']}")
        print(f"🔑 상태 토큰: {result['state']}")
        print(f"💬 메시지: {result['message']}")
    else:
        print(f"❌ Microsoft OAuth URL 생성 실패: {result['error']}")
    
    # 4. 인증 상태 확인 테스트
    print("\n4️⃣ 인증 상태 확인 테스트")
    result = oauth_agent.get_auth_status("gmail")
    print(f"Gmail 인증 상태: {result['message']}")
    print(f"인증됨: {result['authenticated']}")
    print(f"토큰 있음: {result['has_token']}")
    print(f"유효함: {result['is_valid']}")
    
    print("\n" + "=" * 50)
    print("🎉 OAuth 인증 에이전트 테스트 완료!")
    print("\n💡 사용 방법:")
    print("1. oauth_agent.check_auth_required(provider) - 인증 필요 여부 확인")
    print("2. oauth_agent.generate_auth_url(provider) - OAuth 로그인 URL 생성")
    print("3. oauth_agent.process_callback(provider, code, state) - OAuth 콜백 처리")
    print("4. oauth_agent.refresh_token(provider) - 토큰 재발급")
    print("5. oauth_agent.get_auth_status(provider) - 인증 상태 확인")

if __name__ == "__main__":
    test_oauth_auth_agent()
