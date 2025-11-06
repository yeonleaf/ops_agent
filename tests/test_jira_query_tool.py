#!/usr/bin/env python3
"""
JiraQueryTool 테스트 스크립트
"""

import sys
import os

# 상위 디렉토리를 path에 추가 (import 가능하도록)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from tools.jira_query_tool import JiraQueryTool
from batch.jira_client import JiraAPIError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_jira_query_tool():
    """
    JiraQueryTool 기본 테스트
    """
    print("=" * 70)
    print("🧪 JiraQueryTool 테스트")
    print("=" * 70)

    try:
        # 1. 초기화 테스트
        print("\n[1] JiraQueryTool 초기화")
        print("   user_id=1로 JiraQueryTool을 초기화합니다...")

        try:
            tool = JiraQueryTool(user_id=1)
            print("   ✅ 초기화 성공")
        except ValueError as e:
            print(f"   ❌ 초기화 실패 (설정 오류): {e}")
            print("   💡 Jira 설정이 없거나 불완전합니다.")
            print("   💡 integration 테이블에 Jira endpoint와 token을 등록해주세요.")
            return
        except Exception as e:
            print(f"   ❌ 초기화 실패: {e}")
            return

        # 2. 연결 테스트
        print("\n[2] Jira 연결 테스트")
        print("   Jira 서버에 연결을 시도합니다...")

        if tool.test_connection():
            print("   ✅ 연결 성공")
        else:
            print("   ❌ 연결 실패")
            print("   💡 Jira 서버 URL 또는 토큰을 확인해주세요.")
            return

        # 3. 간단한 JQL 쿼리 테스트
        print("\n[3] JQL 쿼리 테스트")
        print("   간단한 JQL 쿼리를 실행합니다 (최대 5개 이슈)...")

        # 테스트용 JQL (실제 환경에 맞게 수정 필요)
        jql = "ORDER BY created DESC"
        print(f"   JQL: {jql}")

        try:
            issues = tool.get_issues_by_jql(jql, max_results=5)
            print(f"   ✅ 조회 성공: {len(issues)}개 이슈")

            if issues:
                print("\n[4] 첫 번째 이슈 상세 정보:")
                first_issue = issues[0]
                for key, value in first_issue.items():
                    # 값이 너무 길면 잘라서 표시
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"      {key}: {value}")

                # 필드 존재 확인
                assert "key" in first_issue, "key 필드가 없습니다"
                assert "summary" in first_issue, "summary 필드가 없습니다"
                print("\n   ✅ 필수 필드 확인 완료 (key, summary)")
            else:
                print("   ⚠️ 조회된 이슈가 없습니다.")

        except JiraAPIError as e:
            print(f"   ❌ JQL 쿼리 실패: {e}")
            return
        except Exception as e:
            print(f"   ❌ 예상치 못한 에러: {e}")
            return

        # 4. 여러 쿼리 통합 테스트
        print("\n[5] 여러 JQL 쿼리 통합 테스트")
        print("   여러 사용자별 쿼리를 실행하고 결과를 통합합니다...")

        queries = [
            {"user": "user1", "jql": "ORDER BY created DESC"},
            {"user": "user2", "jql": "ORDER BY updated DESC"},
        ]

        try:
            all_issues = tool.fetch_for_queries(queries)
            print(f"   ✅ 통합 조회 성공: {len(all_issues)}개 이슈")

            if all_issues:
                # _query_user 필드 확인
                for issue in all_issues[:3]:  # 처음 3개만 확인
                    assert "_query_user" in issue, "_query_user 필드가 없습니다"

                print("   ✅ _query_user 필드 확인 완료")

                # 사용자별 통계
                user_stats = {}
                for issue in all_issues:
                    user = issue.get("_query_user", "Unknown")
                    user_stats[user] = user_stats.get(user, 0) + 1

                print("\n   사용자별 이슈 수:")
                for user, count in user_stats.items():
                    print(f"      {user}: {count}개")

        except Exception as e:
            print(f"   ❌ 통합 쿼리 실패: {e}")
            return

        print("\n" + "=" * 70)
        print("✅ 모든 테스트 통과!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 테스트 실행 중 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_jira_query_tool()
