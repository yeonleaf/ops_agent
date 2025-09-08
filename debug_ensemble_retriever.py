#!/usr/bin/env python3
"""
EnsembleRetriever 디버깅 스크립트
Vector Retriever와 BM25 Retriever를 독립적으로 테스트하여 문제를 진단합니다.
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

class EnsembleRetrieverDebugger:
    """EnsembleRetriever 디버깅 클래스"""
    
    def __init__(self):
        self.vector_db_manager = VectorDBManager()
        self.keyword_extractor = KeywordExtractor()
        self.documents = []
        self.bm25_retriever = None
        self.vector_retriever = None
        
        # 문서 수집 및 검색기 초기화
        self._collect_documents()
        self._setup_retrievers()
    
    def _collect_documents(self):
        """모든 문서를 수집하여 Document 객체 생성"""
        try:
            logger.info("📚 문서 수집 시작...")
            
            # 1. 파일 청크 문서 수집
            file_chunks_docs = self._get_file_chunks()
            self.documents.extend(file_chunks_docs)
            logger.info(f"✅ 파일 청크 문서 {len(file_chunks_docs)}개 수집")
            
            # 2. 메일 문서 수집
            mail_docs = self._get_mail_documents()
            self.documents.extend(mail_docs)
            logger.info(f"✅ 메일 문서 {len(mail_docs)}개 수집")
            
            # 3. 구조적 청크 문서 수집
            structured_docs = self._get_structured_documents()
            self.documents.extend(structured_docs)
            logger.info(f"✅ 구조적 청크 문서 {len(structured_docs)}개 수집")
            
            logger.info(f"✅ 총 {len(self.documents)}개 문서 수집 완료")
            
        except Exception as e:
            logger.error(f"❌ 문서 수집 실패: {e}")
            self.documents = []
    
    def _get_file_chunks(self) -> List[Document]:
        """파일 청크 문서들을 Document 객체로 변환"""
        documents = []
        try:
            file_chunks = self.vector_db_manager.get_all_file_chunks()
            for chunk in file_chunks:
                content = chunk.get('content', '')
                if content and len(content.strip()) > 0:
                    metadata = chunk.get('metadata', {})
                    metadata.update({
                        'source_type': 'file_chunk',
                        'chunk_id': chunk.get('chunk_id', ''),
                        'file_name': chunk.get('file_name', '')
                    })
                    documents.append(Document(page_content=content, metadata=metadata))
        except Exception as e:
            logger.error(f"파일 청크 문서 수집 실패: {e}")
        return documents
    
    def _get_mail_documents(self) -> List[Document]:
        """메일 문서들을 Document 객체로 변환"""
        documents = []
        try:
            mails = self.vector_db_manager.get_all_mails()
            for mail in mails:
                content = mail.get('content', '')
                if content and len(content.strip()) > 0:
                    metadata = mail.get('metadata', {})
                    metadata.update({
                        'source_type': 'mail',
                        'message_id': mail.get('message_id', ''),
                        'subject': mail.get('subject', ''),
                        'sender': mail.get('sender', '')
                    })
                    documents.append(Document(page_content=content, metadata=metadata))
        except Exception as e:
            logger.error(f"메일 문서 수집 실패: {e}")
        return documents
    
    def _get_structured_documents(self) -> List[Document]:
        """구조적 청크 문서들을 Document 객체로 변환"""
        documents = []
        try:
            structured_chunks = self.vector_db_manager.get_all_structured_chunks()
            for chunk in structured_chunks:
                content = chunk.get('content', '')
                if content and len(content.strip()) > 0:
                    metadata = chunk.get('metadata', {})
                    metadata.update({
                        'source_type': 'structured_chunk',
                        'chunk_id': chunk.get('chunk_id', ''),
                        'ticket_id': chunk.get('ticket_id', ''),
                        'chunk_type': chunk.get('chunk_type', '')
                    })
                    documents.append(Document(page_content=content, metadata=metadata))
        except Exception as e:
            logger.error(f"구조적 청크 문서 수집 실패: {e}")
        return documents
    
    def _setup_retrievers(self):
        """BM25Retriever와 Vector Retriever 설정"""
        try:
            # 1. BM25Retriever 생성
            if not self.documents:
                logger.warning("⚠️ 수집된 문서가 없습니다.")
                return
            
            logger.info("🔍 BM25Retriever 생성 중...")
            self.bm25_retriever = BM25Retriever.from_documents(self.documents, k=10)
            logger.info("✅ BM25Retriever 생성 완료")
            
            # 2. Vector Retriever 생성 (VectorDBManager 기반)
            logger.info("🔍 Vector Retriever 생성 중...")
            self.vector_retriever = self._create_vector_retriever()
            logger.info("✅ Vector Retriever 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ Retriever 설정 실패: {e}")
            self.bm25_retriever = None
            self.vector_retriever = None
    
    def _create_vector_retriever(self):
        """VectorDBManager를 위한 Vector Retriever 생성"""
        from multi_query_retriever import ChromaDBRetriever
        return ChromaDBRetriever(
            vector_db_manager=self.vector_db_manager,
            collection_name="file_chunks"
        )
    
    def test_vector_retriever(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Vector Retriever 단독 테스트"""
        logger.info(f"🔍 Vector Retriever 단독 테스트: '{query}'")
        
        if not self.vector_retriever:
            logger.error("❌ Vector Retriever가 초기화되지 않았습니다.")
            return []
        
        try:
            # 쿼리 전처리
            preprocessed_query = preprocess_for_embedding(query)
            logger.info(f"🔍 전처리된 쿼리: '{preprocessed_query}'")
            
            # Vector 검색 수행
            documents = self.vector_retriever.get_relevant_documents(preprocessed_query)
            
            # 결과 변환
            results = []
            for i, doc in enumerate(documents[:k]):
                result = {
                    "id": f"vector_{i}",
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": doc.metadata.get('similarity_score', 0.0),
                    "source_type": "vector_search"
                }
                results.append(result)
            
            logger.info(f"✅ Vector Retriever 테스트 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ Vector Retriever 테스트 실패: {e}")
            return []
    
    def test_bm25_retriever(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """BM25 Retriever 단독 테스트"""
        logger.info(f"🔍 BM25 Retriever 단독 테스트: '{query}'")
        
        if not self.bm25_retriever:
            logger.error("❌ BM25 Retriever가 초기화되지 않았습니다.")
            return []
        
        try:
            # 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(query)
            keyword_query = " ".join(keywords)
            logger.info(f"🔑 추출된 키워드: {keywords}")
            logger.info(f"🔍 BM25 검색 쿼리: '{keyword_query}'")
            
            # 쿼리 전처리
            preprocessed_query = preprocess_for_embedding(keyword_query)
            logger.info(f"🔍 전처리된 BM25 쿼리: '{preprocessed_query}'")
            
            # BM25 검색 수행
            documents = self.bm25_retriever.get_relevant_documents(preprocessed_query)
            
            # 결과 변환
            results = []
            for i, doc in enumerate(documents[:k]):
                result = {
                    "id": f"bm25_{i}",
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": 0.0,  # BM25는 직접적인 유사도 점수를 제공하지 않음
                    "source_type": "bm25_search",
                    "extracted_keywords": keywords
                }
                results.append(result)
            
            logger.info(f"✅ BM25 Retriever 테스트 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ BM25 Retriever 테스트 실패: {e}")
            return []
    
    def analyze_documents(self):
        """수집된 문서 분석"""
        logger.info("📊 문서 분석 시작...")
        
        if not self.documents:
            logger.warning("⚠️ 분석할 문서가 없습니다.")
            return
        
        # 문서 타입별 통계
        source_types = {}
        total_content_length = 0
        empty_docs = 0
        
        for doc in self.documents:
            source_type = doc.metadata.get('source_type', 'unknown')
            source_types[source_type] = source_types.get(source_type, 0) + 1
            
            content_length = len(doc.page_content)
            total_content_length += content_length
            
            if content_length == 0:
                empty_docs += 1
        
        logger.info(f"📊 문서 분석 결과:")
        logger.info(f"  - 총 문서 수: {len(self.documents)}")
        logger.info(f"  - 빈 문서 수: {empty_docs}")
        logger.info(f"  - 평균 내용 길이: {total_content_length / len(self.documents):.1f}자")
        logger.info(f"  - 문서 타입별 분포:")
        for source_type, count in source_types.items():
            logger.info(f"    * {source_type}: {count}개")
        
        # 샘플 문서 내용 출력
        logger.info(f"📄 샘플 문서 내용 (처음 3개):")
        for i, doc in enumerate(self.documents[:3]):
            logger.info(f"  문서 {i+1}:")
            logger.info(f"    - 타입: {doc.metadata.get('source_type', 'unknown')}")
            logger.info(f"    - 내용 길이: {len(doc.page_content)}자")
            logger.info(f"    - 내용 미리보기: {doc.page_content[:100]}...")
    
    def run_debug_test(self, test_query: str):
        """전체 디버깅 테스트 실행"""
        logger.info("=" * 80)
        logger.info("🔍 EnsembleRetriever 디버깅 테스트 시작")
        logger.info("=" * 80)
        
        # 1. 문서 분석
        self.analyze_documents()
        
        logger.info("\n" + "=" * 80)
        logger.info(f"🎯 테스트 쿼리: '{test_query}'")
        logger.info("=" * 80)
        
        # 2. Vector Retriever 테스트
        logger.info("\n🔍 Vector Retriever 단독 테스트")
        logger.info("-" * 50)
        vector_results = self.test_vector_retriever(test_query, k=5)
        
        if vector_results:
            logger.info(f"✅ Vector Retriever 결과 ({len(vector_results)}개):")
            for i, result in enumerate(vector_results):
                logger.info(f"  {i+1}. ID: {result['id']}")
                logger.info(f"     내용: {result['content']}")
                logger.info(f"     유사도: {result['similarity_score']}")
                logger.info(f"     메타데이터: {result['metadata']}")
                logger.info("")
        else:
            logger.warning("⚠️ Vector Retriever 결과가 없습니다.")
        
        # 3. BM25 Retriever 테스트
        logger.info("\n🔍 BM25 Retriever 단독 테스트")
        logger.info("-" * 50)
        bm25_results = self.test_bm25_retriever(test_query, k=5)
        
        if bm25_results:
            logger.info(f"✅ BM25 Retriever 결과 ({len(bm25_results)}개):")
            for i, result in enumerate(bm25_results):
                logger.info(f"  {i+1}. ID: {result['id']}")
                logger.info(f"     내용: {result['content']}")
                logger.info(f"     추출된 키워드: {result['extracted_keywords']}")
                logger.info(f"     메타데이터: {result['metadata']}")
                logger.info("")
        else:
            logger.warning("⚠️ BM25 Retriever 결과가 없습니다.")
        
        # 4. 결과 비교 및 분석
        logger.info("\n📊 결과 비교 및 분석")
        logger.info("-" * 50)
        logger.info(f"Vector Retriever 결과 수: {len(vector_results)}")
        logger.info(f"BM25 Retriever 결과 수: {len(bm25_results)}")
        
        if vector_results and bm25_results:
            # 중복 문서 확인
            vector_ids = {result['id'] for result in vector_results}
            bm25_ids = {result['id'] for result in bm25_results}
            common_ids = vector_ids.intersection(bm25_ids)
            
            logger.info(f"공통 결과 수: {len(common_ids)}")
            if common_ids:
                logger.info(f"공통 결과 ID: {list(common_ids)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("🔍 EnsembleRetriever 디버깅 테스트 완료")
        logger.info("=" * 80)

def main():
    """메인 함수"""
    # 테스트 쿼리 정의
    test_query = "서버 접속이 안 되고 HTTP 500 오류가 나는 문제 있나요?"
    
    # 디버거 초기화 및 테스트 실행
    debugger = EnsembleRetrieverDebugger()
    debugger.run_debug_test(test_query)

if __name__ == "__main__":
    main()
