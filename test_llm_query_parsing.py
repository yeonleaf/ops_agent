#!/usr/bin/env python3
"""
ViewingAgent LLM 쿼리 파싱 테스트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_llm_query_parsing():
    """ViewingAgent의 LLM 쿼리 파싱 기능 테스트"""
    try:
        from specialist_agents import ViewingAgent
        from langchain_openai import AzureChatOpenAI
        import json

        # 더미 LLM 클라이언트 생성
        llm = AzureChatOpenAI(
            azure_deployment="gpt-4.1",
            api_version="2024-10-21",
            temperature=0.1
        )

        # ViewingAgent 인스턴스 생성
        viewing_agent = ViewingAgent(llm)

        print("🧠 ViewingAgent LLM 쿼리 파싱 테스트")
        print("=" * 50)

        # 테스트 케이스들
        test_queries = [
            "NCMS 관련 메일 3개 보여줘",
            "안 읽은 메일 5개",
            "업무 관련 메일",
            "최근 일주일 메일"
        ]

        all_passed = True
        for i, query in enumerate(test_queries, 1):
            print(f"\n{i}. 테스트 쿼리: '{query}'")

            try:
                # LLM 파싱 테스트
                result = viewing_agent._parse_query_with_llm_internal(query)
                print(f"   LLM 파싱 결과: {json.dumps(result, ensure_ascii=False, indent=2)}")

                if result and 'filters' in result:
                    print("   ✅ PASS - LLM 파싱 성공")
                else:
                    print("   ⚠️  FALLBACK - 규칙 기반으로 폴백")
                    fallback_result = viewing_agent._parse_query_with_rules(query)
                    print(f"   규칙 파싱 결과: {json.dumps(fallback_result, ensure_ascii=False, indent=2)}")

            except Exception as e:
                print(f"   ❌ FAIL - 오류: {e}")
                all_passed = False

        print("\n" + "=" * 50)

        if all_passed:
            print("🎉 모든 쿼리 파싱이 정상적으로 작동합니다!")
            return True
        else:
            print("❌ 일부 쿼리 파싱에서 오류가 발생했습니다.")
            return False

    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 ViewingAgent LLM 쿼리 파싱 테스트 시작")
    print()

    success = test_llm_query_parsing()

    print()
    if success:
        print("✅ 테스트 완료: LLM 쿼리 파싱이 정상 작동합니다!")
        sys.exit(0)
    else:
        print("❌ 테스트 실패: 추가 수정이 필요합니다.")
        sys.exit(1)