#!/usr/bin/env python3
"""
HyDE RAG 시스템 (Mock LLM 버전)
OpenAI 라이브러리 없이 Mock 데이터로 HyDE 개념 검증
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
import numpy as np
import random

# 기존 모듈들 import
from intelligent_chunk_weighting import IntelligentChunkWeighting

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HyDEConfig:
    """HyDE 시스템 설정"""
    multi_query_count: int = 3
    hyde_document_count: int = 1
    top_k_per_query: int = 15
    final_candidates: int = 50

class MockHyDEGenerator:
    """Mock HyDE 문서 생성기 (OpenAI 라이브러리 없이 테스트용)"""

    def __init__(self, config: HyDEConfig):
        self.config = config
        logger.info("✅ Mock HyDE 생성기 초기화 완료")

    def generate_hypothetical_document(self, question: str) -> str:
        """Mock HyDE 문서 생성"""
        # 질문에 따른 Mock 가상 문서 생성
        mock_documents = {
            "사용자 인터페이스": "제목: UI 개선 프로젝트\n요약: 사용자 인터페이스의 직관성을 높이고 사용자 경험을 개선하는 프로젝트입니다.\n설명: 기존 UI의 복잡한 메뉴 구조를 단순화하고, 주요 기능에 대한 접근성을 향상시켰습니다. 사용자 피드백을 바탕으로 버튼 배치를 최적화하고 색상 대비를 개선했습니다.",

            "서버 접속": "제목: 서버 접속 문제 해결\n요약: 서버 연결 실패 문제의 원인 분석 및 해결 방안을 제시합니다.\n설명: 네트워크 연결 상태 확인, 방화벽 설정 점검, 포트 상태 확인 등의 단계적 해결 방법을 통해 서버 접속 문제를 해결했습니다. 로그 분석 결과 타임아웃 설정이 원인이었으며, 설정 변경 후 정상 동작을 확인했습니다.",

            "데이터베이스": "제목: 데이터베이스 연결 안정성 개선\n요약: DB 연결 끊김 현상의 원인 조사 및 안정성 향상 방안입니다.\n설명: 연결 풀 설정 최적화, 쿼리 성능 튜닝, 인덱스 재구성을 통해 데이터베이스 연결의 안정성을 크게 향상시켰습니다. 모니터링 시스템을 도입하여 실시간으로 DB 상태를 추적할 수 있게 되었습니다.",

            "API 성능": "제목: API 응답 시간 최적화\n요약: API 성능 개선을 통한 사용자 경험 향상 프로젝트입니다.\n설명: 캐싱 전략 도입, 쿼리 최적화, CDN 활용을 통해 API 응답 시간을 50% 단축했습니다. 비동기 처리 도입으로 동시 처리 능력도 크게 향상되었습니다."
        }

        # 질문과 가장 관련성 높은 Mock 문서 선택
        for keyword, doc in mock_documents.items():
            if keyword in question:
                logger.info(f"✅ HyDE 문서 생성 (키워드: {keyword})")
                return doc

        # 기본 Mock 문서
        default_doc = f"제목: {question} 해결 방안\n요약: {question}에 대한 상세한 분석과 해결 방법을 제시합니다.\n설명: 문제의 원인을 체계적으로 분석하고, 단계별 해결 방안을 통해 효과적인 문제 해결을 달성했습니다."
        logger.info("✅ HyDE 문서 생성 (기본 템플릿)")
        return default_doc

    def generate_multi_queries(self, question: str) -> List[str]:
        """Mock 멀티 쿼리 생성"""
        # 질문에 따른 Mock 멀티 쿼리 생성
        multi_queries_map = {
            "사용자 인터페이스": [
                "UI 개선 방법",
                "사용자 경험 향상 방안",
                "인터페이스 디자인 최적화"
            ],
            "서버 접속": [
                "서버 연결 오류 해결",
                "네트워크 접속 문제",
                "서버 통신 장애 대응"
            ],
            "데이터베이스": [
                "DB 연결 끊김 해결",
                "데이터베이스 안정성 개선",
                "DB 성능 최적화 방법"
            ],
            "API": [
                "API 성능 개선",
                "응답 시간 단축 방법",
                "서비스 속도 최적화"
            ]
        }

        # 키워드 매칭으로 적절한 멀티 쿼리 선택
        for keyword, queries in multi_queries_map.items():
            if keyword in question:
                logger.info(f"✅ 멀티 쿼리 생성 (키워드: {keyword})")
                return queries

        # 기본 멀티 쿼리
        default_queries = [
            f"{question} 해결",
            f"{question} 방법",
            f"{question} 개선"
        ]
        logger.info("✅ 멀티 쿼리 생성 (기본 템플릿)")
        return default_queries

class HyDERAGSystemMock:
    """Mock HyDE RAG 시스템"""

    def __init__(self, collection_name: str = "file_chunks", config: Optional[HyDEConfig] = None):
        self.collection_name = collection_name
        self.config = config or HyDEConfig()
        self._init_components()

    def _init_components(self):
        """컴포넌트 초기화"""
        try:
            # ChromaDB 연결
            self.client = chromadb.PersistentClient(
                path='./vector_db',
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            self.collection = self.client.get_collection(self.collection_name)

            # Mock HyDE 생성기
            self.hyde_generator = MockHyDEGenerator(self.config)

            # 가중치 시스템
            self.weighting_system = IntelligentChunkWeighting()

            logger.info(f"✅ Mock HyDE RAG 시스템 초기화 완료: {self.collection.count()}개 문서")

        except Exception as e:
            logger.error(f"❌ Mock HyDE RAG 시스템 초기화 실패: {e}")
            raise e

    def search(self, query: str, use_hyde: bool = True, use_multi_query: bool = True) -> List[Dict[str, Any]]:
        """HyDE 기반 하이브리드 검색"""
        try:
            logger.info(f"🚀 Mock HyDE RAG 검색 시작: '{query}'")

            # 1. 검색할 텍스트 리스트 준비
            texts_to_embed = [query]

            # 2. 멀티 쿼리 생성
            if use_multi_query:
                multi_queries = self.hyde_generator.generate_multi_queries(query)
                texts_to_embed.extend(multi_queries)
                logger.info(f"📝 멀티 쿼리: {multi_queries}")

            # 3. HyDE 문서 생성
            if use_hyde:
                hypothetical_doc = self.hyde_generator.generate_hypothetical_document(query)
                texts_to_embed.append(hypothetical_doc)
                logger.info(f"🎯 HyDE 문서: {hypothetical_doc[:100]}...")

            logger.info(f"🔍 총 {len(texts_to_embed)}개 텍스트로 검색 수행")

            # 4. 각 텍스트로 벡터 검색 수행
            all_results = []
            for i, text in enumerate(texts_to_embed):
                try:
                    results = self.collection.query(
                        query_texts=[text],
                        n_results=self.config.top_k_per_query
                    )

                    if results['ids'][0]:
                        for j in range(len(results['ids'][0])):
                            result = {
                                'id': results['ids'][0][j],
                                'content': results['documents'][0][j] if results['documents'][0] else "",
                                'distance': results['distances'][0][j] if results['distances'][0] else 1.0,
                                'metadata': results['metadatas'][0][j] if results['metadatas'][0] else {},
                                'query_type': 'original' if i == 0 else ('multi' if i < len(texts_to_embed) - (1 if use_hyde else 0) else 'hyde'),
                                'query_index': i,
                                'source_text': text[:50] + "..." if len(text) > 50 else text
                            }
                            all_results.append(result)

                    logger.info(f"   쿼리 {i+1}: {len(results['ids'][0]) if results['ids'][0] else 0}개 결과")

                except Exception as e:
                    logger.error(f"❌ 쿼리 {i+1} 검색 실패: {e}")
                    continue

            # 5. 결과 통합 및 중복 제거
            unique_results = self._process_and_deduplicate(all_results, query)

            logger.info(f"✅ Mock HyDE RAG 검색 완료: {len(unique_results)}개 고유 결과")
            return unique_results

        except Exception as e:
            logger.error(f"❌ Mock HyDE RAG 검색 실패: {e}")
            return []

    def _process_and_deduplicate(self, all_results: List[Dict[str, Any]], original_query: str) -> List[Dict[str, Any]]:
        """검색 결과 처리 및 중복 제거"""
        try:
            # 1. ID 기반 중복 제거 및 점수 통합
            unique_docs = {}

            for result in all_results:
                doc_id = result['id']
                distance = result['distance']
                cosine_score = max(0.0, 1.0 - distance)

                if doc_id not in unique_docs:
                    unique_docs[doc_id] = {
                        'id': doc_id,
                        'content': result['content'],
                        'metadata': result['metadata'],
                        'scores': [],
                        'query_types': [],
                        'source_texts': []
                    }

                unique_docs[doc_id]['scores'].append(cosine_score)
                unique_docs[doc_id]['query_types'].append(result['query_type'])
                unique_docs[doc_id]['source_texts'].append(result['source_text'])

            # 2. 점수 통합 (최대값 사용)
            processed_results = []
            for doc_id, doc_data in unique_docs.items():
                max_score = max(doc_data['scores'])

                # chunk_type 추정
                chunk_type = self._estimate_chunk_type(doc_data['metadata'], doc_data['content'])

                search_result = {
                    'id': doc_id,
                    'content': doc_data['content'],
                    'chunk_type': chunk_type,
                    'cosine_score': max_score,
                    'embedding': [],
                    'metadata': {
                        **doc_data['metadata'],
                        'query_types': doc_data['query_types'],
                        'source_texts': doc_data['source_texts'],
                        'scores': doc_data['scores'],
                        'max_score': max_score,
                        'hyde_enhanced': True
                    }
                }
                processed_results.append(search_result)

            # 3. 가중치 적용
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()
            weighted_results = self.weighting_system.apply_weighted_scoring(
                processed_results, mock_query_embedding
            )

            # 4. 최종 형식으로 변환
            final_results = []
            for weighted_result in weighted_results[:self.config.final_candidates]:
                result = {
                    "id": weighted_result.id,
                    "content": weighted_result.content,
                    "score": weighted_result.weighted_score,
                    "raw_score": weighted_result.cosine_score,
                    "weight": weighted_result.weight,
                    "chunk_type": weighted_result.chunk_type,
                    "source": "mock_hyde_rag_system",
                    "metadata": {
                        **weighted_result.metadata,
                        "hyde_enhanced": True,
                        "weight_applied": True
                    }
                }
                final_results.append(result)

            return final_results

        except Exception as e:
            logger.error(f"❌ 결과 처리 실패: {e}")
            return []

    def _estimate_chunk_type(self, metadata: Dict[str, Any], content: str) -> str:
        """chunk_type 추정"""
        content_lower = content.lower()

        if any(pattern in content_lower for pattern in ['제목:', 'title:', '이슈 키:']):
            return 'title'
        elif any(pattern in content_lower for pattern in ['요약:', 'summary:']):
            return 'summary'
        elif any(pattern in content_lower for pattern in ['설명:', 'description:']):
            return 'description'
        elif any(pattern in content_lower for pattern in ['댓글:', 'comment:']):
            return 'comment'
        elif len(content.strip()) < 30:
            return 'title'
        elif len(content.strip()) < 100:
            return 'summary'
        elif len(content.strip()) > 1000:
            return 'body'
        else:
            return 'description'

    def compare_search_methods(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """검색 방법별 성능 비교"""
        print(f"\n🔬 검색 방법별 성능 비교: '{query}'")
        print("="*80)

        # 1. 기본 검색 (원본 질문만)
        print("1️⃣ 기본 검색 (원본 질문만)")
        basic_results = self.search(query, use_hyde=False, use_multi_query=False)
        print(f"   결과: {len(basic_results)}개")

        # 2. 멀티 쿼리 검색
        print("2️⃣ 멀티 쿼리 검색")
        multi_results = self.search(query, use_hyde=False, use_multi_query=True)
        print(f"   결과: {len(multi_results)}개")

        # 3. HyDE 검색
        print("3️⃣ HyDE 검색")
        hyde_results = self.search(query, use_hyde=True, use_multi_query=False)
        print(f"   결과: {len(hyde_results)}개")

        # 4. 하이브리드 검색 (멀티 쿼리 + HyDE)
        print("4️⃣ 하이브리드 검색 (멀티 쿼리 + HyDE)")
        hybrid_results = self.search(query, use_hyde=True, use_multi_query=True)
        print(f"   결과: {len(hybrid_results)}개")

        # 결과 분석
        print(f"\n📊 결과 개수 비교:")
        print(f"   기본: {len(basic_results)}, 멀티쿼리: {len(multi_results)}, HyDE: {len(hyde_results)}, 하이브리드: {len(hybrid_results)}")

        return {
            'basic': basic_results,
            'multi_query': multi_results,
            'hyde': hyde_results,
            'hybrid': hybrid_results
        }

def test_mock_hyde_system():
    """Mock HyDE 시스템 테스트"""
    print("🚀 Mock HyDE RAG 시스템 테스트")
    print("="*80)

    try:
        # Mock HyDE 시스템 초기화
        hyde_rag = HyDERAGSystemMock(collection_name="file_chunks")

        # 테스트 질문들
        test_questions = [
            "사용자 인터페이스가 복잡해서 개선이 필요합니다",
            "서버에 접속할 수 없는 문제를 해결하고 싶어요",
            "데이터베이스 연결이 자주 끊어지는 현상을 조사해주세요",
            "API 응답 시간이 너무 느려서 최적화가 필요합니다"
        ]

        for i, question in enumerate(test_questions, 1):
            print(f"\n📝 테스트 {i}: {question}")
            print("-" * 60)

            # 하이브리드 검색 수행
            results = hyde_rag.search(question)

            if results:
                print(f"✅ {len(results)}개 결과 (HyDE + 멀티쿼리 + 가중치)")

                # 상위 3개 결과 표시
                for j, result in enumerate(results[:3], 1):
                    score = result.get('score', 0)
                    raw_score = result.get('raw_score', 0)
                    weight = result.get('weight', 1.0)
                    chunk_type = result.get('chunk_type', 'unknown')

                    print(f"  {j}. [{chunk_type.upper()}] (가중치: {weight:.1f})")
                    print(f"     점수: {raw_score:.4f} → {score:.4f}")

                    # 내용 미리보기
                    content = result.get('content', '')
                    preview = content[:100].replace('\n', ' ') + "..."
                    print(f"     내용: {preview}")

                    # HyDE 정보
                    metadata = result.get('metadata', {})
                    if metadata.get('query_types'):
                        query_types = set(metadata['query_types'])
                        print(f"     검색 타입: {', '.join(query_types)}")
                    print()

                # 검색 방법별 비교 (첫 번째 질문만)
                if i == 1:
                    hyde_rag.compare_search_methods(question)

            else:
                print("❌ 결과 없음")

        return True

    except Exception as e:
        print(f"❌ Mock HyDE 시스템 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_mock_hyde_system()