#!/usr/bin/env python3
"""
보안 강화된 MCP 이메일 서비스 서버
OAuth2 인증 및 HttpOnly 쿠키 기반 세션 관리
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Cookie
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="Secure MCP Email Server", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501", "http://localhost:8504"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastMCP 인스턴스 생성
mcp = FastMCP("SecureEmailService")

# OAuth 서버 URL
OAUTH_SERVER_URL = "http://localhost:8000"

class EmailRequest(BaseModel):
    """이메일 요청 모델"""
    provider: str
    filters: Optional[Dict[str, Any]] = None
    max_results: int = 50

class TokenInfo(BaseModel):
    """토큰 정보 모델"""
    access_token: str
    provider: str
    expires_at: Optional[datetime] = None

async def get_current_token(request: Request) -> TokenInfo:
    """현재 인증된 토큰 정보 가져오기"""
    try:
        # 세션 ID로 인증 상태 확인
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        
        # OAuth 서버에서 세션 상태 확인
        auth_response = requests.get(
            f"{OAUTH_SERVER_URL}/auth/status",
            cookies={"session_id": session_id}
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        
        auth_data = auth_response.json()
        if not auth_data.get("authenticated"):
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        
        # 세션에서 토큰 정보 가져오기
        # 실제로는 OAuth 서버에서 토큰을 가져와야 함
        access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not access_token:
            raise HTTPException(status_code=401, detail="액세스 토큰이 필요합니다.")
        
        return TokenInfo(
            access_token=access_token,
            provider=auth_data.get("provider", "unknown"),
            expires_at=datetime.fromisoformat(auth_data.get("expires_at")) if auth_data.get("expires_at") else None
        )
        
    except requests.RequestException as e:
        logger.error(f"인증 확인 실패: {e}")
        raise HTTPException(status_code=500, detail="인증 서버 연결 실패")

@mcp.tool()
async def get_authenticated_emails(
    provider: str,
    filters: Optional[Dict[str, Any]] = None,
    max_results: int = 50,
    request: Request = None
) -> List[Dict[str, Any]]:
    """
    인증된 사용자의 이메일을 안전하게 가져오기
    
    Args:
        provider: 이메일 제공자 (gmail, outlook)
        filters: 이메일 필터 조건
        max_results: 최대 결과 수
        
    Returns:
        List[Dict[str, Any]]: 이메일 목록
    """
    try:
        # 인증 확인
        token_info = await get_current_token(request)
        
        # 이메일 서비스 호출
        from unified_email_service import UnifiedEmailService
        
        # 토큰을 사용하여 이메일 서비스 초기화
        service = UnifiedEmailService(provider, access_token=token_info.access_token)
        
        # 이메일 가져오기
        if filters:
            emails = service.search_emails(filters.get("query", ""), max_results)
        else:
            emails = service.get_all_emails(max_results)
        
        # 결과 변환
        email_list = []
        for email in emails:
            email_dict = email.model_dump()
            email_list.append({
                'id': email_dict.get('id'),
                'subject': email_dict.get('subject'),
                'sender': email_dict.get('sender'),
                'body': email_dict.get('body'),
                'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                'is_read': email_dict.get('is_read'),
                'priority': email_dict.get('priority'),
                'has_attachments': email_dict.get('has_attachments')
            })
        
        logger.info(f"✅ {len(email_list)}개 이메일 조회 완료 (인증됨)")
        return email_list
        
    except Exception as e:
        logger.error(f"❌ 인증된 이메일 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp.tool()
async def create_authenticated_ticket(
    email_id: str,
    provider: str,
    request: Request = None
) -> Dict[str, Any]:
    """
    인증된 사용자의 이메일로부터 티켓 생성
    
    Args:
        email_id: 이메일 ID
        provider: 이메일 제공자
        
    Returns:
        Dict[str, Any]: 생성된 티켓 정보
    """
    try:
        # 인증 확인
        token_info = await get_current_token(request)
        
        # 이메일 서비스 호출
        from unified_email_service import UnifiedEmailService
        service = UnifiedEmailService(provider, access_token=token_info.access_token)
        
        # 특정 이메일 가져오기
        email = service.get_email_by_id(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="이메일을 찾을 수 없습니다.")
        
        # 티켓 생성
        from memory_based_ticket_processor import create_memory_based_ticket_processor
        processor = create_memory_based_ticket_processor()
        
        # 이메일을 티켓으로 변환
        ticket_data = {
            'message_id': email.id,
            'subject': email.subject,
            'sender': email.sender,
            'body': email.body,
            'received_date': email.received_date,
            'priority': email.priority.value if email.priority else 'Medium'
        }
        
        result = processor.process_single_email(ticket_data)
        
        logger.info(f"✅ 티켓 생성 완료: {email_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ 티켓 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp.tool()
async def refresh_authentication(request: Request) -> Dict[str, Any]:
    """
    인증 토큰 재발급
    
    Returns:
        Dict[str, Any]: 새로운 토큰 정보
    """
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="세션이 없습니다.")
        
        # OAuth 서버에서 토큰 재발급
        refresh_response = requests.post(
            f"{OAUTH_SERVER_URL}/auth/refresh",
            json={"provider": "gmail"},  # 기본값, 실제로는 동적으로 결정
            cookies={"session_id": session_id}
        )
        
        if refresh_response.status_code != 200:
            raise HTTPException(status_code=401, detail="토큰 재발급 실패")
        
        token_data = refresh_response.json()
        
        logger.info("✅ 토큰 재발급 완료")
        return {
            "access_token": token_data["access_token"],
            "expires_in": token_data["expires_in"],
            "provider": token_data["provider"]
        }
        
    except requests.RequestException as e:
        logger.error(f"토큰 재발급 실패: {e}")
        raise HTTPException(status_code=500, detail="인증 서버 연결 실패")

@mcp.tool()
async def get_auth_status(request: Request) -> Dict[str, Any]:
    """
    인증 상태 확인
    
    Returns:
        Dict[str, Any]: 인증 상태 정보
    """
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            return {"authenticated": False, "message": "세션이 없습니다."}
        
        # OAuth 서버에서 상태 확인
        auth_response = requests.get(
            f"{OAUTH_SERVER_URL}/auth/status",
            cookies={"session_id": session_id}
        )
        
        if auth_response.status_code == 200:
            return auth_response.json()
        else:
            return {"authenticated": False, "message": "인증이 필요합니다."}
        
    except requests.RequestException as e:
        logger.error(f"인증 상태 확인 실패: {e}")
        return {"authenticated": False, "message": "인증 서버 연결 실패"}

# FastAPI 라우트 등록
app.include_router(mcp.router)

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Secure MCP Email Server",
        "version": "1.0.0",
        "oauth_server": OAUTH_SERVER_URL
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8505, log_level="info")
