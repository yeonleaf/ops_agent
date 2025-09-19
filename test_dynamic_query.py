#!/usr/bin/env python3
"""
동적 쿼리 파싱 테스트 스크립트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_dynamic_query():
    """동적 쿼리 파싱 테스트"""
    try:
        from specialist_agents import ViewingAgent
        from langchain_openai import AzureChatOpenAI

        # LLM 클라이언트 생성
        llm = AzureChatOpenAI(
            azure_deployment="gpt-4.1",
            api_version="2024-10-21",
            temperature=0.1
        )

        # ViewingAgent 인스턴스 생성
        viewing_agent = ViewingAgent(llm)

        # ViewingAgent의 view_emails_tool 호출해서 로그 확인
        view_emails_tool = None
        for tool in viewing_agent.tools:
            if tool.name == "view_emails_tool":
                view_emails_tool = tool.func
                break

        if view_emails_tool:
            print("🧪 ViewingAgent의 view_emails_tool 직접 호출 테스트")
            print("=" * 60)

            test_queries = [
                "NCMS 관련 메일 3개",
                "안 읽은 메일 5개",
                "최근 메일 조회"
            ]

            for query in test_queries:
                print(f"\n🔍 테스트 쿼리: '{query}'")
                try:
                    # OAuth 없이 파싱 부분만 테스트하기 위해 오류 무시
                    result = view_emails_tool(query, "")
                    print(f"결과: {result[:200]}...")
                except Exception as e:
                    print(f"예상된 OAuth 오류: {str(e)[:100]}...")

        else:
            print("❌ view_emails_tool을 찾을 수 없습니다")

    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")

if __name__ == "__main__":
    print("🚀 동적 쿼리 파싱 테스트 시작")
    test_dynamic_query()
    print("✅ 테스트 완료")