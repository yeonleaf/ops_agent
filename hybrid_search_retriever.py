#!/usr/bin/env python3
"""
하이브리드 검색 시스템
BM25 키워드 검색과 벡터 검색을 결합한 EnsembleRetriever 구현
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from vector_db_models import VectorDBManager
from text_preprocessor import preprocess_for_embedding
from keyword_extractor import KeywordExtractor
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class HybridSearchRetriever:
    """
    하이브리드 검색 시스템
    BM25 키워드 검색 + 벡터 검색을 결합한 EnsembleRetriever
    """
    
    def __init__(self, vector_db_manager: VectorDBManager):
        self.vector_db_manager = vector_db_manager
        self.bm25_retriever = None
        self.ensemble_retriever = None
        self.documents = []
        self.keyword_extractor = KeywordExtractor()  # 키워드 추출기 초기화
        
        # 문서 수집 및 인덱스 생성
        self._collect_documents()
        self._setup_retrievers()
        
        logger.info("✅ HybridSearchRetriever 초기화 완료")
    
    def _collect_documents(self):
        """모든 문서를 수집하여 BM25 인덱스 생성을 위한 Document 객체 생성"""
        try:
            logger.info("📚 문서 수집 시작...")
            
            # 1. 파일 청크 문서 수집
            file_chunks = self._get_file_chunks()
            self.documents.extend(file_chunks)
            
            # 2. 메일 문서 수집
            mail_documents = self._get_mail_documents()
            self.documents.extend(mail_documents)
            
            # 3. 구조적 청크 문서 수집
            structured_documents = self._get_structured_documents()
            self.documents.extend(structured_documents)
            
            logger.info(f"✅ 총 {len(self.documents)}개 문서 수집 완료")
            
        except Exception as e:
            logger.error(f"❌ 문서 수집 실패: {e}")
            self.documents = []
    
    def _get_file_chunks(self) -> List[Document]:
        """파일 청크 문서들을 Document 객체로 변환"""
        documents = []
        try:
            logger.info("📄 파일 청크 문서 처리 중...")
            
            # VectorDBManager에서 모든 파일 청크 가져오기
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
            
            logger.info(f"✅ 파일 청크 문서 {len(documents)}개 처리 완료")
            
        except Exception as e:
            logger.error(f"파일 청크 문서 수집 실패: {e}")
        
        return documents
    
    def _get_mail_documents(self) -> List[Document]:
        """메일 문서들을 Document 객체로 변환"""
        documents = []
        try:
            logger.info("📧 메일 문서 처리 중...")
            
            # VectorDBManager에서 모든 메일 가져오기
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
            
            logger.info(f"✅ 메일 문서 {len(documents)}개 처리 완료")
            
        except Exception as e:
            logger.error(f"메일 문서 수집 실패: {e}")
        
        return documents
    
    def _get_structured_documents(self) -> List[Document]:
        """구조적 청크 문서들을 Document 객체로 변환"""
        documents = []
        try:
            logger.info("🏗️ 구조적 청크 문서 처리 중...")
            
            # VectorDBManager에서 모든 구조적 청크 가져오기
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
            
            logger.info(f"✅ 구조적 청크 문서 {len(documents)}개 처리 완료")
            
        except Exception as e:
            logger.error(f"구조적 청크 문서 수집 실패: {e}")
        
        return documents
    
    def _setup_retrievers(self):
        """BM25Retriever와 EnsembleRetriever 설정"""
        try:
            if not self.documents:
                logger.warning("⚠️ 수집된 문서가 없습니다. 빈 BM25Retriever를 생성합니다.")
                self.documents = [Document(page_content="", metadata={})]
            
            # 1. BM25Retriever 생성
            logger.info("🔍 BM25Retriever 생성 중...")
            self.bm25_retriever = BM25Retriever.from_documents(self.documents)
            self.bm25_retriever.k = 10  # 검색 결과 수 설정
            logger.info("✅ BM25Retriever 생성 완료")
            
            # 2. Vector Retriever 생성 (기존 VectorDBManager 기반)
            logger.info("🔍 Vector Retriever 생성 중...")
            vector_retriever = self._create_vector_retriever()
            logger.info("✅ Vector Retriever 생성 완료")
            
            # 3. EnsembleRetriever 생성
            logger.info("🔍 EnsembleRetriever 생성 중...")
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, vector_retriever],
                weights=[0.2, 0.8]  # 의미 검색(Vector) 최우선
            )
            logger.info("✅ EnsembleRetriever 생성 완료 (BM25: 0.2, Vector: 0.8)")
            
        except Exception as e:
            logger.error(f"❌ Retriever 설정 실패: {e}")
            self.ensemble_retriever = None
    
    def _create_vector_retriever(self):
        """VectorDBManager 기반의 Vector Retriever 생성"""
        from langchain_core.retrievers import BaseRetriever
        
        class VectorDBRetriever(BaseRetriever):
            """VectorDBManager를 위한 BaseRetriever 구현"""
            
            vector_db_manager: Any
            k: int
            
            def __init__(self, vector_db_manager, k: int = 10, **kwargs):
                super().__init__(
                    vector_db_manager=vector_db_manager,
                    k=k,
                    **kwargs
                )
            
            def _get_relevant_documents(self, query: str) -> List[Document]:
                """VectorDBManager에서 관련 문서 검색"""
                try:
                    # 쿼리 전처리
                    preprocessed_query = preprocess_for_embedding(query)
                    
                    # 통합 검색 수행
                    results = []
                    
                    # 파일 청크 검색
                    file_results = self.vector_db_manager.search_similar_file_chunks(
                        preprocessed_query, n_results=self.k//3
                    )
                    for result in file_results:
                        if isinstance(result, dict):
                            content = result.get('content', '')
                            metadata = result.get('metadata', {})
                            metadata.update({
                                'source': 'file_chunk',
                                'similarity_score': result.get('similarity_score', 0.0)
                            })
                        else:
                            content = getattr(result, 'text_chunk', '')
                            metadata = {
                                'source': 'file_chunk',
                                'file_name': getattr(result, 'file_name', ''),
                                'similarity_score': getattr(result, 'similarity_score', 0.0)
                            }
                        
                        if content:
                            results.append(Document(page_content=content, metadata=metadata))
                    
                    # 메일 검색
                    mail_results = self.vector_db_manager.search_similar_mails(
                        preprocessed_query, n_results=self.k//3
                    )
                    for result in mail_results:
                        if isinstance(result, dict):
                            content = result.get('refined_content', '')
                            metadata = result.get('metadata', {})
                            metadata.update({
                                'source': 'mail',
                                'similarity_score': result.get('similarity_score', 0.0)
                            })
                        else:
                            content = getattr(result, 'refined_content', '')
                            metadata = {
                                'source': 'mail',
                                'subject': getattr(result, 'subject', ''),
                                'sender': getattr(result, 'sender', ''),
                                'similarity_score': getattr(result, 'similarity_score', 0.0)
                            }
                        
                        if content:
                            results.append(Document(page_content=content, metadata=metadata))
                    
                    # 구조적 청크 검색
                    structured_results = self.vector_db_manager.search_structured_chunks(
                        preprocessed_query, n_results=self.k//3
                    )
                    for result in structured_results:
                        if isinstance(result, dict):
                            content = result.get('content', '')
                            metadata = result.get('metadata', {})
                            metadata.update({
                                'source': 'structured_chunk',
                                'similarity_score': result.get('similarity_score', 0.0)
                            })
                        else:
                            content = getattr(result, 'content', '')
                            metadata = {
                                'source': 'structured_chunk',
                                'ticket_id': getattr(result, 'ticket_id', ''),
                                'chunk_type': getattr(result, 'chunk_type', ''),
                                'similarity_score': getattr(result, 'similarity_score', 0.0)
                            }
                        
                        if content:
                            results.append(Document(page_content=content, metadata=metadata))
                    
                    return results[:self.k]
                    
                except Exception as e:
                    logger.error(f"Vector 검색 실패: {e}")
                    return []
        
        return VectorDBRetriever(self.vector_db_manager, k=10)
    
    def _perform_separated_search(self, vector_query: str, bm25_query: str) -> List[Document]:
        """
        개선된 분리된 검색을 수행합니다.
        벡터 검색은 원본 쿼리로, BM25 검색은 추출된 키워드로 수행합니다.
        """
        try:
            # 1. 벡터 검색 (원본 쿼리)
            vector_retriever = self._create_vector_retriever()
            vector_docs = vector_retriever.get_relevant_documents(vector_query)
            
            # 2. BM25 검색 (추출된 키워드)
            bm25_docs = self.bm25_retriever.get_relevant_documents(bm25_query)
            
            # 3. 개선된 결과 통합 및 점수 정규화
            combined_docs = []
            
            # 벡터 검색 결과 처리
            vector_results = []
            for i, doc in enumerate(vector_docs):
                # 벡터 검색 결과에 정규화된 점수 부여
                vector_score = doc.metadata.get('similarity_score', 0.0)
                normalized_vector_score = min(vector_score * 0.8, 0.8)  # 최대 0.8로 제한
                
                doc.metadata.update({
                    'search_weight': normalized_vector_score,
                    'search_type': 'vector',
                    'original_score': vector_score,
                    'rank': i + 1
                })
                vector_results.append(doc)
            
            # BM25 검색 결과 처리
            bm25_results = []
            for i, doc in enumerate(bm25_docs):
                # BM25 검색 결과에 정규화된 점수 부여 (순위 기반)
                bm25_score = max(0.1, 0.2 - (i * 0.02))  # 순위에 따라 점수 감소, 최소 0.1
                
                doc.metadata.update({
                    'search_weight': bm25_score,
                    'search_type': 'bm25',
                    'original_score': bm25_score,
                    'rank': i + 1
                })
                bm25_results.append(doc)
            
            # 4. 중복 제거 및 점수 조정
            unique_docs = {}
            
            # 벡터 결과 먼저 추가
            for doc in vector_results:
                doc_id = doc.metadata.get('chunk_id', doc.metadata.get('message_id', str(hash(doc.page_content))))
                unique_docs[doc_id] = doc
            
            # BM25 결과 추가 (중복 시 점수 조정)
            for doc in bm25_results:
                doc_id = doc.metadata.get('chunk_id', doc.metadata.get('message_id', str(hash(doc.page_content))))
                
                if doc_id in unique_docs:
                    # 중복 문서인 경우 점수 조정
                    existing_doc = unique_docs[doc_id]
                    existing_weight = existing_doc.metadata.get('search_weight', 0)
                    bm25_weight = doc.metadata.get('search_weight', 0)
                    
                    # 하이브리드 점수 계산 (가중 평균)
                    hybrid_score = (existing_weight * 0.7) + (bm25_weight * 0.3)
                    
                    existing_doc.metadata.update({
                        'search_weight': hybrid_score,
                        'search_type': 'hybrid',
                        'vector_score': existing_weight,
                        'bm25_score': bm25_weight
                    })
                else:
                    # 새로운 문서인 경우 그대로 추가
                    unique_docs[doc_id] = doc
            
            # 5. 최종 점수 기준으로 정렬
            final_docs = list(unique_docs.values())
            final_docs.sort(key=lambda x: x.metadata.get('search_weight', 0), reverse=True)
            
            # 6. 로깅 개선
            vector_count = len(vector_results)
            bm25_count = len(bm25_results)
            hybrid_count = len([d for d in final_docs if d.metadata.get('search_type') == 'hybrid'])
            
            logger.info(f"✅ 개선된 분리된 검색 완료:")
            logger.info(f"  - 벡터 검색: {vector_count}개")
            logger.info(f"  - BM25 검색: {bm25_count}개")
            logger.info(f"  - 하이브리드 결과: {hybrid_count}개")
            logger.info(f"  - 최종 통합: {len(final_docs)}개")
            
            # 상위 3개 결과의 점수 로깅
            for i, doc in enumerate(final_docs[:3]):
                score = doc.metadata.get('search_weight', 0)
                search_type = doc.metadata.get('search_type', 'unknown')
                logger.info(f"  - 결과 {i+1}: {search_type} (점수: {score:.3f})")
            
            return final_docs
            
        except Exception as e:
            logger.error(f"❌ 개선된 분리된 검색 실패: {e}")
            return []
    
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        키워드 추출을 통한 하이브리드 검색 수행
        
        Args:
            query: 검색 쿼리
            k: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        try:
            if not self.ensemble_retriever:
                logger.warning("⚠️ EnsembleRetriever가 초기화되지 않았습니다.")
                return []
            
            logger.info(f"🔍 키워드 추출 하이브리드 검색 시작: '{query}'")
            
            # 1. 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(query)
            keyword_query = " ".join(keywords)
            logger.info(f"🔑 추출된 키워드: {keywords}")
            
            # 2. 분리된 검색 실행
            # 벡터 검색: 원본 쿼리 사용
            vector_query = preprocess_for_embedding(query)
            
            # BM25 검색: 추출된 키워드 사용
            bm25_query = preprocess_for_embedding(keyword_query)
            
            logger.info(f"🔍 벡터 검색 쿼리: '{vector_query}'")
            logger.info(f"🔍 BM25 검색 쿼리: '{bm25_query}'")
            
            # 3. 분리된 검색 실행
            documents = self._perform_separated_search(vector_query, bm25_query)
            
            # 결과를 표준 형식으로 변환
            results = []
            for i, doc in enumerate(documents[:k]):
                result = {
                    "id": f"hybrid_{i}",
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": doc.metadata.get("similarity_score", 0.0),
                    "source": "hybrid_search",
                    "extracted_keywords": keywords  # 추출된 키워드 정보 추가
                }
                results.append(result)
            
            logger.info(f"✅ 키워드 추출 하이브리드 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ 키워드 추출 하이브리드 검색 실패: {e}")
            return []
    
    def get_search_info(self) -> Dict[str, Any]:
        """검색 시스템 정보 반환"""
        return {
            "total_documents": len(self.documents),
            "bm25_retriever_ready": self.bm25_retriever is not None,
            "ensemble_retriever_ready": self.ensemble_retriever is not None,
            "weights": [0.2, 0.8] if self.ensemble_retriever else None,  # BM25: 0.2, Vector: 0.8
            "weight_description": "BM25(키워드): 20%, Vector(의미): 80%" if self.ensemble_retriever else None
        }

def create_hybrid_search_retriever(vector_db_manager: VectorDBManager) -> HybridSearchRetriever:
    """HybridSearchRetriever 인스턴스 생성"""
    return HybridSearchRetriever(vector_db_manager)

if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)
    
    try:
        vector_db = VectorDBManager()
        hybrid_retriever = create_hybrid_search_retriever(vector_db)
        
        # 검색 테스트
        results = hybrid_retriever.search("서버 접속 문제", k=3)
        
        print(f"검색 결과: {len(results)}개")
        for i, result in enumerate(results):
            print(f"{i+1}. {result['content'][:100]}...")
            print(f"   소스: {result['metadata'].get('source', 'unknown')}")
            print(f"   유사도: {result['similarity_score']}")
            print()
        
        # 시스템 정보 출력
        info = hybrid_retriever.get_search_info()
        print(f"시스템 정보: {info}")
        
    except Exception as e:
        print(f"테스트 실패: {e}")
