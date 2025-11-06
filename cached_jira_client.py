#!/usr/bin/env python3
"""
Cached Jira Client - Jira API 호출 결과를 메모리에 캐싱하는 래퍼 클래스

Jira API 호출 결과를 메모리에 캐싱하여 성능을 향상시킵니다.
- 이슈 key 기반 캐싱
- JQL 쿼리 결과 캐싱
- 월 변경 시 자동 캐시 초기화
- 캐시 통계 수집
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# 전역 캐시 레지스트리 (user_id -> CachedJiraClient)
_cache_registry: Dict[int, 'CachedJiraClient'] = {}


def get_all_cache_clients() -> Dict[int, 'CachedJiraClient']:
    """
    모든 CachedJiraClient 인스턴스 반환

    Returns:
        {user_id: CachedJiraClient} 딕셔너리
    """
    return _cache_registry


def register_cache_client(user_id: int, client: 'CachedJiraClient'):
    """
    CachedJiraClient 인스턴스를 레지스트리에 등록

    Args:
        user_id: 사용자 ID
        client: CachedJiraClient 인스턴스
    """
    _cache_registry[user_id] = client
    logger.debug(f"📝 캐시 클라이언트 등록: user_id={user_id}")


def get_total_cache_stats() -> Dict[str, Any]:
    """
    모든 사용자의 캐시 통계 합산

    Returns:
        전체 캐시 통계
    """
    total_stats = {
        'total_requests': 0,
        'cache_hits': 0,
        'cache_misses': 0,
        'api_calls': 0,
        'cached_items': 0,
        'users': len(_cache_registry)
    }

    for client in _cache_registry.values():
        stats = client.get_cache_stats()
        total_stats['total_requests'] += stats['total_requests']
        total_stats['cache_hits'] += stats['cache_hits']
        total_stats['cache_misses'] += stats['cache_misses']
        total_stats['api_calls'] += stats['api_calls']
        total_stats['cached_items'] += stats['cached_items']

    # 히트율 계산
    total_requests = total_stats['total_requests']
    if total_requests > 0:
        hit_rate = (total_stats['cache_hits'] / total_requests * 100)
        total_stats['hit_rate'] = f"{hit_rate:.1f}%"
    else:
        total_stats['hit_rate'] = "0.0%"

    return total_stats


def clear_all_caches():
    """모든 사용자의 캐시 초기화"""
    count = 0
    for client in _cache_registry.values():
        client.clear_cache()
        count += 1

    logger.info(f"🗑️  전체 캐시 초기화: {count}명의 사용자 캐시 삭제")


class CachedJiraClient:
    """
    JiraClient를 래핑하여 API 호출 결과를 캐싱하는 클래스

    캐시 키 규칙:
    - 이슈: {YYYY-MM}_{ISSUE_KEY} (예: 2024-11_BTVO-61581)
    - JQL: {YYYY-MM}_jql_{MD5_HASH[:8]}

    월이 변경되면 자동으로 전체 캐시가 초기화됩니다.
    """

    def __init__(self, jira_client):
        """
        Args:
            jira_client: batch.jira_client.JiraClient 인스턴스
        """
        self.client = jira_client
        self.cache: Dict[str, Any] = {}
        self.current_month = datetime.now().strftime('%Y-%m')

        # 캐시 통계
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0
        }

        logger.info(f"✅ CachedJiraClient 초기화 (월: {self.current_month})")

    def _check_month_change(self):
        """월이 변경되었는지 확인하고, 변경되었으면 캐시 초기화"""
        current = datetime.now().strftime('%Y-%m')

        if current != self.current_month:
            logger.info(f"📅 월 변경 감지: {self.current_month} → {current}")
            old_count = len(self.cache)
            self.clear_cache()
            self.current_month = current
            logger.info(f"🗑️  캐시 초기화: {old_count}개 항목 삭제")

    def _make_issue_key(self, issue_key: str) -> str:
        """
        이슈 캐시 키 생성

        Args:
            issue_key: 이슈 키 (예: BTVO-61581)

        Returns:
            캐시 키 (예: 2024-11_BTVO-61581)
        """
        return f"{self.current_month}_{issue_key}"

    def _make_jql_key(self, jql: str, max_results: int, fields: Optional[List[str]]) -> str:
        """
        JQL 쿼리 캐시 키 생성

        Args:
            jql: JQL 쿼리
            max_results: 최대 결과 수
            fields: 필드 리스트

        Returns:
            캐시 키 (예: 2024-11_jql_a1b2c3d4)
        """
        # JQL + max_results + fields를 조합하여 해시 생성
        fields_str = ','.join(sorted(fields)) if fields else ''
        content = f"{jql}|{max_results}|{fields_str}"
        hash_digest = hashlib.md5(content.encode()).hexdigest()[:8]

        cache_key = f"{self.current_month}_jql_{hash_digest}"

        # 디버그 로그 (캐시 키 생성 정보)
        logger.debug(f"🔑 캐시 키 생성: {cache_key}")
        logger.debug(f"   JQL: {jql[:100]}{'...' if len(jql) > 100 else ''}")
        logger.debug(f"   max_results: {max_results}")
        logger.debug(f"   fields: {len(fields) if fields else 0}개")

        return cache_key

    def get_issue(self, issue_key: str, expand: Optional[str] = None, use_cache: bool = True) -> Optional[Dict]:
        """
        특정 이슈 조회 (캐싱 지원)

        Args:
            issue_key: 이슈 키 (예: BTVO-123)
            expand: 확장할 필드 (예: "changelog")
            use_cache: 캐시 사용 여부

        Returns:
            이슈 데이터 또는 None
        """
        self._check_month_change()
        self.stats['total_requests'] += 1

        # 캐시 키 생성 (expand 포함)
        cache_key = self._make_issue_key(issue_key)
        if expand:
            cache_key += f"_expand_{expand}"

        # 캐시 확인
        if use_cache and cache_key in self.cache:
            self.stats['cache_hits'] += 1
            logger.info(f"✓ 캐시 히트: 이슈 {issue_key} [캐시 키: {cache_key}]")
            return self.cache[cache_key]

        # 캐시 미스 - API 호출
        self.stats['cache_misses'] += 1
        self.stats['api_calls'] += 1
        logger.warning(f"✗ 캐시 미스: 이슈 {issue_key} - API 호출 필요 [캐시 키: {cache_key}]")

        result = self.client.get_issue(issue_key, expand=expand)

        # 캐시 저장
        if result is not None and use_cache:
            self.cache[cache_key] = result
            logger.info(f"✓ 캐시 저장: 이슈 {issue_key} [캐시 키: {cache_key}]")

        return result

    def search_issues(
        self,
        jql: str,
        max_results: int = 100,
        fields: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        JQL로 이슈 검색 (캐싱 지원)

        Args:
            jql: JQL 쿼리 문자열
            max_results: 페이지당 최대 결과 수
            fields: 조회할 필드 목록
            use_cache: 캐시 사용 여부

        Returns:
            이슈 목록
        """
        self._check_month_change()
        self.stats['total_requests'] += 1

        # 캐시 키 생성
        cache_key = self._make_jql_key(jql, max_results, fields)

        # 캐시 확인
        if use_cache and cache_key in self.cache:
            self.stats['cache_hits'] += 1
            result = self.cache[cache_key]
            logger.info(f"✓ 캐시 히트: JQL 검색 (결과 {len(result)}개) [캐시 키: {cache_key}]")
            logger.info(f"   JQL: {jql[:80]}{'...' if len(jql) > 80 else ''}")
            return result

        # 캐시 미스 - API 호출
        self.stats['cache_misses'] += 1
        self.stats['api_calls'] += 1
        logger.warning(f"✗ 캐시 미스: JQL 검색 - API 호출 필요 [캐시 키: {cache_key}]")
        logger.info(f"   JQL: {jql[:80]}{'...' if len(jql) > 80 else ''}")
        logger.info(f"   max_results: {max_results}, fields: {len(fields) if fields else 0}개")

        result = self.client.search_issues(jql, max_results=max_results, fields=fields)

        # 캐시 저장
        if use_cache:
            self.cache[cache_key] = result
            logger.info(f"✓ 캐시 저장: JQL 검색 (결과 {len(result)}개) [캐시 키: {cache_key}]")

        return result

    def get_all_cached_issues(self) -> List[Dict]:
        """
        캐시에 저장된 모든 이슈 데이터 반환 (중복 제거)

        Returns:
            캐시된 모든 이슈 리스트 (issue key 기준 중복 제거)
        """
        all_issues = []
        seen_keys = set()

        # 캐시에서 JQL 쿼리 결과만 추출
        for cache_key, value in self.cache.items():
            # JQL 쿼리 결과인지 확인
            if '_jql_' in cache_key and isinstance(value, list):
                for issue in value:
                    # 이슈 키로 중복 체크
                    issue_key = issue.get('key')
                    if issue_key and issue_key not in seen_keys:
                        seen_keys.add(issue_key)
                        all_issues.append(issue)

        logger.info(f"📦 캐시된 이슈 조회: {len(all_issues)}개 (고유 이슈)")
        return all_issues

    def get_cache_summary(self) -> Dict[str, Any]:
        """
        캐시 내용 요약 정보 반환

        Returns:
            {
                'total_cached_items': int,
                'jql_queries': int,
                'individual_issues': int,
                'unique_issues': int,
                'month': str
            }
        """
        jql_count = 0
        issue_count = 0
        all_keys = set()

        for cache_key, value in self.cache.items():
            if '_jql_' in cache_key:
                jql_count += 1
                if isinstance(value, list):
                    for issue in value:
                        issue_key = issue.get('key')
                        if issue_key:
                            all_keys.add(issue_key)
            else:
                issue_count += 1

        return {
            'total_cached_items': len(self.cache),
            'jql_queries': jql_count,
            'individual_issues': issue_count,
            'unique_issues': len(all_keys),
            'month': self.current_month
        }

    def clear_cache(self):
        """캐시 수동 초기화"""
        old_count = len(self.cache)
        self.cache.clear()
        logger.info(f"🗑️  캐시 초기화: {old_count}개 항목 삭제")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 조회

        Returns:
            {
                "total_requests": int,
                "cache_hits": int,
                "cache_misses": int,
                "hit_rate": str,
                "api_calls": int,
                "cached_items": int,
                "current_month": str
            }
        """
        total = self.stats['total_requests']
        hits = self.stats['cache_hits']
        hit_rate = f"{(hits / total * 100):.1f}%" if total > 0 else "0.0%"

        return {
            'total_requests': total,
            'cache_hits': hits,
            'cache_misses': self.stats['cache_misses'],
            'hit_rate': hit_rate,
            'api_calls': self.stats['api_calls'],
            'cached_items': len(self.cache),
            'current_month': self.current_month
        }

    def print_cache_stats(self):
        """캐시 통계를 콘솔에 출력"""
        stats = self.get_cache_stats()

        print("\n" + "="*60)
        print("📊 Jira API 캐시 통계")
        print("="*60)
        print(f"총 요청:       {stats['total_requests']:>6}건")
        print(f"캐시 히트:     {stats['cache_hits']:>6}건")
        print(f"캐시 미스:     {stats['cache_misses']:>6}건")
        print(f"히트율:        {stats['hit_rate']:>6}")
        print(f"API 호출:      {stats['api_calls']:>6}건")
        print(f"캐시 항목:     {stats['cached_items']:>6}개")
        print(f"현재 월:       {stats['current_month']}")
        print("="*60 + "\n")
