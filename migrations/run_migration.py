#!/usr/bin/env python3
"""
DB Migration Runner
마이그레이션 SQL 스크립트를 실행하는 유틸리티
"""

import sqlite3
import os
import sys


def run_migration(db_path='reports.db', migration_file='001_add_groups.sql'):
    """
    마이그레이션 실행

    Args:
        db_path: 데이터베이스 파일 경로
        migration_file: 마이그레이션 SQL 파일명
    """
    # 마이그레이션 파일 경로
    migrations_dir = os.path.dirname(__file__)
    migration_path = os.path.join(migrations_dir, migration_file)

    if not os.path.exists(migration_path):
        print(f"❌ 마이그레이션 파일을 찾을 수 없습니다: {migration_path}")
        return False

    try:
        # SQL 읽기
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 트랜잭션 시작
        conn.execute('BEGIN TRANSACTION')

        try:
            # SQL 실행 (세미콜론으로 구분된 각 statement 실행)
            statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]

            for i, statement in enumerate(statements, 1):
                # 주석 제거
                lines = [line for line in statement.split('\n') if not line.strip().startswith('--')]
                clean_statement = '\n'.join(lines).strip()

                if clean_statement:
                    print(f"\n[{i}/{len(statements)}] 실행 중...")
                    print(f"  {clean_statement[:100]}...")
                    cursor.execute(clean_statement)

            # 커밋
            conn.commit()
            print(f"\n✅ 마이그레이션 완료: {migration_file}")
            return True

        except Exception as e:
            # 롤백
            conn.rollback()
            print(f"\n❌ 마이그레이션 실패 (롤백됨): {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"❌ 마이그레이션 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration(db_path='reports.db'):
    """
    마이그레이션 결과 검증

    Args:
        db_path: 데이터베이스 파일 경로
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 테이블 목록 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        print("\n" + "="*60)
        print("📊 마이그레이션 검증")
        print("="*60)

        # 예상 테이블
        expected_tables = ['user_groups', 'group_members', 'prompt_templates', 'reports', 'report_users']

        print("\n[테이블 확인]")
        for table in expected_tables:
            if table in tables:
                # 테이블 스키마 조회
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()

                print(f"\n✅ {table}: {len(columns)}개 컬럼")
                for col in columns:
                    print(f"   - {col[1]} ({col[2]})")
            else:
                print(f"\n❌ {table}: 없음")

        # 그룹 관련 필드 확인
        print("\n[prompt_templates 그룹 필드 확인]")
        cursor.execute("PRAGMA table_info(prompt_templates)")
        pt_columns = [col[1] for col in cursor.fetchall()]

        for field in ['group_id', 'system']:
            if field in pt_columns:
                print(f"   ✅ {field}: 있음")
            else:
                print(f"   ❌ {field}: 없음")

        print("\n[reports 그룹 필드 확인]")
        cursor.execute("PRAGMA table_info(reports)")
        r_columns = [col[1] for col in cursor.fetchall()]

        for field in ['group_id', 'report_type']:
            if field in r_columns:
                print(f"   ✅ {field}: 있음")
            else:
                print(f"   ❌ {field}: 없음")

        print("\n" + "="*60)
        print("✅ 검증 완료")
        print("="*60 + "\n")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 검증 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "🚀 "+"="*58)
    print("🚀 DB Migration Runner")
    print("🚀 "+"="*58 + "\n")

    # DB 경로
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'reports.db'

    print(f"데이터베이스: {db_path}")

    # 마이그레이션 실행
    success = run_migration(db_path=db_path, migration_file='001_add_groups.sql')

    if success:
        # 검증
        verify_migration(db_path=db_path)
    else:
        print("\n❌ 마이그레이션 실패")
        sys.exit(1)

    print("✅ 완료\n")
