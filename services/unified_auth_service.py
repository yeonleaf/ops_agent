#!/usr/bin/env python3
"""
Unified Auth Service - tickets.db와 reports.db 통합 인증

Streamlit 앱(tickets.db)의 계정으로 웹 대시보드(reports.db) 로그인 지원
"""

import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os


class UnifiedAuthService:
    """통합 인증 서비스"""

    def __init__(self, tickets_db_path='tickets.db', reports_session=None):
        """
        Args:
            tickets_db_path: tickets.db 경로
            reports_session: reports.db SQLAlchemy 세션
        """
        self.tickets_db_path = tickets_db_path
        self.reports_session = reports_session
        self.secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')

    def login(self, email: str, password: str) -> Dict:
        """
        로그인 (tickets.db에서 인증)

        Args:
            email: 이메일
            password: 비밀번호

        Returns:
            {
                "user_id": int,
                "username": str,
                "email": str,
                "token": str
            }

        Raises:
            ValueError: 로그인 실패
        """
        # 1. tickets.db에서 사용자 조회
        conn = sqlite3.connect(self.tickets_db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id, email, password_hash, user_name, system_name FROM users WHERE email = ?',
            (email,)
        )
        user_row = cursor.fetchone()
        conn.close()

        if not user_row:
            raise ValueError('이메일 또는 비밀번호가 올바르지 않습니다')

        tickets_user_id, db_email, password_hash, user_name, system_name = user_row

        # 2. 비밀번호 확인
        if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            raise ValueError('이메일 또는 비밀번호가 올바르지 않습니다')

        # 3. reports.db에 사용자 동기화
        reports_user_id = self._sync_user_to_reports_db(
            tickets_user_id=tickets_user_id,
            email=db_email,
            user_name=user_name,
            system_name=system_name,
            password_hash=password_hash
        )

        # 4. JWT 토큰 생성 (email 기반)
        token = self._generate_token(email, reports_user_id)

        return {
            'user_id': reports_user_id,
            'username': user_name or email.split('@')[0],
            'email': db_email,
            'token': token
        }

    def register(self, email: str, password: str, user_name: str = None) -> Dict:
        """
        회원가입 (tickets.db와 reports.db 모두에 생성)

        Args:
            email: 이메일
            password: 비밀번호
            user_name: 사용자 이름

        Returns:
            로그인과 동일한 형식

        Raises:
            ValueError: 회원가입 실패
        """
        # 1. tickets.db에 사용자 생성
        conn = sqlite3.connect(self.tickets_db_path)
        cursor = conn.cursor()

        # 중복 확인
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            raise ValueError('이미 존재하는 이메일입니다')

        # 비밀번호 해싱
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 사용자 생성
        cursor.execute(
            '''INSERT INTO users (email, password_hash, user_name, created_at)
               VALUES (?, ?, ?, ?)''',
            (email, password_hash, user_name, datetime.utcnow().isoformat())
        )
        conn.commit()
        tickets_user_id = cursor.lastrowid
        conn.close()

        # 2. reports.db에 동기화
        reports_user_id = self._sync_user_to_reports_db(
            tickets_user_id=tickets_user_id,
            email=email,
            user_name=user_name,
            system_name=None,
            password_hash=password_hash
        )

        # 3. 토큰 생성
        token = self._generate_token(email, reports_user_id)

        return {
            'user_id': reports_user_id,
            'username': user_name or email.split('@')[0],
            'email': email,
            'token': token
        }

    def verify_token_and_get_user(self, token: str):
        """
        토큰 검증 및 사용자 조회

        Args:
            token: JWT 토큰

        Returns:
            User 객체 (reports.db의 User 모델)

        Raises:
            ValueError: 토큰 검증 실패
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            email = payload.get('email')
            user_id = payload.get('user_id')

            if not email or not user_id:
                raise ValueError('유효하지 않은 토큰입니다')

            # reports.db에서 사용자 조회
            from models.report_models import User
            user = self.reports_session.query(User).filter_by(id=user_id, email=email).first()

            if not user:
                raise ValueError('사용자를 찾을 수 없습니다')

            return user

        except jwt.ExpiredSignatureError:
            raise ValueError('토큰이 만료되었습니다')
        except jwt.InvalidTokenError:
            raise ValueError('유효하지 않은 토큰입니다')

    def _sync_user_to_reports_db(
        self,
        tickets_user_id: int,
        email: str,
        user_name: str,
        system_name: str,
        password_hash: str
    ) -> int:
        """
        tickets.db 사용자를 reports.db에 동기화

        Args:
            tickets_user_id: tickets.db의 user_id
            email: 이메일
            user_name: 사용자 이름
            system_name: 시스템 이름
            password_hash: 비밀번호 해시

        Returns:
            reports.db의 user_id
        """
        from models.report_models import User

        # 이미 존재하는지 확인 (email 기준)
        existing_user = self.reports_session.query(User).filter_by(email=email).first()

        if existing_user:
            # 정보 업데이트
            if user_name:
                existing_user.username = user_name or email.split('@')[0]
            if system_name:
                existing_user.system_name = system_name
            self.reports_session.commit()
            return existing_user.id

        # 새로 생성
        new_user = User(
            username=user_name or email.split('@')[0],
            email=email,
            password_hash=password_hash,
            system_name=system_name,
            created_at=datetime.utcnow()
        )
        self.reports_session.add(new_user)
        self.reports_session.commit()
        self.reports_session.refresh(new_user)

        return new_user.id

    def _generate_token(self, email: str, user_id: int) -> str:
        """
        JWT 토큰 생성

        Args:
            email: 이메일
            user_id: reports.db의 user_id

        Returns:
            JWT 토큰
        """
        payload = {
            'email': email,
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=7)  # 7일 유효
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager

    print("=== Unified Auth Service 테스트 ===\n")

    # reports.db 세션
    db_manager = DatabaseManager('reports.db')
    db_manager.create_tables()
    session = db_manager.get_session()

    try:
        auth_service = UnifiedAuthService(
            tickets_db_path='tickets.db',
            reports_session=session
        )

        # 기존 계정으로 로그인 테스트
        print("1. 기존 계정 로그인 테스트")
        result = auth_service.login('dpffpsk907@gmail.com', 'test1234')
        print(f"   ✅ 로그인 성공!")
        print(f"   User ID: {result['user_id']}")
        print(f"   Username: {result['username']}")
        print(f"   Email: {result['email']}")
        print(f"   Token: {result['token'][:50]}...")

        # 토큰 검증
        print("\n2. 토큰 검증 테스트")
        user = auth_service.verify_token_and_get_user(result['token'])
        print(f"   ✅ 토큰 유효!")
        print(f"   User: {user.username} ({user.email})")

    except Exception as e:
        print(f"   ❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()
