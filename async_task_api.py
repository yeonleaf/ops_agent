#!/usr/bin/env python3
"""
비동기 작업 관리를 위한 FastAPI 엔드포인트
"""

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from async_task_models import AsyncTaskManager
from async_ticket_processor import start_async_ticket_creation

# 로깅 설정
logger = logging.getLogger(__name__)

# FastAPI 앱 인스턴스
app = FastAPI(title="Async Task Management API", version="1.0.0")

# Request/Response 모델들
class CreateTicketTaskRequest(BaseModel):
    user_id: str = "default_user"
    provider_name: str = "gmail"
    user_query: Optional[str] = None
    access_token: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    user_id: str
    overall_status: str
    steps: list
    final_result: Optional[dict] = None
    created_at: str
    updated_at: str

class CreateTaskResponse(BaseModel):
    task_id: str
    message: str
    status: str

# 글로벌 태스크 매니저
task_manager = AsyncTaskManager()

@app.post("/tasks/create-tickets", response_model=CreateTaskResponse)
async def create_ticket_task(request: CreateTicketTaskRequest, background_tasks: BackgroundTasks):
    """
    티켓 생성 작업을 비동기로 시작
    """
    try:
        logger.info(f"🚀 새로운 티켓 생성 작업 요청: user_id={request.user_id}")

        # 1. 새로운 작업 생성
        task_id = task_manager.create_task(
            user_id=request.user_id,
            steps=[
                {"step_name": "이메일 수집", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
                {"step_name": "메일 분류", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
                {"step_name": "Jira 티켓 발행", "status": "PENDING", "log": None, "started_at": None, "completed_at": None}
            ]
        )

        # 2. 백그라운드에서 비동기 처리 시작
        logger.info(f"🧵 백그라운드 작업 시작: task_id={task_id}")

        # mem0_memory 초기화 시도
        mem0_memory = None
        try:
            import sys
            if hasattr(sys.modules.get('__main__', object()), 'mem0_memory'):
                mem0_memory = sys.modules['__main__'].mem0_memory
            else:
                from mem0_memory_adapter import create_mem0_memory
                mem0_memory = create_mem0_memory("ticket_ui")
        except Exception as e:
            logger.warning(f"⚠️ mem0_memory 초기화 실패, 계속 진행: {e}")

        # 백그라운드에서 실제 처리 시작
        background_tasks.add_task(
            start_async_ticket_creation,
            task_id=task_id,
            provider_name=request.provider_name,
            user_query=request.user_query,
            mem0_memory=mem0_memory,
            access_token=request.access_token
        )

        logger.info(f"✅ 작업 생성 및 시작 완료: task_id={task_id}")

        return CreateTaskResponse(
            task_id=task_id,
            message="티켓 생성 작업이 시작되었습니다. 진행 상황을 확인하려면 상태 조회 API를 사용하세요.",
            status="PENDING"
        )

    except Exception as e:
        logger.error(f"❌ 작업 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 생성 실패: {str(e)}")

@app.get("/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    작업 상태 조회
    """
    try:
        logger.info(f"🔍 작업 상태 조회: task_id={task_id}")

        task = task_manager.get_task(task_id)
        if not task:
            logger.warning(f"⚠️ 작업을 찾을 수 없음: task_id={task_id}")
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

        return TaskResponse(
            task_id=task.task_id,
            user_id=task.user_id,
            overall_status=task.overall_status,
            steps=task.steps,
            final_result=task.final_result,
            created_at=task.created_at,
            updated_at=task.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 작업 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 상태 조회 실패: {str(e)}")

@app.get("/tasks/user/{user_id}")
async def get_user_tasks(user_id: str, status: Optional[str] = None):
    """
    사용자의 모든 작업 조회
    """
    try:
        logger.info(f"🔍 사용자 작업 목록 조회: user_id={user_id}, status={status}")

        tasks = task_manager.get_user_tasks(user_id, status)

        return {
            "user_id": user_id,
            "total_tasks": len(tasks),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "overall_status": task.overall_status,
                    "steps": task.steps,
                    "final_result": task.final_result,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at
                }
                for task in tasks
            ]
        }

    except Exception as e:
        logger.error(f"❌ 사용자 작업 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"사용자 작업 목록 조회 실패: {str(e)}")

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    작업 삭제
    """
    try:
        logger.info(f"🗑️ 작업 삭제 요청: task_id={task_id}")

        success = task_manager.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없거나 삭제에 실패했습니다.")

        return {"message": f"작업 {task_id}가 성공적으로 삭제되었습니다.", "success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 작업 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 삭제 실패: {str(e)}")

@app.get("/health")
async def health_check():
    """
    API 상태 확인
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "비동기 작업 관리 API가 정상적으로 동작 중입니다."
    }

# 앱 시작시 테이블 초기화 확인
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 실행"""
    logger.info("🚀 비동기 작업 관리 API 시작")
    task_manager.init_database()
    logger.info("✅ 데이터베이스 초기화 완료")

if __name__ == "__main__":
    import uvicorn

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/async_api.log'),
            logging.StreamHandler()
        ]
    )

    logger.info("🌟 비동기 작업 관리 API 서버 시작")
    uvicorn.run(app, host="0.0.0.0", port=8001)