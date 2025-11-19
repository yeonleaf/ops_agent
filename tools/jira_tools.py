#!/usr/bin/env python3
"""
Jira 연동 관련 원자적 Tool 모음
LLM Agent가 조합하여 사용할 수 있는 단순한 Jira API 호출 기능들
"""

from typing import List, Dict, Any, Optional
from tools.jira_query_tool import JiraQueryTool


def search_issues(
    user_id: int,
    jql: str,
    max_results: int = 50,
    fields: Optional[List[str]] = None,
    db_path: str = "tickets.db"
) -> List[Dict[str, Any]]:
    """
    JQL 쿼리로 Jira 이슈를 검색합니다.

    Args:
        user_id: 로그인 사용자 ID (Jira 인증용)
        jql: Jira Query Language 쿼리 문자열
        max_results: 최대 결과 개수
        fields: 가져올 필드 리스트 (None이면 기본 필드들)
        db_path: 데이터베이스 파일 경로

    Returns:
        이슈 딕셔너리 리스트

    Examples:
        >>> search_issues(1, "project = BTVO AND status = '신규'")
        [
            {
                "key": "BTVO-123",
                "summary": "작업 제목",
                "status": "신규",
                ...
            },
            ...
        ]

        >>> search_issues(1, "assignee = currentUser()", max_results=10)
        [...]

        >>> search_issues(
        ...     1,
        ...     "project = PROJ",
        ...     fields=["key", "summary", "status"]
        ... )
        [...]
    """
    try:
        # JiraQueryTool로 초기화 (user_id로부터 설정 로드)
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client

        # 기본 필드 설정
        if fields is None:
            fields = [
                "key",
                "summary",
                "status",
                "assignee",
                "reporter",
                "created",
                "updated",
                "priority",
                "labels",
                "components",
                "issuetype",
                "fixVersions",
            ]

        # Jira API 호출
        # JiraClient.search_issues는 fields를 리스트로 받고, 이슈 리스트를 직접 반환함
        issues_raw = client.search_issues(
            jql=jql,
            max_results=max_results,
            fields=fields
        )

        if not issues_raw:
            return []

        # 이슈 변환
        issues = []
        for issue_raw in issues_raw:
            issue = _parse_issue(issue_raw)
            if issue:
                issues.append(issue)

        return issues

    except Exception as e:
        # 에러 발생 시 로그 출력
        print(f"❌ search_issues 에러: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_linked_issues(
    user_id: int,
    issue_key: str,
    link_type: Optional[str] = None,
    db_path: str = "tickets.db"
) -> List[Dict[str, Any]]:
    """
    특정 이슈의 연결된 이슈들을 가져옵니다.

    Args:
        user_id: 로그인 사용자 ID
        issue_key: 이슈 키 (예: BTVO-123)
        link_type: 연결 타입 (None이면 모든 타입, 예: "Blocks", "Relates")
        db_path: 데이터베이스 파일 경로

    Returns:
        연결된 이슈 딕셔너리 리스트 (각 이슈에 link_type 필드 추가)

    Examples:
        >>> get_linked_issues(1, "BTVO-123")
        [
            {
                "key": "BTVO-124",
                "summary": "연결된 이슈",
                "link_type": "Blocks",
                ...
            },
            ...
        ]

        >>> get_linked_issues(1, "BTVO-123", link_type="Relates")
        [...]
    """
    try:
        # JiraQueryTool로 초기화
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client

        # 이슈 상세 정보 가져오기 (issuelinks 포함)
        issue_data = client.get_issue(issue_key)

        if not issue_data or "fields" not in issue_data:
            return []

        fields = issue_data["fields"]
        issue_links = fields.get("issuelinks", [])

        if not issue_links:
            return []

        # 연결된 이슈 파싱
        linked_issues = []

        for link in issue_links:
            link_type_info = link.get("type", {})
            current_link_type = link_type_info.get("name", "Unknown")

            # link_type 필터링
            if link_type and link_type != current_link_type:
                continue

            # outward link (이 이슈가 다른 이슈를 가리킴)
            if "outwardIssue" in link:
                outward = link["outwardIssue"]
                issue = _parse_issue(outward)
                if issue:
                    issue["link_type"] = current_link_type
                    issue["link_direction"] = "outward"
                    linked_issues.append(issue)

            # inward link (다른 이슈가 이 이슈를 가리킴)
            if "inwardIssue" in link:
                inward = link["inwardIssue"]
                issue = _parse_issue(inward)
                if issue:
                    issue["link_type"] = current_link_type
                    issue["link_direction"] = "inward"
                    linked_issues.append(issue)

        return linked_issues

    except Exception as e:
        return []


def get_issue_detail(
    user_id: int,
    issue_key: str,
    db_path: str = "tickets.db"
) -> Optional[Dict[str, Any]]:
    """
    특정 이슈의 상세 정보를 가져옵니다.

    Args:
        user_id: 로그인 사용자 ID
        issue_key: 이슈 키 (예: BTVO-123)
        db_path: 데이터베이스 파일 경로

    Returns:
        이슈 상세 정보 딕셔너리, 없으면 None

    Examples:
        >>> get_issue_detail(1, "BTVO-123")
        {
            "key": "BTVO-123",
            "summary": "작업 제목",
            "description": "상세 설명...",
            "status": "신규",
            ...
        }

        >>> get_issue_detail(1, "INVALID-999")
        None
    """
    try:
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client
        issue_data = client.get_issue(issue_key)

        if not issue_data:
            return None

        return _parse_issue(issue_data)

    except Exception:
        return None


def _parse_issue(issue_raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Jira API 원시 응답을 간단한 이슈 딕셔너리로 변환합니다.

    Args:
        issue_raw: Jira API 원시 응답

    Returns:
        파싱된 이슈 딕셔너리
    """
    try:
        # 이슈 키
        key = issue_raw.get("key", "")

        # 필드 추출
        fields = issue_raw.get("fields", {})

        # 기본 정보
        issue = {
            "key": key,
            "summary": fields.get("summary", ""),
            "description": fields.get("description", ""),
        }

        # 상태
        status = fields.get("status")
        if status:
            issue["status"] = status.get("name", "")

        # 담당자
        assignee = fields.get("assignee")
        if assignee:
            issue["assignee"] = assignee.get("displayName", "")
        else:
            issue["assignee"] = None

        # 보고자
        reporter = fields.get("reporter")
        if reporter:
            issue["reporter"] = reporter.get("displayName", "")
        else:
            issue["reporter"] = None

        # 날짜
        issue["created"] = fields.get("created", "")
        issue["updated"] = fields.get("updated", "")

        # 우선순위
        priority = fields.get("priority")
        if priority:
            issue["priority"] = priority.get("name", "")
        else:
            issue["priority"] = None

        # 라벨
        issue["labels"] = fields.get("labels", [])

        # 컴포넌트
        components = fields.get("components", [])
        issue["components"] = [c.get("name", "") for c in components]

        # 이슈 타입
        issuetype = fields.get("issuetype")
        if issuetype:
            issue["issuetype"] = issuetype.get("name", "")
        else:
            issue["issuetype"] = None

        # 수정 버전
        fix_versions = fields.get("fixVersions", [])
        issue["fixVersions"] = [v.get("name", "") for v in fix_versions]

        # 커스텀 필드 추출 (customfield_* 형식의 모든 필드)
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_"):
                # 커스텀 필드를 그대로 추가 (복잡한 객체는 문자열로 변환)
                if isinstance(field_value, (dict, list)):
                    # 딕셔너리나 리스트는 JSON 직렬화 가능한 형태로 유지
                    issue[field_key] = field_value
                else:
                    # 문자열이나 숫자 등은 그대로 저장
                    issue[field_key] = field_value

        return issue

    except Exception:
        return None


def get_issue_comments(
    user_id: int,
    issue_key: str,
    max_results: int = 50,
    db_path: str = "tickets.db"
) -> List[Dict[str, Any]]:
    """
    특정 이슈의 댓글을 가져옵니다.

    Args:
        user_id: 로그인 사용자 ID
        issue_key: 이슈 키
        max_results: 최대 결과 개수
        db_path: 데이터베이스 파일 경로

    Returns:
        댓글 딕셔너리 리스트

    Examples:
        >>> get_issue_comments(1, "BTVO-123")
        [
            {
                "author": "김철수",
                "body": "댓글 내용",
                "created": "2025-10-15T10:30:00",
                ...
            },
            ...
        ]
    """
    try:
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client
        issue_data = client.get_issue(issue_key)

        if not issue_data or "fields" not in issue_data:
            return []

        comment_data = issue_data["fields"].get("comment", {})
        comments_raw = comment_data.get("comments", [])

        if not comments_raw:
            return []

        # 댓글 파싱
        comments = []
        for comment_raw in comments_raw[:max_results]:
            author = comment_raw.get("author", {})
            comment = {
                "author": author.get("displayName", "Unknown"),
                "body": comment_raw.get("body", ""),
                "created": comment_raw.get("created", ""),
                "updated": comment_raw.get("updated", ""),
            }
            comments.append(comment)

        return comments

    except Exception:
        return []


def get_issue_history(
    user_id: int,
    issue_key: str,
    max_results: int = 50,
    db_path: str = "tickets.db"
) -> List[Dict[str, Any]]:
    """
    특정 이슈의 변경 이력을 가져옵니다.

    Args:
        user_id: 로그인 사용자 ID
        issue_key: 이슈 키
        max_results: 최대 결과 개수
        db_path: 데이터베이스 파일 경로

    Returns:
        변경 이력 딕셔너리 리스트

    Examples:
        >>> get_issue_history(1, "BTVO-123")
        [
            {
                "author": "김철수",
                "created": "2025-10-15T10:30:00",
                "items": [
                    {
                        "field": "status",
                        "fromString": "신규",
                        "toString": "진행중"
                    }
                ]
            },
            ...
        ]
    """
    try:
        tool = JiraQueryTool(user_id=user_id, db_path=db_path)
        client = tool.client
        issue_data = client.get_issue(issue_key, expand="changelog")

        if not issue_data:
            return []

        changelog = issue_data.get("changelog", {})
        histories_raw = changelog.get("histories", [])

        if not histories_raw:
            return []

        # 이력 파싱
        histories = []
        for history_raw in histories_raw[:max_results]:
            author = history_raw.get("author", {})
            history = {
                "author": author.get("displayName", "Unknown"),
                "created": history_raw.get("created", ""),
                "items": []
            }

            for item in history_raw.get("items", []):
                history["items"].append({
                    "field": item.get("field", ""),
                    "fieldtype": item.get("fieldtype", ""),
                    "fromString": item.get("fromString", ""),
                    "toString": item.get("toString", ""),
                })

            histories.append(history)

        return histories

    except Exception:
        return []
