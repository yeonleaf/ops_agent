#!/usr/bin/env python3
"""
로깅 설정 테스트
enhanced_ticket_ui_v2.py와 동일한 로깅 설정으로 테스트
"""

import logging
from module.logging_config import setup_logging

def test_logging():
    """로깅 설정 테스트"""
    print("🧪 로깅 설정 테스트 시작")

    # 로깅 설정 초기화 (enhanced_ticket_ui_v2.py와 동일)
    setup_logging(level="INFO", log_file="logs/ticket_ui.log", console_output=True)
    logger = logging.getLogger(__name__)

    # 테스트 로그 메시지들
    logger.info("🔍 테스트 로그 1: INFO 레벨 메시지")
    logger.warning("⚠️ 테스트 로그 2: WARNING 레벨 메시지")
    logger.error("❌ 테스트 로그 3: ERROR 레벨 메시지")

    print("✅ 로깅 테스트 완료")
    print("📄 logs/ticket_ui.log 파일을 확인해주세요")

if __name__ == "__main__":
    test_logging()