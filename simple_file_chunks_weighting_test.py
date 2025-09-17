#!/usr/bin/env python3
"""
file_chunks 데이터를 활용한 간단한 가중치 테스트
pandas 의존성 없이 실행 가능
"""

import os
import sys
import chromadb
from chromadb.config import Settings
from typing import Dict, List, Any
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from intelligent_chunk_weighting import IntelligentChunkWeighting

class FileChunksWeightingTest:
    """file_chunks 기반 가중치 테스트"""

    def __init__(self):
        """초기화"""
        self.client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        self.collection = self.client.get_collection("file_chunks")
        self.weighting_system = IntelligentChunkWeighting()
        print(f"📊 file_chunks 컬렉션: {self.collection.count()}개 문서")

    def search_with_weighting(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """가중치 적용 검색"""
        try:
            # 1. 기본 벡터 검색
            basic_results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )

            if not basic_results['ids'][0]:
                return []

            # 2. 검색 결과 변환
            search_results = []
            for i in range(len(basic_results['ids'][0])):
                metadata = basic_results['metadatas'][0][i] if basic_results['metadatas'][0] else {}
                content = basic_results['documents'][0][i] if basic_results['documents'][0] else ""
                distance = basic_results['distances'][0][i] if basic_results['distances'][0] else 1.0

                cosine_score = max(0.0, 1.0 - distance)
                chunk_type = self._estimate_chunk_type(content)

                search_result = {
                    'id': basic_results['ids'][0][i],
                    'content': content,
                    'chunk_type': chunk_type,
                    'cosine_score': cosine_score,
                    'embedding': [],
                    'metadata': metadata
                }
                search_results.append(search_result)

            # 3. 가중치 적용
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()
            weighted_results = self.weighting_system.apply_weighted_scoring(
                search_results, mock_query_embedding
            )

            return weighted_results

        except Exception as e:
            print(f"❌ 검색 실패: {e}")
            return []

    def _estimate_chunk_type(self, content: str) -> str:
        """내용 기반 chunk_type 추정"""
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

def run_weighting_test():
    """가중치 테스트 실행"""
    print("🎯 file_chunks 가중치 효과 검증 테스트")
    print("="*80)

    test_questions = [
        "사용자 인터페이스 개선 방안",
        "서버 접속 문제 해결",
        "데이터베이스 연결 오류",
        "시스템 성능 최적화",
        "프로젝트 요약 정보"
    ]

    tester = FileChunksWeightingTest()

    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 테스트 {i}: {question}")
        print("-" * 60)

        # 가중치 적용 검색
        weighted_results = tester.search_with_weighting(question)

        if weighted_results:
            print(f"✅ {len(weighted_results)}개 결과")

            # 상위 3개 결과 표시
            for j, result in enumerate(weighted_results[:3], 1):
                chunk_type = result.chunk_type
                original_score = result.cosine_score
                weighted_score = result.weighted_score
                weight = result.weight
                improvement = weighted_score - original_score

                print(f"  {j}. [{chunk_type.upper()}] (가중치: {weight:.1f})")
                print(f"     점수 변화: {original_score:.4f} → {weighted_score:.4f} ({improvement:+.4f})")

                # 내용 미리보기
                content_preview = result.content[:80].replace('\n', ' ') + "..."
                print(f"     내용: {content_preview}")
                print()

            # 통계 요약
            chunk_type_stats = {}
            for result in weighted_results:
                chunk_type = result.chunk_type
                if chunk_type not in chunk_type_stats:
                    chunk_type_stats[chunk_type] = []
                improvement = result.weighted_score - result.cosine_score
                chunk_type_stats[chunk_type].append(improvement)

            print("📊 가중치 효과 통계:")
            for chunk_type, improvements in chunk_type_stats.items():
                avg_improvement = np.mean(improvements)
                count = len(improvements)
                weight = tester.weighting_system.config.get_weight(chunk_type)
                print(f"  - {chunk_type}: {count}개, 가중치 {weight:.1f}, 평균 점수 변화 {avg_improvement:+.4f}")

        else:
            print("❌ 결과 없음")

if __name__ == "__main__":
    run_weighting_test()