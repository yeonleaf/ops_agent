#!/usr/bin/env python3
"""
Jira 배치 설정 관리 모듈

integration 테이블에서 Jira 연동 정보를 로드하고,
batch_history 테이블을 관리합니다.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
import os

# auth_utils에서 TokenEncryption import
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth_utils import TokenEncryption

logger = logging.getLogger(__name__)


def create_batch_history_table(db_path: str = "tickets.db") -> bool:
    """
    batch_history 테이블 생성 (없을 경우)

    Args:
        db_path: SQLite DB 경로

    Returns:
        성공 여부
    """
    try:
        # SQL 파일 읽기
        sql_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations",
            "create_batch_history.sql"
        )

        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # DB 연결 및 실행
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 여러 SQL 문 실행
        cursor.executescript(sql_script)

        conn.commit()
        conn.close()

        logger.info(f"✅ batch_history 테이블 생성 완료: {db_path}")
        return True

    except Exception as e:
        logger.error(f"❌ batch_history 테이블 생성 실패: {e}")
        return False


def load_jira_config(user_id: int, db_path: str = "tickets.db") -> Optional[Dict]:
    """
    integration 테이블에서 Jira 설정 로드

    Args:
        user_id: 사용자 ID
        db_path: SQLite DB 경로

    Returns:
        {
            "endpoint": "https://jira.skbroadband.com",
            "token": "decrypted_token",  # 복호화된 토큰
            "projects": ["BTVO"],
            "labels": {"BTVO": ["NCMS"]}
        }
        또는 None (설정 없음)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Jira 연동 정보 조회
        cursor.execute("""
            SELECT type, value FROM integrations
            WHERE user_id = ? AND source = 'jira'
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"⚠️ User {user_id}의 Jira 연동 정보가 없습니다")
            return None

        # 데이터 파싱
        config = {}
        for type_name, value in rows:
            if type_name == "endpoint":
                config["endpoint"] = value
            elif type_name == "token":
                # 토큰 복호화
                token_encryption = TokenEncryption()
                config["token"] = token_encryption.decrypt_token(value)
            elif type_name == "project":
                # JSON 배열 파싱
                config["projects"] = json.loads(value)
            elif type_name == "labels":
                # JSON 객체 파싱
                config["labels"] = json.loads(value)

        # 필수 필드 확인
        if "endpoint" not in config or "token" not in config:
            logger.error(f"❌ User {user_id}의 Jira 필수 정보 누락 (endpoint 또는 token)")
            return None

        # projects가 없으면 빈 리스트
        if "projects" not in config:
            config["projects"] = []

        # labels가 없으면 빈 객체
        if "labels" not in config:
            config["labels"] = {}

        logger.info(f"✅ User {user_id} Jira 설정 로드 완료")
        logger.debug(f"   - Endpoint: {config['endpoint']}")
        logger.debug(f"   - Projects: {config['projects']}")
        logger.debug(f"   - Labels: {config['labels']}")

        return config

    except Exception as e:
        logger.error(f"❌ Jira 설정 로드 실패: {e}")
        return None


def get_last_sync_time(
    user_id: int,
    batch_type: str = "jira_sync",
    db_path: str = "tickets.db",
    default_days: int = 3650
) -> datetime:
    """
    batch_history 테이블에서 마지막 배치 실행 시각 조회

    Args:
        user_id: 사용자 ID
        batch_type: 배치 타입 (기본값: "jira_sync")
        db_path: SQLite DB 경로
        default_days: 마지막 실행 이력이 없을 경우 기본 조회 기간 (일, 기본값: 3650일=10년)

    Returns:
        마지막 성공 실행 시각 (없으면 N일 전 기본값)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT last_run_at FROM batch_history
            WHERE user_id = ? AND batch_type = ? AND status = 'success'
            ORDER BY last_run_at DESC LIMIT 1
        """, (user_id, batch_type))

        result = cursor.fetchone()
        conn.close()

        if result:
            last_run_at = datetime.fromisoformat(result[0])
            logger.info(f"✅ 마지막 동기화 시각: {last_run_at}")
            return last_run_at
        else:
            default_time = datetime.now() - timedelta(days=default_days)
            logger.info(f"✅ 마지막 동기화 이력 없음. 기본값 사용: {default_time} ({default_days}일 전)")
            return default_time

    except Exception as e:
        logger.error(f"❌ 마지막 동기화 시각 조회 실패: {e}")
        # 에러 발생 시 기본값 반환
        default_time = datetime.now() - timedelta(days=default_days)
        return default_time


def update_batch_history(
    user_id: int,
    batch_type: str,
    status: str,
    processed_count: int = 0,
    error_message: Optional[str] = None,
    db_path: str = "tickets.db"
) -> bool:
    """
    batch_history 테이블에 실행 이력 저장/업데이트 (UPSERT)

    Args:
        user_id: 사용자 ID
        batch_type: 배치 타입 (예: "jira_sync")
        status: 'success' 또는 'failed'
        processed_count: 처리된 청크 개수
        error_message: 에러 메시지 (실패 시)
        db_path: SQLite DB 경로

    Returns:
        성공 여부
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO batch_history (
                user_id, batch_type, last_run_at, status,
                processed_count, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, batch_type) DO UPDATE SET
                last_run_at = excluded.last_run_at,
                status = excluded.status,
                processed_count = excluded.processed_count,
                error_message = excluded.error_message
        """, (user_id, batch_type, now, status, processed_count, error_message))

        conn.commit()
        conn.close()

        logger.info(f"✅ 배치 이력 저장 완료: user_id={user_id}, status={status}, count={processed_count}")
        return True

    except Exception as e:
        logger.error(f"❌ 배치 이력 저장 실패: {e}")
        return False


def get_batch_history(
    user_id: int,
    batch_type: str = "jira_sync",
    db_path: str = "tickets.db"
) -> Optional[Dict]:
    """
    batch_history 조회 (디버깅/모니터링용)

    Args:
        user_id: 사용자 ID
        batch_type: 배치 타입
        db_path: SQLite DB 경로

    Returns:
        배치 이력 딕셔너리 또는 None
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, user_id, batch_type, last_run_at, status,
                processed_count, error_message, created_at
            FROM batch_history
            WHERE user_id = ? AND batch_type = ?
        """, (user_id, batch_type))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "batch_type": row[2],
                "last_run_at": row[3],
                "status": row[4],
                "processed_count": row[5],
                "error_message": row[6],
                "created_at": row[7]
            }
        else:
            return None

    except Exception as e:
        logger.error(f"❌ 배치 이력 조회 실패: {e}")
        return None


def get_all_jira_users(db_path: str = "tickets.db") -> List[int]:
    """
    Jira 연동이 설정된 모든 사용자 ID 조회

    Args:
        db_path: SQLite DB 경로

    Returns:
        사용자 ID 리스트
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Jira 연동 정보가 있는 사용자 조회
        # endpoint와 token이 모두 있는 사용자만
        cursor.execute("""
            SELECT DISTINCT user_id
            FROM integrations
            WHERE source = 'jira'
            AND user_id IN (
                SELECT user_id FROM integrations WHERE source = 'jira' AND type = 'endpoint'
            )
            AND user_id IN (
                SELECT user_id FROM integrations WHERE source = 'jira' AND type = 'token'
            )
            ORDER BY user_id
        """)

        rows = cursor.fetchall()
        conn.close()

        user_ids = [row[0] for row in rows]
        logger.info(f"✅ Jira 연동 사용자 {len(user_ids)}명 발견: {user_ids}")

        return user_ids

    except Exception as e:
        logger.error(f"❌ Jira 사용자 조회 실패: {e}")
        return []


def validate_jira_config(user_id: int, db_path: str = "tickets.db") -> bool:
    """
    사용자의 Jira 설정이 유효한지 검증

    Args:
        user_id: 사용자 ID
        db_path: SQLite DB 경로

    Returns:
        유효 여부
    """
    try:
        config = load_jira_config(user_id, db_path)
        if not config:
            return False

        # 필수 필드 확인
        if not config.get("endpoint") or not config.get("token"):
            return False

        return True

    except Exception as e:
        logger.debug(f"사용자 {user_id} 설정 검증 실패: {e}")
        return False


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 Jira Config 모듈 테스트")
    print("=" * 60)

    # 1. 테이블 생성
    print("\n[1] batch_history 테이블 생성")
    success = create_batch_history_table()
    print(f"   결과: {'✅ 성공' if success else '❌ 실패'}")

    # 2. Jira 설정 로드 (user_id=1)
    print("\n[2] Jira 설정 로드 (user_id=1)")
    config = load_jira_config(user_id=1)
    if config:
        print(f"   ✅ 설정 로드 성공")
        print(f"   - Endpoint: {config['endpoint']}")
        print(f"   - Projects: {config['projects']}")
        print(f"   - Labels: {config['labels']}")
        print(f"   - Token: {'*' * 20} (복호화됨)")
    else:
        print(f"   ❌ 설정 로드 실패")

    # 3. 마지막 동기화 시각 조회
    print("\n[3] 마지막 동기화 시각 조회")
    last_sync = get_last_sync_time(user_id=1)
    print(f"   마지막 동기화: {last_sync}")

    # 4. 배치 이력 저장 (테스트)
    print("\n[4] 배치 이력 저장 (테스트)")
    success = update_batch_history(
        user_id=1,
        batch_type="jira_sync",
        status="success",
        processed_count=42
    )
    print(f"   결과: {'✅ 성공' if success else '❌ 실패'}")

    # 5. 배치 이력 조회
    print("\n[5] 배치 이력 조회")
    history = get_batch_history(user_id=1)
    if history:
        print(f"   ✅ 이력 조회 성공")
        print(f"   - Status: {history['status']}")
        print(f"   - Processed: {history['processed_count']}")
        print(f"   - Last Run: {history['last_run_at']}")
    else:
        print(f"   ❌ 이력 조회 실패")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
