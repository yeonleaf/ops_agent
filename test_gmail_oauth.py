#!/usr/bin/env python3
"""
Gmail API 클라이언트의 OAuth 토큰 갱신 기능 테스트
"""

import os
import sys
from dotenv import load_dotenv

def test_gmail_oauth():
    """Gmail OAuth 토큰 갱신 테스트"""
    try:
        print("🚀 Gmail OAuth 토큰 갱신 테스트 시작")
        print("=" * 50)
        
        # 1. 환경 변수 로드
        print("📁 환경 변수 로드 중...")
        load_dotenv()
        
        # 2. Gmail 설정 확인
        client_id = os.getenv('GMAIL_CLIENT_ID')
        client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
        
        print(f"🔑 GMAIL_CLIENT_ID: {'✅ 설정됨' if client_id else '❌ 설정되지 않음'}")
        print(f"🔑 GMAIL_CLIENT_SECRET: {'✅ 설정됨' if client_secret else '❌ 설정되지 않음'}")
        print(f"🔄 GMAIL_REFRESH_TOKEN: {'✅ 설정됨' if refresh_token else '❌ 설정되지 않음'}")
        
        if not all([client_id, client_secret]):
            print("❌ Gmail 클라이언트 정보가 설정되지 않았습니다.")
            return False
        
        # 3. Gmail API 클라이언트 테스트
        print("\n🔐 Gmail API 클라이언트 테스트 중...")
        from gmail_api_client import GmailAPIClient
        
        client = GmailAPIClient()
        
        # 4. 강제 토큰 갱신 테스트
        print("\n🔄 강제 토큰 갱신 테스트 시작...")
        print("💡 이 과정에서 OAuth 인증이 시작됩니다.")
        print("💡 시크릿 모드 브라우저가 열리고 Gmail 인증을 진행해주세요.")
        
        if client.authenticate(force_refresh=True):
            print("\n🎉 Gmail OAuth 토큰 갱신 성공!")
            print("✅ 새로운 토큰으로 Gmail API를 사용할 수 있습니다.")
            
            # 5. .env 파일 상태 확인
            print("\n📋 .env 파일 상태 확인...")
            if os.path.exists('.env'):
                with open('.env', 'r', encoding='utf-8') as f:
                    env_content = f.read()
                
                if 'GMAIL_REFRESH_TOKEN=' in env_content:
                    print("✅ .env 파일에 GMAIL_REFRESH_TOKEN이 저장되어 있습니다.")
                    # 새로운 토큰 값 확인
                    lines = env_content.split('\n')
                    for line in lines:
                        if line.startswith('GMAIL_REFRESH_TOKEN='):
                            token_value = line.split('=')[1]
                            print(f"🔄 현재 리프레시 토큰: {token_value[:20]}...")
                            break
                else:
                    print("❌ .env 파일에 GMAIL_REFRESH_TOKEN이 없습니다.")
            else:
                print("❌ .env 파일이 존재하지 않습니다.")
            
            return True
        else:
            print("\n❌ Gmail OAuth 토큰 갱신 실패")
            return False
            
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print("🔐 Gmail OAuth 토큰 갱신 시스템 테스트")
    print("=" * 60)
    
    success = test_gmail_oauth()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 테스트 성공! OAuth 토큰 갱신이 정상적으로 작동합니다.")
        print("💡 이제 메인 앱에서 새로운 토큰을 사용할 수 있습니다.")
    else:
        print("❌ 테스트 실패! 문제를 확인하고 다시 시도해주세요.")
    
    print("\n💡 다음 단계:")
    print("   1. 메인 앱 종료")
    print("   2. 'python [메인앱파일명].py' 실행")
    print("   3. 새로운 토큰으로 Gmail API 사용")

if __name__ == "__main__":
    main()
