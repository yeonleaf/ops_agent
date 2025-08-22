#!/usr/bin/env python3
"""
완전한 티켓 워크플로우 테스트
메일 → 티켓 생성 → 임베딩 → LLM 에이전트 테스트
"""

import os
from dotenv import load_dotenv
from langchain_mail_agent import MailAgent, SimpleMailAgent

# 환경변수 로드
load_dotenv()

def test_basic_workflow():
    """기본 워크플로우 테스트 (규칙 기반)"""
    print("=== 기본 워크플로우 테스트 (규칙 기반) ===")
    
    try:
        agent = SimpleMailAgent()
        
        # 오늘 처리할 작업 요청
        result = agent.query("오늘 처리해야 할 티켓 리스트를 보여줘")
        print("✅ 기본 에이전트 작동 성공")
        print(f"응답 미리보기: {result[:200]}...")
        return True
    except Exception as e:
        print(f"❌ 기본 에이전트 오류: {e}")
        return False

def test_llm_workflow():
    """LLM 기반 워크플로우 테스트"""
    print("\n=== LLM 기반 워크플로우 테스트 ===")
    
    # Azure 설정 확인
    azure_settings = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        "AZURE_OPENAI_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    }
    
    if not all(azure_settings.values()):
        print("❌ Azure 설정이 불완전하여 LLM 테스트를 건너뜁니다.")
        return False
    
    try:
        print("LLM 에이전트 생성 중...")
        agent = MailAgent(llm_provider="azure", model_name="gpt-4")
        print("✅ LLM 에이전트 생성 성공")
        
        # 테스트 질문들
        test_queries = [
            "오늘 내가 처리해야 할 티켓 리스트를 보여줘",
            "처리해야 할 작업이 뭐가 있어?",
            "새로운 메일에서 티켓을 만들어야 할 게 있나?"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- 테스트 {i}: {query} ---")
            try:
                result = agent.query(query)
                print("✅ 성공")
                # 결과가 너무 길면 요약해서 표시
                if len(result) > 300:
                    print(f"응답 요약: {result[:300]}...")
                else:
                    print(f"응답: {result}")
            except Exception as e:
                print(f"❌ 질문 {i} 실패: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM 에이전트 오류: {e}")
        return False

def test_individual_tools():
    """개별 툴 테스트"""
    print("\n=== 개별 툴 테스트 ===")
    
    try:
        from ticket_workflow_tools import (
            get_todays_unread_emails, 
            process_todays_tasks,
            get_existing_tickets_by_status
        )
        
        # 1. 안읽은 메일 조회
        print("\n1. 안읽은 메일 조회:")
        result = get_todays_unread_emails.invoke({})
        data = json.loads(result)
        print(f"   발견된 메일: {data.get('count', 0)}개")
        
        # 2. 기존 티켓 조회
        print("\n2. 기존 티켓 조회:")
        result = get_existing_tickets_by_status.invoke({"status": "new"})
        data = json.loads(result)
        print(f"   새 티켓: {data.get('count', 0)}개")
        
        # 3. 전체 워크플로우
        print("\n3. 전체 워크플로우 실행:")
        result = process_todays_tasks.invoke({})
        data = json.loads(result)
        summary = data.get('summary', {})
        print(f"   안읽은 메일: {summary.get('total_unread_emails', 0)}개")
        print(f"   새 티켓 생성: {summary.get('new_tickets_created', 0)}개")
        print(f"   기존 티켓: {summary.get('existing_tickets_found', 0)}개")
        print(f"   총 작업: {summary.get('total_tasks', 0)}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 개별 툴 테스트 오류: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 완전한 티켓 워크플로우 테스트를 시작합니다...\n")
    
    # 필요한 모듈 import
    import json
    
    # 1. 개별 툴 테스트
    tools_ok = test_individual_tools()
    
    # 2. 기본 에이전트 테스트
    basic_ok = test_basic_workflow()
    
    # 3. LLM 에이전트 테스트
    llm_ok = test_llm_workflow()
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    print(f"{'✅' if tools_ok else '❌'} 개별 툴 테스트")
    print(f"{'✅' if basic_ok else '❌'} 기본 에이전트 테스트")
    print(f"{'✅' if llm_ok else '❌'} LLM 에이전트 테스트")
    
    if llm_ok:
        print("\n🎉 모든 테스트 통과! 완전한 워크플로우가 준비되었습니다.")
        print("이제 다음과 같은 질문을 할 수 있습니다:")
        print("- '오늘 처리해야 할 티켓 리스트를 보여줘'")
        print("- '새로운 메일에서 티켓을 만들어야 할 게 있나?'")
        print("- '처리해야 할 작업이 뭐가 있어?'")
        print("\n실행 명령어: streamlit run langchain_chatbot_app.py")
    elif basic_ok:
        print("\n⚠️ LLM 에이전트는 실패했지만 기본 기능은 작동합니다.")
        print("챗봇 앱에서 '간단한 규칙 기반' 모드를 사용하세요.")
    else:
        print("\n❌ 워크플로우 테스트 실패. 설정을 확인해주세요.")

if __name__ == "__main__":
    main()