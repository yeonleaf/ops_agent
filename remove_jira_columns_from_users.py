#!/usr/bin/env python3
"""
User 테이블에서 jira_endpoint와 jira_api_token 컬럼을 제거하는 스크립트

SQLite는 ALTER TABLE DROP COLUMN을 지원하지 않으므로,
테이블을 재생성하는 방식으로 컬럼을 제거합니다.
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_jira_columns():
    """User 테이블에서 Jira 관련 컬럼 제거"""
    db_path = "tickets.db"

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            logger.info("📋 현재 users 테이블 스키마 확인")
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            logger.info(f"현재 컬럼: {[col[1] for col in columns]}")

            # jira_endpoint, jira_api_token이 있는지 확인
            column_names = [col[1] for col in columns]
            if 'jira_endpoint' not in column_names and 'jira_api_token' not in column_names:
                logger.info("✅ Jira 컬럼이 이미 없습니다. 작업 불필요.")
                return

            logger.info("⚠️  경고: 이 작업은 users 테이블을 재생성합니다.")
            logger.info("⚠️  먼저 데이터베이스 백업을 권장합니다!")
            response = input("\n계속 진행하시겠습니까? (y/n): ")

            if response.lower() != 'y':
                logger.info("❌ 작업 취소됨")
                return

            # 1. 임시 테이블 생성 (Jira 컬럼 제외)
            logger.info("1️⃣  임시 테이블 생성 중...")
            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    google_refresh_token TEXT
                )
            """)

            # 2. 기존 데이터 복사 (Jira 컬럼 제외)
            logger.info("2️⃣  데이터 복사 중...")
            cursor.execute("""
                INSERT INTO users_new (id, email, password_hash, created_at, google_refresh_token)
                SELECT id, email, password_hash, created_at, google_refresh_token
                FROM users
            """)

            # 3. 기존 테이블 삭제
            logger.info("3️⃣  기존 테이블 삭제 중...")
            cursor.execute("DROP TABLE users")

            # 4. 새 테이블 이름 변경
            logger.info("4️⃣  테이블 이름 변경 중...")
            cursor.execute("ALTER TABLE users_new RENAME TO users")

            # 5. 인덱스 재생성 (필요한 경우)
            logger.info("5️⃣  인덱스 재생성 중...")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

            conn.commit()
            logger.info("✅ Jira 컬럼 제거 완료!")

            # 최종 스키마 확인
            cursor.execute("PRAGMA table_info(users)")
            new_columns = cursor.fetchall()
            logger.info(f"새 컬럼: {[col[1] for col in new_columns]}")

    except Exception as e:
        logger.error(f"❌ 컬럼 제거 실패: {e}")
        raise

if __name__ == "__main__":
    remove_jira_columns()
