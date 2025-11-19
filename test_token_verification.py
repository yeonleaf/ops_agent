#!/usr/bin/env python3
"""
JWT 토큰 검증 테스트
"""
import jwt
import os
from models.report_models import DatabaseManager, User

# 테스트할 토큰
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImRwZmZwc2s5MDdAZ21haWwuY29tIiwidXNlcl9pZCI6MiwiZXhwIjoxNzYzNjAyMzI1fQ.62cyKRI_-5-yp8OYZaR-kmMcKmdGM3AO5asJxXEed8I"

# Secret key (UnifiedAuthService와 동일)
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')

print("=== JWT 토큰 검증 테스트 ===\n")
print(f"Secret Key: {SECRET_KEY}")
print(f"Token: {TOKEN[:50]}...\n")

try:
    # 토큰 디코딩
    payload = jwt.decode(TOKEN, SECRET_KEY, algorithms=['HS256'])
    print("✅ 토큰 디코딩 성공!")
    print(f"   Payload: {payload}")

    email = payload.get('email')
    user_id = payload.get('user_id')

    print(f"\n   Email: {email}")
    print(f"   User ID: {user_id}")

    # DB에서 사용자 조회
    print("\n데이터베이스에서 사용자 조회 중...")
    db_manager = DatabaseManager('reports.db')
    session = db_manager.get_session()

    user = session.query(User).filter_by(id=user_id, email=email).first()

    if user:
        print(f"✅ 사용자 발견!")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
    else:
        print(f"❌ 사용자를 찾을 수 없습니다 (id={user_id}, email={email})")

        # 디버깅: 모든 사용자 조회
        all_users = session.query(User).all()
        print(f"\n   DB의 모든 사용자:")
        for u in all_users:
            print(f"     - {u.id}: {u.username} ({u.email})")

    session.close()

except jwt.ExpiredSignatureError:
    print("❌ 토큰이 만료되었습니다")
except jwt.InvalidTokenError as e:
    print(f"❌ 유효하지 않은 토큰: {e}")
except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()
