#!/usr/bin/env python3
"""
시스템 관련 Tool 모음
이슈에서 시스템명을 추출하고 그룹핑하는 기능들
"""

from typing import List, Dict, Any
import re
from collections import defaultdict


def extract_system_name(issue: Dict[str, Any]) -> str:
    """
    단일 이슈에서 시스템명 추출

    Args:
        issue: 이슈 딕셔너리

    Returns:
        시스템명 (없으면 "기타")

    Examples:
        >>> extract_system_name({"labels": ["NCMS_BMT"]})
        'NCMS_BMT'

        >>> extract_system_name({"summary": "[BTV] 로그인 버그"})
        'BTV'

        >>> extract_system_name({"summary": "일반 작업"})
        '기타'
    """
    # 1. labels 필드에서 시스템명 패턴 찾기
    labels = issue.get("labels", [])
    if labels and isinstance(labels, list):
        for label in labels:
            label_str = str(label)
            # NCMS_BMT, BTV_Mobile 같은 패턴
            if "_" in label_str:
                # 언더스코어 기준으로 시스템 그룹 추출
                system_group = label_str.split("_")[0]
                return label_str  # 전체 label 반환 (NCMS_BMT, NCMS_Admin 구분)
            # 단순 시스템명 (NCMS, BTV 등)
            elif len(label_str) >= 3 and label_str.isupper():
                return label_str

    # 2. summary 필드에서 시스템명 패턴 찾기
    summary = issue.get("summary", "")
    if summary and isinstance(summary, str):
        # [시스템명] 패턴
        bracket_match = re.search(r'\[([A-Z_]+)\]', summary)
        if bracket_match:
            return bracket_match.group(1)

        # 시스템명: 패턴
        colon_match = re.search(r'^([A-Z_]+):', summary)
        if colon_match:
            return colon_match.group(1)

        # 시스템명 - 패턴
        dash_match = re.search(r'^([A-Z_]+)\s*-', summary)
        if dash_match:
            return dash_match.group(1)

    return "기타"


def group_by_system(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    이슈 리스트를 시스템별로 그룹핑

    Args:
        issues: 이슈 딕셔너리 리스트

    Returns:
        시스템명을 키로, 해당 이슈 리스트를 값으로 하는 딕셔너리

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "labels": ["NCMS_BMT"]},
        ...     {"key": "BTVO-124", "labels": ["NCMS_Admin"]},
        ...     {"key": "BTVO-125", "labels": ["NCMS_BMT"]}
        ... ]
        >>> group_by_system(issues)
        {
            'NCMS_BMT': [{'key': 'BTVO-123', ...}, {'key': 'BTVO-125', ...}],
            'NCMS_Admin': [{'key': 'BTVO-124', ...}]
        }
    """
    if not issues or not isinstance(issues, list):
        return {}

    groups = defaultdict(list)

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        system_name = extract_system_name(issue)
        groups[system_name].append(issue)

    # defaultdict를 일반 dict로 변환
    return dict(groups)


def get_system_summary(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    시스템별 통계 요약 생성

    Args:
        issues: 이슈 딕셔너리 리스트

    Returns:
        시스템별 통계 딕셔너리
        {
            "total_systems": int,
            "systems": {
                "NCMS_BMT": {
                    "count": 45,
                    "completed": 30,
                    "completion_rate": "66.7%",
                    "statuses": {"완료": 30, "진행중": 10, "대기": 5}
                },
                ...
            },
            "largest_system": "NCMS_BMT",
            "smallest_system": "기타"
        }

    Examples:
        >>> issues = [
        ...     {"labels": ["NCMS_BMT"], "status": "완료"},
        ...     {"labels": ["NCMS_BMT"], "status": "진행중"},
        ...     {"labels": ["NCMS_Admin"], "status": "완료"}
        ... ]
        >>> summary = get_system_summary(issues)
        >>> summary["total_systems"]
        2
        >>> summary["systems"]["NCMS_BMT"]["count"]
        2
    """
    if not issues or not isinstance(issues, list):
        return {
            "total_systems": 0,
            "systems": {},
            "largest_system": None,
            "smallest_system": None
        }

    # 시스템별 그룹핑
    groups = group_by_system(issues)

    # 각 시스템별 통계 계산
    systems_stats = {}

    for system_name, system_issues in groups.items():
        # 상태별 카운트
        status_counts = {}
        completed_count = 0

        for issue in system_issues:
            status = issue.get("status", "알 수 없음")
            status_counts[status] = status_counts.get(status, 0) + 1

            # 완료 상태 체크 (Done, 완료, Closed 등)
            if status and isinstance(status, str):
                if status.lower() in ["done", "완료", "closed", "resolved"]:
                    completed_count += 1

        # 완료율 계산
        total_count = len(system_issues)
        completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0

        systems_stats[system_name] = {
            "count": total_count,
            "completed": completed_count,
            "completion_rate": f"{completion_rate:.1f}%",
            "statuses": status_counts
        }

    # 가장 큰/작은 시스템 찾기
    if systems_stats:
        largest = max(systems_stats.items(), key=lambda x: x[1]["count"])
        smallest = min(systems_stats.items(), key=lambda x: x[1]["count"])
        largest_system = largest[0]
        smallest_system = smallest[0]
    else:
        largest_system = None
        smallest_system = None

    return {
        "total_systems": len(systems_stats),
        "systems": systems_stats,
        "largest_system": largest_system,
        "smallest_system": smallest_system
    }


if __name__ == "__main__":
    # 간단한 테스트
    print("="*70)
    print("🧪 System Tools 모듈 테스트")
    print("="*70)

    test_issues = [
        {"key": "BTVO-123", "labels": ["NCMS_BMT"], "status": "완료", "summary": "BMT 버그 수정"},
        {"key": "BTVO-124", "labels": ["NCMS_BMT"], "status": "진행중", "summary": "BMT 성능 개선"},
        {"key": "BTVO-125", "labels": ["NCMS_Admin"], "status": "완료", "summary": "Admin UI 개선"},
        {"key": "BTVO-126", "labels": ["BTV_Mobile"], "status": "완료", "summary": "모바일 버그"},
        {"key": "BTVO-127", "labels": [], "summary": "[NCMS] 일반 작업", "status": "대기"},
        {"key": "BTVO-128", "labels": [], "summary": "일반 작업", "status": "완료"}
    ]

    print("\n[1] 시스템명 추출 테스트")
    print("-" * 70)
    for issue in test_issues:
        system = extract_system_name(issue)
        print(f"  {issue['key']}: {system} (labels={issue.get('labels')}, summary={issue.get('summary')[:30]}...)")

    print("\n[2] 시스템별 그룹핑 테스트")
    print("-" * 70)
    groups = group_by_system(test_issues)
    for system_name, system_issues in groups.items():
        print(f"  {system_name}: {len(system_issues)}개 이슈")
        for issue in system_issues:
            print(f"    - {issue['key']}")

    print("\n[3] 시스템별 통계 테스트")
    print("-" * 70)
    summary = get_system_summary(test_issues)
    print(f"  총 시스템 수: {summary['total_systems']}")
    print(f"  가장 큰 시스템: {summary['largest_system']}")
    print(f"  가장 작은 시스템: {summary['smallest_system']}")
    print("\n  시스템별 상세:")
    for system_name, stats in summary["systems"].items():
        print(f"    {system_name}:")
        print(f"      - 총 이슈: {stats['count']}개")
        print(f"      - 완료: {stats['completed']}개")
        print(f"      - 완료율: {stats['completion_rate']}")
        print(f"      - 상태: {stats['statuses']}")

    print("\n" + "="*70)
    print("✅ 테스트 완료")
    print("="*70)
