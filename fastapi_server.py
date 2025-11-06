#!/usr/bin/env python3
"""
사용자 인증 API 서버
회원가입, 로그인, 외부 서비스 연동 관리
"""
import re
from fastapi import FastAPI, HTTPException, Depends, Cookie, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import uvicorn
from datetime import datetime
import os
import logging
import json
import uuid
import threading
import requests
import httpx
from urllib.parse import urlparse, parse_qs, urlencode, quote
import dotenv
from slack_sdk.web import WebClient
from slack_sdk.signature import SignatureVerifier
from fastmcp import Client
from database_models import DatabaseManager, User
from auth_utils import password_manager, token_encryption, session_manager
import datefinder
from dateutil.parser import parse as dateutil_parse
import dateparser

# .env 파일 로드 (반드시 os.getenv() 호출 전에 실행)
dotenv.load_dotenv()

# FastMCP 클라이언트 설정
mcp = Client("http://127.0.0.1:8001/mcp")

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# OAuth 환경 변수 설정
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")

# Kakao OAuth 설정
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8002/auth/kakao/link/callback")

# Slack OAuth 설정
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URL", os.getenv("SLACK_REDIRECT_URI", "http://localhost:8002/auth/slack/link/callback"))

# 카카오 환경 변수 디버그 로깅
logging.info(f"🔧 Kakao OAuth 설정 로드됨:")
logging.info(f"  - KAKAO_CLIENT_ID: {'설정됨' if KAKAO_CLIENT_ID else '❌ 없음'}")
logging.info(f"  - KAKAO_CLIENT_SECRET: {'설정됨' if KAKAO_CLIENT_SECRET else '❌ 없음'}")
logging.info(f"  - KAKAO_REDIRECT_URI: {KAKAO_REDIRECT_URI}")

# 슬랙 환경 변수 디버그 로깅
logging.info(f"🔧 Slack OAuth 설정 로드됨:")
logging.info(f"  - SLACK_CLIENT_ID: {'설정됨' if SLACK_CLIENT_ID else '❌ 없음'} (값: {SLACK_CLIENT_ID[:10] + '...' if SLACK_CLIENT_ID and len(SLACK_CLIENT_ID) > 10 else SLACK_CLIENT_ID})")
logging.info(f"  - SLACK_CLIENT_SECRET: {'설정됨' if SLACK_CLIENT_SECRET else '❌ 없음'} (길이: {len(SLACK_CLIENT_SECRET) if SLACK_CLIENT_SECRET else 0})")
logging.info(f"  - SLACK_REDIRECT_URI: {SLACK_REDIRECT_URI}")

# OAuth 콜백 설정 (Auth 서버와 동일한 포트 사용)
AUTH_SERVER_PORT = 8002
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"http://localhost:{AUTH_SERVER_PORT}/auth/callback")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", f"http://localhost:{AUTH_SERVER_PORT}/auth/callback")

# 세션 시크릿 키 (환경 변수에서 가져오거나 랜덤 생성)
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", os.urandom(32).hex())

app = FastAPI(title="Ops Agent FastAPI", version="1.0.0")

# SessionMiddleware 추가 (CORS보다 먼저 추가해야 함)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="fastapi_session",
    max_age=86400,  # 24시간
    same_site="lax",
    https_only=False  # 개발 환경에서는 False, 프로덕션에서는 True
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],  # Streamlit 앱과 React 앱
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터베이스 관리자
db_manager = DatabaseManager()

# === OAuth 임시 저장소 (메모리) ===
# 세션 ID를 키로 하여 OAuth 인증 정보를 임시 저장
# 카카오: {session_id: {"kakao_id": ..., "user_id": ..., "timestamp": ..., "purpose": "bot_user_mapping"}}
# 슬랙: {session_id: {"user_id": ..., "timestamp": ..., "purpose": "slack_link"}}
kakao_temp_storage = {}
slack_temp_storage = {}

# === Pydantic 모델들 ===

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    user_name: str
    system_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class JiraIntegrationRequest(BaseModel):
    jira_endpoint: str
    jira_api_token: str

class GoogleTokenByEmailRequest(BaseModel):
    email: EmailStr
    refresh_token: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    email: Optional[str] = None

# === 의존성 함수들 ===

def get_current_user(session_id: Optional[str] = Cookie(None)) -> User:
    """현재 로그인된 사용자 조회"""
    if not session_id:
        raise HTTPException(status_code=401, detail="세션이 없습니다")
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다")
    
    user = db_manager.get_user_by_id(session['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
    
    return user

# === API 엔드포인트들 ===

@app.post("/auth/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """회원가입"""
    try:
        # 이메일 중복 확인
        if db_manager.user_exists(request.email):
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다")
        
        # 비밀번호 해시 처리
        password_hash = password_manager.hash_password(request.password)
        
        # 사용자 생성
        user = User(
            id=None,
            email=request.email,
            password_hash=password_hash,
            user_name=request.user_name,
            system_name=request.system_name,
            created_at=datetime.now().isoformat()
        )
        
        user_id = db_manager.insert_user(user)
        
        return AuthResponse(
            success=True,
            message="회원가입이 완료되었습니다",
            user_id=user_id,
            email=request.email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"회원가입 중 오류가 발생했습니다: {str(e)}")

@app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response):
    """로그인"""
    try:
        # 사용자 조회
        user = db_manager.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        
        # 비밀번호 검증
        if not password_manager.verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        
        # 세션 생성
        session_id = session_manager.create_session(user.id, user.email)
        
        # HttpOnly 쿠키로 세션 ID 전송
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # HTTPS에서는 True로 설정
            samesite="lax",
            max_age=86400  # 24시간
        )
        
        return AuthResponse(
            success=True,
            message="로그인 성공",
            user_id=user.id,
            email=user.email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그인 중 오류가 발생했습니다: {str(e)}")

@app.post("/auth/logout")
async def logout(response: Response, session_id: Optional[str] = Cookie(None)):
    """로그아웃"""
    if session_id:
        session_manager.delete_session(session_id)
    
    # 쿠키 삭제
    response.delete_cookie(key="session_id")
    
    return {"success": True, "message": "로그아웃 완료"}

@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """현재 사용자 정보 조회"""
    # Integration 테이블에서 연동 정보 확인
    gmail_integrations = db_manager.get_integrations_by_source(current_user.id, 'gmail')
    jira_integrations = db_manager.get_integrations_by_source(current_user.id, 'jira')

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "has_google_token": len(gmail_integrations) > 0,
        "has_jira_info": len(jira_integrations) > 0,
        "created_at": current_user.created_at
    }

# === 카카오 계정 연동 엔드포인트들 ===

@app.get("/settings/link/kakao")
async def link_kakao_account(
    request: Request,
    session_id: Optional[str] = None,
    current_user: Optional[User] = None
):
    """카카오 계정 연동 시작 (로그인한 사용자만 접근 가능)"""
    try:
        # 1. URL 파라미터로 전달된 session_id 확인
        if session_id:
            logging.info(f"URL 파라미터로 session_id 수신: {session_id}")
            session = session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다")

            user = db_manager.get_user_by_id(session['user_id'])
            if not user:
                raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

            current_user = user
        else:
            # 2. 쿠키에서 session_id 확인
            cookie_session_id = request.cookies.get("session_id")
            if not cookie_session_id:
                raise HTTPException(status_code=401, detail="세션이 없습니다")

            session = session_manager.get_session(cookie_session_id)
            if not session:
                raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다")

            user = db_manager.get_user_by_id(session['user_id'])
            if not user:
                raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

            current_user = user

        logging.info(f"카카오 연동 시작: user_id={current_user.id}, email={current_user.email}")

        # 세션에 현재 사용자 ID 저장
        request.session["pending_kakao_link_user_id"] = current_user.id
        logging.info(f"세션에 사용자 ID 저장: {current_user.id}")

        # 카카오 OAuth 인증 URL 생성
        kakao_auth_url = (
            f"https://kauth.kakao.com/oauth/authorize?"
            f"client_id={KAKAO_CLIENT_ID}&"
            f"redirect_uri={quote(KAKAO_REDIRECT_URI)}&"
            f"response_type=code"
        )

        logging.info(f"카카오 OAuth URL로 리다이렉트: {kakao_auth_url}")
        return RedirectResponse(url=kakao_auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"카카오 연동 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"카카오 연동 시작 중 오류가 발생했습니다: {str(e)}")

@app.get("/auth/kakao/bot-link")
async def link_kakao_bot_account(request: Request, session_id: str):
    """카카오 봇 계정 연동 시작 (botUserKey 매핑용)"""
    try:
        logging.info(f"카카오 봇 연동 시작: session_id={session_id}")

        # 임시 저장소에서 botUserKey 확인
        bot_data = kakao_temp_storage.get(session_id)
        if not bot_data or bot_data.get("purpose") != "bot_user_mapping":
            raise HTTPException(status_code=400, detail="유효하지 않은 세션입니다")

        # FastAPI 세션에 bot_user_session_id 저장 (콜백에서 사용)
        request.session["pending_bot_user_session_id"] = session_id
        logging.info(f"세션에 bot_user_session_id 저장: {session_id}")

        # 카카오 OAuth 인증 URL 생성 (별도 콜백 사용)
        kakao_bot_redirect_uri = "http://localhost:8002/auth/kakao/bot-link/callback"
        kakao_auth_url = (
            f"https://kauth.kakao.com/oauth/authorize?"
            f"client_id={KAKAO_CLIENT_ID}&"
            f"redirect_uri={quote(kakao_bot_redirect_uri)}&"
            f"response_type=code"
        )

        logging.info(f"카카오 봇 OAuth URL로 리다이렉트: {kakao_auth_url}")
        return RedirectResponse(url=kakao_auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"카카오 봇 연동 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"카카오 봇 연동 시작 중 오류가 발생했습니다: {str(e)}")

@app.get("/auth/kakao/bot-link/callback", response_class=HTMLResponse)
async def kakao_bot_link_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """카카오 봇 계정 연동 콜백 처리 - botUserKey와 kakao_id 매핑"""
    try:
        logging.info(f"카카오 봇 연동 콜백 수신: code={code is not None}, error={error}")

        # 세션에서 bot_user_session_id 가져오기
        bot_user_session_id = request.session.get("pending_bot_user_session_id")
        logging.info(f"세션에서 bot_user_session_id 가져옴: {bot_user_session_id}")

        if not bot_user_session_id:
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 카카오 연동 오류</h1>
                    <p>세션 정보를 찾을 수 없습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        # 임시 저장소에서 botUserKey 가져오기
        bot_data = kakao_temp_storage.get(bot_user_session_id)
        if not bot_data:
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 카카오 연동 오류</h1>
                    <p>봇 사용자 정보를 찾을 수 없습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        bot_user_key = bot_data.get("bot_user_key")
        logging.info(f"botUserKey 조회: {bot_user_key}")

        # 오류 처리
        if error:
            logging.error(f"카카오 OAuth 오류: {error}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>오류: {error}</p>
                </body>
                </html>
                """,
                status_code=400
            )

        if not code:
            logging.error("카카오 OAuth 콜백: code 파라미터 없음")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>인증 코드가 없습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        # Authorization Code를 Access Token으로 교환
        token_url = "https://kauth.kakao.com/oauth/token"
        kakao_bot_redirect_uri = "http://localhost:8002/auth/kakao/bot-link/callback"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "client_secret": KAKAO_CLIENT_SECRET,
            "redirect_uri": kakao_bot_redirect_uri,
            "code": code
        }

        logging.info(f"카카오 토큰 교환 요청 시작")
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)

        if token_response.status_code != 200:
            logging.error(f"카카오 토큰 교환 실패: {token_response.text}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 카카오 연동 오류</h1>
                    <p>토큰 교환에 실패했습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        logging.info(f"카카오 Access Token 획득 성공")

        # Access Token으로 사용자 정보 가져오기
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(user_info_url, headers=headers)

        if user_info_response.status_code != 200:
            logging.error(f"카카오 사용자 정보 조회 실패: {user_info_response.text}")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 카카오 연동 오류</h1>
                    <p>사용자 정보 조회에 실패했습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        user_info = user_info_response.json()
        kakao_id = str(user_info.get("id"))
        logging.info(f"카카오 사용자 정보: kakao_id={kakao_id}")

        # kakao_id로 integration 테이블에서 app_user_id 조회
        app_user_id = db_manager.get_user_id_by_kakao_id(kakao_id)

        if not app_user_id:
            logging.error(f"kakao_id로 app_user_id를 찾을 수 없음: kakao_id={kakao_id}")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 카카오 연동 오류</h1>
                    <p>먼저 웹 페이지에서 카카오 계정을 연동해주세요.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        # botUserKey와 app_user_id 매핑 저장
        from database_models import Integration
        bot_user_integration = Integration(
            id=None,
            user_id=app_user_id,
            source='kakao',
            type='botUserKey',
            value=bot_user_key,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(bot_user_integration)
        logging.info(f"✅ botUserKey 매핑 저장 완료: app_user_id={app_user_id}, bot_user_key={bot_user_key}")

        # 임시 저장소에서 삭제
        del kakao_temp_storage[bot_user_session_id]
        request.session.pop("pending_bot_user_session_id", None)

        # 성공 페이지 반환
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>카카오 계정 연동 완료</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; padding: 20px; }}
                    .success {{ color: #2e7d32; font-size: 24px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <h1 class="success">✅ 카카오 계정 연동 완료!</h1>
                <p>이제 카카오톡 챗봇에서 티켓을 생성할 수 있습니다.</p>
                <p>이 창을 닫고 챗봇으로 돌아가서 다시 시도해주세요.</p>
                <script>setTimeout(() => window.close(), 3000);</script>
            </body>
            </html>
            """
        )

    except Exception as e:
        logging.error(f"카카오 봇 연동 콜백 처리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>카카오 연동 오류</title>
                <meta charset="utf-8">
            </head>
            <body>
                <h1>❌ 카카오 연동 오류</h1>
                <p>내부 서버 오류: {str(e)}</p>
            </body>
            </html>
            """,
            status_code=500
        )

@app.get("/auth/kakao/link/callback/data")
async def kakao_link_callback_data(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """카카오 계정 연동 콜백 - JSON 데이터 반환"""
    try:
        logging.info(f"카카오 연동 콜백 (JSON) 수신: code={code is not None}, error={error}")

        # 오류 처리
        if error:
            logging.error(f"카카오 OAuth 오류: {error}")
            return {
                "success": False,
                "error": error,
                "message": f"카카오 OAuth 오류: {error}"
            }

        if not code:
            logging.error("카카오 OAuth 콜백: code 파라미터 없음")
            return {
                "success": False,
                "error": "no_code",
                "message": "인증 코드가 없습니다"
            }

        # Authorization Code를 Access Token으로 교환
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "client_secret": KAKAO_CLIENT_SECRET,
            "redirect_uri": KAKAO_REDIRECT_URI.replace("/callback", "/callback/data"),  # JSON 엔드포인트로 변경
            "code": code
        }

        logging.info(f"카카오 토큰 교환 요청 시작")
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)

        if token_response.status_code != 200:
            logging.error(f"카카오 토큰 교환 실패: {token_response.text}")
            return {
                "success": False,
                "error": "token_exchange_failed",
                "message": f"토큰 교환 실패: {token_response.text}"
            }

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        logging.info(f"카카오 Access Token 획득 성공")

        # Access Token으로 사용자 정보 가져오기
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(user_info_url, headers=headers)

        if user_info_response.status_code != 200:
            logging.error(f"카카오 사용자 정보 조회 실패: {user_info_response.text}")
            return {
                "success": False,
                "error": "user_info_failed",
                "message": "사용자 정보 조회 실패"
            }

        user_info = user_info_response.json()
        logging.info(f"카카오 사용자 정보: {user_info}")
        kakao_id = user_info.get("id")
        kakao_email = user_info.get("kakao_account", {}).get("email")
        kakao_nickname = user_info.get("properties", {}).get("nickname")

        logging.info(f"카카오 사용자 정보: id={kakao_id}, email={kakao_email}, nickname={kakao_nickname}")

        # JSON 응답 반환
        return {
            "success": True,
            "access_token": access_token,
            "kakao_id": str(kakao_id) if kakao_id else None,
            "kakao_email": kakao_email,
            "kakao_nickname": kakao_nickname
        }

    except Exception as e:
        logging.error(f"카카오 연동 콜백 처리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "internal_error",
            "message": f"내부 서버 오류: {str(e)}"
        }

@app.get("/auth/kakao/link/callback", response_class=HTMLResponse)
async def kakao_link_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """카카오 계정 연동 콜백 처리 - HTML 페이지 반환 + 임시 저장소에 저장"""
    try:
        logging.info(f"카카오 연동 콜백 수신: code={code is not None}, error={error}")

        # 세션에서 pending_kakao_link_user_id 가져오기 (연동 시작할 때 저장됨)
        user_id = request.session.get("pending_kakao_link_user_id")
        logging.info(f"세션에서 user_id 가져옴: {user_id}")

        # 오류 처리
        if error:
            logging.error(f"카카오 OAuth 오류: {error}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: #d32f2f; font-size: 18px; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>오류: {error}</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        if not code:
            logging.error("카카오 OAuth 콜백: code 파라미터 없음")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                        .error { color: #d32f2f; font-size: 18px; }
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>인증 코드가 없습니다.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        # 2. Authorization Code를 Access Token으로 교환
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "client_secret": KAKAO_CLIENT_SECRET,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "code": code
        }

        logging.info(f"카카오 토큰 교환 요청 시작")
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)

        if token_response.status_code != 200:
            logging.error(f"카카오 토큰 교환 실패: {token_response.text}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: #d32f2f; font-size: 18px; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>토큰 교환에 실패했습니다.</p>
                    <p>상세 내용: {token_response.text}</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        logging.info(f"카카오 Access Token 획득 성공")

        # 3. Access Token으로 사용자 정보 가져오기
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(user_info_url, headers=headers)

        if user_info_response.status_code != 200:
            logging.error(f"카카오 사용자 정보 조회 실패: {user_info_response.text}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>카카오 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: #d32f2f; font-size: 18px; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 카카오 연동 오류</h1>
                    <p>사용자 정보 조회에 실패했습니다.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        user_info = user_info_response.json()
        logging.info(f"카카오 사용자 정보: {user_info}")
        kakao_id = user_info.get("id")
        kakao_email = user_info.get("kakao_account", {}).get("email")
        kakao_nickname = user_info.get("properties", {}).get("nickname")

        logging.info(f"카카오 사용자 정보: id={kakao_id}, email={kakao_email}, nickname={kakao_nickname}")

        # 4. 임시 저장소에 카카오 정보 저장 (세션 ID를 키로 사용)
        # 브라우저 세션 쿠키에서 세션 ID 가져오기
        fastapi_session_id = request.cookies.get("fastapi_session")
        if not fastapi_session_id:
            # 세션 쿠키가 없으면 새로 생성
            fastapi_session_id = str(uuid.uuid4())
            logging.warning(f"세션 쿠키가 없어서 새로 생성: {fastapi_session_id}")

        # 임시 저장소에 카카오 정보 저장 (카카오 ID만 저장)
        from datetime import datetime as dt
        kakao_temp_storage[fastapi_session_id] = {
            "kakao_id": str(kakao_id) if kakao_id else None,
            "user_id": user_id,  # 연동 시작할 때 세션에 저장된 user_id
            "timestamp": dt.now().isoformat()
        }
        logging.info(f"임시 저장소에 카카오 정보 저장: session_id={fastapi_session_id}, kakao_id={kakao_id}, user_id={user_id}")

        # 5. 세션에서 pending_kakao_link_user_id 삭제
        request.session.pop("pending_kakao_link_user_id", None)

        # 6. HTML 응답 반환 (임시 저장소 키를 포함)
        response = HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>카카오 인증 완료</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; padding: 20px; }}
                    .success {{ color: #2e7d32; font-size: 24px; margin-bottom: 20px; }}
                    .session-id {{
                        background: #f5f5f5;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 20px auto;
                        max-width: 600px;
                        word-break: break-all;
                    }}
                    .session-label {{
                        font-weight: bold;
                        color: #666;
                        margin-bottom: 10px;
                    }}
                    .session-value {{
                        font-family: monospace;
                        font-size: 14px;
                        color: #000;
                        background: white;
                        padding: 10px;
                        border: 2px solid #ddd;
                        border-radius: 4px;
                    }}
                    .copy-btn {{
                        background: #4CAF50;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-top: 10px;
                    }}
                    .copy-btn:hover {{
                        background: #45a049;
                    }}
                    .debug-info {{
                        background: #fff3cd;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 20px auto;
                        max-width: 600px;
                        text-align: left;
                        font-size: 12px;
                    }}
                </style>
            </head>
            <body>
                <h1 class="success">✅ 카카오 인증 완료!</h1>
                <p>카카오 계정 인증이 완료되었습니다.</p>

                <div class="session-id">
                    <div class="session-label">📋 아래 세션 ID를 복사하세요:</div>
                    <div class="session-value" id="sessionId">{fastapi_session_id}</div>
                    <button class="copy-btn" onclick="copySessionId()">📋 복사하기</button>
                </div>

                <div class="debug-info">
                    <strong>🔍 디버깅 정보:</strong><br>
                    - 카카오 ID: {kakao_id or '없음'}<br>
                    - User ID: {user_id or '세션에서 가져오지 못함'}
                </div>

                <p>이 창을 닫고 원래 페이지로 돌아가서 세션 ID를 입력해주세요.</p>
                <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>

                <script>
                    function copySessionId() {{
                        const sessionId = document.getElementById('sessionId').innerText;
                        navigator.clipboard.writeText(sessionId).then(() => {{
                            alert('세션 ID가 복사되었습니다!\\n\\n' + sessionId);
                        }}).catch(err => {{
                            alert('복사 실패. 수동으로 복사해주세요.');
                        }});
                    }}

                    // 5초 후 자동으로 창 닫기 (선택사항)
                    // setTimeout(() => window.close(), 5000);
                </script>
            </body>
            </html>
            """
        )

        # 세션 쿠키 설정 (Streamlit에서 읽을 수 있도록)
        response.set_cookie(
            key="kakao_session_id",
            value=fastapi_session_id,
            httponly=False,  # JavaScript에서 읽을 수 있도록
            secure=False,
            samesite="lax",
            max_age=300  # 5분
        )

        return response

    except Exception as e:
        logging.error(f"카카오 연동 콜백 처리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>카카오 연동 오류</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                    .error {{ color: #d32f2f; font-size: 18px; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ 카카오 연동 오류</h1>
                <p>내부 서버 오류: {str(e)}</p>
                <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
            </body>
            </html>
            """,
            status_code=500
        )

@app.get("/auth/kakao/temp")
async def get_kakao_temp_data(kakao_session_id: Optional[str] = None):
    """임시 저장소에서 카카오 인증 정보 조회"""
    try:
        logging.info(f"🔍 카카오 임시 데이터 조회 요청: session_id={kakao_session_id}")
        logging.info(f"📦 현재 임시 저장소에 있는 키들: {list(kakao_temp_storage.keys())}")

        if not kakao_session_id:
            logging.warning("❌ 세션 ID가 없습니다")
            return {
                "success": False,
                "message": "세션 ID가 없습니다",
                "debug": {
                    "available_keys": list(kakao_temp_storage.keys())
                }
            }

        # 임시 저장소에서 데이터 조회
        kakao_data = kakao_temp_storage.get(kakao_session_id)

        if not kakao_data:
            logging.warning(f"❌ 카카오 인증 정보를 찾을 수 없습니다: {kakao_session_id}")
            logging.warning(f"📦 사용 가능한 키: {list(kakao_temp_storage.keys())}")
            return {
                "success": False,
                "message": "카카오 인증 정보를 찾을 수 없습니다",
                "debug": {
                    "requested_key": kakao_session_id,
                    "available_keys": list(kakao_temp_storage.keys()),
                    "storage_size": len(kakao_temp_storage)
                }
            }

        logging.info(f"✅ 카카오 임시 데이터 조회 성공")
        logging.info(f"📋 데이터: kakao_email={kakao_data.get('kakao_email')}, user_id={kakao_data.get('user_id')}")

        return {
            "success": True,
            "data": kakao_data
        }

    except Exception as e:
        logging.error(f"❌ 카카오 임시 데이터 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"오류: {str(e)}",
            "debug": {
                "error_type": type(e).__name__,
                "available_keys": list(kakao_temp_storage.keys())
            }
        }

@app.delete("/auth/kakao/temp")
async def delete_kakao_temp_data(kakao_session_id: Optional[str] = None):
    """임시 저장소에서 카카오 인증 정보 삭제"""
    try:
        logging.info(f"카카오 임시 데이터 삭제 요청: session_id={kakao_session_id}")

        if not kakao_session_id:
            return {
                "success": False,
                "message": "세션 ID가 없습니다"
            }

        # 임시 저장소에서 삭제
        if kakao_session_id in kakao_temp_storage:
            del kakao_temp_storage[kakao_session_id]
            logging.info(f"카카오 임시 데이터 삭제 완료: session_id={kakao_session_id}")
            return {
                "success": True,
                "message": "삭제 완료"
            }
        else:
            return {
                "success": False,
                "message": "데이터를 찾을 수 없습니다"
            }

    except Exception as e:
        logging.error(f"카카오 임시 데이터 삭제 오류: {e}")
        return {
            "success": False,
            "message": f"오류: {str(e)}"
        }

@app.post("/user/integrations/kakao")
async def save_kakao_integration(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """카카오 연동 정보 저장 (카카오 ID만 저장)"""
    try:
        from database_models import Integration

        # 요청 본문에서 카카오 ID 추출
        body = await request.json()
        kakao_id = body.get("kakao_id")

        logging.info(f"카카오 연동 저장 요청: user_id={current_user.id}, kakao_id={kakao_id}")

        # 카카오 ID 저장
        if kakao_id:
            kakao_id_integration = Integration(
                id=None,
                user_id=current_user.id,
                source='kakao',
                type='id',
                value=str(kakao_id),
                created_at=None,
                updated_at=None
            )
            db_manager.insert_integration(kakao_id_integration)
            logging.info(f"✅ 카카오 ID 저장 완료: user_id={current_user.id}, kakao_id={kakao_id}")

            return {
                "success": True,
                "message": "카카오 ID가 저장되었습니다",
                "kakao_id": kakao_id
            }
        else:
            logging.warning(f"⚠️ 카카오 ID가 없습니다: user_id={current_user.id}")
            return {
                "success": False,
                "message": "카카오 ID가 없습니다"
            }

    except Exception as e:
        logging.error(f"❌ 카카오 연동 저장 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"카카오 연동 저장 중 오류가 발생했습니다: {str(e)}")

@app.get("/user/integrations/kakao")
async def get_kakao_integration(current_user: User = Depends(get_current_user)):
    """카카오 연동 정보 조회"""
    try:
        # Integration 테이블에서 카카오 설정 조회
        kakao_integrations = db_manager.get_integrations_by_source(current_user.id, 'kakao')

        if not kakao_integrations:
            return {
                "success": False,
                "message": "카카오 연동 정보가 없습니다",
                "linked": False
            }

        # 카카오 연동 정보 구성
        kakao_data = {"linked": True}
        for integration in kakao_integrations:
            if integration.type == 'id':
                kakao_data['kakao_id'] = integration.value
            elif integration.type == 'email':
                kakao_data['kakao_email'] = integration.value
            elif integration.type == 'nickname':
                kakao_data['kakao_nickname'] = integration.value

        return {
            "success": True,
            **kakao_data
        }

    except Exception as e:
        logging.error(f"카카오 연동 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"카카오 연동 정보 조회 중 오류가 발생했습니다: {str(e)}")

# === 슬랙 계정 연동 엔드포인트들 ===

@app.get("/settings/link/slack")
async def link_slack_account(
    request: Request,
    session_id: Optional[str] = None,
    current_user: Optional[User] = None
):
    """슬랙 계정 연동 시작 (로그인한 사용자만 접근 가능)"""
    try:
        # 1. URL 파라미터로 전달된 session_id 확인
        if session_id:
            logging.info(f"URL 파라미터로 session_id 수신: {session_id}")
            session = session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다")

            user = db_manager.get_user_by_id(session['user_id'])
            if not user:
                raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

            current_user = user
        else:
            # 2. 쿠키에서 session_id 확인
            cookie_session_id = request.cookies.get("session_id")
            if not cookie_session_id:
                raise HTTPException(status_code=401, detail="세션이 없습니다")

            session = session_manager.get_session(cookie_session_id)
            if not session:
                raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다")

            user = db_manager.get_user_by_id(session['user_id'])
            if not user:
                raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

            current_user = user

        logging.info(f"슬랙 연동 시작: user_id={current_user.id}, email={current_user.email}")

        # 임시 저장소에 사용자 ID 저장 (UUID 세션 ID 생성)
        slack_session_id = str(uuid.uuid4())
        slack_temp_storage[slack_session_id] = {
            "user_id": current_user.id,
            "timestamp": datetime.now().isoformat(),
            "purpose": "slack_link"
        }
        logging.info(f"임시 저장소에 사용자 ID 저장: session_id={slack_session_id}, user_id={current_user.id}")

        # 슬랙 OAuth 인증 URL 생성 (state에 slack_session_id 포함)
        # 필요한 스코프: identity.basic, identity.email, identity.team, identity.avatar
        slack_auth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={SLACK_CLIENT_ID}&"
            f"redirect_uri={quote(SLACK_REDIRECT_URI)}&"
            f"scope=users:read,users:read.email&"
            f"user_scope=identity.basic,identity.email,identity.team,identity.avatar&"
            f"state={slack_session_id}"
        )

        logging.info(f"슬랙 OAuth URL로 리다이렉트: {slack_auth_url}")
        return RedirectResponse(url=slack_auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"슬랙 연동 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"슬랙 연동 시작 중 오류가 발생했습니다: {str(e)}")

@app.get("/auth/slack/link/callback", response_class=HTMLResponse)
async def slack_link_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None, state: Optional[str] = None):
    """슬랙 계정 연동 콜백 처리 - access_token 및 user_id 저장"""
    try:
        logging.info(f"슬랙 연동 콜백 수신: code={code is not None}, error={error}, state={state}")

        # state에서 slack_session_id 가져오기
        slack_session_id = state
        if not slack_session_id:
            logging.error("슬랙 OAuth 콜백: state 파라미터 없음")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                        .error { color: #d32f2f; font-size: 18px; }
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 슬랙 연동 오류</h1>
                    <p>세션 정보를 찾을 수 없습니다.</p>
                    <p>다시 슬랙 연동을 시도해주세요.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        # 임시 저장소에서 사용자 정보 가져오기
        slack_data = slack_temp_storage.get(slack_session_id)
        if not slack_data:
            logging.error(f"슬랙 OAuth 콜백: 임시 저장소에 데이터 없음 (session_id={slack_session_id})")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                        .error { color: #d32f2f; font-size: 18px; }
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 슬랙 연동 오류</h1>
                    <p>연동 정보를 찾을 수 없습니다.</p>
                    <p>다시 슬랙 연동을 시도해주세요.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        user_id = slack_data.get("user_id")
        logging.info(f"임시 저장소에서 user_id 가져옴: {user_id}")

        # 오류 처리
        if error:
            logging.error(f"슬랙 OAuth 오류: {error}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: #d32f2f; font-size: 18px; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 슬랙 연동 오류</h1>
                    <p>오류: {error}</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        if not code:
            logging.error("슬랙 OAuth 콜백: code 파라미터 없음")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                        .error { color: #d32f2f; font-size: 18px; }
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 슬랙 연동 오류</h1>
                    <p>인증 코드가 없습니다.</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        # Authorization Code를 Access Token으로 교환
        token_url = "https://slack.com/api/oauth.v2.access"
        token_data = {
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": SLACK_REDIRECT_URI
        }

        logging.info(f"슬랙 토큰 교환 요청 시작")
        logging.info(f"  - client_id: {SLACK_CLIENT_ID[:10] + '...' if SLACK_CLIENT_ID and len(SLACK_CLIENT_ID) > 10 else SLACK_CLIENT_ID}")
        logging.info(f"  - client_secret 길이: {len(SLACK_CLIENT_SECRET) if SLACK_CLIENT_SECRET else 0}")
        logging.info(f"  - redirect_uri: {SLACK_REDIRECT_URI}")

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)

        if token_response.status_code != 200:
            logging.error(f"슬랙 토큰 교환 실패: {token_response.text}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: #d32f2f; font-size: 18px; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ 슬랙 연동 오류</h1>
                    <p>토큰 교환에 실패했습니다.</p>
                    <p>상세 내용: {token_response.text}</p>
                    <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        tokens = token_response.json()

        # Slack OAuth v2 응답 구조
        if not tokens.get("ok"):
            logging.error(f"슬랙 OAuth 오류: {tokens.get('error', 'unknown')}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 슬랙 연동 오류</h1>
                    <p>OAuth 응답 오류: {tokens.get('error', 'unknown')}</p>
                </body>
                </html>
                """,
                status_code=400
            )

        # authed_user에서 access_token과 user_id 추출
        authed_user = tokens.get("authed_user", {})
        access_token = authed_user.get("access_token")
        slack_user_id = authed_user.get("id")

        logging.info(f"슬랙 Access Token 획득 성공: user_id={slack_user_id}")

        if not access_token or not slack_user_id:
            logging.error("슬랙 토큰 또는 사용자 ID가 없습니다")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>슬랙 연동 오류</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 슬랙 연동 오류</h1>
                    <p>토큰 또는 사용자 ID를 찾을 수 없습니다.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        # Integration 테이블에 저장
        from database_models import Integration

        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(access_token)

        # Slack User ID 저장
        slack_id_integration = Integration(
            id=None,
            user_id=user_id,
            source='slack',
            type='user_id',
            value=str(slack_user_id),
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(slack_id_integration)

        # Slack Access Token 저장
        slack_token_integration = Integration(
            id=None,
            user_id=user_id,
            source='slack',
            type='token',
            value=encrypted_token,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(slack_token_integration)

        logging.info(f"✅ 슬랙 연동 정보 저장 완료: user_id={user_id}, slack_user_id={slack_user_id}")

        # 임시 저장소에서 삭제
        del slack_temp_storage[slack_session_id]
        logging.info(f"임시 저장소에서 세션 삭제: {slack_session_id}")

        # 성공 페이지 반환
        return HTMLResponse(
            content="""
            <html>
            <head>
                <title>슬랙 계정 연동 완료</title>
                <meta charset="utf-8">
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; padding: 20px; }
                    .success { color: #2e7d32; font-size: 24px; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <h1 class="success">✅ 슬랙 계정 연동 완료!</h1>
                <p>이제 슬랙에서 티켓을 생성할 수 있습니다.</p>
                <p>이 창을 닫고 원래 페이지로 돌아가세요.</p>
                <script>setTimeout(() => window.close(), 3000);</script>
            </body>
            </html>
            """
        )

    except Exception as e:
        logging.error(f"슬랙 연동 콜백 처리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>슬랙 연동 오류</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                    .error {{ color: #d32f2f; font-size: 18px; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ 슬랙 연동 오류</h1>
                <p>내부 서버 오류: {str(e)}</p>
                <p><a href="http://localhost:8501">홈으로 돌아가기</a></p>
            </body>
            </html>
            """,
            status_code=500
        )

@app.get("/user/integrations/slack")
async def get_slack_integration(current_user: User = Depends(get_current_user)):
    """슬랙 연동 정보 조회"""
    try:
        # Integration 테이블에서 슬랙 설정 조회
        slack_integrations = db_manager.get_integrations_by_source(current_user.id, 'slack')

        if not slack_integrations:
            return {
                "success": False,
                "message": "슬랙 연동 정보가 없습니다",
                "linked": False
            }

        # 슬랙 연동 정보 구성
        slack_data = {"linked": True}
        for integration in slack_integrations:
            if integration.type == 'user_id':
                slack_data['slack_user_id'] = integration.value
            elif integration.type == 'token':
                slack_data['has_token'] = True

        return {
            "success": True,
            **slack_data
        }

    except Exception as e:
        logging.error(f"슬랙 연동 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"슬랙 연동 정보 조회 중 오류가 발생했습니다: {str(e)}")

@app.post("/user/integrations/jira")
async def update_jira_integration(
    request: JiraIntegrationRequest,
    current_user: User = Depends(get_current_user)
):
    """Jira 연동 정보 저장"""
    try:
        from database_models import Integration

        # API 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.jira_api_token)

        # Jira Endpoint 저장
        endpoint_integration = Integration(
            id=None,
            user_id=current_user.id,
            source='jira',
            type='endpoint',
            value=request.jira_endpoint,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(endpoint_integration)

        # Jira Token 저장
        token_integration = Integration(
            id=None,
            user_id=current_user.id,
            source='jira',
            type='token',
            value=encrypted_token,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(token_integration)

        # 기존 User 테이블도 업데이트 (하위 호환성)
        db_manager.update_user_jira_info(
            current_user.id,
            request.jira_endpoint,
            encrypted_token
        )

        return {
            "success": True,
            "message": "Jira 연동 정보가 저장되었습니다"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Jira 연동 정보 저장 중 오류가 발생했습니다: {str(e)}")

@app.get("/user/integrations/jira")
async def get_jira_integration(current_user: User = Depends(get_current_user)):
    """Jira 연동 정보 조회 (Integration 테이블만 사용)"""
    try:
        # Integration 테이블에서 Jira 설정 조회
        jira_integrations = db_manager.get_integrations_by_source(current_user.id, 'jira')

        if not jira_integrations:
            return {
                "success": False,
                "message": "Jira 연동 정보가 없습니다",
                "has_api_token": False,
                "has_projects": False,
                "has_labels": False,
                "is_complete": False
            }

        # Integration 테이블 데이터로 응답 구성
        jira_data = {
            "has_api_token": False,
            "has_projects": False,
            "has_labels": False
        }

        for integration in jira_integrations:
            if integration.type == 'endpoint':
                jira_data['jira_endpoint'] = integration.value
            elif integration.type == 'token':
                jira_data['has_api_token'] = True
            elif integration.type == 'project':
                jira_data['has_projects'] = True
            elif integration.type == 'labels':
                jira_data['has_labels'] = True

        # 모든 단계가 완료되었는지 확인
        jira_data['is_complete'] = (
            jira_data['has_api_token'] and
            jira_data['has_projects'] and
            jira_data['has_labels']
        )

        return {
            "success": True,
            **jira_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Jira 연동 정보 조회 중 오류가 발생했습니다: {str(e)}")

@app.post("/user/integrations/google")
async def update_google_token(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Google Refresh Token 저장"""
    try:
        from database_models import Integration

        # 요청 본문에서 refresh_token 추출
        body = await request.body()
        form_data = body.decode('utf-8')
        refresh_token = None

        for param in form_data.split('&'):
            if param.startswith('refresh_token='):
                refresh_token = param.split('=', 1)[1]
                break

        if not refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token이 필요합니다")

        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(refresh_token)

        # Integration 테이블에 저장
        token_integration = Integration(
            id=None,
            user_id=current_user.id,
            source='gmail',
            type='token',
            value=encrypted_token,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(token_integration)

        # 기존 User 테이블도 업데이트 (하위 호환성)
        db_manager.update_user_google_token(current_user.id, encrypted_token)

        return {
            "success": True,
            "message": "Google 연동 정보가 저장되었습니다"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google 연동 정보 저장 중 오류가 발생했습니다: {str(e)}")

@app.post("/user/integrations/google/by-email")
async def update_google_token_by_email(request: GoogleTokenByEmailRequest):
    """이메일로 Google Refresh Token 저장 (OAuth 콜백용)"""
    try:
        from database_models import Integration

        # 이메일로 사용자 조회
        user = db_manager.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.refresh_token)

        # Integration 테이블에 저장
        token_integration = Integration(
            id=None,
            user_id=user.id,
            source='gmail',
            type='token',
            value=encrypted_token,
            created_at=None,
            updated_at=None
        )
        db_manager.insert_integration(token_integration)

        return {
            "success": True,
            "message": f"Google 연동 정보가 업데이트되었습니다: {request.email}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google 연동 정보 업데이트 실패: {str(e)}")

@app.get("/user/integrations/google")
async def get_google_integration(current_user: User = Depends(get_current_user)):
    """Google 연동 정보 조회"""
    try:
        # Integration 테이블에서 Gmail 설정 조회
        gmail_integrations = db_manager.get_integrations_by_source(current_user.id, 'gmail')

        if not gmail_integrations:
            return {
                "success": False,
                "message": "Google 연동 정보가 없습니다"
            }

        # Integration 테이블 데이터로 응답 구성
        has_token = False
        token_preview = None

        for integration in gmail_integrations:
            if integration.type == 'token':
                has_token = True
                try:
                    decrypted_token = token_encryption.decrypt_token(integration.value)
                    token_preview = decrypted_token[:10] + "..."
                except:
                    pass

        return {
            "success": True,
            "has_refresh_token": has_token,
            "token_preview": token_preview
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google 연동 정보 조회 중 오류가 발생했습니다: {str(e)}")

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# === OAuth 관련 기능들 ===

@app.get("/auth/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    provider: str = "gmail"
):
    """OAuth 콜백 처리"""
    try:
        logging.info(f"OAuth 콜백 요청: provider={provider}, code={code is not None}, state={state is not None}, error={error}")

        if error:
            # OAuth 오류 처리
            logging.error(f"OAuth 오류: {error}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>OAuth Error</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: red; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ OAuth Error</h1>
                    <p>OAuth Error: {error}</p>
                </body>
                </html>
                """,
                status_code=400
            )

        if not code or not state:
            # 파라미터 오류
            logging.error("OAuth 콜백 오류: code 또는 state 파라미터가 없습니다.")
            return HTMLResponse(
                content="""
                <html>
                <head>
                    <title>OAuth Error</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: red; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ OAuth Error</h1>
                    <p>OAuth Callback Error: Missing code or state parameter.</p>
                </body>
                </html>
                """,
                status_code=400
            )

        # Authorization Code를 토큰으로 교환
        result = await process_oauth_callback(code, state, provider)

        if result["success"]:
            # 성공 페이지
            logging.info(f"OAuth 콜백 성공: {provider}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>OAuth 인증 완료</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .success {{ color: green; }}
                    </style>
                </head>
                <body>
                    <h1 class="success">✅ OAuth 인증 완료!</h1>
                    <p>{result["message"]}</p>
                    <p>이 창을 닫아도 됩니다.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                </body>
                </html>
                """
            )
        else:
            # 실패 페이지
            logging.error(f"OAuth 토큰 교환 실패: {result}")
            return HTMLResponse(
                content=f"""
                <html>
                <head>
                    <title>OAuth Error</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                        .error {{ color: red; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">❌ OAuth Error</h1>
                    <p>OAuth Token Exchange Failed: {result.get('message', 'Unknown error')}</p>
                </body>
                </html>
                """,
                status_code=400
            )

    except Exception as e:
        logging.error(f"OAuth 콜백 처리 중 예외 발생: {e}")
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>OAuth Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                    .error {{ color: red; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ OAuth Error</h1>
                <p>Internal Server Error: {e}</p>
            </body>
            </html>
            """,
            status_code=500
        )

async def process_oauth_callback(code: str, state: Optional[str], provider: str = "gmail") -> dict:
    """OAuth 콜백 처리 - Authorization Code를 Access Token으로 교환"""
    try:
        logging.info(f"OAuth 콜백 처리 시작: {provider}")

        # state에서 사용자 이메일 추출
        user_email = "user@example.com"  # 기본값
        if state:
            try:
                state_data = json.loads(state)
                user_email = state_data.get("user_email", user_email)
            except:
                pass

        # 제공자별 토큰 교환 설정
        if provider.lower() == "gmail":
            token_url = "https://oauth2.googleapis.com/token"
            client_id = GOOGLE_CLIENT_ID
            client_secret = GOOGLE_CLIENT_SECRET
            redirect_uri = GOOGLE_REDIRECT_URI
        elif provider.lower() == "microsoft":
            token_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
            client_id = MICROSOFT_CLIENT_ID
            client_secret = MICROSOFT_CLIENT_SECRET
            redirect_uri = MICROSOFT_REDIRECT_URI
        else:
            return {"success": False, "message": "Unsupported OAuth provider"}

        # 토큰 교환 요청
        token_data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(token_url, data=token_data)

        if response.status_code == 200:
            tokens = response.json()
            refresh_token = tokens.get("refresh_token")

            if refresh_token:
                # 리프레시 토큰을 데이터베이스에 저장
                await save_oauth_token(user_email, refresh_token)

                logging.info(f"OAuth 토큰 교환 성공: {provider}")
                return {
                    "success": True,
                    "message": f"{provider.upper()} OAuth 인증이 완료되었습니다.",
                    "user_email": user_email
                }

        return {
            "success": False,
            "message": f"토큰 교환에 실패했습니다: {response.text}"
        }

    except Exception as e:
        logging.error(f"OAuth 콜백 처리 실패: {e}")
        return {
            "success": False,
            "message": f"OAuth 인증 처리 중 오류가 발생했습니다: {e}"
        }

async def save_oauth_token(user_email: str, refresh_token: str):
    """OAuth 토큰을 Integration 테이블에 저장"""
    try:
        from database_models import Integration

        # 이메일로 사용자 조회
        user = db_manager.get_user_by_email(user_email)
        if not user:
            logging.error(f"사용자를 찾을 수 없습니다: {user_email}")
            return

        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(refresh_token)

        # 기존 Gmail 토큰 삭제 (있다면)
        existing_token = db_manager.get_integration(user.id, 'gmail', 'token')
        if existing_token:
            db_manager.delete_integration(existing_token.id)
            logging.info(f"기존 Gmail 토큰 삭제: {user_email}")

        # Integration 테이블에 저장
        gmail_integration = Integration(
            id=None,
            user_id=user.id,
            source='gmail',
            type='token',
            value=encrypted_token,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db_manager.insert_integration(gmail_integration)

        logging.info(f"OAuth 토큰 저장 성공 (Integration 테이블): {user_email}")

    except Exception as e:
        logging.error(f"OAuth 토큰 저장 중 오류: {e}")

# OAuth 로그인 URL 생성 endpoints
@app.get("/auth/login/gmail")
async def gmail_oauth_login(user_email: str = "unknown@example.com"):
    """Gmail OAuth 로그인 리다이렉트"""
    try:
        state = json.dumps({"user_email": user_email})

        # redirect_uri 디버그 로깅
        logging.info(f"🔍 GOOGLE_REDIRECT_URI 값: {GOOGLE_REDIRECT_URI}")

        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={quote(GOOGLE_REDIRECT_URI)}&"
            f"scope=openid profile email https://www.googleapis.com/auth/gmail.readonly&"
            f"response_type=code&"
            f"state={quote(state)}&"
            f"access_type=offline&"
            f"prompt=consent"
        )

        logging.info(f"📧 Gmail OAuth로 리다이렉트: {user_email}")
        logging.info(f"🔗 생성된 OAuth URL: {auth_url[:150]}...")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logging.error(f"❌ Gmail OAuth 리다이렉트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/login/microsoft")
async def microsoft_oauth_login(user_email: str = "unknown@example.com"):
    """Microsoft OAuth 로그인 리다이렉트"""
    try:
        state = json.dumps({"user_email": user_email})

        auth_url = (
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize?"
            f"client_id={MICROSOFT_CLIENT_ID}&"
            f"response_type=code&"
            f"redirect_uri={MICROSOFT_REDIRECT_URI}&"
            f"scope=openid profile email https://graph.microsoft.com/mail.read&"
            f"state={state}&"
            f"prompt=consent"
        )

        logging.info(f"Microsoft OAuth로 리다이렉트: {user_email}")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logging.error(f"❌ Microsoft OAuth 리다이렉트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# OAuth 인증 상태 확인
@app.get("/auth/oauth-status/{provider}")
async def check_oauth_status(provider: str, current_user: User = Depends(get_current_user)):
    """OAuth 인증 상태 확인"""
    try:
        if provider.lower() == "gmail":
            # Integration 테이블에서 Gmail 토큰 확인
            gmail_integrations = db_manager.get_integrations_by_source(current_user.id, 'gmail')
            has_token = len(gmail_integrations) > 0

            if has_token:
                # 토큰 유효성 검증 (선택사항)
                return {
                    "authenticated": True,
                    "message": "Gmail OAuth 인증이 완료되어 있습니다.",
                    "provider": "gmail"
                }
            else:
                # OAuth URL 생성
                auth_url = await gmail_oauth_login(current_user.email)
                return {
                    "authenticated": False,
                    "message": "Gmail OAuth 인증이 필요합니다.",
                    "auth_url": auth_url["auth_url"],
                    "provider": "gmail"
                }
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 OAuth 제공자입니다.")

    except Exception as e:
        logging.error(f"❌ OAuth 상태 확인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


client = WebClient(token=dotenv.get_key(".env", "SLACK_BOT_TOKEN"))
signature_verifier = SignatureVerifier(dotenv.get_key(".env", "SLACK_SIGNING_SECRET"))

async def make_ticket_data(original_text_parts: list):
    # 1. 문의 내용 (제목 재료)
    first_message = original_text_parts[0]
    middle_messages = original_text_parts[1:]

    # 제목 만들기
    title_prompt = f"""
    다음 고객 문의 내용을 바탕으로 Jira 티켓 제목으로 사용할 만한 핵심 내용을 한 줄로 요약해줘.

    문의 내용:
    {first_message.get('text', '')}
    """

    # LLM 호출
    async with mcp:

        ticket_title_result = await mcp.call_tool("simple_llm_call", {"prompt": title_prompt})
        ticket_title = ticket_title_result.content[0].text

        
        original_text = "\n".join([part.get('received_date', '') + " " + part.get('sender', '') + ": " + part.get('text', '') for part in original_text_parts])

        # 요약 생성
        summary_prompt = f"""
        다음은 고객 문의와 내부 댓글 대화 내용이야. 이 대화는 구어체로 작성되어 있어.\n
        이 내용을 아래 형식에 맞춰 구조화하고 요약해주세요\n
        1.핵심 문제 요약:\n
        2.문제의 상세 원인:\n
        3.논의된 해결 방안들:\n
        4.최종적으로 결정된 사항:\n
        5.각 인물별 역할 정리:\n
            
        고객 문의:  
        {first_message.get('text', '')}

        대화 내용:
        {original_text}
        """
        summary_text = await mcp.call_tool("simple_llm_call", {"prompt": summary_prompt}) # "요약 내용"

        ticket_body = f"""
        ### 💬 원문
        {original_text}

        ---

        ### 📝 요약
        {summary_text}
        """

        # sender 정보 추출
        email_data = {
            "id": first_message.get('client_msg_id', ''), # 원본 메시지 ID
            "subject": ticket_title,                       # 2단계에서 만든 제목
            "sender": first_message.get('user', ''),       # 문의를 시작한 사람
            "body": ticket_body,                           # 3단계에서 만든 본문
            "received_date": first_message.get('ts', '')   # 문의 시작 시간
        }
        
        return email_data


@app.post("/slack/events")
async def handle_slack_events(request: Request):

    # --- 1. Slack 요청 검증 (수정된 부분) ---
    body = await request.body()
    if not signature_verifier.is_valid_request(body, request.headers):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    # --- 2. 이벤트 데이터 파싱 ---
    # request.json()은 body를 다시 읽으려 해서 오류 발생 가능 -> 파싱된 body 사용
    event_data = json.loads(body.decode('utf-8'))

    logging.info(f"Slack events: {event_data}")

    # URL 검증을 위한 초기 요청 처리
    if "challenge" in event_data:
        return {"challenge": event_data["challenge"]}
        
    # --- 3. app_mention 이벤트 처리 ---
    if event_data.get("event", {}).get("type") == "app_mention":
        event = event_data["event"]

        # 이벤트를 발생시킨 사용자 ID 가져오기
        slack_user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        message_ts = event.get("ts")
        target_ts = thread_ts if thread_ts else message_ts

        logging.info(f"🔍 슬랙 이벤트 발생: user={slack_user_id}, channel={channel_id}")

        # Integration 테이블에서 slack_user_id로 시스템 user_id 조회
        system_user_id = db_manager.get_user_id_by_integration(source='slack', type='user_id', value=slack_user_id)

        if not system_user_id:
            # 권한이 없는 사용자 → 에러 메시지 전송
            logging.warning(f"⚠️ 권한 없는 사용자: slack_user_id={slack_user_id}")
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=target_ts,
                    text="❌ 권한이 없는 사용자입니다.\n\n티켓을 생성하려면 먼저 웹 페이지에서 슬랙 계정을 연동해주세요.\n연동 페이지: http://localhost:8501"
                )
            except Exception as e:
                logging.error(f"슬랙 메시지 전송 실패: {e}")

            return {"status": "ok"}

        logging.info(f"✅ 연동된 사용자 확인: system_user_id={system_user_id}")

        # 권한이 있는 사용자 → 티켓 생성 진행
        try:
            result = client.conversations_replies(channel=channel_id, ts=target_ts)
            messages = result['messages']

            # 원문 정리
            original_text_parts = []
            for msg in messages[1:-1]:
                sender = msg.get('user', 'unknown')
                sender_info_raw = client.users_info(user=sender)
                sender_info = sender_info_raw.get('user', {})
                logging.info(f"Sender info: {sender_info}")
                if not sender_info:
                    continue
                if sender_info.get('is_bot') == True or sender_info.get('is_app_user') == True:
                    continue
                original_text_parts.append({
                    "sender": sender_info.get('profile', {}).get('real_name', 'unknown'),
                    "text": msg.get('text', ''),
                    "received_date": msg.get('ts', '')
                })

            if original_text_parts:
                email_data = await make_ticket_data(original_text_parts)
                email_data['force_create'] = True

                async with mcp:
                    await mcp.call_tool("create_ticket_from_single_email_tool", {"email_data": email_data})

                # 티켓 생성 완료 메시지 전송
                try:
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=target_ts,
                        text="✅ 티켓이 생성되었습니다."
                    )
                except Exception as e:
                    logging.error(f"슬랙 메시지 전송 실패: {e}")

        except Exception as e:
            logging.error(f"티켓 생성 중 오류 발생: {e}")
            # 오류 메시지 전송
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=target_ts,
                    text=f"❌ 티켓 생성 중 오류가 발생했습니다: {str(e)}"
                )
            except Exception as msg_error:
                logging.error(f"슬랙 메시지 전송 실패: {msg_error}")
            
    return {"status": "ok"}

@app.post("/kakao/events")
async def handle_kakao_events(request: Request):
    body = await request.body()
    event_data = json.loads(body.decode('utf-8'))

    logging.info(f"Kakao events: {event_data}")
    utterance = event_data.get("userRequest").get("utterance")
    bot_user_key = event_data.get("userRequest").get("user").get("id")

    # botUserKey로 integration 테이블에서 시스템 user_id 조회
    logging.info(f"🔍 botUserKey로 사용자 조회: bot_user_key={bot_user_key}")
    system_user_id = db_manager.get_user_id_by_integration(source='kakao', type='botUserKey', value=bot_user_key)

    if not system_user_id:
        # botUserKey가 없는 경우 → 카카오 로그인 유도
        logging.warning(f"⚠️ botUserKey가 integration 테이블에 없음: bot_user_key={bot_user_key}")

        # 임시 저장소에 botUserKey 저장 (카카오 로그인 후 매핑에 사용)
        bot_user_session_id = str(uuid.uuid4())
        kakao_temp_storage[bot_user_session_id] = {
            "bot_user_key": bot_user_key,
            "timestamp": datetime.now().isoformat(),
            "purpose": "bot_user_mapping"
        }
        logging.info(f"📦 임시 저장소에 botUserKey 저장: session_id={bot_user_session_id}")

        # 카카오 로그인 링크 생성
        kakao_login_url = (
            f"http://localhost:8002/auth/kakao/bot-link?"
            f"session_id={bot_user_session_id}"
        )

        return {
            "version": "2.0",
            "template": {
                "outputs": [{
                    "textCard": {
                        "title": "🔗 계정 연동이 필요합니다",
                        "description": "티켓을 생성하려면 먼저 카카오 계정을 연동해야 합니다.\n\n아래 버튼을 눌러 카카오 로그인을 진행해주세요.",
                        "buttons": [
                            {
                                "action": "webLink",
                                "label": "카카오 계정 연동하기",
                                "webLinkUrl": kakao_login_url
                            }
                        ]
                    }
                }]
            }
        }

    logging.info(f"✅ 연동된 사용자 확인: system_user_id={system_user_id}")

    # 사용자 정보 조회
    user = db_manager.get_user_by_id(system_user_id)
    if not user:
        logging.error(f"❌ 사용자 정보를 찾을 수 없음: system_user_id={system_user_id}")
        return {
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "⚠️ 사용자 정보를 찾을 수 없습니다."
                    }
                }]
            }
        }

    # action.params 존재 여부 확인
    has_params = bool(event_data.get("action", {}).get("params"))

    # 사용자 이메일을 sender로 사용
    parsed_data, additional_text = parse_kakao_utterance(utterance, user.email, has_params)

    email_data = await make_ticket_data(parsed_data)
    email_data['force_create'] = True

    async with mcp:
        await mcp.call_tool("create_ticket_from_single_email_tool", {"email_data": email_data})

    return {
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleText": {
                    "text": "✅ 티켓이 생성되었습니다."
                }
            }]
        }
    }

def parse_kakao_utterance(utterance: str, user_id: str, has_date_in_utterance: bool = False):
    utterance_type = classify_kakao_utterance(utterance)
    parsed_data, additional_text = None, None
    if utterance_type == "kakaotalk_log":
        parsed_data, additional_text = parse_kakao_log(utterance, user_id, has_date_in_utterance)
    else:
        parsed_data, additional_text = parse_plain_text(utterance, user_id)

    return parsed_data, additional_text

def classify_kakao_utterance(utterance: str):
    utterance = utterance.replace('\r\n', '\n')
    kakaotalk_pattern = re.compile(r"^\s*(오전|오후)\s+(\d{1,2}:\d{1,2})\s+(.+)", re.MULTILINE)
    matches = kakaotalk_pattern.findall(utterance)

    # 패턴이 없으면 일반 텍스트
    if len(matches) > 0:
        return "kakaotalk_log"
    return "plain_text"

def parse_plain_text(utterance, user_id):
    return [{
        "sender": user_id,
        "text": utterance,
        "received_date": datetime.now().isoformat()
    }], ""

def parse_date_flexible(text):
    """한국어/영어 날짜를 유연하게 파싱"""
    # 1. 먼저 한국어 패턴 시도
    korean_patterns = [
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
        r'(\d{1,2})월\s*(\d{1,2})일',
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})'
    ]
    
    for pattern in korean_patterns:
        match = re.search(pattern, text)
        if match:
            nums = [int(n) for n in match.groups()]
            try:
                if len(nums) == 3:
                    return datetime(nums[0], nums[1], nums[2])
                elif len(nums) == 2:
                    return datetime(datetime.now().year, nums[0], nums[1])
            except ValueError:
                continue
    
    # 2. dateparser 시도 (영어 등)
    date = dateparser.parse(text, languages=['ko', 'en'])
    if date:
        return date
    
    return None

def parse_kakao_log(utterance, user_id, has_date_in_utterance: bool = False):

    utterance = utterance.replace('\r\n', '\n')
    message_pattern = re.compile(r"^\s*(오전|오후)\s+(\d{1,2}:\d{1,2})\s+(.+)", re.MULTILINE)
    parsed_data = []
    unmatched_lines = []
    lines = utterance.strip().split('\n')
    current_date = None
    today = datetime.now().date()

    if not has_date_in_utterance:
        current_date = today

    for line in lines:
        # --- [최종 수정 1] 눈에 보이지 않는 특수 공백을 일반 공백으로 치환 ---
        # 이것이 문제 해결의 핵심입니다.
        line = line.replace('\xa0', ' ')

        # --- [최종 수정 2] 비효율적인 중복 호출을 방지하기 위해 한 번만 실행 ---
        found_dates = parse_date_flexible(line)
        
        message_match = message_pattern.match(line)
        
        if message_match:
            am_pm, time_str, rest_of_line = message_match.groups()
            
            parts = rest_of_line.split(" ", 1)
            sender = parts[0]
            message = parts[1] if len(parts) > 1 else ""
            hour, minute = map(int, time_str.split(':'))
            if am_pm == '오후' and hour != 12: hour += 12
            elif am_pm == '오전' and hour == 12: hour = 0
            
            effective_date = current_date if current_date else today
            received_datetime = datetime.combine(effective_date, datetime.min.time().replace(hour=hour, minute=minute))
            parsed_data.append({
                "sender": sender,
                "text": message,
                "received_date": received_datetime.isoformat()
            })
        
        elif found_dates:
            # 변수를 사용하여 깔끔하게 처리
            current_date = found_dates.date()
            pass

        else:
            if parsed_data:
                parsed_data[-1]["text"] += "\n" + line
            else:
                unmatched_lines.append(line)

    additional_text = "\n".join(unmatched_lines)
    return parsed_data, additional_text


# === Jira 온보딩 관련 엔드포인트 ===

class JiraCredentialsRequest(BaseModel):
    jira_endpoint: str
    jira_api_token: str


class JiraProjectsRequest(BaseModel):
    projects: list


class JiraLabelsRequest(BaseModel):
    labels_config: dict


class JiraValidateLabelsRequest(BaseModel):
    project_key: str
    labels: list


@app.post("/jira/validate")
async def validate_jira_credentials(
    request: JiraCredentialsRequest,
    session_id: Optional[str] = Cookie(None)
):
    """
    Jira 인증 정보 검증 (/myself API 호출)
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        # JiraConnector를 사용하여 인증 검증
        from jira_connector import JiraConnector

        # Jira 연결 (Bearer Token 방식, email 불필요)
        jira_conn = JiraConnector(
            url=request.jira_endpoint,
            token=request.jira_api_token
        )

        # /myself API 호출
        result = jira_conn.validate_credentials()

        return result

    except Exception as e:
        logging.error(f"Jira 인증 검증 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 인증 검증 중 오류가 발생했습니다: {str(e)}")


@app.post("/jira/credentials")
async def save_jira_credentials(
    request: JiraCredentialsRequest,
    session_id: Optional[str] = Cookie(None)
):
    """
    Jira 인증 정보 저장 (endpoint, token)
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        from database_models import Integration

        # Endpoint 저장
        endpoint_integration = Integration(
            id=None,
            user_id=user_id,
            source='jira',
            type='endpoint',
            value=request.jira_endpoint,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db_manager.insert_integration(endpoint_integration)

        # Token 저장 (암호화)
        encrypted_token = token_encryption.encrypt_token(request.jira_api_token)
        token_integration = Integration(
            id=None,
            user_id=user_id,
            source='jira',
            type='token',
            value=encrypted_token,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db_manager.insert_integration(token_integration)

        return {
            "success": True,
            "message": "Jira 인증 정보가 저장되었습니다."
        }

    except Exception as e:
        logging.error(f"Jira 인증 정보 저장 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 인증 정보 저장 중 오류가 발생했습니다: {str(e)}")


@app.get("/jira/projects")
async def get_jira_projects(session_id: Optional[str] = Cookie(None)):
    """
    Jira 프로젝트 목록 조회 (/project API 호출)
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        # Integration 테이블에서 Jira 정보 가져오기
        endpoint_integration = db_manager.get_integration(user_id, 'jira', 'endpoint')
        token_integration = db_manager.get_integration(user_id, 'jira', 'token')

        if not endpoint_integration or not token_integration:
            raise HTTPException(status_code=404, detail="Jira 인증 정보를 찾을 수 없습니다")

        # 토큰 복호화
        decrypted_token = token_encryption.decrypt_token(token_integration.value)

        # 이메일 가져오기
        user = db_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        # JiraConnector를 사용하여 프로젝트 조회
        from jira_connector import JiraConnector

        jira_conn = JiraConnector(
            url=endpoint_integration.value,
            token=decrypted_token
        )

        # /project API 호출
        result = jira_conn.get_projects()

        return result

    except Exception as e:
        logging.error(f"Jira 프로젝트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 프로젝트 조회 중 오류가 발생했습니다: {str(e)}")


@app.post("/jira/projects")
async def save_jira_projects(
    request: JiraProjectsRequest,
    session_id: Optional[str] = Cookie(None)
):
    """
    선택한 Jira 프로젝트 저장
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        from database_models import Integration

        # 프로젝트 목록 JSON으로 저장
        project_integration = Integration(
            id=None,
            user_id=user_id,
            source='jira',
            type='project',
            value=json.dumps(request.projects),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db_manager.insert_integration(project_integration)

        return {
            "success": True,
            "message": f"{len(request.projects)}개의 프로젝트가 저장되었습니다."
        }

    except Exception as e:
        logging.error(f"Jira 프로젝트 저장 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 프로젝트 저장 중 오류가 발생했습니다: {str(e)}")


@app.post("/jira/validate-labels")
async def validate_jira_labels(
    request: JiraValidateLabelsRequest,
    session_id: Optional[str] = Cookie(None)
):
    """
    프로젝트와 레이블 조합으로 JQL 쿼리 검증
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        # Integration 테이블에서 Jira 정보 가져오기
        endpoint_integration = db_manager.get_integration(user_id, 'jira', 'endpoint')
        token_integration = db_manager.get_integration(user_id, 'jira', 'token')

        if not endpoint_integration or not token_integration:
            raise HTTPException(status_code=404, detail="Jira 인증 정보를 찾을 수 없습니다")

        # 토큰 복호화
        decrypted_token = token_encryption.decrypt_token(token_integration.value)

        # 이메일 가져오기
        user = db_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        # JiraConnector를 사용하여 JQL 검증
        from jira_connector import JiraConnector

        jira_conn = JiraConnector(
            url=endpoint_integration.value,
            token=decrypted_token
        )

        # JQL 검증
        result = jira_conn.validate_jql_with_labels(request.project_key, request.labels)

        return result

    except Exception as e:
        logging.error(f"JQL 쿼리 검증 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"JQL 쿼리 검증 중 오류가 발생했습니다: {str(e)}")


@app.post("/jira/labels")
async def save_jira_labels(
    request: JiraLabelsRequest,
    session_id: Optional[str] = Cookie(None)
):
    """
    프로젝트별 레이블 설정 저장
    """
    try:
        # 세션 검증
        if not session_id:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        from database_models import Integration

        # 레이블 설정 JSON으로 저장
        labels_integration = Integration(
            id=None,
            user_id=user_id,
            source='jira',
            type='labels',
            value=json.dumps(request.labels_config),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db_manager.insert_integration(labels_integration)

        return {
            "success": True,
            "message": "Jira 레이블 설정이 저장되었습니다."
        }

    except Exception as e:
        logging.error(f"Jira 레이블 저장 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 레이블 저장 중 오류가 발생했습니다: {str(e)}")


@app.delete("/jira/integration")
async def reset_jira_integration(session_id: Optional[str] = Cookie(None)):
    """
    Jira 연동 정보 전체 삭제 (재설정용)
    """
    try:
        logging.info(f"🗑️ Jira 연동 삭제 요청 시작")
        logging.info(f"🍪 전달된 session_id: {session_id[:10] if session_id else 'None'}...")

        # 세션 검증
        if not session_id:
            logging.error("❌ session_id가 없음")
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")

        session = session_manager.get_session(session_id)
        logging.info(f"📋 세션 정보: {session}")

        if not session:
            logging.error("❌ 세션이 만료됨")
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

        user_id = session.get("user_id")
        logging.info(f"👤 user_id: {user_id}")

        if not user_id:
            logging.error("❌ user_id를 찾을 수 없음")
            raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다")

        # 삭제 전 데이터 확인
        before_data = db_manager.get_integrations_by_source(user_id, 'jira')
        logging.info(f"🔍 삭제 전 Integration 테이블 Jira 데이터: {len(before_data) if before_data else 0}개")

        # Integration 테이블에서 Jira 관련 모든 데이터 삭제
        db_manager.delete_integration_source(user_id, 'jira')

        # 삭제 후 데이터 확인
        after_data = db_manager.get_integrations_by_source(user_id, 'jira')
        logging.info(f"🔍 삭제 후 Integration 테이블 Jira 데이터: {len(after_data) if after_data else 0}개")

        logging.info(f"✅ 사용자 {user_id}의 Jira 연동 정보 삭제 완료")

        return {
            "success": True,
            "message": "Jira 연동 정보가 삭제되었습니다."
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Jira 연동 정보 삭제 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira 연동 정보 삭제 중 오류가 발생했습니다: {str(e)}")


# ============================================
# 그룹 협업 API 통합
# ============================================
from api.group_api import create_group_router

# 그룹 API 라우터 생성 (이 파일의 get_current_user 전달)
group_router = create_group_router(get_current_user)
app.include_router(group_router)


if __name__ == "__main__":
    # 만료된 세션 정리 (주기적으로 실행)
    def cleanup_sessions():
        while True:
            session_manager.cleanup_expired_sessions()
            threading.Event().wait(3600)  # 1시간마다 실행

    cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    cleanup_thread.start()

    logging.info("🚀 FastAPI 서버 시작: http://localhost:8002")
    logging.info("   - 그룹 협업 API 사용 가능: /api/groups")
    uvicorn.run(app, host="0.0.0.0", port=8002)
