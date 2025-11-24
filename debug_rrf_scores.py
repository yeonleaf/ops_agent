#!/usr/bin/env python3
"""
RRF 점수 디버깅 스크립트
실제 검색 결과의 점수 흐름을 추적
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rrf_fusion_rag_system import RRFRAGSystem, RRFConfig
import logging

# 로깅 레벨을 DEBUG로 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_single_query():
    """단일 쿼리로 점수 흐름 확인"""

    # RAG 시스템 초기화
    rrf_config = RRFConfig(
        rrf_k=60,
        multi_query_results=20,
        hyde_results=20,
        bm25_results=20,
        final_candidates=30,
        enable_bm25=True,
        bm25_tokenizer="korean",
        deduplicate_tickets=True,
        deduplication_strategy='all_scores'
    )

    rag_system = RRFRAGSystem(
        collection_name="jira_chunks",
        rrf_config=rrf_config
    )

    # 테스트 쿼리
    query = "동영상 다운로드가 지연되면 어떤 문제가 발생하지?"

    print(f"\n{'='*80}")
    print(f"🔍 테스트 쿼리: {query}")
    print(f"{'='*80}\n")

    # 검색 실행
    results = rag_system.rrf_search(query)

    print(f"\n📊 검색 결과 상세:")
    print(f"총 결과 수: {len(results)}")
    print(f"\n상위 10개 결과:\n")

    for i, result in enumerate(results[:10], start=1):
        doc_id = result.get('id', 'N/A')
        content_preview = result.get('content', '')[:50] + '...'

        # 점수 정보
        score = result.get('score', 'N/A')
        rrf_score_from_metadata = result.get('metadata', {}).get('rrf_score', 'N/A')
        final_score = result.get('final_score', 'N/A')

        # 메타데이터에서 티켓 ID 추출
        metadata = result.get('metadata', {})
        ticket_id = None
        for key in ['ticket_id', 'ticket_key', 'jira_key', 'issue_key', 'key']:
            if key in metadata:
                ticket_id = metadata[key]
                break

        print(f"{i:2d}. Ticket: {ticket_id or 'N/A'}")
        print(f"    Doc ID: {doc_id}")
        print(f"    Score: {score}")
        print(f"    RRF Score (metadata): {rrf_score_from_metadata}")
        print(f"    Final Score: {final_score}")
        print(f"    Content: {content_preview}")
        print(f"    All keys in result: {list(result.keys())}")
        print(f"    All keys in metadata: {list(metadata.keys())}")
        print()

    # RRF 점수 분포 확인
    print(f"\n📈 점수 분포 분석:")
    scores = [r.get('score', 0) for r in results if r.get('score')]
    if scores:
        print(f"  최대 점수: {max(scores):.6f}")
        print(f"  최소 점수: {min(scores):.6f}")
        print(f"  평균 점수: {sum(scores)/len(scores):.6f}")
        print(f"  고유 점수 개수: {len(set(scores))}")

    # 점수가 0인 결과 확인
    zero_score_count = sum(1 for r in results if r.get('score', 0) == 0)
    print(f"  점수가 0인 결과: {zero_score_count}/{len(results)}")

    return results

if __name__ == "__main__":
    results = debug_single_query()
