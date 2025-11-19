#!/usr/bin/env python3
"""
테스트 데이터 생성 스크립트

템플릿 에디터를 테스트하기 위한 사용자와 프롬프트를 생성합니다.
"""

import os
from models.report_models import DatabaseManager, User, PromptTemplate
from services.auth_service import AuthService

def setup_test_data():
    """테스트 데이터 생성"""

    # DB 경로 설정 (환경변수 또는 기본값)
    db_path = os.getenv('REPORTS_DB_PATH', 'reports.db')

    print(f"📦 데이터베이스: {db_path}")

    # DB 초기화
    db_manager = DatabaseManager(db_path)
    db_manager.create_tables()
    print("✅ 데이터베이스 테이블 생성 완료")

    session = db_manager.get_session()

    try:
        # 1. 테스트 사용자 생성
        auth_service = AuthService(session)

        # 기존 사용자 확인
        existing_user = session.query(User).filter_by(username='testuser').first()

        if existing_user:
            print(f"ℹ️  사용자 'testuser'가 이미 존재합니다 (ID: {existing_user.id})")
            user = existing_user
        else:
            # 새 사용자 생성
            result = auth_service.register(
                username='testuser',
                email='test@example.com',
                password='test123'
            )
            print(f"✅ 테스트 사용자 생성 완료")
            print(f"   사용자명: testuser")
            print(f"   비밀번호: test123")
            print(f"   이메일: test@example.com")

            # 사용자 객체 조회
            user = session.query(User).filter_by(username='testuser').first()

        # 2. 테스트 프롬프트 생성
        prompts_data = [
            {
                'title': '주간 업무 요약',
                'category': '주간보고',
                'description': 'Jira 이슈 기반 주간 업무 요약',
                'prompt_content': '이번 주에 처리한 Jira 이슈를 요약해주세요.',
                'is_public': False,
                'order_index': 1
            },
            {
                'title': 'BMT 현황',
                'category': 'BMT',
                'description': 'BMT 진행 현황 및 결과',
                'prompt_content': 'BMT 진행 현황과 주요 결과를 테이블로 작성해주세요.',
                'is_public': False,
                'order_index': 2
            },
            {
                'title': 'PM 업무 현황',
                'category': 'PM',
                'description': '프로젝트 관리 업무 현황',
                'prompt_content': '프로젝트 관리 업무 현황을 정리해주세요.',
                'is_public': True,  # 공개 프롬프트
                'order_index': 3
            },
            {
                'title': '기술 지원 이슈',
                'category': '기술지원',
                'description': '고객 기술 지원 이슈 목록',
                'prompt_content': '이번 주 기술 지원 이슈를 정리해주세요.',
                'is_public': False,
                'order_index': 4
            },
            {
                'title': '다음 주 계획',
                'category': '계획',
                'description': '다음 주 업무 계획',
                'prompt_content': '다음 주 업무 계획을 작성해주세요.',
                'is_public': False,
                'order_index': 5
            }
        ]

        created_prompts = []
        for prompt_data in prompts_data:
            # 기존 프롬프트 확인 (제목 중복 방지)
            existing_prompt = session.query(PromptTemplate)\
                .filter_by(user_id=user.id, title=prompt_data['title'])\
                .first()

            if existing_prompt:
                print(f"   ⏭️  프롬프트 '{prompt_data['title']}' 이미 존재 (ID: {existing_prompt.id})")
                created_prompts.append(existing_prompt)
            else:
                prompt = PromptTemplate(
                    user_id=user.id,
                    **prompt_data
                )
                session.add(prompt)
                session.commit()
                session.refresh(prompt)
                created_prompts.append(prompt)
                print(f"   ✅ 프롬프트 생성: {prompt.title} (ID: {prompt.id})")

        print(f"\n📊 생성된 프롬프트: {len(created_prompts)}개")

        # 3. 테스트 템플릿 예제 생성 (선택사항)
        from models.report_models import ReportTemplate

        template_content = f"""# 월간 업무 보고서

## 주간 업무 요약
{{{{prompt:{created_prompts[0].id}}}}}

## BMT 현황
{{{{prompt:{created_prompts[1].id}}}}}

## PM 업무 현황
{{{{prompt:{created_prompts[2].id}}}}}

## 기술 지원 이슈
{{{{prompt:{created_prompts[3].id}}}}}

## 다음 주 계획
{{{{prompt:{created_prompts[4].id}}}}}

---
*자동 생성된 보고서*
"""

        existing_template = session.query(ReportTemplate)\
            .filter_by(user_id=user.id, title='기본 월간 보고서 템플릿')\
            .first()

        if not existing_template:
            template = ReportTemplate(
                user_id=user.id,
                title='기본 월간 보고서 템플릿',
                description='기본 월간 업무 보고서 템플릿',
                template_content=template_content
            )
            session.add(template)
            session.commit()
            print(f"✅ 기본 템플릿 생성 완료 (ID: {template.id})")
        else:
            print(f"ℹ️  기본 템플릿이 이미 존재합니다 (ID: {existing_template.id})")

        print("\n" + "="*60)
        print("✅ 테스트 데이터 생성 완료!")
        print("="*60)
        print("\n🌐 에디터 접속: http://localhost:8002/editor")
        print("\n🔐 로그인 정보:")
        print("   사용자명: testuser")
        print("   비밀번호: test123")
        print("\n📝 생성된 프롬프트:")
        for p in created_prompts:
            print(f"   - [{p.id}] {p.title} ({p.category})")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    setup_test_data()
