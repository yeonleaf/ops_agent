#!/usr/bin/env python3
"""
Whoosh 기반 키워드 검색 관리자
디스크 기반 인덱스를 사용하여 메모리 효율적인 키워드 검색 제공
"""

import os
import logging
from typing import List, Dict, Any, Optional
from whoosh import index
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh.query import *
from whoosh.analysis import StandardAnalyzer
from text_preprocessor import preprocess_for_embedding
from keyword_extractor import KeywordExtractor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhooshSearchManager:
    """Whoosh 기반 키워드 검색 관리자"""
    
    def __init__(self, index_dir: str = "whoosh_index"):
        self.index_dir = index_dir
        self.keyword_extractor = KeywordExtractor()
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """인덱스 존재 여부 확인"""
        if not index.exists_in(self.index_dir):
            raise FileNotFoundError(f"Whoosh 인덱스가 존재하지 않습니다: {self.index_dir}. 먼저 build_whoosh_index.py를 실행하세요.")
    
    def search_with_whoosh(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Whoosh를 사용한 키워드 검색 수행 (다중 전략)
        
        Args:
            query: 검색 쿼리
            k: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        try:
            logger.info(f"🔍 Whoosh 키워드 검색 시작: '{query}'")
            
            # 인덱스 열기
            ix = index.open_dir(self.index_dir)
            
            with ix.searcher() as searcher:
                search_results = []
                
                # 전략 1: 키워드 추출 후 검색
                try:
                    keywords = self.keyword_extractor.extract_keywords(query)
                    keyword_query = " ".join(keywords)
                    logger.info(f"🔑 추출된 키워드: {keywords}")
                    
                    # 쿼리 전처리
                    preprocessed_query = preprocess_for_embedding(keyword_query)
                    
                    # 쿼리 파서 설정
                    parser = QueryParser("content", ix.schema)
                    search_query = parser.parse(preprocessed_query)
                    results = searcher.search(search_query, limit=k)
                    
                    for i, hit in enumerate(results):
                        result = {
                            'id': hit['id'],
                            'content': hit['content'],
                            'metadata': {
                                'source_type': hit.get('source_type', 'unknown'),
                                'search_type': 'whoosh_keywords',
                                'search_rank': i + 1,
                                'score': hit.score,
                                'extracted_keywords': keywords
                            },
                            'similarity_score': hit.score,
                            'source': 'whoosh_search'
                        }
                        search_results.append(result)
                    
                    logger.info(f"✅ 키워드 검색 완료: {len(search_results)}개 결과")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 키워드 검색 실패: {e}")
                
                # 전략 2: 원본 쿼리로 직접 검색 (키워드 검색이 실패한 경우)
                if not search_results:
                    try:
                        logger.info("🔄 원본 쿼리로 직접 검색 시도...")
                        parser = QueryParser("content", ix.schema)
                        search_query = parser.parse(query)
                        results = searcher.search(search_query, limit=k)
                        
                        for i, hit in enumerate(results):
                            result = {
                                'id': hit['id'],
                                'content': hit['content'],
                                'metadata': {
                                    'source_type': hit.get('source_type', 'unknown'),
                                    'search_type': 'whoosh_direct',
                                    'search_rank': i + 1,
                                    'score': hit.score
                                },
                                'similarity_score': hit.score,
                                'source': 'whoosh_search'
                            }
                            search_results.append(result)
                        
                        logger.info(f"✅ 직접 검색 완료: {len(search_results)}개 결과")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ 직접 검색 실패: {e}")
                
                # 전략 3: 와일드카드 검색 (여전히 결과가 없는 경우)
                if not search_results:
                    try:
                        logger.info("🔄 와일드카드 검색 시도...")
                        # 쿼리의 각 단어에 와일드카드 추가
                        words = query.split()
                        wildcard_query = " OR ".join([f"{word}*" for word in words if len(word) > 2])
                        
                        if wildcard_query:
                            parser = QueryParser("content", ix.schema)
                            search_query = parser.parse(wildcard_query)
                            results = searcher.search(search_query, limit=k)
                            
                            for i, hit in enumerate(results):
                                result = {
                                    'id': hit['id'],
                                    'content': hit['content'],
                                    'metadata': {
                                        'source_type': hit.get('source_type', 'unknown'),
                                        'search_type': 'whoosh_wildcard',
                                        'search_rank': i + 1,
                                        'score': hit.score
                                    },
                                    'similarity_score': hit.score,
                                    'source': 'whoosh_search'
                                }
                                search_results.append(result)
                            
                            logger.info(f"✅ 와일드카드 검색 완료: {len(search_results)}개 결과")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ 와일드카드 검색 실패: {e}")
                
                logger.info(f"✅ Whoosh 검색 최종 완료: {len(search_results)}개 결과")
                return search_results
                
        except Exception as e:
            logger.error(f"❌ Whoosh 검색 실패: {e}")
            return []
    
    def search_with_multifield(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        다중 필드 검색 (content, metadata)
        
        Args:
            query: 검색 쿼리
            k: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        try:
            logger.info(f"🔍 Whoosh 다중 필드 검색 시작: '{query}'")
            
            # 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(query)
            keyword_query = " ".join(keywords)
            
            # 쿼리 전처리
            preprocessed_query = preprocess_for_embedding(keyword_query)
            
            # 인덱스 열기
            ix = index.open_dir(self.index_dir)
            
            with ix.searcher() as searcher:
                # 다중 필드 쿼리 파서 설정
                parser = MultifieldParser(["content", "metadata"], ix.schema)
                
                # 검색 쿼리 생성
                search_query = parser.parse(preprocessed_query)
                
                # 검색 수행
                results = searcher.search(search_query, limit=k)
                
                # 결과 변환
                search_results = []
                for i, hit in enumerate(results):
                    result = {
                        'id': hit['id'],
                        'content': hit['content'],
                        'metadata': {
                            'source_type': hit.get('source_type', 'unknown'),
                            'search_type': 'whoosh_multifield',
                            'search_rank': i + 1,
                            'score': hit.score,
                            'extracted_keywords': keywords
                        },
                        'similarity_score': hit.score,
                        'source': 'whoosh_search'
                    }
                    search_results.append(result)
                
                logger.info(f"✅ Whoosh 다중 필드 검색 완료: {len(search_results)}개 결과")
                return search_results
                
        except Exception as e:
            logger.error(f"❌ Whoosh 다중 필드 검색 실패: {e}")
            return []
    
    def get_index_stats(self) -> Dict[str, Any]:
        """인덱스 통계 정보 반환"""
        try:
            ix = index.open_dir(self.index_dir)
            with ix.searcher() as searcher:
                return {
                    'total_documents': searcher.doc_count(),
                    'index_dir': self.index_dir,
                    'schema_fields': list(ix.schema.names())
                }
        except Exception as e:
            logger.error(f"❌ 인덱스 통계 조회 실패: {e}")
            return {}

def create_whoosh_search_manager(index_dir: str = "whoosh_index") -> WhooshSearchManager:
    """WhooshSearchManager 인스턴스 생성"""
    return WhooshSearchManager(index_dir)
