#!/usr/bin/env python3
"""
로깅 시스템 테스트 스크립트
"""

from module.logging_config import setup_session_logging, get_logger
import time


def test_basic_logging():
    """기본 로깅 기능 테스트"""
    # 세션별 로깅 설정
    session_id = setup_session_logging(level="DEBUG", console_output=True)

    logger = get_logger(__name__)

    # 다양한 로그 레벨 테스트
    logger.debug("디버그 메시지 - 개발자용 상세 정보")
    logger.info("정보 메시지 - 일반적인 작업 진행 상황")
    logger.warning("경고 메시지 - 주의가 필요한 상황")
    logger.error("에러 메시지 - 오류 발생")

    # 세션 정보 로그
    logger.info(f"현재 세션 ID: {session_id}")

    return session_id


def test_multiple_modules():
    """여러 모듈에서의 로깅 테스트"""
    # 다른 모듈에서의 로거 생성 시뮬레이션
    modules = ['oauth_auth_agent', 'gmail_api_client', 'sqlite_ticket_models']

    for module_name in modules:
        logger = get_logger(module_name)
        logger.info(f"{module_name} 모듈에서 로그 테스트")
        logger.debug(f"{module_name} 모듈 디버그 정보")


def test_exception_logging():
    """예외 처리 로깅 테스트"""
    logger = get_logger(__name__)

    try:
        # 의도적으로 예외 발생
        result = 1 / 0
    except ZeroDivisionError as e:
        logger.error(f"예외 발생: {e}", exc_info=True)
        logger.error("예외 처리 완료")


if __name__ == "__main__":
    print("🚀 로깅 시스템 테스트 시작...")

    # 1. 기본 로깅 테스트
    session_id = test_basic_logging()

    # 2. 다중 모듈 로깅 테스트
    test_multiple_modules()

    # 3. 예외 로깅 테스트
    test_exception_logging()

    print(f"✅ 테스트 완료. 세션 ID: {session_id}")
    print("📁 logs 폴더에 로그 파일을 확인하세요.")