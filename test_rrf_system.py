#!/usr/bin/env python3
"""
RRF (Reciprocal Rank Fusion) 시스템 테스트
file_chunks 데이터를 활용하여 RRF vs 기존 하이브리드 방식 성능 비교
"""

import os
import sys
import chromadb
from chromadb.config import Settings
from typing import Dict, List, Any
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rrf_fusion_rag_system import RRFRAGSystem

class RRFSystemTester:
    """RRF 시스템 테스트 클래스"""

    def __init__(self):
        """초기화"""
        self.client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        self.collection = self.client.get_collection("file_chunks")
        self.rrf_system = RRFRAGSystem("file_chunks")
        print(f"📊 file_chunks 컬렉션: {self.collection.count()}개 문서")

    def run_comparison_test(self, test_queries: List[str], n_results: int = 10):
        """RRF vs 하이브리드 방식 비교 테스트"""
        print("🎯 RRF vs 멀티쿼리/HyDE 개별 성능 비교 테스트")
        print("=" * 80)

        total_rrf_score = 0.0
        total_multi_score = 0.0
        total_hyde_score = 0.0
        valid_tests = 0

        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 테스트 {i}: {query}")
            print("-" * 60)

            try:
                # RRF 방식으로 검색
                rrf_results = self.rrf_system.rrf_search(query)

                # 멀티쿼리 검색 (개별)
                multi_results = self.rrf_system.multi_query_search(query)

                # HyDE 검색 (개별)
                hyde_results = self.rrf_system.hyde_search(query)

                if rrf_results and multi_results and hyde_results:
                    # 상위 결과들의 평균 점수 계산
                    rrf_avg_score = np.mean([r.get('score', r.get('cosine_score', 0)) for r in rrf_results[:5]])
                    multi_avg_score = np.mean([r.get('cosine_score', 0) for r in multi_results[:5]])
                    hyde_avg_score = np.mean([r.get('cosine_score', 0) for r in hyde_results[:5]])

                    total_rrf_score += rrf_avg_score
                    total_multi_score += multi_avg_score
                    total_hyde_score += hyde_avg_score
                    valid_tests += 1

                    multi_improvement = ((rrf_avg_score - multi_avg_score) / multi_avg_score) * 100 if multi_avg_score > 0 else 0
                    hyde_improvement = ((rrf_avg_score - hyde_avg_score) / hyde_avg_score) * 100 if hyde_avg_score > 0 else 0

                    print(f"✅ RRF 평균 점수: {rrf_avg_score:.4f}")
                    print(f"✅ 멀티쿼리 평균 점수: {multi_avg_score:.4f}")
                    print(f"✅ HyDE 평균 점수: {hyde_avg_score:.4f}")
                    print(f"📈 RRF vs 멀티쿼리 개선: {multi_improvement:+.2f}%")
                    print(f"📈 RRF vs HyDE 개선: {hyde_improvement:+.2f}%")

                    # 상위 3개 결과 비교
                    print("\n🔍 상위 결과 비교:")
                    print("RRF 방식:")
                    for j, result in enumerate(rrf_results[:3], 1):
                        content_preview = result.get('content', '')[:60].replace('\n', ' ') + "..."
                        score = result.get('score', result.get('cosine_score', 0))
                        print(f"  {j}. {score:.4f} - {content_preview}")

                    print("멀티쿼리 방식:")
                    for j, result in enumerate(multi_results[:3], 1):
                        content_preview = result.get('content', '')[:60].replace('\n', ' ') + "..."
                        score = result.get('cosine_score', 0)
                        print(f"  {j}. {score:.4f} - {content_preview}")

                    print("HyDE 방식:")
                    for j, result in enumerate(hyde_results[:3], 1):
                        content_preview = result.get('content', '')[:60].replace('\n', ' ') + "..."
                        score = result.get('cosine_score', 0)
                        print(f"  {j}. {score:.4f} - {content_preview}")

                else:
                    print("❌ 결과 없음")

            except Exception as e:
                print(f"❌ 테스트 실패: {e}")

        # 전체 성능 요약
        if valid_tests > 0:
            avg_rrf_score = total_rrf_score / valid_tests
            avg_multi_score = total_multi_score / valid_tests
            avg_hyde_score = total_hyde_score / valid_tests

            rrf_vs_multi = ((avg_rrf_score - avg_multi_score) / avg_multi_score) * 100 if avg_multi_score > 0 else 0
            rrf_vs_hyde = ((avg_rrf_score - avg_hyde_score) / avg_hyde_score) * 100 if avg_hyde_score > 0 else 0

            print(f"\n📊 전체 성능 요약 ({valid_tests}개 테스트)")
            print("=" * 50)
            print(f"RRF 평균 점수: {avg_rrf_score:.4f}")
            print(f"멀티쿼리 평균 점수: {avg_multi_score:.4f}")
            print(f"HyDE 평균 점수: {avg_hyde_score:.4f}")
            print(f"RRF vs 멀티쿼리 전체 개선: {rrf_vs_multi:+.2f}%")
            print(f"RRF vs HyDE 전체 개선: {rrf_vs_hyde:+.2f}%")

    def test_rrf_fusion_details(self, query: str):
        """RRF 융합 세부 과정 분석"""
        print(f"\n🔬 RRF 융합 세부 분석: '{query}'")
        print("=" * 60)

        try:
            # 멀티쿼리 검색 결과
            multi_query_results = self.rrf_system.multi_query_search(query)
            print(f"📋 멀티쿼리 검색: {len(multi_query_results)}개 결과")
            for i, result in enumerate(multi_query_results[:3], 1):
                score = result.get('cosine_score', 0)
                content = result.get('content', '')[:50]
                print(f"  {i}. {score:.4f} - {content}...")

            # HyDE 검색 결과
            hyde_results = self.rrf_system.hyde_search(query)
            print(f"📋 HyDE 검색: {len(hyde_results)}개 결과")
            for i, result in enumerate(hyde_results[:3], 1):
                score = result.get('cosine_score', 0)
                content = result.get('content', '')[:50]
                print(f"  {i}. {score:.4f} - {content}...")

            # RRF 융합 결과
            fused_results = self.rrf_system.rrf_search(query)
            print(f"📋 RRF 융합 결과: {len(fused_results)}개 결과")
            for i, result in enumerate(fused_results[:3], 1):
                score = result.get('score', result.get('cosine_score', 0))
                content = result.get('content', '')[:50]
                rrf_rank = result.get('rrf_rank', i)
                print(f"  {i}. 점수:{score:.4f}, RRF순위:{rrf_rank} - {content}...")

        except Exception as e:
            print(f"❌ 세부 분석 실패: {e}")

def main():
    """메인 테스트 함수"""
    print("🚀 RRF 시스템 종합 테스트 시작")

    # 테스트 쿼리들
    test_queries = [
        "사용자 인터페이스 개선 방안",
        "서버 접속 문제 해결",
        "데이터베이스 연결 오류",
        "시스템 성능 최적화",
        "프로젝트 관리 및 계획",
        "API 통합 문제",
        "보안 취약점 분석",
        "메모리 사용량 최적화"
    ]

    tester = RRFSystemTester()

    # 1. 전체 비교 테스트
    tester.run_comparison_test(test_queries)

    # 2. 특정 쿼리에 대한 세부 분석
    tester.test_rrf_fusion_details("사용자 인터페이스 개선 방안")

if __name__ == "__main__":
    main()