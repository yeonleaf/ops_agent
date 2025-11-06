#!/usr/bin/env python3
"""
search_issues 수정 테스트
"""

from tools.jira_tools import search_issues

# 테스트 JQL
test_jql = "project = BTVO AND labels = 'NCMS_BMT' AND fixVersion = 25.05"

print("=" * 70)
print("🧪 search_issues 수정 테스트")
print("=" * 70)
print(f"\nJQL: {test_jql}")
print("\n테스트 실행 중...")

try:
    # user_id는 실제 사용자 ID로 변경 필요
    # 여기서는 디버그 모드로 실행
    results = search_issues(
        user_id=1,
        jql=test_jql,
        max_results=10
    )

    print(f"\n✅ 결과: {len(results)}개 이슈")

    if results:
        print("\n처음 3개 이슈:")
        for i, issue in enumerate(results[:3], 1):
            print(f"  {i}. {issue.get('key')}: {issue.get('summary')}")
    else:
        print("\n⚠️ 조회된 이슈가 없습니다.")
        print("   - Jira 인증이 설정되어 있는지 확인하세요")
        print("   - JQL이 정확한지 확인하세요")

except Exception as e:
    print(f"\n❌ 테스트 실패: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
