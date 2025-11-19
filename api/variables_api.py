#!/usr/bin/env python3
"""
Variables API - 전역 변수 관리
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import List, Optional
import re
import logging

from api.dynamic_report_api import get_current_user
from models.report_models import DatabaseManager, Variable, PromptTemplate
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/variables", tags=["variables"])

# 데이터베이스 초기화
db_manager = DatabaseManager(os.getenv('REPORTS_DB_PATH', 'reports.db'))


# Request/Response 모델
class VariableCreate(BaseModel):
    name: str
    value: str
    description: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        """변수명 유효성 검사"""
        if not v:
            raise ValueError('변수명은 필수입니다')

        # 영문자로 시작, 영문자/숫자/언더스코어만 허용
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            raise ValueError('변수명은 영문자로 시작해야 하며, 영문자/숫자/언더스코어만 사용할 수 있습니다')

        # 길이 제한
        if len(v) > 100:
            raise ValueError('변수명은 100자를 초과할 수 없습니다')

        return v


class VariableUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None


class VariableResponse(BaseModel):
    id: int
    name: str
    value: str
    description: Optional[str]
    created_at: str
    updated_at: str


class VariableUsage(BaseModel):
    prompt_id: int
    prompt_title: str
    usage_location: str  # 'prompt_content' 또는 'jql'


# 변수 CRUD API

@router.get("", response_model=List[VariableResponse])
async def get_variables():
    """
    모든 변수 목록 조회
    """
    session = db_manager.get_session()

    try:
        variables = session.query(Variable).order_by(Variable.name).all()
        return [var.to_dict() for var in variables]

    except Exception as e:
        logger.error(f"❌ 변수 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("", response_model=VariableResponse)
async def create_variable(request: VariableCreate):
    """
    새 변수 생성
    """
    session = db_manager.get_session()

    try:
        # 중복 확인
        existing = session.query(Variable).filter_by(name=request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"이미 존재하는 변수명입니다: {request.name}")

        # 변수 생성
        new_variable = Variable(
            name=request.name,
            value=request.value,
            description=request.description
        )

        session.add(new_variable)
        session.commit()
        session.refresh(new_variable)

        logger.info(f"✅ 변수 생성: {request.name} = {request.value}")

        return new_variable.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"❌ 변수 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{variable_name}", response_model=VariableResponse)
async def get_variable(variable_name: str):
    """
    특정 변수 조회
    """
    session = db_manager.get_session()

    try:
        variable = session.query(Variable).filter_by(name=variable_name).first()

        if not variable:
            raise HTTPException(status_code=404, detail=f"변수를 찾을 수 없습니다: {variable_name}")

        return variable.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 변수 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/{variable_name}", response_model=VariableResponse)
async def update_variable(variable_name: str, request: VariableUpdate):
    """
    변수 값 또는 설명 수정
    """
    session = db_manager.get_session()

    try:
        variable = session.query(Variable).filter_by(name=variable_name).first()

        if not variable:
            raise HTTPException(status_code=404, detail=f"변수를 찾을 수 없습니다: {variable_name}")

        # 업데이트할 필드가 하나도 없으면 에러
        if request.value is None and request.description is None:
            raise HTTPException(status_code=400, detail="업데이트할 필드가 없습니다")

        # 값 업데이트
        if request.value is not None:
            variable.value = request.value

        if request.description is not None:
            variable.description = request.description

        session.commit()
        session.refresh(variable)

        logger.info(f"✅ 변수 업데이트: {variable_name}")

        return variable.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"❌ 변수 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{variable_name}")
async def delete_variable(variable_name: str, force: bool = False):
    """
    변수 삭제

    Args:
        variable_name: 삭제할 변수명
        force: 강제 삭제 여부 (사용 중인 변수도 삭제)
    """
    session = db_manager.get_session()

    try:
        variable = session.query(Variable).filter_by(name=variable_name).first()

        if not variable:
            raise HTTPException(status_code=404, detail=f"변수를 찾을 수 없습니다: {variable_name}")

        # 사용 현황 확인 (force가 아닐 때)
        if not force:
            usage = _check_variable_usage(session, variable_name)

            if usage:
                # 사용 중인 프롬프트가 있으면 에러
                prompt_titles = [u['prompt_title'] for u in usage]
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": f"이 변수는 {len(usage)}개 프롬프트에서 사용 중입니다",
                        "prompts": prompt_titles,
                        "suggestion": "force=true 파라미터를 추가하여 강제 삭제할 수 있습니다"
                    }
                )

        # 변수 삭제
        session.delete(variable)
        session.commit()

        logger.info(f"✅ 변수 삭제: {variable_name}")

        return {"message": f"변수 '{variable_name}'가 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"❌ 변수 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{variable_name}/usage", response_model=List[VariableUsage])
async def get_variable_usage(variable_name: str):
    """
    특정 변수가 사용되는 프롬프트 목록 조회
    """
    session = db_manager.get_session()

    try:
        usage = _check_variable_usage(session, variable_name)
        return usage

    except Exception as e:
        logger.error(f"❌ 변수 사용 현황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# 헬퍼 함수

def _check_variable_usage(session, variable_name: str) -> List[dict]:
    """
    변수가 사용되는 프롬프트 목록 확인

    Args:
        session: SQLAlchemy 세션
        variable_name: 확인할 변수명

    Returns:
        사용 중인 프롬프트 정보 리스트
    """
    usage = []
    pattern = f"{{{{{variable_name}}}}}"  # {{변수명}} 패턴

    # 모든 프롬프트 조회
    prompts = session.query(PromptTemplate).all()

    for prompt in prompts:
        if pattern in prompt.prompt_content:
            usage.append({
                "prompt_id": prompt.id,
                "prompt_title": prompt.title,
                "usage_location": "prompt_content"
            })

    return usage
