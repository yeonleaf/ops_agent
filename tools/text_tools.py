#!/usr/bin/env python3
"""
텍스트 처리 관련 원자적 Tool 모음
LLM Agent가 조합하여 사용할 수 있는 단순한 텍스트 처리 기능들
"""

import re
from typing import List, Optional
from datetime import datetime


def extract_version(text: str) -> Optional[str]:
    """
    텍스트에서 버전 번호를 추출합니다.

    패턴 예시:
    - v1.2.3
    - V1.2
    - 1.2.3
    - version 1.2

    Args:
        text: 버전 정보를 포함한 텍스트

    Returns:
        추출된 버전 번호 (문자열), 찾지 못하면 None

    Examples:
        >>> extract_version("Release v1.2.3")
        '1.2.3'

        >>> extract_version("버전 2.0 배포")
        '2.0'

        >>> extract_version("no version here")
        None

        >>> extract_version("[NCMS] v10.5.2 배포")
        '10.5.2'
    """
    if not text or not isinstance(text, str):
        return None

    # 버전 패턴들 (우선순위 순서)
    patterns = [
        r'[vV](\d+\.\d+(?:\.\d+)?)',  # v1.2.3 or v1.2
        r'버전\s*(\d+\.\d+(?:\.\d+)?)',  # 버전 1.2.3
        r'version\s*(\d+\.\d+(?:\.\d+)?)',  # version 1.2
        r'\b(\d+\.\d+\.\d+)\b',  # standalone 1.2.3
        r'\b(\d+\.\d+)\b',  # standalone 1.2
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_pattern(text: str, pattern: str, group: int = 0) -> Optional[str]:
    """
    정규표현식 패턴으로 텍스트에서 원하는 부분을 추출합니다.

    Args:
        text: 검색 대상 텍스트
        pattern: 정규표현식 패턴
        group: 추출할 그룹 번호 (0=전체 매치, 1=첫 번째 그룹, ...)

    Returns:
        추출된 문자열, 찾지 못하면 None

    Examples:
        >>> extract_pattern("BTVO-61032", r"[A-Z]+-\\d+")
        'BTVO-61032'

        >>> extract_pattern("[NCMS] 작업 완료", r"\\[([A-Z]+)\\]", group=1)
        'NCMS'

        >>> extract_pattern("priority: High", r"priority:\\s*(\\w+)", group=1)
        'High'

        >>> extract_pattern("no match here", r"\\d{4}")
        None
    """
    if not text or not isinstance(text, str):
        return None

    if not pattern or not isinstance(pattern, str):
        return None

    try:
        match = re.search(pattern, text)
        if match:
            return match.group(group)
        return None
    except (re.error, IndexError) as e:
        # 잘못된 정규표현식이거나 그룹 번호가 범위를 벗어남
        return None


def format_date(
    date_str: str,
    output_format: str = "%Y-%m-%d",
    input_formats: Optional[List[str]] = None
) -> Optional[str]:
    """
    날짜 문자열을 원하는 형식으로 변환합니다.

    Args:
        date_str: 입력 날짜 문자열
        output_format: 출력 날짜 형식 (strftime 포맷)
        input_formats: 시도할 입력 형식 리스트 (None이면 기본 형식들 사용)

    Returns:
        변환된 날짜 문자열, 변환 실패 시 None

    Examples:
        >>> format_date("2025-10-15T10:30:00")
        '2025-10-15'

        >>> format_date("2025-10-15T10:30:00", "%Y년 %m월 %d일")
        '2025년 10월 15일'

        >>> format_date("15/10/2025", input_formats=["%d/%m/%Y"])
        '2025-10-15'

        >>> format_date("2025-10-15", "%m/%d")
        '10/15'

        >>> format_date("invalid date")
        None
    """
    if not date_str or not isinstance(date_str, str):
        return None

    # 기본 입력 형식들
    if input_formats is None:
        input_formats = [
            "%Y-%m-%dT%H:%M:%S",  # ISO format with time
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
            "%Y-%m-%d %H:%M:%S",  # Standard datetime
            "%Y-%m-%d",  # Date only
            "%Y/%m/%d",  # Slash separated
            "%d-%m-%Y",  # European format
            "%d/%m/%Y",  # European with slash
            "%m-%d-%Y",  # US format
            "%m/%d/%Y",  # US with slash
        ]

    # 각 형식으로 파싱 시도
    for input_fmt in input_formats:
        try:
            dt = datetime.strptime(date_str, input_fmt)
            return dt.strftime(output_format)
        except ValueError:
            continue

    return None


def extract_all_patterns(text: str, pattern: str) -> List[str]:
    """
    정규표현식 패턴으로 텍스트에서 모든 매칭을 추출합니다.

    Args:
        text: 검색 대상 텍스트
        pattern: 정규표현식 패턴

    Returns:
        추출된 문자열 리스트 (매칭이 없으면 빈 리스트)

    Examples:
        >>> extract_all_patterns("BTVO-123, PROJ-456", r"[A-Z]+-\\d+")
        ['BTVO-123', 'PROJ-456']

        >>> extract_all_patterns("v1.2, v2.0, v3.1", r"v(\\d+\\.\\d+)")
        ['1.2', '2.0', '3.1']

        >>> extract_all_patterns("no match", r"\\d{4}")
        []
    """
    if not text or not isinstance(text, str):
        return []

    if not pattern or not isinstance(pattern, str):
        return []

    try:
        # 그룹이 있으면 그룹 내용만, 없으면 전체 매치
        matches = re.findall(pattern, text)
        return matches if matches else []
    except re.error:
        return []


def clean_whitespace(text: str) -> str:
    """
    텍스트의 불필요한 공백을 정리합니다.

    Args:
        text: 정리할 텍스트

    Returns:
        공백이 정리된 텍스트

    Examples:
        >>> clean_whitespace("  hello   world  ")
        'hello world'

        >>> clean_whitespace("multiple\\n\\n\\nlines")
        'multiple lines'

        >>> clean_whitespace("  ")
        ''
    """
    if not text or not isinstance(text, str):
        return ""

    # 여러 공백을 하나로, 앞뒤 공백 제거
    return ' '.join(text.split())


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    텍스트를 지정된 길이로 자릅니다.

    Args:
        text: 자를 텍스트
        max_length: 최대 길이
        suffix: 잘렸을 때 추가할 접미사

    Returns:
        잘린 텍스트

    Examples:
        >>> truncate_text("This is a long text", 10)
        'This is...'

        >>> truncate_text("Short", 10)
        'Short'

        >>> truncate_text("Long text here", 8, "…")
        'Long tex…'
    """
    if not text or not isinstance(text, str):
        return ""

    if len(text) <= max_length:
        return text

    # suffix를 포함한 최종 길이가 max_length가 되도록 자르기
    cut_length = max_length - len(suffix)
    if cut_length <= 0:
        return suffix[:max_length]

    return text[:cut_length] + suffix
