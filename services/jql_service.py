#!/usr/bin/env python3
"""
JQL Service - JQL 쿼리 관리 서비스

사용자별 JQL 쿼리 CRUD 및 관리
"""

from typing import List, Dict, Optional
from models.report_models import JQLQuery, User
from sqlalchemy import or_, and_


class JQLService:
    """JQL 쿼리 관리 서비스"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def get_user_jqls(
        self,
        user_id: int,
        include_public: bool = False,
        system: str = None,
        category: str = None,
        search: str = None
    ) -> Dict:
        """
        사용자의 JQL 쿼리 조회 (+ 옵션: 공개 JQL, 필터링)

        Args:
            user_id: 사용자 ID
            include_public: 공개 JQL 포함 여부
            system: 필터링할 시스템 (None이면 전체)
            category: 필터링할 카테고리 (None이면 전체)
            search: 검색 키워드 (이름, JQL 내용)

        Returns:
            {
                "my_jqls": [...],
                "public_jqls": [...],  # include_public=True인 경우
                "systems": [...],
                "categories": [...]
            }
        """
        # 내 JQL 쿼리
        my_query = self.db.query(JQLQuery).filter_by(user_id=user_id)

        # 필터 적용
        if system:
            my_query = my_query.filter(JQLQuery.system == system)
        if category:
            my_query = my_query.filter(JQLQuery.category == category)
        if search:
            my_query = my_query.filter(
                or_(
                    JQLQuery.name.contains(search),
                    JQLQuery.jql.contains(search),
                    JQLQuery.description.contains(search)
                )
            )

        my_jqls = my_query.order_by(JQLQuery.name).all()

        result = {
            "my_jqls": [j.to_dict(include_jql=True, include_owner=True) for j in my_jqls]
        }

        # 공개 JQL 포함
        if include_public:
            public_query = self.db.query(JQLQuery).filter(
                and_(
                    JQLQuery.is_public == True,
                    JQLQuery.user_id != user_id
                )
            )

            # 필터 적용
            if system:
                public_query = public_query.filter(JQLQuery.system == system)
            if category:
                public_query = public_query.filter(JQLQuery.category == category)
            if search:
                public_query = public_query.filter(
                    or_(
                        JQLQuery.name.contains(search),
                        JQLQuery.jql.contains(search),
                        JQLQuery.description.contains(search)
                    )
                )

            public_jqls = public_query.order_by(JQLQuery.name).all()
            result["public_jqls"] = [j.to_dict(include_jql=True, include_owner=True) for j in public_jqls]

        # 시스템 목록 (중복 제거)
        systems_query = self.db.query(JQLQuery.system).filter(
            or_(
                JQLQuery.user_id == user_id,
                JQLQuery.is_public == True if include_public else False
            )
        ).distinct()
        result["systems"] = [s[0] for s in systems_query.all() if s[0]]

        # 카테고리 목록 (중복 제거)
        categories_query = self.db.query(JQLQuery.category).filter(
            or_(
                JQLQuery.user_id == user_id,
                JQLQuery.is_public == True if include_public else False
            )
        ).distinct()
        result["categories"] = [c[0] for c in categories_query.all() if c[0]]

        return result

    def get_jql_by_id(self, jql_id: int, user_id: int) -> Optional[JQLQuery]:
        """
        JQL ID로 조회 (본인 또는 공개 JQL만)

        Args:
            jql_id: JQL ID
            user_id: 요청 사용자 ID

        Returns:
            JQLQuery 또는 None
        """
        jql = self.db.query(JQLQuery).filter(
            and_(
                JQLQuery.id == jql_id,
                or_(
                    JQLQuery.user_id == user_id,
                    JQLQuery.is_public == True
                )
            )
        ).first()

        return jql

    def get_jql_by_name(self, name: str, user_id: int) -> Optional[JQLQuery]:
        """
        JQL 이름으로 조회 (본인 또는 공개 JQL만)

        Args:
            name: JQL 이름
            user_id: 요청 사용자 ID

        Returns:
            JQLQuery 또는 None
        """
        jql = self.db.query(JQLQuery).filter(
            and_(
                JQLQuery.name == name,
                or_(
                    JQLQuery.user_id == user_id,
                    JQLQuery.is_public == True
                )
            )
        ).first()

        return jql

    def create_jql(
        self,
        user_id: int,
        name: str,
        jql: str,
        description: str = None,
        system: str = None,
        category: str = None,
        is_public: bool = False
    ) -> JQLQuery:
        """
        JQL 생성

        Args:
            user_id: 사용자 ID
            name: JQL 이름
            jql: JQL 쿼리 문자열
            description: 설명
            system: 시스템 구분
            category: 카테고리
            is_public: 공개 여부

        Returns:
            생성된 JQLQuery

        Raises:
            ValueError: 중복된 이름이 있을 경우
        """
        # 중복 체크 (같은 사용자의 같은 이름)
        existing = self.db.query(JQLQuery).filter(
            and_(
                JQLQuery.user_id == user_id,
                JQLQuery.name == name
            )
        ).first()

        if existing:
            raise ValueError(f"JQL 이름 '{name}'이 이미 존재합니다.")

        # JQL 생성
        new_jql = JQLQuery(
            user_id=user_id,
            name=name,
            jql=jql,
            description=description,
            system=system,
            category=category,
            is_public=is_public
        )

        self.db.add(new_jql)
        self.db.commit()
        self.db.refresh(new_jql)

        return new_jql

    def update_jql(
        self,
        jql_id: int,
        user_id: int,
        name: str = None,
        jql: str = None,
        description: str = None,
        system: str = None,
        category: str = None,
        is_public: bool = None
    ) -> Optional[JQLQuery]:
        """
        JQL 수정 (본인 JQL만 수정 가능)

        Args:
            jql_id: JQL ID
            user_id: 사용자 ID
            name: JQL 이름 (선택)
            jql: JQL 쿼리 (선택)
            description: 설명 (선택)
            system: 시스템 (선택)
            category: 카테고리 (선택)
            is_public: 공개 여부 (선택)

        Returns:
            수정된 JQLQuery 또는 None

        Raises:
            ValueError: 권한이 없거나 중복된 이름일 경우
        """
        jql_obj = self.db.query(JQLQuery).filter_by(id=jql_id).first()

        if not jql_obj:
            return None

        # 권한 체크 (본인만 수정 가능)
        if jql_obj.user_id != user_id:
            raise ValueError("본인의 JQL만 수정할 수 있습니다.")

        # 이름 중복 체크 (이름이 변경되는 경우)
        if name and name != jql_obj.name:
            existing = self.db.query(JQLQuery).filter(
                and_(
                    JQLQuery.user_id == user_id,
                    JQLQuery.name == name,
                    JQLQuery.id != jql_id
                )
            ).first()

            if existing:
                raise ValueError(f"JQL 이름 '{name}'이 이미 존재합니다.")

        # 업데이트
        if name is not None:
            jql_obj.name = name
        if jql is not None:
            jql_obj.jql = jql
        if description is not None:
            jql_obj.description = description
        if system is not None:
            jql_obj.system = system
        if category is not None:
            jql_obj.category = category
        if is_public is not None:
            jql_obj.is_public = is_public

        self.db.commit()
        self.db.refresh(jql_obj)

        return jql_obj

    def delete_jql(self, jql_id: int, user_id: int) -> bool:
        """
        JQL 삭제 (본인 JQL만 삭제 가능)

        Args:
            jql_id: JQL ID
            user_id: 사용자 ID

        Returns:
            성공 여부

        Raises:
            ValueError: 권한이 없을 경우
        """
        jql = self.db.query(JQLQuery).filter_by(id=jql_id).first()

        if not jql:
            return False

        # 권한 체크
        if jql.user_id != user_id:
            raise ValueError("본인의 JQL만 삭제할 수 있습니다.")

        self.db.delete(jql)
        self.db.commit()

        return True

    def get_jql_usage(self, jql_id: int, user_id: int) -> Dict:
        """
        JQL 사용 현황 조회 (어떤 프롬프트에서 사용되는지)

        Args:
            jql_id: JQL ID
            user_id: 사용자 ID

        Returns:
            {
                "jql_id": ...,
                "jql_name": ...,
                "usage_count": ...,
                "used_in_prompts": [...]
            }
        """
        from models.report_models import PromptTemplate

        jql = self.get_jql_by_id(jql_id, user_id)

        if not jql:
            return None

        # JQL을 참조하는 프롬프트 검색
        # 방법 1: prompt_content에서 {{JQL:이름}} 패턴 검색
        # 방법 2: jql 컬럼에서 직접 비교 (레거시 방식)
        prompts = self.db.query(PromptTemplate).filter(
            or_(
                PromptTemplate.prompt_content.contains(f"{{{{JQL:{jql.name}}}}}"),
                PromptTemplate.jql == jql.jql
            )
        ).all()

        return {
            "jql_id": jql.id,
            "jql_name": jql.name,
            "usage_count": len(prompts),
            "used_in_prompts": [p.to_dict() for p in prompts]
        }
