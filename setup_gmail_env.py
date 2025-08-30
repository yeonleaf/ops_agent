#!/usr/bin/env python3
"""
Gmail API 환경 변수 설정 도우미 스크립트
"""

import os
from pathlib import Path

def create_gmail_env_file():
    """Gmail API 환경 변수를 포함한 .env 파일 생성"""
    
    env_content = """# Gmail API 설정
GMAIL_CLIENT_ID=your_gmail_client_id_here
GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token_here

# Azure OpenAI 설정 (기존 설정 유지)
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision

# Microsoft Graph API 설정 (선택사항)
GRAPH_CLIENT_ID=your_graph_client_id
GRAPH_CLIENT_SECRET=your_graph_client_secret
GRAPH_REFRESH_TOKEN=your_graph_refresh_token
GRAPH_TENANT_ID=your_tenant_id

# 기본 이메일 제공자 설정
EMAIL_PROVIDER=gmail
"""
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("⚠️ .env 파일이 이미 존재합니다.")
        response = input("덮어쓰시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("취소되었습니다.")
            return
    
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print("✅ .env 파일이 성공적으로 생성되었습니다!")
        print(f"   파일 위치: {env_file.absolute()}")
        print("\n📝 Gmail API 설정 방법:")
        print("   1. Google Cloud Console에서 프로젝트 생성")
        print("   2. Gmail API 활성화")
        print("   3. OAuth 2.0 클라이언트 ID 생성")
        print("   4. .env 파일에 다음 정보 입력:")
        print("      - GMAIL_CLIENT_ID: OAuth 2.0 클라이언트 ID")
        print("      - GMAIL_CLIENT_SECRET: OAuth 2.0 클라이언트 시크릿")
        print("      - GMAIL_REFRESH_TOKEN: Gmail 계정 인증 후 받은 리프레시 토큰")
        print("\n   5. 설정 완료 후 다음 명령어로 테스트하세요:")
        print("      python test_token_refresh.py")
        
    except Exception as e:
        print(f"❌ .env 파일 생성 실패: {e}")

def check_gmail_env_variables():
    """현재 Gmail 환경 변수 상태 확인"""
    print("🔍 현재 Gmail API 환경 변수 상태:")
    print("=" * 50)
    
    variables = [
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET", 
        "GMAIL_REFRESH_TOKEN"
    ]
    
    all_set = True
    for var in variables:
        value = os.getenv(var)
        status = "✅ 설정됨" if value and value != "your_gmail_client_id_here" else "❌ 설정되지 않음"
        print(f"   {var}: {status}")
        if not value or value == "your_gmail_client_id_here":
            all_set = False
    
    print()
    if all_set:
        print("🎉 모든 Gmail API 환경 변수가 설정되었습니다!")
        print("   이제 자동 토큰 갱신 기능을 테스트할 수 있습니다.")
    else:
        print("⚠️ 일부 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일을 생성하고 Gmail API 정보를 입력해주세요.")
    
    return all_set

def load_env_file():
    """환경 변수 파일 로드"""
    env_file = Path(".env")
    if env_file.exists():
        print("📁 .env 파일을 찾았습니다. 환경 변수를 로드합니다...")
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
            print("✅ 환경 변수 로드 완료")
            return True
        except Exception as e:
            print(f"❌ 환경 변수 로드 실패: {e}")
            return False
    else:
        print("❌ .env 파일을 찾을 수 없습니다.")
        return False

def main():
    """메인 함수"""
    print("🚀 Gmail API 환경 변수 설정 도우미")
    print("=" * 50)
    
    # .env 파일 로드 시도
    env_loaded = load_env_file()
    
    # 현재 환경 변수 상태 확인
    env_ready = check_gmail_env_variables()
    
    if not env_ready:
        print("\n📝 .env 파일 생성을 원하시나요?")
        response = input("Gmail API 환경 변수를 포함한 .env 파일을 생성하시겠습니까? (y/N): ")
        
        if response.lower() == 'y':
            create_gmail_env_file()
        else:
            print("취소되었습니다.")
    
    print("\n💡 Gmail API 설정 방법:")
    print("   1. Google Cloud Console (https://console.cloud.google.com/) 접속")
    print("   2. 새 프로젝트 생성 또는 기존 프로젝트 선택")
    print("   3. Gmail API 활성화")
    print("   4. OAuth 2.0 클라이언트 ID 생성")
    print("   5. .env 파일에 클라이언트 정보 입력")
    print("   6. Gmail 계정 인증 및 리프레시 토큰 획득")
    print("   7. test_token_refresh.py 실행")

if __name__ == "__main__":
    main()
