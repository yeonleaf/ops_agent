#!/usr/bin/env python3
"""
기존 file_chunks 데이터를 활용한 가중치 시스템 테스트 (호환성 버전)
기존 384차원 임베딩 모델 사용
"""

import chromadb
from chromadb.config import Settings
from intelligent_chunk_weighting import IntelligentChunkWeighting, SearchResult
import numpy as np
from typing import List, Dict, Any

def test_weighting_with_compatible_embeddings():
    """기존 file_chunks와 호환되는 가중치 테스트"""
    print("🚀 기존 file_chunks 데이터로 가중치 시스템 테스트 (호환성 모드)")
    print("="*80)

    try:
        # ChromaDB 연결
        client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        # file_chunks 컬렉션 가져오기 (기존 임베딩 함수 사용)
        collection = client.get_collection("file_chunks")
        print(f"📊 file_chunks 컬렉션: {collection.count()}개 문서")

        # 테스트 쿼리들
        test_queries = [
            "사용자 인터페이스 개선 방안",
            "서버 접속 문제 해결",
            "데이터베이스 연결 오류",
            "시스템 성능 최적화"
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 테스트 {i}: {query}")
            print("-" * 60)

            # 1. 기본 벡터 검색 (기존 임베딩 함수 사용)
            basic_results = collection.query(
                query_texts=[query],
                n_results=10
            )

            if not basic_results['ids'][0]:
                print("❌ 기본 검색 결과 없음")
                continue

            print(f"✅ 기본 검색: {len(basic_results['ids'][0])}개 결과")

            # 2. 검색 결과를 가중치 시스템 형식으로 변환
            search_results = []
            for j in range(len(basic_results['ids'][0])):
                # 메타데이터에서 정보 추출
                metadata = basic_results['metadatas'][0][j] if basic_results['metadatas'][0] else {}
                content = basic_results['documents'][0][j] if basic_results['documents'][0] else ""
                distance = basic_results['distances'][0][j] if basic_results['distances'][0] else 1.0

                # 코사인 유사도로 변환 (거리 -> 유사도)
                cosine_score = max(0.0, 1.0 - distance)

                # chunk_type 추정 (파일 기반)
                chunk_type = estimate_chunk_type_from_content_and_metadata(metadata, content)

                search_result = {
                    'id': basic_results['ids'][0][j],
                    'content': content,
                    'chunk_type': chunk_type,
                    'cosine_score': cosine_score,
                    'embedding': [],  # 임베딩은 재계산하지 않음
                    'metadata': {
                        **metadata,
                        'estimated_chunk_type': chunk_type,
                        'original_distance': distance
                    }
                }
                search_results.append(search_result)

            # 3. 가중치 시스템 적용 (Mock 쿼리 임베딩 사용)
            weighting_system = IntelligentChunkWeighting()

            # Mock 쿼리 임베딩 (384차원으로 맞춤)
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()

            weighted_results = weighting_system.apply_weighted_scoring(
                search_results, mock_query_embedding
            )

            # 4. 결과 비교 출력
            print("\n📋 Before weighting (기본 유사도 순):")
            for j, result in enumerate(search_results[:5], 1):
                chunk_type = result['chunk_type']
                score = result['cosine_score']
                weight = weighting_system.config.get_weight(chunk_type)
                content_preview = result['content'][:50].replace('\n', ' ') + "..."
                print(f"  {j}. [{chunk_type}] {score:.4f} (가중치: {weight:.1f})")
                print(f"      내용: {content_preview}")

            print("\n📋 After weighting (가중치 적용 순):")
            for j, result in enumerate(weighted_results[:5], 1):
                content_preview = result.content[:50].replace('\n', ' ') + "..."
                print(f"  {j}. [{result.chunk_type}] {result.cosine_score:.4f} → {result.weighted_score:.4f} "
                      f"(가중치: {result.weight:.1f})")
                print(f"      내용: {content_preview}")

            # 5. 순위 변화 분석
            rank_changes = analyze_rank_changes(search_results, weighted_results)
            if rank_changes:
                print("\n📈 주요 순위 변화:")
                for change in rank_changes[:3]:
                    print(f"  {change}")
            else:
                print("\n📈 주요 순위 변화: 없음")

            # 6. 가중치 효과 통계
            print(f"\n📊 가중치 효과 통계:")
            chunk_type_stats = {}
            for result in weighted_results:
                chunk_type = result.chunk_type
                if chunk_type not in chunk_type_stats:
                    chunk_type_stats[chunk_type] = []
                improvement = result.weighted_score - result.cosine_score
                chunk_type_stats[chunk_type].append(improvement)

            for chunk_type, improvements in chunk_type_stats.items():
                avg_improvement = np.mean(improvements)
                count = len(improvements)
                weight = weighting_system.config.get_weight(chunk_type)
                print(f"  - {chunk_type}: {count}개, 가중치 {weight:.1f}, 평균 점수 변화 {avg_improvement:+.4f}")

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def estimate_chunk_type_from_content_and_metadata(metadata: Dict[str, Any], content: str) -> str:
    """메타데이터와 내용을 기반으로 chunk_type 추정 (개선된 버전)"""

    # 파일명에서 타입 추정
    file_name = metadata.get('file_name', '').lower()

    # 내용 기반 분석
    content_lower = content.lower()
    content_lines = content.split('\n')

    # 1. 구조적 패턴 분석
    if any(pattern in content_lower for pattern in ['제목:', 'title:', '이슈 키:', 'issue key:']):
        return 'title'
    elif any(pattern in content_lower for pattern in ['요약:', 'summary:', '개요:']):
        return 'summary'
    elif any(pattern in content_lower for pattern in ['설명:', 'description:', '상세:', '내용:']):
        return 'description'
    elif any(pattern in content_lower for pattern in ['댓글:', 'comment:', '의견:', '피드백:']):
        return 'comment'
    elif any(pattern in content_lower for pattern in ['헤더:', 'header:', '제목']):
        return 'header'

    # 2. 내용 길이 기반 분석
    elif len(content.strip()) < 30:
        return 'title'  # 매우 짧은 텍스트
    elif len(content.strip()) < 100:
        return 'summary'  # 짧은 텍스트
    elif len(content.strip()) > 1000:
        return 'body'  # 긴 텍스트

    # 3. 파일 확장자 기반 분석
    elif any(ext in file_name for ext in ['.pdf', '.doc', '.docx']):
        # 문서 파일인 경우 내용 패턴으로 세분화
        if len(content_lines) == 1:
            return 'title'
        elif len(content_lines) <= 3:
            return 'summary'
        else:
            return 'description'

    # 4. 메타데이터 기반 추가 분석
    elif metadata.get('element_count', 0) == 1:
        return 'title'  # 단일 요소
    elif 'vision_analysis' in metadata:
        return 'description'  # 시각적 분석이 포함된 경우

    # 5. 기본값
    else:
        return 'body'

def analyze_rank_changes(basic_results: List[Dict], weighted_results: List[SearchResult]) -> List[str]:
    """순위 변화 분석"""
    changes = []

    # ID 기반 순위 매핑
    basic_ranks = {result['id']: i+1 for i, result in enumerate(basic_results)}
    weighted_ranks = {result.id: i+1 for i, result in enumerate(weighted_results)}

    for doc_id in basic_ranks:
        if doc_id in weighted_ranks:
            basic_rank = basic_ranks[doc_id]
            weighted_rank = weighted_ranks[doc_id]
            rank_change = basic_rank - weighted_rank

            if abs(rank_change) >= 2:  # 2순위 이상 변화만 표시
                direction = "⬆️상승" if rank_change > 0 else "⬇️하락"
                chunk_type = next((r.chunk_type for r in weighted_results if r.id == doc_id), "unknown")
                changes.append(f"{doc_id[:12]}... ({chunk_type}): {basic_rank} → {weighted_rank} {direction}")

    return changes

if __name__ == "__main__":
    test_weighting_with_compatible_embeddings()