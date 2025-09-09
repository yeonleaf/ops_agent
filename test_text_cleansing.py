#!/usr/bin/env python3
"""
텍스트 정제 함수 테스트
"""

import re

def cleanse_text(text: str) -> str:
    """
    임베딩 전 텍스트 정제 - 잡음 제거
    반복되는 메타데이터 패턴을 제거하여 의미있는 텍스트만 추출
    """
    if not text:
        return ""
    
    # 1. Jira 티켓 키 패턴 제거 [BTVO-NNNNN]
    text = re.sub(r'\[BTVO-\s?\d+\]', '', text)
    
    # 2. NCMS 패턴 제거 [NCMS]
    text = re.sub(r'\[NCMS\]', '', text)
    
    # 3. 날짜 패턴 제거 (MM/DD) 또는 (YYYY-MM-DD)
    text = re.sub(r'\(\d{1,2}/\d{1,2}\)', '', text)
    text = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', text)
    
    # 4. 기타 불필요한 패턴들
    text = re.sub(r'\[.*?\]', '', text)  # 대괄호 안의 모든 내용 제거
    text = re.sub(r'\(.*?\)', '', text)  # 소괄호 안의 모든 내용 제거
    
    # 5. 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 6. 앞뒤 공백 제거
    text = text.strip()
    
    return text

def test_text_cleansing():
    """텍스트 정제 테스트"""
    test_cases = [
        "[BTVO-51247] [NCMS] Admin 로직 및 샘플 데이터 (6/14)",
        "[BTVO-12345] 서버 접속 불가 문제",
        "[NCMS] 데이터베이스 연결 오류 (2024-01-01)",
        "일반적인 텍스트입니다",
        "[BTVO-99999] [NCMS] (12/25) 크리스마스 이슈",
        "복잡한 [BTVO-11111] 패턴과 (날짜) 혼합 텍스트",
        "",  # 빈 문자열
        "   ",  # 공백만 있는 문자열
    ]
    
    print("🧪 텍스트 정제 테스트")
    print("=" * 60)
    
    for i, original in enumerate(test_cases, 1):
        cleaned = cleanse_text(original)
        print(f"테스트 {i}:")
        print(f"  원본: '{original}'")
        print(f"  정제: '{cleaned}'")
        print()

if __name__ == "__main__":
    test_text_cleansing()
