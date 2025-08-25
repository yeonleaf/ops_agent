"""
로깅 설정 모듈
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: str = None,
    console_output: bool = True
) -> None:
    """
    로깅 설정을 초기화합니다.
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (선택사항)
        console_output: 콘솔 출력 여부
    """
    # 로그 레벨 설정
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 로그 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러
    if log_file:
        # 로그 디렉토리 생성
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 특정 모듈의 로그 레벨 조정
    logging.getLogger('module').setLevel(numeric_level)
    
    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('fitz').setLevel(logging.WARNING)
    logging.getLogger('openpyxl').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    지정된 이름의 로거를 반환합니다.
    
    Args:
        name: 로거 이름
        
    Returns:
        로거 인스턴스
    """
    return logging.getLogger(name) 