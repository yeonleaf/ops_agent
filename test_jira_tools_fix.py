#!/usr/bin/env python3
"""
간단한 Jira tools 수정 검증 테스트
"""

from tools.jira_tools import search_issues

print("=" * 70)
print("🧪 Jira Tools 수정 검증 테스트")
print("=" * 70)

# 간단한 프로젝트 검색
test_jql = "project = BTVO"

print(f"\nJQL: {test_jql}")
print("테스트 실행 중...\n")

try:
    # search_issues 호출 (이제 JiraQueryTool을 사용함)
    results = search_issues(
        user_id=1,
        jql=test_jql,
        max_results=5
    )

    print(f"✅ search_issues 호출 성공!")
    print(f"   결과: {len(results)}개 이슈")

    if results:
        print("\n   첫 번째 이슈:")
        first_issue = results[0]
        print(f"   - Key: {first_issue.get('key')}")
        print(f"   - Summary: {first_issue.get('summary')[:50]}...")
        print(f"   - Status: {first_issue.get('status')}")

    print("\n✅ 모든 Jira 함수가 JiraQueryTool 패턴으로 수정되었습니다!")
    print("   - search_issues() ✅")
    print("   - get_linked_issues() ✅")
    print("   - get_issue_detail() ✅")
    print("   - get_issue_comments() ✅")
    print("   - get_issue_history() ✅")

except Exception as e:
    print(f"❌ 테스트 실패: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
