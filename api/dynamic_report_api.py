#!/usr/bin/env python3
"""
Dynamic Report API - 멀티유저 동적 보고서 시스템 API

인증, 프롬프트 관리, 보고서 생성 API
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import os

from models.report_models import DatabaseManager
from services.auth_service import AuthService
from services.prompt_service import PromptService
from services.report_service import ReportService
from services.group_service import GroupService
from services.group_report_service import GroupReportService
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
    is_public: bool = False
    order_index: int = 999
    group_id: Optional[int] = None
    system: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    prompt_content: Optional[str] = None
    is_public: Optional[bool] = None
    order_index: Optional[int] = None
    group_id: Optional[int] = None
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


# 그룹 관련 Request/Response 모델
class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddMemberRequest(BaseModel):
    user_id: int
    system: Optional[str] = None


class GroupReportGenerateRequest(BaseModel):
    title: str
    prompt_ids: List[int]
    include_toc: bool = True
    save: bool = True


# Dependency: 인증 토큰 검증
def get_current_user(authorization: str = Header(None)):
    """
    토큰 검증 및 사용자 조회

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
        auth_service = AuthService(session)

        # 토큰 검증
        user = auth_service.verify_token_and_get_user(token)
        session.close()

        return user.id

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# 인증 API
@router.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """회원가입"""
    session = db_manager.get_session()

    try:
        auth_service = AuthService(session)
        result = auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password
        )
        return result

    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """로그인"""
    session = db_manager.get_session()

    try:
        auth_service = AuthService(session)
        result = auth_service.login(
            username=request.username,
            password=request.password
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        session.close()


# 그룹 관리 API
@router.get("/groups")
async def get_user_groups(user_id: int = Depends(get_current_user)):
    """사용자의 그룹 목록 조회"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        groups = group_service.get_user_groups(user_id)
        return {"success": True, "groups": groups}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/groups")
async def create_group(
    request: GroupCreateRequest,
    user_id: int = Depends(get_current_user)
):
    """그룹 생성 (생성자가 자동으로 owner로 추가됨)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        group = group_service.create_group(
            user_id=user_id,
            name=request.name,
            description=request.description
        )
        return {"success": True, "group": group}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/groups/{group_id}")
async def get_group_detail(
    group_id: int,
    user_id: int = Depends(get_current_user)
):
    """그룹 상세 조회 (멤버만 접근 가능)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        detail = group_service.get_group_detail(group_id=group_id, user_id=user_id)
        return {"success": True, "data": detail}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/groups/{group_id}/members")
async def add_group_member(
    group_id: int,
    request: AddMemberRequest,
    user_id: int = Depends(get_current_user)
):
    """그룹에 멤버 추가 (owner만 가능)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        member = group_service.add_member(
            group_id=group_id,
            owner_id=user_id,
            new_user_id=request.user_id,
            system=request.system
        )
        return {"success": True, "member": member}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/groups/{group_id}/members/{target_user_id}")
async def remove_group_member(
    group_id: int,
    target_user_id: int,
    user_id: int = Depends(get_current_user)
):
    """그룹에서 멤버 제거 (owner만 가능, owner는 제거 불가)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        success = group_service.remove_member(
            group_id=group_id,
            owner_id=user_id,
            target_user_id=target_user_id
        )
        return {"success": success, "message": "멤버가 제거되었습니다"}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/groups/{group_id}")
async def update_group(
    group_id: int,
    request: GroupUpdateRequest,
    user_id: int = Depends(get_current_user)
):
    """그룹 정보 수정 (owner만 가능)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        group = group_service.update_group(
            group_id=group_id,
            user_id=user_id,
            name=request.name,
            description=request.description
        )
        return {"success": True, "group": group}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: int,
    user_id: int = Depends(get_current_user)
):
    """그룹 삭제 (owner만 가능)"""
    session = db_manager.get_session()

    try:
        group_service = GroupService(session)
        success = group_service.delete_group(group_id=group_id, user_id=user_id)
        return {"success": success, "message": "그룹이 삭제되었습니다"}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/groups/{group_id}/reports/generate")
async def generate_group_report(
    group_id: int,
    request: GroupReportGenerateRequest,
    user_id: int = Depends(get_current_user)
):
    """그룹 보고서 생성 (멤버만 가능)"""
    session = db_manager.get_session()

    try:
        # Azure OpenAI 클라이언트 생성
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        # Agent 생성
        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            db_path=os.getenv("DB_PATH", "tickets.db")
        )

        # GroupReportService 생성
        prompt_service = PromptService(session)
        group_service = GroupService(session)
        group_report_service = GroupReportService(
            session,
            agent,
            prompt_service,
            group_service
        )

        # 그룹 보고서 생성
        result = group_report_service.generate_group_report(
            user_id=user_id,
            group_id=group_id,
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

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 프롬프트 관리 API
@router.get("/prompts")
async def get_prompts(
    include_public: bool = False,
    user_id: int = Depends(get_current_user)
):
    """사용자의 프롬프트 목록 조회"""
    session = db_manager.get_session()

    try:
        prompt_service = PromptService(session)
        result = prompt_service.get_user_prompts(user_id, include_public)
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

        # 2. 변수 치환 (옵션)
        prompt_content = prompt.prompt_content
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

                # 변수 치환
                prompt_content = prompt.prompt_content
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
