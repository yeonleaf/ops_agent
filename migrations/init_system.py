#!/usr/bin/env python3
"""
System Initialization & Migration Script

데이터베이스 초기화 및 샘플 데이터 생성
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.report_models import DatabaseManager, User, PromptTemplate
from services.auth_service import AuthService


def init_database(db_path='reports.db'):
    """데이터베이스 초기화"""
    print("=" * 80)
    print("🗄️  데이터베이스 초기화")
    print("=" * 80)

    db = DatabaseManager(db_path)
    db.create_tables()

    print("✅ 테이블 생성 완료")
    print(f"   - report_users")
    print(f"   - prompt_templates")
    print(f"   - reports")
    print()

    return db


def create_sample_user(db):
    """샘플 사용자 생성"""
    print("=" * 80)
    print("👤 샘플 사용자 생성")
    print("=" * 80)

    session = db.get_session()

    try:
        auth_service = AuthService(session)

        # 사용자 생성
        result = auth_service.register(
            username='demo',
            email='demo@example.com',
            password='demo123'
        )

        print(f"✅ 사용자 생성: {result['username']}")
        print(f"   - User ID: {result['user_id']}")
        print(f"   - Email: {result['email']}")
        print(f"   - Token: {result['token'][:50]}...")
        print()

        return result['user_id']

    except ValueError as e:
        print(f"⚠️  사용자가 이미 존재하거나 오류 발생: {e}")

        # 기존 사용자 조회
        user = auth_service.get_user_by_username('demo')
        if user:
            print(f"✅ 기존 사용자 사용: {user.username} (ID: {user.id})")
            return user.id

        return None

    finally:
        session.close()


def create_sample_prompts(db, user_id):
    """샘플 프롬프트 생성"""
    print("=" * 80)
    print("📝 샘플 프롬프트 생성")
    print("=" * 80)

    session = db.get_session()

    sample_prompts = [
        {
            'title': '전체 운영 업무 현황',
            'category': '개요',
            'description': '프로젝트별 진행 중인 이슈 현황',
            'prompt_content': '''전체 운영 업무 현황을 HTML 테이블로 생성해주세요.

다음 항목들을 포함해주세요:
1. 프로젝트별 진행 중인 이슈 현황 (NCMS, EDMP, ACS, EUXP)
2. 상태별 통계 (진행중, 완료, 대기 등)
3. 우선순위별 분포

JQL: project IN (NCMS, EDMP, ACS, EUXP) AND created >= '2025-10-01' AND created <= '2025-10-31'

테이블 형식:
- 프로젝트명
- 전체 이슈 수
- 진행중
- 완료
- 대기''',
            'is_public': True,
            'order_index': 1
        },
        {
            'title': 'NCMS BMT 현황',
            'category': 'BMT',
            'description': 'NCMS BMT 이슈 목록 및 현황',
            'prompt_content': '''NCMS BMT 현황을 HTML 테이블로 생성해주세요.

JQL: labels = 'NCMS_BMT' AND created >= '2025-10-01' AND created <= '2025-10-31'

테이블 형식:
- 이슈 키
- 요약
- 상태
- 담당자
- 생성일
- 해결일''',
            'is_public': False,
            'order_index': 10
        },
        {
            'title': 'NCMS PM 현황',
            'category': 'PM',
            'description': 'NCMS PM 이슈 목록 및 현황',
            'prompt_content': '''NCMS PM 현황을 HTML 테이블로 생성해주세요.

JQL: labels = 'NCMS_PM' AND created >= '2025-10-01' AND created <= '2025-10-31'

테이블 형식:
- 이슈 키
- 요약
- 상태
- 담당자
- 우선순위
- 생성일''',
            'is_public': False,
            'order_index': 20
        },
        {
            'title': 'NCMS DB작업 현황',
            'category': 'DB작업',
            'description': 'NCMS 상용 DB작업 현황',
            'prompt_content': '''NCMS 상용 DB작업 현황을 HTML 테이블로 생성해주세요.

JQL: labels = 'NCMS_DB' AND created >= '2025-10-01' AND created <= '2025-10-31'

테이블 형식:
- 이슈 키
- 요약
- 상태
- 담당자
- 작업 유형
- 생성일''',
            'is_public': False,
            'order_index': 30
        }
    ]

    try:
        for prompt_data in sample_prompts:
            prompt = PromptTemplate(
                user_id=user_id,
                **prompt_data
            )
            session.add(prompt)

        session.commit()

        print(f"✅ {len(sample_prompts)}개 샘플 프롬프트 생성 완료:")
        for prompt_data in sample_prompts:
            print(f"   - {prompt_data['title']} ({prompt_data['category']})")

        print()

    except Exception as e:
        session.rollback()
        print(f"❌ 프롬프트 생성 실패: {e}")

    finally:
        session.close()


def main():
    """메인 실행"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "멀티유저 보고서 시스템 초기화" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # 1. 데이터베이스 초기화
    db = init_database('reports.db')

    # 2. 샘플 사용자 생성
    user_id = create_sample_user(db)

    if user_id:
        # 3. 샘플 프롬프트 생성
        create_sample_prompts(db, user_id)

    print("=" * 80)
    print("✨ 초기화 완료!")
    print("=" * 80)
    print()
    print("🚀 다음 단계:")
    print("   1. 서버 실행: python dynamic_report_server.py")
    print("   2. 브라우저 접속: http://localhost:8004")
    print("   3. 로그인: username=demo, password=demo123")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
