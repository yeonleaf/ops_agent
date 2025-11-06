#!/usr/bin/env python3
"""
Jira API 클라이언트

Jira REST API를 통해 이슈 데이터를 조회합니다.
"""

import requests
from typing import List, Dict, Optional
import logging
import time
import json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class JiraAPIError(Exception):
    """Jira API 에러"""
    pass


class JiraClient:
    """Jira REST API 클라이언트"""

    def __init__(self, endpoint: str, token: str, timeout: int = 30, debug_mode: bool = True):
        """
        초기화

        Args:
            endpoint: Jira 서버 URL (예: https://jira.skbroadband.com)
            token: API 토큰 (복호화된 평문)
            timeout: HTTP 요청 타임아웃 (초)
            debug_mode: 디버그 모드 활성화 (response를 JSON 파일로 저장)
        """
        self.endpoint = endpoint.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.debug_mode = debug_mode

        # Session 생성
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        # 디버그 디렉토리 생성
        if self.debug_mode:
            self.debug_dir = Path("debug_jira_responses")
            self.debug_dir.mkdir(exist_ok=True)
            logger.info(f"🐛 디버그 모드 활성화: {self.debug_dir}")

        logger.info(f"✅ JiraClient 초기화: {self.endpoint}")

    def _save_response_to_json(self, response_data: Dict, operation: str, identifier: str = ""):
        """
        디버그용 response를 JSON 파일로 저장

        Args:
            response_data: 저장할 response 데이터
            operation: 작업 유형 (예: "search", "get_issue")
            identifier: 추가 식별자 (예: 이슈 키, JQL의 일부)
        """
        if not self.debug_mode:
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            safe_identifier = identifier.replace("/", "_").replace(" ", "_")[:50] if identifier else ""
            filename = f"{operation}_{timestamp}_{safe_identifier}.json" if safe_identifier else f"{operation}_{timestamp}.json"
            filepath = self.debug_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)

            logger.info(f"💾 디버그 JSON 저장: {filepath}")

        except Exception as e:
            logger.warning(f"⚠️ 디버그 JSON 저장 실패: {e}")

    def search_issues(
        self,
        jql: str,
        max_results: int = 100,
        fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        JQL로 이슈 검색 (페이지네이션 자동 처리)

        Args:
            jql: JQL 쿼리 문자열
            max_results: 페이지당 최대 결과 수 (기본값: 100)
            fields: 조회할 필드 목록 (None이면 기본 필드)

        Returns:
            이슈 목록 (전체)

        Raises:
            JiraAPIError: API 호출 실패 시
        """
        # 기본 필드 설정
        if fields is None:
            fields = [
                "key", "summary", "description",
                "issuetype", "status", "priority",
                "labels", "assignee", "reporter",
                "project", "comment", "components", "fixVersions",
                "created", "updated"
            ]

        all_issues = []
        start_at = 0

        logger.info(f"🔍 Jira 이슈 검색 시작")
        logger.info(f"   원본 JQL: {jql}")

        # JQL 정규화
        original_jql = jql
        modifications = []

        # 1. 작은따옴표를 큰따옴표로 변환
        jql = jql.replace("'", '"')
        if "'" in original_jql:
            modifications.append("작은따옴표 → 큰따옴표")

        # 2. fixVersions → fixVersion (JQL에서는 단수형 사용)
        import re
        if re.search(r'\bfixVersions\b', jql, re.IGNORECASE):
            jql = re.sub(r'\bfixVersions\b', 'fixVersion', jql, flags=re.IGNORECASE)
            modifications.append("fixVersions → fixVersion")

        if modifications:
            logger.warning(f"   ⚠️ JQL 자동 수정: {', '.join(modifications)}")
            logger.info(f"   수정된 JQL: {jql}")
        else:
            logger.info(f"   JQL: {jql}")

        logger.info(f"   필드 수: {len(fields)}")

        while True:
            try:
                # API 호출
                url = f"{self.endpoint}/rest/api/2/search"
                params = {
                    "jql": jql,
                    "fields": ",".join(fields),
                    "startAt": start_at,
                    "maxResults": max_results
                }

                logger.debug(f"   페이지 요청: startAt={start_at}, maxResults={max_results}")

                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )

                # HTTP 에러 처리
                if response.status_code == 400:
                    # JQL 문법 오류 등
                    error_detail = ""
                    try:
                        error_data = response.json()
                        error_messages = error_data.get("errorMessages", [])
                        if error_messages:
                            error_detail = f": {', '.join(error_messages)}"
                    except:
                        pass
                    raise JiraAPIError(f"JQL 문법 오류 (400){error_detail}\nJQL: {jql}")
                elif response.status_code == 401:
                    raise JiraAPIError("인증 실패 (401): 토큰이 유효하지 않습니다")
                elif response.status_code == 403:
                    raise JiraAPIError("권한 없음 (403): 해당 프로젝트/이슈에 접근 권한이 없습니다")
                elif response.status_code == 404:
                    raise JiraAPIError("Not Found (404): 엔드포인트가 존재하지 않습니다")
                elif response.status_code >= 500:
                    raise JiraAPIError(f"서버 에러 ({response.status_code}): Jira 서버에 문제가 있습니다")

                response.raise_for_status()

                # JSON 파싱
                data = response.json()

                # 디버그: response를 JSON 파일로 저장
                if self.debug_mode:
                    jql_short = jql[:30].replace(" ", "_")
                    self._save_response_to_json(data, "search_issues", f"page_{start_at}_{jql_short}")

                issues = data.get("issues", [])
                total = data.get("total", 0)

                logger.debug(f"   수신: {len(issues)}개 (전체: {total}개)")

                all_issues.extend(issues)

                # 페이지네이션 종료 조건
                if len(issues) < max_results:
                    break

                # 다음 페이지로
                start_at += max_results

                # Rate limiting 방지 (간단한 지연)
                time.sleep(0.1)

            except requests.exceptions.Timeout:
                raise JiraAPIError(f"타임아웃 ({self.timeout}초): Jira 서버 응답 없음")
            except requests.exceptions.ConnectionError:
                raise JiraAPIError(f"연결 실패: Jira 서버에 연결할 수 없습니다 ({self.endpoint})")
            except requests.exceptions.RequestException as e:
                raise JiraAPIError(f"HTTP 요청 실패: {e}")
            except Exception as e:
                raise JiraAPIError(f"예상치 못한 에러: {e}")

        logger.info(f"✅ Jira 이슈 검색 완료: {len(all_issues)}개")
        return all_issues

    def get_issue(self, issue_key: str, expand: Optional[str] = None) -> Optional[Dict]:
        """
        특정 이슈 조회 (단건)

        Args:
            issue_key: 이슈 키 (예: BTVO-123)
            expand: 확장할 필드 (예: "changelog")

        Returns:
            이슈 데이터 또는 None

        Raises:
            JiraAPIError: API 호출 실패 시
        """
        try:
            url = f"{self.endpoint}/rest/api/2/issue/{issue_key}"
            params = {}
            if expand:
                params["expand"] = expand

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 404:
                logger.warning(f"⚠️ 이슈를 찾을 수 없음: {issue_key}")
                return None

            response.raise_for_status()

            issue = response.json()

            # 디버그: response를 JSON 파일로 저장
            if self.debug_mode:
                self._save_response_to_json(issue, "get_issue", issue_key)

            logger.debug(f"✅ 이슈 조회 성공: {issue_key}")
            return issue

        except requests.exceptions.RequestException as e:
            raise JiraAPIError(f"이슈 조회 실패 ({issue_key}): {e}")

    def test_connection(self) -> bool:
        """
        Jira 연결 테스트

        Returns:
            연결 성공 여부
        """
        try:
            url = f"{self.endpoint}/rest/api/2/myself"

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            user_data = response.json()
            logger.info(f"✅ Jira 연결 성공: {user_data.get('displayName', 'Unknown')}")
            return True

        except Exception as e:
            logger.error(f"❌ Jira 연결 실패: {e}")
            return False


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 Jira Client 모듈 테스트")
    print("=" * 60)

    # Mock 테스트 (실제 API 호출하지 않음)
    print("\n[1] JiraClient 초기화")
    client = JiraClient(
        endpoint="https://jira.example.com",
        token="test_token_123"
    )
    print("   ✅ 초기화 성공")

    print("\n[2] 연결 테스트 (Mock - 실제 호출 안 함)")
    print("   💡 실제 테스트는 실제 Jira 서버로 진행하세요")

    # 실제 환경에서 테스트하려면:
    # from batch.jira_config import load_jira_config
    # config = load_jira_config(user_id=1)
    # if config:
    #     client = JiraClient(config["endpoint"], config["token"])
    #     success = client.test_connection()
    #     if success:
    #         jql = 'project = BTVO AND updated >= "2025-10-01"'
    #         issues = client.search_issues(jql, max_results=10)
    #         print(f"   조회된 이슈: {len(issues)}개")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
