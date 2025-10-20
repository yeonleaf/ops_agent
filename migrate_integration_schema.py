#!/usr/bin/env python3
"""
Integration 테이블 스키마 마이그레이션 스크립트
기존 (email, source_type, token) 구조를
새로운 (user_id, source, type, value) 구조로 변경
"""

from database_models import DatabaseManager

def main():
    print("=" * 60)
    print("Integration 테이블 스키마 마이그레이션 시작")
    print("=" * 60)

    # 데이터베이스 관리자 초기화
    db_manager = DatabaseManager()

    # 마이그레이션 실행
    try:
        # 1. Integration 테이블 스키마 마이그레이션
        print("\n[1단계] Integration 테이블 스키마 마이그레이션...")
        db_manager.migrate_integrations_to_new_schema()

        # 2. User 테이블의 레거시 데이터도 마이그레이션 (있는 경우)
        print("\n[2단계] User 테이블에서 Integration 테이블로 레거시 데이터 마이그레이션...")
        db_manager.migrate_user_data_to_integrations()

        print("\n" + "=" * 60)
        print("✅ 모든 마이그레이션이 성공적으로 완료되었습니다!")
        print("=" * 60)

        # 마이그레이션 결과 확인
        print("\n[마이그레이션 결과 확인]")
        import sqlite3
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()

            # 새 테이블 스키마 확인
            cursor.execute("PRAGMA table_info(integrations)")
            columns = cursor.fetchall()
            print("\n새 Integration 테이블 스키마:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")

            # 데이터 개수 확인
            cursor.execute("SELECT COUNT(*) FROM integrations")
            count = cursor.fetchone()[0]
            print(f"\n마이그레이션된 레코드 수: {count}개")

            # 샘플 데이터 확인
            if count > 0:
                cursor.execute("""
                    SELECT user_id, source, type, value, created_at
                    FROM integrations
                    LIMIT 5
                """)
                samples = cursor.fetchall()
                print("\n샘플 데이터 (최대 5개):")
                for sample in samples:
                    value_preview = sample[3][:20] + "..." if len(sample[3]) > 20 else sample[3]
                    print(f"  - User ID: {sample[0]}, Source: {sample[1]}, Type: {sample[2]}, Value: {value_preview}")

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 마이그레이션 중 오류 발생: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
