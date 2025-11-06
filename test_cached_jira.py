#!/usr/bin/env python3
"""
CachedJiraClient 테스트 스크립트

Jira API 캐싱이 올바르게 동작하는지 테스트합니다.
"""

import sys
import logging
from tools.jira_query_tool import JiraQueryTool
from cached_jira_client import get_total_cache_stats, get_all_cache_clients

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title=""):
    """구분선 출력"""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print(f"\n{'-'*80}\n")


def print_cache_stats():
    """캐시 통계 출력"""
    stats = get_total_cache_stats()

    print("📊 Jira API 캐시 통계")
    print(f"총 요청:       {stats['total_requests']:>6}건")
    print(f"캐시 히트:     {stats['cache_hits']:>6}건")
    print(f"캐시 미스:     {stats['cache_misses']:>6}건")
    print(f"히트율:        {stats['hit_rate']:>6}")
    print(f"API 호출:      {stats['api_calls']:>6}건")
    print(f"캐시 항목:     {stats['cached_items']:>6}개")
    print(f"사용자 수:     {stats['users']:>6}명")


def test_cached_jira_client():
    """CachedJiraClient 테스트"""

    print_separator("CachedJiraClient 테스트 시작")

    try:
        # 1. JiraQueryTool 초기화 (자동으로 CachedJiraClient 생성 및 등록)
        print("1️⃣ JiraQueryTool 초기화 (user_id=1)")
        tool = JiraQueryTool(user_id=1)
        print("   ✅ 초기화 완료\n")

        # 2. 첫 번째 검색 (캐시 미스 예상)
        print_separator("2️⃣ 첫 번째 검색 (캐시 미스 예상)")
        jql = "project = BTVO ORDER BY created DESC"
        print(f"   JQL: {jql}")
        print(f"   max_results: 10\n")

        issues1 = tool.get_issues_by_jql(jql, max_results=10)
        print(f"   ✅ 조회 완료: {len(issues1)}개 이슈")
        print_separator()
        print_cache_stats()

        # 3. 두 번째 검색 (같은 쿼리 - 캐시 히트 예상)
        print_separator("3️⃣ 두 번째 검색 (같은 쿼리 - 캐시 히트 예상)")
        issues2 = tool.get_issues_by_jql(jql, max_results=10)
        print(f"   ✅ 조회 완료: {len(issues2)}개 이슈")
        print_separator()
        print_cache_stats()

        # 4. 세 번째 검색 (같은 쿼리 - 캐시 히트 예상)
        print_separator("4️⃣ 세 번째 검색 (같은 쿼리 - 캐시 히트 예상)")
        issues3 = tool.get_issues_by_jql(jql, max_results=10)
        print(f"   ✅ 조회 완료: {len(issues3)}개 이슈")
        print_separator()
        print_cache_stats()

        # 5. 다른 쿼리 (캐시 미스 예상)
        print_separator("5️⃣ 다른 쿼리 (캐시 미스 예상)")
        jql2 = "project = BTVO AND status = '완료' ORDER BY created DESC"
        print(f"   JQL: {jql2}")
        issues4 = tool.get_issues_by_jql(jql2, max_results=5)
        print(f"   ✅ 조회 완료: {len(issues4)}개 이슈")
        print_separator()
        print_cache_stats()

        # 6. 특정 이슈 조회 (캐시 미스)
        if issues1:
            print_separator("6️⃣ 특정 이슈 조회 (캐시 미스)")
            issue_key = issues1[0]['key']
            print(f"   이슈 키: {issue_key}\n")

            # 첫 번째 조회
            issue = tool.client.get_issue(issue_key)
            print(f"   ✅ 조회 완료: {issue.get('key')}")
            print_separator()
            print_cache_stats()

            # 7. 같은 이슈 재조회 (캐시 히트)
            print_separator("7️⃣ 같은 이슈 재조회 (캐시 히트)")
            issue2 = tool.client.get_issue(issue_key)
            print(f"   ✅ 조회 완료: {issue2.get('key')}")
            print_separator()
            print_cache_stats()

        # 8. 최종 결과 분석
        print_separator("8️⃣ 최종 결과 분석")
        stats = get_total_cache_stats()

        print(f"✅ 테스트 완료!\n")
        print(f"   총 요청:     {stats['total_requests']}건")
        print(f"   캐시 히트:   {stats['cache_hits']}건")
        print(f"   캐시 미스:   {stats['cache_misses']}건")
        print(f"   히트율:      {stats['hit_rate']}")
        print(f"   API 호출:    {stats['api_calls']}건")
        print(f"   절감율:      {(1 - stats['api_calls'] / stats['total_requests']) * 100:.1f}%")

        # 성공 조건 확인
        if stats['cache_hits'] > 0 and stats['api_calls'] < stats['total_requests']:
            print("\n✅ 캐싱이 정상적으로 작동하고 있습니다!")
        else:
            print("\n⚠️  캐싱이 제대로 작동하지 않을 수 있습니다.")

        print_separator()

    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_cached_jira_client()
