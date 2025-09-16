#!/usr/bin/env python3
"""
FastMCP 기반 이메일 서비스 서버
기존 mcp_server.py를 FastMCP 애플리케이션으로 교체
"""

import os
import logging
import requests
import secrets
import hashlib
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# FastMCP import
from fastmcp import FastMCP

# FastAPI import
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from email_validator import validate_email
import bcrypt
from cryptography.fernet import Fernet
import sqlite3
import uuid

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("EmailServiceServer")

# 글로벌 컨텍스트 저장소
current_context = {
    "user_email": None
}

def set_current_user_email(email: str):
    """현재 사용자 이메일을 컨텍스트에 설정"""
    current_context["user_email"] = email
    logging.info(f"📧 사용자 이메일 컨텍스트 설정: {email}")

def get_current_user_email() -> Optional[str]:
    """현재 사용자 이메일을 컨텍스트에서 가져오기"""
    return current_context.get("user_email")

def clear_user_context():
    """사용자 컨텍스트 초기화"""
    current_context["user_email"] = None
    logging.info("🧹 사용자 컨텍스트 초기화 완료")

# FastAPI 앱 생성
auth_app = FastAPI(title="Auth API", version="1.0.0")

# CORS 설정
auth_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터베이스 관리자
class DatabaseManager:
    def __init__(self, db_path="tickets.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # users 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                google_refresh_token TEXT NULL,
                jira_endpoint VARCHAR(255) NULL,
                jira_api_token TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # sessions 테이블 제거됨 (메모리 기반 세션 관리 사용)
        
        conn.commit()
        conn.close()
    
    def get_user_by_email(self, email: str):
        """이메일로 사용자 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def create_user(self, email: str, password_hash: str):
        """사용자 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    
    # sessions 테이블 관련 메서드 제거됨 (메모리 기반 세션 관리 사용)
    
    def update_user_google_token(self, user_id: int, encrypted_token: str = None):
        """사용자 Google 토큰 업데이트 (None이면 토큰 삭제)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET google_refresh_token = ? WHERE id = ?",
            (encrypted_token, user_id)
        )
        conn.commit()
        conn.close()

# 전역 데이터베이스 관리자
db_manager = DatabaseManager()

# 토큰 암호화 관리자
class TokenEncryption:
    def __init__(self):
        self.key = os.getenv("ENCRYPTION_KEY")
        if not self.key:
            # 새로운 키 생성
            self.key = Fernet.generate_key().decode()
            print(f"⚠️ 새로운 암호화 키가 생성되었습니다. ENCRYPTION_KEY={self.key}")
        
        logging.info(f"🔐 암호화 키 정보: 길이={len(self.key)}, 시작={self.key[:10]}...")
        
        try:
            self.fernet = Fernet(self.key.encode())
            logging.info("✅ Fernet 객체 생성 성공")
        except Exception as e:
            logging.error(f"❌ Fernet 객체 생성 실패: {e}")
            raise
    
    def encrypt_token(self, token: str) -> str:
        """토큰 암호화 (POC용 비활성화)"""
        logging.info("🔓 POC 모드: 토큰 암호화 비활성화")
        return token  # 암호화하지 않고 그대로 반환
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """토큰 복호화 (POC용 비활성화)"""
        logging.info("🔓 POC 모드: 토큰 복호화 비활성화")
        return encrypted_token  # 복호화하지 않고 그대로 반환

token_encryption = TokenEncryption()

# Pydantic 모델들
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleTokenByEmailRequest(BaseModel):
    email: EmailStr
    refresh_token: str

class LogoutRequest(BaseModel):
    session_id: Optional[str] = None

class AuthResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    email: Optional[str] = None

# 인증 의존성
def get_current_user(request: Request):
    """현재 로그인된 사용자 조회 (메모리 기반 세션 관리)"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 메모리 기반 세션 관리 사용
    from auth_utils import session_manager
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다")
    
    return {
        "user_id": session['user_id'],
        "email": session['email']
    }

# FastAPI 엔드포인트들
@auth_app.post("/auth/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """회원가입"""
    try:
        # 이메일 중복 확인
        existing_user = db_manager.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다")
        
        # 비밀번호 해시
        password_hash = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # 사용자 생성
        user_id = db_manager.create_user(request.email, password_hash)
        
        return AuthResponse(
            success=True,
            message="회원가입이 완료되었습니다",
            user_id=user_id,
            email=request.email
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"회원가입 실패: {str(e)}")

@auth_app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response):
    """로그인"""
    try:
        # 사용자 조회
        user = db_manager.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        
        # 비밀번호 확인
        if not bcrypt.checkpw(request.password.encode('utf-8'), user[2].encode('utf-8')):
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        
        # 메모리 기반 세션 생성
        from auth_utils import session_manager
        session_id = session_manager.create_session(user[0], user[1])
        
        # HttpOnly 쿠키 설정
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # 개발 환경에서는 False
            samesite="lax",
            max_age=7*24*60*60  # 7일
        )
        
        # 현재 사용자 이메일을 컨텍스트에 설정
        set_current_user_email(user[1])
        
        return AuthResponse(
            success=True,
            message="로그인이 완료되었습니다",
            user_id=user[0],
            email=user[1]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그인 실패: {str(e)}")

@auth_app.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """현재 사용자 정보 조회"""
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"]
    }

@auth_app.post("/auth/logout")
async def logout(request: LogoutRequest, response: Response):
    """로그아웃"""
    try:
        # 현재 사용자 정보 가져오기
        current_user = get_current_user(request)
        
        # 메모리 기반 세션 삭제
        session_id = request.cookies.get("session_id")
        if session_id:
            from auth_utils import session_manager
            session_manager.delete_session(session_id)
            logging.info(f"🔓 세션 삭제: {session_id}")
        
        logging.info(f"🔓 사용자 로그아웃: {current_user['user_id']}")
        
        # 글로벌 컨텍스트 초기화
        clear_user_context()
        
        # 쿠키 삭제
        response.delete_cookie(
            key="session_id",
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        return {
            "success": True,
            "message": "로그아웃이 완료되었습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ 로그아웃 실패: {e}")
        raise HTTPException(status_code=500, detail=f"로그아웃 실패: {str(e)}")

@auth_app.get("/user/integrations/google")
async def get_google_integration(current_user: dict = Depends(get_current_user)):
    """Google 연동 정보 조회"""
    try:
        user = db_manager.get_user_by_email(current_user["email"])
        if not user or not user[3]:  # google_refresh_token이 없음
            return {"success": False, "message": "Google 연동 정보가 없습니다", "needs_reauth": True}
        
        # 저장된 토큰 정보 확인
        stored_token = user[3]
        logging.info(f"🗄️ 저장된 토큰 정보: 길이={len(stored_token)}, 시작={stored_token[:30]}...")
        
        # 토큰 복호화
        try:
            decrypted_token = token_encryption.decrypt_token(stored_token)
            logging.info(f"✅ 토큰 복호화 성공: {user[1]}")
            
            return {
                "success": True,
                "message": "Google 연동 정보가 있습니다",
                "has_token": True,
                "refresh_token": decrypted_token
            }
        except Exception as e:
            logging.error(f"❌ 토큰 복호화 실패: {user[1]} - {str(e)}")
            # 토큰이 손상된 경우 재인증 필요
            return {
                "success": False, 
                "message": f"토큰이 손상되어 재인증이 필요합니다: {str(e)}",
                "needs_reauth": True,
                "corrupted_token": True
            }
    except Exception as e:
        return {"success": False, "message": f"Google 연동 정보 조회 실패: {str(e)}"}

@auth_app.post("/user/integrations/google")
async def update_google_integration(request: GoogleTokenByEmailRequest, current_user: dict = Depends(get_current_user)):
    """Google 연동 정보 업데이트 (현재 사용자)"""
    try:
        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.refresh_token)
        
        # DB에 저장
        db_manager.update_user_google_token(current_user["user_id"], encrypted_token)
        
        return {
            "success": True,
            "message": "Google 연동 정보가 업데이트되었습니다"
        }
    except Exception as e:
        return {"success": False, "message": f"Google 연동 정보 업데이트 실패: {str(e)}"}

@auth_app.post("/user/integrations/google/by-email")
async def update_google_token_by_email(request: GoogleTokenByEmailRequest):
    logging.info(f"🍪 이메일로 Google Refresh Token 저장 시도: {request.email}")
    """이메일로 Google Refresh Token 저장 (OAuth 콜백용)"""
    try:
        # 이메일로 사용자 조회
        user = db_manager.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.refresh_token)
        
        # 데이터베이스 업데이트
        db_manager.update_user_google_token(user[0], encrypted_token)
        
        return {
            "success": True,
            "message": f"Google 연동 정보가 업데이트되었습니다: {request.email}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google 연동 정보 업데이트 실패: {str(e)}")

@auth_app.delete("/user/integrations/google")
async def delete_google_integration(current_user: dict = Depends(get_current_user)):
    """Google 연동 정보 삭제 (손상된 토큰 정리용)"""
    try:
        # 사용자의 Google 토큰을 NULL로 설정
        db_manager.update_user_google_token(current_user["user_id"], None)
        
        return {
            "success": True,
            "message": "Google 연동 정보가 삭제되었습니다. 재인증을 진행해주세요."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google 연동 정보 삭제 실패: {str(e)}")

# OAuth 콜백 서버 설정
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth 콜백 처리 핸들러"""
    
    def do_GET(self):
        """GET 요청 처리 (OAuth 콜백)"""
        try:
            # URL 파싱
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # OAuth 콜백 파라미터 추출
            code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            error = query_params.get('error', [None])[0]
            
            # state에서 사용자 이메일 추출
            user_email = None
            if state and state.startswith('email_'):
                # 'email_' 제거하고 첫 번째 부분만 추출
                user_email = state[6:].split('_')[0]
                print(f"🍪 OAuth 콜백: state에서 이메일 추출: {user_email}")
            else:
                print(f"🍪 OAuth 콜백: state에 이메일이 없음 - state: {state}")
            
            if error:
                # OAuth 오류 처리
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"<html><body><h1>OAuth Error: {error}</h1></body></html>".encode('utf-8'))
                print(f"❌ OAuth 오류: {error}")
                return
            
            if code and state:
                # Authorization Code를 토큰으로 교환
                print(f"🔄 Authorization Code를 토큰으로 교환 중...")
                token_result = exchange_code_for_tokens(code, state)
                
                if token_result["success"]:
                    # 토큰 교환 성공
                    access_token = token_result["access_token"]
                    refresh_token = token_result["refresh_token"]
                    expires_in = token_result["expires_in"]
                    
                    # state에서 추출한 이메일로 DB에 토큰 저장
                    if user_email:
                        print(f"🍪 DB에 Google 토큰 저장 시도: {user_email}")
                        save_google_token_to_db(user_email, refresh_token)
                    else:
                        print("🍪 이메일이 없어서 DB 저장 불가")
                    
                    # 응답 헤더 설정
                    self.send_response(302)  # 리디렉션
                    redirect_url = f"http://localhost:8501?access_token={access_token}&refresh_token={refresh_token}"
                    self.send_header('Location', redirect_url)
                    self.end_headers()
                    
                    # 콘솔에 성공 메시지 출력
                    print(f"\n🎉 OAuth 인증 완료!")
                    print(f"✅ Access Token: {access_token[:20]}...")
                    print(f"✅ Refresh Token: {refresh_token[:20]}...")
                    print(f"⏰ 만료 시간: {expires_in}초")
                    print(f"🔄 Streamlit 앱으로 리디렉션 중...")
                else:
                    # 토큰 교환 실패
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f"<html><body><h1>OAuth Token Exchange Failed: {token_result.get('message', 'Unknown error')}</h1></body></html>".encode('utf-8'))
                    print(f"❌ 토큰 교환 실패: {token_result.get('message', 'Unknown error')}")
            else:
                # code 또는 state 파라미터가 없음
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write("<html><body><h1>OAuth Callback Error: Missing code or state parameter.</h1></body></html>".encode('utf-8'))
                print("❌ OAuth 콜백 오류: code 또는 state 파라미터가 없습니다.")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Internal Server Error: {e}</h1></body></html>".encode('utf-8'))
            print(f"❌ OAuth 콜백 처리 중 예외 발생: {e}")

def exchange_code_for_tokens(code, state):
    """Authorization Code를 access_token과 refresh_token으로 교환"""
    try:
        import requests
        
        # Google OAuth2 토큰 엔드포인트
        token_url = "https://oauth2.googleapis.com/token"
        
        # 요청 데이터
        data = {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:8000/auth/callback'
        }
        
        # 토큰 요청
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            return {
                "success": True,
                "access_token": token_data.get('access_token'),
                "refresh_token": token_data.get('refresh_token'),
                "expires_in": token_data.get('expires_in', 3600)
            }
        else:
            return {
                "success": False,
                "message": f"토큰 교환 실패: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"토큰 교환 중 오류: {e}"
        }

def save_google_token_to_db(user_email, refresh_token):
    """DB에 Google 토큰 저장 (통합된 DB 사용)"""
    try:
        # 이메일로 사용자 조회
        user = db_manager.get_user_by_email(user_email)
        if not user:
            print(f"⚠️ 사용자를 찾을 수 없습니다: {user_email}")
            # unknown@example.com인 경우 임시 사용자 생성
            if user_email == 'unknown@example.com':
                print(f"🍪 unknown@example.com 사용자 생성 시도")
                # 임시 사용자 생성 (비밀번호는 랜덤)
                import secrets
                temp_password = secrets.token_urlsafe(16)
                password_hash = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                user_id = db_manager.create_user(user_email, password_hash)
                print(f"✅ 임시 사용자 생성 완료: {user_email} (ID: {user_id})")
                user = (user_id, user_email, password_hash, None, None, None, None)
            else:
                return False
        
        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(refresh_token)
        
        # 데이터베이스 업데이트
        db_manager.update_user_google_token(user[0], encrypted_token)
        
        print(f"✅ Google 토큰이 사용자 계정에 저장되었습니다: {user_email}")
        return True
            
    except Exception as e:
        print(f"⚠️ Google 토큰 저장 중 오류: {e}")
        return False

# OAuth 설정
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback")

FRONTEND_MAIN_PAGE = os.getenv("FRONTEND_MAIN_PAGE", "http://localhost:8501")

# 세션 저장소 (실제 운영에서는 Redis 등 사용)
sessions: Dict[str, Dict[str, Any]] = {}

# OAuth 콜백 핸들러 클래스
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth 콜백 처리 HTTP 핸들러"""
    
    def do_GET(self):
        """GET 요청 처리 (OAuth 콜백)"""
        try:
            # URL 파싱
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            logging.info(f"🍪 OAuth 콜백 파라미터: {query_params}")
            
            # OAuth 콜백 파라미터 추출
            code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            error = query_params.get('error', [None])[0]
            
            if error:
                # OAuth 오류 처리
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                error_message = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>OAuth 인증 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .error {{ color: #d32f2f; font-size: 18px; margin-bottom: 20px; }}
                        .info {{ color: #666; margin-bottom: 15px; }}
                        .button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>❌ OAuth 인증 오류</h1>
                        <div class="error">오류: {error}</div>
                        <div class="info">OAuth 인증 중 오류가 발생했습니다.</div>
                        <div class="info">다시 시도해주세요.</div>
                        <button class="button" onclick="window.close()">창 닫기</button>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(error_message.encode('utf-8'))
                return
            
            if code and state:
                # FastMCP 서버의 OAuth 콜백 핸들러 호출
                try:
                    # 제공자 추출 (URL에서)
                    provider = "gmail"  # 기본값
                    if "provider" in query_params:
                        provider = query_params.get('provider', ['gmail'])[0]
                    
                    # OAuth 콜백 처리 (인라인)
                    result = self._process_oauth_callback(code, state, provider)
                    
                    if result.get("success", False):
                        # 성공적인 OAuth 콜백 처리
                        access_token = result.get("access_token", "")
                        refresh_token = result.get("refresh_token", "")
                        
                        # 리디렉션 URL 생성
                        redirect_url = f"{FRONTEND_MAIN_PAGE}?access_token={access_token}&refresh_token={refresh_token}"
                        
                        # 리디렉션 응답
                        self.send_response(302)
                        self.send_header('Location', redirect_url)
                        self.end_headers()
                        
                        logging.info(f"✅ OAuth 콜백 성공: {provider}")
                        
                    else:
                        # 토큰 교환 실패
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        
                        error_message = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>OAuth 토큰 교환 실패</title>
                            <meta charset="utf-8">
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                                .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                                .error {{ color: #d32f2f; font-size: 18px; margin-bottom: 20px; }}
                                .info {{ color: #666; margin-bottom: 15px; }}
                                .button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <h1>❌ OAuth 토큰 교환 실패</h1>
                                <div class="error">오류: {result.get('error', 'Unknown error')}</div>
                                <div class="info">토큰 교환 중 오류가 발생했습니다.</div>
                                <div class="info">다시 시도해주세요.</div>
                                <button class="button" onclick="window.close()">창 닫기</button>
                            </div>
                        </body>
                        </html>
                        """
                        self.wfile.write(error_message.encode('utf-8'))
                        
                except Exception as e:
                    logging.error(f"❌ OAuth 콜백 처리 실패: {e}")
                    self.send_response(500)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(b"Internal Server Error")
                    
            else:
                # 잘못된 요청
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                error_message = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>잘못된 요청</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 잘못된 요청</h1>
                    <p>OAuth 콜백 파라미터가 올바르지 않습니다.</p>
                </body>
                </html>
                """
                self.wfile.write(error_message.encode('utf-8'))
                
        except Exception as e:
            logging.error(f"❌ HTTP 핸들러 오류: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
    
    def log_message(self, format, *args):
        """로그 메시지 출력 비활성화"""
        pass
    
    def _process_oauth_callback(self, code: str, state: str, provider: str = "gmail") -> Dict[str, Any]:
        """OAuth 콜백 처리 - Authorization Code를 Access Token으로 교환"""
        try:
            logging.info(f"🔄 OAuth 콜백 처리 시작: {provider}")
            
            # 상태 토큰 검증 (선택적)
            if state and state not in sessions:
                logging.warning(f"⚠️ 상태 토큰이 세션에 없음: {state}")
                # 상태 토큰이 없어도 토큰 교환을 진행 (보안상 완전하지 않지만 테스트용)
                logging.info("🔄 상태 토큰 없이 토큰 교환 진행")
            
            # 제공자별 설정
            if provider.lower() == "gmail":
                client_id = GOOGLE_CLIENT_ID
                client_secret = GOOGLE_CLIENT_SECRET
                redirect_uri = GOOGLE_REDIRECT_URI
                token_url = "https://oauth2.googleapis.com/token"
            elif provider.lower() == "microsoft":
                client_id = MICROSOFT_CLIENT_ID
                client_secret = MICROSOFT_CLIENT_SECRET
                redirect_uri = MICROSOFT_REDIRECT_URI
                token_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
            else:
                return {
                    "success": False,
                    "error": "Unsupported provider",
                    "message": f"지원하지 않는 제공자입니다: {provider}"
                }
            
            # 토큰 교환 요청
            token_data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            
            token_response = response.json()
            access_token = token_response.get("access_token")
            refresh_token = token_response.get("refresh_token")
            expires_in = token_response.get("expires_in", 3600)
            
            # 세션에 토큰 저장 (상태 토큰이 있는 경우에만)
            if state:
                sessions[state] = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": datetime.now() + timedelta(seconds=expires_in),
                    "provider": provider
                }
                logging.info(f"✅ 세션에 토큰 저장: {state}")
            else:
                logging.info("⚠️ 상태 토큰이 없어 세션에 저장하지 않음")
            
            # DB에 토큰 저장 (이메일이 포함된 경우에만)
            if state and state.startswith('email_'):
                user_email = state[6:].split('_')[0]  # 'email_' 제거하고 첫 번째 부분만
                if user_email:
                    print(f"🍪 DB에 Google 토큰 저장 시도: {user_email}")
                    save_google_token_to_db(user_email, refresh_token)
                else:
                    print(f"🍪 이메일이 없어서 DB 저장 불가: {user_email}")
            else:
                print(f"🍪 state에 이메일이 없어서 DB 저장 불가: {state}")
            
            logging.info(f"✅ OAuth 토큰 교환 성공: {provider}")
            
            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "provider": provider,
                "message": f"{provider.upper()} 인증이 완료되었습니다.",
                "redirect_url": f"{FRONTEND_MAIN_PAGE}?access_token={access_token}&refresh_token={refresh_token}"
            }
            
        except Exception as e:
            logging.error(f"❌ OAuth 콜백 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"OAuth 인증 처리 중 오류가 발생했습니다: {e}"
            }

# 이메일 도구들 import
from fastmcp_email_tools import (
    get_raw_emails,
    process_emails_with_ticket_logic,
    get_email_provider_status,
    get_mail_content_by_id,
    create_ticket_from_single_email,
    fetch_emails_sync
)

# 이메일 에이전트 import
from fastmcp_email_agent import email_agent

# 도구들을 FastMCP에 등록
@mcp.tool()
def get_raw_emails_tool(provider_name: str, filters: Dict[str, Any]) -> list:
    """사용자의 특정 조건에 맞는 순수 이메일 목록을 반환합니다."""
    return get_raw_emails(provider_name, filters)

@mcp.tool()
def process_emails_with_ticket_logic_tool(provider_name: str, user_query: str = None) -> Dict[str, Any]:
    """안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다."""
    return process_emails_with_ticket_logic(provider_name, user_query)

@mcp.tool()
def get_email_provider_status_tool(provider_name: str = None) -> Dict[str, Any]:
    """이메일 제공자의 연결 상태와 설정 정보를 확인합니다."""
    return get_email_provider_status(provider_name)

@mcp.tool()
def get_mail_content_by_id_tool(message_id: str) -> Optional[Dict[str, Any]]:
    """VectorDB에서 message_id로 메일 상세 내용을 조회합니다."""
    return get_mail_content_by_id(message_id)

@mcp.tool()
def create_ticket_from_single_email_tool(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """단일 이메일을 티켓으로 변환하는 함수입니다."""
    return create_ticket_from_single_email(email_data)

@mcp.tool()
def fetch_emails_sync_tool(provider_name: str, use_classifier: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """동기적으로 이메일을 가져와서 티켓 형태로 변환하여 반환합니다."""
    return fetch_emails_sync(provider_name, use_classifier, max_results)

# 에이전트를 FastMCP 도구로 등록
@mcp.tool()
def email_agent_tool(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    이메일 관리 및 티켓 생성 전문 AI 어시스턴트
    
    사용자의 이메일 관련 요청을 이해하고 적절한 도구를 선택하여 실행합니다.
    
    Args:
        user_query (str): 사용자의 요청 또는 질문
        context (Optional[Dict[str, Any]]): 추가 컨텍스트 정보
    
    Returns:
        Dict[str, Any]: 처리 결과
            - success (bool): 처리 성공 여부
            - message (str): 응답 메시지
            - data (Any): 처리된 데이터
            - tools_used (List[str]): 사용된 도구 목록
            - error (str, optional): 오류 메시지
    """
    return email_agent(user_query, context)

# 추가 유틸리티 도구들
@mcp.tool()
def get_available_providers() -> list:
    """
    사용 가능한 이메일 제공자 목록을 반환합니다.
    
    Returns:
        list: 사용 가능한 이메일 제공자 목록
    """
    try:
        from email_provider import get_available_providers as original_function
        providers = original_function()
        logging.info(f"✅ 사용 가능한 이메일 제공자: {providers}")
        return providers
    except Exception as e:
        logging.error(f"❌ 이메일 제공자 목록 조회 실패: {str(e)}")
        return []

@mcp.tool()
def get_default_provider() -> str:
    """
    기본 이메일 제공자를 반환합니다.
    
    Returns:
        str: 기본 이메일 제공자 이름
    """
    try:
        from email_provider import get_default_provider as original_function
        provider = original_function()
        logging.info(f"✅ 기본 이메일 제공자: {provider}")
        return provider
    except Exception as e:
        logging.error(f"❌ 기본 이메일 제공자 조회 실패: {str(e)}")
        return "gmail"

@mcp.tool()
def test_work_related_filtering() -> Dict[str, Any]:
    """
    테스트용 업무 관련 메일 필터링 기능을 실행합니다.
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_work_related_filtering as original_function
        result = original_function()
        logging.info(f"✅ 업무 관련 메일 필터링 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 업무 관련 메일 필터링 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_email_fetch_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 메일 조회 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_email_fetch_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 메일 조회 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 메일 조회 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_ticket_creation_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 티켓 생성 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_ticket_creation_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 티켓 생성 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 티켓 생성 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# OAuth 인증 도구들
@mcp.tool()
def oauth_login_gmail(user_email: str = "unknown@example.com") -> Dict[str, Any]:
    """Gmail OAuth 로그인 URL을 생성합니다.
    
    Args:
        user_email: Gmail 계정 이메일 주소 (예: "user@gmail.com")
    """
    try:
        # 사용자 이메일 검증 및 로깅
        logging.info(f"🔍 oauth_login_gmail 호출됨 - user_email: {user_email} (type: {type(user_email)})")
        logging.info(f"🔍 현재 컨텍스트 사용자 이메일: {get_current_user_email()}")
        
        # 파라미터로 전달된 user_email이 없거나 기본값인 경우, 컨텍스트에서 가져오기 시도
        if user_email is None:
            logging.warning("⚠️ user_email이 None으로 전달됨")
            # 컨텍스트에서 사용자 이메일 가져오기 시도
            context_email = get_current_user_email()
            if context_email:
                user_email = context_email
                logging.info(f"📧 컨텍스트에서 사용자 이메일 복구: {user_email}")
            else:
                user_email = "unknown@example.com"
                logging.warning("⚠️ 컨텍스트에도 사용자 이메일이 없음, unknown@example.com 사용")
        elif not user_email or user_email == "unknown@example.com":
            logging.warning(f"⚠️ 사용자 이메일이 제공되지 않음: {user_email}")
            # 컨텍스트에서 사용자 이메일 가져오기 시도
            context_email = get_current_user_email()
            if context_email:
                user_email = context_email
                logging.info(f"📧 컨텍스트에서 사용자 이메일 복구: {user_email}")
            else:
                user_email = "unknown@example.com"
                logging.warning("⚠️ 컨텍스트에도 사용자 이메일이 없음, unknown@example.com 사용")
        
        # 상태 토큰 생성 (이메일 포함)
        state = f"email_{user_email}_{secrets.token_urlsafe(16)}"
        logging.info(f"🍪 OAuth URL 생성: user_email={user_email}, state={state}")
        
        # 세션에 상태 저장
        sessions[state] = {
            "provider": "gmail",
            "created_at": datetime.now(),
            "user_agent": "MCP Client",
            "ip": "localhost"
        }
        
        # Gmail OAuth URL 생성
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"scope=openid profile email https://www.googleapis.com/auth/gmail.readonly&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state={state}"
        )
        
        logging.info(f"🔐 Gmail OAuth 로그인 URL 생성: {state}")
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state,
            "provider": "gmail",
            "message": "Gmail OAuth 로그인 URL이 생성되었습니다. 브라우저에서 이 URL을 열어 인증을 완료하세요."
        }
        
    except Exception as e:
        logging.error(f"❌ Gmail 로그인 URL 생성 실패: {e}")
        return {
            "success": False,
            "error": f"Gmail 로그인 URL 생성 실패: {e}"
        }

@mcp.tool()
def oauth_login_microsoft() -> Dict[str, Any]:
    """Microsoft OAuth 로그인 URL을 생성합니다."""
    try:
        # 상태 토큰 생성 (CSRF 보호)
        state = secrets.token_urlsafe(32)
        
        # 세션에 상태 저장
        sessions[state] = {
            "provider": "microsoft",
            "created_at": datetime.now(),
            "user_agent": "MCP Client",
            "ip": "localhost"
        }
        
        # Microsoft OAuth URL 생성
        auth_url = (
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize?"
            f"client_id={MICROSOFT_CLIENT_ID}&"
            f"response_type=code&"
            f"redirect_uri={MICROSOFT_REDIRECT_URI}&"
            f"scope=openid profile email Mail.ReadWrite offline_access&"
            f"response_mode=query&"
            f"state={state}"
        )
        
        logging.info(f"🔐 Microsoft OAuth 로그인 URL 생성: {state}")
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state,
            "provider": "microsoft",
            "message": "Microsoft OAuth 로그인 URL이 생성되었습니다. 브라우저에서 이 URL을 열어 인증을 완료하세요."
        }
        
    except Exception as e:
        logging.error(f"❌ Microsoft 로그인 URL 생성 실패: {e}")
        return {
            "success": False,
            "error": f"Microsoft 로그인 URL 생성 실패: {e}"
        }

@mcp.tool()
def oauth_callback(provider: str, code: str, state: str) -> Dict[str, Any]:
    """OAuth 콜백 처리 - authorization_code를 access_token과 refresh_token으로 교환"""
    try:
        if not code or not provider:
            return {
                "success": False,
                "error": "Missing code or provider"
            }
        
        # 상태 토큰 검증 (CSRF 보호)
        if state not in sessions:
            return {
                "success": False,
                "error": "Invalid state token"
            }
        
        session_info = sessions[state]
        if session_info["provider"] != provider:
            return {
                "success": False,
                "error": "Provider mismatch"
            }
        
        # 세션 정리
        del sessions[state]
        
        access_token = None
        refresh_token = None
        
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        elif provider == "microsoft":
            token_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
            data = {
                "code": code,
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "redirect_uri": MICROSOFT_REDIRECT_URI,
                "grant_type": "authorization_code",
                "scope": "openid profile email Mail.ReadWrite offline_access",
            }
        else:
            return {
                "success": False,
                "error": "Unsupported OAuth provider"
            }
        
        # 토큰 교환
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        
        if not access_token:
            return {
                "success": False,
                "error": "Failed to get access token"
            }
        
        logging.info(f"✅ OAuth 콜백 성공: {provider}")
        
        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "provider": provider,
            "message": f"{provider.upper()} OAuth 인증이 완료되었습니다. 이제 이메일 서비스를 사용할 수 있습니다."
        }
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ 토큰 교환 실패: {e}")
        return {
            "success": False,
            "error": f"Token exchange failed: {e}"
        }
    except Exception as e:
        logging.error(f"❌ OAuth 콜백 실패: {e}")
        return {
            "success": False,
            "error": f"Callback failed: {e}"
        }

@mcp.tool()
def oauth_refresh_token(provider: str, refresh_token: str) -> Dict[str, Any]:
    """토큰 재발급 - refresh_token을 사용하여 새로운 access_token 발급"""
    try:
        if not provider:
            return {
                "success": False,
                "error": "Missing provider"
            }
        
        if not refresh_token:
            return {
                "success": False,
                "error": "Refresh token not provided"
            }
        
        access_token = None
        
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "refresh_token": refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            }
        elif provider == "microsoft":
            token_url = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
            data = {
                "refresh_token": refresh_token,
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "scope": "openid profile email Mail.ReadWrite offline_access",
            }
        else:
            return {
                "success": False,
                "error": "Unsupported OAuth provider"
            }
        
        # 토큰 재발급
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data.get("access_token")
        new_refresh_token = token_data.get("refresh_token")  # 새로운 refresh token이 발급될 수도 있음
        
        if not access_token:
            return {
                "success": False,
                "error": "Failed to get new access token"
            }
        
        result = {
            "success": True,
            "access_token": access_token,
            "provider": provider,
            "message": f"{provider.upper()} 토큰이 성공적으로 재발급되었습니다."
        }
        
        # 새로운 refresh token이 있다면 포함
        if new_refresh_token and new_refresh_token != refresh_token:
            result["refresh_token"] = new_refresh_token
            result["message"] += " 새로운 refresh token도 발급되었습니다."
        
        logging.info(f"✅ 토큰 재발급 성공: {provider}")
        return result
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ 토큰 재발급 실패: {e}")
        return {
            "success": False,
            "error": f"Token refresh failed: {e}"
        }
    except Exception as e:
        logging.error(f"❌ 토큰 재발급 실패: {e}")
        return {
            "success": False,
            "error": f"Refresh failed: {e}"
        }

@mcp.tool()
def oauth_auth_status(provider: str = "gmail") -> Dict[str, Any]:
    """인증 상태 확인"""
    try:
        logging.info(f"🔍 인증 상태 확인: {provider}")
        
        # 실제로는 세션이나 데이터베이스에서 인증 상태를 확인해야 함
        # 여기서는 간단히 세션 정보를 확인
        active_sessions = len([s for s in sessions.values() if s["provider"] == provider])
        
        return {
            "success": True,
            "authenticated": active_sessions > 0,
            "provider": provider,
            "active_sessions": active_sessions,
            "message": f"{provider.upper()} 인증 상태: {'인증됨' if active_sessions > 0 else '인증되지 않음'}"
        }
        
    except Exception as e:
        logging.error(f"❌ 인증 상태 확인 실패: {e}")
        return {
            "success": False,
            "error": f"Status check failed: {e}"
        }

# 서버 상태 확인 도구
@mcp.tool()
def set_user_email_context(user_email: str) -> Dict[str, Any]:
    """현재 사용자 이메일을 컨텍스트에 설정합니다.
    
    Args:
        user_email: 설정할 사용자 이메일 주소
    """
    try:
        if not user_email or not user_email.strip():
            return {
                "success": False,
                "error": "유효한 이메일 주소를 입력해주세요"
            }
        
        set_current_user_email(user_email.strip())
        
        return {
            "success": True,
            "message": f"사용자 이메일이 설정되었습니다: {user_email}",
            "user_email": user_email
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"사용자 이메일 설정 실패: {str(e)}"
        }

@mcp.tool()
def get_user_email_context() -> Dict[str, Any]:
    """현재 컨텍스트에 설정된 사용자 이메일을 조회합니다."""
    try:
        user_email = get_current_user_email()
        
        return {
            "success": True,
            "user_email": user_email or "unknown@example.com",
            "has_email_set": user_email is not None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"사용자 이메일 조회 실패: {str(e)}"
        }

@mcp.tool()
def logout_user() -> Dict[str, Any]:
    """현재 사용자를 로그아웃하고 세션과 컨텍스트를 정리합니다."""
    try:
        # 글로벌 컨텍스트 초기화
        clear_user_context()
        
        # OAuth 세션들도 정리 (sessions 딕셔너리)
        global sessions
        expired_sessions = []
        for state, session_data in sessions.items():
            if session_data.get("created_at"):
                # 24시간 이상 된 세션은 만료된 것으로 간주
                if (datetime.now() - session_data["created_at"]).total_seconds() > 24 * 3600:
                    expired_sessions.append(state)
        
        for state in expired_sessions:
            del sessions[state]
        
        logging.info(f"🧹 OAuth 세션 정리: {len(expired_sessions)}개 세션 삭제")
        
        return {
            "success": True,
            "message": "로그아웃이 완료되었습니다. 세션과 컨텍스트가 정리되었습니다.",
            "cleared_sessions": len(expired_sessions)
        }
    except Exception as e:
        logging.error(f"❌ 로그아웃 실패: {e}")
        return {
            "success": False,
            "error": f"로그아웃 실패: {str(e)}"
        }

@mcp.tool()
def check_encryption_key() -> Dict[str, Any]:
    """암호화 키 상태를 확인합니다."""
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        return {
            "success": True,
            "has_encryption_key": bool(encryption_key),
            "key_length": len(encryption_key) if encryption_key else 0,
            "message": "ENCRYPTION_KEY가 설정되어 있습니다" if encryption_key else "ENCRYPTION_KEY가 설정되지 않았습니다"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"암호화 키 확인 실패: {str(e)}"
        }

@mcp.tool()
def reset_corrupted_tokens() -> Dict[str, Any]:
    """손상된 토큰들을 정리합니다."""
    try:
        # 모든 사용자의 Google 토큰을 확인하고 손상된 것들을 정리
        import sqlite3
        conn = sqlite3.connect("tickets.db")
        cursor = conn.cursor()
        
        # Google 토큰이 있는 모든 사용자 조회
        cursor.execute("SELECT id, email, google_refresh_token FROM users WHERE google_refresh_token IS NOT NULL")
        users_with_tokens = cursor.fetchall()
        
        corrupted_count = 0
        for user_id, email, encrypted_token in users_with_tokens:
            try:
                # 토큰 복호화 시도
                token_encryption.decrypt_token(encrypted_token)
                logging.info(f"✅ {email}: 토큰 정상")
            except Exception as e:
                # 손상된 토큰 삭제
                cursor.execute("UPDATE users SET google_refresh_token = NULL WHERE id = ?", (user_id,))
                corrupted_count += 1
                logging.warning(f"🗑️ {email}: 손상된 토큰 삭제")
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"토큰 정리 완료: {corrupted_count}개의 손상된 토큰을 삭제했습니다",
            "corrupted_tokens_removed": corrupted_count,
            "total_tokens_checked": len(users_with_tokens)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"토큰 정리 실패: {str(e)}"
        }

@mcp.tool()
def get_server_status() -> Dict[str, Any]:
    """
    FastMCP 서버의 상태를 확인합니다.
    
    Returns:
        Dict[str, Any]: 서버 상태 정보
    """
    try:
        import psutil
        import platform
        
        # 시스템 정보 수집
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage('/').percent
        }
        
        # 환경 변수 확인
        env_vars = {
            'AZURE_OPENAI_ENDPOINT': bool(os.getenv('AZURE_OPENAI_ENDPOINT')),
            'AZURE_OPENAI_API_KEY': bool(os.getenv('AZURE_OPENAI_API_KEY')),
            'AZURE_OPENAI_DEPLOYMENT_NAME': bool(os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')),
            'AZURE_OPENAI_API_VERSION': bool(os.getenv('AZURE_OPENAI_API_VERSION'))
        }
        
        logging.info("✅ 서버 상태 확인 완료")
        
        return {
            'status': 'healthy',
            'system_info': system_info,
            'environment_variables': env_vars,
            'timestamp': str(os.path.getmtime(__file__))
        }
        
    except Exception as e:
        logging.error(f"❌ 서버 상태 확인 실패: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': str(os.path.getmtime(__file__))
        }

# FastMCP 앱 실행을 위한 메인 함수
def run_fastmcp_server():
    """FastMCP 서버 실행"""
    logging.info("🚀 FastMCP 이메일 서비스 서버 시작")
    logging.info("📧 등록된 도구들:")
    logging.info("  - get_raw_emails_tool")
    logging.info("  - process_emails_with_ticket_logic_tool")
    logging.info("  - get_email_provider_status_tool")
    logging.info("  - get_mail_content_by_id_tool")
    logging.info("  - create_ticket_from_single_email_tool")
    logging.info("  - fetch_emails_sync_tool")
    logging.info("  - email_agent_tool")
    logging.info("  - get_available_providers")
    logging.info("  - get_default_provider")
    logging.info("  - test_work_related_filtering")
    logging.info("  - test_email_fetch_logic")
    logging.info("  - test_ticket_creation_logic")
    logging.info("  - get_server_status")
    logging.info("📧 사용자 컨텍스트 도구들:")
    logging.info("  - set_user_email_context")
    logging.info("  - get_user_email_context")
    logging.info("  - logout_user")
    logging.info("🔐 암호화 도구들:")
    logging.info("  - check_encryption_key")
    logging.info("🔐 OAuth 인증 도구들:")
    logging.info("  - oauth_login_gmail")
    logging.info("  - oauth_login_microsoft")
    logging.info("  - oauth_callback")
    logging.info("  - oauth_refresh_token")
    logging.info("  - oauth_auth_status")
    
    
    # HTTP 서버 시작 (OAuth 콜백용)
    def start_http_server():
        """OAuth 콜백을 위한 HTTP 서버 시작"""
        try:
            server = HTTPServer(('localhost', 8000), OAuthCallbackHandler)
            logging.info("🚀 OAuth 콜백 HTTP 서버 시작: http://localhost:8000")
            server.serve_forever()
        except Exception as e:
            logging.error(f"❌ HTTP 서버 시작 실패: {e}")
    
    # HTTP 서버를 별도 스레드에서 실행 (OAuth 콜백용)
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # FastAPI 서버를 별도 스레드에서 실행 (인증 API용)
    def start_fastapi_server():
        """FastAPI 서버 시작"""
        try:
            import uvicorn
            logging.info("🚀 FastAPI 인증 서버 시작: http://localhost:8001")
            uvicorn.run(auth_app, host="0.0.0.0", port=8001)
        except Exception as e:
            logging.error(f"❌ FastAPI 서버 시작 실패: {e}")
    
    fastapi_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    fastapi_thread.start()
    
    # FastMCP 서버 실행
    mcp.run()

if __name__ == "__main__":
    run_fastmcp_server()
