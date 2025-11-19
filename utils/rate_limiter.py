#!/usr/bin/env python3
"""
Rate Limiter - API 호출 속도 제한 및 429 에러 방어
"""

import time
import logging
from collections import deque
from typing import Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    토큰 버킷(Token Bucket) 알고리즘 기반 Rate Limiter

    특징:
    - 분당 최대 요청 수 제한
    - 버스트 트래픽 허용
    - Thread-safe (단일 프로세스 내)
    """

    def __init__(self, max_requests_per_minute: int = 60, burst_size: Optional[int] = None):
        """
        Args:
            max_requests_per_minute: 분당 최대 요청 수
            burst_size: 버스트 허용 크기 (None이면 max_requests_per_minute과 동일)
        """
        self.max_requests = max_requests_per_minute
        self.burst_size = burst_size or max_requests_per_minute
        self.window_seconds = 60.0
        self.min_interval = self.window_seconds / max_requests_per_minute

        # 슬라이딩 윈도우 방식: 최근 요청 타임스탬프 저장
        self.request_times = deque(maxlen=self.burst_size)

        logger.info(f"✅ RateLimiter 초기화: {max_requests_per_minute}req/min (burst={self.burst_size})")

    def acquire(self, timeout: float = 60.0) -> bool:
        """
        요청 토큰 획득 (블로킹)

        Args:
            timeout: 최대 대기 시간 (초)

        Returns:
            토큰 획득 성공 여부
        """
        start_time = time.time()

        while True:
            now = time.time()

            # 만료된 요청 제거 (60초 이전)
            cutoff_time = now - self.window_seconds
            while self.request_times and self.request_times[0] < cutoff_time:
                self.request_times.popleft()

            # 현재 윈도우 내 요청 수 확인
            current_requests = len(self.request_times)

            if current_requests < self.max_requests:
                # 토큰 사용 가능
                self.request_times.append(now)

                if current_requests > 0:
                    # 마지막 요청과의 간격 확인
                    last_request_time = self.request_times[-2] if len(self.request_times) > 1 else 0
                    interval = now - last_request_time

                    if interval < self.min_interval:
                        wait_time = self.min_interval - interval
                        logger.debug(f"⏱️  Rate limit: {wait_time:.2f}초 대기 (간격 유지)")
                        time.sleep(wait_time)

                return True

            # 타임아웃 체크
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"⚠️  Rate limit 타임아웃 ({timeout}초)")
                return False

            # 가장 오래된 요청이 만료될 때까지 대기
            oldest_request = self.request_times[0]
            wait_time = min(
                (oldest_request + self.window_seconds) - now,
                timeout - elapsed
            )

            if wait_time > 0:
                logger.info(f"🚦 Rate limit 도달: {wait_time:.1f}초 대기 중... ({current_requests}/{self.max_requests})")
                time.sleep(wait_time)

    def get_current_usage(self) -> dict:
        """
        현재 사용량 통계 반환

        Returns:
            {
                "current_requests": int,
                "max_requests": int,
                "usage_percent": float,
                "available_tokens": int
            }
        """
        now = time.time()
        cutoff_time = now - self.window_seconds

        # 만료된 요청 제거
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()

        current_requests = len(self.request_times)
        available = self.max_requests - current_requests
        usage_percent = (current_requests / self.max_requests) * 100

        return {
            "current_requests": current_requests,
            "max_requests": self.max_requests,
            "usage_percent": usage_percent,
            "available_tokens": available
        }


def rate_limited(
    max_requests_per_minute: int = 60,
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    max_backoff: float = 60.0
):
    """
    Rate limiting 데코레이터 (with exponential backoff)

    Args:
        max_requests_per_minute: 분당 최대 요청 수
        max_retries: 429 에러 발생 시 최대 재시도 횟수
        initial_backoff: 초기 백오프 시간 (초)
        max_backoff: 최대 백오프 시간 (초)

    Example:
        @rate_limited(max_requests_per_minute=30, max_retries=5)
        def call_openai_api():
            return client.chat.completions.create(...)
    """
    limiter = RateLimiter(max_requests_per_minute=max_requests_per_minute)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Rate limiting 적용
            if not limiter.acquire(timeout=120.0):
                raise Exception("Rate limit 타임아웃: 2분 내에 토큰을 획득할 수 없습니다")

            # 재시도 로직 (Exponential Backoff)
            last_exception = None
            backoff = initial_backoff

            for attempt in range(max_retries + 1):
                try:
                    # 함수 실행
                    result = func(*args, **kwargs)

                    # 성공 시 통계 로그
                    if attempt > 0:
                        logger.info(f"✅ 재시도 성공 (시도 {attempt + 1}/{max_retries + 1})")

                    return result

                except Exception as e:
                    error_msg = str(e).lower()

                    # 429 에러 또는 rate limit 관련 에러인지 확인
                    is_rate_limit_error = (
                        "429" in error_msg or
                        "too many requests" in error_msg or
                        "rate limit" in error_msg or
                        "quota" in error_msg
                    )

                    if is_rate_limit_error and attempt < max_retries:
                        # Exponential backoff
                        wait_time = min(backoff * (2 ** attempt), max_backoff)
                        logger.warning(
                            f"⚠️  Rate limit 에러 (429) 감지: {wait_time:.1f}초 후 재시도 "
                            f"(시도 {attempt + 1}/{max_retries + 1})"
                        )
                        time.sleep(wait_time)
                        last_exception = e
                        continue

                    # 다른 에러이거나 최대 재시도 도달
                    logger.error(f"❌ API 호출 실패: {e}")
                    raise

            # 모든 재시도 실패
            logger.error(f"❌ 최대 재시도 횟수 도달 ({max_retries + 1}회)")
            raise last_exception

        return wrapper

    return decorator


def get_rate_limiter_stats(limiter: RateLimiter) -> str:
    """
    Rate limiter 통계를 문자열로 반환

    Args:
        limiter: RateLimiter 인스턴스

    Returns:
        통계 문자열
    """
    stats = limiter.get_current_usage()
    return (
        f"Rate Limit 사용량: {stats['current_requests']}/{stats['max_requests']} "
        f"({stats['usage_percent']:.1f}%) | "
        f"사용 가능: {stats['available_tokens']}개"
    )


# 전역 rate limiter (싱글톤)
_global_limiter: Optional[RateLimiter] = None


def get_global_rate_limiter(max_requests_per_minute: int = 60) -> RateLimiter:
    """
    전역 rate limiter 반환 (싱글톤)

    Args:
        max_requests_per_minute: 분당 최대 요청 수

    Returns:
        전역 RateLimiter 인스턴스
    """
    global _global_limiter

    if _global_limiter is None:
        _global_limiter = RateLimiter(max_requests_per_minute=max_requests_per_minute)
        logger.info(f"🌍 전역 RateLimiter 생성: {max_requests_per_minute}req/min")

    return _global_limiter


if __name__ == "__main__":
    # 테스트
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 RateLimiter 테스트")
    print("=" * 60)

    # 테스트 1: 기본 rate limiting
    print("\n[테스트 1] 기본 rate limiting (10req/min)")
    limiter = RateLimiter(max_requests_per_minute=10)

    for i in range(3):
        limiter.acquire()
        print(f"  요청 {i + 1}: {get_rate_limiter_stats(limiter)}")

    # 테스트 2: 데코레이터 사용
    print("\n[테스트 2] rate_limited 데코레이터")

    call_count = 0

    @rate_limited(max_requests_per_minute=5, max_retries=2)
    def test_api_call():
        global call_count
        call_count += 1
        print(f"  API 호출 {call_count}")

        # 두 번째 호출에서 429 에러 시뮬레이션
        if call_count == 2:
            raise Exception("429 Too Many Requests")

        return "Success"

    try:
        test_api_call()  # 1번째
        test_api_call()  # 2번째 (에러 발생 → 재시도)
        test_api_call()  # 3번째
    except Exception as e:
        print(f"  에러: {e}")

    print("\n✅ 테스트 완료")
