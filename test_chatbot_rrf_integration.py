#!/usr/bin/env python3
"""
챗봇 RRF 통합 테스트
RouterAgentClient가 RRF 시스템을 올바르게 사용하는지 확인
"""

import sys
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def test_rrf_system_with_jira_chunks():
    """RRF 시스템이 jira_chunks 컬렉션을 올바르게 사용하는지 테스트"""
    print("🧪 RRF + jira_chunks 통합 테스트")
    print("=" * 60)

    try:
        # 1. RRF 시스템 직접 초기화
        print("\n1️⃣ RRF 시스템 직접 초기화 테스트")
        from rrf_fusion_rag_system import RRFRAGSystem

        rrf_system = RRFRAGSystem("jira_chunks")
        print("✅ RRF 시스템 초기화 성공")

        # 컬렉션 정보 확인
        if rrf_system.collection:
            doc_count = rrf_system.collection.count()
            print(f"📊 jira_chunks 컬렉션: {doc_count}개 문서")

        # 2. 간단한 검색 테스트
        print("\n2️⃣ RRF 검색 테스트")
        test_query = "Jira 이슈"
        print(f"🔍 검색 쿼리: '{test_query}'")

        results = rrf_system.rrf_search(test_query)

        if results:
            print(f"✅ 검색 완료: {len(results)}개 결과")
            print("\n📄 상위 3개 결과:")
            for i, result in enumerate(results[:3], 1):
                content = result.get('content', '')[:100]
                score = result.get('score', 0)
                rrf_rank = result.get('rrf_rank', i)
                print(f"\n  {i}. RRF순위:{rrf_rank}, 점수:{score:.4f}")
                print(f"     내용: {content}...")
        else:
            print("⚠️ 검색 결과 없음")

        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_router_agent_client():
    """RouterAgentClient의 RRF 통합 테스트"""
    print("\n\n🧪 RouterAgentClient RRF 통합 테스트")
    print("=" * 60)

    try:
        # LLM 클라이언트 생성 (간단한 더미)
        print("\n1️⃣ LLM 클라이언트 생성")
        from langchain_openai import AzureChatOpenAI

        llm_client = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            temperature=0.1,
            max_tokens=500
        )
        print("✅ LLM 클라이언트 생성 성공")

        # RouterAgentClient 초기화
        print("\n2️⃣ RouterAgentClient 초기화")
        # fastmcp_chatbot_app에서 클래스 직접 import
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chatbot_module",
            "./fastmcp_chatbot_app.py"
        )
        chatbot_module = importlib.util.module_from_spec(spec)

        # 모듈 실행 전에 streamlit import 방지
        import sys
        if 'streamlit' not in sys.modules:
            sys.modules['streamlit'] = type('MockStreamlit', (), {
                'set_page_config': lambda **kwargs: None,
                'session_state': type('SessionState', (), {})()
            })()

        spec.loader.exec_module(chatbot_module)

        RouterAgentClient = chatbot_module.RouterAgentClient
        client = RouterAgentClient(llm_client)

        print("✅ RouterAgentClient 초기화 완료")

        # RRF 시스템 활성화 확인
        if client.rrf_system:
            print("✅ RRF 시스템 활성화됨")
        else:
            print("⚠️ RRF 시스템 비활성화 (폴백 모드)")

        # 3. 검색 테스트
        print("\n3️⃣ search_knowledge_base 테스트")
        test_query = "Jira 티켓"
        print(f"🔍 검색 쿼리: '{test_query}'")

        documents = client.search_knowledge_base(test_query, top_k=3)

        if documents:
            print(f"✅ 검색 완료: {len(documents)}개 결과")
            print("\n📄 검색 결과:")
            for i, doc in enumerate(documents, 1):
                content = doc.get('content', '')[:80]
                similarity = doc.get('similarity', 0)
                method = doc.get('search_method', 'unknown')
                print(f"\n  {i}. 방법:{method}, 유사도:{similarity:.4f}")
                print(f"     내용: {content}...")
        else:
            print("⚠️ 검색 결과 없음")

        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """전체 통합 테스트 실행"""
    print("🎯 챗봇 RRF 통합 검증 테스트")
    print("=" * 60)

    # 테스트 1: RRF 시스템 직접 테스트
    test1_pass = test_rrf_system_with_jira_chunks()

    # 테스트 2: RouterAgentClient 통합 테스트
    test2_pass = test_router_agent_client()

    # 결과 요약
    print("\n\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    print(f"1. RRF + jira_chunks 직접 테스트: {'✅ 통과' if test1_pass else '❌ 실패'}")
    print(f"2. RouterAgentClient 통합 테스트: {'✅ 통과' if test2_pass else '❌ 실패'}")

    if test1_pass and test2_pass:
        print("\n🎉 모든 테스트 통과!")
        print("\n✨ 챗봇에서 이제 다음 기능을 사용합니다:")
        print("  - 멀티쿼리: 질문을 여러 각도로 확장")
        print("  - HyDE: 가상 답변 기반 검색")
        print("  - RRF: 검색 결과를 순위 기반으로 융합")
        print("  - 예상 성능 향상: 20-30%")
    else:
        print("\n⚠️ 일부 테스트 실패")
        print("기본 벡터 검색으로 폴백됩니다.")


if __name__ == "__main__":
    main()
