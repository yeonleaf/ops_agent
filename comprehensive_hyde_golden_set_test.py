#!/usr/bin/env python3
"""
HyDE + 가중치 + file_chunks 데이터를 활용한 포괄적 Golden Set 테스트
기본 검색 vs HyDE vs 하이브리드 성능 비교 포함
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import chromadb
from chromadb.config import Settings
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 모듈들 import
from intelligent_chunk_weighting import IntelligentChunkWeighting
from hyde_rag_system_mock import MockHyDEGenerator, HyDEConfig

class ComprehensiveHyDETestSystem:
    """HyDE 포괄적 테스트 시스템"""

    def __init__(self, collection_name: str = "file_chunks"):
        """
        초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
        """
        self.collection_name = collection_name
        self.config = HyDEConfig()

        # 컴포넌트 초기화
        self.client = None
        self.collection = None
        self.hyde_generator = None
        self.weighting_system = None

        self._init_components()

    def _init_components(self):
        """시스템 컴포넌트 초기화"""
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

            print(f"✅ 포괄적 HyDE 테스트 시스템 초기화 완료: {self.collection.count()}개 문서")

        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
            raise e

    def basic_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        1. 기본 검색 (원본 질문만)

        Args:
            query: 검색 쿼리
            n_results: 결과 수

        Returns:
            기본 검색 결과
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )

            if not results['ids'][0]:
                return []

            # 기본 형식으로 변환
            basic_results = []
            for i in range(len(results['ids'][0])):
                distance = results['distances'][0][i] if results['distances'][0] else 1.0
                cosine_score = max(0.0, 1.0 - distance)

                result = {
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i] if results['documents'][0] else "",
                    'score': cosine_score,
                    'raw_score': cosine_score,
                    'method': 'basic',
                    'source': 'basic_search'
                }
                basic_results.append(result)

            return basic_results

        except Exception as e:
            print(f"❌ 기본 검색 실패: {e}")
            return []

    def multi_query_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        2. 멀티 쿼리 검색

        Args:
            query: 검색 쿼리
            n_results: 결과 수

        Returns:
            멀티 쿼리 검색 결과
        """
        try:
            # 멀티 쿼리 생성
            multi_queries = self.hyde_generator.generate_multi_queries(query)
            all_texts = [query] + multi_queries

            # 각 쿼리로 검색
            all_results = []
            for i, text in enumerate(all_texts):
                results = self.collection.query(
                    query_texts=[text],
                    n_results=n_results
                )

                if results['ids'][0]:
                    for j in range(len(results['ids'][0])):
                        distance = results['distances'][0][j] if results['distances'][0] else 1.0
                        cosine_score = max(0.0, 1.0 - distance)

                        result = {
                            'id': results['ids'][0][j],
                            'content': results['documents'][0][j] if results['documents'][0] else "",
                            'distance': distance,
                            'cosine_score': cosine_score,
                            'query_type': 'original' if i == 0 else 'multi',
                            'query_index': i,
                            'source_text': text[:50] + "..." if len(text) > 50 else text
                        }
                        all_results.append(result)

            # 중복 제거 및 점수 통합
            unique_results = self._deduplicate_results(all_results)

            # 가중치 적용
            weighted_results = self._apply_weighting(unique_results)

            return weighted_results[:n_results]

        except Exception as e:
            print(f"❌ 멀티 쿼리 검색 실패: {e}")
            return []

    def hyde_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        3. HyDE 검색

        Args:
            query: 검색 쿼리
            n_results: 결과 수

        Returns:
            HyDE 검색 결과
        """
        try:
            # HyDE 문서 생성
            hypothetical_doc = self.hyde_generator.generate_hypothetical_document(query)
            all_texts = [query, hypothetical_doc]

            # 각 텍스트로 검색
            all_results = []
            for i, text in enumerate(all_texts):
                results = self.collection.query(
                    query_texts=[text],
                    n_results=n_results
                )

                if results['ids'][0]:
                    for j in range(len(results['ids'][0])):
                        distance = results['distances'][0][j] if results['distances'][0] else 1.0
                        cosine_score = max(0.0, 1.0 - distance)

                        result = {
                            'id': results['ids'][0][j],
                            'content': results['documents'][0][j] if results['documents'][0] else "",
                            'distance': distance,
                            'cosine_score': cosine_score,
                            'query_type': 'original' if i == 0 else 'hyde',
                            'query_index': i,
                            'source_text': text[:100] + "..." if len(text) > 100 else text
                        }
                        all_results.append(result)

            # 중복 제거 및 점수 통합
            unique_results = self._deduplicate_results(all_results)

            # 가중치 적용
            weighted_results = self._apply_weighting(unique_results)

            return weighted_results[:n_results]

        except Exception as e:
            print(f"❌ HyDE 검색 실패: {e}")
            return []

    def hybrid_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        4. 하이브리드 검색 (멀티 쿼리 + HyDE)

        Args:
            query: 검색 쿼리
            n_results: 결과 수

        Returns:
            하이브리드 검색 결과
        """
        try:
            # 멀티 쿼리 + HyDE 문서 생성
            multi_queries = self.hyde_generator.generate_multi_queries(query)
            hypothetical_doc = self.hyde_generator.generate_hypothetical_document(query)
            all_texts = [query] + multi_queries + [hypothetical_doc]

            # 각 텍스트로 검색
            all_results = []
            for i, text in enumerate(all_texts):
                results = self.collection.query(
                    query_texts=[text],
                    n_results=self.config.top_k_per_query
                )

                if results['ids'][0]:
                    for j in range(len(results['ids'][0])):
                        distance = results['distances'][0][j] if results['distances'][0] else 1.0
                        cosine_score = max(0.0, 1.0 - distance)

                        # 쿼리 타입 결정
                        if i == 0:
                            query_type = 'original'
                        elif i < len(all_texts) - 1:
                            query_type = 'multi'
                        else:
                            query_type = 'hyde'

                        result = {
                            'id': results['ids'][0][j],
                            'content': results['documents'][0][j] if results['documents'][0] else "",
                            'distance': distance,
                            'cosine_score': cosine_score,
                            'query_type': query_type,
                            'query_index': i,
                            'source_text': text[:100] + "..." if len(text) > 100 else text
                        }
                        all_results.append(result)

            # 중복 제거 및 점수 통합
            unique_results = self._deduplicate_results(all_results)

            # 가중치 적용
            weighted_results = self._apply_weighting(unique_results)

            return weighted_results[:n_results]

        except Exception as e:
            print(f"❌ 하이브리드 검색 실패: {e}")
            return []

    def _deduplicate_results(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """검색 결과 중복 제거 및 점수 통합"""
        unique_docs = {}

        for result in all_results:
            doc_id = result['id']
            cosine_score = result['cosine_score']

            if doc_id not in unique_docs:
                unique_docs[doc_id] = {
                    'id': doc_id,
                    'content': result['content'],
                    'scores': [],
                    'query_types': [],
                    'source_texts': []
                }

            unique_docs[doc_id]['scores'].append(cosine_score)
            unique_docs[doc_id]['query_types'].append(result['query_type'])
            unique_docs[doc_id]['source_texts'].append(result['source_text'])

        # 점수 통합 (최대값 사용)
        processed_results = []
        for doc_id, doc_data in unique_docs.items():
            max_score = max(doc_data['scores'])

            processed_result = {
                'id': doc_id,
                'content': doc_data['content'],
                'cosine_score': max_score,
                'query_types': doc_data['query_types'],
                'source_texts': doc_data['source_texts'],
                'scores': doc_data['scores']
            }
            processed_results.append(processed_result)

        return processed_results

    def _apply_weighting(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """가중치 적용"""
        try:
            # 가중치 시스템 형식으로 변환
            search_results = []
            for result in results:
                chunk_type = self._estimate_chunk_type(result['content'])

                search_result = {
                    'id': result['id'],
                    'content': result['content'],
                    'chunk_type': chunk_type,
                    'cosine_score': result['cosine_score'],
                    'embedding': [],
                    'metadata': {
                        'query_types': result.get('query_types', []),
                        'source_texts': result.get('source_texts', []),
                        'scores': result.get('scores', [])
                    }
                }
                search_results.append(search_result)

            # 가중치 적용
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()
            weighted_results = self.weighting_system.apply_weighted_scoring(
                search_results, mock_query_embedding
            )

            # 최종 형식으로 변환
            final_results = []
            for weighted_result in weighted_results:
                result = {
                    'id': weighted_result.id,
                    'content': weighted_result.content,
                    'score': weighted_result.weighted_score,
                    'raw_score': weighted_result.cosine_score,
                    'weight': weighted_result.weight,
                    'chunk_type': weighted_result.chunk_type,
                    'method': 'weighted',
                    'source': 'weighted_search',
                    'metadata': weighted_result.metadata
                }
                final_results.append(result)

            return final_results

        except Exception as e:
            print(f"❌ 가중치 적용 실패: {e}")
            return results

    def _estimate_chunk_type(self, content: str) -> str:
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

    def compare_all_methods(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """
        모든 검색 방법 비교

        Args:
            query: 검색 쿼리
            n_results: 각 방법별 결과 수

        Returns:
            비교 결과
        """
        print(f"\n🔬 검색 방법 종합 비교: '{query}'")
        print("="*80)

        # 각 방법별 검색 수행
        methods_results = {}

        # 1. 기본 검색
        print("1️⃣ 기본 검색 (원본 질문만)")
        basic_results = self.basic_search(query, n_results)
        methods_results['basic'] = basic_results
        print(f"   결과: {len(basic_results)}개")

        # 2. 멀티 쿼리 검색
        print("2️⃣ 멀티 쿼리 검색")
        multi_results = self.multi_query_search(query, n_results)
        methods_results['multi_query'] = multi_results
        print(f"   결과: {len(multi_results)}개")

        # 3. HyDE 검색
        print("3️⃣ HyDE 검색")
        hyde_results = self.hyde_search(query, n_results)
        methods_results['hyde'] = hyde_results
        print(f"   결과: {len(hyde_results)}개")

        # 4. 하이브리드 검색
        print("4️⃣ 하이브리드 검색 (멀티 쿼리 + HyDE)")
        hybrid_results = self.hybrid_search(query, n_results)
        methods_results['hybrid'] = hybrid_results
        print(f"   결과: {len(hybrid_results)}개")

        # 결과 분석
        self._analyze_comparison_results(methods_results, query)

        return methods_results

    def _analyze_comparison_results(self, methods_results: Dict[str, List[Dict[str, Any]]], query: str):
        """비교 결과 분석"""
        print(f"\n📊 성능 분석:")
        print("-" * 60)

        # 1. 결과 수 비교
        counts = {method: len(results) for method, results in methods_results.items()}
        print(f"결과 수: 기본({counts['basic']}) < 멀티쿼리({counts['multi_query']}) < HyDE({counts['hyde']}) < 하이브리드({counts['hybrid']})")

        # 2. 평균 점수 비교
        for method, results in methods_results.items():
            if results:
                avg_score = sum(r.get('score', r.get('raw_score', 0)) for r in results) / len(results)
                max_score = max(r.get('score', r.get('raw_score', 0)) for r in results)
                print(f"{method}: 평균 점수 {avg_score:.4f}, 최고 점수 {max_score:.4f}")

        # 3. 상위 결과 비교
        print(f"\n🏆 각 방법별 최고 점수 결과:")
        for method, results in methods_results.items():
            if results:
                best_result = max(results, key=lambda x: x.get('score', x.get('raw_score', 0)))
                score = best_result.get('score', best_result.get('raw_score', 0))
                content_preview = best_result['content'][:80].replace('\n', ' ') + "..."
                print(f"  {method}: {score:.4f} - {content_preview}")

        # 4. 고유성 분석 (하이브리드 검색의 경우)
        if 'hybrid' in methods_results and methods_results['hybrid']:
            hybrid_results = methods_results['hybrid']
            query_type_stats = {}
            for result in hybrid_results:
                if 'metadata' in result and 'query_types' in result['metadata']:
                    query_types = result['metadata']['query_types']
                    for qt in query_types:
                        query_type_stats[qt] = query_type_stats.get(qt, 0) + 1

            if query_type_stats:
                print(f"\n🎯 하이브리드 검색 구성:")
                for qt, count in query_type_stats.items():
                    print(f"  - {qt}: {count}개")

def run_comprehensive_hyde_test():
    """포괄적 HyDE 테스트 실행"""
    print("🚀 HyDE 포괄적 성능 테스트")
    print("="*80)

    try:
        # 테스트 시스템 초기화
        test_system = ComprehensiveHyDETestSystem()

        # 테스트 질문들
        test_questions = [
            "사용자 인터페이스가 복잡해서 개선이 필요합니다",
            "서버에 접속할 수 없는 문제를 해결하고 싶어요",
            "데이터베이스 연결이 자주 끊어지는 현상을 조사해주세요",
            "API 응답 시간이 너무 느려서 최적화가 필요합니다",
            "모바일 앱에서 로그인이 안 되는 문제가 있어요"
        ]

        # 전체 테스트 결과 저장
        all_test_results = {}

        for i, question in enumerate(test_questions, 1):
            print(f"\n📝 테스트 {i}/{len(test_questions)}: {question}")
            print("="*80)

            # 모든 방법 비교
            comparison_results = test_system.compare_all_methods(question, n_results=3)
            all_test_results[f"test_{i}"] = {
                'question': question,
                'results': comparison_results
            }

            # 간단한 결과 요약
            print(f"\n✅ 테스트 {i} 완료")

        # 전체 결과 요약
        print(f"\n🎉 전체 테스트 완료!")
        print("="*80)

        # 결과를 JSON 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"hyde_comprehensive_test_results_{timestamp}.json"

        # JSON 직렬화 가능한 형태로 변환
        serializable_results = {}
        for test_key, test_data in all_test_results.items():
            serializable_results[test_key] = {
                'question': test_data['question'],
                'results': {}
            }

            for method, results in test_data['results'].items():
                serializable_results[test_key]['results'][method] = []
                for result in results:
                    # 직렬화 가능한 필드만 포함
                    clean_result = {
                        'id': result.get('id', ''),
                        'content': result.get('content', '')[:200],  # 내용 길이 제한
                        'score': result.get('score', result.get('raw_score', 0)),
                        'method': result.get('method', method),
                        'chunk_type': result.get('chunk_type', 'unknown')
                    }
                    serializable_results[test_key]['results'][method].append(clean_result)

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)

        print(f"📄 상세 결과 저장: {results_file}")

        # 전체 통계 요약
        print(f"\n📊 전체 테스트 통계:")
        method_totals = {'basic': 0, 'multi_query': 0, 'hyde': 0, 'hybrid': 0}

        for test_data in all_test_results.values():
            for method, results in test_data['results'].items():
                method_totals[method] += len(results)

        for method, total in method_totals.items():
            avg_per_test = total / len(test_questions)
            print(f"  - {method}: 총 {total}개 결과 (평균 {avg_per_test:.1f}개/테스트)")

        return True

    except Exception as e:
        print(f"❌ 포괄적 HyDE 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_comprehensive_hyde_test()