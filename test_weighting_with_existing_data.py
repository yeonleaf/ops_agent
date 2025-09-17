#!/usr/bin/env python3
"""
기존 file_chunks 데이터를 활용한 가중치 시스템 테스트
jira_multi_vector_chunks가 비어있어서 file_chunks를 활용
"""

import chromadb
from chromadb.config import Settings
from intelligent_chunk_weighting import IntelligentChunkWeighting, ChunkData, SearchResult
from setup_korean_embedding import KoreanEmbeddingFunction
import numpy as np
from typing import List, Dict, Any

def test_weighting_with_file_chunks():
    """기존 file_chunks 데이터를 활용한 가중치 테스트"""
    print("🚀 기존 file_chunks 데이터로 가중치 시스템 테스트")
    print("="*80)

    try:
        # ChromaDB 연결
        client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        # file_chunks 컬렉션 가져오기
        collection = client.get_collection("file_chunks")
        print(f"📊 file_chunks 컬렉션: {collection.count()}개 문서")

        # 한국어 임베딩 함수 초기화
        korean_embedding = KoreanEmbeddingFunction()

        # 테스트 쿼리들
        test_queries = [
            "사용자 인터페이스 개선 방안",
            "서버 접속 문제 해결",
            "데이터베이스 연결 오류",
            "시스템 아키텍처 설계"
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 테스트 {i}: {query}")
            print("-" * 60)

            # 1. 기본 벡터 검색 (가중치 없음)
            query_embedding = korean_embedding([query])
            basic_results = collection.query(
                query_embeddings=query_embedding,
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
                chunk_type = estimate_chunk_type_from_metadata(metadata, content)

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

            # 3. 가중치 시스템 적용
            weighting_system = IntelligentChunkWeighting()
            weighted_results = weighting_system.apply_weighted_scoring(
                search_results, query_embedding[0]
            )

            # 4. 결과 비교 출력
            print("\n📋 Before weighting (기본 유사도 순):")
            for j, result in enumerate(search_results[:5], 1):
                chunk_type = result['chunk_type']
                score = result['cosine_score']
                weight = weighting_system.config.get_weight(chunk_type)
                print(f"  {j}. {chunk_type}: {score:.4f} (가중치: {weight:.1f})")

            print("\n📋 After weighting (가중치 적용 순):")
            for j, result in enumerate(weighted_results[:5], 1):
                print(f"  {j}. {result.chunk_type}: {result.cosine_score:.4f} → {result.weighted_score:.4f} "
                      f"(가중치: {result.weight:.1f})")

            # 5. 순위 변화 분석
            rank_changes = analyze_rank_changes(search_results, weighted_results)
            if rank_changes:
                print("\n📈 주요 순위 변화:")
                for change in rank_changes[:3]:
                    print(f"  {change}")

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

def estimate_chunk_type_from_metadata(metadata: Dict[str, Any], content: str) -> str:
    """메타데이터와 내용을 기반으로 chunk_type 추정"""

    # 파일명에서 타입 추정
    file_name = metadata.get('file_name', '').lower()
    section_title = metadata.get('section_title', '').lower()

    # 섹션 제목이나 파일명에서 타입 판단
    if any(keyword in section_title for keyword in ['title', '제목', 'heading']):
        return 'title'
    elif any(keyword in section_title for keyword in ['summary', '요약', '개요']):
        return 'summary'
    elif any(keyword in section_title for keyword in ['description', '설명', '상세']):
        return 'description'
    elif any(keyword in section_title for keyword in ['comment', '댓글', '의견']):
        return 'comment'
    elif any(keyword in section_title for keyword in ['header', '헤더']):
        return 'header'

    # 파일 확장자에서 타입 추정
    elif any(ext in file_name for ext in ['.pdf', '.doc', '.txt']):
        # 내용 길이로 판단
        if len(content) < 50:
            return 'title'
        elif len(content) < 200:
            return 'summary'
        elif len(content) > 1000:
            return 'body'
        else:
            return 'description'

    # 기타 메타데이터 활용
    elif metadata.get('element_count', 0) == 1:
        return 'title'  # 단일 요소는 제목으로 추정

    # 기본값
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
                direction = "상승" if rank_change > 0 else "하락"
                chunk_type = next((r.chunk_type for r in weighted_results if r.id == doc_id), "unknown")
                changes.append(f"{doc_id[:8]}... ({chunk_type}): {basic_rank} → {weighted_rank} ({direction})")

    return changes

if __name__ == "__main__":
    test_weighting_with_file_chunks()