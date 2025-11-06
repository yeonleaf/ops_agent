#!/usr/bin/env python3
"""
filter_issues 개선 사항 테스트
"""

from tools.data_tools import filter_issues

# 테스트 데이터
test_issues = [
    {
        "key": "BTVO-123",
        "summary": "로그인 버그",
        "status": "완료",
        "priority": "High",
        "labels": ["NCMS_BMT", "backend"]
    },
    {
        "key": "BTVO-124",
        "summary": "성능 개선",
        "status": "Done",  # 영어 상태
        "priority": "Medium",
        "labels": ["performance"]
    },
    {
        "key": "BTVO-125",
        "summary": "UI 수정",
        "status": "  완료  ",  # 공백 포함
        "priority": "Low",
        "labels": ["frontend", "NCMS_BMT"]
    },
    {
        "key": "BTVO-126",
        "summary": "신규 기능",
        "status": "진행중",
        "priority": "high",  # 소문자
        "labels": []
    },
    {
        "key": "BTVO-127",
        "summary": "문서 작성",
        "status": None,  # None 값
        "priority": "Low",
        "labels": ["documentation"]
    }
]

print("="*70)
print("🧪 filter_issues 개선 사항 테스트")
print("="*70)

# 테스트 1: 대소문자 구분 없는 매칭
print("\n[테스트 1] 대소문자 구분 없는 매칭")
print("-" * 70)
result = filter_issues(test_issues, status="완료")
print(f"filter_issues(status='완료'): {len(result)}개")
for issue in result:
    print(f"  - {issue['key']}: status='{issue['status']}'")

# 테스트 2: 공백이 있는 값 매칭
print("\n[테스트 2] 공백이 있는 값 매칭")
print("-" * 70)
result = filter_issues(test_issues, status="완료")
print(f"filter_issues(status='완료'): {len(result)}개 (공백 포함된 '  완료  ' 포함)")
for issue in result:
    print(f"  - {issue['key']}: status='{issue['status']}'")

# 테스트 3: priority 대소문자 테스트
print("\n[테스트 3] priority 대소문자 테스트")
print("-" * 70)
result = filter_issues(test_issues, priority="high")
print(f"filter_issues(priority='high'): {len(result)}개")
for issue in result:
    print(f"  - {issue['key']}: priority='{issue['priority']}'")

# 테스트 4: 리스트 필드 (labels) 테스트
print("\n[테스트 4] 리스트 필드 (labels) 테스트")
print("-" * 70)
result = filter_issues(test_issues, labels="NCMS_BMT")
print(f"filter_issues(labels='NCMS_BMT'): {len(result)}개")
for issue in result:
    print(f"  - {issue['key']}: labels={issue['labels']}")

# 테스트 5: 여러 조건 동시 적용
print("\n[테스트 5] 여러 조건 동시 적용")
print("-" * 70)
result = filter_issues(test_issues, status="완료", priority="High")
print(f"filter_issues(status='완료', priority='High'): {len(result)}개")
for issue in result:
    print(f"  - {issue['key']}: status='{issue['status']}', priority='{issue['priority']}'")

# 테스트 6: None 값 테스트
print("\n[테스트 6] None 값 테스트")
print("-" * 70)
result = filter_issues(test_issues, status=None)
print(f"filter_issues(status=None): {len(result)}개")
for issue in result:
    print(f"  - {issue['key']}: status={issue['status']}")

# 테스트 7: 존재하지 않는 값
print("\n[테스트 7] 존재하지 않는 값")
print("-" * 70)
result = filter_issues(test_issues, status="취소됨")
print(f"filter_issues(status='취소됨'): {len(result)}개 (예상: 0개)")

# 테스트 8: 빈 labels 검색
print("\n[테스트 8] 빈 labels 검색")
print("-" * 70)
result = filter_issues(test_issues, labels="nonexistent")
print(f"filter_issues(labels='nonexistent'): {len(result)}개 (예상: 0개)")

print("\n" + "="*70)
print("✅ 모든 테스트 완료!")
print("="*70)

# 실제 캐시된 이슈로 테스트
print("\n\n[추가] 실제 캐시 데이터로 테스트")
print("="*70)

try:
    from tools.cache_tools import get_cached_issues, get_cache_summary

    summary = get_cache_summary(user_id=1)
    print(f"캐시 요약: {summary['unique_issues']}개 이슈")

    if summary['unique_issues'] > 0:
        cached_issues = get_cached_issues(user_id=1)

        # 실제 status 값들 확인
        statuses = set(issue.get('status') for issue in cached_issues if issue.get('status'))
        print(f"\n실제 status 값들: {sorted(statuses)[:10]}")

        # 첫 번째 status 값으로 테스트
        if statuses:
            first_status = list(statuses)[0]
            result = filter_issues(cached_issues, status=first_status)
            print(f"\nfilter_issues(status='{first_status}'): {len(result)}개")

            # 대소문자 다르게 테스트
            result2 = filter_issues(cached_issues, status=first_status.lower())
            print(f"filter_issues(status='{first_status.lower()}'): {len(result2)}개 (대소문자 무시)")
    else:
        print("⚠️  캐시에 데이터가 없습니다.")

except Exception as e:
    print(f"⚠️  실제 데이터 테스트 실패: {e}")

print("\n")
