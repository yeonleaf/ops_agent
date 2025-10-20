#!/usr/bin/env python3
"""
User 테이블의 Jira 정보를 Integration 테이블로 마이그레이션하는 스크립트
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_jira_data():
    """User 테이블의 Jira 데이터를 Integration 테이블로 마이그레이션"""
    db_path = "tickets.db"

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # User 테이블에서 Jira 정보가 있는 사용자 조회
            cursor.execute("""
                SELECT id, jira_endpoint, jira_api_token
                FROM users
                WHERE jira_endpoint IS NOT NULL OR jira_api_token IS NOT NULL
            """)

            users_with_jira = cursor.fetchall()
            logger.info(f"📊 Jira 정보가 있는 사용자: {len(users_with_jira)}명")

            migrated_count = 0
            for user_id, jira_endpoint, jira_api_token in users_with_jira:
                logger.info(f"👤 사용자 ID {user_id} 마이그레이션 시작")

                # Integration 테이블에 이미 데이터가 있는지 확인
                cursor.execute("""
                    SELECT COUNT(*) FROM integrations
                    WHERE user_id = ? AND source = 'jira'
                """, (user_id,))

                existing_count = cursor.fetchone()[0]

                if existing_count > 0:
                    logger.info(f"  ℹ️  Integration 테이블에 이미 데이터가 있음 (건너뜀)")
                    continue

                # Endpoint 마이그레이션
                if jira_endpoint:
                    cursor.execute("""
                        INSERT INTO integrations (user_id, source, type, value, created_at, updated_at)
                        VALUES (?, 'jira', 'endpoint', ?, ?, ?)
                    """, (user_id, jira_endpoint, datetime.now().isoformat(), datetime.now().isoformat()))
                    logger.info(f"  ✅ Endpoint 마이그레이션 완료")

                # Token 마이그레이션
                if jira_api_token:
                    cursor.execute("""
                        INSERT INTO integrations (user_id, source, type, value, created_at, updated_at)
                        VALUES (?, 'jira', 'token', ?, ?, ?)
                    """, (user_id, jira_api_token, datetime.now().isoformat(), datetime.now().isoformat()))
                    logger.info(f"  ✅ Token 마이그레이션 완료")

                migrated_count += 1

            conn.commit()
            logger.info(f"🎉 마이그레이션 완료: {migrated_count}명의 사용자 데이터 이동")

            # 마이그레이션 후 User 테이블의 Jira 정보 삭제 (선택사항)
            if migrated_count > 0:
                response = input("\nUser 테이블의 Jira 정보를 삭제하시겠습니까? (y/n): ")
                if response.lower() == 'y':
                    cursor.execute("""
                        UPDATE users
                        SET jira_endpoint = NULL, jira_api_token = NULL
                        WHERE jira_endpoint IS NOT NULL OR jira_api_token IS NOT NULL
                    """)
                    conn.commit()
                    logger.info("✅ User 테이블의 Jira 정보 삭제 완료")
                else:
                    logger.info("ℹ️  User 테이블의 Jira 정보 유지 (나중에 ALTER TABLE로 컬럼 삭제 가능)")

    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}")
        raise

if __name__ == "__main__":
    migrate_jira_data()
