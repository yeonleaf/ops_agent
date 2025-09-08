#!/usr/bin/env python3
"""
Retrieve then Re-rank 검색 시스템
BM25 키워드 검색과 벡터 검색을 독립적으로 실행한 후, CohereRerank로 최종 선별
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from vector_db_models import VectorDBManager
from text_preprocessor import preprocess_for_embedding
from keyword_extractor import KeywordExtractor
import cohere
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class RetrieveRerankRetriever:
    """
    Retrieve then Re-rank 검색 시스템
    1단계: Vector + BM25 독립 검색
    2단계: 후보군 통합 및 중복 제거
    3단계: CohereRerank로 최종 선별
    """
    
    def __init__(self, vector_db_manager: VectorDBManager, enable_bm25: bool = False):
        self.vector_db_manager = vector_db_manager
        self.bm25_retriever = None
        self.documents = []
        self.keyword_extractor = KeywordExtractor()
        self.cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))
        self.enable_bm25 = enable_bm25
        
        # BM25가 활성화된 경우에만 문서 수집 및 인덱스 생성
        if self.enable_bm25:
            self._collect_documents()
            self._setup_bm25_retriever()
        else:
            logger.info("⚠️ BM25 검색 비활성화 (메모리 절약 모드)")
        
        logger.info("✅ RetrieveRerankRetriever 초기화 완료")
    
    def _collect_documents(self):
        """제한된 문서를 수집하여 BM25 인덱스 생성을 위한 Document 객체 생성 (메모리 절약)"""
        try:
            logger.info("📚 제한된 문서 수집 시작 (메모리 절약)...")
            
            # 1. 파일 청크 문서 수집 (최대 200개로 제한)
            file_chunks = self._get_file_chunks(limit=200)
            self.documents.extend(file_chunks)
            logger.info(f"✅ 파일 청크 문서 {len(file_chunks)}개 수집 (제한됨)")
            
            # 2. 메일 문서 수집 (최대 50개로 제한)
            mail_docs = self._get_mail_documents(limit=50)
            self.documents.extend(mail_docs)
            logger.info(f"✅ 메일 문서 {len(mail_docs)}개 수집 (제한됨)")
            
            # 3. 구조적 청크 문서 수집 (최대 50개로 제한)
            structured_docs = self._get_structured_documents(limit=50)
            self.documents.extend(structured_docs)
            logger.info(f"✅ 구조적 청크 문서 {len(structured_docs)}개 수집 (제한됨)")
            
            logger.info(f"✅ 총 {len(self.documents)}개 문서 수집 완료 (메모리 절약 모드)")
            
        except Exception as e:
            logger.error(f"❌ 문서 수집 실패: {e}")
            self.documents = []
    
    def _get_file_chunks(self, limit: int = 200) -> List[Document]:
        """파일 청크 문서들을 Document 객체로 변환 (제한된 수)"""
        documents = []
        try:
            file_chunks = self.vector_db_manager.get_all_file_chunks()
            # 제한된 수만큼만 처리
            limited_chunks = file_chunks[:limit]
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
        except Exception as e:
            logger.error(f"파일 청크 문서 수집 실패: {e}")
        return documents
    
    def _get_mail_documents(self, limit: int = 50) -> List[Document]:
        """메일 문서들을 Document 객체로 변환 (제한된 수)"""
        documents = []
        try:
            mails = self.vector_db_manager.get_all_mails()
            # 제한된 수만큼만 처리
            limited_mails = mails[:limit]
            for mail in limited_mails:
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
    
    def _get_structured_documents(self, limit: int = 50) -> List[Document]:
        """구조적 청크 문서들을 Document 객체로 변환 (제한된 수)"""
        documents = []
        try:
            structured_chunks = self.vector_db_manager.get_all_structured_chunks()
            # 제한된 수만큼만 처리
            limited_chunks = structured_chunks[:limit]
            for chunk in limited_chunks:
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
    
    def _setup_bm25_retriever(self):
        """BM25Retriever 설정"""
        try:
            if not self.documents:
                logger.warning("⚠️ 수집된 문서가 없습니다. 빈 BM25Retriever를 생성합니다.")
                self.documents = [Document(page_content="", metadata={})]
            
            logger.info("🔍 BM25Retriever 생성 중...")
            self.bm25_retriever = BM25Retriever.from_documents(self.documents, k=10)
            logger.info("✅ BM25Retriever 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ BM25Retriever 설정 실패: {e}")
            self.bm25_retriever = None
    
    def _create_vector_retriever(self):
        """VectorDBManager를 위한 Vector Retriever 생성"""
        from multi_query_retriever import ChromaDBRetriever
        return ChromaDBRetriever(
            vector_db_manager=self.vector_db_manager,
            collection_name="file_chunks"
        )
    
    def _perform_vector_search(self, query: str, k: int = 10) -> List[Document]:
        """1단계: 벡터 검색 수행 (직접 VectorDBManager 사용)"""
        try:
            logger.info(f"🔍 벡터 검색 시작: '{query}'")
            
            # 쿼리 전처리
            preprocessed_query = preprocess_for_embedding(query)
            
            # VectorDBManager를 직접 사용하여 검색
            search_results = self.vector_db_manager.search_similar_file_chunks(preprocessed_query, n_results=k)
            
            # 결과를 Document 객체로 변환
            documents = []
            for i, result in enumerate(search_results):
                content = result.get('content', '')
                metadata = result.get('metadata', {})
                metadata.update({
                    'search_type': 'vector',
                    'search_rank': i + 1,
                    'similarity_score': result.get('similarity_score', 0.0)
                })
                documents.append(Document(page_content=content, metadata=metadata))
            
            logger.info(f"✅ 벡터 검색 완료: {len(documents)}개 결과")
            return documents
            
        except Exception as e:
            logger.error(f"❌ 벡터 검색 실패: {e}")
            return []
    
    def _perform_bm25_search(self, query: str, k: int = 10) -> List[Document]:
        """1단계: BM25 검색 수행"""
        try:
            if not self.enable_bm25 or not self.bm25_retriever:
                logger.warning("⚠️ BM25 검색이 비활성화되었습니다.")
                return []
            
            logger.info(f"🔍 BM25 검색 시작: '{query}'")
            
            # 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(query)
            keyword_query = " ".join(keywords)
            logger.info(f"🔑 추출된 키워드: {keywords}")
            
            # 쿼리 전처리
            preprocessed_query = preprocess_for_embedding(keyword_query)
            
            # BM25 검색 수행
            documents = self.bm25_retriever.get_relevant_documents(preprocessed_query)
            
            # 결과에 검색 타입 표시
            for doc in documents:
                doc.metadata['search_type'] = 'bm25'
                doc.metadata['search_rank'] = documents.index(doc) + 1
                doc.metadata['extracted_keywords'] = keywords
            
            logger.info(f"✅ BM25 검색 완료: {len(documents)}개 결과")
            return documents[:k]
            
        except Exception as e:
            logger.error(f"❌ BM25 검색 실패: {e}")
            return []
    
    def _merge_and_deduplicate_candidates(self, vector_docs: List[Document], bm25_docs: List[Document]) -> List[Document]:
        """2단계: 후보군 통합 및 중복 제거"""
        try:
            logger.info("🔄 후보군 통합 및 중복 제거 시작...")
            
            # 중복 제거를 위한 딕셔너리
            unique_docs = {}
            
            # 벡터 검색 결과 먼저 추가
            for doc in vector_docs:
                doc_id = doc.metadata.get('chunk_id', doc.metadata.get('message_id', str(hash(doc.page_content))))
                if doc_id not in unique_docs:
                    unique_docs[doc_id] = doc
                else:
                    # 중복 문서인 경우 벡터 검색 결과 우선 (더 높은 품질)
                    existing_doc = unique_docs[doc_id]
                    existing_doc.metadata['search_type'] = 'hybrid'
                    existing_doc.metadata['vector_rank'] = doc.metadata.get('search_rank', 0)
                    existing_doc.metadata['bm25_rank'] = existing_doc.metadata.get('search_rank', 0)
            
            # BM25 검색 결과 추가 (중복되지 않는 것만)
            for doc in bm25_docs:
                doc_id = doc.metadata.get('chunk_id', doc.metadata.get('message_id', str(hash(doc.page_content))))
                if doc_id not in unique_docs:
                    unique_docs[doc_id] = doc
                else:
                    # 중복 문서인 경우 BM25 순위 정보 추가
                    existing_doc = unique_docs[doc_id]
                    if existing_doc.metadata.get('search_type') == 'hybrid':
                        existing_doc.metadata['bm25_rank'] = doc.metadata.get('search_rank', 0)
            
            # 최종 후보군 리스트 생성
            final_candidates = list(unique_docs.values())
            
            logger.info(f"✅ 후보군 통합 완료: 벡터 {len(vector_docs)}개, BM25 {len(bm25_docs)}개 → 통합 {len(final_candidates)}개")
            return final_candidates
            
        except Exception as e:
            logger.error(f"❌ 후보군 통합 실패: {e}")
            return vector_docs + bm25_docs  # 실패 시 단순 합치기
    
    def _rerank_candidates(self, query: str, candidates: List[Document], k: int = 3) -> List[Document]:
        """3단계: CohereRerank로 최종 선별"""
        try:
            if not candidates:
                logger.warning("⚠️ 재순위화할 후보가 없습니다.")
                return []
            
            logger.info(f"🎯 CohereRerank 재순위화 시작: {len(candidates)}개 후보 → {k}개 최종 결과")
            
            # Document 객체를 텍스트 리스트로 변환
            documents_text = [doc.page_content for doc in candidates]
            
            # Cohere API를 사용한 재순위화
            response = self.cohere_client.rerank(
                model="rerank-multilingual-v3.0",
                query=query,
                documents=documents_text,
                top_n=k
            )
            
            # 재순위화된 결과를 Document 객체로 변환
            final_documents = []
            for i, result in enumerate(response.results):
                # 원본 Document 찾기
                original_doc = None
                for doc in candidates:
                    if doc.page_content == documents_text[result.index]:
                        original_doc = doc
                        break
                
                if original_doc:
                    # 재순위화 정보 추가
                    original_doc.metadata.update({
                        'rerank_score': result.relevance_score,
                        'final_rank': i + 1,
                        'rerank_method': 'cohere'
                    })
                    final_documents.append(original_doc)
            
            logger.info(f"✅ CohereRerank 재순위화 완료: {len(final_documents)}개 최종 결과")
            
            # 상위 3개 결과의 점수 로깅
            for i, doc in enumerate(final_documents[:3]):
                rerank_score = doc.metadata.get('rerank_score', 0)
                search_type = doc.metadata.get('search_type', 'unknown')
                logger.info(f"  - 최종 결과 {i+1}: {search_type} (재순위화 점수: {rerank_score:.3f})")
            
            return final_documents
            
        except Exception as e:
            logger.error(f"❌ CohereRerank 재순위화 실패: {e}")
            # 실패 시 원본 순서대로 상위 k개 반환
            return candidates[:k]
    
    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve then Re-rank 검색 수행
        1단계: Vector + BM25 독립 검색
        2단계: 후보군 통합 및 중복 제거
        3단계: CohereRerank로 최종 선별
        """
        try:
            logger.info(f"🚀 Retrieve then Re-rank 검색 시작: '{query}'")
            
            # 1단계: 두 검색기로 각각 검색
            vector_docs = self._perform_vector_search(query, k=10)
            bm25_docs = self._perform_bm25_search(query, k=10)
            
            # 2단계: 후보군 통합 및 중복 제거
            candidates = self._merge_and_deduplicate_candidates(vector_docs, bm25_docs)
            
            # 3단계: CohereRerank로 최종 선별
            final_docs = self._rerank_candidates(query, candidates, k=k)
            
            # 결과를 표준 형식으로 변환
            results = []
            for i, doc in enumerate(final_docs):
                result = {
                    "id": f"rerank_{i}",
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": doc.metadata.get("rerank_score", 0.0),
                    "source": "retrieve_rerank",
                    "search_type": doc.metadata.get("search_type", "unknown"),
                    "final_rank": doc.metadata.get("final_rank", i + 1)
                }
                results.append(result)
            
            logger.info(f"✅ Retrieve then Re-rank 검색 완료: {len(results)}개 최종 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ Retrieve then Re-rank 검색 실패: {e}")
            return []
    
    def get_search_info(self) -> Dict[str, Any]:
        """검색 시스템 정보 반환"""
        return {
            "total_documents": len(self.documents),
            "bm25_retriever_ready": self.bm25_retriever is not None,
            "cohere_rerank_ready": self.cohere_client is not None,
            "search_method": "retrieve_then_rerank",
            "pipeline_steps": [
                "1. Vector Search (top 10)",
                "2. BM25 Search (top 10)", 
                "3. Merge & Deduplicate",
                "4. CohereRerank (final top 3)"
            ]
        }

def create_retrieve_rerank_retriever(vector_db_manager: VectorDBManager, enable_bm25: bool = False) -> RetrieveRerankRetriever:
    """RetrieveRerankRetriever 인스턴스를 생성합니다."""
    return RetrieveRerankRetriever(vector_db_manager, enable_bm25=enable_bm25)
