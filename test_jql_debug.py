#!/usr/bin/env python3
"""
JQL 디버그 테스트 - 다양한 JQL 형식 테스트
"""

from tools.jira_query_tool import JiraQueryTool
import sys

def test_jql_variations(user_id: int):
    """다양한 JQL 형식 테스트"""

    # JiraQueryTool로 초기화 (user_id로부터 설정 로드)
    tool = JiraQueryTool(user_id=user_id)
    client = tool.client

    # 테스트할 JQL 변형들
    jql_tests = [
        # 원본 (작은따옴표)
        ("원본", "project = BTVO AND labels = 'NCMS_BMT' AND fixVersion = 25.05"),

        # 큰따옴표로 변경
        ("큰따옴표", 'project = BTVO AND labels = "NCMS_BMT" AND fixVersion = "25.05"'),

        # 따옴표 없음
        ("따옴표 없음", "project = BTVO AND labels = NCMS_BMT AND fixVersion = 25.05"),

        # 단계별 테스트
        ("프로젝트만", "project = BTVO"),
        ("프로젝트+라벨", 'project = BTVO AND labels = "NCMS_BMT"'),
        ("프로젝트+버전", 'project = BTVO AND fixVersion = "25.05"'),

        # fixVersions로 변경
        ("fixVersions", 'project = BTVO AND fixVersions = "25.05"'),

        # IN 연산자
        ("IN 연산자", 'project = BTVO AND labels in ("NCMS_BMT")'),
    ]

    print("=" * 80)
    print("🔍 JQL 디버그 테스트")
    print("=" * 80)

    for name, jql in jql_tests:
        print(f"\n【{name}】")
        print(f"JQL: {jql}")

        try:
            results = client.search_issues(jql=jql, max_results=5)
            print(f"✅ 결과: {len(results)}개")

            if results:
                print(f"   첫 번째 이슈: {results[0].get('key')}")

        except Exception as e:
            print(f"❌ 에러: {str(e)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test_jql_debug.py <user_id>")
        print("예: python test_jql_debug.py 1")
        sys.exit(1)

    user_id = int(sys.argv[1])
    test_jql_variations(user_id)
