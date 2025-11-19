#!/usr/bin/env python3
"""
Dynamic Report API - 멀티유저 동적 보고서 시스템 API

인증, 프롬프트 관리, 보고서 생성 API
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

from models.report_models import DatabaseManager
from services.unified_auth_service import UnifiedAuthService
from services.prompt_service import PromptService
from services.report_service import ReportService
from services.template_service import TemplateService
from services.variable_service import VariableService, UndefinedVariableError
from services.template_parser import TemplatePlaceholderParser
# from services.group_service import GroupService  # 제거됨 (보안 정책)
# from services.group_report_service import GroupReportService  # 제거됨 (보안 정책)
from agent.monthly_report_agent import MonthlyReportAgent
from openai import AzureOpenAI


# API Router 생성
router = APIRouter(prefix="/api/v2", tags=["dynamic-report"])

# 데이터베이스 초기화
db_manager = DatabaseManager(os.getenv('REPORTS_DB_PATH', 'reports.db'))
db_manager.create_tables()


# Request/Response 모델
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: int
    username: str
    email: str
    token: str


class PromptCreateRequest(BaseModel):
    title: str
    category: str = '기타'
    description: Optional[str] = None
    prompt_content: str
    jql: Optional[str] = None  # JQL 쿼리 (선택적)
    is_public: bool = False
    order_index: int = 999
    # group_id: Optional[int] = None  # 제거됨 (보안 정책)
    system: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    prompt_content: Optional[str] = None
    jql: Optional[str] = None  # JQL 쿼리 (선택적)
    is_public: Optional[bool] = None
    order_index: Optional[int] = None
    # group_id: Optional[int] = None  # 제거됨 (보안 정책)
    system: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    title: str
    prompt_ids: List[int]
    include_toc: bool = True
    save: bool = False


class ExecutePromptRequest(BaseModel):
    variables: Optional[dict] = {}


class ExecuteBatchRequest(BaseModel):
    prompt_ids: List[int]
    variables: Optional[dict] = {}


class SectionData(BaseModel):
    prompt_id: int
    html_content: str
    order: int


class GenerateFromResultsRequest(BaseModel):
    title: str
    sections: List[SectionData]
    include_toc: bool = True
    save: bool = False


class TemplateCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    template_content: str


class TemplateUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    template_content: Optional[str] = None


class TemplateReportGenerateRequest(BaseModel):
    template_id: int
    title: str  # 보고서 제목
    save: bool = True  # DB에 저장 여부


# ============================================
# 그룹 관련 Request/Response 모델 - 제거됨 (보안 정책)
# ============================================
# class GroupCreateRequest(BaseModel):
#     name: str
#     description: Optional[str] = None


# class GroupUpdateRequest(BaseModel):
#     name: Optional[str] = None
#     description: Optional[str] = None


# class AddMemberRequest(BaseModel):
#     user_id: int
#     system: Optional[str] = None


# class GroupReportGenerateRequest(BaseModel):
#     title: str
#     prompt_ids: List[int]
#     include_toc: bool = True
#     save: bool = True


# Dependency: 인증 토큰 검증
def get_current_user(authorization: str = Header(None)):
    """
    토큰 검증 및 사용자 조회 (통합 인증)

    Args:
        authorization: Authorization 헤더 ("Bearer <token>")

    Returns:
        user_id (int)

    Raises:
        HTTPException: 인증 실패
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다")

    try:
        # "Bearer <token>" 형식에서 토큰 추출
        token = authorization.split(' ')[1] if ' ' in authorization else authorization

        # 세션 생성
        session = db_manager.get_session()
        auth_service = UnifiedAuthService(
            tickets_db_path=os.getenv('TICKETS_DB_PATH', 'tickets.db'),
            reports_session=session
        )

        # 토큰 검증
        user = auth_service.verify_token_and_get_user(token)
        session.close()

        return user.id

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# 인증 API
@router.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """회원가입 (tickets.db와 reports.db 모두에 생성)"""
    session = db_manager.get_session()

    try:
        # UnifiedAuthService 사용 (tickets.db + reports.db 동시 생성)
        auth_service = UnifiedAuthService(
            tickets_db_path=os.getenv('TICKETS_DB_PATH', 'tickets.db'),
            reports_session=session
        )
        result = auth_service.register(
            email=request.email,
            password=request.password,
            user_name=request.username
        )
        return result

    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """로그인 (tickets.db에서 인증)"""
    session = db_manager.get_session()

    try:
        # UnifiedAuthService 사용 (tickets.db 인증 + reports.db 동기화)
        auth_service = UnifiedAuthService(
            tickets_db_path=os.getenv('TICKETS_DB_PATH', 'tickets.db'),
            reports_session=session
        )

        # username 또는 email로 로그인 가능
        # username이 이메일 형식이 아니면 tickets.db에서 조회하여 email 획득
        email = request.username
        if '@' not in email:
            # username으로 email 찾기
            import sqlite3
            conn = sqlite3.connect(os.getenv('TICKETS_DB_PATH', 'tickets.db'))
            cursor = conn.cursor()
            cursor.execute('SELECT email FROM users WHERE user_name = ?', (request.username,))
            row = cursor.fetchone()
            conn.close()
            if row:
                email = row[0]

        result = auth_service.login(
            email=email,
            password=request.password
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        session.close()


# ============================================
# 그룹 관리 API - 제거됨 (보안 정책)
# ============================================
# @router.get("/groups")
# async def get_user_groups(user_id: int = Depends(get_current_user)):
#     """사용자의 그룹 목록 조회"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         groups = group_service.get_user_groups(user_id)
#         return {"success": True, "groups": groups}
#
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.post("/groups")
# async def create_group(
#     request: GroupCreateRequest,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹 생성 (생성자가 자동으로 owner로 추가됨)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         group = group_service.create_group(
#             user_id=user_id,
#             name=request.name,
#             description=request.description
#         )
#         return {"success": True, "group": group}
#
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.get("/groups/{group_id}")
# async def get_group_detail(
#     group_id: int,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹 상세 조회 (멤버만 접근 가능)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         detail = group_service.get_group_detail(group_id=group_id, user_id=user_id)
#         return {"success": True, "data": detail}
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.post("/groups/{group_id}/members")
# async def add_group_member(
#     group_id: int,
#     request: AddMemberRequest,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹에 멤버 추가 (owner만 가능)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         member = group_service.add_member(
#             group_id=group_id,
#             owner_id=user_id,
#             new_user_id=request.user_id,
#             system=request.system
#         )
#         return {"success": True, "member": member}
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.delete("/groups/{group_id}/members/{target_user_id}")
# async def remove_group_member(
#     group_id: int,
#     target_user_id: int,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹에서 멤버 제거 (owner만 가능, owner는 제거 불가)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         success = group_service.remove_member(
#             group_id=group_id,
#             owner_id=user_id,
#             target_user_id=target_user_id
#         )
#         return {"success": success, "message": "멤버가 제거되었습니다"}
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.put("/groups/{group_id}")
# async def update_group(
#     group_id: int,
#     request: GroupUpdateRequest,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹 정보 수정 (owner만 가능)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         group = group_service.update_group(
#             group_id=group_id,
#             user_id=user_id,
#             name=request.name,
#             description=request.description
#         )
#         return {"success": True, "group": group}
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.delete("/groups/{group_id}")
# async def delete_group(
#     group_id: int,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹 삭제 (owner만 가능)"""
#     session = db_manager.get_session()
#
#     try:
#         group_service = GroupService(session)
#         success = group_service.delete_group(group_id=group_id, user_id=user_id)
#         return {"success": success, "message": "그룹이 삭제되었습니다"}
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()
#
#
# @router.post("/groups/{group_id}/reports/generate")
# async def generate_group_report(
#     group_id: int,
#     request: GroupReportGenerateRequest,
#     user_id: int = Depends(get_current_user)
# ):
#     """그룹 보고서 생성 (멤버만 가능)"""
#     session = db_manager.get_session()
#
#     try:
#         # Azure OpenAI 클라이언트 생성
#         azure_client = AzureOpenAI(
#             api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#             api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
#             azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
#         )
#
#         # Agent 생성
#         agent = MonthlyReportAgent(
#             azure_client=azure_client,
#             user_id=user_id,
#             deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
#             db_path=os.getenv("DB_PATH", "tickets.db")
#         )
#
#         # GroupReportService 생성
#         prompt_service = PromptService(session)
#         group_service = GroupService(session)
#         group_report_service = GroupReportService(
#             session,
#             agent,
#             prompt_service,
#             group_service
#         )
#
#         # 그룹 보고서 생성
#         result = group_report_service.generate_group_report(
#             user_id=user_id,
#             group_id=group_id,
#             title=request.title,
#             prompt_ids=request.prompt_ids,
#             include_toc=request.include_toc,
#             save=request.save
#         )
#
#         return {
#             "success": True,
#             "report_id": result['report_id'],
#             "html": result['html'],
#             "metadata": result['metadata']
#         }
#
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         session.close()


# 프롬프트 관리 API
@router.get("/prompts")
async def get_prompts(
    include_public: bool = False,
    category: Optional[str] = None,
    user_id: int = Depends(get_current_user)
):
    """
    사용자의 프롬프트 목록 조회

    Args:
        include_public: 공개 프롬프트 포함 여부
        category: 카테고리 필터 (예: "월간보고", "주간보고" 등)

    Returns:
        {
            "my_prompts": [...],
            "public_prompts": [...],
            "categories": [...]  # 전체 카테고리 목록
        }
    """
    session = db_manager.get_session()

    try:
        prompt_service = PromptService(session)
        result = prompt_service.get_user_prompts(user_id, include_public, category)
        return result

    finally:
        session.close()


@router.post("/prompts")
async def create_prompt(
    request: PromptCreateRequest,
    user_id: int = Depends(get_current_user)
):
    """프롬프트 생성"""
    session = db_manager.get_session()

    try:
        prompt_service = PromptService(session)
        prompt_id = prompt_service.create_prompt(
            user_id=user_id,
            data=request.dict()
        )
        return {"id": prompt_id, "message": "프롬프트 생성 완료"}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: int,
    request: PromptUpdateRequest,
    user_id: int = Depends(get_current_user)
):
    """프롬프트 수정"""
    session = db_manager.get_session()

    try:
        prompt_service = PromptService(session)

        # None이 아닌 필드만 추출
        update_data = {k: v for k, v in request.dict().items() if v is not None}

        prompt_service.update_prompt(user_id, prompt_id, update_data)
        return {"message": "프롬프트 수정 완료"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    user_id: int = Depends(get_current_user)
):
    """프롬프트 삭제"""
    session = db_manager.get_session()

    try:
        prompt_service = PromptService(session)
        prompt_service.delete_prompt(user_id, prompt_id)
        return {"message": "프롬프트 삭제 완료"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 보고서 생성 API
@router.post("/reports/generate")
async def generate_report(
    request: ReportGenerateRequest,
    user_id: int = Depends(get_current_user)
):
    """동적 보고서 생성"""
    session = db_manager.get_session()

    try:
        # Agent 생성
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            db_path=os.getenv("DB_PATH", "tickets.db")
        )

        # ReportService 생성
        prompt_service = PromptService(session)
        report_service = ReportService(session, agent, prompt_service)

        # 보고서 생성
        result = report_service.generate_report(
            user_id=user_id,
            title=request.title,
            prompt_ids=request.prompt_ids,
            include_toc=request.include_toc,
            save=request.save
        )

        return {
            "success": True,
            "report_id": result['report_id'],
            "html": result['html'],
            "metadata": result['metadata']
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/reports")
async def get_reports(user_id: int = Depends(get_current_user)):
    """사용자의 보고서 목록"""
    session = db_manager.get_session()

    try:
        # Agent는 히스토리 조회에 필요 없으므로 None
        report_service = ReportService(session, agent=None)
        reports = report_service.get_user_reports(user_id)
        return {"reports": reports}

    finally:
        session.close()


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    user_id: int = Depends(get_current_user)
):
    """보고서 조회 (HTML 포함)"""
    session = db_manager.get_session()

    try:
        report_service = ReportService(session, agent=None)
        report = report_service.get_report_by_id(user_id, report_id)
        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        session.close()


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: int,
    user_id: int = Depends(get_current_user)
):
    """보고서 삭제"""
    session = db_manager.get_session()

    try:
        report_service = ReportService(session, agent=None)
        report_service.delete_report(user_id, report_id)
        return {"message": "보고서 삭제 완료"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 단일 프롬프트 실행 API
@router.post("/prompts/{prompt_id}/execute")
async def execute_prompt(
    prompt_id: int,
    request: ExecutePromptRequest,
    user_id: int = Depends(get_current_user)
):
    """
    단일 프롬프트를 AI Agent로 실행

    Args:
        prompt_id: 프롬프트 ID
        request: {
            "variables": {  // 선택사항: 프롬프트 변수 치환
                "month": "2024.11",
                "project": "NCMS"
            }
        }

    Returns:
        {
            "prompt_id": 1,
            "title": "전체 운영 업무 현황",
            "category": "월간보고",
            "html_result": "<table>...</table>",
            "executed_at": "2024-11-02T15:30:00",
            "elapsed_time": 3.5
        }
    """
    session = db_manager.get_session()

    try:
        # 1. 프롬프트 조회 (본인 것 + 공개된 것만)
        prompt_service = PromptService(session)
        prompts = prompt_service.get_prompts_by_ids([prompt_id], user_id)

        if not prompts:
            raise HTTPException(status_code=403, detail="프롬프트를 찾을 수 없거나 권한이 없습니다")

        prompt = prompts[0]

        # 2. 전역 변수 치환 ({{변수명}} 형식)
        prompt_content = prompt.prompt_content
        variable_service = VariableService()

        try:
            prompt_content, substitution_map = variable_service.substitute_variables(prompt_content)
            logger.info(f"✅ 변수 치환 완료: {substitution_map}")
        except UndefinedVariableError as e:
            logger.warning(f"⚠️ 정의되지 않은 변수: {e.variable_names}")
            raise HTTPException(
                status_code=400,
                detail=f"정의되지 않은 변수가 있습니다: {', '.join(e.variable_names)}"
            )

        # 2.5. JQL 참조 치환 ({{jql:id}} 형식)
        import re
        from services.jql_service import JQLService
        from tools.jira_query_tool import JiraQueryTool

        jql_pattern = r'\{\{jql:(\d+)\}\}'
        jql_matches = re.findall(jql_pattern, prompt_content)

        logger.info(f"🔍 JQL 참조 검색: {len(jql_matches)}개 발견 - {jql_matches}")

        if jql_matches:
            jql_service = JQLService(session)
            jira_tool = JiraQueryTool(user_id=user_id)

            for jql_id_str in jql_matches:
                jql_id = int(jql_id_str)

                # JQL 조회
                jql_obj = jql_service.get_jql_by_id(jql_id, user_id)
                if not jql_obj:
                    logger.warning(f"⚠️ JQL ID {jql_id}를 찾을 수 없습니다. 건너뜁니다.")
                    continue

                # JQL 실행
                try:
                    # JQL에 변수 치환 적용
                    jql_query = jql_obj.jql
                    jql_query, _ = variable_service.substitute_variables(jql_query)

                    issues = jira_tool.get_issues_by_jql(
                        jql=jql_query,
                        fields=["key", "summary", "status", "assignee", "created", "updated", "priority"],
                        max_results=1000
                    )

                    # 이슈 목록을 텍스트로 변환
                    if issues:
                        issue_text = "\n".join([
                            f"- [{issue.get('key', 'N/A')}] {issue.get('summary', '')} "
                            f"(상태: {issue.get('status', 'N/A')}, "
                            f"담당자: {issue.get('assignee', 'Unassigned')}, "
                            f"우선순위: {issue.get('priority', 'N/A')})"
                            for issue in issues
                        ])
                        jql_result = f"JQL '{jql_obj.name}' 실행 결과 ({len(issues)}개 이슈):\n{issue_text}"
                    else:
                        jql_result = f"JQL '{jql_obj.name}' 실행 결과: 이슈 없음"

                    # {{jql:id}}를 실행 결과로 치환
                    prompt_content = prompt_content.replace(f"{{{{jql:{jql_id}}}}}", jql_result)
                    logger.info(f"✅ JQL ID {jql_id} ({jql_obj.name}) 실행 완료: {len(issues)}개 이슈")

                except Exception as e:
                    logger.error(f"❌ JQL ID {jql_id} 실행 실패: {e}")
                    prompt_content = prompt_content.replace(
                        f"{{{{jql:{jql_id}}}}}",
                        f"[JQL 실행 실패: {str(e)}]"
                    )

        # 추가 변수 치환 (request로 전달된 변수 - {변수명} 형식, 하위 호환성)
        variables = request.variables or {}
        for key, value in variables.items():
            prompt_content = prompt_content.replace(f"{{{key}}}", str(value))

        # 3. AI Agent 실행
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            db_path=os.getenv("DB_PATH", "tickets.db")
        )

        result = agent.generate_page(
            page_title=prompt.title,
            user_prompt=prompt_content,
            context=variables
        )

        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', '알 수 없는 오류'))

        # 4. 결과 반환
        from datetime import datetime
        return {
            "prompt_id": prompt.id,
            "title": prompt.title,
            "category": prompt.category,
            "html_result": result.get('content', ''),
            "executed_at": datetime.now().isoformat(),
            "elapsed_time": result.get('elapsed_time', 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 일괄 실행 API
@router.post("/reports/execute-batch")
async def execute_batch(
    request: ExecuteBatchRequest,
    user_id: int = Depends(get_current_user)
):
    """
    여러 프롬프트를 일괄 실행

    Args:
        request: {
            "prompt_ids": [1, 3, 5, 7],
            "variables": {
                "month": "2024.11"
            }
        }

    Returns:
        {
            "results": [
                {
                    "prompt_id": 1,
                    "title": "...",
                    "category": "...",
                    "html_result": "...",
                    "status": "success",
                    "elapsed_time": 3.5
                },
                ...
            ],
            "total": 4,
            "success": 4,
            "failed": 0
        }
    """
    session = db_manager.get_session()

    try:
        prompt_ids = request.prompt_ids
        variables = request.variables or {}

        # 프롬프트 조회
        prompt_service = PromptService(session)
        prompts = prompt_service.get_prompts_by_ids(prompt_ids, user_id)

        # ID로 매핑
        prompt_map = {p.id: p for p in prompts}

        # Agent 생성
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            db_path=os.getenv("DB_PATH", "tickets.db")
        )

        results = []

        for prompt_id in prompt_ids:
            try:
                prompt = prompt_map.get(prompt_id)

                if not prompt:
                    results.append({
                        "prompt_id": prompt_id,
                        "status": "error",
                        "error": "프롬프트를 찾을 수 없거나 권한이 없습니다"
                    })
                    continue

                # 전역 변수 치환 ({{변수명}} 형식)
                prompt_content = prompt.prompt_content
                variable_service = VariableService()

                try:
                    prompt_content, substitution_map = variable_service.substitute_variables(prompt_content)
                except UndefinedVariableError as e:
                    logger.warning(f"⚠️ 프롬프트 {prompt_id} - 정의되지 않은 변수: {e.variable_names}")
                    results.append({
                        "prompt_id": prompt_id,
                        "title": prompt.title,
                        "status": "error",
                        "error": f"정의되지 않은 변수: {', '.join(e.variable_names)}"
                    })
                    continue

                # 추가 변수 치환 (request로 전달된 변수 - {변수명} 형식, 하위 호환성)
                for key, value in variables.items():
                    prompt_content = prompt_content.replace(f"{{{key}}}", str(value))

                # AI 실행
                result = agent.generate_page(
                    page_title=prompt.title,
                    user_prompt=prompt_content,
                    context=variables
                )

                if result.get('success'):
                    results.append({
                        "prompt_id": prompt.id,
                        "title": prompt.title,
                        "category": prompt.category,
                        "html_result": result.get('content', ''),
                        "status": "success",
                        "elapsed_time": result.get('elapsed_time', 0)
                    })
                else:
                    results.append({
                        "prompt_id": prompt_id,
                        "status": "error",
                        "error": result.get('error', '알 수 없는 오류')
                    })

            except Exception as e:
                results.append({
                    "prompt_id": prompt_id,
                    "status": "error",
                    "error": str(e)
                })

        success_count = sum(1 for r in results if r.get('status') == 'success')

        return {
            "results": results,
            "total": len(prompt_ids),
            "success": success_count,
            "failed": len(prompt_ids) - success_count
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 실행 결과 조합 API
@router.post("/reports/generate-from-results")
async def generate_from_results(
    request: GenerateFromResultsRequest,
    user_id: int = Depends(get_current_user)
):
    """
    이미 실행된 결과로 최종 보고서 생성

    Args:
        request: {
            "title": "월간보고 (2024.11)",
            "sections": [
                {
                    "prompt_id": 1,
                    "html_content": "<table>...</table>",
                    "order": 0
                },
                {
                    "prompt_id": 3,
                    "html_content": "<div>...</div>",
                    "order": 1
                }
            ],
            "include_toc": true,
            "save": true
        }

    Returns:
        {
            "report_id": 42,
            "title": "월간보고 (2024.11)",
            "html": "<!DOCTYPE html>...",
            "created_at": "2024-11-02T16:00:00"
        }
    """
    session = db_manager.get_session()

    try:
        from datetime import datetime
        from models.report_models import Report, PromptTemplate
        import json as json_module

        title = request.title
        sections = sorted(request.sections, key=lambda x: x.order)
        include_toc = request.include_toc
        save = request.save

        # 프롬프트 정보 조회 (제목, 카테고리)
        prompt_ids = [s.prompt_id for s in sections]
        prompt_service = PromptService(session)
        prompts = prompt_service.get_prompts_by_ids(prompt_ids, user_id)
        prompt_map = {p.id: p for p in prompts}

        # HTML 문서 생성
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .report-header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #4CAF50;
        }}
        .report-header h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .report-date {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}
        .toc {{
            background-color: #f8f9fa;
            padding: 20px;
            margin-bottom: 30px;
            border-left: 4px solid #4CAF50;
        }}
        .toc h2 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .toc ol {{
            padding-left: 20px;
        }}
        .toc li {{
            margin: 8px 0;
        }}
        .toc a {{
            color: #3498db;
            text-decoration: none;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
        .report-section {{
            margin-bottom: 40px;
        }}
        .report-section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .section-content {{
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>{title}</h1>
            <p class="report-date">{datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
"""

        # 목차 생성
        if include_toc:
            html += '\n<div class="toc">\n'
            html += '<h2>목차</h2>\n'
            html += '<ol>\n'

            for i, section in enumerate(sections, 1):
                prompt = prompt_map.get(section.prompt_id)
                section_title = prompt.title if prompt else f"Section {i}"
                html += f'<li><a href="#section-{i}">{section_title}</a></li>\n'

            html += '</ol>\n'
            html += '</div>\n'

        # 각 섹션 추가
        for i, section in enumerate(sections, 1):
            prompt = prompt_map.get(section.prompt_id)
            section_title = prompt.title if prompt else f"Section {i}"

            html += f"""
<section id="section-{i}" class="report-section">
    <h2>{i}. {section_title}</h2>
    <div class="section-content">
        {section.html_content}
    </div>
</section>
"""

        html += """
    </div>
</body>
</html>
"""

        # DB 저장
        report_id = None
        if save:
            report = Report(
                user_id=user_id,
                title=title,
                html_content=html,
                prompt_ids=json_module.dumps(prompt_ids)
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

        return {
            "report_id": report_id,
            "title": title,
            "html": html,
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ========================================
# Jira API 캐시 관리 엔드포인트
# ========================================

@router.get("/cache/stats")
async def get_cache_stats(user_id: int = Depends(get_current_user)):
    """
    Jira API 캐시 통계 조회

    Returns:
        {
            "total_requests": int,
            "cache_hits": int,
            "cache_misses": int,
            "hit_rate": str,
            "api_calls": int,
            "cached_items": int,
            "users": int
        }
    """
    try:
        from cached_jira_client import get_total_cache_stats

        stats = get_total_cache_stats()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(user_id: int = Depends(get_current_user)):
    """
    Jira API 캐시 수동 초기화 (모든 사용자)

    Note:
        관리자 전용 기능. 모든 사용자의 캐시를 초기화합니다.
    """
    try:
        from cached_jira_client import clear_all_caches, get_total_cache_stats

        # 초기화 전 통계
        before_stats = get_total_cache_stats()

        # 캐시 초기화
        clear_all_caches()

        # 초기화 후 통계
        after_stats = get_total_cache_stats()

        return {
            "success": True,
            "message": "캐시가 초기화되었습니다",
            "before": {
                "cached_items": before_stats['cached_items'],
                "users": before_stats['users']
            },
            "after": {
                "cached_items": after_stats['cached_items'],
                "users": after_stats['users']
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# 템플릿 관리 API
# ========================================

@router.get("/templates")
async def get_templates(user_id: int = Depends(get_current_user)):
    """사용자의 템플릿 목록 조회"""
    session = db_manager.get_session()

    try:
        template_service = TemplateService(session)
        templates = template_service.get_user_templates(user_id)
        return {"success": True, "templates": templates}

    finally:
        session.close()


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    user_id: int = Depends(get_current_user)
):
    """특정 템플릿 조회 (내용 포함)"""
    session = db_manager.get_session()

    try:
        template_service = TemplateService(session)
        template = template_service.get_template_by_id(template_id, user_id)

        if not template:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

        return {"success": True, "template": template}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    finally:
        session.close()


@router.post("/templates")
async def create_template(
    request: TemplateCreateRequest,
    user_id: int = Depends(get_current_user)
):
    """템플릿 생성"""
    session = db_manager.get_session()

    try:
        template_service = TemplateService(session)

        # 템플릿 유효성 검사 (선택사항)
        validation = template_service.validate_template(
            request.template_content,
            user_id
        )

        # 생성
        template_id = template_service.create_template(
            user_id=user_id,
            data=request.dict()
        )

        return {
            "success": True,
            "id": template_id,
            "message": "템플릿 생성 완료",
            "validation": validation
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    request: TemplateUpdateRequest,
    user_id: int = Depends(get_current_user)
):
    """템플릿 수정"""
    session = db_manager.get_session()

    try:
        template_service = TemplateService(session)

        # None이 아닌 필드만 추출
        update_data = {k: v for k, v in request.dict().items() if v is not None}

        template_service.update_template(user_id, template_id, update_data)
        return {"success": True, "message": "템플릿 수정 완료"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    user_id: int = Depends(get_current_user)
):
    """템플릿 삭제"""
    session = db_manager.get_session()

    try:
        template_service = TemplateService(session)
        template_service.delete_template(user_id, template_id)
        return {"success": True, "message": "템플릿 삭제 완료"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 템플릿 기반 보고서 생성
@router.post("/reports/generate-from-template")
async def generate_report_from_template(
    request: TemplateReportGenerateRequest,
    user_id: int = Depends(get_current_user)
):
    """
    템플릿 기반 보고서 생성

    템플릿의 {{prompt:id}} placeholder를 실제 프롬프트 실행 결과로 치환하여 보고서 생성

    Args:
        request: {
            "template_id": 1,
            "title": "2024년 11월 월간 보고서",
            "save": true
        }

    Returns:
        {
            "report_id": 123,
            "title": "2024년 11월 월간 보고서",
            "html": "<!DOCTYPE html>...",
            "created_at": "2024-11-13T10:30:00",
            "missing_executions": [],  # 실행 결과가 없는 프롬프트 ID 목록
            "warnings": []
        }
    """
    session = db_manager.get_session()

    try:
        from datetime import datetime
        from models.report_models import Report, ReportTemplate, PromptExecution
        import json as json_module
        import markdown

        template_id = request.template_id
        title = request.title
        save = request.save

        # 1. 템플릿 조회
        template_service = TemplateService(session)
        template = session.query(ReportTemplate).filter_by(id=template_id, user_id=user_id).first()

        if not template:
            raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

        # 2. 템플릿 파싱 및 변수 치환
        parser = TemplatePlaceholderParser(session)

        # 전역 변수 치환 먼저 수행
        variable_service = VariableService()
        template_content = template.template_content

        try:
            template_content, var_map = variable_service.substitute_variables(template_content)
            logger.info(f"✅ 템플릿 전역 변수 치환 완료: {var_map}")
        except UndefinedVariableError as e:
            logger.warning(f"⚠️ 템플릿에 정의되지 않은 변수: {e.variable_names}")
            raise HTTPException(
                status_code=400,
                detail=f"템플릿에 정의되지 않은 변수가 있습니다: {', '.join(e.variable_names)}"
            )

        # 3. 프롬프트 ID 추출
        prompt_ids = parser.extract_prompt_ids(template_content)

        if not prompt_ids:
            raise HTTPException(status_code=400, detail="템플릿에 프롬프트 placeholder가 없습니다")

        # 4. 각 프롬프트 실행
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            db_path=os.getenv("DB_PATH", "tickets.db")
        )

        prompt_service = PromptService(session)
        prompts = prompt_service.get_prompts_by_ids(prompt_ids, user_id)
        prompt_map = {p.id: p for p in prompts}

        execution_cache = {}
        warnings = []

        for prompt_id in prompt_ids:
            prompt = prompt_map.get(prompt_id)

            if not prompt:
                warnings.append(f"프롬프트 ID {prompt_id}를 찾을 수 없거나 권한이 없습니다")
                continue

            # 프롬프트 내용의 변수 치환
            prompt_content = prompt.prompt_content
            try:
                prompt_content, sub_map = variable_service.substitute_variables(prompt_content)
            except UndefinedVariableError as e:
                warnings.append(f"프롬프트 '{prompt.title}' (ID: {prompt_id})에 정의되지 않은 변수: {', '.join(e.variable_names)}")
                continue

            # JQL 참조 치환 ({{jql:id}} 형식)
            import re
            from services.jql_service import JQLService
            from tools.jira_query_tool import JiraQueryTool

            jql_pattern = r'\{\{jql:(\d+)\}\}'
            jql_matches = re.findall(jql_pattern, prompt_content)

            if jql_matches:
                jql_service = JQLService(session)
                jira_tool = JiraQueryTool(user_id=user_id)

                for jql_id_str in jql_matches:
                    jql_id = int(jql_id_str)

                    # JQL 조회
                    jql_obj = jql_service.get_jql_by_id(jql_id, user_id)
                    if not jql_obj:
                        logger.warning(f"⚠️ JQL ID {jql_id}를 찾을 수 없습니다. 건너뜁니다.")
                        continue

                    # JQL 실행
                    try:
                        # JQL에 변수 치환 적용
                        jql_query = jql_obj.jql
                        jql_query, _ = variable_service.substitute_variables(jql_query)

                        issues = jira_tool.get_issues_by_jql(
                            jql=jql_query,
                            fields=["key", "summary", "status", "assignee", "created", "updated", "priority"],
                            max_results=1000
                        )

                        # 이슈 목록을 텍스트로 변환
                        if issues:
                            issue_text = "\n".join([
                                f"- [{issue.get('key', 'N/A')}] {issue.get('summary', '')} "
                                f"(상태: {issue.get('status', 'N/A')}, "
                                f"담당자: {issue.get('assignee', 'Unassigned')}, "
                                f"우선순위: {issue.get('priority', 'N/A')})"
                                for issue in issues
                            ])
                            jql_result = f"JQL '{jql_obj.name}' 실행 결과 ({len(issues)}개 이슈):\n{issue_text}"
                        else:
                            jql_result = f"JQL '{jql_obj.name}' 실행 결과: 이슈 없음"

                        # {{jql:id}}를 실행 결과로 치환
                        prompt_content = prompt_content.replace(f"{{{{jql:{jql_id}}}}}", jql_result)
                        logger.info(f"✅ JQL ID {jql_id} ({jql_obj.name}) 실행 완료: {len(issues)}개 이슈")

                    except Exception as e:
                        logger.error(f"❌ JQL ID {jql_id} 실행 실패: {e}")
                        warnings.append(f"프롬프트 '{prompt.title}' (ID: {prompt_id})의 JQL ID {jql_id} 실행 실패: {str(e)}")
                        prompt_content = prompt_content.replace(
                            f"{{{{jql:{jql_id}}}}}",
                            f"[JQL 실행 실패: {str(e)}]"
                        )

            # AI 실행
            try:
                result = agent.generate_page(
                    page_title=prompt.title,
                    user_prompt=prompt_content,
                    context={}
                )

                if result.get('success'):
                    execution_cache[prompt_id] = result.get('content', '')
                else:
                    warnings.append(f"프롬프트 '{prompt.title}' (ID: {prompt_id}) 실행 실패: {result.get('error')}")
            except Exception as e:
                warnings.append(f"프롬프트 '{prompt.title}' (ID: {prompt_id}) 실행 중 오류: {str(e)}")

        # 5. Placeholder 치환
        parse_result = parser.parse_template(template_content, execution_cache)

        # 6. Markdown을 HTML로 변환
        # extra extension: HTML을 그대로 유지하면서 표, 코드블록 등 지원
        markdown_content = parse_result['html']
        body_html = markdown.markdown(
            markdown_content,
            extensions=['extra', 'nl2br', 'sane_lists'],
            extension_configs={
                'extra': {
                    'fenced_code': {
                        'lang_prefix': 'language-'
                    }
                }
            }
        )

        # 7. 최종 HTML 문서 생성 (스타일 포함)
        final_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .report-header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #4CAF50;
        }}
        .report-header h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .report-date {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #2c3e50;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h2 {{
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        .missing-execution-warning, .missing-prompt-warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .missing-execution-warning strong, .missing-prompt-warning strong {{
            color: #856404;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>{title}</h1>
            <p class="report-date">{datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
        {body_html}
    </div>
</body>
</html>
"""

        # 8. DB 저장
        report_id = None
        if save:
            report = Report(
                user_id=user_id,
                title=title,
                html_content=final_html,
                prompt_ids=json_module.dumps(prompt_ids)
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

        return {
            "report_id": report_id,
            "title": title,
            "html": final_html,
            "created_at": datetime.now().isoformat(),
            "missing_executions": parse_result.get('missing_executions', []),
            "warnings": warnings
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 헬스 체크
@router.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "ok",
        "service": "dynamic-report-api",
        "version": "2.0.0"
    }


if __name__ == "__main__":
    print("Dynamic Report API 모듈")
    print("FastAPI 서버에 router를 포함시켜야 합니다:")
    print("  from api.dynamic_report_api import router")
    print("  app.include_router(router)")
