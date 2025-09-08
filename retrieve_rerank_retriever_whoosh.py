#!/usr/bin/env python3
"""
Retrieve then Re-rank 검색 시스템 (Whoosh 기반)
Whoosh 키워드 검색과 벡터 검색으로 후보군을 생성하고, Cohere Rerank로 최종 선별
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from vector_db_models import VectorDBManager
from text_preprocessor import preprocess_for_embedding
from whoosh_search_manager import WhooshSearchManager
import cohere
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class RetrieveRerankRetrieverWhoosh:
    """
    Retrieve then Re-rank 검색 시스템 (Whoosh 기반)
    1단계: Vector + Whoosh 독립 검색
    2단계: 후보군 통합 및 중복 제거
    3단계: CohereRerank로 최종 선별
    """
    
    def __init__(self, vector_db_manager: VectorDBManager, whoosh_index_dir: str = "whoosh_index"):
        self.vector_db_manager = vector_db_manager
        self.whoosh_search_manager = WhooshSearchManager(whoosh_index_dir)
        self.cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))
        
        logger.info("✅ RetrieveRerankRetrieverWhoosh 초기화 완료")
    
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
    
    def _perform_whoosh_search(self, query: str, k: int = 10) -> List[Document]:
        """1단계: Whoosh 키워드 검색 수행"""
        try:
            logger.info(f"🔍 Whoosh 키워드 검색 시작: '{query}'")
            
            # Whoosh 검색 수행
            search_results = self.whoosh_search_manager.search_with_whoosh(query, k=k)
            
            # 결과를 Document 객체로 변환
            documents = []
            for result in search_results:
                content = result.get('content', '')
                metadata = result.get('metadata', {})
                metadata.update({
                    'search_type': 'whoosh',
                    'similarity_score': result.get('similarity_score', 0.0)
                })
                documents.append(Document(page_content=content, metadata=metadata))
            
            logger.info(f"✅ Whoosh 검색 완료: {len(documents)}개 결과")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Whoosh 검색 실패: {e}")
            return []
    
    def _merge_and_deduplicate_candidates(self, vector_docs: List[Document], whoosh_docs: List[Document]) -> List[Document]:
        """2단계: 후보군 통합 및 중복 제거"""
        try:
            logger.info("🔄 후보군 통합 및 중복 제거 시작...")
            
            combined_docs = []
            seen_content = set()
            
            # 벡터 검색 결과 추가
            for doc in vector_docs:
                content_hash = hash(doc.page_content)
                if content_hash not in seen_content:
                    combined_docs.append(doc)
                    seen_content.add(content_hash)
            
            # Whoosh 검색 결과 추가 (중복 제거)
            for doc in whoosh_docs:
                content_hash = hash(doc.page_content)
                if content_hash not in seen_content:
                    combined_docs.append(doc)
                    seen_content.add(content_hash)
            
            logger.info(f"✅ 후보군 통합 완료: 벡터 {len(vector_docs)}개, Whoosh {len(whoosh_docs)}개 → 통합 {len(combined_docs)}개")
            return combined_docs
            
        except Exception as e:
            logger.error(f"❌ 후보군 통합 실패: {e}")
            return vector_docs + whoosh_docs
    
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
                    # 재순위화 메타데이터 추가
                    original_doc.metadata.update({
                        'rerank_score': result.relevance_score,
                        'final_rank': i + 1,
                        'rerank_method': 'cohere'
                    })
                    final_documents.append(original_doc)
            
            logger.info(f"✅ CohereRerank 재순위화 완료: {len(final_documents)}개 최종 결과")
            
            # 최종 결과 로깅
            for i, doc in enumerate(final_documents[:3]):
                rerank_score = doc.metadata.get('rerank_score', 0)
                search_type = doc.metadata.get('search_type', 'unknown')
                logger.info(f"  - 최종 결과 {i+1}: {search_type} (재순위화 점수: {rerank_score:.3f})")
            
            return final_documents
            
        except Exception as e:
            logger.error(f"❌ CohereRerank 재순위화 실패: {e}")
            return candidates[:k]
    
    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve then Re-rank 검색 수행 (Whoosh 기반)
        1단계: Vector + Whoosh 독립 검색
        2단계: 후보군 통합 및 중복 제거
        3단계: Cohere Rerank로 최종 선별
        """
        try:
            logger.info(f"🚀 Retrieve then Re-rank 검색 시작 (Whoosh 기반): '{query}'")
            
            # 1단계: 독립 검색
            vector_candidates = self._perform_vector_search(query, k=10)
            whoosh_candidates = self._perform_whoosh_search(query, k=10)
            
            # 2단계: 후보군 통합 및 중복 제거
            merged_candidates = self._merge_and_deduplicate_candidates(vector_candidates, whoosh_candidates)
            
            # 3단계: Cohere Rerank로 최종 선별
            final_results = self._rerank_candidates(query, merged_candidates, k=k)
            
            # 결과 포맷팅
            formatted_results = []
            for i, doc in enumerate(final_results):
                formatted_results.append({
                    "id": doc.metadata.get("chunk_id", doc.metadata.get("message_id", f"WHOOSH-{i}")),
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": doc.metadata.get("rerank_score", doc.metadata.get("similarity_score", 0.0)),
                    "source": "retrieve_rerank_whoosh",
                    "search_type": doc.metadata.get("search_type", "unknown")
                })
            
            logger.info(f"✅ Retrieve then Re-rank 검색 완료 (Whoosh 기반): {len(formatted_results)}개 최종 결과")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Retrieve then Re-rank 검색 실패 (Whoosh 기반): {e}")
            return []
    
    def get_search_info(self) -> Dict[str, Any]:
        """검색 시스템 정보 반환"""
        try:
            whoosh_stats = self.whoosh_search_manager.get_index_stats()
            return {
                "search_method": "retrieve_then_rerank_whoosh",
                "whoosh_index_stats": whoosh_stats,
                "cohere_rerank_ready": self.cohere_client is not None,
                "pipeline_steps": [
                    "1. Vector Search (top 10)",
                    "2. Whoosh Search (top 10)", 
                    "3. Merge & Deduplicate",
                    "4. Cohere Re-rank (top 3)"
                ]
            }
        except Exception as e:
            logger.error(f"❌ 검색 시스템 정보 조회 실패: {e}")
            return {"error": str(e)}

def create_retrieve_rerank_retriever_whoosh(vector_db_manager: VectorDBManager, whoosh_index_dir: str = "whoosh_index") -> RetrieveRerankRetrieverWhoosh:
    """RetrieveRerankRetrieverWhoosh 인스턴스를 생성합니다."""
    return RetrieveRerankRetrieverWhoosh(vector_db_manager, whoosh_index_dir)
