#!/usr/bin/env python3
"""
RRF 점수 검증 스크립트
수정된 평가 스크립트가 올바르게 점수를 추출하는지 확인
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rrf_fusion_rag_system import RRFRAGSystem, RRFConfig
import logging

logging.basicConfig(level=logging.INFO)

# RAG 시스템 초기화
rrf_config = RRFConfig(
    deduplicate_tickets=True,
    deduplication_strategy='all_scores'
)

rag_system = RRFRAGSystem("jira_chunks", rrf_config)

# 테스트 쿼리
query = "동영상 다운로드가 지연되면 어떤 문제가 발생하지?"
results = rag_system.rrf_search(query)

print("\n✅ RRF 점수 추출 검증\n")
print(f"쿼리: {query}\n")
print(f"{'순위':<5} {'티켓 ID':<15} {'Score':<12} {'RRF Score':<12} {'청크 수':<8}")
print("-" * 70)

for i, result in enumerate(results[:10], start=1):
    metadata = result.get('metadata', {})

    # 티켓 ID 추출
    ticket_id = metadata.get('issue_key', 'N/A')

    # 점수 추출
    score = result.get('score', 0.0)
    rrf_score = metadata.get('rrf_score', 0.0)
    aggregated = metadata.get('aggregated_chunks', 1)

    print(f"{i:<5} {ticket_id:<15} {score:<12.6f} {rrf_score:<12.6f} {aggregated:<8}")

# RRF 점수 분석
print("\n📊 점수 분석:")
rrf_scores = [r.get('metadata', {}).get('rrf_score', 0.0) for r in results]
rrf_scores = [s for s in rrf_scores if s > 0]

if rrf_scores:
    print(f"  RRF 점수 범위: {min(rrf_scores):.6f} ~ {max(rrf_scores):.6f}")
    print(f"  RRF 점수 평균: {sum(rrf_scores)/len(rrf_scores):.6f}")
    print(f"  0이 아닌 RRF 점수: {len(rrf_scores)}/{len(results)}")

    # 이론적 RRF 점수 (k=60)
    k = 60
    theoretical_scores = [1.0/(k+r) for r in range(1, 6)]
    print(f"\n  이론적 단일 RRF 점수 (k=60):")
    for r, s in enumerate(theoretical_scores, 1):
        print(f"    Rank {r}: {s:.6f}")

    print(f"\n  실제 RRF 점수 (여러 검색 합산):")
    for r, s in enumerate(sorted(rrf_scores, reverse=True)[:5], 1):
        multiplier = s / (1.0/(k+1))
        print(f"    {r}위: {s:.6f} (단일 1위의 약 {multiplier:.1f}배)")
else:
    print("  ❌ RRF 점수가 모두 0입니다!")

print("\n✅ 검증 완료")
