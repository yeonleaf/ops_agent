#!/usr/bin/env python3
"""
Tool Registry - Tool 등록 및 OpenAI Function Schema 관리
"""

from typing import Dict, List, Callable, Any, Optional
import json

from tools.jira_tools import search_issues, get_linked_issues
from tools.cache_tools import get_cached_issues, get_cache_summary
from tools.text_tools import extract_version, extract_pattern, extract_all_patterns, format_date
from tools.data_tools import (
    find_issue_by_field,
    find_all_issues_by_field,
    group_by_field,
    filter_issues,
    count_by_field
)
from tools.format_tools import format_as_table, format_as_list
from tools.system_tools import group_by_system, get_system_summary


class ToolRegistry:
    """
    사용 가능한 Tool들을 등록하고 OpenAI Function 형식으로 변환
    """

    def __init__(self, user_id: int, db_path: str = "tickets.db"):
        """
        Args:
            user_id: Jira API 호출에 사용할 사용자 ID
            db_path: 데이터베이스 경로
        """
        self.user_id = user_id
        self.db_path = db_path
        self.tools: Dict[str, Callable] = {}
        self.tool_schemas: List[Dict] = []
        self._register_tools()

    def _register_tools(self):
        """
        사용 가능한 Tool들을 등록
        """
        # Tool 등록 (함수명: 실제 함수)
        # Jira Tools - user_id와 db_path를 자동으로 전달
        self.tools = {
            "search_issues": lambda jql, max_results=100: search_issues(
                user_id=self.user_id,
                jql=jql,
                max_results=max_results,
                fields=None,
                db_path=self.db_path
            ),
            "get_linked_issues": lambda issue_key, link_type=None: get_linked_issues(
                user_id=self.user_id,
                issue_key=issue_key,
                link_type=link_type,
                db_path=self.db_path
            ),
            # Cache Tools
            "get_cached_issues": lambda: get_cached_issues(
                user_id=self.user_id,
                db_path=self.db_path
            ),
            "get_cache_summary": lambda: get_cache_summary(
                user_id=self.user_id,
                db_path=self.db_path
            ),
            # System Tools
            "group_by_system": group_by_system,
            "get_system_summary": get_system_summary,
            # Text Tools
            "extract_version": extract_version,
            "extract_pattern": lambda text, pattern, group=0: extract_pattern(text, pattern, group),
            "extract_all_patterns": extract_all_patterns,
            "format_date": lambda date_str, output_format="%Y-%m-%d": format_date(date_str, output_format),
            # Data Tools
            "find_issue_by_field": lambda issues, field_name, field_value, exact_match=True: find_issue_by_field(
                issues, field_name, field_value, exact_match
            ),
            "find_all_issues_by_field": lambda issues, field_name, field_value, exact_match=True: find_all_issues_by_field(
                issues, field_name, field_value, exact_match
            ),
            "group_by_field": group_by_field,
            "filter_issues": lambda issues, field_conditions=None, filter_func=None: filter_issues(
                issues,
                filter_func=filter_func,
                **(field_conditions or {})
            ),
            "count_by_field": count_by_field,
            # Format Tools
            "format_as_table": lambda data, columns, max_width=50: format_as_table(data, columns, max_width),
            "format_as_list": lambda data, template="{key}: {summary}", bullet="- ": format_as_list(data, template, bullet),
        }

        # OpenAI Function Schema 정의
        self.tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": "search_issues",
                    "description": "JQL 쿼리로 Jira 이슈를 검색합니다. 프로젝트, 라벨, 상태, 담당자 등으로 필터링할 수 있습니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jql": {
                                "type": "string",
                                "description": "Jira JQL 쿼리. 예시:\n- 'project = BTVO AND labels = \"NCMS_BMT\"'\n- 'status = \"완료\" AND created >= \"2025-10-01\"'\n- 'assignee = \"김철수\" AND priority = High'"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "최대 결과 수 (기본: 100)",
                                "default": 100
                            }
                        },
                        "required": ["jql"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_linked_issues",
                    "description": "특정 이슈에 연결된 다른 이슈들을 조회합니다. 블로킹, 관련 이슈 등을 찾을 때 사용합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "이슈 키 (예: BTVO-61032, PROJ-456)"
                            },
                            "link_type": {
                                "type": "string",
                                "description": "연결 타입 (선택사항). 예: 'Blocks', 'Relates', 'Duplicates'. 지정하지 않으면 모든 타입 반환",
                                "default": None
                            }
                        },
                        "required": ["issue_key"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cached_issues",
                    "description": "현재 캐시에 저장된 모든 Jira 이슈를 조회합니다. 새로운 API 호출 없이 이미 검색한 데이터만 사용합니다. Insight 추출이나 종합 분석 시 사용하세요.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cache_summary",
                    "description": "현재 캐시 상태의 요약 정보를 조회합니다. 캐시된 이슈 개수, JQL 쿼리 수 등을 확인할 때 사용하세요.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "group_by_system",
                    "description": "이슈들을 시스템별로 그룹핑합니다. labels 또는 summary에서 시스템명을 자동 추출하여 그룹화합니다. NCMS_BMT, BTV_Mobile 등으로 구분됩니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            }
                        },
                        "required": ["issues"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_system_summary",
                    "description": "시스템별 통계 요약을 생성합니다. 각 시스템의 이슈 개수, 완료율, 상태별 분포 등을 집계합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            }
                        },
                        "required": ["issues"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_version",
                    "description": "텍스트에서 버전 번호를 추출합니다. v1.2.3, RD5.4.3-8, 버전 10.5 등 다양한 형식 지원",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "버전 정보가 포함된 텍스트 (예: 이슈 제목, 설명)"
                            }
                        },
                        "required": ["text"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_pattern",
                    "description": "정규식 패턴으로 텍스트에서 원하는 부분을 추출합니다. 특정 문자열 패턴을 찾을 때 사용",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "원본 텍스트"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "정규식 패턴. 예:\n- r'Admin|User' (Admin 또는 User)\n- r'\\[([A-Z]+)\\]' (대괄호 안의 대문자)\n- r'\\d{4}-\\d{2}-\\d{2}' (날짜 형식)"
                            },
                            "group": {
                                "type": "integer",
                                "description": "추출할 그룹 번호 (0=전체, 1=첫 번째 그룹, ...)",
                                "default": 0
                            }
                        },
                        "required": ["text", "pattern"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_issue_by_field",
                    "description": "이슈 목록에서 특정 필드 값으로 이슈를 찾습니다. 첫 번째 매칭 이슈만 반환",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            },
                            "field_name": {
                                "type": "string",
                                "description": "검색할 필드명 (예: key, status, assignee, version)"
                            },
                            "field_value": {
                                "type": "string",
                                "description": "찾을 값"
                            },
                            "exact_match": {
                                "type": "boolean",
                                "description": "정확히 일치해야 하는지 여부 (False면 부분 일치)",
                                "default": True
                            }
                        },
                        "required": ["issues", "field_name", "field_value"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_all_issues_by_field",
                    "description": "이슈 목록에서 특정 필드 값으로 모든 이슈를 찾습니다. 매칭되는 모든 이슈 반환",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            },
                            "field_name": {
                                "type": "string",
                                "description": "검색할 필드명"
                            },
                            "field_value": {
                                "type": "string",
                                "description": "찾을 값"
                            },
                            "exact_match": {
                                "type": "boolean",
                                "description": "정확히 일치해야 하는지 여부",
                                "default": True
                            }
                        },
                        "required": ["issues", "field_name", "field_value"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "group_by_field",
                    "description": "이슈들을 특정 필드로 그룹핑합니다. 상태별, 담당자별 분류에 사용",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            },
                            "field_name": {
                                "type": "string",
                                "description": "그룹핑할 필드명 (예: status, assignee, priority)"
                            }
                        },
                        "required": ["issues", "field_name"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_issues",
                    "description": "조건에 맞는 이슈들만 필터링합니다. 여러 조건 동시 적용 가능",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록"
                            },
                            "field_conditions": {
                                "type": "object",
                                "description": "필터 조건 (필드명: 값). 예: {'status': '완료', 'priority': 'High'}",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["issues"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "count_by_field",
                    "description": "특정 필드 값별로 이슈 개수를 집계합니다. 통계 생성에 사용",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issues": {
                                "type": "string",
                                "description": "이슈 목록"
                            },
                            "field_name": {
                                "type": "string",
                                "description": "집계할 필드명"
                            }
                        },
                        "required": ["issues", "field_name"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "format_as_table",
                    "description": "데이터를 마크다운 표로 변환합니다. 최종 출력 생성에 사용",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "표시할 데이터 (이전 단계의 결과를 참조하려면 '$변수명' 형식 사용)"
                            },
                            "columns": {
                                "type": "array",
                                "description": "표시할 컬럼 목록. 예: ['key', 'summary', 'status', 'assignee']",
                                "items": {"type": "string"}
                            },
                            "max_width": {
                                "type": "integer",
                                "description": "셀의 최대 너비",
                                "default": 50
                            }
                        },
                        "required": ["data", "columns"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "format_as_list",
                    "description": "데이터를 불릿 리스트로 변환합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "표시할 데이터"
                            },
                            "template": {
                                "type": "string",
                                "description": "각 항목의 포맷 템플릿. 예: '{key}: {summary}'",
                                "default": "{key}: {summary}"
                            },
                            "bullet": {
                                "type": "string",
                                "description": "불릿 문자열",
                                "default": "- "
                            }
                        },
                        "required": ["data"],
                        "additionalProperties": False
                    }
                }
            }
        ]

    def get_tool(self, name: str) -> Optional[Callable]:
        """
        Tool 함수 반환

        Args:
            name: Tool 이름

        Returns:
            Tool 함수, 없으면 None
        """
        return self.tools.get(name)

    def get_schemas(self) -> List[Dict]:
        """
        OpenAI Function Schema 반환

        Returns:
            Function schema 리스트
        """
        return self.tool_schemas

    def list_tools(self) -> List[str]:
        """
        등록된 Tool 이름 목록 반환

        Returns:
            Tool 이름 리스트
        """
        return list(self.tools.keys())
