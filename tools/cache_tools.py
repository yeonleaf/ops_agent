#!/usr/bin/env python3
"""
캐시 관련 Tool 모음
캐시에 저장된 Jira 이슈 데이터를 활용하는 Tool들
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_cached_issues(
    user_id: int,
    db_path: str = "tickets.db"
) -> List[Dict[str, Any]]:
    """
    현재 캐시에 저장된 모든 Jira 이슈를 가져옵니다.

    이 Tool은 새로운 Jira API 호출 없이 이미 조회한 데이터만 사용합니다.
    이전에 실행한 프롬프트에서 조회한 모든 이슈를 종합하여 분석할 때 유용합니다.

    Args:
        user_id: 로그인 사용자 ID
        db_path: 데이터베이스 파일 경로

    Returns:
        캐시된 이슈 딕셔너리 리스트 (중복 제거됨)

    Examples:
        >>> get_cached_issues(1)
        [
            {
                "key": "BTVO-123",
                "summary": "작업 제목",
                "status": "완료",
                "assignee": "홍길동",
                ...
            },
            ...
        ]

    Note:
        - API 호출을 하지 않으므로 매우 빠릅니다
        - 이슈 key 기준으로 중복이 제거됩니다
        - 캐시에 데이터가 없으면 빈 리스트를 반환합니다
        - 월이 바뀌면 캐시가 자동으로 초기화됩니다
    """
    try:
        from tools.jira_query_tool import JiraQueryTool

        # JiraQueryTool 초기화 (CachedJiraClient 재사용)
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client

        # 캐시된 모든 이슈 가져오기
        issues = client.get_all_cached_issues()

        logger.info(f"✅ 캐시된 이슈 조회 완료: {len(issues)}개")

        return issues

    except Exception as e:
        logger.error(f"❌ get_cached_issues 에러: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_cache_summary(
    user_id: int,
    db_path: str = "tickets.db"
) -> Dict[str, Any]:
    """
    현재 캐시 상태의 요약 정보를 가져옵니다.

    Args:
        user_id: 로그인 사용자 ID
        db_path: 데이터베이스 파일 경로

    Returns:
        캐시 요약 정보
        {
            "total_cached_items": int,      # 전체 캐시 항목 수
            "jql_queries": int,              # 캐시된 JQL 쿼리 수
            "individual_issues": int,        # 개별 이슈 수
            "unique_issues": int,            # 고유 이슈 수
            "month": str                     # 현재 월 (YYYY-MM)
        }

    Examples:
        >>> get_cache_summary(1)
        {
            "total_cached_items": 25,
            "jql_queries": 5,
            "individual_issues": 3,
            "unique_issues": 220,
            "month": "2025-11"
        }
    """
    try:
        from tools.jira_query_tool import JiraQueryTool

        # JiraQueryTool 초기화
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client

        # 캐시 요약 정보 가져오기
        summary = client.get_cache_summary()

        logger.info(f"✅ 캐시 요약 조회 완료: {summary['unique_issues']}개 고유 이슈")

        return summary

    except Exception as e:
        logger.error(f"❌ get_cache_summary 에러: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "total_cached_items": 0,
            "jql_queries": 0,
            "individual_issues": 0,
            "unique_issues": 0,
            "month": "unknown"
        }


if __name__ == "__main__":
    # 간단한 테스트
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 Cache Tools 모듈 테스트")
    print("=" * 60)

    try:
        print("\n[1] 캐시 요약 조회")
        summary = get_cache_summary(user_id=1)
        print(f"   ✅ 캐시 요약:")
        for key, value in summary.items():
            print(f"      {key}: {value}")

        print("\n[2] 캐시된 이슈 조회")
        issues = get_cached_issues(user_id=1)
        print(f"   ✅ 캐시된 이슈: {len(issues)}개")

        if issues:
            print("\n[3] 첫 번째 이슈:")
            first_issue = issues[0]
            for key, value in first_issue.items():
                print(f"      {key}: {value}")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
