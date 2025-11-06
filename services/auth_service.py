#!/usr/bin/env python3
"""
Auth Service - 인증 서비스

JWT 기반 사용자 인증 및 관리
"""

import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os
from models.report_models import User


class AuthService:
    """인증 서비스"""

    def __init__(self, db_session, secret_key=None):
        """
        Args:
            db_session: SQLAlchemy 세션
            secret_key: JWT 시크릿 키
        """
        self.db = db_session
        self.secret_key = secret_key or os.getenv('JWT_SECRET_KEY', 'default-secret-key-change-me')
        self.algorithm = 'HS256'
        self.token_expiry_hours = 24

    def hash_password(self, password: str) -> str:
        """비밀번호 해싱"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """비밀번호 검증"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def generate_token(self, user_id: int, username: str) -> str:
        """JWT 토큰 생성"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Optional[Dict]:
        """JWT 토큰 디코딩"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("토큰이 만료되었습니다")
        except jwt.InvalidTokenError:
            raise ValueError("유효하지 않은 토큰입니다")

    def register(self, username: str, email: str, password: str) -> Dict:
        """
        회원가입

        Args:
            username: 사용자명
            email: 이메일
            password: 비밀번호

        Returns:
            {
                "user_id": int,
                "username": str,
                "token": str
            }

        Raises:
            ValueError: 중복된 사용자명/이메일
        """
        # 중복 체크
        existing = self.db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            if existing.username == username:
                raise ValueError("이미 사용 중인 사용자명입니다")
            else:
                raise ValueError("이미 사용 중인 이메일입니다")

        # 비밀번호 해싱
        password_hash = self.hash_password(password)

        # 사용자 생성
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # 토큰 생성
        token = self.generate_token(user.id, user.username)

        return {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'token': token
        }

    def login(self, username: str, password: str) -> Dict:
        """
        로그인

        Args:
            username: 사용자명
            password: 비밀번호

        Returns:
            {
                "user_id": int,
                "username": str,
                "token": str
            }

        Raises:
            ValueError: 인증 실패
        """
        # 사용자 조회
        user = self.db.query(User).filter(User.username == username).first()

        if not user:
            raise ValueError("사용자명 또는 비밀번호가 올바르지 않습니다")

        # 비밀번호 검증
        if not self.verify_password(password, user.password_hash):
            raise ValueError("사용자명 또는 비밀번호가 올바르지 않습니다")

        # 토큰 생성
        token = self.generate_token(user.id, user.username)

        return {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'token': token
        }

    def verify_token_and_get_user(self, token: str) -> Optional[User]:
        """
        토큰 검증 및 사용자 조회

        Args:
            token: JWT 토큰

        Returns:
            User 객체 또는 None

        Raises:
            ValueError: 유효하지 않은 토큰
        """
        payload = self.decode_token(token)
        user_id = payload.get('user_id')

        if not user_id:
            raise ValueError("유효하지 않은 토큰입니다")

        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")

        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """사용자 ID로 조회"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """사용자명으로 조회"""
        return self.db.query(User).filter(User.username == username).first()


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager

    print("=== Auth Service 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_auth.db')
    db.create_tables()
    session = db.get_session()

    try:
        # 서비스 생성
        auth_service = AuthService(session, secret_key='test-secret-key')

        # 1. 회원가입
        print("1. 회원가입 테스트")
        result = auth_service.register(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        print(f"   ✅ 회원가입 성공: {result['username']}")
        print(f"   Token: {result['token'][:50]}...")

        # 2. 중복 회원가입 시도
        print("\n2. 중복 회원가입 테스트")
        try:
            auth_service.register('testuser', 'test2@example.com', 'password')
        except ValueError as e:
            print(f"   ✅ 예상된 오류: {e}")

        # 3. 로그인
        print("\n3. 로그인 테스트")
        login_result = auth_service.login('testuser', 'password123')
        print(f"   ✅ 로그인 성공: {login_result['username']}")
        print(f"   Token: {login_result['token'][:50]}...")

        # 4. 잘못된 비밀번호
        print("\n4. 잘못된 비밀번호 테스트")
        try:
            auth_service.login('testuser', 'wrongpassword')
        except ValueError as e:
            print(f"   ✅ 예상된 오류: {e}")

        # 5. 토큰 검증
        print("\n5. 토큰 검증 테스트")
        user = auth_service.verify_token_and_get_user(login_result['token'])
        print(f"   ✅ 토큰 검증 성공: {user.username}")

        # 6. 잘못된 토큰
        print("\n6. 잘못된 토큰 테스트")
        try:
            auth_service.verify_token_and_get_user('invalid.token.here')
        except ValueError as e:
            print(f"   ✅ 예상된 오류: {e}")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
