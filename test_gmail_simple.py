#!/usr/bin/env python3
"""
Gmail API 토큰 갱신 기능을 Streamlit 없이 테스트하는 스크립트
"""

import os
import sys
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gmail_without_streamlit():
    """Streamlit 없이 Gmail API 테스트"""
    try:
        # 환경변수 로드
        from setup_gmail_env import load_env_file
        load_env_file()
        
        print("🔄 Gmail API 테스트 (Streamlit 없이)")
        print("=" * 50)
        
        # Gmail 클라이언트 직접 테스트
        from gmail_api_client import GmailAPIClient
        
        client = GmailAPIClient()
        
        # 1. 토큰 상태 확인
        print("\n1️⃣ 현재 토큰 상태 확인")
        status = client.get_token_status()
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        # 2. 인증 시도 (Streamlit UI 없이)
        print("\n2️⃣ Gmail API 인증 시도")
        
        # 환경변수 확인
        client_id = os.getenv('GMAIL_CLIENT_ID')
        client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
        
        print(f"   Client ID: {'✅ 설정됨' if client_id else '❌ 설정되지 않음'}")
        print(f"   Client Secret: {'✅ 설정됨' if client_secret else '❌ 설정되지 않음'}")
        print(f"   Refresh Token: {'✅ 설정됨' if refresh_token else '❌ 설정되지 않음'}")
        
        if all([client_id, client_secret, refresh_token]):
            print("   모든 환경변수가 설정되어 있습니다.")
            
            # Credentials 객체 직접 생성
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            creds = Credentials(
                None,  # access_token은 자동 갱신됨
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=['https://www.googleapis.com/auth/gmail.readonly']
            )
            
            # 토큰 갱신 시도
            print("   🔄 토큰 갱신 시도...")
            try:
                creds.refresh(Request())
                print("   ✅ 토큰 갱신 성공!")
                
                # Gmail API 서비스 생성
                from googleapiclient.discovery import build
                service = build('gmail', 'v1', credentials=creds)
                
                # 프로필 정보 가져오기
                print("   📧 Gmail 프로필 확인...")
                profile = service.users().getProfile(userId='me').execute()
                email = profile.get('emailAddress', 'Unknown')
                print(f"   ✅ 연결된 Gmail: {email}")
                
                # 안읽은 메일 개수 확인
                print("   📬 안읽은 메일 개수 확인...")
                unread = service.users().messages().list(
                    userId='me', 
                    labelIds=['UNREAD'],
                    maxResults=1
                ).execute()
                
                total_unread = unread.get('resultSizeEstimate', 0)
                print(f"   ✅ 안읽은 메일: {total_unread}개")
                
                # 토큰 정보 저장
                print("   💾 토큰 정보 저장...")
                client.creds = creds
                client.service = service
                client._save_tokens()
                print("   ✅ 토큰 정보 저장 완료")
                
            except Exception as e:
                print(f"   ❌ 토큰 갱신 실패: {e}")
                
        else:
            print("   ❌ 필요한 환경변수가 설정되지 않았습니다.")
            
        # 3. 토큰 파일 상태 확인
        print("\n3️⃣ 토큰 파일 상태")
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

if __name__ == "__main__":
    print("🚀 Gmail API 간단 테스트 시작")
    test_gmail_without_streamlit()
    print("\n🎯 테스트 완료!")
