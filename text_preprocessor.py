#!/usr/bin/env python3
"""
임베딩용 텍스트 전처리 모듈
RAG 시스템의 1차 검색 성능 향상을 위한 텍스트 정제
"""

import re
from typing import Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextPreprocessor:
    """임베딩용 텍스트 전처리기"""
    
    def __init__(self):
        """전처리기 초기화"""
        self._compile_patterns()
        logger.info("텍스트 전처리기 초기화 완료")
    
    def _compile_patterns(self):
        """정규식 패턴 컴파일"""
        # 1. 대괄호로 묶인 프로젝트 코드 및 티켓 ID 패턴
        self.bracket_patterns = [
            r'\[NCMS\]',                    # [NCMS]
            r'\[BTVO[-\s]*\d+\]',          # [BTVO-12345] 또는 [BTVO 12345]
            r'\[[A-Z]{2,}[-\s]*\d+\]',     # [PROJ-123] 형태의 프로젝트 코드
            r'\[[A-Z]{2,}\]',              # [PROJ] 형태의 프로젝트 코드
            r'\[T-\d+\]',                  # [T-123] 형태의 티켓 ID
            r'\[[A-Z]+-\d+\]',             # [ABC-123] 형태의 일반적인 티켓 ID
        ]
        
        # 2. 필드 이름 접두사 패턴
        self.field_prefix_patterns = [
            r'^요약\s*[:：]\s*',           # 요약: 또는 요약：
            r'^설명\s*[:：]\s*',           # 설명: 또는 설명：
            r'^제목\s*[:：]\s*',           # 제목: 또는 제목：
            r'^내용\s*[:：]\s*',           # 내용: 또는 내용：
            r'^댓글\s*[:：]\s*',           # 댓글: 또는 댓글：
            r'^코멘트\s*[:：]\s*',         # 코멘트: 또는 코멘트：
            r'^Summary\s*[:：]\s*',        # Summary: 또는 Summary：
            r'^Description\s*[:：]\s*',    # Description: 또는 Description：
            r'^Title\s*[:：]\s*',          # Title: 또는 Title：
            r'^Content\s*[:：]\s*',        # Content: 또는 Content：
            r'^Comment\s*[:：]\s*',        # Comment: 또는 Comment：
        ]
        
        # 3. 괄호로 묶인 날짜 정보 패턴
        self.date_patterns = [
            r'\(\d{1,2}/\d{1,2}~\d{1,2}\)',     # (5/8~12)
            r'\(\d{1,2}/\d{1,2}\)',             # (5/8)
            r'\(\d{4}-\d{1,2}-\d{1,2}\)',       # (2024-01-15)
            r'\(\d{1,2}월\s*\d{1,2}일\)',       # (1월 15일)
            r'\(\d{1,2}/\d{1,2}/\d{4}\)',       # (1/15/2024)
            r'\(\d{4}\.\d{1,2}\.\d{1,2}\)',     # (2024.01.15)
        ]
        
        # 4. 기타 노이즈 패턴
        self.noise_patterns = [
            r'https?://[^\s]+',              # URL 제거
            r'www\.[^\s]+',                  # www.로 시작하는 링크
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # 이메일 주소
            r'#\d+',                         # #123 형태의 해시태그
            r'@\w+',                         # @username 형태의 멘션
            r'\s+',                          # 연속된 공백 (나중에 처리)
        ]
        
        # 모든 패턴을 하나의 정규식으로 컴파일
        all_patterns = (
            self.bracket_patterns + 
            self.field_prefix_patterns + 
            self.date_patterns + 
            self.noise_patterns[:-1]  # 공백 패턴은 별도 처리
        )
        
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_patterns]
        self.whitespace_pattern = re.compile(r'\s+')
    
    def preprocess_for_embedding(self, text: str) -> str:
        """
        임베딩용 텍스트 전처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            전처리된 깨끗한 텍스트
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 원본 텍스트 로깅 (디버깅용)
        original_text = text.strip()
        if len(original_text) > 100:
            logger.debug(f"전처리 전: {original_text[:100]}...")
        else:
            logger.debug(f"전처리 전: {original_text}")
        
        # 1. 기본 정리
        cleaned_text = original_text
        
        # 2. 대괄호 패턴 제거
        for pattern in self.compiled_patterns[:len(self.bracket_patterns)]:
            cleaned_text = pattern.sub('', cleaned_text)
        
        # 3. 필드 접두사 제거
        for pattern in self.compiled_patterns[len(self.bracket_patterns):len(self.bracket_patterns) + len(self.field_prefix_patterns)]:
            cleaned_text = pattern.sub('', cleaned_text)
        
        # 4. 날짜 패턴 제거
        date_start = len(self.bracket_patterns) + len(self.field_prefix_patterns)
        date_end = date_start + len(self.date_patterns)
        for pattern in self.compiled_patterns[date_start:date_end]:
            cleaned_text = pattern.sub('', cleaned_text)
        
        # 5. 기타 노이즈 제거 (URL, 이메일 등)
        noise_start = date_end
        for pattern in self.compiled_patterns[noise_start:]:
            cleaned_text = pattern.sub('', cleaned_text)
        
        # 6. 연속된 공백 정리
        cleaned_text = self.whitespace_pattern.sub(' ', cleaned_text)
        
        # 7. 앞뒤 공백 제거
        cleaned_text = cleaned_text.strip()
        
        # 전처리 결과 로깅 (디버깅용)
        if len(cleaned_text) > 100:
            logger.debug(f"전처리 후: {cleaned_text[:100]}...")
        else:
            logger.debug(f"전처리 후: {cleaned_text}")
        
        # 전처리 효과 로깅
        if len(original_text) != len(cleaned_text):
            reduction_ratio = (len(original_text) - len(cleaned_text)) / len(original_text) * 100
            logger.info(f"텍스트 전처리 완료: {len(original_text)} → {len(cleaned_text)} 문자 ({reduction_ratio:.1f}% 감소)")
        
        return cleaned_text
    
    def preprocess_batch(self, texts: list) -> list:
        """
        여러 텍스트를 일괄 전처리
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            전처리된 텍스트 리스트
        """
        return [self.preprocess_for_embedding(text) for text in texts]
    
    def get_preprocessing_stats(self, original_text: str, cleaned_text: str) -> dict:
        """
        전처리 통계 정보 반환
        
        Args:
            original_text: 원본 텍스트
            cleaned_text: 전처리된 텍스트
            
        Returns:
            전처리 통계 딕셔너리
        """
        if not original_text:
            return {}
        
        original_length = len(original_text)
        cleaned_length = len(cleaned_text)
        reduction_ratio = (original_length - cleaned_length) / original_length * 100 if original_length > 0 else 0
        
        # 제거된 패턴들 분석
        removed_patterns = []
        
        # 대괄호 패턴 제거 확인
        for pattern in self.bracket_patterns:
            if re.search(pattern, original_text, re.IGNORECASE):
                removed_patterns.append(f"대괄호 패턴: {pattern}")
        
        # 필드 접두사 제거 확인
        for pattern in self.field_prefix_patterns:
            if re.search(pattern, original_text, re.IGNORECASE):
                removed_patterns.append(f"필드 접두사: {pattern}")
        
        # 날짜 패턴 제거 확인
        for pattern in self.date_patterns:
            if re.search(pattern, original_text, re.IGNORECASE):
                removed_patterns.append(f"날짜 패턴: {pattern}")
        
        return {
            "original_length": original_length,
            "cleaned_length": cleaned_length,
            "reduction_ratio": reduction_ratio,
            "removed_patterns": removed_patterns,
            "text_shortened": original_length > cleaned_length
        }


# 전역 인스턴스 생성
text_preprocessor = TextPreprocessor()


def preprocess_for_embedding(text: str) -> str:
    """
    임베딩용 텍스트 전처리 (커스텀 전처리 제거됨)
    
    Args:
        text: 원본 텍스트
        
    Returns:
        원문 그대로 반환 (전처리 없음)
    """
    # 커스텀 전처리 제거: 원문 그대로 반환
    return text.strip() if text else ""
    
    # 기존 전처리 코드 (주석 처리됨)
    # return text_preprocessor.preprocess_for_embedding(text)


def preprocess_batch_for_embedding(texts: list) -> list:
    """
    여러 텍스트를 일괄 전처리 (커스텀 전처리 제거됨)
    
    Args:
        texts: 텍스트 리스트
        
    Returns:
        원문 그대로 반환 (전처리 없음)
    """
    # 커스텀 전처리 제거: 원문 그대로 반환
    return [text.strip() if text else "" for text in texts]
    
    # 기존 전처리 코드 (주석 처리됨)
    # return text_preprocessor.preprocess_batch(texts)


def main():
    """테스트용 메인 함수"""
    print("🧪 텍스트 전처리 함수 테스트")
    print("=" * 60)
    
    # 테스트 케이스들
    test_cases = [
        "[NCMS] 서버 접속 불가 문제",
        "요약: [BTVO-12345] 데이터베이스 성능 최적화 (5/8~12)",
        "설명: 메인 서버에 접속이 되지 않습니다. HTTP 500 오류가 발생하고 있습니다.",
        "[T-001] 제목: 사용자 인증 시스템 오류 (2024-01-15)",
        "댓글: 김개발님이 작성한 코멘트입니다. https://example.com 참고하세요.",
        "Summary: [PROJ-456] API 문서 업데이트 (1월 15일)",
        "Description: 새로운 API 엔드포인트에 대한 문서를 작성해야 합니다. @admin 확인 부탁드립니다.",
        "이슈 키: BTVO-39373 제목: [BTVO-39373] [NCMS] release/5.3.44 Admin/API BMT (12/22)",
        "내용: • 이슈 및 문제점 release/5.3.44 Admin/API BMT (12/22) 상세 요청 내역 https://confluence.example.com",
        "Comment: 이 작업은 우선순위가 높습니다. #urgent #bug"
    ]
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n--- 테스트 케이스 {i} ---")
        print(f"원본: {test_text}")
        
        cleaned_text = preprocess_for_embedding(test_text)
        print(f"정제: {cleaned_text}")
        
        # 통계 정보
        stats = text_preprocessor.get_preprocessing_stats(test_text, cleaned_text)
        if stats:
            print(f"통계: {stats['original_length']} → {stats['cleaned_length']} 문자 ({stats['reduction_ratio']:.1f}% 감소)")
            if stats['removed_patterns']:
                print(f"제거된 패턴: {', '.join(stats['removed_patterns'][:3])}")  # 최대 3개만 표시
    
    print("\n" + "=" * 60)
    print("✅ 텍스트 전처리 함수 테스트 완료")


if __name__ == "__main__":
    main()
