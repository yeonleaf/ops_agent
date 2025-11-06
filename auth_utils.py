#!/usr/bin/env python3
"""
사용자 인증 관련 유틸리티
비밀번호 해싱, 토큰 암호화, 세션 관리 등
"""

import bcrypt
import secrets
import base64
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import json
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class PasswordManager:
    """비밀번호 관리 클래스"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """비밀번호를 bcrypt로 해시 처리"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """비밀번호 검증"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

class TokenEncryption:
    """토큰 암호화/복호화 클래스"""
    
    def __init__(self, key: Optional[str] = None):
        if key:
            self.key = key.encode()
        else:
            # 환경변수에서 키 가져오기 또는 새로 생성
            key = os.getenv('ENCRYPTION_KEY')
            if not key:
                # 새 키 생성 (실제 운영에서는 안전한 곳에 저장)
                key = Fernet.generate_key().decode()
                print(f"⚠️ 새로운 암호화 키가 생성되었습니다. ENCRYPTION_KEY={key}")
            self.key = key.encode()
        
        self.cipher = Fernet(self.key)
    
    def encrypt_token(self, token: str) -> str:
        """토큰 암호화"""
        encrypted = self.cipher.encrypt(token.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """토큰 복호화"""
        encrypted = base64.b64decode(encrypted_token.encode('utf-8'))
        decrypted = self.cipher.decrypt(encrypted)
        return decrypted.decode('utf-8')

class SessionManager:
    """세션 관리 클래스"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = timedelta(hours=24)  # 24시간
    
    def create_session(self, user_id: int, email: str) -> str:
        """새 세션 생성"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + self.session_timeout
        
        self.sessions[session_id] = {
            'user_id': user_id,
            'email': email,
            'created_at': datetime.now(),
            'expires_at': expires_at
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 조회"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # 만료 확인
        if datetime.now() > session['expires_at']:
            del self.sessions[session_id]
            return None
        
        return session
    
    def delete_session(self, session_id: str):
        """세션 삭제"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def cleanup_expired_sessions(self):
        """만료된 세션 정리"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if now > session['expires_at']
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]

# 전역 인스턴스들
password_manager = PasswordManager()
token_encryption = TokenEncryption()
session_manager = SessionManager()
