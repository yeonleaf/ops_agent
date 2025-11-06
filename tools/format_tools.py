#!/usr/bin/env python3
"""
데이터 포맷팅 관련 원자적 Tool 모음
LLM Agent가 조합하여 사용할 수 있는 단순한 출력 포맷팅 기능들
"""

from typing import List, Dict, Any, Optional


def format_as_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    max_width: int = 50,
    align: str = "left"
) -> str:
    """
    데이터를 마크다운 테이블 형식으로 변환합니다.

    Args:
        data: 테이블로 만들 딕셔너리 리스트
        columns: 출력할 컬럼 리스트 (None이면 첫 번째 항목의 모든 키)
        max_width: 셀의 최대 너비
        align: 정렬 방식 ("left", "center", "right")

    Returns:
        마크다운 테이블 문자열

    Examples:
        >>> data = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "PROJ-456", "status": "완료"}
        ... ]
        >>> print(format_as_table(data))
        | key | status |
        |-----|--------|
        | BTVO-123 | 신규 |
        | PROJ-456 | 완료 |

        >>> print(format_as_table(data, columns=["key"]))
        | key |
        |-----|
        | BTVO-123 |
        | PROJ-456 |
    """
    if not data or not isinstance(data, list):
        return "| (데이터 없음) |\n|--------------|"

    # 컬럼 결정
    if columns is None:
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            return "| (잘못된 데이터 형식) |\n|---------------------|"

    if not columns:
        return "| (컬럼 없음) |\n|-------------|"

    # 셀 값 가져오기 및 최대 너비 계산
    rows = []
    col_widths = {col: len(col) for col in columns}

    for item in data:
        if not isinstance(item, dict):
            continue

        row = {}
        for col in columns:
            value = item.get(col, "")
            # 값을 문자열로 변환
            if value is None:
                str_value = "-"
            elif isinstance(value, list):
                str_value = ", ".join(str(v) for v in value)
            else:
                str_value = str(value)

            # 최대 너비 적용
            if len(str_value) > max_width:
                str_value = str_value[:max_width - 3] + "..."

            row[col] = str_value
            col_widths[col] = max(col_widths[col], len(str_value))

        rows.append(row)

    if not rows:
        return "| (데이터 없음) |\n|--------------|"

    # 정렬 기호
    if align == "center":
        align_char = ":"
    elif align == "right":
        align_char = "-:"
    else:
        align_char = "-"

    # 테이블 생성
    lines = []

    # 헤더
    header = "| " + " | ".join(col.ljust(col_widths[col]) for col in columns) + " |"
    lines.append(header)

    # 구분선
    if align == "center":
        separator = "| " + " | ".join(":" + "-" * (col_widths[col] - 2) + ":" for col in columns) + " |"
    elif align == "right":
        separator = "| " + " | ".join("-" * (col_widths[col] - 1) + ":" for col in columns) + " |"
    else:
        separator = "| " + " | ".join("-" * col_widths[col] for col in columns) + " |"
    lines.append(separator)

    # 데이터 행
    for row in rows:
        line = "| " + " | ".join(row[col].ljust(col_widths[col]) for col in columns) + " |"
        lines.append(line)

    return "\n".join(lines)


def format_as_list(
    data: List[Dict[str, Any]],
    template: str = "{key}: {summary}",
    bullet: str = "- "
) -> str:
    """
    데이터를 리스트 형식으로 변환합니다.

    Args:
        data: 리스트로 만들 딕셔너리 리스트
        template: 각 항목의 포맷 템플릿 (예: "{key}: {summary}")
        bullet: 불릿 문자열

    Returns:
        포맷된 리스트 문자열

    Examples:
        >>> data = [
        ...     {"key": "BTVO-123", "summary": "작업1"},
        ...     {"key": "PROJ-456", "summary": "작업2"}
        ... ]
        >>> print(format_as_list(data))
        - BTVO-123: 작업1
        - PROJ-456: 작업2

        >>> print(format_as_list(data, template="[{key}] {summary}", bullet="• "))
        • [BTVO-123] 작업1
        • [PROJ-456] 작업2
    """
    if not data or not isinstance(data, list):
        return "(데이터 없음)"

    lines = []
    for item in data:
        if not isinstance(item, dict):
            continue

        try:
            # 템플릿에 데이터 적용
            line = template.format(**item)
            lines.append(f"{bullet}{line}")
        except (KeyError, ValueError):
            # 템플릿과 맞지 않는 경우 스킵
            continue

    if not lines:
        return "(포맷할 수 있는 데이터 없음)"

    return "\n".join(lines)


def format_as_json(
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False
) -> str:
    """
    데이터를 JSON 문자열로 변환합니다.

    Args:
        data: JSON으로 변환할 데이터
        indent: 들여쓰기 크기
        ensure_ascii: True면 ASCII만 사용 (한글 이스케이프)

    Returns:
        JSON 문자열

    Examples:
        >>> data = {"key": "BTVO-123", "status": "신규"}
        >>> print(format_as_json(data))
        {
          "key": "BTVO-123",
          "status": "신규"
        }

        >>> print(format_as_json([1, 2, 3]))
        [
          1,
          2,
          3
        ]
    """
    import json

    try:
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError):
        return '{"error": "JSON 변환 실패"}'


def format_as_csv(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    delimiter: str = ",",
    include_header: bool = True
) -> str:
    """
    데이터를 CSV 문자열로 변환합니다.

    Args:
        data: CSV로 만들 딕셔너리 리스트
        columns: 출력할 컬럼 리스트
        delimiter: 구분자
        include_header: 헤더 포함 여부

    Returns:
        CSV 문자열

    Examples:
        >>> data = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "PROJ-456", "status": "완료"}
        ... ]
        >>> print(format_as_csv(data))
        key,status
        BTVO-123,신규
        PROJ-456,완료

        >>> print(format_as_csv(data, delimiter="|"))
        key|status
        BTVO-123|신규
        PROJ-456|완료
    """
    if not data or not isinstance(data, list):
        return "(데이터 없음)"

    # 컬럼 결정
    if columns is None:
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            return "(잘못된 데이터 형식)"

    if not columns:
        return "(컬럼 없음)"

    lines = []

    # 헤더
    if include_header:
        lines.append(delimiter.join(columns))

    # 데이터 행
    for item in data:
        if not isinstance(item, dict):
            continue

        values = []
        for col in columns:
            value = item.get(col, "")
            if value is None:
                str_value = ""
            elif isinstance(value, list):
                str_value = ";".join(str(v) for v in value)
            else:
                str_value = str(value)

            # CSV 이스케이프 (쉼표, 따옴표 등)
            if delimiter in str_value or '"' in str_value or '\n' in str_value:
                str_value = '"' + str_value.replace('"', '""') + '"'

            values.append(str_value)

        lines.append(delimiter.join(values))

    return "\n".join(lines)


def format_as_summary(
    data: List[Dict[str, Any]],
    group_by: Optional[str] = None
) -> str:
    """
    데이터의 요약 정보를 생성합니다.

    Args:
        data: 요약할 딕셔너리 리스트
        group_by: 그룹화할 필드명

    Returns:
        요약 정보 문자열

    Examples:
        >>> data = [
        ...     {"key": "BTVO-123", "status": "신규"},
        ...     {"key": "BTVO-124", "status": "완료"},
        ...     {"key": "PROJ-456", "status": "신규"}
        ... ]
        >>> print(format_as_summary(data, group_by="status"))
        총 3개 이슈

        status별 분포:
        - 신규: 2개 (66.7%)
        - 완료: 1개 (33.3%)
    """
    if not data or not isinstance(data, list):
        return "데이터 없음"

    total = len(data)
    lines = [f"총 {total}개 이슈"]

    if group_by and isinstance(group_by, str):
        # 그룹별 집계
        groups = {}
        for item in data:
            if not isinstance(item, dict):
                continue

            if group_by not in item:
                key = "(없음)"
            else:
                value = item[group_by]
                key = str(value) if value is not None else "(없음)"

            groups[key] = groups.get(key, 0) + 1

        if groups:
            lines.append("")
            lines.append(f"{group_by}별 분포:")
            for key, count in sorted(groups.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total) * 100
                lines.append(f"- {key}: {count}개 ({percentage:.1f}%)")

    return "\n".join(lines)


def format_key_value(
    data: Dict[str, Any],
    indent: int = 0,
    separator: str = ": "
) -> str:
    """
    딕셔너리를 Key-Value 형식으로 변환합니다.

    Args:
        data: 딕셔너리
        indent: 들여쓰기 수준
        separator: 키-값 구분자

    Returns:
        Key-Value 문자열

    Examples:
        >>> data = {"key": "BTVO-123", "status": "신규", "priority": "High"}
        >>> print(format_key_value(data))
        key: BTVO-123
        status: 신규
        priority: High

        >>> print(format_key_value(data, indent=2, separator=" = "))
          key = BTVO-123
          status = 신규
          priority = High
    """
    if not data or not isinstance(data, dict):
        return "(데이터 없음)"

    indent_str = " " * indent
    lines = []

    for key, value in data.items():
        if value is None:
            str_value = "(없음)"
        elif isinstance(value, list):
            str_value = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            # 중첩 딕셔너리는 재귀 호출
            lines.append(f"{indent_str}{key}:")
            lines.append(format_key_value(value, indent + 2, separator))
            continue
        else:
            str_value = str(value)

        lines.append(f"{indent_str}{key}{separator}{str_value}")

    return "\n".join(lines)


def wrap_text(
    text: str,
    width: int = 80,
    indent: int = 0
) -> str:
    """
    텍스트를 지정된 너비로 줄바꿈합니다.

    Args:
        text: 줄바꿈할 텍스트
        width: 한 줄의 최대 너비
        indent: 들여쓰기 수준

    Returns:
        줄바꿈된 텍스트

    Examples:
        >>> text = "This is a very long text that needs to be wrapped"
        >>> print(wrap_text(text, width=20))
        This is a very long
        text that needs to
        be wrapped

        >>> print(wrap_text(text, width=20, indent=2))
          This is a very
          long text that
          needs to be
          wrapped
    """
    if not text or not isinstance(text, str):
        return ""

    import textwrap

    indent_str = " " * indent
    wrapped = textwrap.fill(
        text,
        width=width - indent,
        initial_indent=indent_str,
        subsequent_indent=indent_str
    )

    return wrapped
