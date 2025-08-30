#!/usr/bin/env python3
"""
Gmail API 토큰 갱신 기능 테스트 스크립트
"""

import os
import sys
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_token_refresh():
    """토큰 갱신 기능 테스트"""
    try:
        from gmail_api_client import GmailAPIClient
        
        print("🔄 Gmail API 토큰 갱신 테스트 시작")
        print("=" * 50)
        
        # Gmail 클라이언트 생성
        client = GmailAPIClient()
        
        # 1. 토큰 상태 확인
        print("\n1️⃣ 현재 토큰 상태 확인")
        status = client.get_token_status()
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        # 2. 인증 시도
        print("\n2️⃣ Gmail API 인증 시도")
        if client.authenticate():
            print("   ✅ 인증 성공")
            
            # 3. 인증 후 토큰 상태 재확인
            print("\n3️⃣ 인증 후 토큰 상태")
            status_after = client.get_token_status()
            for key, value in status_after.items():
                print(f"   {key}: {value}")
            
            # 4. 간단한 API 호출 테스트
            print("\n4️⃣ Gmail API 호출 테스트")
            try:
                # 프로필 정보 가져오기 (가장 간단한 API 호출)
                profile = client.service.users().getProfile(userId='me').execute()
                print(f"   ✅ API 호출 성공: {profile.get('emailAddress', 'Unknown')}")
                
                # 5. 안읽은 메일 개수 확인
                print("\n5️⃣ 안읽은 메일 개수 확인")
                unread = client.service.users().messages().list(
                    userId='me', 
                    labelIds=['UNREAD'],
                    maxResults=1
                ).execute()
                
                total_unread = unread.get('resultSizeEstimate', 0)
                print(f"   📧 안읽은 메일: {total_unread}개")
                
            except Exception as e:
                print(f"   ❌ API 호출 실패: {e}")
                
        else:
            print("   ❌ 인증 실패")
            
        # 6. 토큰 파일 확인
        print("\n6️⃣ 토큰 파일 상태")
        token_file = "gmail_tokens.json"
        if os.path.exists(token_file):
            file_size = os.path.getsize(token_file)
            file_time = datetime.fromtimestamp(os.path.getmtime(token_file))
            print(f"   📁 토큰 파일: {token_file}")
            print(f"   📏 파일 크기: {file_size} bytes")
            print(f"   🕒 수정 시간: {file_time}")
        else:
            print(f"   ❌ 토큰 파일 없음: {token_file}")
            
        print("\n" + "=" * 50)
        print("✅ 테스트 완료")
        
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("   필요한 패키지가 설치되어 있는지 확인하세요.")
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")

def test_force_refresh():
    """강제 토큰 갱신 테스트"""
    try:
        from gmail_api_client import GmailAPIClient
        
        print("\n🔄 강제 토큰 갱신 테스트")
        print("=" * 30)
        
        client = GmailAPIClient()
        
        # 강제 갱신 시도
        if client.force_token_refresh():
            print("   ✅ 강제 토큰 갱신 성공")
        else:
            print("   ❌ 강제 토큰 갱신 실패")
            
        # 갱신 후 상태 확인
        status = client.get_token_status()
        print(f"   🔄 갱신 시도 횟수: {status.get('refresh_attempts', 0)}")
        
    except Exception as e:
        print(f"❌ 강제 갱신 테스트 실패: {e}")

if __name__ == "__main__":
    print("🚀 Gmail API 토큰 갱신 테스트 시작")
    
    # 기본 테스트
    test_token_refresh()
    
    # 강제 갱신 테스트
    test_force_refresh()
    
    print("\n🎯 모든 테스트 완료!")
