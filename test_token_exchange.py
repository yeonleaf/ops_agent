#!/usr/bin/env python3
"""
토큰 교환 직접 테스트 스크립트
"""

import os
import requests
from dotenv import load_dotenv

def test_token_exchange():
    """토큰 교환을 직접 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ 환경 변수가 설정되지 않았습니다.")
        print("   GMAIL_CLIENT_ID와 GMAIL_CLIENT_SECRET을 확인해주세요.")
        return
    
    print("🔍 토큰 교환 테스트 시작")
    print(f"   클라이언트 ID: {client_id[:20]}...")
    print(f"   클라이언트 시크릿: {client_secret[:10]}...")
    print()
    
    # 사용자로부터 인증 코드 입력 받기
    auth_code = input("📝 인증 코드를 입력해주세요: ").strip()
    
    if not auth_code:
        print("❌ 인증 코드가 입력되지 않았습니다.")
        return
    
    print(f"🔑 입력된 인증 코드: {auth_code[:20]}...")
    print()
    
    # 토큰 교환 시도
    redirect_uri = "http://localhost:8081"
    
    print("🔄 토큰 교환 시도 중...")
    print(f"   리디렉션 URI: {redirect_uri}")
    print()
    
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': auth_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    try:
        print("📤 POST 요청 전송...")
        print(f"   URL: {token_url}")
        print(f"   데이터: {token_data}")
        print()
        
        response = requests.post(token_url, data=token_data)
        
        print(f"📥 응답 수신: {response.status_code}")
        print(f"   응답 헤더: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            token_info = response.json()
            print("✅ 토큰 교환 성공!")
            print("📋 토큰 정보:")
            print(f"   액세스 토큰: {token_info.get('access_token', 'N/A')[:30]}...")
            print(f"   리프레시 토큰: {token_info.get('refresh_token', 'N/A')[:30]}...")
            print(f"   만료 시간: {token_info.get('expires_in', 'N/A')}초")
            print(f"   토큰 타입: {token_info.get('token_type', 'N/A')}")
            print(f"   스코프: {token_info.get('scope', 'N/A')}")
            
            # .env 파일에 리프레시 토큰 저장
            refresh_token = token_info.get('refresh_token')
            if refresh_token:
                print()
                print("💾 .env 파일에 리프레시 토큰 저장 중...")
                
                # 기존 .env 파일 읽기
                env_content = ""
                if os.path.exists('.env'):
                    with open('.env', 'r', encoding='utf-8') as f:
                        env_content = f.read()
                
                # GMAIL_REFRESH_TOKEN 업데이트 또는 추가
                if 'GMAIL_REFRESH_TOKEN=' in env_content:
                    # 기존 토큰 교체
                    lines = env_content.split('\n')
                    updated_lines = []
                    for line in lines:
                        if line.startswith('GMAIL_REFRESH_TOKEN='):
                            updated_lines.append(f'GMAIL_REFRESH_TOKEN={refresh_token}')
                        else:
                            updated_lines.append(line)
                    env_content = '\n'.join(updated_lines)
                else:
                    # 새로 추가
                    env_content += f'\nGMAIL_REFRESH_TOKEN={refresh_token}'
                
                # .env 파일 저장
                with open('.env', 'w', encoding='utf-8') as f:
                    f.write(env_content)
                
                print("✅ .env 파일 업데이트 완료!")
                print("🔄 이제 Gmail API 클라이언트를 다시 실행하면 새로운 토큰을 사용할 수 있습니다.")
            
        else:
            print("❌ 토큰 교환 실패")
            print(f"   오류 코드: {response.status_code}")
            print(f"   오류 응답: {response.text}")
            print()
            print("🔍 문제 해결 방법:")
            print("   1. 인증 코드가 올바른지 확인")
            print("   2. 클라이언트 ID와 시크릿이 정확한지 확인")
            print("   3. 리디렉션 URI가 Google Cloud Console에 등록되어 있는지 확인")
            print("   4. 인증 코드가 이미 사용되었는지 확인 (한 번만 사용 가능)")
            
    except Exception as e:
        print(f"❌ 토큰 교환 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_token_exchange()
