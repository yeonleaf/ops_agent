#!/usr/bin/env python3
"""
Database Migration: Add variables table
"""

import sqlite3
import sys

def migrate_add_variables_table(db_path='reports.db'):
    """
    variables 테이블 생성
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='variables'")
        if cursor.fetchone():
            print("✅ variables 테이블이 이미 존재합니다.")
            return True

        # variables 테이블 생성
        print("🔄 variables 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                value TEXT NOT NULL,
                description TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_variables_name ON variables(name)")

        conn.commit()
        print("✅ variables 테이블이 생성되었습니다.")

        # 확인
        cursor.execute("PRAGMA table_info(variables)")
        columns = cursor.fetchall()
        print(f"📋 생성된 컬럼: {', '.join([col[1] for col in columns])}")

        return True

    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'reports.db'

    print(f"=== Database Migration: Add variables Table ===")
    print(f"Target DB: {db_path}\n")

    success = migrate_add_variables_table(db_path)

    if success:
        print("\n✅ 마이그레이션 완료!")
        sys.exit(0)
    else:
        print("\n❌ 마이그레이션 실패!")
        sys.exit(1)
