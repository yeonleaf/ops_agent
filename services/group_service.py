#!/usr/bin/env python3
"""
Group Service - 그룹 관리 서비스

그룹 생성, 멤버 관리, 권한 체크
"""

from typing import List, Dict, Optional
from models.report_models import UserGroup, GroupMember, User, PromptTemplate, GroupCategory
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError


class GroupService:
    """그룹 관리 서비스"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def get_user_groups(self, user_id: int) -> List[Dict]:
        """
        사용자가 속한 그룹 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            그룹 목록 (역할 포함)
            [
                {
                    "id": 1,
                    "name": "OTT운영팀",
                    "role": "owner",
                    "member_count": 3,
                    "prompt_count": 8
                }
            ]
        """
        # 사용자의 그룹 멤버십 조회
        memberships = self.db.query(GroupMember)\
            .filter_by(user_id=user_id)\
            .all()

        result = []
        for membership in memberships:
            group = membership.group
            group_dict = group.to_dict(include_stats=True)
            group_dict['role'] = membership.role
            group_dict['system'] = membership.system
            result.append(group_dict)

        return result

    def create_group(self, user_id: int, name: str, description: str = None) -> Dict:
        """
        그룹 생성 (생성자를 owner로 자동 추가)

        Args:
            user_id: 생성자 ID
            name: 그룹명
            description: 그룹 설명

        Returns:
            생성된 그룹 정보

        Raises:
            ValueError: 그룹명 중복
        """
        try:
            # 트랜잭션 시작
            # 1. 그룹 생성
            group = UserGroup(
                name=name,
                description=description,
                created_by=user_id
            )
            self.db.add(group)
            self.db.flush()  # ID 생성

            # 2. 생성자를 owner로 추가
            owner_membership = GroupMember(
                group_id=group.id,
                user_id=user_id,
                role='owner'
            )
            self.db.add(owner_membership)

            self.db.commit()

            return group.to_dict(include_members=True, include_stats=True)

        except IntegrityError as e:
            self.db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'unique' in str(e).lower():
                raise ValueError(f"이미 존재하는 그룹명입니다: {name}")
            raise

        except Exception as e:
            self.db.rollback()
            raise

    def get_group_detail(self, group_id: int, user_id: int) -> Dict:
        """
        그룹 상세 조회 (권한 체크)

        Args:
            group_id: 그룹 ID
            user_id: 요청 사용자 ID

        Returns:
            {
                "group": {...},
                "members": [...],
                "prompts_by_category": {
                    "운영지원": [...],
                    "BMT": [...]
                },
                "my_role": "owner" or "member"
            }

        Raises:
            PermissionError: 그룹 멤버가 아님
            ValueError: 그룹 없음
        """
        # 그룹 조회
        group = self.db.query(UserGroup).filter_by(id=group_id).first()
        if not group:
            raise ValueError(f"그룹을 찾을 수 없습니다 (ID: {group_id})")

        # 권한 체크 (멤버인지 확인)
        membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=user_id)\
            .first()

        if not membership:
            raise PermissionError("이 그룹에 접근할 권한이 없습니다")

        # 멤버 목록
        members = [m.to_dict(include_user=True) for m in group.members]

        # 카테고리 목록
        categories = self.db.query(GroupCategory)\
            .filter_by(group_id=group_id)\
            .order_by(GroupCategory.order_index, GroupCategory.name)\
            .all()

        # 프롬프트 목록 (카테고리별 그룹핑) - User 관계 eager load
        from sqlalchemy.orm import joinedload

        prompts = self.db.query(PromptTemplate)\
            .options(joinedload(PromptTemplate.user))\
            .filter_by(group_id=group_id)\
            .order_by(PromptTemplate.category, PromptTemplate.order_index, PromptTemplate.title)\
            .all()

        prompts_by_category = {}
        for prompt in prompts:
            category = prompt.category or '기타'
            if category not in prompts_by_category:
                prompts_by_category[category] = []

            prompt_dict = prompt.to_dict(include_content=True, include_owner=True)

            # 디버깅: prompt_content 확인
            if not prompt_dict.get('prompt_content'):
                print(f"⚠️ 프롬프트 ID {prompt.id}의 내용이 없습니다")
                print(f"   prompt.prompt_content: {prompt.prompt_content}")

            prompts_by_category[category].append(prompt_dict)

        return {
            "group": group.to_dict(include_stats=True),
            "members": members,
            "categories": [cat.to_dict() for cat in categories],
            "prompts_by_category": prompts_by_category,
            "my_role": membership.role
        }

    def add_member(self, group_id: int, owner_id: int, new_user_id: int, system: str = None) -> Dict:
        """
        그룹에 멤버 추가 (owner만 가능)

        Args:
            group_id: 그룹 ID
            owner_id: 요청자 ID (owner 여부 체크)
            new_user_id: 추가할 사용자 ID
            system: 담당 시스템 (NCMS, EUXP 등)

        Returns:
            추가된 멤버 정보

        Raises:
            PermissionError: owner가 아님
            ValueError: 사용자 없음, 이미 멤버
        """
        # 권한 체크 (owner인지 확인)
        owner_membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=owner_id, role='owner')\
            .first()

        if not owner_membership:
            raise PermissionError("멤버를 추가할 권한이 없습니다 (owner만 가능)")

        # 사용자 존재 확인
        user = self.db.query(User).filter_by(id=new_user_id).first()
        if not user:
            raise ValueError(f"사용자를 찾을 수 없습니다 (ID: {new_user_id})")

        # 이미 멤버인지 확인
        existing = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=new_user_id)\
            .first()

        if existing:
            raise ValueError(f"{user.username}님은 이미 그룹 멤버입니다")

        try:
            # 멤버 추가
            new_member = GroupMember(
                group_id=group_id,
                user_id=new_user_id,
                role='member',
                system=system
            )
            self.db.add(new_member)
            self.db.commit()

            return new_member.to_dict(include_user=True)

        except Exception as e:
            self.db.rollback()
            raise

    def remove_member(self, group_id: int, owner_id: int, target_user_id: int) -> bool:
        """
        그룹에서 멤버 제거 (owner만 가능, owner는 제거 불가)

        Args:
            group_id: 그룹 ID
            owner_id: 요청자 ID (owner 여부 체크)
            target_user_id: 제거할 사용자 ID

        Returns:
            성공 여부

        Raises:
            PermissionError: owner가 아니거나, owner를 제거하려고 시도
            ValueError: 멤버가 아님
        """
        # 권한 체크 (owner인지 확인)
        owner_membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=owner_id, role='owner')\
            .first()

        if not owner_membership:
            raise PermissionError("멤버를 제거할 권한이 없습니다 (owner만 가능)")

        # 제거 대상 조회
        target_membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=target_user_id)\
            .first()

        if not target_membership:
            raise ValueError("그룹 멤버가 아닙니다")

        # owner는 제거 불가
        if target_membership.role == 'owner':
            raise PermissionError("그룹 owner는 제거할 수 없습니다")

        try:
            self.db.delete(target_membership)
            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            raise

    def update_group(self, group_id: int, user_id: int, name: str = None, description: str = None) -> Dict:
        """
        그룹 정보 수정 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID
            name: 새 그룹명 (선택)
            description: 새 설명 (선택)

        Returns:
            수정된 그룹 정보

        Raises:
            PermissionError: owner가 아님
            ValueError: 그룹 없음
        """
        # 권한 체크
        owner_membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=user_id, role='owner')\
            .first()

        if not owner_membership:
            raise PermissionError("그룹 정보를 수정할 권한이 없습니다 (owner만 가능)")

        group = self.db.query(UserGroup).filter_by(id=group_id).first()
        if not group:
            raise ValueError(f"그룹을 찾을 수 없습니다 (ID: {group_id})")

        try:
            if name:
                group.name = name
            if description is not None:
                group.description = description

            self.db.commit()
            return group.to_dict(include_stats=True)

        except IntegrityError as e:
            self.db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'unique' in str(e).lower():
                raise ValueError(f"이미 존재하는 그룹명입니다: {name}")
            raise

        except Exception as e:
            self.db.rollback()
            raise

    def delete_group(self, group_id: int, user_id: int) -> bool:
        """
        그룹 삭제 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID

        Returns:
            성공 여부

        Raises:
            PermissionError: owner가 아님
            ValueError: 그룹 없음
        """
        # 권한 체크
        owner_membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=user_id, role='owner')\
            .first()

        if not owner_membership:
            raise PermissionError("그룹을 삭제할 권한이 없습니다 (owner만 가능)")

        group = self.db.query(UserGroup).filter_by(id=group_id).first()
        if not group:
            raise ValueError(f"그룹을 찾을 수 없습니다 (ID: {group_id})")

        try:
            self.db.delete(group)
            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            raise

    def is_group_member(self, group_id: int, user_id: int) -> bool:
        """
        그룹 멤버 여부 확인

        Args:
            group_id: 그룹 ID
            user_id: 사용자 ID

        Returns:
            멤버 여부
        """
        membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=user_id)\
            .first()

        return membership is not None

    def is_group_owner(self, group_id: int, user_id: int) -> bool:
        """
        그룹 owner 여부 확인

        Args:
            group_id: 그룹 ID
            user_id: 사용자 ID

        Returns:
            owner 여부
        """
        membership = self.db.query(GroupMember)\
            .filter_by(group_id=group_id, user_id=user_id, role='owner')\
            .first()

        return membership is not None

    # ==================== 카테고리 관리 ====================

    def get_group_categories(self, group_id: int, user_id: int) -> List[Dict]:
        """
        그룹 카테고리 목록 조회 (멤버 접근 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID

        Returns:
            카테고리 목록 (order_index 순)

        Raises:
            PermissionError: 그룹 멤버가 아님
            ValueError: 그룹 없음
        """
        # 그룹 존재 확인
        group = self.db.query(UserGroup).filter_by(id=group_id).first()
        if not group:
            raise ValueError(f"그룹을 찾을 수 없습니다 (ID: {group_id})")

        # 권한 체크 (멤버인지 확인)
        if not self.is_group_member(group_id, user_id):
            raise PermissionError("이 그룹에 접근할 권한이 없습니다")

        # 카테고리 조회
        categories = self.db.query(GroupCategory)\
            .filter_by(group_id=group_id)\
            .order_by(GroupCategory.order_index, GroupCategory.name)\
            .all()

        return [cat.to_dict() for cat in categories]

    def add_category(self, group_id: int, user_id: int, name: str,
                    description: str = None, order_index: int = 999) -> Dict:
        """
        그룹에 카테고리 추가 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID (owner 여부 체크)
            name: 카테고리명
            description: 설명
            order_index: 순서

        Returns:
            추가된 카테고리 정보

        Raises:
            PermissionError: owner가 아님
            ValueError: 카테고리명 중복
        """
        # 권한 체크 (owner인지 확인)
        if not self.is_group_owner(group_id, user_id):
            raise PermissionError("카테고리를 추가할 권한이 없습니다 (owner만 가능)")

        try:
            # 카테고리 생성
            category = GroupCategory(
                group_id=group_id,
                name=name,
                description=description,
                order_index=order_index
            )
            self.db.add(category)
            self.db.commit()

            return category.to_dict()

        except IntegrityError as e:
            self.db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'uq_group_category' in str(e):
                raise ValueError(f"이미 존재하는 카테고리명입니다: {name}")
            raise

        except Exception as e:
            self.db.rollback()
            raise

    def update_category(self, group_id: int, user_id: int, category_id: int,
                       name: str = None, description: str = None) -> Dict:
        """
        카테고리 정보 수정 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID
            category_id: 카테고리 ID
            name: 새 카테고리명 (선택)
            description: 새 설명 (선택)

        Returns:
            수정된 카테고리 정보

        Raises:
            PermissionError: owner가 아님
            ValueError: 카테고리 없음
        """
        # 권한 체크
        if not self.is_group_owner(group_id, user_id):
            raise PermissionError("카테고리를 수정할 권한이 없습니다 (owner만 가능)")

        # 카테고리 조회
        category = self.db.query(GroupCategory)\
            .filter_by(id=category_id, group_id=group_id)\
            .first()

        if not category:
            raise ValueError(f"카테고리를 찾을 수 없습니다 (ID: {category_id})")

        try:
            if name:
                category.name = name
            if description is not None:
                category.description = description

            self.db.commit()
            return category.to_dict()

        except IntegrityError as e:
            self.db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'uq_group_category' in str(e):
                raise ValueError(f"이미 존재하는 카테고리명입니다: {name}")
            raise

        except Exception as e:
            self.db.rollback()
            raise

    def delete_category(self, group_id: int, user_id: int, category_id: int) -> bool:
        """
        카테고리 삭제 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID
            category_id: 카테고리 ID

        Returns:
            성공 여부

        Raises:
            PermissionError: owner가 아님
            ValueError: 카테고리 없음
        """
        # 권한 체크
        if not self.is_group_owner(group_id, user_id):
            raise PermissionError("카테고리를 삭제할 권한이 없습니다 (owner만 가능)")

        # 카테고리 조회
        category = self.db.query(GroupCategory)\
            .filter_by(id=category_id, group_id=group_id)\
            .first()

        if not category:
            raise ValueError(f"카테고리를 찾을 수 없습니다 (ID: {category_id})")

        try:
            self.db.delete(category)
            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            raise

    def reorder_categories(self, group_id: int, user_id: int,
                          category_orders: List[Dict]) -> List[Dict]:
        """
        카테고리 순서 변경 (owner만 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청자 ID
            category_orders: [{"id": 1, "order_index": 0}, {"id": 2, "order_index": 1}, ...]

        Returns:
            수정된 카테고리 목록

        Raises:
            PermissionError: owner가 아님
        """
        # 권한 체크
        if not self.is_group_owner(group_id, user_id):
            raise PermissionError("카테고리 순서를 변경할 권한이 없습니다 (owner만 가능)")

        try:
            for order_info in category_orders:
                category_id = order_info.get('id')
                order_index = order_info.get('order_index')

                if category_id is None or order_index is None:
                    continue

                category = self.db.query(GroupCategory)\
                    .filter_by(id=category_id, group_id=group_id)\
                    .first()

                if category:
                    category.order_index = order_index

            self.db.commit()

            # 갱신된 목록 반환
            categories = self.db.query(GroupCategory)\
                .filter_by(group_id=group_id)\
                .order_by(GroupCategory.order_index, GroupCategory.name)\
                .all()

            return [cat.to_dict() for cat in categories]

        except Exception as e:
            self.db.rollback()
            raise
