#!/usr/bin/env python3
"""
User 테이블을 새로운 스키마로 마이그레이션하는 스크립트
- mail_type, google_refresh_token, jira_endpoint, jira_api_token 컬럼 제거
- 해당 데이터를 Integration 테이블로 이동
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_users_table():
    """User 테이블 마이그레이션"""
    db_path = "tickets.db"

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            logger.info("📋 1단계: 현재 테이블 구조 확인")

            # 현재 users 테이블의 컬럼 확인
            cursor.execute("PRAGMA table_info(users)")
            columns = {col[1]: col[2] for col in cursor.fetchall()}
            logger.info(f"   현재 users 테이블 컬럼: {list(columns.keys())}")

            # 존재하는 컬럼만 조회
            select_columns = ["id", "email", "password_hash", "created_at"]
            optional_columns = {
                "mail_type": None,
                "google_refresh_token": None,
                "jira_endpoint": None,
                "jira_api_token": None
            }

            for col in optional_columns.keys():
                if col in columns:
                    select_columns.append(col)
                    logger.info(f"   발견: {col} 컬럼")

            # 기존 users 테이블의 모든 데이터 조회
            query = f"SELECT {', '.join(select_columns)} FROM users"
            cursor.execute(query)
            users = cursor.fetchall()
            logger.info(f"   총 {len(users)}명의 사용자 데이터 발견")

            # 2단계: 연동 정보를 Integration 테이블로 마이그레이션
            logger.info("📋 2단계: 연동 정보를 Integration 테이블로 마이그레이션")
            migrated_count = 0

            # 컬럼 인덱스 매핑
            col_indices = {col: idx for idx, col in enumerate(select_columns)}

            for user in users:
                user_id = user[col_indices['id']]
                email = user[col_indices['email']]

                # Integration 테이블에 이미 데이터가 있는지 확인
                cursor.execute("SELECT COUNT(*) FROM integrations WHERE user_id = ?", (user_id,))
                if cursor.fetchone()[0] > 0:
                    logger.info(f"   사용자 {email}: Integration 데이터 이미 존재 (건너뜀)")
                    continue

                migrated_this_user = False

                # Google 연동 정보 마이그레이션
                if 'google_refresh_token' in col_indices:
                    google_token = user[col_indices['google_refresh_token']]
                    if google_token:
                        cursor.execute("""
                            INSERT INTO integrations (user_id, source, type, value, created_at, updated_at)
                            VALUES (?, 'google', 'token', ?, ?, ?)
                        """, (user_id, google_token, datetime.now().isoformat(), datetime.now().isoformat()))
                        logger.info(f"   사용자 {email}: Google 토큰 마이그레이션 완료")
                        migrated_this_user = True

                # Jira endpoint 마이그레이션
                if 'jira_endpoint' in col_indices:
                    jira_endpoint = user[col_indices['jira_endpoint']]
                    if jira_endpoint:
                        cursor.execute("""
                            INSERT INTO integrations (user_id, source, type, value, created_at, updated_at)
                            VALUES (?, 'jira', 'endpoint', ?, ?, ?)
                        """, (user_id, jira_endpoint, datetime.now().isoformat(), datetime.now().isoformat()))
                        logger.info(f"   사용자 {email}: Jira endpoint 마이그레이션 완료")
                        migrated_this_user = True

                # Jira token 마이그레이션
                if 'jira_api_token' in col_indices:
                    jira_token = user[col_indices['jira_api_token']]
                    if jira_token:
                        cursor.execute("""
                            INSERT INTO integrations (user_id, source, type, value, created_at, updated_at)
                            VALUES (?, 'jira', 'token', ?, ?, ?)
                        """, (user_id, jira_token, datetime.now().isoformat(), datetime.now().isoformat()))
                        logger.info(f"   사용자 {email}: Jira token 마이그레이션 완료")
                        migrated_this_user = True

                if migrated_this_user:
                    migrated_count += 1

            conn.commit()
            logger.info(f"   {migrated_count}명의 연동 정보 마이그레이션 완료")

            # 3단계: users 테이블 재생성
            logger.info("📋 3단계: Users 테이블 재생성")

            # 새 users 테이블 생성
            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 기존 데이터 복사 (연동 정보 제외)
            cursor.execute("""
                INSERT INTO users_new (id, email, password_hash, created_at)
                SELECT id, email, password_hash, created_at
                FROM users
            """)

            # 기존 테이블 삭제 및 이름 변경
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")

            # 인덱스 재생성
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

            conn.commit()
            logger.info("   Users 테이블 재생성 완료")

            # 4단계: 최종 확인
            logger.info("📋 4단계: 마이그레이션 결과 확인")
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            logger.info(f"   새 users 테이블 컬럼: {columns}")

            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            logger.info(f"   사용자 수: {user_count}명")

            cursor.execute("SELECT COUNT(*) FROM integrations")
            integration_count = cursor.fetchone()[0]
            logger.info(f"   연동 정보 수: {integration_count}개")

            logger.info("✅ 마이그레이션 완료!")

    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}")
        raise

if __name__ == "__main__":
    logger.info("⚠️  경고: 이 스크립트는 데이터베이스를 변경합니다.")
    logger.info("⚠️  먼저 tickets.db 파일을 백업하는 것을 권장합니다!")
    response = input("\n계속 진행하시겠습니까? (y/n): ")

    if response.lower() == 'y':
        migrate_users_table()
    else:
        logger.info("❌ 마이그레이션 취소됨")
