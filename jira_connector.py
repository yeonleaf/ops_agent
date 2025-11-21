#!/usr/bin/env python3
"""
Jira 연동 모듈

Jira API를 통해 티켓 데이터를 가져와서 벡터 DB에 동기화하는 기능을 제공합니다.
"""

import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from jira import JIRA
from jira.exceptions import JIRAError
import hashlib
from dotenv import load_dotenv

# Rate limiting 및 backoff 전략을 위한 패키지들
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from ratelimit import limits, sleep_and_retry
    TENACITY_AVAILABLE = True
    RATELIMIT_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    RATELIMIT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ tenacity 또는 ratelimit 패키지가 설치되지 않았습니다. 기본 retry 로직을 사용합니다.")

# 로깅 설정
def setup_jira_logging():
    """Jira 관련 로깅 설정"""
    # 로그 디렉토리 생성
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 현재 시간으로 로그 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"jira_sync_{timestamp}.log")
    
    # 로거 설정
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 파일 핸들러 (상세 로그)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 콘솔 핸들러 (요약 로그)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 포맷터 설정
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    file_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"📝 Jira 로깅 시작: {log_file}")
    return logger

# 로거 초기화
logger = setup_jira_logging()

class JiraConnector:
    """Jira 연동 및 데이터 동기화 관리자"""
    
    def __init__(self, url: str = None, email: str = None, token: str = None):
        """
        JiraConnector 초기화

        Args:
            url: Jira 서버 URL (예: https://your-domain.atlassian.net)
            email: Jira 계정 이메일 (Bearer token 방식에서는 사용 안 함)
            token: Jira API Bearer 토큰

        Note:
            인자가 제공되지 않으면 .env 파일에서 자동으로 읽어옵니다.
            Bearer Token 인증 방식을 사용합니다.
        """
        # .env 파일 로드
        load_dotenv()

        # 환경 변수에서 Jira 설정 읽기
        self.url = url or os.getenv('JIRA_ENDPOINT', '').replace('/rest/api/3/', '').replace('/rest/api/2/', '')
        self.email = email or os.getenv('JIRA_ACCOUNT')  # Bearer token에서는 불필요
        self.token = token or os.getenv('JIRA_TOKEN')

        # 설정 검증 (Bearer token 방식에서는 URL과 토큰만 필요)
        if not all([self.url, self.token]):
            raise ValueError(
                "Jira 설정이 완전하지 않습니다. "
                "URL과 토큰을 직접 제공하거나 .env 파일에 설정해주세요."
            )

        # URL 정리 (끝의 슬래시 제거)
        self.url = self.url.rstrip('/')

        # API 토큰 형식 검증
        if not self._validate_api_token(self.token):
            logger.warning("⚠️ API 토큰 형식이 예상과 다릅니다. 인증이 실패할 수 있습니다.")

        logger.info(f"🔗 Jira 설정 로드 완료: {self.url}")
        logger.info(f"🔐 인증 방식: Bearer Token")

        # Jira 클라이언트 초기화 (Bearer Token 방식)
        try:
            logger.info(f"🔗 Jira 서버에 연결 시도: {self.url}")
            logger.info(f"🔑 API 토큰 길이: {len(self.token) if self.token else 0}자")

            self.jira = JIRA(
                server=self.url,
                token_auth=self.token,
                options={'verify': True}  # SSL 인증서 검증
            )
            
            # 연결 테스트 및 서버 정보 확인
            try:
                server_info = self.jira.server_info()
                logger.info(f"✅ Jira 클라이언트 초기화 성공: {self.url}")
                logger.info(f"📊 서버 정보: {server_info.get('serverTitle', 'Unknown')}")
                logger.info(f"📊 서버 버전: {server_info.get('version', 'Unknown')}")
                logger.info(f"📊 빌드 번호: {server_info.get('buildNumber', 'Unknown')}")
                logger.info(f"📊 서버 시간: {server_info.get('serverTime', 'Unknown')}")
                
            except Exception as info_error:
                logger.warning(f"⚠️ 서버 정보 조회 실패 (연결은 성공): {info_error}")
                logger.info(f"✅ Jira 클라이언트 초기화 성공: {self.url}")
                
        except JIRAError as e:
            # 오류 상세 정보 로깅
            self._log_error_details(e, "클라이언트 초기화")
            
            # 인증 오류 상세 분석
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.error("🔐 인증 오류 (HTTP 401) - 가능한 원인:")
                logger.error("  1. Bearer API 토큰이 만료되었거나 잘못됨")
                logger.error("  2. 토큰 형식이 올바르지 않음")
                logger.error("  3. Jira 계정에 API 접근 권한이 없음")
                logger.error("  4. 해당 Jira 인스턴스에 대한 접근 권한이 없음")

                # 사용자 친화적인 오류 메시지
                raise ValueError(
                    "Jira 인증에 실패했습니다. 다음을 확인해주세요:\n"
                    "1. Bearer API 토큰이 유효한지 확인\n"
                    "2. 토큰이 올바른 형식인지 확인\n"
                    "3. Jira 계정에 API 접근 권한이 있는지 확인\n"
                    "4. 해당 프로젝트에 대한 접근 권한이 있는지 확인"
                )
            else:
                raise
        
        # SQLite DB 초기화
        self._init_sqlite_db()
        
        # 벡터 DB 매니저 초기화
        self._init_vector_db()
        
        # Rate limiting 설정
        self._setup_rate_limiting()
        
        # Backoff 설정
        self._setup_backoff_strategy()
    
    def _setup_rate_limiting(self):
        """Rate limiting 설정"""
        if RATELIMIT_AVAILABLE:
            # Jira Cloud: 분당 1000개 요청, 분당 100개 검색 요청
            # Jira Server: 분당 1000개 요청
            self.rate_limited_search = limits(calls=100, period=60)(self._raw_search_issues)
            self.rate_limited_get_issue = limits(calls=1000, period=60)(self._raw_get_issue)
            logger.info("✅ Rate limiting 설정 완료 (검색: 100/분, 일반: 1000/분)")
        else:
            # 기본 rate limiting (수동 구현)
            self.rate_limited_search = self._manual_rate_limited_search
            self.rate_limited_get_issue = self._manual_rate_limited_get_issue
            logger.info("⚠️ 기본 rate limiting 사용 (수동 구현)")
    
    def _setup_backoff_strategy(self):
        """Backoff 전략 설정"""
        if TENACITY_AVAILABLE:
            # 429 에러에 대한 exponential backoff
            self.retry_with_backoff = retry(
                stop=stop_after_attempt(5),
                wait=wait_exponential(multiplier=1, min=4, max=60),
                retry=retry_if_exception_type((JIRAError, ConnectionError, TimeoutError)),
                before_sleep=lambda retry_state: logger.warning(
                    f"🔄 재시도 {retry_state.attempt_number}/5 - "
                    f"대기 시간: {retry_state.next_action.sleep}초"
                )
            )
            logger.info("✅ Exponential backoff 전략 설정 완료 (최대 5회 재시도)")
        else:
            # 기본 retry 로직
            self.retry_with_backoff = self._manual_retry_with_backoff
            logger.info("⚠️ 기본 retry 로직 사용 (수동 구현)")
    
    def _retry_wrapper(self, func, *args, **kwargs):
        """tenacity retry를 위한 래퍼 함수"""
        if TENACITY_AVAILABLE:
            return self.retry_with_backoff(func)(*args, **kwargs)
        else:
            return self._manual_retry_with_backoff(func, *args, **kwargs)
    
    def _manual_rate_limited_search(self, *args, **kwargs):
        """수동 rate limiting을 적용한 검색"""
        time.sleep(0.6)  # 100/분 = 0.6초 간격
        return self._raw_search_issues(*args, **kwargs)
    
    def _manual_rate_limited_get_issue(self, *args, **kwargs):
        """수동 rate limiting을 적용한 티켓 조회"""
        time.sleep(0.06)  # 1000/분 = 0.06초 간격
        return self._raw_get_issue(*args, **kwargs)
    
    def _manual_retry_with_backoff(self, func, *args, **kwargs):
        """수동 retry 로직"""
        max_attempts = 5
        base_delay = 1
        
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except JIRAError as e:
                if "429" in str(e) and attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)  # exponential backoff
                    logger.warning(f"🔄 429 에러 발생, {delay}초 후 재시도 ({attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue
                else:
                    raise
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"🔄 연결 오류, {delay}초 후 재시도 ({attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue
                else:
                    raise
    
    def _log_response_details(self, response, operation: str):
        """응답 객체의 상세 정보를 로그에 기록"""
        try:
            logger.info(f"📊 {operation} 응답 상세 정보:")
            logger.info(f"  - 응답 타입: {type(response)}")
            
            if hasattr(response, 'total'):
                logger.info(f"  - 총 이슈 수: {response.total}")
            if hasattr(response, 'maxResults'):
                logger.info(f"  - 최대 결과 수: {response.maxResults}")
            if hasattr(response, 'startAt'):
                logger.info(f"  - 시작 위치: {response.startAt}")
            if hasattr(response, '__len__'):
                logger.info(f"  - 실제 반환된 이슈 수: {len(response)}")
            
            # 응답 객체의 모든 속성 로깅
            if hasattr(response, '__dict__'):
                logger.info(f"  - 응답 객체 속성: {list(response.__dict__.keys())}")
            
        except Exception as log_error:
            logger.warning(f"⚠️ 응답 상세 정보 로깅 실패: {log_error}")
    
    def _log_error_details(self, error, operation: str):
        """오류 객체의 상세 정보를 로그에 기록"""
        try:
            logger.error(f"❌ {operation} 오류 상세 정보:")
            logger.error(f"  - 오류 타입: {type(error)}")
            logger.error(f"  - 오류 메시지: {str(error)}")
            
            # Jira API 응답 상세 정보 로깅
            if hasattr(error, 'status_code'):
                logger.error(f"  - HTTP 상태 코드: {error.status_code}")
            if hasattr(error, 'text'):
                logger.error(f"  - 응답 본문: {error.text}")
                # 응답 본문을 별도 파일에 저장
                self._save_error_response(error.text, operation)
            if hasattr(error, 'url'):
                logger.error(f"  - 요청 URL: {error.url}")
            if hasattr(error, 'headers'):
                logger.error(f"  - 응답 헤더: {dict(error.headers)}")
            if hasattr(error, 'response'):
                logger.error(f"  - 응답 객체: {error.response}")
                
        except Exception as log_error:
            logger.warning(f"⚠️ 오류 상세 정보 로깅 실패: {log_error}")
    
    def _save_error_response(self, response_text: str, operation: str):
        """오류 응답 본문을 별도 파일에 저장"""
        try:
            # 오류 응답 저장 디렉토리 생성
            error_dir = "logs/error_responses"
            if not os.path.exists(error_dir):
                os.makedirs(error_dir)
            
            # 현재 시간으로 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jira_error_{operation}_{timestamp}.txt"
            filepath = os.path.join(error_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Jira API 오류 응답 - {operation}\n")
                f.write(f"시간: {datetime.now().isoformat()}\n")
                f.write(f"=" * 50 + "\n")
                f.write(response_text)
            
            logger.info(f"📁 오류 응답 본문 저장됨: {filepath}")
            
        except Exception as save_error:
            logger.warning(f"⚠️ 오류 응답 저장 실패: {save_error}")
    
    def _create_safe_jql_query(self, base_query: str, project_key: str = None) -> str:
        """
        Jira에서 허용되는 안전한 JQL 쿼리 생성
        
        Args:
            base_query: 기본 쿼리 (예: "ORDER BY updated DESC")
            project_key: 프로젝트 키 (선택사항)
            
        Returns:
            안전한 JQL 쿼리
        """
        # 기본 제한 조건들
        safe_conditions = [
            "status != Closed",  # 닫히지 않은 이슈
            "status in (Open, 'In Progress', Reopened)",  # 활성 상태의 이슈
            "priority in (High, Medium, Low)",  # 우선순위가 있는 이슈
            "assignee is not EMPTY",  # 담당자가 있는 이슈
            "reporter is not EMPTY",  # 보고자가 있는 이슈
            "created >= -30d",  # 최근 30일 내 생성
            "updated >= -7d"  # 최근 7일 내 업데이트
        ]
        
        # 프로젝트 제한 추가
        if project_key:
            safe_conditions.insert(0, f"project = {project_key}")
        
        # 기본 쿼리에 제한 조건 추가
        if "ORDER BY" in base_query:
            # ORDER BY 앞에 제한 조건 삽입
            order_part = base_query.split("ORDER BY")[1]
            safe_query = f"{safe_conditions[0]} ORDER BY{order_part}"
        else:
            safe_query = f"{safe_conditions[0]} {base_query}"
        
        logger.info(f"🔒 안전한 JQL 쿼리 생성: {safe_query}")
        return safe_query
    
    def _raw_search_issues(self, *args, **kwargs):
        """실제 Jira 검색 API 호출 (rate limiting 적용 전)"""
        try:
            logger.info(f"🔍 Jira 검색 API 호출 시작: {args}, {kwargs}")
            response = self.jira.search_issues(*args, **kwargs)
            
            # 응답 상세 정보 로깅
            self._log_response_details(response, "검색 API")
            
            return response
            
        except Exception as e:
            # 오류 상세 정보 로깅
            self._log_error_details(e, "검색 API")
            raise
    
    def _raw_get_issue(self, *args, **kwargs):
        """실제 Jira 티켓 조회 API 호출 (rate limiting 적용 전)"""
        try:
            logger.info(f"🔍 Jira 티켓 조회 API 호출 시작: {args}, {kwargs}")
            response = self.jira.issue(*args, **kwargs)
            
            # 응답 상세 정보 로깅
            self._log_response_details(response, "티켓 조회 API")
            
            return response
            
        except Exception as e:
            # 오류 상세 정보 로깅
            self._log_error_details(e, "티켓 조회 API")
            raise
    
    def _validate_api_token(self, token: str) -> bool:
        """
        API 토큰 형식 검증
        
        Args:
            token: 검증할 API 토큰
            
        Returns:
            유효한 형식이면 True, 아니면 False
        """
        if not token:
            return False
        
        # Atlassian API 토큰은 보통 24자 이상의 영숫자 조합
        if len(token) < 20:
            return False
        
        # 특수문자가 포함되어 있을 수 있음 (+, /, = 등)
        # 기본적인 형식 검증만 수행
        return True
    
    def _init_sqlite_db(self):
        """SQLite DB 초기화 및 테이블 생성"""
        try:
            self.db_path = "jira_sync.db"
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            
            # 동기화 정보 테이블 생성
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_info (
                    id INTEGER PRIMARY KEY,
                    last_sync_time TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 초기 데이터 삽입 (최초 실행 시)
            self.cursor.execute("SELECT COUNT(*) FROM sync_info")
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute("""
                    INSERT INTO sync_info (last_sync_time, created_at, updated_at)
                    VALUES (?, ?, ?)
                """, ('1900-01-01 00:00:00', datetime.now().isoformat(), datetime.now().isoformat()))
                self.conn.commit()
                logger.info("✅ SQLite DB 초기화 완료")
            
            self.conn.commit()
            logger.info("✅ SQLite DB 연결 성공")
            
        except Exception as e:
            logger.error(f"❌ SQLite DB 초기화 실패: {e}")
            raise
    
    def _init_vector_db(self):
        """벡터 DB 매니저 초기화"""
        try:
            from vector_db_models import SystemInfoVectorDBManager
            
            # jira_info 컬렉션을 위한 별도 벡터DB 매니저
            self.vector_db = SystemInfoVectorDBManager()
            
            # jira_info 컬렉션으로 변경
            self.vector_db.collection_name = "jira_info"
            self.vector_db.collection = self.vector_db._get_or_create_collection()
            
            logger.info("✅ 벡터 DB 매니저 초기화 성공")
            
        except Exception as e:
            logger.error(f"❌ 벡터 DB 매니저 초기화 실패: {e}")
            raise
    
    def get_last_sync_time(self) -> str:
        """
        SQLite DB에 저장된 'last_sync_time'을 조회
        
        Returns:
            마지막 동기화 시각 (ISO 형식 문자열)
        """
        try:
            self.cursor.execute("SELECT last_sync_time FROM sync_info ORDER BY id DESC LIMIT 1")
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            else:
                return '1900-01-01 00:00:00'
                
        except Exception as e:
            logger.error(f"❌ 마지막 동기화 시각 조회 실패: {e}")
            return '1900-01-01 00:00:00'
    
    def fetch_updated_tickets(self, since: str) -> List[Dict[str, Any]]:
        """
        since 시각 이후로 업데이트된 모든 Jira 티켓을 JQL로 조회
        
        Args:
            since: 시작 시각 (ISO 형식 문자열)
            
        Returns:
            Jira 티켓 객체 리스트
        """
        try:
            # 1. 먼저 간단한 쿼리로 전체 이슈 수 확인 (제한 조건 추가)
            logger.info("🔍 1단계: 전체 이슈 수 확인")
            try:
                # 안전한 JQL 쿼리 생성 및 사용
                safe_query = self._create_safe_jql_query("ORDER BY updated DESC")
                total_issues = self._retry_wrapper(
                    self.rate_limited_search,
                    safe_query,
                    maxResults=1,
                    fields='key'
                )
                if total_issues and hasattr(total_issues, 'total'):
                    logger.info(f"📊 전체 이슈 수 (닫히지 않은 것만): {total_issues.total}")
                else:
                    logger.warning("⚠️ 전체 이슈 수를 확인할 수 없습니다")
            except Exception as e:
                logger.warning(f"⚠️ 전체 이슈 수 확인 실패: {e}")
                # 더 제한적인 쿼리 시도
                try:
                    safe_query = self._create_safe_jql_query("ORDER BY updated DESC")
                    total_issues = self._retry_wrapper(
                        self.rate_limited_search,
                        safe_query,
                        maxResults=1,
                        fields='key'
                    )
                    if total_issues and hasattr(total_issues, 'total'):
                        logger.info(f"📊 전체 이슈 수 (안전한 쿼리): {total_issues.total}")
                except Exception as e2:
                    logger.warning(f"⚠️ 대안 쿼리도 실패: {e2}")
            
            # 2. 프로젝트별 이슈 확인 (제한 조건 추가)
            logger.info("🔍 2단계: 프로젝트별 이슈 확인")
            try:
                # 모든 프로젝트 조회
                projects = self.jira.projects()
                logger.info(f"📊 접근 가능한 프로젝트 수: {len(projects)}")
                
                for project in projects[:5]:  # 처음 5개만 확인
                    try:
                        # 안전한 프로젝트별 JQL 쿼리 생성 및 사용
                        safe_query = self._create_safe_jql_query("ORDER BY updated DESC", project.key)
                        project_issues = self._retry_wrapper(
                            self.rate_limited_search,
                            safe_query,
                            maxResults=5,
                            fields='key,summary'
                        )
                        if project_issues and hasattr(project_issues, 'total'):
                            logger.info(f"📊 프로젝트 {project.key}: {project_issues.total}개 이슈 (닫히지 않은 것만)")
                        else:
                            logger.info(f"📊 프로젝트 {project.key}: 이슈 없음")
                    except Exception as e:
                        logger.warning(f"⚠️ 프로젝트 {project.key} 이슈 조회 실패: {e}")
                        # 더 제한적인 쿼리 시도
                        try:
                            safe_query = self._create_safe_jql_query("ORDER BY updated DESC", project.key)
                            project_issues = self._retry_wrapper(
                                self.rate_limited_search,
                                safe_query,
                                maxResults=5,
                                fields='key,summary'
                            )
                            if project_issues and hasattr(project_issues, 'total'):
                                logger.info(f"📊 프로젝트 {project.key}: {project_issues.total}개 이슈 (안전한 쿼리)")
                        except Exception as e2:
                            logger.warning(f"⚠️ 프로젝트 {project.key} 대안 쿼리도 실패: {e2}")
                        
            except Exception as e:
                logger.warning(f"⚠️ 프로젝트 조회 실패: {e}")
            
            # 3. 메인 JQL 쿼리 실행 (개선된 버전)
            logger.info("🔍 3단계: 메인 JQL 쿼리 실행")
            
            # 날짜가 너무 오래된 경우 최근 1년으로 제한
            if since == '1900-01-01 00:00:00':
                from datetime import datetime, timedelta
                one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                jql_query = f'updated >= "{one_year_ago}" ORDER BY updated DESC'
                logger.info(f"📅 날짜가 너무 오래되어 최근 1년으로 제한: {jql_query}")
            else:
                jql_query = f'updated >= "{since}" ORDER BY updated DESC'
            
            logger.info(f"🔍 JQL 쿼리 실행: {jql_query}")
            
            # Rate limiting과 backoff를 적용한 티켓 조회
            try:
                issues = self._retry_wrapper(
                    self.rate_limited_search,
                    jql_query,
                    maxResults=1000,  # 최대 1000개
                    fields='summary,description,status,priority,assignee,reporter,created,updated,comment'
                )
                
                # 응답 객체 상세 정보 로깅
                logger.info(f"📊 Jira API 응답 객체 타입: {type(issues)}")
                if hasattr(issues, 'total'):
                    logger.info(f"📊 총 이슈 수: {issues.total}")
                if hasattr(issues, 'maxResults'):
                    logger.info(f"📊 최대 결과 수: {issues.maxResults}")
                if hasattr(issues, 'startAt'):
                    logger.info(f"📊 시작 위치: {issues.startAt}")
                if hasattr(issues, '__len__'):
                    logger.info(f"📊 실제 반환된 이슈 수: {len(issues)}")
                
                # 4. 결과가 0개인 경우 추가 진단
                if issues and hasattr(issues, 'total') and issues.total == 0:
                    logger.warning("⚠️ 검색 결과가 0개입니다. 추가 진단을 시작합니다.")
                    
                    # 다양한 JQL 쿼리 시도 (제한 조건 추가)
                    alternative_queries = [
                        "status != Closed ORDER BY created DESC",  # 닫히지 않은 이슈, 생성일 기준
                        "status != Closed ORDER BY updated DESC",  # 닫히지 않은 이슈, 업데이트 기준
                        "priority in (High, Medium, Low) ORDER BY updated DESC",  # 우선순위가 있는 이슈
                        "assignee is not EMPTY ORDER BY updated DESC",  # 담당자가 있는 이슈
                        "created >= -30d ORDER BY updated DESC",  # 최근 30일 내 생성된 이슈
                        "updated >= -7d ORDER BY updated DESC"  # 최근 7일 내 업데이트된 이슈
                    ]
                    
                    for i, alt_query in enumerate(alternative_queries, 1):
                        try:
                            logger.info(f"🔍 대안 쿼리 {i} 시도: {alt_query}")
                            alt_issues = self._retry_wrapper(
                                self.rate_limited_search,
                                alt_query,
                                maxResults=10,
                                fields='key,summary'
                            )
                            if alt_issues and hasattr(alt_issues, 'total') and alt_issues.total > 0:
                                logger.info(f"✅ 대안 쿼리 {i} 성공: {alt_issues.total}개 이슈 발견")
                                # 이 쿼리로 메인 검색 실행
                                issues = self._retry_wrapper(
                                    self.rate_limited_search,
                                    alt_query,
                                    maxResults=1000,
                                    fields='summary,description,status,priority,assignee,reporter,created,updated,comment'
                                )
                                break
                            else:
                                logger.info(f"⚠️ 대안 쿼리 {i}: 0개 이슈")
                        except Exception as e:
                            logger.warning(f"⚠️ 대안 쿼리 {i} 실패: {e}")
                
            except Exception as e:
                logger.error(f"❌ Jira API 검색 실패: {e}")
                logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
                return []
            
            tickets = []
            if issues and hasattr(issues, '__iter__'):
                for issue in issues:
                    try:
                        ticket_data = {
                            'key': issue.key,
                            'summary': issue.fields.summary or '',
                            'description': issue.fields.description or '',
                            'status': issue.fields.status.name if issue.fields.status else 'Unknown',
                            'priority': issue.fields.priority.name if issue.fields.priority else 'Unknown',
                            'assignee': issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned',
                            'reporter': issue.fields.reporter.displayName if issue.fields.reporter else 'Unknown',
                            'created': issue.fields.created,
                            'updated': issue.fields.updated,
                            'comments': []
                        }
                        
                        # 최신 코멘트 3개 추출
                        if hasattr(issue.fields, 'comment') and issue.fields.comment.comments:
                            comments = sorted(issue.fields.comment.comments, key=lambda x: x.created, reverse=True)
                            for comment in comments[:3]:
                                ticket_data['comments'].append({
                                    'author': comment.author.displayName,
                                    'body': comment.body,
                                    'created': comment.created
                                })
                        
                        tickets.append(ticket_data)
                    except Exception as e:
                        logger.warning(f"⚠️ 티켓 데이터 처리 중 오류 발생, 건너뛰기: {e}")
                        continue
            else:
                logger.warning("⚠️ Jira API에서 유효한 응답을 받지 못했습니다")
                return []
            
            logger.info(f"✅ {len(tickets)}개의 업데이트된 티켓 조회 완료")
            return tickets
            
        except JIRAError as e:
            error_msg = str(e)
            if "429" in error_msg:
                logger.error(f"❌ Rate Limit 초과 (HTTP 429): {error_msg}")
                logger.warning("💡 Jira API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.")
                logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
                return []
            elif "401" in error_msg:
                logger.error(f"❌ 인증 실패 (HTTP 401): {error_msg}")
                logger.warning("💡 API 토큰이나 이메일 주소를 확인해주세요.")
                logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
                return []
            elif "403" in error_msg:
                logger.error(f"❌ 권한 부족 (HTTP 403): {error_msg}")
                logger.warning("💡 Jira 프로젝트에 대한 접근 권한이 있는지 확인해주세요.")
                logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
                return []
            else:
                logger.error(f"❌ Jira API 오류: {error_msg}")
                logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
                return []
        except Exception as e:
            logger.error(f"❌ 티켓 조회 중 예상치 못한 오류: {e}")
            logger.warning("⚠️ 빈 리스트 반환하여 동기화 계속 진행")
            return []
    
    def upsert_tickets_to_vector_db(self, tickets: List[Dict[str, Any]]) -> int:
        """
        Jira 티켓 객체 리스트를 벡터 DB에 적재
        
        Args:
            tickets: Jira 티켓 객체 리스트
            
        Returns:
            처리된 티켓 개수
        """
        try:
            if not tickets:
                logger.info("ℹ️ 처리할 티켓이 없습니다.")
                return 0
                
            processed_count = 0
            
            for i, ticket in enumerate(tickets):
                try:
                    # Rate limiting: 일정 간격으로 처리
                    if i > 0 and i % 10 == 0:  # 10개마다 잠시 대기
                        logger.info(f"⏳ Rate limiting: {i}개 티켓 처리 후 잠시 대기...")
                        time.sleep(1)  # 1초 대기
                    
                    # 임베딩할 텍스트 생성
                    text_content = self._generate_embedding_text(ticket)
                    
                    # 티켓 ID로 기존 문서 삭제
                    self._delete_existing_ticket(ticket['key'])
                    
                    # 새 문서 추가
                    self._add_ticket_to_vector_db(ticket, text_content)
                    
                    processed_count += 1
                    logger.info(f"✅ 티켓 {ticket['key']} 처리 완료 ({i+1}/{len(tickets)})")
                    
                except Exception as e:
                    logger.error(f"❌ 티켓 {ticket.get('key', 'Unknown')} 처리 실패: {e}")
                    continue
            
            logger.info(f"✅ 총 {processed_count}개 티켓 벡터 DB 적재 완료")
            return processed_count
            
        except Exception as e:
            logger.error(f"❌ 벡터 DB 적재 중 오류: {e}")
            raise
    
    def _generate_embedding_text(self, ticket: Dict[str, Any]) -> str:
        """
        티켓 정보를 바탕으로 임베딩할 텍스트 생성
        
        Args:
            ticket: Jira 티켓 객체
            
        Returns:
            임베딩용 텍스트
        """
        text_parts = []
        
        # 요약
        if ticket['summary']:
            text_parts.append(f"요약: {ticket['summary']}")
        
        # 설명
        if ticket['description']:
            # HTML 태그 제거 (간단한 처리)
            description = ticket['description'].replace('<p>', '').replace('</p>', '\n')
            description = description.replace('<br>', '\n').replace('<br/>', '\n')
            text_parts.append(f"설명: {description}")
        
        # 최신 코멘트
        if ticket['comments']:
            text_parts.append("최신 코멘트:")
            for i, comment in enumerate(ticket['comments'], 1):
                text_parts.append(f"  {i}. {comment['author']}: {comment['body']}")
        
        # 상태 및 우선순위
        text_parts.append(f"상태: {ticket['status']}")
        text_parts.append(f"우선순위: {ticket['priority']}")
        text_parts.append(f"담당자: {ticket['assignee']}")
        text_parts.append(f"보고자: {ticket['reporter']}")
        
        return "\n".join(text_parts)
    
    def _delete_existing_ticket(self, ticket_key: str):
        """
        벡터 DB에서 기존 티켓 문서 삭제
        
        Args:
            ticket_key: Jira 티켓 키
        """
        try:
            # ticket_key로 기존 문서 검색
            results = self.vector_db.collection.get(
                where={"ticket_key": ticket_key},
                include=["ids"]
            )
            
            if results['ids']:
                # 기존 문서 삭제
                self.vector_db.collection.delete(ids=results['ids'])
                logger.info(f"🗑️ 기존 티켓 {ticket_key} 문서 삭제 완료")
                
        except Exception as e:
            logger.warning(f"⚠️ 기존 티켓 {ticket_key} 삭제 중 오류: {e}")
    
    def _add_ticket_to_vector_db(self, ticket: Dict[str, Any], text_content: str):
        """
        벡터 DB에 새 티켓 문서 추가
        
        Args:
            ticket: Jira 티켓 객체
            text_content: 임베딩할 텍스트
        """
        try:
            # 메타데이터 준비
            metadata = {
                "ticket_key": ticket['key'],
                "summary": ticket['summary'],
                "status": ticket['status'],
                "priority": ticket['priority'],
                "assignee": ticket['assignee'],
                "reporter": ticket['reporter'],
                "created": ticket['created'],
                "updated": ticket['updated'],
                "comment_count": len(ticket['comments']),
                "source": "jira",
                "sync_time": datetime.now().isoformat()
            }
            
            # 코멘트 요약 정보
            if ticket['comments']:
                comment_authors = [c['author'] for c in ticket['comments']]
                metadata["recent_commenters"] = ", ".join(comment_authors[:3])
            
            # 벡터 DB에 추가
            self.vector_db.collection.add(
                documents=[text_content],
                metadatas=[metadata],
                ids=[f"jira_{ticket['key']}_{int(datetime.now().timestamp())}"]
            )
            
            logger.info(f"✅ 티켓 {ticket['key']} 벡터 DB 추가 완료")
            
        except Exception as e:
            logger.error(f"❌ 티켓 {ticket['key']} 벡터 DB 추가 실패: {e}")
            raise
    
    def update_last_sync_time(self):
        """모든 작업 완료 후 현재 시각을 SQLite DB의 'last_sync_time'으로 업데이트"""
        try:
            current_time = datetime.now().isoformat()
            
            self.cursor.execute("""
                UPDATE sync_info 
                SET last_sync_time = ?, updated_at = ?
                WHERE id = (SELECT id FROM sync_info ORDER BY id DESC LIMIT 1)
            """, (current_time, current_time))
            
            self.conn.commit()
            logger.info(f"✅ 마지막 동기화 시각 업데이트 완료: {current_time}")
            
        except Exception as e:
            logger.error(f"❌ 마지막 동기화 시각 업데이트 실패: {e}")
            raise
    
    def sync_jira(self) -> Dict[str, Any]:
        """
        Jira 데이터 동기화 메인 함수
        
        Returns:
            동기화 결과 요약 정보
        """
        # 변수 초기화 (예외 발생 시에도 안전하게 접근 가능)
        start_time = datetime.now()
        end_time = None
        sync_duration = 0
        processed_count = 0
        tickets = []
        
        try:
            logger.info("🚀 Jira 데이터 동기화 시작")
            
            # 1. 마지막 동기화 시각 조회
            last_sync = self.get_last_sync_time()
            logger.info(f"📅 마지막 동기화: {last_sync}")
            
            # 2. 업데이트된 티켓 조회
            tickets = self.fetch_updated_tickets(last_sync)
            
            if not tickets:
                logger.info("ℹ️ 동기화할 새로운 티켓이 없습니다.")
                end_time = datetime.now()
                sync_duration = (end_time - start_time).total_seconds()
                return {
                    "success": True,
                    "message": "동기화할 새로운 티켓이 없습니다.",
                    "tickets_processed": 0,
                    "total_tickets_found": 0,
                    "sync_duration": sync_duration,
                    "last_sync_time": last_sync,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            
            # 3. 벡터 DB에 티켓 적재
            processed_count = self.upsert_tickets_to_vector_db(tickets)
            
            # 4. 마지막 동기화 시각 업데이트
            self.update_last_sync_time()
            
            # 5. 결과 요약
            end_time = datetime.now()
            sync_duration = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "message": f"✅ Jira 데이터 동기화 완료! {processed_count}개 티켓 처리",
                "tickets_processed": processed_count,
                "total_tickets_found": len(tickets) if tickets else 0,
                "sync_duration": sync_duration,
                "last_sync_time": end_time.isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            logger.info(f"🎉 Jira 동기화 완료: {processed_count}개 티켓, {sync_duration:.2f}초 소요")
            return result
            
        except Exception as e:
            logger.error(f"❌ Jira 동기화 실패: {e}")
            
            # 예외 발생 시에도 end_time과 duration 계산
            if end_time is None:
                end_time = datetime.now()
            sync_duration = (end_time - start_time).total_seconds()
            
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ Jira 동기화 실패: {str(e)}",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "sync_duration": sync_duration,
                "tickets_processed": processed_count,
                "total_tickets_found": len(tickets) if tickets else 0
            }
    
    def create_jira_issue(self, ticket_data: Dict[str, Any], project_key: str = None) -> Dict[str, Any]:
        """
        Jira에 새 이슈 생성
        
        Args:
            ticket_data: 티켓 데이터 (summary, description 등)
            project_key: Jira 프로젝트 키 (없으면 첫 번째 프로젝트 사용)
            
        Returns:
            생성 결과 (성공/실패, 생성된 이슈 키 등)
        """
        try:
            logger.info(f"🎫 Jira 이슈 생성 시작: {ticket_data.get('summary', 'Unknown')}")
            
            # 프로젝트 키가 없으면 첫 번째 프로젝트 사용
            if not project_key:
                projects = self.jira.projects()
                if not projects:
                    return {"success": False, "error": "접근 가능한 Jira 프로젝트가 없습니다."}
                project_key = projects[0].key
                logger.info(f"📁 기본 프로젝트 사용: {project_key}")
            
            # 프로젝트별 이슈 타입 조회
            project = self.jira.project(project_key)
            
            # 프로젝트에서 사용 가능한 이슈 타입 확인
            createmeta = self.jira.createmeta(projectKeys=project_key, expand='projects.issuetypes.fields')
            project_issue_types = []
            
            if createmeta.get('projects'):
                for proj in createmeta['projects']:
                    if proj['key'] == project_key:
                        project_issue_types = proj.get('issuetypes', [])
                        break
            
            logger.info(f"📋 프로젝트 {project_key}에서 사용 가능한 이슈 타입: {[it['name'] for it in project_issue_types]}")
            
            # Task, Story, Bug, Epic 순으로 사용 가능한 이슈 타입 찾기
            preferred_types = ['Task', 'Story', 'Bug', 'Epic']
            issue_type = None
            
            for pref_type in preferred_types:
                for it in project_issue_types:
                    if it['name'] == pref_type and not it.get('subtask', False):
                        issue_type = it
                        break
                if issue_type:
                    break
            
            if not issue_type and project_issue_types:
                # 서브태스크가 아닌 첫 번째 이슈 타입 사용
                for it in project_issue_types:
                    if not it.get('subtask', False):
                        issue_type = it
                        break
            
            if not issue_type:
                return {"success": False, "error": "사용 가능한 이슈 타입이 없습니다."}
            
            logger.info(f"📋 이슈 타입: {issue_type['name']}")
            
            # 이슈 필드 준비
            issue_dict = {
                'project': {'key': project_key},
                'summary': ticket_data.get('title', 'Unknown Issue'),
                'description': ticket_data.get('description', ''),
                'issuetype': {'id': issue_type['id']},
                'labels': ticket_data.get('labels', [])
            }
            
            # Start Date 설정 (duedate 필드 사용)
            if ticket_data.get('start_date'):
                try:
                    from datetime import datetime
                    # ISO 형식의 날짜를 Jira 형식(YYYY-MM-DD)으로 변환
                    if isinstance(ticket_data['start_date'], str):
                        start_date_obj = datetime.fromisoformat(ticket_data['start_date'].replace('Z', '+00:00'))
                        issue_dict['duedate'] = start_date_obj.strftime('%Y-%m-%d')
                        logger.info(f"📅 Jira 이슈 시작일 설정: {issue_dict['duedate']}")
                except Exception as e:
                    logger.warning(f"⚠️ 시작일 설정 실패: {e}")
                    
            # 사용자 정의 필드로 실제 시작일 설정 시도 (선택사항)
            # 대부분의 Jira 인스턴스에서 customfield_xxxxx 형태로 시작일 필드가 있을 수 있음
            
            # 우선순위 설정 (선택사항) - JIRA 프로젝트에서 Priority 필드가 비활성화된 경우 주석 처리
            # if ticket_data.get('priority'):
            #     try:
            #         priorities = self.jira.priorities()
            #         for priority in priorities:
            #             if priority.name.lower() == ticket_data['priority'].lower():
            #                 issue_dict['priority'] = {'name': priority.name}
            #                 logger.info(f"✅ 우선순위 설정: {priority.name}")
            #                 break
            #     except Exception as e:
            #         logger.warning(f"⚠️ 우선순위 설정 실패: {e}")
            
            # Jira 이슈 생성
            new_issue = self.jira.create_issue(fields=issue_dict)
            
            logger.info(f"✅ Jira 이슈 생성 성공: {new_issue.key}")
            
            return {
                "success": True,
                "issue_key": new_issue.key,
                "issue_url": f"{self.url}/browse/{new_issue.key}",
                "message": f"Jira 이슈 생성 완료: {new_issue.key}"
            }
            
        except JIRAError as e:
            logger.error(f"❌ Jira 이슈 생성 실패: {e}")
            return {
                "success": False,
                "error": f"Jira API 오류: {str(e)}",
                "message": "Jira 이슈 생성에 실패했습니다."
            }
        except Exception as e:
            logger.error(f"❌ 이슈 생성 중 예상치 못한 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "이슈 생성 중 오류가 발생했습니다."
            }
    
    def validate_credentials(self) -> Dict[str, Any]:
        """
        /myself API를 호출하여 Jira 인증 정보 검증 (Bearer Token 사용)

        Returns:
            검증 결과 (성공 여부, 사용자 정보 등)
        """
        try:
            logger.info("🔐 Jira 인증 정보 검증 시작 (Bearer Token)")

            # requests를 사용하여 직접 /myself API 호출 (Bearer Token)
            import requests

            url = f"{self.url}/rest/api/2/myself"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            logger.info(f"🔗 API 호출: {url}")
            logger.info(f"🔑 Authorization: Bearer {self.token[:10]}...")

            response = requests.get(url, headers=headers, verify=True, timeout=30)

            logger.info(f"📊 응답 상태 코드: {response.status_code}")
            logger.info(f"📊 응답 헤더: {dict(response.headers)}")
            logger.info(f"📊 응답 본문 (처음 200자): {response.text[:200]}")

            # 상태 코드 확인
            if response.status_code == 401:
                logger.error("❌ 401 Unauthorized: Bearer 토큰이 잘못되었거나 만료됨")
                return {
                    "success": False,
                    "error": "인증 실패: Bearer API 토큰이 잘못되었거나 만료되었습니다.",
                    "message": "Bearer API 토큰을 확인해주세요."
                }
            elif response.status_code == 403:
                logger.error("❌ 403 Forbidden: 권한 부족")
                return {
                    "success": False,
                    "error": "권한 부족: Jira 접근 권한이 없습니다.",
                    "message": "Jira 계정 권한을 확인해주세요."
                }
            elif response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"Jira API 오류 (HTTP {response.status_code}): {response.text[:100]}",
                    "message": "인증 중 오류가 발생했습니다."
                }

            # JSON 파싱
            try:
                myself = response.json()
                logger.info(f"✅ Jira 인증 성공: {myself.get('displayName', 'Unknown')}")

                return {
                    "success": True,
                    "user_info": {
                        "account_id": myself.get('accountId', ''),
                        "email": myself.get('emailAddress', ''),
                        "display_name": myself.get('displayName', ''),
                        "active": myself.get('active', False)
                    },
                    "message": f"인증 성공: {myself.get('displayName', 'Unknown')}"
                }
            except ValueError as json_error:
                logger.error(f"❌ JSON 파싱 실패: {json_error}")
                logger.error(f"📊 응답 본문 전체: {response.text}")
                return {
                    "success": False,
                    "error": f"응답 파싱 실패: {str(json_error)}",
                    "message": "Jira 응답을 처리할 수 없습니다."
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP 요청 실패: {e}")
            return {
                "success": False,
                "error": f"네트워크 오류: {str(e)}",
                "message": "Jira 서버에 연결할 수 없습니다."
            }
        except Exception as e:
            logger.error(f"❌ 인증 검증 중 예상치 못한 오류: {e}")
            import traceback
            logger.error(f"📊 스택 트레이스:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "message": "인증 검증 중 오류가 발생했습니다."
            }

    def get_projects(self) -> Dict[str, Any]:
        """
        /project API를 호출하여 접근 가능한 프로젝트 목록 조회 (Bearer Token 사용)

        Returns:
            프로젝트 목록 (성공 여부, 프로젝트 리스트 등)
        """
        try:
            logger.info("📁 Jira 프로젝트 목록 조회 시작 (Bearer Token)")

            # requests를 사용하여 직접 /project API 호출
            import requests

            url = f"{self.url}/rest/api/2/project"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            logger.info(f"🔗 API 호출: {url}")

            response = requests.get(url, headers=headers, verify=True, timeout=30)

            logger.info(f"📊 응답 상태 코드: {response.status_code}")

            # 상태 코드 확인
            if response.status_code == 401:
                logger.error("❌ 401 Unauthorized")
                return {
                    "success": False,
                    "error": "인증 실패: Bearer API 토큰이 만료되었거나 잘못되었습니다.",
                    "message": "Bearer API 토큰을 다시 확인해주세요."
                }
            elif response.status_code == 403:
                logger.error("❌ 403 Forbidden")
                return {
                    "success": False,
                    "error": "권한 부족: 프로젝트 조회 권한이 없습니다.",
                    "message": "프로젝트 접근 권한을 확인해주세요."
                }
            elif response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"Jira API 오류 (HTTP {response.status_code}): {response.text[:100]}",
                    "message": "프로젝트 조회 중 오류가 발생했습니다."
                }

            # JSON 파싱
            try:
                projects = response.json()

                project_list = []
                for project in projects:
                    project_list.append({
                        "key": project.get("key", ""),
                        "name": project.get("name", ""),
                        "id": project.get("id", ""),
                        "project_type": project.get("projectTypeKey", "unknown")
                    })

                logger.info(f"✅ {len(project_list)}개의 프로젝트 조회 완료")

                return {
                    "success": True,
                    "projects": project_list,
                    "count": len(project_list),
                    "message": f"{len(project_list)}개의 프로젝트를 찾았습니다."
                }
            except ValueError as json_error:
                logger.error(f"❌ JSON 파싱 실패: {json_error}")
                logger.error(f"📊 응답 본문: {response.text[:200]}")
                return {
                    "success": False,
                    "error": f"응답 파싱 실패: {str(json_error)}",
                    "message": "Jira 응답을 처리할 수 없습니다."
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP 요청 실패: {e}")
            return {
                "success": False,
                "error": f"네트워크 오류: {str(e)}",
                "message": "Jira 서버에 연결할 수 없습니다."
            }
        except Exception as e:
            logger.error(f"❌ 프로젝트 조회 중 예상치 못한 오류: {e}")
            import traceback
            logger.error(f"📊 스택 트레이스:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "message": "프로젝트 조회 중 오류가 발생했습니다."
            }

    def validate_jql_with_labels(self, project_key: str, labels: List[str]) -> Dict[str, Any]:
        """
        프로젝트와 레이블 조합으로 JQL 쿼리를 생성하고 검증 (Bearer Token 사용)

        Args:
            project_key: Jira 프로젝트 키
            labels: 필터링할 레이블 리스트

        Returns:
            검증 결과 (성공 여부, 이슈 개수 등)
        """
        try:
            logger.info(f"🔍 JQL 쿼리 검증 시작 (Bearer Token): {project_key} - {labels}")

            # JQL 쿼리 생성
            if labels:
                label_condition = " OR ".join([f'labels = "{label}"' for label in labels])
                jql_query = f'project = {project_key} AND ({label_condition}) ORDER BY updated DESC'
            else:
                jql_query = f'project = {project_key} ORDER BY updated DESC'

            logger.info(f"📝 생성된 JQL 쿼리: {jql_query}")

            # requests를 사용하여 직접 JQL 검색 API 호출
            import requests

            url = f"{self.url}/rest/api/2/search"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            params = {
                "jql": jql_query,
                "maxResults": 10,
                "fields": "key,summary"
            }

            logger.info(f"🔗 API 호출: {url}")

            response = requests.get(url, headers=headers, params=params, verify=True, timeout=30)

            logger.info(f"📊 응답 상태 코드: {response.status_code}")

            # 상태 코드 확인
            if response.status_code == 400:
                logger.error("❌ 400 Bad Request: JQL 쿼리 오류")
                return {
                    "success": False,
                    "error": "잘못된 JQL 쿼리: 프로젝트 키 또는 레이블이 잘못되었습니다.",
                    "message": "프로젝트 키와 레이블을 확인해주세요.",
                    "jql_query": jql_query
                }
            elif response.status_code == 401:
                logger.error("❌ 401 Unauthorized")
                return {
                    "success": False,
                    "error": "인증 실패: Bearer API 토큰이 만료되었거나 잘못되었습니다.",
                    "message": "Bearer API 토큰을 다시 확인해주세요."
                }
            elif response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"Jira API 오류 (HTTP {response.status_code}): {response.text[:100]}",
                    "message": "JQL 쿼리 검증 중 오류가 발생했습니다."
                }

            # JSON 파싱
            try:
                result = response.json()
                issue_count = result.get("total", 0)

                logger.info(f"✅ JQL 쿼리 검증 성공: {issue_count}개 이슈 발견")

                return {
                    "success": True,
                    "issue_count": issue_count,
                    "jql_query": jql_query,
                    "has_issues": issue_count > 0,
                    "message": f"{issue_count}개의 이슈를 찾았습니다." if issue_count > 0 else "조회된 이슈가 없습니다."
                }
            except ValueError as json_error:
                logger.error(f"❌ JSON 파싱 실패: {json_error}")
                logger.error(f"📊 응답 본문: {response.text[:200]}")
                return {
                    "success": False,
                    "error": f"응답 파싱 실패: {str(json_error)}",
                    "message": "Jira 응답을 처리할 수 없습니다."
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP 요청 실패: {e}")
            return {
                "success": False,
                "error": f"네트워크 오류: {str(e)}",
                "message": "Jira 서버에 연결할 수 없습니다."
            }
        except Exception as e:
            logger.error(f"❌ JQL 쿼리 검증 중 예상치 못한 오류: {e}")
            import traceback
            logger.error(f"📊 스택 트레이스:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "message": "JQL 쿼리 검증 중 오류가 발생했습니다."
            }

    def validate_jql(self, jql: str, max_results: int = 10) -> Dict[str, Any]:
        """
        사용자가 입력한 JQL 쿼리를 직접 검증 (Bearer Token 사용)

        Args:
            jql: 검증할 JQL 쿼리
            max_results: 조회할 최대 이슈 개수 (기본 10개)

        Returns:
            검증 결과 (성공 여부, 이슈 개수, 샘플 이슈 등)
        """
        try:
            logger.info(f"🔍 JQL 쿼리 검증 시작 (Bearer Token): {jql}")

            # requests를 사용하여 직접 JQL 검색 API 호출
            import requests

            url = f"{self.url}/rest/api/2/search"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": "key,summary,status,priority,updated"
            }

            logger.info(f"🔗 API 호출: {url}")

            response = requests.get(url, headers=headers, params=params, verify=True, timeout=30)

            logger.info(f"📊 응답 상태 코드: {response.status_code}")

            # 상태 코드 확인
            if response.status_code == 400:
                logger.error("❌ 400 Bad Request: JQL 쿼리 오류")
                error_detail = ""
                try:
                    error_json = response.json()
                    if "errorMessages" in error_json:
                        error_detail = " ".join(error_json["errorMessages"])
                except:
                    error_detail = response.text[:200]

                return {
                    "success": False,
                    "error": f"잘못된 JQL 쿼리: {error_detail}",
                    "message": "JQL 쿼리 문법을 확인해주세요.",
                    "jql_query": jql
                }
            elif response.status_code == 401:
                logger.error("❌ 401 Unauthorized")
                return {
                    "success": False,
                    "error": "인증 실패: Bearer API 토큰이 만료되었거나 잘못되었습니다.",
                    "message": "Bearer API 토큰을 다시 확인해주세요."
                }
            elif response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"Jira API 오류 (HTTP {response.status_code}): {response.text[:100]}",
                    "message": "JQL 쿼리 검증 중 오류가 발생했습니다."
                }

            # JSON 파싱
            try:
                result = response.json()
                issue_count = result.get("total", 0)
                issues = result.get("issues", [])

                # 샘플 이슈 데이터 추출
                sample_issues = []
                for issue in issues[:5]:  # 최대 5개만
                    fields = issue.get("fields", {})
                    sample_issues.append({
                        "key": issue.get("key"),
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
                        "updated": fields.get("updated")
                    })

                logger.info(f"✅ JQL 쿼리 검증 성공: {issue_count}개 이슈 발견")

                return {
                    "success": True,
                    "issue_count": issue_count,
                    "sample_issues": sample_issues,
                    "jql_query": jql,
                    "has_issues": issue_count > 0,
                    "message": f"{issue_count}개의 이슈를 찾았습니다." if issue_count > 0 else "조회된 이슈가 없습니다."
                }
            except ValueError as json_error:
                logger.error(f"❌ JSON 파싱 실패: {json_error}")
                logger.error(f"📊 응답 본문: {response.text[:200]}")
                return {
                    "success": False,
                    "error": f"응답 파싱 실패: {str(json_error)}",
                    "message": "Jira 응답을 처리할 수 없습니다."
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP 요청 실패: {e}")
            return {
                "success": False,
                "error": f"네트워크 오류: {str(e)}",
                "message": "Jira 서버에 연결할 수 없습니다."
            }
        except Exception as e:
            logger.error(f"❌ JQL 쿼리 검증 중 예상치 못한 오류: {e}")
            import traceback
            logger.error(f"📊 스택 트레이스:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "message": "JQL 쿼리 검증 중 오류가 발생했습니다."
            }

    def close(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
            logger.info("✅ JiraConnector 리소스 정리 완료")
        except Exception as e:
            logger.error(f"❌ 리소스 정리 중 오류: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 