#!/usr/bin/env python3
"""
Template Service - 보고서 템플릿 관리 서비스

사용자별 템플릿 CRUD 및 템플릿 파싱
"""

from typing import List, Dict, Optional
from models.report_models import ReportTemplate, PromptTemplate
from sqlalchemy import and_


class TemplateService:
    """템플릿 관리 서비스"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def get_user_templates(self, user_id: int) -> List[Dict]:
        """
        사용자의 템플릿 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            템플릿 리스트 (내용 제외)
        """
        templates = self.db.query(ReportTemplate)\
            .filter_by(user_id=user_id)\
            .order_by(ReportTemplate.updated_at.desc())\
            .all()

        return [t.to_dict(include_content=False) for t in templates]

    def get_template_by_id(self, template_id: int, user_id: int) -> Optional[Dict]:
        """
        템플릿 조회 (ID)

        Args:
            template_id: 템플릿 ID
            user_id: 사용자 ID (권한 체크용)

        Returns:
            템플릿 딕셔너리 (내용 포함) 또는 None

        Raises:
            PermissionError: 접근 권한 없음
        """
        template = self.db.query(ReportTemplate).filter_by(id=template_id).first()

        if not template:
            return None

        # 권한 체크 (본인 것만)
        if template.user_id != user_id:
            raise PermissionError("이 템플릿에 접근할 권한이 없습니다")

        return template.to_dict(include_content=True)

    def create_template(self, user_id: int, data: Dict) -> int:
        """
        템플릿 생성

        Args:
            user_id: 사용자 ID
            data: {
                "title": str,
                "description": str (optional),
                "template_content": str
            }

        Returns:
            생성된 템플릿 ID
        """
        template = ReportTemplate(
            user_id=user_id,
            title=data['title'],
            description=data.get('description'),
            template_content=data['template_content']
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        return template.id

    def update_template(self, user_id: int, template_id: int, data: Dict) -> None:
        """
        템플릿 수정 (본인 것만)

        Args:
            user_id: 사용자 ID
            template_id: 템플릿 ID
            data: 수정할 필드들

        Raises:
            PermissionError: 권한 없음
            ValueError: 템플릿 없음
        """
        template = self.db.query(ReportTemplate)\
            .filter_by(id=template_id, user_id=user_id)\
            .first()

        if not template:
            raise ValueError("템플릿을 찾을 수 없거나 권한이 없습니다")

        # 수정 가능한 필드
        allowed_fields = ['title', 'description', 'template_content']

        for key, value in data.items():
            if key in allowed_fields:
                setattr(template, key, value)

        self.db.commit()

    def delete_template(self, user_id: int, template_id: int) -> None:
        """
        템플릿 삭제 (본인 것만)

        Args:
            user_id: 사용자 ID
            template_id: 템플릿 ID

        Raises:
            ValueError: 템플릿 없음 또는 권한 없음
        """
        template = self.db.query(ReportTemplate)\
            .filter_by(id=template_id, user_id=user_id)\
            .first()

        if not template:
            raise ValueError("템플릿을 찾을 수 없거나 권한이 없습니다")

        self.db.delete(template)
        self.db.commit()

    def validate_template(self, template_content: str, user_id: int) -> Dict:
        """
        템플릿 유효성 검사 (placeholder 체크)

        Args:
            template_content: 템플릿 내용
            user_id: 사용자 ID

        Returns:
            {
                "valid": bool,
                "errors": [str],
                "warnings": [str],
                "prompt_ids": [int]
            }
        """
        import re

        errors = []
        warnings = []

        # Placeholder 패턴: {{prompt:123}}
        placeholder_pattern = r'\{\{prompt:(\d+)\}\}'
        prompt_ids = [int(m) for m in re.findall(placeholder_pattern, template_content)]

        if not prompt_ids:
            warnings.append("템플릿에 프롬프트 placeholder가 없습니다")

        # 각 프롬프트의 존재 및 권한 확인
        for prompt_id in prompt_ids:
            prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()

            if not prompt:
                errors.append(f"프롬프트 ID {prompt_id}를 찾을 수 없습니다")
            elif prompt.user_id != user_id and not prompt.is_public:
                errors.append(f"프롬프트 ID {prompt_id}에 접근 권한이 없습니다")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "prompt_ids": prompt_ids
        }


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager, User

    print("=== Template Service 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_templates.db')
    db.create_tables()
    session = db.get_session()

    try:
        # 사용자 생성
        user = User(username='testuser', email='test@example.com', password_hash='hash')
        session.add(user)
        session.commit()

        # 서비스 생성
        template_service = TemplateService(session)

        # 1. 템플릿 생성
        print("1. 템플릿 생성 테스트")
        template_id = template_service.create_template(user.id, {
            'title': '월간 보고서 템플릿',
            'description': '기본 월간 보고서',
            'template_content': '# 보고서\n\n{{prompt:1}}\n\n{{prompt:2}}'
        })
        print(f"   ✅ 템플릿 생성: ID={template_id}")

        # 2. 템플릿 조회
        print("\n2. 템플릿 조회 테스트")
        templates = template_service.get_user_templates(user.id)
        print(f"   템플릿 개수: {len(templates)}")

        # 3. 템플릿 유효성 검사
        print("\n3. 템플릿 유효성 검사")
        validation = template_service.validate_template(
            '# Report\n{{prompt:999}}',
            user.id
        )
        print(f"   Valid: {validation['valid']}")
        print(f"   Errors: {validation['errors']}")
        print(f"   Warnings: {validation['warnings']}")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
