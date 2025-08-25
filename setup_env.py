#!/usr/bin/env python3
"""
Azure OpenAI 환경 변수 설정 도우미 스크립트
"""

import os
from pathlib import Path

def create_env_file():
    """Azure OpenAI 환경 변수를 포함한 .env 파일 생성"""
    
    env_content = """# Azure OpenAI 설정
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision

# Gmail API 설정 (선택사항)
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token

# Microsoft Graph API 설정 (선택사항)
GRAPH_CLIENT_ID=your_graph_client_id
GRAPH_CLIENT_SECRET=your_graph_client_secret
GRAPH_REFRESH_TOKEN=your_graph_refresh_token
GRAPH_TENANT_ID=your_tenant_id

# 기본 이메일 제공자 설정 (선택사항)
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
        print("\n📝 다음 단계:")
        print("   1. .env 파일을 열어서 Azure OpenAI 정보를 입력하세요:")
        print("      - AZURE_OPENAI_ENDPOINT: Azure OpenAI 엔드포인트 URL")
        print("      - AZURE_OPENAI_API_KEY: Azure OpenAI API 키")
        print("      - AZURE_OPENAI_DEPLOYMENT_NAME: 배포 이름 (기본값: gpt-4-vision)")
        print("      - AZURE_OPENAI_API_VERSION: API 버전 (기본값: 2024-10-21)")
        print("\n   2. 설정 완료 후 다음 명령어로 테스트하세요:")
        print("      python test_azure_vision_first.py")
        
    except Exception as e:
        print(f"❌ .env 파일 생성 실패: {e}")

def check_env_variables():
    """현재 환경 변수 상태 확인"""
    print("🔍 현재 Azure OpenAI 환경 변수 상태:")
    print("=" * 50)
    
    variables = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", 
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION"
    ]
    
    all_set = True
    for var in variables:
        value = os.getenv(var)
        status = "✅ 설정됨" if value else "❌ 설정되지 않음"
        print(f"   {var}: {status}")
        if not value:
            all_set = False
    
    print()
    if all_set:
        print("🎉 모든 Azure OpenAI 환경 변수가 설정되었습니다!")
        print("   이제 Vision-First 분류 전략을 테스트할 수 있습니다.")
    else:
        print("⚠️ 일부 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일을 생성하고 설정을 완료해주세요.")
    
    return all_set

def main():
    """메인 함수"""
    print("🚀 Azure OpenAI 환경 변수 설정 도우미")
    print("=" * 50)
    
    # 현재 환경 변수 상태 확인
    env_ready = check_env_variables()
    
    if not env_ready:
        print("\n📝 .env 파일 생성을 원하시나요?")
        response = input("Azure OpenAI 환경 변수를 포함한 .env 파일을 생성하시겠습니까? (y/N): ")
        
        if response.lower() == 'y':
            create_env_file()
        else:
            print("취소되었습니다.")
    
    print("\n💡 Azure OpenAI 설정 방법:")
    print("   1. Azure Portal에서 OpenAI 서비스 생성")
    print("   2. API 키 및 엔드포인트 URL 확인")
    print("   3. GPT-4 Vision 모델 배포")
    print("   4. .env 파일에 정보 입력")
    print("   5. test_azure_vision_first.py 실행")

if __name__ == "__main__":
    main() 