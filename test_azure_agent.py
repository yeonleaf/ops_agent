#!/usr/bin/env python3
"""
Azure OpenAI 에이전트 테스트 스크립트
"""

import os
from dotenv import load_dotenv
from langchain_mail_agent import MailAgent, SimpleMailAgent

# 환경변수 로드
load_dotenv()

def test_azure_setup():
    """Azure 설정 확인"""
    print("=== Azure OpenAI 설정 확인 ===")
    
    azure_settings = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        "AZURE_OPENAI_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    }
    
    for key, value in azure_settings.items():
        status = "✅" if value else "❌"
        masked_value = value[:10] + "..." if value and len(value) > 10 else value
        print(f"{status} {key}: {masked_value}")
    
    all_set = all(azure_settings.values())
    print(f"\n{'✅' if all_set else '❌'} Azure 설정 완료 여부: {all_set}")
    return all_set

def test_simple_agent():
    """간단한 에이전트 테스트"""
    print("\n=== 간단한 에이전트 테스트 ===")
    
    try:
        agent = SimpleMailAgent()
        result = agent.query("안읽은 메일 보여줘")
        print("✅ 간단한 에이전트 작동 성공")
        print(f"응답 미리보기: {result[:100]}...")
        return True
    except Exception as e:
        print(f"❌ 간단한 에이전트 오류: {e}")
        return False

def test_azure_agent():
    """Azure 에이전트 테스트"""
    print("\n=== Azure 에이전트 테스트 ===")
    
    if not test_azure_setup():
        print("❌ Azure 설정이 완료되지 않아 테스트를 건너뜁니다.")
        return False
    
    try:
        print("Azure 에이전트 생성 중...")
        agent = MailAgent(llm_provider="azure", model_name="gpt-4")
        print("✅ Azure 에이전트 생성 성공")
        
        print("테스트 질문 실행 중...")
        result = agent.query("안읽은 메일 3개만 간단히 보여줘")
        print("✅ Azure 에이전트 작동 성공")
        print(f"\n응답 결과:\n{result}")
        return True
        
    except Exception as e:
        print(f"❌ Azure 에이전트 오류: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Azure OpenAI 에이전트 테스트를 시작합니다...\n")
    
    # 1. Azure 설정 확인
    azure_ok = test_azure_setup()
    
    # 2. 간단한 에이전트 테스트
    simple_ok = test_simple_agent()
    
    # 3. Azure 에이전트 테스트
    azure_agent_ok = test_azure_agent() if azure_ok else False
    
    # 결과 요약
    print("\n" + "="*50)
    print("📊 테스트 결과 요약")
    print("="*50)
    print(f"{'✅' if azure_ok else '❌'} Azure 설정")
    print(f"{'✅' if simple_ok else '❌'} 간단한 에이전트")
    print(f"{'✅' if azure_agent_ok else '❌'} Azure 에이전트")
    
    if azure_agent_ok:
        print("\n🎉 모든 테스트 통과! 챗봇 앱을 실행할 수 있습니다.")
        print("실행 명령어: streamlit run langchain_chatbot_app.py")
    elif simple_ok:
        print("\n⚠️ Azure 에이전트는 실패했지만 간단한 에이전트는 작동합니다.")
        print("챗봇 앱에서 '간단한 규칙 기반' 모드를 사용하세요.")
    else:
        print("\n❌ 에이전트 테스트 실패. 설정을 확인해주세요.")

if __name__ == "__main__":
    main()