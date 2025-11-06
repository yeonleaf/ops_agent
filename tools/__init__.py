#!/usr/bin/env python3
"""
LLM Agent를 위한 원자적 Tool 모음

이 모듈은 LLM Agent가 조합하여 사용할 수 있는 단순하고 독립적인 기능들을 제공합니다.
각 Tool은 복잡한 비즈니스 로직 없이 원자적 기능만 제공하며, LLM이 자유롭게 조합할 수 있습니다.
"""

# Text Tools
from .text_tools import (
    extract_version,
    extract_pattern,
    extract_all_patterns,
    format_date,
    clean_whitespace,
    truncate_text,
)

# Data Tools
from .data_tools import (
    find_issue_by_field,
    find_all_issues_by_field,
    group_by_field,
    filter_issues,
    sort_issues,
    extract_field_values,
    count_by_field,
)

# Jira Tools
from .jira_tools import (
    search_issues,
    get_linked_issues,
    get_issue_detail,
    get_issue_comments,
    get_issue_history,
)

# Format Tools
from .format_tools import (
    format_as_table,
    format_as_list,
    format_as_json,
    format_as_csv,
    format_as_summary,
    format_key_value,
    wrap_text,
)

__all__ = [
    # Text Tools
    "extract_version",
    "extract_pattern",
    "extract_all_patterns",
    "format_date",
    "clean_whitespace",
    "truncate_text",
    # Data Tools
    "find_issue_by_field",
    "find_all_issues_by_field",
    "group_by_field",
    "filter_issues",
    "sort_issues",
    "extract_field_values",
    "count_by_field",
    # Jira Tools
    "search_issues",
    "get_linked_issues",
    "get_issue_detail",
    "get_issue_comments",
    "get_issue_history",
    # Format Tools
    "format_as_table",
    "format_as_list",
    "format_as_json",
    "format_as_csv",
    "format_as_summary",
    "format_key_value",
    "wrap_text",
]

__version__ = "1.0.0"
