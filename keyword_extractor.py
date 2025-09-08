#!/usr/bin/env python3
"""
키워드 추출 모듈
LLM을 이용하여 사용자 쿼리에서 BM25 검색에 적합한 핵심 키워드를 추출합니다.
"""

import logging
from typing import List, Optional
from langchain_openai import AzureChatOpenAI
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger(__name__)

class KeywordExtractor:
    """
    LLM을 이용한 키워드 추출기
    사용자 쿼리에서 BM25 검색에 적합한 핵심 키워드를 추출합니다.
    """
    
    def __init__(self):
        """키워드 추출기 초기화"""
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """Azure OpenAI LLM 초기화"""
        try:
            self.llm = AzureChatOpenAI(
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                temperature=0,  # 일관된 결과를 위해 0으로 설정
                max_tokens=100  # 키워드 추출이므로 짧은 응답
            )
            logger.info("✅ 키워드 추출용 Azure OpenAI LLM 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 키워드 추출용 LLM 초기화 실패: {e}")
            self.llm = None
    
    def extract_keywords(self, query: str) -> List[str]:
        """
        사용자 쿼리에서 핵심 키워드를 추출합니다.
        
        Args:
            query: 사용자의 원본 쿼리
            
        Returns:
            추출된 키워드 리스트
        """
        if not self.llm:
            logger.warning("⚠️ LLM이 초기화되지 않았습니다. 기본 키워드 추출을 사용합니다.")
            return self._fallback_keyword_extraction(query)
        
        try:
            # 키워드 추출 프롬프트
            prompt = self._create_keyword_extraction_prompt(query)
            
            # LLM 호출
            response = self.llm.invoke(prompt)
            keywords_text = response.content.strip()
            
            # 키워드 파싱
            keywords = self._parse_keywords(keywords_text)
            
            logger.info(f"🔍 키워드 추출 완료: '{query}' -> {keywords}")
            return keywords
            
        except Exception as e:
            logger.error(f"❌ 키워드 추출 실패: {e}")
            return self._fallback_keyword_extraction(query)
    
    def _create_keyword_extraction_prompt(self, query: str) -> str:
        """키워드 추출을 위한 프롬프트 생성"""
        return f"""당신은 검색 쿼리 분석 전문가입니다. 다음 사용자 질문에서, 키워드 검색(BM25)에 사용하기에 가장 적합한 핵심 명사, 고유명사, 기술 용어를 3~5개 추출해주세요. 답변은 쉼표로 구분된 단어 목록으로만 제공해야 합니다.

입력: {query}
출력:"""
    
    def _parse_keywords(self, keywords_text: str) -> List[str]:
        """LLM 응답에서 키워드를 파싱합니다."""
        try:
            # 쉼표로 분리하고 공백 제거
            keywords = [keyword.strip() for keyword in keywords_text.split(',')]
            
            # 빈 문자열 제거
            keywords = [keyword for keyword in keywords if keyword]
            
            # 3~5개로 제한
            keywords = keywords[:5]
            
            # 최소 3개가 되도록 보장
            if len(keywords) < 3:
                logger.warning(f"⚠️ 추출된 키워드가 3개 미만입니다: {keywords}")
            
            return keywords
            
        except Exception as e:
            logger.error(f"❌ 키워드 파싱 실패: {e}")
            return []
    
    def _fallback_keyword_extraction(self, query: str) -> List[str]:
        """LLM 실패 시 사용할 기본 키워드 추출"""
        try:
            # 간단한 키워드 추출 (공백으로 분리)
            words = query.split()
            
            # 불용어 제거 (간단한 버전)
            stop_words = {'있나요', '있나', '있어요', '있습니다', '있습니까', '문제', '도움이', '필요합니다', '관련', '어디', '어떤', '무엇', '어떻게', '왜', '언제', '어느', '이', '그', '저', '가', '을', '를', '에', '에서', '로', '으로', '와', '과', '의', '는', '은', '이', '가', '을', '를', '에', '에서', '로', '으로', '와', '과', '의', '는', '은'}
            
            keywords = [word for word in words if word not in stop_words and len(word) > 1]
            
            # 3~5개로 제한
            keywords = keywords[:5]
            
            # 최소 3개가 되도록 보장
            if len(keywords) < 3:
                keywords = words[:3]  # 원본 단어 사용
            
            logger.info(f"🔍 기본 키워드 추출: '{query}' -> {keywords}")
            return keywords
            
        except Exception as e:
            logger.error(f"❌ 기본 키워드 추출 실패: {e}")
            return ['검색', '쿼리', '문제']  # 최후의 수단

def create_keyword_extractor() -> KeywordExtractor:
    """KeywordExtractor 인스턴스 생성"""
    return KeywordExtractor()
