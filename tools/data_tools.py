#!/usr/bin/env python3
"""
데이터 처리 관련 원자적 Tool 모음
LLM Agent가 조합하여 사용할 수 있는 단순한 데이터 처리 기능들
"""

from typing import List, Dict, Any, Optional, Callable


def find_issue_by_field(
    issues: List[Dict[str, Any]],
    field_name: str,
    field_value: Any,
    exact_match: bool = True
) -> Optional[Dict[str, Any]]:
    """
    이슈 리스트에서 특정 필드 값으로 이슈를 찾습니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 검색할 필드명
        field_value: 검색할 값
        exact_match: True면 정확히 일치, False면 부분 일치 (문자열인 경우)

    Returns:
        첫 번째로 매칭된 이슈 딕셔너리, 없으면 None

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "PROJ-456", "status": "완료"}
        ... ]
        >>> find_issue_by_field(issues, "key", "BTVO-123")
        {'key': 'BTVO-123', 'status': '신규'}

        >>> find_issue_by_field(issues, "status", "완료")
        {'key': 'PROJ-456', 'status': '완료'}

        >>> find_issue_by_field(issues, "key", "BTVO", exact_match=False)
        {'key': 'BTVO-123', 'status': '신규'}

        >>> find_issue_by_field(issues, "key", "NOTFOUND")
        None
    """
    if not issues or not isinstance(issues, list):
        return None

    if not field_name or not isinstance(field_name, str):
        return None

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if field_name not in issue:
            continue

        issue_value = issue[field_name]

        # 정확히 일치
        if exact_match:
            if issue_value == field_value:
                return issue
        # 부분 일치 (문자열인 경우)
        else:
            if isinstance(issue_value, str) and isinstance(field_value, str):
                if field_value.lower() in issue_value.lower():
                    return issue
            elif issue_value == field_value:
                return issue

    return None


def find_all_issues_by_field(
    issues: List[Dict[str, Any]],
    field_name: str,
    field_value: Any,
    exact_match: bool = True
) -> List[Dict[str, Any]]:
    """
    이슈 리스트에서 특정 필드 값으로 모든 이슈를 찾습니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 검색할 필드명
        field_value: 검색할 값
        exact_match: True면 정확히 일치, False면 부분 일치

    Returns:
        매칭된 이슈 딕셔너리 리스트

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "BTVO-124", "status": "신규"},
        ...     {"key": "PROJ-456", "status": "완료"}
        ... ]
        >>> find_all_issues_by_field(issues, "status", "신규")
        [{'key': 'BTVO-123', 'status': '신규'}, {'key': 'BTVO-124', 'status': '신규'}]

        >>> find_all_issues_by_field(issues, "key", "BTVO", exact_match=False)
        [{'key': 'BTVO-123', 'status': '신규'}, {'key': 'BTVO-124', 'status': '신규'}]
    """
    if not issues or not isinstance(issues, list):
        return []

    if not field_name or not isinstance(field_name, str):
        return []

    results = []

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if field_name not in issue:
            continue

        issue_value = issue[field_name]

        # 정확히 일치
        if exact_match:
            if issue_value == field_value:
                results.append(issue)
        # 부분 일치
        else:
            if isinstance(issue_value, str) and isinstance(field_value, str):
                if field_value.lower() in issue_value.lower():
                    results.append(issue)
            elif issue_value == field_value:
                results.append(issue)

    return results


def group_by_field(
    issues: List[Dict[str, Any]],
    field_name: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    이슈 리스트를 특정 필드 값으로 그룹화합니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 그룹화할 필드명

    Returns:
        필드 값을 키로, 해당 이슈 리스트를 값으로 하는 딕셔너리

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "status": "신규", "assignee": "김철수"},
        ...     {"key": "BTVO-124", "status": "완료", "assignee": "김철수"},
        ...     {"key": "PROJ-456", "status": "신규", "assignee": "박영희"}
        ... ]
        >>> group_by_field(issues, "status")
        {
            '신규': [{'key': 'BTVO-123', ...}, {'key': 'PROJ-456', ...}],
            '완료': [{'key': 'BTVO-124', ...}]
        }

        >>> group_by_field(issues, "assignee")
        {
            '김철수': [{'key': 'BTVO-123', ...}, {'key': 'BTVO-124', ...}],
            '박영희': [{'key': 'PROJ-456', ...}]
        }
    """
    if not issues or not isinstance(issues, list):
        return {}

    if not field_name or not isinstance(field_name, str):
        return {}

    groups = {}

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if field_name not in issue:
            # 필드가 없는 경우 "(없음)" 그룹으로
            key = "(없음)"
        else:
            field_value = issue[field_name]
            # None이나 빈 문자열도 "(없음)"으로 처리
            if field_value is None or field_value == "":
                key = "(없음)"
            else:
                key = str(field_value)

        if key not in groups:
            groups[key] = []

        groups[key].append(issue)

    return groups


def filter_issues(
    issues: List[Dict[str, Any]],
    filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
    **field_conditions
) -> List[Dict[str, Any]]:
    """
    이슈 리스트를 필터링합니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        filter_func: 커스텀 필터 함수 (issue를 받아 bool 반환)
        **field_conditions: 필드명=값 형태의 조건들

    Returns:
        필터링된 이슈 리스트

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "status": "신규", "priority": "High"},
        ...     {"key": "BTVO-124", "status": "완료", "priority": "Low"},
        ...     {"key": "PROJ-456", "status": "신규", "priority": "Medium"}
        ... ]
        >>> filter_issues(issues, status="신규")
        [{'key': 'BTVO-123', ...}, {'key': 'PROJ-456', ...}]

        >>> filter_issues(issues, status="신규", priority="High")
        [{'key': 'BTVO-123', ...}]

        >>> filter_issues(issues, filter_func=lambda x: x.get("priority") == "High")
        [{'key': 'BTVO-123', ...}]
    """
    if not issues or not isinstance(issues, list):
        return []

    results = issues.copy()

    # 필드 조건 필터링
    if field_conditions:
        for field_name, field_value in field_conditions.items():
            filtered = []
            for issue in results:
                if not isinstance(issue, dict):
                    continue

                issue_value = issue.get(field_name)

                # None이나 빈 값 처리
                if issue_value is None and field_value is None:
                    filtered.append(issue)
                    continue
                elif issue_value is None or field_value is None:
                    continue

                # 문자열인 경우 대소문자 구분 없이 비교
                if isinstance(issue_value, str) and isinstance(field_value, str):
                    # 양쪽 공백 제거 및 대소문자 무시
                    if issue_value.strip().lower() == field_value.strip().lower():
                        filtered.append(issue)
                # 리스트인 경우 (labels 같은 필드)
                elif isinstance(issue_value, list):
                    # field_value가 리스트에 포함되어 있는지 확인
                    if isinstance(field_value, str):
                        # 대소문자 구분 없이 리스트 내 검색
                        if any(str(v).strip().lower() == field_value.strip().lower() for v in issue_value):
                            filtered.append(issue)
                    elif field_value in issue_value:
                        filtered.append(issue)
                # 그 외 타입은 정확히 일치
                else:
                    if issue_value == field_value:
                        filtered.append(issue)

            results = filtered

    # 커스텀 함수 필터링
    if filter_func and callable(filter_func):
        results = [
            issue for issue in results
            if filter_func(issue)
        ]

    return results


def sort_issues(
    issues: List[Dict[str, Any]],
    field_name: str,
    reverse: bool = False
) -> List[Dict[str, Any]]:
    """
    이슈 리스트를 특정 필드로 정렬합니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 정렬 기준 필드명
        reverse: True면 내림차순, False면 오름차순

    Returns:
        정렬된 이슈 리스트 (원본은 변경하지 않음)

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "priority": "Medium"},
        ...     {"key": "BTVO-124", "priority": "High"},
        ...     {"key": "PROJ-456", "priority": "Low"}
        ... ]
        >>> sort_issues(issues, "priority")
        [{'key': 'BTVO-124', 'priority': 'High'}, ...]

        >>> sort_issues(issues, "key", reverse=True)
        [{'key': 'PROJ-456', ...}, {'key': 'BTVO-124', ...}, ...]
    """
    if not issues or not isinstance(issues, list):
        return []

    if not field_name or not isinstance(field_name, str):
        return issues.copy()

    try:
        # 필드가 없는 경우를 고려하여 정렬
        return sorted(
            issues,
            key=lambda x: x.get(field_name, ""),
            reverse=reverse
        )
    except (TypeError, KeyError):
        # 정렬 불가능한 경우 원본 반환
        return issues.copy()


def extract_field_values(
    issues: List[Dict[str, Any]],
    field_name: str,
    unique: bool = False
) -> List[Any]:
    """
    이슈 리스트에서 특정 필드의 값들을 추출합니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 추출할 필드명
        unique: True면 중복 제거

    Returns:
        필드 값 리스트

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "assignee": "김철수"},
        ...     {"key": "BTVO-124", "assignee": "김철수"},
        ...     {"key": "PROJ-456", "assignee": "박영희"}
        ... ]
        >>> extract_field_values(issues, "assignee")
        ['김철수', '김철수', '박영희']

        >>> extract_field_values(issues, "assignee", unique=True)
        ['김철수', '박영희']

        >>> extract_field_values(issues, "key")
        ['BTVO-123', 'BTVO-124', 'PROJ-456']
    """
    if not issues or not isinstance(issues, list):
        return []

    if not field_name or not isinstance(field_name, str):
        return []

    values = []

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if field_name in issue:
            value = issue[field_name]
            if value is not None:
                values.append(value)

    if unique:
        # 순서를 유지하면서 중복 제거
        seen = set()
        unique_values = []
        for value in values:
            # 해시 가능한 타입만 set에 추가
            try:
                if value not in seen:
                    seen.add(value)
                    unique_values.append(value)
            except TypeError:
                # 해시 불가능한 타입은 그냥 추가
                unique_values.append(value)
        return unique_values

    return values


def count_by_field(
    issues: List[Dict[str, Any]],
    field_name: str
) -> Dict[str, int]:
    """
    이슈 리스트에서 특정 필드 값별 개수를 집계합니다.

    Args:
        issues: 이슈 딕셔너리 리스트
        field_name: 집계할 필드명

    Returns:
        필드 값을 키로, 개수를 값으로 하는 딕셔너리

    Examples:
        >>> issues = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "BTVO-124", "status": "완료"},
        ...     {"key": "PROJ-456", "status": "신규"}
        ... ]
        >>> count_by_field(issues, "status")
        {'신규': 2, '완료': 1}

        >>> count_by_field(issues, "assignee")  # 필드가 없는 경우
        {'(없음)': 3}
    """
    if not issues or not isinstance(issues, list):
        return {}

    if not field_name or not isinstance(field_name, str):
        return {}

    counts = {}

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if field_name not in issue:
            key = "(없음)"
        else:
            field_value = issue[field_name]
            if field_value is None or field_value == "":
                key = "(없음)"
            else:
                key = str(field_value)

        counts[key] = counts.get(key, 0) + 1

    return counts
