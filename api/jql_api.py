#!/usr/bin/env python3
"""
JQL API - JQL 쿼리 관리 CRUD API
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
import time
import logging

from api.dynamic_report_api import get_current_user
from services.jql_service import JQLService
from models.report_models import DatabaseManager
from tools.jira_query_tool import JiraQueryTool
from batch.jira_client import JiraAPIError
from services.variable_service import VariableService
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/jql", tags=["jql"])

# 데이터베이스 매니저 초기화
db_manager = DatabaseManager(os.getenv('REPORTS_DB_PATH', 'reports.db'))


def get_db_session():
    """DB 세션 생성 (Dependency)"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


# Request/Response 모델
class JQLCreateRequest(BaseModel):
    name: str
    jql: str
    description: Optional[str] = None
    system: Optional[str] = None
    category: Optional[str] = None
    is_public: bool = False


class JQLUpdateRequest(BaseModel):
    name: Optional[str] = None
    jql: Optional[str] = None
    description: Optional[str] = None
    system: Optional[str] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None


class JQLResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    jql: Optional[str] = None
    system: Optional[str] = None
    category: Optional[str] = None
    is_public: bool
    owner: Optional[str] = None
    created_at: str
    updated_at: str


class JQLListResponse(BaseModel):
    my_jqls: List[JQLResponse]
    public_jqls: Optional[List[JQLResponse]] = None
    systems: List[str]
    categories: List[str]
    total: int


class JQLTestRequest(BaseModel):
    jql_id: Optional[int] = None  # JQL ID로 테스트
    jql: Optional[str] = None  # 직접 JQL 문자열로 테스트
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
    jql_name: Optional[str] = None  # JQL 이름 (ID로 테스트한 경우)


class JQLUsageResponse(BaseModel):
    jql_id: int
    jql_name: str
    usage_count: int
    used_in_prompts: List[Dict]


# CRUD 엔드포인트

@router.get("", response_model=JQLListResponse)
async def list_jqls(
    include_public: bool = Query(False, description="공개 JQL 포함 여부"),
    system: Optional[str] = Query(None, description="시스템 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    search: Optional[str] = Query(None, description="검색 키워드"),
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 목록 조회

    - 본인의 JQL 목록
    - 옵션: 공개 JQL 포함
    - 필터: 시스템, 카테고리, 검색어
    """
    try:
        service = JQLService(db)
        result = service.get_user_jqls(
            user_id=user_id,
            include_public=include_public,
            system=system,
            category=category,
            search=search
        )

        total = len(result["my_jqls"])
        if include_public and "public_jqls" in result:
            total += len(result["public_jqls"])

        return JQLListResponse(
            my_jqls=result["my_jqls"],
            public_jqls=result.get("public_jqls"),
            systems=result["systems"],
            categories=result["categories"],
            total=total
        )

    except Exception as e:
        logger.error(f"❌ JQL 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{jql_id}", response_model=JQLResponse)
async def get_jql(
    jql_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 상세 조회 (ID)
    """
    try:
        service = JQLService(db)
        jql = service.get_jql_by_id(jql_id, user_id)

        if not jql:
            raise HTTPException(status_code=404, detail="JQL을 찾을 수 없습니다.")

        return JQLResponse(**jql.to_dict(include_jql=True, include_owner=True))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=JQLResponse, status_code=201)
async def create_jql(
    request: JQLCreateRequest,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 생성
    """
    try:
        service = JQLService(db)
        jql = service.create_jql(
            user_id=user_id,
            name=request.name,
            jql=request.jql,
            description=request.description,
            system=request.system,
            category=request.category,
            is_public=request.is_public
        )

        logger.info(f"✅ JQL 생성 완료: {jql.name} (ID: {jql.id})")
        return JQLResponse(**jql.to_dict(include_jql=True, include_owner=True))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ JQL 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{jql_id}", response_model=JQLResponse)
async def update_jql(
    jql_id: int,
    request: JQLUpdateRequest,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 수정 (본인만 가능)
    """
    try:
        service = JQLService(db)
        jql = service.update_jql(
            jql_id=jql_id,
            user_id=user_id,
            name=request.name,
            jql=request.jql,
            description=request.description,
            system=request.system,
            category=request.category,
            is_public=request.is_public
        )

        if not jql:
            raise HTTPException(status_code=404, detail="JQL을 찾을 수 없습니다.")

        logger.info(f"✅ JQL 수정 완료: {jql.name} (ID: {jql.id})")
        return JQLResponse(**jql.to_dict(include_jql=True, include_owner=True))

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{jql_id}", status_code=204)
async def delete_jql(
    jql_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 삭제 (본인만 가능)
    """
    try:
        service = JQLService(db)
        success = service.delete_jql(jql_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="JQL을 찾을 수 없습니다.")

        logger.info(f"✅ JQL 삭제 완료: ID {jql_id}")
        return None

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{jql_id}/usage", response_model=JQLUsageResponse)
async def get_jql_usage(
    jql_id: int,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 사용 현황 조회 (어떤 프롬프트에서 사용되는지)
    """
    try:
        service = JQLService(db)
        usage = service.get_jql_usage(jql_id, user_id)

        if not usage:
            raise HTTPException(status_code=404, detail="JQL을 찾을 수 없습니다.")

        return JQLUsageResponse(**usage)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 사용 현황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# JQL 테스트 엔드포인트

@router.post("/test", response_model=JQLTestResponse)
async def test_jql(
    request: JQLTestRequest,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 테스트 실행

    - JQL ID 또는 직접 JQL 문자열로 테스트 가능
    - 변수 치환 지원
    - Jira API 호출하여 결과 반환
    """
    try:
        # JQL 문자열 결정
        jql_string = None
        jql_name = None

        if request.jql_id:
            # JQL ID로 조회
            service = JQLService(db)
            jql_obj = service.get_jql_by_id(request.jql_id, user_id)

            if not jql_obj:
                raise HTTPException(status_code=404, detail="JQL을 찾을 수 없습니다.")

            jql_string = jql_obj.jql
            jql_name = jql_obj.name

        elif request.jql:
            # 직접 JQL 문자열 사용
            jql_string = request.jql

        else:
            raise HTTPException(status_code=400, detail="jql_id 또는 jql 중 하나를 제공해야 합니다.")

        # 변수 치환
        var_service = VariableService()  # DB 경로는 환경변수나 기본값 사용
        original_jql = jql_string
        substituted_jql, substitutions = var_service.substitute_variables(jql_string)

        # JQL 실행
        start_time = time.time()
        tool = JiraQueryTool(user_id=user_id)

        issues = tool.get_issues_by_jql(
            jql=substituted_jql,
            fields=["key", "summary", "status", "assignee", "created", "updated"],
            max_results=request.max_results
        )

        execution_time = (time.time() - start_time) * 1000  # ms

        logger.info(f"✅ JQL 테스트 완료: {len(issues)}개 이슈 조회 ({execution_time:.2f}ms)")

        return JQLTestResponse(
            success=True,
            total=len(issues),
            execution_time_ms=round(execution_time, 2),
            issues=issues,
            original_jql=original_jql,
            substituted_jql=substituted_jql if substituted_jql != original_jql else None,
            substitutions=substitutions if substitutions else None,
            jql_name=jql_name
        )

    except JiraAPIError as e:
        logger.warning(f"⚠️  Jira API 에러: {e}")

        # 에러 타입 분류
        error_type = "syntax_error"
        suggestion = None

        if "does not exist" in str(e).lower():
            error_type = "field_not_found"
            suggestion = "필드명이 올바른지 확인해주세요."
        elif "permission" in str(e).lower():
            error_type = "permission_error"
            suggestion = "프로젝트 접근 권한을 확인해주세요."

        return JQLTestResponse(
            success=False,
            error=str(e),
            error_type=error_type,
            suggestion=suggestion,
            original_jql=original_jql,
            substituted_jql=substituted_jql if substituted_jql != original_jql else None,
            substitutions=substitutions if substitutions else None,
            jql_name=jql_name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 테스트 실패: {e}")
        return JQLTestResponse(
            success=False,
            error=str(e),
            error_type="unknown_error",
            original_jql=original_jql if 'original_jql' in locals() else None,
            jql_name=jql_name if 'jql_name' in locals() else None
        )


@router.get("/name/{jql_name}", response_model=JQLResponse)
async def get_jql_by_name(
    jql_name: str,
    user_id: int = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    JQL 조회 (이름)

    프롬프트에서 {{JQL:이름}} 참조 시 사용
    """
    try:
        service = JQLService(db)
        jql = service.get_jql_by_name(jql_name, user_id)

        if not jql:
            raise HTTPException(status_code=404, detail=f"JQL '{jql_name}'을 찾을 수 없습니다.")

        return JQLResponse(**jql.to_dict(include_jql=True, include_owner=True))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JQL 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
