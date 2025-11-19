#!/usr/bin/env python3
"""
데이터베이스 마이그레이션: PromptExecution, ReportTemplate 테이블 추가

실행 방법:
    python migrations/add_execution_and_template_tables.py
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, inspect, text
from models.report_models import Base, PromptExecution, ReportTemplate


def check_table_exists(engine, table_name):
    """테이블 존재 여부 확인"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate_database(db_path='reports.db'):
    """데이터베이스 마이그레이션 실행"""
    print(f"\n{'='*80}")
    print(f"📦 데이터베이스 마이그레이션 시작")
    print(f"{'='*80}\n")
    print(f"DB 파일: {db_path}\n")

    # 엔진 생성
    engine = create_engine(f'sqlite:///{db_path}', echo=False)

    # 기존 테이블 확인
    print("🔍 기존 테이블 확인:")
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    for table in existing_tables:
        print(f"  ✓ {table}")

    # 새로 추가할 테이블 확인
    new_tables = []

    if not check_table_exists(engine, 'prompt_executions'):
        new_tables.append('prompt_executions')

    if not check_table_exists(engine, 'report_templates'):
        new_tables.append('report_templates')

    if not new_tables:
        print("\n✅ 모든 테이블이 이미 존재합니다. 마이그레이션 불필요.")
        return

    print(f"\n📝 추가할 테이블: {', '.join(new_tables)}\n")

    # 사용자 확인
    response = input("⚠️  마이그레이션을 진행하시겠습니까? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ 마이그레이션 취소")
        return

    # 테이블 생성
    try:
        print("\n🔧 테이블 생성 중...")

        # 개별 테이블 생성
        if 'prompt_executions' in new_tables:
            PromptExecution.__table__.create(engine)
            print("  ✅ prompt_executions 테이블 생성 완료")

        if 'report_templates' in new_tables:
            ReportTemplate.__table__.create(engine)
            print("  ✅ report_templates 테이블 생성 완료")

        # 결과 확인
        print("\n🔍 마이그레이션 후 테이블 목록:")
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        for table in sorted(all_tables):
            print(f"  ✓ {table}")

        print(f"\n{'='*80}")
        print(f"✨ 마이그레이션 완료!")
        print(f"{'='*80}\n")

        # 새 테이블 스키마 출력
        print("📋 새로운 테이블 스키마:\n")

        if 'prompt_executions' in new_tables:
            print("prompt_executions:")
            columns = inspector.get_columns('prompt_executions')
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
            print()

        if 'report_templates' in new_tables:
            print("report_templates:")
            columns = inspector.get_columns('report_templates')
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
            print()

    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def rollback_migration(db_path='reports.db'):
    """마이그레이션 롤백 (테이블 삭제)"""
    print(f"\n{'='*80}")
    print(f"⚠️  마이그레이션 롤백")
    print(f"{'='*80}\n")

    response = input("⚠️  정말로 prompt_executions, report_templates 테이블을 삭제하시겠습니까? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ 롤백 취소")
        return

    engine = create_engine(f'sqlite:///{db_path}', echo=False)

    try:
        with engine.connect() as conn:
            if check_table_exists(engine, 'prompt_executions'):
                conn.execute(text("DROP TABLE prompt_executions"))
                print("  ✅ prompt_executions 테이블 삭제 완료")

            if check_table_exists(engine, 'report_templates'):
                conn.execute(text("DROP TABLE report_templates"))
                print("  ✅ report_templates 테이블 삭제 완료")

            conn.commit()

        print("\n✅ 롤백 완료")

    except Exception as e:
        print(f"\n❌ 롤백 실패: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='데이터베이스 마이그레이션')
    parser.add_argument('--db', default='reports.db', help='데이터베이스 파일 경로')
    parser.add_argument('--rollback', action='store_true', help='마이그레이션 롤백')

    args = parser.parse_args()

    if args.rollback:
        rollback_migration(args.db)
    else:
        migrate_database(args.db)
