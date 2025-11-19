#!/usr/bin/env python3
"""
Group API - 그룹 협업 기능 API
fastapi_server.py에 통합되는 그룹 관리 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Callable
import os

from models.report_models import DatabaseManager
from services.group_service import GroupService
from services.group_report_service import GroupReportService
from services.prompt_service import PromptService
from agent.monthly_report_agent import MonthlyReportAgent
from openai import AzureOpenAI
from database_models import User

# 데이터베이스 초기화
db_manager = DatabaseManager(os.getenv('REPORTS_DB_PATH', 'reports.db'))
db_manager.create_tables()


# Request/Response 모델
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


class CategoryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    order_index: int = 999


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CategoryReorderRequest(BaseModel):
    category_orders: List[dict]  # [{"id": 1, "order_index": 0}, ...]


def create_group_router(get_current_user: Callable) -> APIRouter:
    """
    그룹 API 라우터 생성 (Factory 함수)

    Args:
        get_current_user: fastapi_server.py의 get_current_user dependency

    Returns:
        APIRouter
    """
    router = APIRouter(prefix="/api/v2", tags=["groups"])

    @router.get("/groups")
    async def get_user_groups(current_user: User = Depends(get_current_user)):
        """사용자의 그룹 목록 조회"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            groups = group_service.get_user_groups(current_user.id)
            return {"success": True, "groups": groups}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.post("/groups")
    async def create_group(
        request: GroupCreateRequest,
        current_user: User = Depends(get_current_user)
    ):
        """그룹 생성"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            group = group_service.create_group(
                user_id=current_user.id,
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
        current_user: User = Depends(get_current_user)
    ):
        """그룹 상세 조회"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            detail = group_service.get_group_detail(group_id=group_id, user_id=current_user.id)
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
        current_user: User = Depends(get_current_user)
    ):
        """멤버 추가"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            member = group_service.add_member(
                group_id=group_id,
                owner_id=current_user.id,
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
        current_user: User = Depends(get_current_user)
    ):
        """멤버 제거"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            success = group_service.remove_member(
                group_id=group_id,
                owner_id=current_user.id,
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
        current_user: User = Depends(get_current_user)
    ):
        """그룹 수정"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            group = group_service.update_group(
                group_id=group_id,
                user_id=current_user.id,
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
        current_user: User = Depends(get_current_user)
    ):
        """그룹 삭제"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            success = group_service.delete_group(group_id=group_id, user_id=current_user.id)
            return {"success": success, "message": "그룹이 삭제되었습니다"}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.get("/groups/{group_id}/categories")
    async def get_group_categories(
        group_id: int,
        current_user: User = Depends(get_current_user)
    ):
        """그룹 카테고리 목록 조회"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            categories = group_service.get_group_categories(group_id=group_id, user_id=current_user.id)
            return {"success": True, "categories": categories}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.post("/groups/{group_id}/categories")
    async def add_group_category(
        group_id: int,
        request: CategoryCreateRequest,
        current_user: User = Depends(get_current_user)
    ):
        """카테고리 추가 (owner만)"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            category = group_service.add_category(
                group_id=group_id,
                user_id=current_user.id,
                name=request.name,
                description=request.description,
                order_index=request.order_index
            )
            return {"success": True, "category": category}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.put("/groups/{group_id}/categories/{category_id}")
    async def update_group_category(
        group_id: int,
        category_id: int,
        request: CategoryUpdateRequest,
        current_user: User = Depends(get_current_user)
    ):
        """카테고리 수정 (owner만)"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            category = group_service.update_category(
                group_id=group_id,
                user_id=current_user.id,
                category_id=category_id,
                name=request.name,
                description=request.description
            )
            return {"success": True, "category": category}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.delete("/groups/{group_id}/categories/{category_id}")
    async def delete_group_category(
        group_id: int,
        category_id: int,
        current_user: User = Depends(get_current_user)
    ):
        """카테고리 삭제 (owner만)"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            success = group_service.delete_category(
                group_id=group_id,
                user_id=current_user.id,
                category_id=category_id
            )
            return {"success": success, "message": "카테고리가 삭제되었습니다"}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.put("/groups/{group_id}/categories/reorder")
    async def reorder_group_categories(
        group_id: int,
        request: CategoryReorderRequest,
        current_user: User = Depends(get_current_user)
    ):
        """카테고리 순서 변경 (owner만)"""
        session = db_manager.get_session()
        try:
            group_service = GroupService(session)
            categories = group_service.reorder_categories(
                group_id=group_id,
                user_id=current_user.id,
                category_orders=request.category_orders
            )
            return {"success": True, "categories": categories}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    @router.post("/groups/{group_id}/reports/generate")
    async def generate_group_report(
        group_id: int,
        request: GroupReportGenerateRequest,
        current_user: User = Depends(get_current_user)
    ):
        """그룹 보고서 생성"""
        session = db_manager.get_session()
        try:
            azure_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )

            agent = MonthlyReportAgent(
                azure_client=azure_client,
                user_id=current_user.id,
                deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
                db_path=os.getenv("DB_PATH", "tickets.db")
            )

            prompt_service = PromptService(session)
            group_service = GroupService(session)
            group_report_service = GroupReportService(
                session,
                agent,
                prompt_service,
                group_service
            )

            result = group_report_service.generate_group_report(
                user_id=current_user.id,
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

    return router
