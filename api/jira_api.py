#!/usr/bin/env python3
"""
Jira API - JQL 테스트 및 메타데이터 조회
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import time
import logging

from api.dynamic_report_api import get_current_user
from tools.jira_query_tool import JiraQueryTool
from batch.jira_client import JiraAPIError
from services.variable_service import VariableService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/jira", tags=["jira"])


# Request/Response 모델
class JQLTestRequest(BaseModel):
    jql: str
    max_results: int = 20


class JQLTestResponse(BaseModel):
    success: bool
    total: Optional[int] = None
    execution_time_ms: Optional[float] = None
    issues: Optional[List[Dict]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    suggestion: Optional[str] = None
    original_jql: Optional[str] = None  # 원본 JQL (변수 포함)
    substituted_jql: Optional[str] = None  # 치환된 JQL
    substitutions: Optional[Dict[str, str]] = None  # 변수 치환 매핑


class ProjectInfo(BaseModel):
    key: str
    name: str


class UserInfo(BaseModel):
    accountId: str
    displayName: str
    emailAddress: Optional[str] = None
    avatarUrl: Optional[str] = None


# 메타데이터 API 엔드포인트

@router.get("/projects", response_model=List[ProjectInfo])
async def get_projects(user_id: int = Depends(get_current_user)):
    """
    Jira 프로젝트 목록 조회
    """
    try:
        tool = JiraQueryTool(user_id=user_id)

        # Jira Client를 통해 프로젝트 조회
        # /rest/api/2/project 엔드포인트 사용
        url = f"{tool.client.client.endpoint}/rest/api/2/project"
        response = tool.client.client.session.get(url, timeout=tool.client.client.timeout)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="프로젝트 목록 조회 실패")

        projects = response.json()

        # key와 name만 추출
        result = [
            ProjectInfo(key=p.get("key", ""), name=p.get("name", ""))
            for p in projects
        ]

        logger.info(f"✅ 프로젝트 {len(result)}개 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ 프로젝트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statuses", response_model=List[str])
async def get_statuses(user_id: int = Depends(get_current_user)):
    """
    Jira 상태 목록 조회
    """
    try:
        tool = JiraQueryTool(user_id=user_id)

        # /rest/api/2/status 엔드포인트 사용
        url = f"{tool.client.client.endpoint}/rest/api/2/status"
        response = tool.client.client.session.get(url, timeout=tool.client.client.timeout)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="상태 목록 조회 실패")

        statuses = response.json()

        # name만 추출
        result = [s.get("name", "") for s in statuses if s.get("name")]

        logger.info(f"✅ 상태 {len(result)}개 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priorities", response_model=List[str])
async def get_priorities(user_id: int = Depends(get_current_user)):
    """
    Jira 우선순위 목록 조회
    """
    try:
        tool = JiraQueryTool(user_id=user_id)

        # /rest/api/2/priority 엔드포인트 사용
        url = f"{tool.client.client.endpoint}/rest/api/2/priority"
        response = tool.client.client.session.get(url, timeout=tool.client.client.timeout)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="우선순위 목록 조회 실패")

        priorities = response.json()

        # name만 추출
        result = [p.get("name", "") for p in priorities if p.get("name")]

        logger.info(f"✅ 우선순위 {len(result)}개 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ 우선순위 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issue-types", response_model=List[str])
async def get_issue_types(user_id: int = Depends(get_current_user)):
    """
    Jira 이슈 타입 목록 조회
    """
    try:
        tool = JiraQueryTool(user_id=user_id)

        # /rest/api/2/issuetype 엔드포인트 사용
        url = f"{tool.client.client.endpoint}/rest/api/2/issuetype"
        response = tool.client.client.session.get(url, timeout=tool.client.client.timeout)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="이슈 타입 목록 조회 실패")

        issue_types = response.json()

        # name만 추출
        result = [it.get("name", "") for it in issue_types if it.get("name")]

        logger.info(f"✅ 이슈 타입 {len(result)}개 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ 이슈 타입 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users", response_model=List[UserInfo])
async def search_users(
    query: Optional[str] = None,
    user_id: int = Depends(get_current_user)
):
    """
    Jira 사용자 검색

    Args:
        query: 검색어 (선택사항, 없으면 최근 사용자 반환)
    """
    try:
        tool = JiraQueryTool(user_id=user_id)

        # /rest/api/2/user/search 엔드포인트 사용
        url = f"{tool.client.client.endpoint}/rest/api/2/user/search"
        params = {"maxResults": 50}

        if query:
            params["query"] = query

        response = tool.client.client.session.get(
            url,
            params=params,
            timeout=tool.client.client.timeout
        )

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="사용자 검색 실패")

        users = response.json()

        # 필요한 정보만 추출
        result = []
        for u in users:
            result.append(UserInfo(
                accountId=u.get("accountId", ""),
                displayName=u.get("displayName", ""),
                emailAddress=u.get("emailAddress"),
                avatarUrl=u.get("avatarUrls", {}).get("48x48")
            ))

        logger.info(f"✅ 사용자 {len(result)}명 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ 사용자 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# JQL 테스트 API

@router.post("/test-jql", response_model=JQLTestResponse)
async def test_jql(
    request: JQLTestRequest,
    user_id: int = Depends(get_current_user)
):
    """
    JQL 쿼리 테스트 (변수 치환 지원)

    Args:
        request: JQL 쿼리 및 옵션
    """
    start_time = time.time()
    original_jql = request.jql
    substituted_jql = request.jql
    substitutions = {}

    try:
        # 변수 치환 수행
        variable_service = VariableService()
        substituted_jql, substitutions = variable_service.substitute_variables(request.jql)

        logger.info(f"🔍 JQL 테스트: {original_jql}")
        if substitutions:
            logger.info(f"   변수 치환: {substitutions}")
            logger.info(f"   치환 후: {substituted_jql}")

        tool = JiraQueryTool(user_id=user_id)

        # 치환된 JQL로 실행
        raw_issues = tool.client.search_issues(
            jql=substituted_jql,
            max_results=request.max_results
        )

        execution_time = (time.time() - start_time) * 1000  # 밀리초로 변환

        # 이슈 데이터 정리
        issues = []
        for issue in raw_issues:
            fields = issue.get("fields", {})

            # 담당자 정보 추출
            assignee_info = fields.get("assignee")
            assignee_name = ""
            assignee_avatar = ""

            if assignee_info:
                assignee_name = assignee_info.get("displayName", "")
                avatars = assignee_info.get("avatarUrls", {})
                assignee_avatar = avatars.get("48x48", "")

            # 상태 정보
            status_info = fields.get("status", {})
            status_name = status_info.get("name", "")

            # 우선순위 정보
            priority_info = fields.get("priority", {})
            priority_name = priority_info.get("name", "")

            # 이슈 타입 정보
            issuetype_info = fields.get("issuetype", {})
            issuetype_name = issuetype_info.get("name", "")

            # Jira 이슈 URL 생성
            issue_key = issue.get("key", "")
            jira_url = f"{tool.client.client.endpoint}/browse/{issue_key}"

            issues.append({
                "key": issue_key,
                "summary": fields.get("summary", ""),
                "status": status_name,
                "assignee": assignee_name or "Unassigned",
                "assigneeAvatar": assignee_avatar,
                "updated": fields.get("updated", ""),
                "priority": priority_name,
                "type": issuetype_name,
                "url": jira_url
            })

        logger.info(f"✅ JQL 테스트 성공: {len(issues)}개 이슈 ({execution_time:.0f}ms)")

        return JQLTestResponse(
            success=True,
            total=len(raw_issues),
            execution_time_ms=execution_time,
            issues=issues,
            original_jql=original_jql if substitutions else None,
            substituted_jql=substituted_jql if substitutions else None,
            substitutions=substitutions if substitutions else None
        )

    except JiraAPIError as e:
        execution_time = (time.time() - start_time) * 1000
        error_msg = str(e)

        logger.error(f"❌ JQL 테스트 실패: {error_msg}")

        # 에러 타입 분류
        error_type = "JQL_SYNTAX_ERROR"
        if "401" in error_msg or "인증" in error_msg:
            error_type = "AUTH_ERROR"
        elif "403" in error_msg or "권한" in error_msg:
            error_type = "PERMISSION_ERROR"
        elif "404" in error_msg:
            error_type = "NOT_FOUND_ERROR"
        elif "500" in error_msg or "서버" in error_msg:
            error_type = "SERVER_ERROR"

        # 간단한 제안 생성
        suggestion = _generate_suggestion(substituted_jql, error_msg)

        return JQLTestResponse(
            success=False,
            error=error_msg,
            error_type=error_type,
            suggestion=suggestion,
            original_jql=original_jql if substitutions else None,
            substituted_jql=substituted_jql if substitutions else None,
            substitutions=substitutions if substitutions else None
        )

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        error_msg = str(e)

        logger.error(f"❌ JQL 테스트 예상치 못한 오류: {error_msg}")

        return JQLTestResponse(
            success=False,
            error=error_msg,
            error_type="UNKNOWN_ERROR",
            suggestion="JQL 문법을 확인해주세요. https://confluence.atlassian.com/jirasoftwarecloud/advanced-search-reference-jql-fields-764478330.html",
            original_jql=original_jql if substitutions else None,
            substituted_jql=substituted_jql if substitutions else None,
            substitutions=substitutions if substitutions else None
        )


def _generate_suggestion(jql: str, error_msg: str) -> Optional[str]:
    """
    JQL 오류에 대한 수정 제안 생성

    Args:
        jql: 원본 JQL
        error_msg: 에러 메시지

    Returns:
        수정 제안 (없으면 None)
    """
    # 일반적인 오타 패턴 감지
    common_typos = {
        "statuss": "status",
        "assignees": "assignee",
        "reporters": "reporter",
        "prioritys": "priority",
        "fixVersions": "fixVersion",
        "issuetypes": "issuetype",
    }

    for typo, correct in common_typos.items():
        if typo in jql.lower():
            return f"'{typo}'를 '{correct}'로 수정해보세요."

    # 기본 가이드 링크
    return "JQL 문법 가이드: https://confluence.atlassian.com/jirasoftwarecloud/advanced-search-reference-jql-fields-764478330.html"
