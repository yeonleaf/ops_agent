#!/usr/bin/env python3
"""
Report Editor API - HTML 보고서 편집 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from pathlib import Path
import html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editor", tags=["editor"])

# 보고서 저장 디렉토리
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


class ReportContent(BaseModel):
    content: str


class SaveAsRequest(BaseModel):
    filename: str
    content: str


def sanitize_filename(filename: str) -> str:
    """
    파일명 검증 및 정제 (경로 순회 공격 방지)

    Args:
        filename: 입력 파일명

    Returns:
        정제된 파일명

    Raises:
        ValueError: 유효하지 않은 파일명
    """
    # 경로 구분자 제거
    filename = os.path.basename(filename)

    # HTML 파일만 허용
    if not filename.endswith('.html'):
        filename += '.html'

    # 위험한 문자 제거
    dangerous_chars = ['..', '/', '\\', '\0']
    for char in dangerous_chars:
        if char in filename:
            raise ValueError(f"Invalid filename: contains '{char}'")

    return filename


@router.get("/reports")
async def list_reports() -> List[str]:
    """
    보고서 디렉토리의 모든 HTML 파일 목록 반환

    Returns:
        HTML 파일명 리스트
    """
    try:
        files = []
        for file in REPORTS_DIR.glob("*.html"):
            files.append(file.name)

        # 최신 파일 우선 정렬
        files.sort(key=lambda x: (REPORTS_DIR / x).stat().st_mtime, reverse=True)

        logger.info(f"✅ 보고서 목록 조회: {len(files)}개 파일")
        return files

    except Exception as e:
        logger.error(f"❌ 보고서 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/save-as")
async def save_report_as(request: SaveAsRequest) -> dict:
    """
    새 파일명으로 보고서 저장

    Args:
        request: SaveAsRequest (filename과 content)

    Returns:
        {"success": True, "filename": "저장된 파일명"}
    """
    try:
        # 파일명 검증
        safe_filename = sanitize_filename(request.filename)
        file_path = REPORTS_DIR / safe_filename

        # 파일이 이미 존재하는지 확인
        if file_path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"File already exists: {safe_filename}"
            )

        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)

        logger.info(f"✅ 보고서 다른 이름으로 저장: {safe_filename}")
        return {
            "success": True,
            "filename": safe_filename,
            "message": f"파일이 '{safe_filename}'로 저장되었습니다."
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 보고서 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{filename}")
async def get_report(filename: str) -> dict:
    """
    특정 보고서 파일의 HTML 내용 반환

    Args:
        filename: 파일명

    Returns:
        {"content": "HTML 문자열", "filename": "파일명"}
    """
    try:
        # 파일명 검증
        safe_filename = sanitize_filename(filename)
        file_path = REPORTS_DIR / safe_filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {safe_filename}")

        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        logger.info(f"✅ 보고서 로드: {safe_filename}")
        return {
            "content": content,
            "filename": safe_filename
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 보고서 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/{filename}")
async def save_report(filename: str, request: ReportContent) -> dict:
    """
    보고서 파일 저장 (덮어쓰기)

    Args:
        filename: 파일명
        request: ReportContent (content 필드에 HTML)

    Returns:
        {"success": True, "filename": "저장된 파일명"}
    """
    try:
        # 파일명 검증
        safe_filename = sanitize_filename(filename)
        file_path = REPORTS_DIR / safe_filename

        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)

        logger.info(f"✅ 보고서 저장: {safe_filename}")
        return {
            "success": True,
            "filename": safe_filename,
            "message": "파일이 성공적으로 저장되었습니다."
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 보고서 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reports/{filename}")
async def delete_report(filename: str) -> dict:
    """
    보고서 파일 삭제

    Args:
        filename: 파일명

    Returns:
        {"success": True, "message": "삭제 완료"}
    """
    try:
        # 파일명 검증
        safe_filename = sanitize_filename(filename)
        file_path = REPORTS_DIR / safe_filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {safe_filename}")

        # 파일 삭제
        file_path.unlink()

        logger.info(f"✅ 보고서 삭제: {safe_filename}")
        return {
            "success": True,
            "message": f"'{safe_filename}' 파일이 삭제되었습니다."
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 보고서 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
