#!/usr/bin/env python3
"""
Jira Query Tool - JQL로 Jira 이슈를 조회하고 필드를 추출하는 도구
"""

from typing import List, Dict, Optional
import sqlite3
import logging

from batch.jira_client import JiraClient, JiraAPIError
from auth_utils import TokenEncryption
from cached_jira_client import CachedJiraClient, register_cache_client

logger = logging.getLogger(__name__)


class JiraQueryTool:
    """
    JQL로 Jira 이슈를 조회하는 도구
    기존 JiraClient를 재사용하여 이슈를 조회하고, 필요한 필드만 추출합니다.
    """

    def __init__(self, user_id: int, db_path: str = "tickets.db"):
        """
        Args:
            user_id: integration 테이블에서 Jira 설정을 가져올 유저 ID
            db_path: SQLite DB 파일 경로
        """
        self.user_id = user_id
        self.db_path = db_path
        self.client = self._init_jira_client()

    def _init_jira_client(self) -> CachedJiraClient:
        """
        integration 테이블에서 Jira 설정 로드 후 CachedJiraClient 생성 또는 재사용

        Returns:
            초기화된 CachedJiraClient 인스턴스 (JiraClient를 래핑하여 캐싱 기능 제공)

        Raises:
            ValueError: Jira 설정이 없거나 불완전한 경우
        """
        try:
            # 이미 등록된 캐시 클라이언트가 있으면 재사용
            from cached_jira_client import get_all_cache_clients
            cache_clients = get_all_cache_clients()

            if self.user_id in cache_clients:
                logger.info(f"♻️  기존 CachedJiraClient 재사용 (user_id={self.user_id})")
                return cache_clients[self.user_id]

            # 새로 생성
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # endpoint, token 조회
            cursor.execute("""
                SELECT type, value FROM integrations
                WHERE user_id = ? AND source = 'jira' AND type IN ('endpoint', 'token')
            """, (self.user_id,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                raise ValueError(f"Jira 설정을 찾을 수 없습니다 (user_id={self.user_id})")

            config = dict(rows)

            # 필수 설정 확인
            if 'endpoint' not in config or 'token' not in config:
                raise ValueError(f"Jira 설정이 불완전합니다. endpoint 또는 token이 없습니다.")

            # 토큰 평문 사용 (복호화 제거)
            # token_encryption = TokenEncryption()
            # decrypted_token = token_encryption.decrypt_token(config['token'])
            plain_token = config['token']  # 평문으로 저장되어 있음

            # JiraClient 생성
            jira_client = JiraClient(
                endpoint=config['endpoint'],
                token=plain_token  # 평문 토큰 사용
            )

            # CachedJiraClient로 래핑 (캐싱 기능 추가)
            cached_client = CachedJiraClient(jira_client)

            # 전역 레지스트리에 등록 (캐시 통계 및 관리용)
            register_cache_client(self.user_id, cached_client)

            logger.info(f"✅ CachedJiraClient 생성 및 등록 (user_id={self.user_id})")
            return cached_client

        except Exception as e:
            logger.error(f"❌ JiraClient 초기화 실패: {e}")
            raise

    def get_issues_by_jql(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: int = 1000
    ) -> List[Dict]:
        """
        JQL로 이슈 조회

        Args:
            jql: Jira JQL 쿼리
            fields: 가져올 필드 목록 (None이면 기본 필드)
            max_results: 최대 결과 수 (페이지당, JiraClient가 페이지네이션 자동 처리)

        Returns:
            정리된 이슈 목록
            [
                {
                    "key": "BTVO-123",
                    "summary": "로그인 실패 문제",
                    "created": "2025-10-15T10:30:00",
                    "updated": "2025-10-16T14:20:00",
                    "status": "Done",
                    "priority": "High",
                    "assignee": "user1",
                    "reporter": "user2",
                    "labels": ["NCMS", "backend"],
                    "components": ["Database"],
                    "issuetype": "Bug"
                }
            ]

        Raises:
            JiraAPIError: API 호출 실패 시
        """
        # 기본 필드 설정
        if fields is None:
            fields = [
                "key", "summary", "created", "updated",
                "status", "priority", "assignee", "reporter",
                "labels", "components", "issuetype", "fixVersions"
            ]

        try:
            # JiraClient의 search_issues 사용 (페이지네이션 자동 처리)
            logger.info(f"🔍 JQL 실행: {jql}")
            raw_issues = self.client.search_issues(jql, max_results=max_results)

            logger.info(f"✅ 조회 완료: {len(raw_issues)}개 이슈")

            # 필요한 필드만 추출 및 정리
            cleaned_issues = []
            for issue in raw_issues:
                cleaned = self._extract_fields(issue, fields)
                cleaned_issues.append(cleaned)

            return cleaned_issues

        except JiraAPIError as e:
            logger.error(f"❌ Jira API 에러: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 예상치 못한 에러: {e}")
            raise

    def _extract_fields(self, issue: Dict, fields: List[str]) -> Dict:
        """
        Jira API 응답에서 필요한 필드만 추출 및 정리

        Args:
            issue: Jira API 응답 (raw)
            fields: 추출할 필드 목록

        Returns:
            정리된 이슈 데이터
        """
        result = {}
        issue_fields = issue.get("fields", {})

        # key는 최상위에 있음
        if "key" in fields:
            result["key"] = issue.get("key", "")

        # 필드별 추출 로직
        field_mapping = {
            "summary": lambda: issue_fields.get("summary", ""),
            "created": lambda: issue_fields.get("created", ""),
            "updated": lambda: issue_fields.get("updated", ""),
            "status": lambda: issue_fields.get("status", {}).get("name", "") if issue_fields.get("status") else "",
            "priority": lambda: issue_fields.get("priority", {}).get("name", "") if issue_fields.get("priority") else "",
            "assignee": lambda: issue_fields.get("assignee", {}).get("displayName", "") if issue_fields.get("assignee") else "",
            "reporter": lambda: issue_fields.get("reporter", {}).get("displayName", "") if issue_fields.get("reporter") else "",
            "labels": lambda: issue_fields.get("labels", []),
            "components": lambda: [c.get("name") for c in issue_fields.get("components", [])],
            "issuetype": lambda: issue_fields.get("issuetype", {}).get("name", "") if issue_fields.get("issuetype") else "",
            "fixVersions": lambda: [v.get("name") for v in issue_fields.get("fixVersions", [])]
        }

        for field in fields:
            if field in field_mapping:
                try:
                    result[field] = field_mapping[field]()
                except Exception as e:
                    logger.warning(f"⚠️ 필드 추출 실패 ({field}): {e}")
                    result[field] = ""  # 기본값

        return result

    def fetch_for_queries(self, queries: List[Dict]) -> List[Dict]:
        """
        여러 JQL 쿼리를 실행하고 결과 통합

        Args:
            queries: [{"user": "user1", "jql": "..."}, {"user": "user2", "jql": "..."}, ...]

        Returns:
            통합된 이슈 목록 (각 이슈에 _query_user 필드 추가)

        Raises:
            JiraAPIError: API 호출 실패 시
        """
        all_issues = []

        for i, query in enumerate(queries):
            user = query.get("user", "Unknown")
            jql = query.get("jql", "")

            if not jql:
                logger.warning(f"⚠️ 쿼리 {i+1}: JQL이 비어 있습니다. 스킵합니다.")
                continue

            try:
                logger.info(f"🔍 쿼리 {i+1}/{len(queries)} (user={user})")
                issues = self.get_issues_by_jql(jql)

                # 각 이슈에 user 정보 추가
                for issue in issues:
                    issue["_query_user"] = user

                all_issues.extend(issues)
                logger.info(f"   ✅ {len(issues)}개 이슈 조회")

            except JiraAPIError as e:
                logger.error(f"   ❌ 쿼리 {i+1} 실패: {e}")
                # 에러가 발생해도 다른 쿼리는 계속 실행
                continue
            except Exception as e:
                logger.error(f"   ❌ 예상치 못한 에러: {e}")
                continue

        logger.info(f"✅ 전체 조회 완료: {len(all_issues)}개 이슈")
        return all_issues

    def test_connection(self) -> bool:
        """
        Jira 연결 테스트

        Returns:
            연결 성공 여부
        """
        try:
            return self.client.test_connection()
        except Exception as e:
            logger.error(f"❌ 연결 테스트 실패: {e}")
            return False


if __name__ == "__main__":
    # 간단한 테스트
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 JiraQueryTool 모듈 테스트")
    print("=" * 60)

    try:
        print("\n[1] JiraQueryTool 초기화")
        tool = JiraQueryTool(user_id=1)
        print("   ✅ 초기화 성공")

        print("\n[2] Jira 연결 테스트")
        if tool.test_connection():
            print("   ✅ 연결 성공")
        else:
            print("   ❌ 연결 실패")

        print("\n[3] JQL 쿼리 테스트 (최대 5개)")
        jql = "project = BTVO ORDER BY created DESC"
        issues = tool.get_issues_by_jql(jql, max_results=5)
        print(f"   ✅ 조회된 이슈: {len(issues)}개")

        if issues:
            print("\n[4] 첫 번째 이슈:")
            first_issue = issues[0]
            for key, value in first_issue.items():
                print(f"      {key}: {value}")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
