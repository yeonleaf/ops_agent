#!/usr/bin/env python3
"""
Database Migration: Add jql column to prompt_templates table
"""

import sqlite3
import sys

def migrate_add_jql_column(db_path='reports.db'):
    """
    prompt_templates 테이블에 jql 컬럼 추가
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 컬럼 존재 여부 확인
        cursor.execute("PRAGMA table_info(prompt_templates)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'jql' in columns:
            print("✅ jql 컬럼이 이미 존재합니다.")
            return True

        # jql 컬럼 추가
        print("🔄 jql 컬럼 추가 중...")
        cursor.execute("""
            ALTER TABLE prompt_templates
            ADD COLUMN jql TEXT
        """)

        conn.commit()
        print("✅ jql 컬럼이 추가되었습니다.")

        # 확인
        cursor.execute("PRAGMA table_info(prompt_templates)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 현재 컬럼 목록: {', '.join(columns)}")

        return True

    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'reports.db'

    print(f"=== Database Migration: Add jql Column ===")
    print(f"Target DB: {db_path}\n")

    success = migrate_add_jql_column(db_path)

    if success:
        print("\n✅ 마이그레이션 완료!")
        sys.exit(0)
    else:
        print("\n❌ 마이그레이션 실패!")
        sys.exit(1)
