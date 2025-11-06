#!/usr/bin/env python3
"""
Report Models - 멀티유저 보고서 시스템 모델

SQLAlchemy 모델 정의:
- User: 사용자
- UserGroup: 사용자 그룹
- GroupMember: 그룹 멤버십
- PromptTemplate: 프롬프트 템플릿
- Report: 보고서 히스토리
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, create_engine, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json

Base = declarative_base()


class User(Base):
    """사용자 모델"""
    __tablename__ = 'report_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    system_name = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    prompts = relationship('PromptTemplate', back_populates='user', cascade='all, delete-orphan')
    reports = relationship('Report', back_populates='user', cascade='all, delete-orphan')
    owned_groups = relationship('UserGroup', back_populates='owner', foreign_keys='UserGroup.created_by')
    group_memberships = relationship('GroupMember', back_populates='user', cascade='all, delete-orphan')

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'system_name': self.system_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class UserGroup(Base):
    """사용자 그룹 모델"""
    __tablename__ = 'user_groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship('User', back_populates='owned_groups', foreign_keys=[created_by])
    members = relationship('GroupMember', back_populates='group', cascade='all, delete-orphan')
    categories = relationship('GroupCategory', back_populates='group', cascade='all, delete-orphan', order_by='GroupCategory.order_index')
    prompts = relationship('PromptTemplate', back_populates='group')
    reports = relationship('Report', back_populates='group')

    def to_dict(self, include_members=False, include_stats=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

        if include_members:
            result['members'] = [m.to_dict(include_user=True) for m in self.members]

        if include_stats:
            result['member_count'] = len(self.members)
            result['prompt_count'] = len(self.prompts)

        return result

    def __repr__(self):
        return f"<UserGroup(id={self.id}, name='{self.name}')>"


class GroupMember(Base):
    """그룹 멤버십 모델"""
    __tablename__ = 'group_members'
    __table_args__ = (
        UniqueConstraint('group_id', 'user_id', name='uq_group_user'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('user_groups.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    role = Column(String(20), default='member', nullable=False, index=True)  # 'owner' or 'member'
    system = Column(String(50))  # NCMS, EUXP, EDMP, ACS
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    group = relationship('UserGroup', back_populates='members')
    user = relationship('User', back_populates='group_memberships')

    def to_dict(self, include_user=False, include_group=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'role': self.role,
            'system': self.system,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }

        if include_user and self.user:
            # Flatten user info for easier access
            result['username'] = getattr(self.user, 'username', self.user.email)
            result['email'] = self.user.email
            result['user'] = {
                'id': self.user.id,
                'username': getattr(self.user, 'username', self.user.email),
                'email': self.user.email
            }

        if include_group and self.group:
            result['group'] = {
                'id': self.group.id,
                'name': self.group.name
            }

        return result

    def __repr__(self):
        return f"<GroupMember(id={self.id}, group_id={self.group_id}, user_id={self.user_id}, role='{self.role}')>"


class GroupCategory(Base):
    """그룹 카테고리 모델 - 그룹별 고유 카테고리"""
    __tablename__ = 'group_categories'
    __table_args__ = (
        UniqueConstraint('group_id', 'name', name='uq_group_category'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('user_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    order_index = Column(Integer, default=999)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    group = relationship('UserGroup', back_populates='categories')

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'group_id': self.group_id,
            'name': self.name,
            'description': self.description,
            'order_index': self.order_index,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<GroupCategory(id={self.id}, group_id={self.group_id}, name='{self.name}')>"


class PromptTemplate(Base):
    """프롬프트 템플릿 모델"""
    __tablename__ = 'prompt_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default='기타', nullable=False, index=True)
    description = Column(Text)
    prompt_content = Column(Text, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False, index=True)
    order_index = Column(Integer, default=999, nullable=False)
    group_id = Column(Integer, ForeignKey('user_groups.id'), nullable=True, index=True)  # 그룹 프롬프트
    system = Column(String(50), nullable=True, index=True)  # NCMS, EUXP, EDMP 등
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship('User', back_populates='prompts')
    group = relationship('UserGroup', back_populates='prompts')

    def to_dict(self, include_content=False, include_owner=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'is_public': self.is_public,
            'order_index': self.order_index,
            'group_id': self.group_id,
            'system': self.system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_content:
            result['prompt_content'] = self.prompt_content

        if include_owner and self.user:
            result['owner'] = self.user.username

        return result

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, title='{self.title}', user_id={self.user_id}, group_id={self.group_id})>"


class Report(Base):
    """보고서 히스토리 모델"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    html_content = Column(Text, nullable=False)
    prompt_ids = Column(Text, nullable=False)  # JSON array: ["1", "3", "5"]
    group_id = Column(Integer, ForeignKey('user_groups.id'), nullable=True, index=True)  # 그룹 보고서
    report_type = Column(String(20), default='personal', nullable=False, index=True)  # 'personal' or 'group'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship('User', back_populates='reports')
    group = relationship('UserGroup', back_populates='reports')

    def get_prompt_ids(self):
        """prompt_ids를 리스트로 반환"""
        try:
            return json.loads(self.prompt_ids) if self.prompt_ids else []
        except:
            return []

    def set_prompt_ids(self, ids):
        """prompt_ids를 JSON 문자열로 저장"""
        self.prompt_ids = json.dumps(ids)

    def to_dict(self, include_html=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'prompt_count': len(self.get_prompt_ids()),
            'group_id': self.group_id,
            'report_type': self.report_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

        if include_html:
            result['html_content'] = self.html_content
            result['prompt_ids'] = self.get_prompt_ids()

        return result

    def __repr__(self):
        return f"<Report(id={self.id}, title='{self.title}', user_id={self.user_id}, report_type='{self.report_type}')>"


# 데이터베이스 초기화
class DatabaseManager:
    """데이터베이스 관리자"""

    def __init__(self, db_path='reports.db'):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """테이블 생성"""
        Base.metadata.create_all(self.engine)
        print("✅ 데이터베이스 테이블 생성 완료")

    def get_session(self):
        """세션 생성"""
        return self.SessionLocal()

    def drop_tables(self):
        """테이블 삭제 (주의!)"""
        Base.metadata.drop_all(self.engine)
        print("⚠️  데이터베이스 테이블 삭제 완료")


if __name__ == "__main__":
    # 테스트
    print("=== Report Models 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_reports.db')
    db.create_tables()

    # 세션 생성
    session = db.get_session()

    try:
        # 사용자 생성
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash='hashed_password'
        )
        session.add(user)
        session.commit()
        print(f"✅ 사용자 생성: {user}")

        # 프롬프트 생성
        prompt = PromptTemplate(
            user_id=user.id,
            title='테스트 프롬프트',
            category='테스트',
            description='테스트용 프롬프트입니다',
            prompt_content='테스트 내용',
            is_public=False,
            order_index=1
        )
        session.add(prompt)
        session.commit()
        print(f"✅ 프롬프트 생성: {prompt}")

        # 보고서 생성
        report = Report(
            user_id=user.id,
            title='테스트 보고서',
            html_content='<html>...</html>',
            prompt_ids=json.dumps([1, 2, 3])
        )
        session.add(report)
        session.commit()
        print(f"✅ 보고서 생성: {report}")

        # 조회 테스트
        print("\n=== 조회 테스트 ===")
        print(f"사용자: {user.to_dict()}")
        print(f"프롬프트: {prompt.to_dict(include_content=True, include_owner=True)}")
        print(f"보고서: {report.to_dict(include_html=True)}")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
