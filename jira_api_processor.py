#!/usr/bin/env python3
"""
JIRA API 응답 정제 프로세서
임베딩 최적화와 비용 효율성을 고려한 데이터 처리
"""

import os
import time
import json
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from dotenv import load_dotenv

# HTML 정제기 import
try:
    from html_text_cleaner import JiraHTMLCleaner
    HTML_CLEANER_AVAILABLE = True
except ImportError:
    HTML_CLEANER_AVAILABLE = False

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IssueStatus(Enum):
    """이슈 상태"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"
    UNKNOWN = "unknown"


class IssuePriority(Enum):
    """이슈 우선순위"""
    HIGHEST = "highest"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    LOWEST = "lowest"
    UNKNOWN = "unknown"


@dataclass
class JiraComment:
    """JIRA 댓글 데이터"""
    id: str
    author: str
    body: str
    created: str
    updated: str
    is_public: bool = True


@dataclass
class JiraAttachment:
    """JIRA 첨부파일 메타데이터"""
    id: str
    filename: str
    size: int
    mime_type: str
    created: str
    author: str
    download_url: Optional[str] = None


@dataclass
class JiraIssueLink:
    """JIRA 이슈 링크 (핵심 유형만)"""
    id: str
    type: str  # "blocks", "is blocked by", "relates to", "duplicates" 등
    inward_issue: Optional[str] = None  # 들어오는 링크의 이슈 키
    outward_issue: Optional[str] = None  # 나가는 링크의 이슈 키
    description: Optional[str] = None


@dataclass
class ProcessedJiraIssue:
    """정제된 JIRA 이슈 데이터"""
    # 기본 식별자
    id: str
    key: str
    
    # 임베딩용 텍스트 (품질과 비용 최적화)
    embedding_text: str  # summary + description + 최근 댓글 3개
    
    # 핵심 메타데이터
    summary: str
    description: str
    issue_type: str
    status: IssueStatus
    priority: IssuePriority
    
    # 시간 정보 (정렬·증분 기준: updated)
    created: str
    updated: str
    resolved: Optional[str] = None
    
    # 담당자 정보
    assignee: Optional[str] = None
    reporter: str = ""
    
    # 프로젝트 정보
    project_key: str = ""
    project_name: str = ""
    
    # 댓글 (전체 보존, 임베딩에는 최근 3개만)
    comments: List[JiraComment] = field(default_factory=list)
    recent_comments_for_embedding: List[str] = field(default_factory=list)
    
    # 첨부파일 (메타데이터만)
    attachments: List[JiraAttachment] = field(default_factory=list)
    
    # 이슈 링크 (핵심 유형만 요약)
    issue_links: List[JiraIssueLink] = field(default_factory=list)
    
    # 처리 메타데이터
    processed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_data_available: bool = False  # 원본 데이터 보존 여부


class JiraRateLimiter:
    """JIRA API Rate Limit 관리"""
    
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests_per_minute = max_requests_per_minute
        self.requests_times = []
        
    def wait_if_needed(self):
        """필요시 대기"""
        now = time.time()
        
        # 1분 이내의 요청만 유지
        self.requests_times = [t for t in self.requests_times if now - t < 60]
        
        if len(self.requests_times) >= self.max_requests_per_minute:
            wait_time = 60 - (now - self.requests_times[0]) + 1
            if wait_time > 0:
                logger.info(f"Rate limit 대기: {wait_time:.1f}초")
                time.sleep(wait_time)
                
        self.requests_times.append(now)


class JiraAPIProcessor:
    """JIRA API 응답 정제 프로세서"""
    
    def __init__(self, 
                 api_token: Optional[str] = None, 
                 endpoint: Optional[str] = None,
                 email: Optional[str] = None,
                 max_requests_per_minute: int = 50,
                 enable_html_cleaning: bool = True):
        """
        초기화
        
        Args:
            api_token: JIRA API 토큰
            endpoint: JIRA 엔드포인트 (예: https://company.atlassian.net)
            email: JIRA 계정 이메일
            max_requests_per_minute: 분당 최대 요청 수
            enable_html_cleaning: HTML 정제 기능 사용 여부
        """
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")
        self.endpoint = endpoint or os.getenv("JIRA_API_ENDPOINT")
        self.email = email or os.getenv("JIRA_USER_EMAIL")
        
        if not all([self.api_token, self.endpoint, self.email]):
            raise ValueError("JIRA API 토큰, 엔드포인트, 이메일이 모두 필요합니다")
            
        self.rate_limiter = JiraRateLimiter(max_requests_per_minute)
        self.session = requests.Session()
        
        # Bearer Token 방식 사용 (테스트에서 성공한 방식)
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # HTML 정제기 초기화
        self.enable_html_cleaning = enable_html_cleaning and HTML_CLEANER_AVAILABLE
        if self.enable_html_cleaning:
            self.html_cleaner = JiraHTMLCleaner()
            logger.info("HTML 정제기 활성화")
        else:
            self.html_cleaner = None
            if enable_html_cleaning and not HTML_CLEANER_AVAILABLE:
                logger.warning("HTML 정제기를 사용할 수 없습니다. html_text_cleaner.py를 확인하세요.")
        
        logger.info(f"JIRA API 프로세서 초기화 완료: {self.endpoint}")
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Rate limit을 고려한 API 요청"""
        self.rate_limiter.wait_if_needed()
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {url}, 에러: {e}")
            raise
    
    def _normalize_status(self, status_name: str) -> IssueStatus:
        """상태 정규화"""
        status_lower = status_name.lower()
        
        if status_lower in ["open", "new", "created", "to do"]:
            return IssueStatus.OPEN
        elif status_lower in ["in progress", "in review", "in development"]:
            return IssueStatus.IN_PROGRESS
        elif status_lower in ["resolved", "fixed", "done"]:
            return IssueStatus.RESOLVED
        elif status_lower in ["closed", "completed"]:
            return IssueStatus.CLOSED
        elif status_lower in ["reopened"]:
            return IssueStatus.REOPENED
        else:
            return IssueStatus.UNKNOWN
    
    def _normalize_priority(self, priority_name: str) -> IssuePriority:
        """우선순위 정규화"""
        if not priority_name:
            return IssuePriority.UNKNOWN
            
        priority_lower = priority_name.lower()
        
        if priority_lower in ["highest", "critical", "blocker"]:
            return IssuePriority.HIGHEST
        elif priority_lower in ["high", "major"]:
            return IssuePriority.HIGH
        elif priority_lower in ["medium", "normal"]:
            return IssuePriority.MEDIUM
        elif priority_lower in ["low", "minor"]:
            return IssuePriority.LOW
        elif priority_lower in ["lowest", "trivial"]:
            return IssuePriority.LOWEST
        else:
            return IssuePriority.UNKNOWN
    
    def _extract_comments(self, issue_data: Dict) -> Tuple[List[JiraComment], List[str]]:
        """댓글 추출 (전체 보존 + 최근 3개 임베딩용)"""
        comments = []
        
        # 댓글 데이터 확인
        comment_data = issue_data.get("fields", {}).get("comment", {})
        if not comment_data or "comments" not in comment_data:
            return [], []
        
        # 모든 댓글 추출
        for comment in comment_data.get("comments", []):
            jira_comment = JiraComment(
                id=comment.get("id", ""),
                author=comment.get("author", {}).get("displayName", "Unknown"),
                body=comment.get("body", ""),
                created=comment.get("created", ""),
                updated=comment.get("updated", ""),
                is_public=not comment.get("visibility", {})  # visibility가 없으면 public
            )
            comments.append(jira_comment)
        
        # 최근 3개 댓글 (임베딩용)
        recent_comments = sorted(comments, key=lambda x: x.updated, reverse=True)[:3]
        recent_comments_text = [c.body for c in recent_comments if c.body.strip()]
        
        return comments, recent_comments_text
    
    def _extract_attachments(self, issue_data: Dict) -> List[JiraAttachment]:
        """첨부파일 메타데이터 추출"""
        attachments = []
        
        attachment_data = issue_data.get("fields", {}).get("attachment", [])
        
        for attachment in attachment_data:
            jira_attachment = JiraAttachment(
                id=attachment.get("id", ""),
                filename=attachment.get("filename", ""),
                size=attachment.get("size", 0),
                mime_type=attachment.get("mimeType", ""),
                created=attachment.get("created", ""),
                author=attachment.get("author", {}).get("displayName", "Unknown"),
                download_url=attachment.get("content", "")
            )
            attachments.append(jira_attachment)
        
        return attachments
    
    def _extract_issue_links(self, issue_data: Dict) -> List[JiraIssueLink]:
        """핵심 이슈 링크만 추출"""
        issue_links = []
        
        link_data = issue_data.get("fields", {}).get("issuelinks", [])
        
        # 핵심 링크 유형만 처리
        important_link_types = {
            "blocks", "is blocked by", "relates to", "duplicates", 
            "is duplicated by", "causes", "is caused by"
        }
        
        for link in link_data:
            link_type = link.get("type", {}).get("name", "").lower()
            
            if link_type in important_link_types:
                jira_link = JiraIssueLink(
                    id=link.get("id", ""),
                    type=link_type,
                    inward_issue=link.get("inwardIssue", {}).get("key"),
                    outward_issue=link.get("outwardIssue", {}).get("key"),
                    description=link.get("type", {}).get("inward") or link.get("type", {}).get("outward")
                )
                issue_links.append(jira_link)
        
        return issue_links
    
    def _create_embedding_text(self, summary: str, description: str, recent_comments: List[str]) -> str:
        """임베딩용 텍스트 생성 (품질과 비용 최적화)"""
        parts = []
        
        # Summary (항상 포함)
        if summary.strip():
            parts.append(f"제목: {summary}")
        
        # Description (있는 경우)
        if description.strip():
            # HTML 정제 적용
            if self.enable_html_cleaning and self.html_cleaner:
                cleaned_desc = self.html_cleaner.clean_html_to_text(description)
                # 정제 후에도 길이 제한 적용
                if len(cleaned_desc) > 1500:
                    cleaned_desc = cleaned_desc[:1500] + "..."
                desc = cleaned_desc
            else:
                # HTML 정제기가 없는 경우 기존 방식
                desc = description[:1000] + "..." if len(description) > 1000 else description
            
            if desc.strip():
                parts.append(f"설명: {desc}")
        
        # 최근 댓글 3개 (HTML 정제 적용)
        if recent_comments:
            cleaned_comments = []
            for comment in recent_comments:
                if self.enable_html_cleaning and self.html_cleaner:
                    cleaned_comment = self.html_cleaner.clean_html_to_text(comment)
                    # 댓글은 300자로 제한
                    if len(cleaned_comment) > 300:
                        cleaned_comment = cleaned_comment[:300] + "..."
                    cleaned_comments.append(cleaned_comment)
                else:
                    # HTML 정제기가 없는 경우 기존 방식
                    cleaned_comments.append(comment[:300])
            
            if cleaned_comments:
                comments_text = "\n".join([f"댓글: {comment}" for comment in cleaned_comments])
                parts.append(f"최근 댓글:\n{comments_text}")
        
        return "\n\n".join(parts)
    
    def process_issue(self, issue_data: Dict, extract_attachments_content: bool = False) -> ProcessedJiraIssue:
        """단일 이슈 데이터 정제"""
        # JIRA API v2의 복잡한 데이터 구조 처리
        def safe_get_field(field_name: str, default=""):
            """다양한 섹션에서 필드 값을 안전하게 추출"""
            # 1. renderedFields에서 찾기
            rendered_fields = issue_data.get("renderedFields", {})
            if field_name in rendered_fields and rendered_fields[field_name] is not None:
                return rendered_fields[field_name]
            
            # 2. fields에서 찾기
            fields = issue_data.get("fields", {})
            if field_name in fields and fields[field_name] is not None:
                return fields[field_name]
            
            # 3. versionedRepresentations에서 찾기
            versioned = issue_data.get("versionedRepresentations", {})
            if field_name in versioned and "1" in versioned[field_name]:
                value = versioned[field_name]["1"]
                if value is not None:
                    return value
            
            return default
        
        def safe_get_complex_field(field_name: str, sub_field: str = None):
            """복잡한 객체 필드를 안전하게 추출"""
            # renderedFields에서 시도
            rendered_fields = issue_data.get("renderedFields", {})
            field_value = rendered_fields.get(field_name)
            if field_value and isinstance(field_value, dict) and sub_field:
                return field_value.get(sub_field, "")
            elif field_value and not sub_field:
                return field_value
            
            # fields에서 시도
            fields = issue_data.get("fields", {})
            field_value = fields.get(field_name)
            if field_value and isinstance(field_value, dict) and sub_field:
                return field_value.get(sub_field, "")
            elif field_value and not sub_field:
                return field_value
            
            # versionedRepresentations에서 시도
            versioned = issue_data.get("versionedRepresentations", {})
            if field_name in versioned and "1" in versioned[field_name]:
                field_value = versioned[field_name]["1"]
                if isinstance(field_value, dict) and sub_field:
                    return field_value.get(sub_field, "")
                elif field_value:
                    return field_value
                    
            return "" if sub_field else {}
        
        # 기본 정보
        issue_id = issue_data.get("id", "")
        issue_key = issue_data.get("key", "")
        summary = safe_get_field("summary", "")
        description = safe_get_field("description", "")
        
        # 상태 및 우선순위 (복잡한 객체)
        status_obj = safe_get_complex_field("status")
        status_name = ""
        if isinstance(status_obj, dict):
            status_name = status_obj.get("name", "")
        elif isinstance(status_obj, str):
            status_name = status_obj
        status = self._normalize_status(status_name)
        
        priority_obj = safe_get_complex_field("priority")
        priority_name = ""
        if isinstance(priority_obj, dict):
            priority_name = priority_obj.get("name", "")
        elif isinstance(priority_obj, str):
            priority_name = priority_obj
        priority = self._normalize_priority(priority_name)
        
        # 시간 정보
        created = safe_get_field("created", "")
        updated = safe_get_field("updated", "")
        resolved = safe_get_field("resolutiondate")
        
        # 담당자 정보
        assignee_obj = safe_get_complex_field("assignee")
        assignee = None
        if isinstance(assignee_obj, dict):
            assignee = assignee_obj.get("displayName")
        elif isinstance(assignee_obj, str):
            assignee = assignee_obj
            
        reporter_obj = safe_get_complex_field("reporter")
        reporter = ""
        if isinstance(reporter_obj, dict):
            reporter = reporter_obj.get("displayName", "")
        elif isinstance(reporter_obj, str):
            reporter = reporter_obj
        
        # 프로젝트 정보
        project_obj = safe_get_complex_field("project")
        project_key = ""
        project_name = ""
        if isinstance(project_obj, dict):
            project_key = project_obj.get("key", "")
            project_name = project_obj.get("name", "")
        
        # 이슈 타입
        issuetype_obj = safe_get_complex_field("issuetype")
        issue_type = ""
        if isinstance(issuetype_obj, dict):
            issue_type = issuetype_obj.get("name", "")
        elif isinstance(issuetype_obj, str):
            issue_type = issuetype_obj
        
        # 댓글 추출
        comments, recent_comments_text = self._extract_comments(issue_data)
        
        # 첨부파일 메타데이터
        attachments = self._extract_attachments(issue_data)
        
        # 이슈 링크
        issue_links = self._extract_issue_links(issue_data)
        
        # 임베딩용 텍스트 생성
        embedding_text = self._create_embedding_text(summary, description, recent_comments_text)
        
        return ProcessedJiraIssue(
            id=issue_id,
            key=issue_key,
            embedding_text=embedding_text,
            summary=summary,
            description=description,
            issue_type=issue_type,
            status=status,
            priority=priority,
            created=created,
            updated=updated,
            resolved=resolved,
            assignee=assignee,
            reporter=reporter,
            project_key=project_key,
            project_name=project_name,
            comments=comments,
            recent_comments_for_embedding=recent_comments_text,
            attachments=attachments,
            issue_links=issue_links,
            raw_data_available=True
        )
    
    def fetch_and_process_issue(self, issue_key: str) -> ProcessedJiraIssue:
        """이슈 키로 데이터 가져와서 정제"""
        # URL 정리 (테스트에서 성공한 패턴 사용)
        if self.endpoint.endswith('/rest/api/2/'):
            url = f"{self.endpoint}issue/{issue_key}"
        elif self.endpoint.endswith('/rest/api/2'):
            url = f"{self.endpoint}/issue/{issue_key}"
        else:
            base_url = self.endpoint.rstrip('/')
            url = f"{base_url}/rest/api/2/issue/{issue_key}"
        
        # 모든 필드 요청 (디버깅용)
        params = {
            "expand": "renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations",
            "fields": "*all"
        }
        
        issue_data = self._make_request(url, params)
        return self.process_issue(issue_data)
    
    def fetch_and_process_issues_by_jql(self, 
                                       jql: str, 
                                       max_results: int = 100,
                                       start_at: int = 0) -> List[ProcessedJiraIssue]:
        """JQL로 이슈들 가져와서 정제"""
        # URL 정리 (테스트에서 성공한 패턴 사용)
        if self.endpoint.endswith('/rest/api/2/'):
            url = f"{self.endpoint}search"
        elif self.endpoint.endswith('/rest/api/2'):
            url = f"{self.endpoint}/search"
        else:
            base_url = self.endpoint.rstrip('/')
            url = f"{base_url}/rest/api/2/search"
        
        params = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
            "expand": "renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations",
            "fields": "*all"
        }
        
        search_result = self._make_request(url, params)
        issues = search_result.get("issues", [])
        
        processed_issues = []
        for issue_data in issues:
            try:
                processed_issue = self.process_issue(issue_data)
                processed_issues.append(processed_issue)
            except Exception as e:
                logger.error(f"이슈 처리 실패 {issue_data.get('key', 'Unknown')}: {e}")
                continue
        
        logger.info(f"JQL 처리 완료: {len(processed_issues)}개 이슈")
        return processed_issues
    
    def fetch_updated_issues_since(self, 
                                  since_date: datetime, 
                                  project_key: Optional[str] = None) -> List[ProcessedJiraIssue]:
        """특정 날짜 이후 업데이트된 이슈들 가져오기 (증분 처리용)"""
        since_str = since_date.strftime("%Y-%m-%d %H:%M")
        
        jql = f"updated >= '{since_str}'"
        if project_key:
            jql += f" AND project = {project_key}"
        
        # updated 기준으로 정렬
        jql += " ORDER BY updated ASC"
        
        return self.fetch_and_process_issues_by_jql(jql)


# 테스트 및 사용 예시
def test_jira_processor():
    """JIRA 프로세서 테스트"""
    try:
        processor = JiraAPIProcessor()
        
        # 특정 이슈 처리 테스트
        test_issue_key = "TEST-1"  # 실제 이슈 키로 변경
        
        try:
            issue = processor.fetch_and_process_issue(test_issue_key)
            print(f"✅ 이슈 처리 성공: {issue.key}")
            print(f"   제목: {issue.summary}")
            print(f"   상태: {issue.status.value}")
            print(f"   임베딩 텍스트 길이: {len(issue.embedding_text)} 문자")
            print(f"   댓글 수: {len(issue.comments)}")
            print(f"   첨부파일 수: {len(issue.attachments)}")
            
        except Exception as e:
            print(f"❌ 단일 이슈 테스트 실패: {e}")
        
        # 최근 업데이트 이슈들 처리 테스트
        try:
            since_date = datetime.now() - timedelta(days=7)  # 7일 전부터
            recent_issues = processor.fetch_updated_issues_since(since_date)
            print(f"✅ 최근 업데이트 이슈 처리: {len(recent_issues)}개")
            
        except Exception as e:
            print(f"❌ 최근 이슈 테스트 실패: {e}")
            
    except Exception as e:
        print(f"❌ JIRA 프로세서 초기화 실패: {e}")
        print("환경변수를 확인하세요: JIRA_API_TOKEN, JIRA_API_ENDPOINT, JIRA_EMAIL")


if __name__ == "__main__":
    test_jira_processor()