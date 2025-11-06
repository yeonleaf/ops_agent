#!/usr/bin/env python3
"""
Jira 토큰 재암호화 스크립트

.env에 ENCRYPTION_KEY가 없을 때 사용:
1. 새 암호화 키 생성
2. 평문 토큰 입력받아 암호화
3. DB 업데이트
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from auth_utils import TokenEncryption
from cryptography.fernet import Fernet

def main():
    print("=" * 70)
    print("🔐 Jira 토큰 재암호화 도구")
    print("=" * 70)

    # 1. 현재 암호화 키 확인
    print("\n[Step 1] 암호화 키 확인")
    current_key = os.getenv('ENCRYPTION_KEY')

    if current_key:
        print(f"✅ 현재 .env에 ENCRYPTION_KEY 설정됨: {current_key[:20]}...")
        print("\n이 키로 토큰을 암호화합니다.")
        response = input("계속하시겠습니까? (y/n): ")
        if response.lower() != 'y':
            print("❌ 취소됨")
            sys.exit(0)
    else:
        print("⚠️  .env에 ENCRYPTION_KEY가 없습니다.")
        print("새 암호화 키를 생성합니다.")
        new_key = Fernet.generate_key().decode()
        print(f"\n✅ 새 키 생성: {new_key}")
        print(f"\n⚠️  이 키를 .env 파일에 저장하세요:")
        print(f"    ENCRYPTION_KEY={new_key}")

        # .env 업데이트 확인
        response = input("\n.env 파일에 키를 추가했습니까? (y/n): ")
        if response.lower() != 'y':
            print("❌ .env 파일에 키를 추가한 후 다시 실행하세요")
            sys.exit(1)

        # .env 다시 로드
        from dotenv import load_dotenv
        load_dotenv(override=True)

    # 2. DB 연결
    print("\n[Step 2] 데이터베이스 연결")
    db_path = input("DB 경로 (기본값: tickets.db): ").strip() or "tickets.db"

    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Jira 사용자 조회
    cursor.execute("""
        SELECT DISTINCT user_id
        FROM integrations
        WHERE source = 'jira' AND type = 'token'
        ORDER BY user_id
    """)
    user_ids = [row[0] for row in cursor.fetchall()]

    if not user_ids:
        print("⚠️ Jira 토큰이 설정된 사용자가 없습니다")
        conn.close()
        sys.exit(0)

    print(f"✅ Jira 토큰이 있는 사용자: {user_ids}")

    # 3. 사용자별 토큰 재암호화
    print("\n[Step 3] 토큰 재암호화")
    token_encryption = TokenEncryption()

    for user_id in user_ids:
        print(f"\n--- User {user_id} ---")

        # 평문 토큰 입력
        print(f"User {user_id}의 Jira API 토큰을 입력하세요")
        print("(Jira → Settings → Personal Access Tokens에서 발급)")
        plain_token = input("토큰: ").strip()

        if not plain_token:
            print(f"⚠️ User {user_id} 스킵 (토큰 없음)")
            continue

        # 암호화
        encrypted_token = token_encryption.encrypt_token(plain_token)

        # DB 업데이트
        cursor.execute("""
            UPDATE integrations
            SET value = ?
            WHERE user_id = ? AND source = 'jira' AND type = 'token'
        """, (encrypted_token, user_id))

        print(f"✅ User {user_id} 토큰 업데이트 완료")

    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("✅ 모든 토큰 재암호화 완료!")
    print("=" * 70)
    print("\n다음 단계:")
    print("1. .env 파일에 ENCRYPTION_KEY가 저장되어 있는지 확인")
    print("2. Jira 배치 실행:")
    print("   python batch/jira_sync.py --user-id 1 --debug")

if __name__ == "__main__":
    main()
