#!/usr/bin/env python3
"""
사용자 인증 API 서버
회원가입, 로그인, 외부 서비스 연동 관리
"""

from fastapi import FastAPI, HTTPException, Depends, Cookie, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import uvicorn
from datetime import datetime

from database_models import DatabaseManager, User
from auth_utils import password_manager, token_encryption, session_manager

app = FastAPI(title="Ops Agent Auth API", version="1.0.0")

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

# === Pydantic 모델들 ===

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

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
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "has_google_token": current_user.google_refresh_token is not None,
        "has_jira_info": current_user.jira_endpoint is not None,
        "created_at": current_user.created_at
    }

@app.post("/user/integrations/jira")
async def update_jira_integration(
    request: JiraIntegrationRequest,
    current_user: User = Depends(get_current_user)
):
    """Jira 연동 정보 저장"""
    try:
        # API 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.jira_api_token)
        
        # 데이터베이스 업데이트
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
    """Jira 연동 정보 조회 (토큰은 마스킹)"""
    if not current_user.jira_endpoint:
        return {
            "success": False,
            "message": "Jira 연동 정보가 없습니다"
        }
    
    return {
        "success": True,
        "jira_endpoint": current_user.jira_endpoint,
        "has_api_token": current_user.jira_api_token is not None
    }

@app.post("/user/integrations/google")
async def update_google_token(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Google Refresh Token 저장"""
    try:
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
        
        # 데이터베이스 업데이트
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
        # 이메일로 사용자 조회
        user = db_manager.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 토큰 암호화
        encrypted_token = token_encryption.encrypt_token(request.refresh_token)
        
        # 데이터베이스 업데이트
        db_manager.update_user_google_token(user.id, encrypted_token)
        
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
    if not current_user.google_refresh_token:
        return {
            "success": False,
            "message": "Google 연동 정보가 없습니다"
        }
    
    try:
        # 토큰 복호화
        decrypted_token = token_encryption.decrypt_token(current_user.google_refresh_token)
        
        return {
            "success": True,
            "has_refresh_token": True,
            "token_preview": decrypted_token[:10] + "..."  # 보안을 위해 일부만 표시
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Google 토큰 복호화 중 오류가 발생했습니다"
        }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    # 만료된 세션 정리 (주기적으로 실행)
    import asyncio
    import threading
    
    def cleanup_sessions():
        while True:
            session_manager.cleanup_expired_sessions()
            threading.Event().wait(3600)  # 1시간마다 실행
    
    cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    cleanup_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
