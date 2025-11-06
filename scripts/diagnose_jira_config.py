#!/usr/bin/env python3
"""
Jira 배치 설정 진단 도구

문제를 빠르게 파악할 수 있도록 모든 설정을 체크합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from pathlib import Path

def check_encryption_key():
    """ENCRYPTION_KEY 체크"""
    print("\n[1/5] ENCRYPTION_KEY 체크")

    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env 파일이 없습니다")
        return False

    with open(env_path, 'r') as f:
        content = f.read()

    if "ENCRYPTION_KEY" not in content:
        print("❌ .env에 ENCRYPTION_KEY가 없습니다")
        print("   해결: scripts/reencrypt_jira_tokens.py 실행")
        return False

    # 키 추출
    for line in content.split('\n'):
        if line.startswith('ENCRYPTION_KEY'):
            key = line.split('=', 1)[1].strip()
            if key:
                print(f"✅ ENCRYPTION_KEY 설정됨 ({len(key)}자)")
                return True

    print("❌ ENCRYPTION_KEY가 비어있습니다")
    return False


def check_database(db_path):
    """데이터베이스 체크"""
    print("\n[2/5] 데이터베이스 체크")

    if not os.path.exists(db_path):
        print(f"❌ DB 파일 없음: {db_path}")
        return False

    print(f"✅ DB 파일 존재: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # integrations 테이블 확인
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='integrations'
        """)
        if not cursor.fetchone():
            print("❌ integrations 테이블이 없습니다")
            conn.close()
            return False

        print("✅ integrations 테이블 존재")

        # batch_history 테이블 확인
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='batch_history'
        """)
        if not cursor.fetchone():
            print("⚠️  batch_history 테이블이 없습니다")
            print("   해결: python batch/jira_sync.py --init-db")
        else:
            print("✅ batch_history 테이블 존재")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ DB 접근 실패: {e}")
        return False


def check_jira_users(db_path):
    """Jira 연동 사용자 체크"""
    print("\n[3/5] Jira 연동 사용자 체크")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 모든 Jira 사용자 조회
        cursor.execute("""
            SELECT DISTINCT user_id FROM integrations
            WHERE source = 'jira'
            ORDER BY user_id
        """)
        all_users = [row[0] for row in cursor.fetchall()]

        if not all_users:
            print("❌ Jira 연동 사용자가 없습니다")
            conn.close()
            return False

        print(f"✅ Jira 연동 사용자: {all_users}")

        # 사용자별 필수 필드 체크
        print("\n사용자별 설정 상태:")
        for user_id in all_users:
            cursor.execute("""
                SELECT type FROM integrations
                WHERE user_id = ? AND source = 'jira'
            """, (user_id,))
            types = [row[0] for row in cursor.fetchall()]

            has_endpoint = 'endpoint' in types
            has_token = 'token' in types
            has_project = 'project' in types

            status = "✅" if (has_endpoint and has_token) else "❌"

            details = []
            if has_endpoint:
                cursor.execute("""
                    SELECT value FROM integrations
                    WHERE user_id = ? AND source = 'jira' AND type = 'endpoint'
                """, (user_id,))
                endpoint = cursor.fetchone()[0]
                details.append(f"endpoint={endpoint}")
            else:
                details.append("endpoint=없음")

            details.append(f"token={'있음' if has_token else '없음'}")
            details.append(f"project={'있음' if has_project else '없음'}")

            print(f"  {status} User {user_id}: {', '.join(details)}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ 사용자 조회 실패: {e}")
        return False


def check_token_decryption(db_path):
    """토큰 복호화 테스트"""
    print("\n[4/5] 토큰 복호화 테스트")

    try:
        from auth_utils import TokenEncryption

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, value FROM integrations
            WHERE source = 'jira' AND type = 'token'
            ORDER BY user_id
            LIMIT 1
        """)

        row = cursor.fetchone()
        if not row:
            print("⚠️  테스트할 토큰이 없습니다")
            conn.close()
            return False

        user_id, encrypted_token = row

        # 복호화 시도
        token_encryption = TokenEncryption()
        try:
            decrypted = token_encryption.decrypt_token(encrypted_token)
            if decrypted:
                print(f"✅ User {user_id} 토큰 복호화 성공 ({len(decrypted)}자)")
                return True
            else:
                print(f"❌ User {user_id} 토큰 복호화 실패 (None 반환)")
                return False
        except Exception as e:
            print(f"❌ User {user_id} 토큰 복호화 실패: {e}")
            print("   해결: scripts/reencrypt_jira_tokens.py 실행")
            return False

    except ImportError as e:
        print(f"❌ auth_utils import 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 복호화 테스트 실패: {e}")
        return False


def check_jira_config_load(db_path):
    """Jira 설정 로드 테스트"""
    print("\n[5/5] Jira 설정 로드 테스트")

    try:
        from batch.jira_config import load_jira_config, get_all_jira_users

        # 모든 사용자 조회
        user_ids = get_all_jira_users(db_path)

        if not user_ids:
            print("❌ 유효한 Jira 사용자가 없습니다")
            return False

        print(f"✅ 발견된 사용자: {user_ids}")

        # 첫 번째 사용자 설정 로드
        user_id = user_ids[0]
        config = load_jira_config(user_id, db_path)

        if config:
            print(f"✅ User {user_id} 설정 로드 성공")
            print(f"   - Endpoint: {config['endpoint']}")
            print(f"   - Projects: {config.get('projects', [])}")
            print(f"   - Labels: {config.get('labels', {})}")
            return True
        else:
            print(f"❌ User {user_id} 설정 로드 실패")
            return False

    except Exception as e:
        print(f"❌ 설정 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("🔍 Jira 배치 설정 진단")
    print("=" * 70)

    db_path = sys.argv[1] if len(sys.argv) > 1 else "tickets.db"
    print(f"DB 경로: {db_path}")

    results = []

    # 1. ENCRYPTION_KEY 체크
    results.append(check_encryption_key())

    # 2. 데이터베이스 체크
    results.append(check_database(db_path))

    # 3. Jira 사용자 체크
    results.append(check_jira_users(db_path))

    # 4. 토큰 복호화 체크 (ENCRYPTION_KEY가 있을 때만)
    if results[0]:
        results.append(check_token_decryption(db_path))
    else:
        print("\n[4/5] 토큰 복호화 테스트")
        print("⚠️  ENCRYPTION_KEY가 없어서 스킵")
        results.append(False)

    # 5. 설정 로드 체크
    if results[0] and results[3]:
        results.append(check_jira_config_load(db_path))
    else:
        print("\n[5/5] Jira 설정 로드 테스트")
        print("⚠️  이전 단계 실패로 스킵")
        results.append(False)

    # 결과 요약
    print("\n" + "=" * 70)
    print("📊 진단 결과 요약")
    print("=" * 70)

    checks = [
        "ENCRYPTION_KEY",
        "데이터베이스",
        "Jira 사용자",
        "토큰 복호화",
        "설정 로드"
    ]

    for i, (check, result) in enumerate(zip(checks, results), 1):
        status = "✅" if result else "❌"
        print(f"{status} [{i}/5] {check}")

    success_count = sum(results)
    total_count = len(results)

    print(f"\n성공률: {success_count}/{total_count} ({success_count/total_count*100:.0f}%)")

    if all(results):
        print("\n🎉 모든 체크 통과! Jira 배치를 실행할 수 있습니다.")
        print("   실행: python batch/jira_sync.py --user-id 1")
    else:
        print("\n⚠️  문제가 발견되었습니다. 위의 메시지를 참고하여 수정하세요.")

    print("=" * 70)

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
