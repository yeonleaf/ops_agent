#!/usr/bin/env python3
"""
인증 시스템 테스트 스크립트
API 엔드포인트들을 테스트하고 통합 확인
"""

import requests
import json
import time
from datetime import datetime

# API 서버 URL
BASE_URL = "http://localhost:8001"

def test_health_check():
    """헬스 체크 테스트"""
    print("🔍 헬스 체크 테스트...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 헬스 체크 성공")
            return True
        else:
            print(f"❌ 헬스 체크 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 헬스 체크 오류: {e}")
        return False

def test_signup():
    """회원가입 테스트"""
    print("\n🔍 회원가입 테스트...")
    
    test_email = f"test_{int(time.time())}@example.com"
    test_password = "test_password_123"
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/signup",
            json={
                "email": test_email,
                "password": test_password
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✅ 회원가입 성공: {test_email}")
                return test_email, test_password
            else:
                print(f"❌ 회원가입 실패: {result.get('message')}")
                return None, None
        else:
            print(f"❌ 회원가입 HTTP 오류: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ 회원가입 오류: {e}")
        return None, None

def test_login(email, password):
    """로그인 테스트"""
    print(f"\n🔍 로그인 테스트: {email}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 로그인 성공")
                # 세션 ID 추출
                cookies = response.cookies
                session_id = cookies.get('session_id')
                return session_id
            else:
                print(f"❌ 로그인 실패: {result.get('message')}")
                return None
        else:
            print(f"❌ 로그인 HTTP 오류: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 로그인 오류: {e}")
        return None

def test_get_user_info(session_id):
    """사용자 정보 조회 테스트"""
    print("\n🔍 사용자 정보 조회 테스트...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 사용자 정보 조회 성공: {result.get('email')}")
            return result
        else:
            print(f"❌ 사용자 정보 조회 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 사용자 정보 조회 오류: {e}")
        return None

def test_jira_integration(session_id):
    """Jira 연동 테스트"""
    print("\n🔍 Jira 연동 테스트...")
    
    test_jira_endpoint = "https://test-domain.atlassian.net"
    test_jira_token = "test_jira_token_123"
    
    try:
        # Jira 연동 정보 저장
        response = requests.post(
            f"{BASE_URL}/user/integrations/jira",
            json={
                "jira_endpoint": test_jira_endpoint,
                "jira_api_token": test_jira_token
            },
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Jira 연동 정보 저장 성공")
            else:
                print(f"❌ Jira 연동 정보 저장 실패: {result.get('message')}")
                return False
        else:
            print(f"❌ Jira 연동 정보 저장 HTTP 오류: {response.status_code}")
            return False
        
        # Jira 연동 정보 조회
        response = requests.get(
            f"{BASE_URL}/user/integrations/jira",
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✅ Jira 연동 정보 조회 성공: {result.get('jira_endpoint')}")
                return True
            else:
                print(f"❌ Jira 연동 정보 조회 실패: {result.get('message')}")
                return False
        else:
            print(f"❌ Jira 연동 정보 조회 HTTP 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Jira 연동 테스트 오류: {e}")
        return False

def test_google_integration(session_id):
    """Google 연동 테스트"""
    print("\n🔍 Google 연동 테스트...")
    
    test_refresh_token = "test_google_refresh_token_123"
    
    try:
        # Google 토큰 저장
        response = requests.post(
            f"{BASE_URL}/user/integrations/google",
            data=f"refresh_token={test_refresh_token}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Google 토큰 저장 성공")
            else:
                print(f"❌ Google 토큰 저장 실패: {result.get('message')}")
                return False
        else:
            print(f"❌ Google 토큰 저장 HTTP 오류: {response.status_code}")
            return False
        
        # Google 연동 정보 조회
        response = requests.get(
            f"{BASE_URL}/user/integrations/google",
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✅ Google 연동 정보 조회 성공: {result.get('token_preview')}")
                return True
            else:
                print(f"❌ Google 연동 정보 조회 실패: {result.get('message')}")
                return False
        else:
            print(f"❌ Google 연동 정보 조회 HTTP 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Google 연동 테스트 오류: {e}")
        return False

def test_logout(session_id):
    """로그아웃 테스트"""
    print("\n🔍 로그아웃 테스트...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/logout",
            cookies={"session_id": session_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 로그아웃 성공")
                return True
            else:
                print(f"❌ 로그아웃 실패: {result.get('message')}")
                return False
        else:
            print(f"❌ 로그아웃 HTTP 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 로그아웃 오류: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 인증 시스템 테스트 시작")
    print("=" * 50)
    
    # 1. 헬스 체크
    if not test_health_check():
        print("❌ API 서버가 실행되지 않았습니다. 먼저 auth_server.py를 실행해주세요.")
        return
    
    # 2. 회원가입
    email, password = test_signup()
    if not email:
        print("❌ 회원가입 실패로 테스트를 중단합니다.")
        return
    
    # 3. 로그인
    session_id = test_login(email, password)
    if not session_id:
        print("❌ 로그인 실패로 테스트를 중단합니다.")
        return
    
    # 4. 사용자 정보 조회
    user_info = test_get_user_info(session_id)
    if not user_info:
        print("❌ 사용자 정보 조회 실패로 테스트를 중단합니다.")
        return
    
    # 5. Jira 연동 테스트
    jira_success = test_jira_integration(session_id)
    
    # 6. Google 연동 테스트
    google_success = test_google_integration(session_id)
    
    # 7. 로그아웃
    logout_success = test_logout(session_id)
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"✅ 헬스 체크: 성공")
    print(f"✅ 회원가입: 성공")
    print(f"✅ 로그인: 성공")
    print(f"✅ 사용자 정보 조회: 성공")
    print(f"{'✅' if jira_success else '❌'} Jira 연동: {'성공' if jira_success else '실패'}")
    print(f"{'✅' if google_success else '❌'} Google 연동: {'성공' if google_success else '실패'}")
    print(f"{'✅' if logout_success else '❌'} 로그아웃: {'성공' if logout_success else '실패'}")
    
    if all([jira_success, google_success, logout_success]):
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다. 로그를 확인해주세요.")

if __name__ == "__main__":
    main()
