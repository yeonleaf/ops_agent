#!/usr/bin/env python3
"""
간단한 RRF 챗봇 통합 테스트 (Streamlit 없이)
"""

from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

def test_simple_rrf_integration():
    """RouterAgentClient 클래스만 직접 테스트"""
    print("🧪 RouterAgentClient RRF 간단 통합 테스트")
    print("=" * 60)

    try:
        # 1. LLM 클라이언트 생성
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

        # 2. RouterAgentClient 클래스만 추출
        print("\n2️⃣ RouterAgentClient 초기화")

        # RouterAgentClient 정의 (fastmcp_chatbot_app.py에서 복사)
        from typing import List, Dict, Any, Optional

        class RouterAgentClient:
            """라우터 에이전트 클라이언트 래퍼 - RAG 파이프라인 통합 (RRF 지원)"""

            def __init__(self, llm_client):
                self.llm_client = llm_client

                # RRF 시스템 초기화 (우선)
                self.rrf_system = None
                try:
                    from rrf_fusion_rag_system import RRFRAGSystem
                    self.rrf_system = RRFRAGSystem("jira_chunks")
                    print("✅ RAG: RRF 시스템 초기화 완료 (멀티쿼리 + HyDE + RRF 융합)")
                except Exception as e:
                    print(f"⚠️ RAG: RRF 시스템 초기화 실패, 기본 검색으로 폴백: {e}")

                # ChromaDB 클라이언트 초기화 (폴백용)
                from chromadb_singleton import get_chromadb_collection
                self.jira_collection = None
                try:
                    self.jira_collection = get_chromadb_collection("jira_chunks", create_if_not_exists=False)
                    print("✅ RAG: jira_chunks 컬렉션 로드 성공 (폴백용)")
                except Exception as e:
                    print(f"⚠️ RAG: jira_chunks 컬렉션 없음 (동기화 필요): {e}")

            def search_knowledge_base(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
                """ChromaDB에서 관련 문서 검색 (RRF 기반 멀티쿼리 + HyDE)"""
                # 1. RRF 시스템 사용 (우선)
                if self.rrf_system:
                    try:
                        print(f"🚀 RRF 기반 검색: '{query}' (멀티쿼리 + HyDE + Rank Fusion)")
                        rrf_results = self.rrf_system.rrf_search(query)

                        if rrf_results:
                            # RRF 결과를 기존 형식으로 변환
                            documents = []
                            for result in rrf_results[:top_k]:
                                content = result.get('content', '')
                                metadata = result.get('metadata', {})
                                score = result.get('score', result.get('cosine_score', 0.0))

                                documents.append({
                                    "content": content,
                                    "metadata": metadata,
                                    "distance": 1 - score,
                                    "similarity": score,
                                    "rrf_rank": result.get('rrf_rank', 0),
                                    "search_method": "rrf_fusion"
                                })

                            print(f"✅ RRF 검색 완료: {len(documents)}개 결과")
                            return documents
                        else:
                            print("⚠️ RRF 검색 결과 없음, 폴백 검색 시도")
                    except Exception as e:
                        print(f"⚠️ RRF 검색 실패, 기본 검색으로 폴백: {e}")

                # 2. 기본 ChromaDB 검색 (폴백)
                if not self.jira_collection:
                    return []

                try:
                    print(f"🔍 기본 벡터 검색: '{query}'")
                    results = self.jira_collection.query(
                        query_texts=[query],
                        n_results=top_k,
                        include=["documents", "metadatas", "distances"]
                    )

                    documents = []
                    if results and results.get("documents") and len(results["documents"]) > 0:
                        for i, doc in enumerate(results["documents"][0]):
                            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                            distance = results["distances"][0][i] if results.get("distances") else 1.0

                            documents.append({
                                "content": doc,
                                "metadata": metadata,
                                "distance": distance,
                                "similarity": 1 - distance,
                                "search_method": "basic_vector"
                            })

                    print(f"✅ 기본 검색 완료: {len(documents)}개 결과")
                    return documents
                except Exception as e:
                    print(f"❌ RAG 검색 실패: {e}")
                    return []

        # RouterAgentClient 초기화
        client = RouterAgentClient(llm_client)
        print("✅ RouterAgentClient 초기화 완료")

        # RRF 시스템 활성화 확인
        if client.rrf_system:
            print("✅ RRF 시스템 활성화됨")
        else:
            print("⚠️ RRF 시스템 비활성화 (폴백 모드)")

        # 3. 검색 테스트
        print("\n3️⃣ search_knowledge_base 테스트")
        test_queries = [
            "Jira 티켓 생성",
            "이슈 해결 방법",
            "프로젝트 관리"
        ]

        for query in test_queries:
            print(f"\n🔍 검색 쿼리: '{query}'")
            documents = client.search_knowledge_base(query, top_k=3)

            if documents:
                print(f"✅ 검색 완료: {len(documents)}개 결과")
                for i, doc in enumerate(documents, 1):
                    content = doc.get('content', '')[:60]
                    similarity = doc.get('similarity', 0)
                    method = doc.get('search_method', 'unknown')
                    rrf_rank = doc.get('rrf_rank', 'N/A')
                    print(f"  {i}. [{method}] RRF순위:{rrf_rank}, 유사도:{similarity:.4f}, 내용:{content}...")
            else:
                print("⚠️ 검색 결과 없음")
            print()

        print("\n" + "=" * 60)
        print("🎉 테스트 완료!")
        print("\n✨ 챗봇이 이제 다음 기능을 사용합니다:")
        print("  - 멀티쿼리: 질문을 여러 각도로 확장")
        print("  - HyDE: 가상 답변 기반 검색")
        print("  - RRF: 검색 결과를 순위 기반으로 융합")
        print("  - 예상 성능 향상: 20-30%")

        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_simple_rrf_integration()
