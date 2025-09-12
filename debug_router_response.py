#!/usr/bin/env python3
"""
라우터 에이전트 응답 디버깅 스크립트
"""

import os
import logging
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from router_agent import create_router_agent

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def debug_router_response():
    """라우터 에이전트 응답 디버깅"""
    print("🔍 라우터 에이전트 응답 디버깅 시작")
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
    
    # 테스트 쿼리
    query = "안 읽은 메일 3개를 보여주세요"
    print(f"🔍 테스트 쿼리: {query}")
    print("-" * 40)
    
    try:
        # 라우터 에이전트 실행
        result = router.execute(query)
        
        print(f"✅ 최종 응답: {result}")
        print(f"📊 응답 타입: {type(result)}")
        print(f"📏 응답 길이: {len(str(result))}")
        
        # 응답 내용 분석
        if "OAuth" in result or "인증" in result:
            print("✅ OAuth 인증 메시지가 포함되어 있습니다.")
        elif "티켓" in result:
            print("❌ 티켓 관련 메시지가 포함되어 있습니다.")
        else:
            print("⚠️ 예상치 못한 응답 내용입니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🎉 라우터 에이전트 응답 디버깅 완료!")

if __name__ == "__main__":
    debug_router_response()
