#!/usr/bin/env python3
"""
라우터 에이전트 OAuth 통합 테스트
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from router_agent import create_router_agent

# 환경 변수 로드
load_dotenv()

def test_router_oauth():
    """라우터 에이전트 OAuth 통합 테스트"""
    print("🚀 라우터 에이전트 OAuth 통합 테스트 시작")
    print("=" * 60)
    
    # LLM 클라이언트 생성
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0.1
    )
    
    # 라우터 에이전트 생성
    router = create_router_agent(llm)
    
    # 테스트 쿼리들
    test_queries = [
        "안 읽은 메일 3개 보여줘",
        "이메일 조회해줘",
        "받은편지함 메일 보여줘",
        "메일 분석해줘"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}️⃣ 테스트 쿼리: {query}")
        print("-" * 40)
        
        try:
            result = router.execute(query)
            print(f"🤖 응답: {result}")
        except Exception as e:
            print(f"❌ 오류: {e}")
        
        print("-" * 40)
    
    print("\n" + "=" * 60)
    print("🎉 라우터 에이전트 OAuth 통합 테스트 완료!")

if __name__ == "__main__":
    test_router_oauth()
