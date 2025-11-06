#!/usr/bin/env python3
"""
Report API - 월간보고서 생성 API

FastAPI 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import os
import logging

# Azure OpenAI 설정
from openai import AzureOpenAI

# 보고서 생성 모듈
from report_structure import get_report_structure
from report_utils import filter_structure, validate_components
from component_generator import ComponentGenerator
from report_builder import ReportBuilder
from agent.monthly_report_agent import MonthlyReportAgent


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# API Router 생성
router = APIRouter(prefix="/api", tags=["report"])


# Request/Response 모델
class GenerateReportRequest(BaseModel):
    components: List[str]
    year: int = None
    month: int = None
    user_id: int = 1  # 기본값


class GenerateReportResponse(BaseModel):
    success: bool
    html: str = None
    error: str = None
    metadata: dict = None


# Azure OpenAI 클라이언트 초기화 (환경 변수에서 가져오기)
def get_azure_client():
    """Azure OpenAI 클라이언트 생성"""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    if not api_key or not azure_endpoint:
        raise ValueError("Azure OpenAI 환경 변수가 설정되지 않았습니다.")

    return AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint
    )


# Agent 초기화
def create_agent(user_id: int):
    """MonthlyReportAgent 생성"""
    azure_client = get_azure_client()
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    db_path = os.getenv("DB_PATH", "tickets.db")

    return MonthlyReportAgent(
        azure_client=azure_client,
        user_id=user_id,
        deployment_name=deployment_name,
        db_path=db_path
    )


@router.post("/generate-report", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest):
    """
    월간보고서 생성 API

    Args:
        request: {
            "components": ["operation_status", "ncms_bmt", ...],
            "year": 2025,  # 선택적
            "month": 9,    # 선택적
            "user_id": 1   # 선택적
        }

    Returns:
        {
            "success": true,
            "html": "<!DOCTYPE html>...",
            "metadata": {
                "component_count": 3,
                "generation_time": 45.2
            }
        }
    """
    logger.info(f"📊 보고서 생성 요청 받음: {len(request.components)}개 컴포넌트")
    logger.info(f"   선택된 컴포넌트: {', '.join(request.components)}")

    try:
        # 1. 구조 생성
        structure = get_report_structure(request.year, request.month)

        # 2. 컴포넌트 검증
        validation = validate_components(structure, request.components)
        if not validation["valid"]:
            logger.error(f"❌ 컴포넌트 검증 실패: {validation['message']}")
            raise HTTPException(status_code=400, detail=validation["message"])

        # 3. 구조 필터링
        filtered_structure = filter_structure(structure, request.components)
        logger.info(f"✅ 구조 필터링 완료: {len(request.components)}개 컴포넌트")

        # 4. Agent 생성
        agent = create_agent(request.user_id)
        logger.info(f"✅ Agent 초기화 완료 (user_id={request.user_id})")

        # 5. ComponentGenerator와 ReportBuilder 생성
        generator = ComponentGenerator(agent=agent, prompts_dir="prompts/")
        builder = ReportBuilder(component_generator=generator)
        logger.info(f"✅ Generator와 Builder 초기화 완료")

        # 6. 보고서 빌드
        logger.info(f"🚀 보고서 빌드 시작...")
        html_report = builder.build(filtered_structure)
        logger.info(f"✅ 보고서 빌드 완료")

        # 7. 메타데이터 생성
        metadata = {
            "component_count": len(request.components),
            "title": filtered_structure.get("title", ""),
            "date": filtered_structure.get("date", "")
        }

        logger.info(f"✨ 보고서 생성 완료!")

        return GenerateReportResponse(
            success=True,
            html=html_report,
            metadata=metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 보고서 생성 실패: {str(e)}")
        import traceback
        traceback.print_exc()

        return GenerateReportResponse(
            success=False,
            error=str(e)
        )


@router.get("/components")
async def get_available_components():
    """
    사용 가능한 컴포넌트 목록 조회

    Returns:
        {
            "components": [
                {
                    "name": "operation_status",
                    "description": "전체 운영 업무 현황",
                    "prompt_file": "operation_status.txt"
                },
                ...
            ]
        }
    """
    try:
        structure = get_report_structure()
        components = []

        for section in structure.get("sections", []):
            if "components" in section:
                components.extend(section["components"])

            if "subsections" in section:
                for subsection in section["subsections"]:
                    if "components" in subsection:
                        components.extend(subsection["components"])

        return {
            "components": components
        }
    except Exception as e:
        logger.error(f"❌ 컴포넌트 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure")
async def get_report_structure_api(year: int = None, month: int = None):
    """
    보고서 구조 조회

    Args:
        year: 연도 (선택적)
        month: 월 (선택적)

    Returns:
        보고서 구조 딕셔너리
    """
    try:
        structure = get_report_structure(year, month)
        return structure
    except Exception as e:
        logger.error(f"❌ 보고서 구조 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 테스트용 엔드포인트
@router.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "ok",
        "service": "report-api",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    print("Report API 모듈")
    print("FastAPI 서버에 router를 포함시켜야 합니다:")
    print("  from report_api import router")
    print("  app.include_router(router)")
