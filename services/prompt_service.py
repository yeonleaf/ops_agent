#!/usr/bin/env python3
"""
Prompt Service - 프롬프트 관리 서비스

사용자별 프롬프트 템플릿 CRUD
"""

from typing import List, Dict, Optional
from models.report_models import PromptTemplate, User
from sqlalchemy import or_, and_


class PromptService:
    """프롬프트 관리 서비스"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def get_user_prompts(self, user_id: int, include_public: bool = False, category: str = None) -> Dict:
        """
        사용자의 프롬프트 조회 (+ 옵션: 공개 프롬프트, 카테고리 필터)

        Args:
            user_id: 사용자 ID
            include_public: 공개 프롬프트 포함 여부
            category: 필터링할 카테고리 (None이면 전체)

        Returns:
            {
                "my_prompts": [...],
                "public_prompts": [...],  # include_public=True인 경우
                "categories": [...]
            }
        """
        # 내 프롬프트 쿼리
        my_query = self.db.query(PromptTemplate).filter_by(user_id=user_id)

        # 카테고리 필터 적용
        if category:
            my_query = my_query.filter(PromptTemplate.category == category)

        my_prompts = my_query.order_by(PromptTemplate.order_index, PromptTemplate.title).all()

        result = {
            "my_prompts": [p.to_dict(include_content=True) for p in my_prompts]
        }

        # 공개 프롬프트
        if include_public:
            public_query = self.db.query(PromptTemplate)\
                .filter(
                    and_(
                        PromptTemplate.is_public == True,
                        PromptTemplate.user_id != user_id
                    )
                )

            # 카테고리 필터 적용
            if category:
                public_query = public_query.filter(PromptTemplate.category == category)

            public_prompts = public_query.order_by(PromptTemplate.order_index, PromptTemplate.title).all()

            result["public_prompts"] = [
                p.to_dict(include_content=True, include_owner=True)
                for p in public_prompts
            ]
        else:
            result["public_prompts"] = []

        # 카테고리 추출 (필터 적용 전 전체 카테고리 목록 제공)
        # 사용자가 볼 수 있는 모든 프롬프트의 카테고리를 반환
        all_prompts_query = self.db.query(PromptTemplate).filter(
            or_(
                PromptTemplate.user_id == user_id,
                PromptTemplate.is_public == True if include_public else False
            )
        )
        all_prompts = all_prompts_query.all()

        if all_prompts:
            categories = sorted(set(p.category for p in all_prompts))
        else:
            categories = []

        result["categories"] = categories

        return result

    def get_prompt_by_id(self, prompt_id: int, user_id: int = None) -> Optional[PromptTemplate]:
        """
        프롬프트 조회 (ID)

        Args:
            prompt_id: 프롬프트 ID
            user_id: 사용자 ID (권한 체크용, None이면 체크 안 함)

        Returns:
            PromptTemplate 객체 또는 None

        Raises:
            PermissionError: 접근 권한 없음
        """
        prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()

        if not prompt:
            return None

        # 권한 체크 (본인 것이거나 공개 프롬프트)
        if user_id is not None:
            if prompt.user_id != user_id and not prompt.is_public:
                raise PermissionError("이 프롬프트에 접근할 권한이 없습니다")

        return prompt

    def create_prompt(self, user_id: int, data: Dict) -> int:
        """
        프롬프트 생성

        Args:
            user_id: 사용자 ID
            data: {
                "title": str,
                "category": str (optional),
                "description": str (optional),
                "prompt_content": str,
                "is_public": bool (optional),
                "order_index": int (optional),
                "system": str (optional)
            }

        Returns:
            생성된 프롬프트 ID
        """
        prompt = PromptTemplate(
            user_id=user_id,
            title=data['title'],
            category=data.get('category', '기타'),
            description=data.get('description'),
            prompt_content=data['prompt_content'],
            is_public=data.get('is_public', False),
            order_index=data.get('order_index', 999),
            system=data.get('system')
        )

        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)

        return prompt.id

    def update_prompt(self, user_id: int, prompt_id: int, data: Dict) -> None:
        """
        프롬프트 수정 (본인 것만)

        Args:
            user_id: 사용자 ID
            prompt_id: 프롬프트 ID
            data: 수정할 필드들

        Raises:
            PermissionError: 권한 없음
            ValueError: 프롬프트 없음
        """
        prompt = self.db.query(PromptTemplate)\
            .filter_by(id=prompt_id, user_id=user_id)\
            .first()

        if not prompt:
            raise ValueError("프롬프트를 찾을 수 없거나 권한이 없습니다")

        # 수정 가능한 필드
        allowed_fields = ['title', 'category', 'description', 'prompt_content', 'is_public', 'order_index', 'system']

        for key, value in data.items():
            if key in allowed_fields:
                setattr(prompt, key, value)

        self.db.commit()

    def delete_prompt(self, user_id: int, prompt_id: int) -> None:
        """
        프롬프트 삭제 (본인 것만)

        Args:
            user_id: 사용자 ID
            prompt_id: 프롬프트 ID

        Raises:
            ValueError: 프롬프트 없음 또는 권한 없음
        """
        prompt = self.db.query(PromptTemplate)\
            .filter_by(id=prompt_id, user_id=user_id)\
            .first()

        if not prompt:
            raise ValueError("프롬프트를 찾을 수 없거나 권한이 없습니다")

        self.db.delete(prompt)
        self.db.commit()

    def get_prompts_by_ids(self, prompt_ids: List[int], user_id: int) -> List[PromptTemplate]:
        """
        여러 프롬프트 조회 (ID 리스트)
        본인 것 + 공개 프롬프트만

        Args:
            prompt_ids: 프롬프트 ID 리스트
            user_id: 사용자 ID

        Returns:
            프롬프트 리스트 (order_index 순)

        Raises:
            ValueError: 일부 프롬프트에 접근 권한 없음
        """
        prompts = self.db.query(PromptTemplate)\
            .filter(
                and_(
                    PromptTemplate.id.in_(prompt_ids),
                    or_(
                        PromptTemplate.user_id == user_id,
                        PromptTemplate.is_public == True
                    )
                )
            )\
            .order_by(PromptTemplate.order_index, PromptTemplate.title)\
            .all()

        # 권한 체크
        if len(prompts) != len(prompt_ids):
            found_ids = set(p.id for p in prompts)
            missing_ids = set(prompt_ids) - found_ids
            raise ValueError(f"일부 프롬프트에 접근할 수 없습니다: {missing_ids}")

        return prompts

    def get_categories(self, user_id: int) -> List[str]:
        """사용자가 사용 가능한 카테고리 목록"""
        prompts = self.db.query(PromptTemplate)\
            .filter(
                or_(
                    PromptTemplate.user_id == user_id,
                    PromptTemplate.is_public == True
                )
            )\
            .all()

        categories = sorted(set(p.category for p in prompts))
        return categories


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager, User

    print("=== Prompt Service 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_prompts.db')
    db.create_tables()
    session = db.get_session()

    try:
        # 사용자 생성
        user1 = User(username='user1', email='user1@test.com', password_hash='hash1')
        user2 = User(username='user2', email='user2@test.com', password_hash='hash2')
        session.add_all([user1, user2])
        session.commit()

        # 서비스 생성
        prompt_service = PromptService(session)

        # 1. 프롬프트 생성
        print("1. 프롬프트 생성 테스트")
        prompt_id1 = prompt_service.create_prompt(user1.id, {
            'title': 'BMT 현황',
            'category': 'BMT',
            'description': 'BMT 현황 조회',
            'prompt_content': 'BMT 테이블을 생성해주세요',
            'is_public': False,
            'order_index': 1
        })
        print(f"   ✅ 프롬프트 생성: ID={prompt_id1}")

        prompt_id2 = prompt_service.create_prompt(user1.id, {
            'title': 'PM 현황',
            'category': 'PM',
            'prompt_content': 'PM 현황 조회',
            'is_public': True,  # 공개
            'order_index': 2
        })
        print(f"   ✅ 공개 프롬프트 생성: ID={prompt_id2}")

        # 2. 프롬프트 조회
        print("\n2. 프롬프트 조회 테스트")
        result = prompt_service.get_user_prompts(user1.id, include_public=True)
        print(f"   내 프롬프트: {len(result['my_prompts'])}개")
        print(f"   공개 프롬프트: {len(result['public_prompts'])}개")
        print(f"   카테고리: {result['categories']}")

        # 3. 다른 사용자가 공개 프롬프트 조회
        print("\n3. 다른 사용자의 공개 프롬프트 조회")
        result2 = prompt_service.get_user_prompts(user2.id, include_public=True)
        print(f"   user2의 프롬프트: {len(result2['my_prompts'])}개")
        print(f"   user2가 볼 수 있는 공개 프롬프트: {len(result2['public_prompts'])}개")

        # 4. 프롬프트 수정
        print("\n4. 프롬프트 수정 테스트")
        prompt_service.update_prompt(user1.id, prompt_id1, {
            'title': '수정된 BMT 현황',
            'description': '수정된 설명'
        })
        print("   ✅ 프롬프트 수정 완료")

        # 5. 권한 없는 수정 시도
        print("\n5. 권한 없는 수정 시도")
        try:
            prompt_service.update_prompt(user2.id, prompt_id1, {'title': 'hack'})
        except ValueError as e:
            print(f"   ✅ 예상된 오류: {e}")

        # 6. 프롬프트 삭제
        print("\n6. 프롬프트 삭제 테스트")
        prompt_service.delete_prompt(user1.id, prompt_id1)
        print("   ✅ 프롬프트 삭제 완료")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
