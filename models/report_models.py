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
import uuid

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


class PromptTemplate(Base):
    """프롬프트 템플릿 모델"""
    __tablename__ = 'prompt_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default='기타', nullable=False, index=True)
    description = Column(Text)
    prompt_content = Column(Text, nullable=False)
    jql = Column(Text, nullable=True)  # JQL 쿼리 (선택적)
    is_public = Column(Boolean, default=False, nullable=False, index=True)
    order_index = Column(Integer, default=999, nullable=False)
    system = Column(String(50), nullable=True, index=True)  # NCMS, EUXP, EDMP 등
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship('User', back_populates='prompts')

    def to_dict(self, include_content=False, include_owner=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'is_public': self.is_public,
            'order_index': self.order_index,
            'system': self.system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_content:
            result['prompt_content'] = self.prompt_content
            result['jql'] = self.jql

        if include_owner and self.user:
            result['owner'] = self.user.username

        return result

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class Report(Base):
    """보고서 히스토리 모델"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    html_content = Column(Text, nullable=False)
    prompt_ids = Column(Text, nullable=False)  # JSON array: ["1", "3", "5"]
    group_id = Column(Integer, nullable=True)
    report_type = Column(String(20), default='monthly', nullable=False)  # 'monthly', 'weekly', 'custom'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship('User', back_populates='reports')

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
            'report_type': self.report_type,
            'group_id': self.group_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

        if include_html:
            result['html_content'] = self.html_content
            result['prompt_ids'] = self.get_prompt_ids()

        return result

    def __repr__(self):
        return f"<Report(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class PromptExecution(Base):
    """프롬프트 실행 캐시 모델 - Jira 이슈 및 HTML 결과 캐싱"""
    __tablename__ = 'prompt_executions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_id = Column(Integer, ForeignKey('prompt_templates.id'), nullable=False, index=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    jira_issues = Column(Text, nullable=True)  # JSON array of Jira issues
    html_output = Column(Text, nullable=True)  # AI generated HTML fragment
    execution_metadata = Column(Text, nullable=True)  # JSON: execution stats, query params, etc.

    def get_jira_issues(self):
        """jira_issues를 리스트로 반환"""
        try:
            return json.loads(self.jira_issues) if self.jira_issues else []
        except:
            return []

    def set_jira_issues(self, issues):
        """jira_issues를 JSON 문자열로 저장"""
        self.jira_issues = json.dumps(issues, ensure_ascii=False)

    def get_metadata(self):
        """metadata를 딕셔너리로 반환"""
        try:
            return json.loads(self.execution_metadata) if self.execution_metadata else {}
        except:
            return {}

    def set_metadata(self, meta):
        """metadata를 JSON 문자열로 저장"""
        self.execution_metadata = json.dumps(meta, ensure_ascii=False)

    def to_dict(self, include_content=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'prompt_id': self.prompt_id,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'jira_issue_count': len(self.get_jira_issues()),
            'has_html': bool(self.html_output),
            'metadata': self.get_metadata()
        }

        if include_content:
            result['jira_issues'] = self.get_jira_issues()
            result['html_output'] = self.html_output

        return result

    def __repr__(self):
        return f"<PromptExecution(id={self.id}, prompt_id={self.prompt_id}, executed_at={self.executed_at})>"


class ReportTemplate(Base):
    """보고서 템플릿 모델 - Markdown + placeholder"""
    __tablename__ = 'report_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    template_content = Column(Text, nullable=False)  # Markdown with {{prompt:id}} placeholders
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship('User')

    def to_dict(self, include_content=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_content:
            result['template_content'] = self.template_content

        return result

    def __repr__(self):
        return f"<ReportTemplate(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class Variable(Base):
    """전역 변수 모델"""
    __tablename__ = 'variables'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'value': self.value,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Variable(name='{self.name}', value='{self.value}')>"


class JQLQuery(Base):
    """JQL 쿼리 모델 - 재사용 가능한 JQL 저장소"""
    __tablename__ = 'jql_queries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('report_users.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)  # 예: "NCMS_BMT", "EUXP_PM작업"
    description = Column(Text, nullable=True)
    jql = Column(Text, nullable=False)  # JQL 쿼리 문자열
    system = Column(String(50), nullable=True, index=True)  # NCMS, EUXP, EDMP, ACS 등
    category = Column(String(50), nullable=True, index=True)  # BMT, PM, DB작업, 개발, 운영지원 등
    is_public = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship('User')

    def to_dict(self, include_jql=False, include_owner=False):
        """딕셔너리 변환"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'system': self.system,
            'category': self.category,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_jql:
            result['jql'] = self.jql

        if include_owner and self.user:
            result['owner'] = self.user.username

        return result

    def __repr__(self):
        return f"<JQLQuery(id={self.id}, name='{self.name}', system='{self.system}')>"


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
