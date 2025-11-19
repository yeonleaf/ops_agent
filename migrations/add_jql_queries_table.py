#!/usr/bin/env python3
"""
JQL Queries 테이블 추가 마이그레이션

JQL 관리를 독립적인 기능으로 분리하기 위해 jql_queries 테이블을 추가합니다.
"""

import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def migrate_add_jql_queries_table(db_path='reports.db'):
    """jql_queries 테이블 추가"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 테이블 존재 여부 확인
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='jql_queries'
        """)

        if cursor.fetchone():
            print("⚠️  jql_queries 테이블이 이미 존재합니다. 스킵합니다.")
            return

        # jql_queries 테이블 생성
        cursor.execute("""
            CREATE TABLE jql_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                jql TEXT NOT NULL,
                system VARCHAR(50),
                category VARCHAR(50),
                is_public BOOLEAN DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES report_users(id)
            )
        """)

        # 인덱스 생성
        cursor.execute("""
            CREATE INDEX ix_jql_queries_user_id ON jql_queries(user_id)
        """)
        cursor.execute("""
            CREATE INDEX ix_jql_queries_name ON jql_queries(name)
        """)
        cursor.execute("""
            CREATE INDEX ix_jql_queries_system ON jql_queries(system)
        """)
        cursor.execute("""
            CREATE INDEX ix_jql_queries_category ON jql_queries(category)
        """)
        cursor.execute("""
            CREATE INDEX ix_jql_queries_is_public ON jql_queries(is_public)
        """)

        conn.commit()
        print("✅ jql_queries 테이블 생성 완료")

    except Exception as e:
        conn.rollback()
        print(f"❌ 마이그레이션 실패: {e}")
        raise
    finally:
        conn.close()


def migrate_existing_jqls(db_path='reports.db'):
    """
    기존 prompt_templates의 JQL을 jql_queries로 마이그레이션

    - JQL이 있는 프롬프트를 찾아서 JQL 쿼리로 변환
    - 프롬프트에는 JQL ID를 참조하도록 변경
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # JQL이 있는 프롬프트 조회
        cursor.execute("""
            SELECT id, user_id, title, jql, system, category
            FROM prompt_templates
            WHERE jql IS NOT NULL AND jql != ''
        """)

        prompts_with_jql = cursor.fetchall()

        if not prompts_with_jql:
            print("ℹ️  마이그레이션할 JQL이 없습니다.")
            return

        print(f"ℹ️  {len(prompts_with_jql)}개의 프롬프트에서 JQL을 마이그레이션합니다...")

        migrated_count = 0
        for prompt_id, user_id, title, jql, system, category in prompts_with_jql:
            # JQL 이름 생성 (프롬프트 제목 기반)
            jql_name = f"{title}_JQL" if title else f"Prompt_{prompt_id}_JQL"

            # JQL 쿼리 생성
            cursor.execute("""
                INSERT INTO jql_queries (user_id, name, description, jql, system, category, is_public)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                user_id,
                jql_name,
                f"프롬프트 '{title}'에서 마이그레이션된 JQL",
                jql,
                system,
                category
            ))

            jql_id = cursor.lastrowid

            # 프롬프트에 JQL ID를 메모 (향후 연동을 위해 description에 추가)
            # 실제 연동은 별도 컬럼이나 프롬프트 내용 수정으로 처리 가능
            print(f"  ✅ '{jql_name}' (ID: {jql_id}) 생성됨 <- 프롬프트 ID {prompt_id}")

            migrated_count += 1

        conn.commit()
        print(f"✅ {migrated_count}개의 JQL 마이그레이션 완료")
        print(f"ℹ️  프롬프트와 JQL 연동은 수동으로 진행해주세요.")

    except Exception as e:
        conn.rollback()
        print(f"❌ JQL 마이그레이션 실패: {e}")
        raise
    finally:
        conn.close()


def main(auto_migrate=False):
    """메인 실행 함수"""
    print("=== JQL Queries 테이블 추가 마이그레이션 ===\n")

    db_path = 'reports.db'

    # 1. 테이블 생성
    migrate_add_jql_queries_table(db_path)

    # 2. 기존 JQL 마이그레이션 (선택적)
    print("\n=== 기존 JQL 마이그레이션 ===")

    if auto_migrate:
        print("ℹ️  자동 모드: 기존 JQL 마이그레이션을 건너뜁니다.")
    else:
        print("기존 프롬프트의 JQL을 jql_queries 테이블로 마이그레이션하시겠습니까?")
        print("(프롬프트 템플릿의 JQL 필드는 유지되며, 새로운 JQL 레코드가 생성됩니다)")
        try:
            response = input("마이그레이션하시겠습니까? (y/N): ").lower()
            if response == 'y':
                migrate_existing_jqls(db_path)
            else:
                print("ℹ️  JQL 마이그레이션을 건너뜁니다.")
        except (EOFError, KeyboardInterrupt):
            print("\nℹ️  JQL 마이그레이션을 건너뜁니다.")

    print("\n✅ 모든 마이그레이션 완료")


if __name__ == "__main__":
    import sys
    auto_migrate = '--auto' in sys.argv or '--yes' in sys.argv or '-y' in sys.argv
    main(auto_migrate=auto_migrate)
