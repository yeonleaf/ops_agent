#!/usr/bin/env python3
"""
DB Migration - SQLAlchemy를 사용한 안전한 마이그레이션
"""

import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.report_models import Base, DatabaseManager
from sqlalchemy import inspect, text
import sqlite3


def migrate_add_groups(db_path='reports.db'):
    """그룹 기능 추가 마이그레이션"""

    print("\n" + "="*70)
    print("🚀 DB Migration: 그룹 협업 기능 추가")
    print("="*70)

    try:
        # 1. DatabaseManager로 테이블 생성/업데이트
        print("\n[1] 테이블 생성/업데이트...")
        db = DatabaseManager(db_path=db_path)
        Base.metadata.create_all(db.engine)
        print("✅ 테이블 생성 완료")

        # 2. SQLite에서는 ALTER TABLE로 컬럼 추가가 제한적이므로
        #    기존 테이블에 컬럼이 없으면 수동으로 추가
        print("\n[2] 기존 테이블에 컬럼 추가...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # prompt_templates에 group_id, system 컬럼 추가
        try:
            cursor.execute("SELECT group_id FROM prompt_templates LIMIT 1")
            print("   - prompt_templates.group_id: 이미 존재")
        except sqlite3.OperationalError:
            print("   - prompt_templates.group_id 추가 중...")
            cursor.execute("ALTER TABLE prompt_templates ADD COLUMN group_id INTEGER")
            print("   ✅ group_id 추가 완료")

        try:
            cursor.execute("SELECT system FROM prompt_templates LIMIT 1")
            print("   - prompt_templates.system: 이미 존재")
        except sqlite3.OperationalError:
            print("   - prompt_templates.system 추가 중...")
            cursor.execute("ALTER TABLE prompt_templates ADD COLUMN system VARCHAR(50)")
            print("   ✅ system 추가 완료")

        # reports에 group_id, report_type 컬럼 추가
        try:
            cursor.execute("SELECT group_id FROM reports LIMIT 1")
            print("   - reports.group_id: 이미 존재")
        except sqlite3.OperationalError:
            print("   - reports.group_id 추가 중...")
            cursor.execute("ALTER TABLE reports ADD COLUMN group_id INTEGER")
            print("   ✅ group_id 추가 완료")

        try:
            cursor.execute("SELECT report_type FROM reports LIMIT 1")
            print("   - reports.report_type: 이미 존재")
        except sqlite3.OperationalError:
            print("   - reports.report_type 추가 중...")
            cursor.execute("ALTER TABLE reports ADD COLUMN report_type VARCHAR(20) DEFAULT 'personal' NOT NULL")
            print("   ✅ report_type 추가 완료")

        conn.commit()

        # 3. 기존 데이터 마이그레이션
        print("\n[3] 기존 데이터 마이그레이션...")
        cursor.execute("UPDATE reports SET report_type = 'personal' WHERE report_type IS NULL OR report_type = ''")
        affected_rows = cursor.rowcount
        conn.commit()
        print(f"   ✅ {affected_rows}개 보고서의 report_type을 'personal'로 설정")

        cursor.close()
        conn.close()

        # 4. 검증
        print("\n[4] 마이그레이션 검증...")
        inspector = inspect(db.engine)

        # 테이블 확인
        tables = inspector.get_table_names()
        expected_tables = ['user_groups', 'group_members', 'prompt_templates', 'reports', 'report_users']

        print("\n   [테이블 확인]")
        all_tables_exist = True
        for table in expected_tables:
            if table in tables:
                columns = inspector.get_columns(table)
                print(f"   ✅ {table}: {len(columns)}개 컬럼")
            else:
                print(f"   ❌ {table}: 없음")
                all_tables_exist = False

        # 필드 확인
        print("\n   [그룹 관련 필드 확인]")
        pt_columns = {col['name'] for col in inspector.get_columns('prompt_templates')}
        r_columns = {col['name'] for col in inspector.get_columns('reports')}

        all_fields_exist = True
        for field in ['group_id', 'system']:
            if field in pt_columns:
                print(f"   ✅ prompt_templates.{field}: 있음")
            else:
                print(f"   ❌ prompt_templates.{field}: 없음")
                all_fields_exist = False

        for field in ['group_id', 'report_type']:
            if field in r_columns:
                print(f"   ✅ reports.{field}: 있음")
            else:
                print(f"   ❌ reports.{field}: 없음")
                all_fields_exist = False

        print("\n" + "="*70)

        if all_tables_exist and all_fields_exist:
            print("✅ 마이그레이션 성공!")
            print("="*70 + "\n")
            return True
        else:
            print("⚠️  마이그레이션 완료했으나 일부 테이블/필드 누락")
            print("="*70 + "\n")
            return False

    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # DB 경로
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'reports.db'

    print(f"\n데이터베이스: {db_path}")

    if not os.path.exists(db_path):
        print(f"\n⚠️  DB 파일이 없습니다. 새로 생성합니다: {db_path}")

    # 마이그레이션 실행
    success = migrate_add_groups(db_path=db_path)

    if success:
        print("✅ 모든 작업이 완료되었습니다!\n")
        sys.exit(0)
    else:
        print("❌ 마이그레이션 실패\n")
        sys.exit(1)
