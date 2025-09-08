#!/usr/bin/env python3
"""
간단한 EnsembleRetriever 디버깅 스크립트
메모리 사용량을 줄여서 BM25와 Vector 검색기를 독립적으로 테스트합니다.
"""

import logging
from typing import List, Dict, Any
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from vector_db_models import VectorDBManager
from text_preprocessor import preprocess_for_embedding
from keyword_extractor import KeywordExtractor
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_bm25_only():
    """BM25 Retriever만 단독 테스트"""
    logger.info("🔍 BM25 Retriever 단독 테스트 시작")
    
    # VectorDBManager 초기화
    vector_db = VectorDBManager()
    
    # 키워드 추출기 초기화
    keyword_extractor = KeywordExtractor()
    
    # 테스트 쿼리
    test_query = "서버 접속이 안 되고 HTTP 500 오류가 나는 문제 있나요?"
    
    try:
        # 1. 문서 수집 (제한된 수)
        logger.info("📚 문서 수집 중...")
        file_chunks = vector_db.get_all_file_chunks()
        logger.info(f"✅ {len(file_chunks)}개 파일 청크 수집")
        
        # 처음 100개 문서만 사용 (메모리 절약)
        limited_chunks = file_chunks[:100]
        
        # 2. Document 객체 생성
        documents = []
        for chunk in limited_chunks:
            content = chunk.get('content', '')
            if content and len(content.strip()) > 0:
                metadata = chunk.get('metadata', {})
                metadata.update({
                    'source_type': 'file_chunk',
                    'chunk_id': chunk.get('chunk_id', ''),
                    'file_name': chunk.get('file_name', '')
                })
                documents.append(Document(page_content=content, metadata=metadata))
        
        logger.info(f"✅ {len(documents)}개 Document 객체 생성")
        
        # 3. BM25Retriever 생성
        logger.info("🔍 BM25Retriever 생성 중...")
        bm25_retriever = BM25Retriever.from_documents(documents, k=5)
        logger.info("✅ BM25Retriever 생성 완료")
        
        # 4. 키워드 추출
        keywords = keyword_extractor.extract_keywords(test_query)
        keyword_query = " ".join(keywords)
        logger.info(f"🔑 추출된 키워드: {keywords}")
        logger.info(f"🔍 BM25 검색 쿼리: '{keyword_query}'")
        
        # 5. 쿼리 전처리
        preprocessed_query = preprocess_for_embedding(keyword_query)
        logger.info(f"🔍 전처리된 쿼리: '{preprocessed_query}'")
        
        # 6. BM25 검색 수행
        logger.info("🔍 BM25 검색 수행 중...")
        documents = bm25_retriever.get_relevant_documents(preprocessed_query)
        
        # 7. 결과 출력
        logger.info(f"✅ BM25 검색 완료: {len(documents)}개 결과")
        for i, doc in enumerate(documents):
            logger.info(f"  {i+1}. 내용: {doc.page_content[:100]}...")
            logger.info(f"     메타데이터: {doc.metadata}")
            logger.info("")
        
        return documents
        
    except Exception as e:
        logger.error(f"❌ BM25 테스트 실패: {e}")
        return []

def test_vector_only():
    """Vector Retriever만 단독 테스트"""
    logger.info("🔍 Vector Retriever 단독 테스트 시작")
    
    # VectorDBManager 초기화
    vector_db = VectorDBManager()
    
    # 테스트 쿼리
    test_query = "서버 접속이 안 되고 HTTP 500 오류가 나는 문제 있나요?"
    
    try:
        # 1. 쿼리 전처리
        preprocessed_query = preprocess_for_embedding(test_query)
        logger.info(f"🔍 전처리된 쿼리: '{preprocessed_query}'")
        
        # 2. Vector 검색 수행
        logger.info("🔍 Vector 검색 수행 중...")
        results = vector_db.search_similar_file_chunks(preprocessed_query, n_results=5)
        
        # 3. 결과 출력
        logger.info(f"✅ Vector 검색 완료: {len(results)}개 결과")
        for i, result in enumerate(results):
            content = result.get('content', '')
            logger.info(f"  {i+1}. 내용: {content[:100]}...")
            logger.info(f"     유사도: {result.get('similarity_score', 0.0)}")
            logger.info(f"     메타데이터: {result.get('metadata', {})}")
            logger.info("")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Vector 테스트 실패: {e}")
        return []

def analyze_documents():
    """문서 분석"""
    logger.info("📊 문서 분석 시작")
    
    vector_db = VectorDBManager()
    
    try:
        # 파일 청크 분석
        file_chunks = vector_db.get_all_file_chunks()
        logger.info(f"📄 파일 청크 수: {len(file_chunks)}")
        
        if file_chunks:
            # 샘플 문서 내용 분석
            sample_chunk = file_chunks[0]
            content = sample_chunk.get('content', '')
            logger.info(f"📄 샘플 문서 내용:")
            logger.info(f"  - 길이: {len(content)}자")
            logger.info(f"  - 내용: {content[:200]}...")
            logger.info(f"  - 메타데이터: {sample_chunk.get('metadata', {})}")
            
            # 내용 길이 분포
            lengths = [len(chunk.get('content', '')) for chunk in file_chunks[:10]]
            avg_length = sum(lengths) / len(lengths)
            logger.info(f"📊 평균 내용 길이 (샘플 10개): {avg_length:.1f}자")
        
    except Exception as e:
        logger.error(f"❌ 문서 분석 실패: {e}")

def main():
    """메인 함수"""
    logger.info("=" * 80)
    logger.info("🔍 EnsembleRetriever 간단 디버깅 테스트")
    logger.info("=" * 80)
    
    # 1. 문서 분석
    analyze_documents()
    
    logger.info("\n" + "=" * 80)
    logger.info("🔍 BM25 Retriever 단독 테스트")
    logger.info("=" * 80)
    
    # 2. BM25 테스트
    bm25_results = test_bm25_only()
    
    logger.info("\n" + "=" * 80)
    logger.info("🔍 Vector Retriever 단독 테스트")
    logger.info("=" * 80)
    
    # 3. Vector 테스트
    vector_results = test_vector_only()
    
    # 4. 결과 요약
    logger.info("\n" + "=" * 80)
    logger.info("📊 테스트 결과 요약")
    logger.info("=" * 80)
    logger.info(f"BM25 검색 결과: {len(bm25_results)}개")
    logger.info(f"Vector 검색 결과: {len(vector_results)}개")
    
    if bm25_results and vector_results:
        logger.info("✅ 두 검색기 모두 결과를 반환했습니다.")
    elif bm25_results:
        logger.info("⚠️ BM25만 결과를 반환했습니다.")
    elif vector_results:
        logger.info("⚠️ Vector만 결과를 반환했습니다.")
    else:
        logger.info("❌ 두 검색기 모두 결과를 반환하지 못했습니다.")

if __name__ == "__main__":
    main()
