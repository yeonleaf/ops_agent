#!/usr/bin/env python3
"""
Report Server - 월간보고서 생성 서버

독립 실행형 FastAPI 서버입니다.
정적 파일 서빙과 API 엔드포인트를 제공합니다.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Report API 라우터
from report_api import router as report_router

# FastAPI 앱 생성
app = FastAPI(
    title="월간보고 자동화 시스템",
    description="LLM Agent 기반 월간보고서 자동 생성 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Report API 라우터 등록
app.include_router(report_router)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """루트 경로 - index.html 반환"""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """헬스 체크"""
    return {
        "status": "ok",
        "service": "report-server",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 월간보고 자동화 시스템 서버 시작")
    print("=" * 80)
    print()
    print("📍 접속 주소:")
    print("   - 웹 UI: http://localhost:8003")
    print("   - API 문서: http://localhost:8003/docs")
    print("   - 헬스 체크: http://localhost:8003/health")
    print()
    print("📋 API 엔드포인트:")
    print("   - POST /api/generate-report : 보고서 생성")
    print("   - GET  /api/components       : 컴포넌트 목록 조회")
    print("   - GET  /api/structure        : 보고서 구조 조회")
    print()
    print("=" * 80)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info"
    )
