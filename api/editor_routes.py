#!/usr/bin/env python3
"""
Dashboard Routes - 통합 대시보드 UI 라우트
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from pathlib import Path
import os

router = APIRouter(tags=["dashboard"])

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).parent.parent


@router.get("/editor")
async def editor_page():
    """
    통합 대시보드 페이지 반환

    브라우저에서 /editor 접속 시 통합 월간보고 자동화 시스템 표시
    - JQL 관리
    - 프롬프트 관리
    - 템플릿 에디터 (Monaco Editor)
    - 보고서 생성
    - 보고서 목록
    """
    html_path = BASE_DIR / "frontend" / "static" / "dashboard.html"

    if not html_path.exists():
        return {"error": "Dashboard page not found", "path": str(html_path)}

    return FileResponse(html_path)


@router.get("/report-editor")
async def report_editor_page():
    """
    HTML 보고서 에디터 페이지 반환

    브라우저에서 /report-editor 접속 시 TinyMCE 기반 WYSIWYG 에디터 표시
    - 보고서 파일 불러오기/저장
    - HTML 편집 (표, 서식 등)
    - 미리보기 기능
    """
    html_path = BASE_DIR / "frontend" / "static" / "editor.html"

    if not html_path.exists():
        return {"error": "Report editor page not found", "path": str(html_path)}

    # HTML 파일 읽기
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # TinyMCE API 키 주입
    tinymce_key = os.getenv('TINYMCE_KEY', 'no-api-key')
    html_content = html_content.replace('no-api-key', tinymce_key)

    return HTMLResponse(content=html_content)


@router.get("/")
async def root():
    """
    루트 페이지 - 대시보드로 리다이렉트
    """
    return RedirectResponse(url="/editor")
