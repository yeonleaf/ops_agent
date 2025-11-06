#!/usr/bin/env python3
"""
Dynamic Report Server - 멀티유저 동적 보고서 시스템 서버

통합 FastAPI 서버
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# API 라우터
from api.dynamic_report_api import router as dynamic_router

# FastAPI 앱 생성
app = FastAPI(
    title="멀티유저 월간보고 자동화 시스템",
    description="프롬프트 기반 동적 보고서 생성 시스템",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(dynamic_router)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """루트 - 로그인 페이지로 리다이렉트"""
    return RedirectResponse(url="/login.html")


@app.get("/login.html")
async def login_page():
    """로그인 페이지"""
    return FileResponse("static/login.html")


@app.get("/report-builder.html")
async def report_builder_page():
    """보고서 빌더 페이지"""
    return FileResponse("static/report-builder.html")


@app.get("/app.html")
async def app_page():
    """메인 앱 페이지"""
    # 실제로는 app.html을 만들어야 하지만, 데모를 위해 간단한 페이지 반환
    html_content = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>월간보고 생성기</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #4CAF50;
        }
        .header h1 { color: #2c3e50; }
        .user-info { color: #7f8c8d; }
        .btn {
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
        }
        .btn:hover { background: #45a049; }
        .section {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 6px;
        }
        .section h2 { color: #2c3e50; margin-bottom: 15px; }
        .info { color: #7f8c8d; line-height: 1.8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 월간보고 생성기</h1>
            <div class="user-info">
                <span id="username"></span>
                <button class="btn" onclick="logout()">로그아웃</button>
            </div>
        </div>

        <div class="section">
            <h2>🎉 시스템 구축 완료!</h2>
            <div class="info">
                <p><strong>멀티유저 동적 보고서 시스템</strong>이 성공적으로 구축되었습니다.</p>
                <br>
                <p><strong>구현된 기능:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>✅ 회원가입/로그인 (JWT 인증)</li>
                    <li>✅ 프롬프트 관리 (생성/수정/삭제)</li>
                    <li>✅ 공개 프롬프트 공유</li>
                    <li>✅ 동적 보고서 생성 (프롬프트 조합)</li>
                    <li>✅ 보고서 히스토리 저장</li>
                    <li>✅ Drag & Drop 보고서 빌더</li>
                </ul>
                <br>
                <p><strong>🚀 시작하기:</strong></p>
                <div style="margin: 20px 0;">
                    <a href="/report-builder.html" style="display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        📊 보고서 빌더 열기
                    </a>
                </div>
                <br>
                <p><strong>API 엔드포인트:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>POST /api/v2/auth/register - 회원가입</li>
                    <li>POST /api/v2/auth/login - 로그인</li>
                    <li>GET /api/v2/prompts - 프롬프트 목록</li>
                    <li>POST /api/v2/prompts - 프롬프트 생성</li>
                    <li>PUT /api/v2/prompts/:id - 프롬프트 수정</li>
                    <li>DELETE /api/v2/prompts/:id - 프롬프트 삭제</li>
                    <li>POST /api/v2/prompts/:id/execute - 단일 프롬프트 실행</li>
                    <li>POST /api/v2/reports/execute-batch - 일괄 실행</li>
                    <li>POST /api/v2/reports/generate-from-results - 결과 조합</li>
                    <li>POST /api/v2/reports/generate - 보고서 생성</li>
                    <li>GET /api/v2/reports - 보고서 목록</li>
                </ul>
                <br>
                <p>API 문서: <a href="/docs" target="_blank">http://localhost:8004/docs</a></p>
            </div>
        </div>
    </div>

    <script>
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/login.html';
        }

        document.getElementById('username').textContent = localStorage.getItem('username');

        function logout() {
            localStorage.clear();
            window.location.href = '/login.html';
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health():
    """헬스 체크"""
    return {
        "status": "ok",
        "service": "dynamic-report-server",
        "version": "2.0.0"
    }


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 멀티유저 월간보고 자동화 시스템 서버 시작")
    print("=" * 80)
    print()
    print("📍 접속 주소:")
    print("   - 웹 UI: http://localhost:8004")
    print("   - 로그인: http://localhost:8004/login.html")
    print("   - API 문서: http://localhost:8004/docs")
    print()
    print("📋 주요 기능:")
    print("   - 회원가입/로그인 (JWT 인증)")
    print("   - 프롬프트 관리 (CRUD)")
    print("   - 동적 보고서 생성")
    print("   - 보고서 히스토리")
    print()
    print("=" * 80)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8004,
        log_level="info"
    )
