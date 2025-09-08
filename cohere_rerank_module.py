"""
Cohere Re-ranking을 활용한 압축 검색 파이프라인 모듈

이 모듈은 LangChain의 ContextualCompressionRetriever와 Cohere의 Re-rank 모델을 사용하여
RAG 시스템의 검색 정확도를 향상시킵니다.
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain.retrievers.document_compressors import DocumentCompressorPipeline
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from vector_db_models import VectorDBManager

# 텍스트 전처리 모듈 import
from text_preprocessor import preprocess_for_embedding

# 환경 변수 로드
load_dotenv()

class CohereRerankRetriever:
    """Cohere Re-ranking을 활용한 압축 검색기"""
    
    def __init__(self, cohere_api_key: Optional[str] = None):
        """
        Cohere Re-ranking 검색기 초기화
        
        Args:
            cohere_api_key: Cohere API 키 (None이면 환경변수에서 로드)
        """
        self.cohere_api_key = cohere_api_key or os.getenv('COHERE_API_KEY')
        if not self.cohere_api_key:
            raise ValueError("COHERE_API_KEY가 설정되지 않았습니다. .env 파일에 COHERE_API_KEY를 추가하세요.")
        
        self.vector_db = VectorDBManager()
        self._setup_retrievers()
    
    def _setup_retrievers(self):
        """검색기 설정"""
        # 1. 기본 검색기 (Vector DB Retriever) 생성
        self.base_retriever = VectorDBRetriever(self.vector_db)
        
        # 2. Cohere Re-rank 압축기 생성
        self.rerank_compressor = CohereRerank(
            cohere_api_key=self.cohere_api_key,
            top_n=3,  # 최종 반환할 문서 개수
            model="rerank-multilingual-v3.0"  # 다국어 지원 모델
        )
        
        # 3. 압축 검색기 생성
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.rerank_compressor,
            base_retriever=self.base_retriever
        )
    
    def search_with_rerank(self, query: str, k: int = 20) -> List[Dict[str, Any]]:
        """
        Cohere Re-ranking을 활용한 압축 검색 실행
        
        Args:
            query: 검색 쿼리
            k: 1차 검색에서 가져올 후보 문서 수 (기본값: 20)
            
        Returns:
            재순위화된 검색 결과 리스트
        """
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            print(f"🔍 Cohere Re-ranking 검색 시작: '{preprocessed_query}'")
            
            # 1차 검색에서 더 많은 후보를 가져오기 위해 k 설정
            self.base_retriever.k = k
            
            # 압축 검색 실행
            documents = self.compression_retriever.get_relevant_documents(preprocessed_query)
            
            # 결과를 표준 형식으로 변환
            results = []
            for i, doc in enumerate(documents):
                result = {
                    "id": f"rerank-{i}",
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": doc.metadata.get("similarity_score", 0.0),
                    "rerank_score": doc.metadata.get("rerank_score", 0.0),
                    "source": "cohere_rerank"
                }
                results.append(result)
            
            print(f"✅ Cohere Re-ranking 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            print(f"❌ Cohere Re-ranking 검색 실패: {str(e)}")
            # 폴백: 기본 벡터 검색 사용
            print("🔄 기본 벡터 검색으로 폴백...")
            return self._fallback_search(query)
    
    def _fallback_search(self, query: str) -> List[Dict[str, Any]]:
        """Cohere Re-ranking 실패 시 기본 벡터 검색으로 폴백"""
        try:
            # 메일 검색
            similar_emails = self.vector_db.search_similar_mails(query, n_results=2)
            
            # 파일 청크 검색
            similar_chunks = self.vector_db.search_similar_file_chunks(query, n_results=3)
            
            # 결과 통합
            results = []
            
            # 메일 결과 추가
            for email in similar_emails:
                results.append({
                    "id": email.get("message_id", "unknown"),
                    "content": email.get("content", ""),
                    "metadata": {
                        "source": "mail",
                        "subject": email.get("subject", ""),
                        "sender": email.get("sender", "")
                    },
                    "similarity_score": email.get("similarity_score", 0.0),
                    "source": "fallback_mail"
                })
            
            # 파일 청크 결과 추가
            for chunk in similar_chunks:
                results.append({
                    "id": chunk.get("chunk_id", "unknown"),
                    "content": chunk.get("content", ""),
                    "metadata": {
                        "source": "file_chunk",
                        "file_name": chunk.get("file_name", ""),
                        "file_type": chunk.get("file_type", "")
                    },
                    "similarity_score": chunk.get("similarity_score", 0.0),
                    "source": "fallback_chunk"
                })
            
            # 유사도 점수 기준으로 정렬
            results.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
            
            return results[:5]  # 상위 5개만 반환
            
        except Exception as e:
            print(f"❌ 폴백 검색도 실패: {str(e)}")
            return []


class VectorDBRetriever(BaseRetriever):
    """Vector DB를 LangChain Retriever로 래핑"""
    
    def __init__(self, vector_db: VectorDBManager, k: int = 20):
        """
        Vector DB Retriever 초기화
        
        Args:
            vector_db: VectorDBManager 인스턴스
            k: 검색할 문서 수
        """
        super().__init__()
        # Pydantic 모델이므로 필드를 직접 설정하지 않고 저장
        self._vector_db = vector_db
        self._k = k
    
    @property
    def vector_db(self):
        return self._vector_db
    
    @property
    def k(self):
        return self._k
    
    @k.setter
    def k(self, value):
        self._k = value
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        쿼리에 대한 관련 문서 검색
        
        Args:
            query: 검색 쿼리
            
        Returns:
            LangChain Document 리스트
        """
        try:
            print(f"🔍 VectorDBRetriever 검색 시작: '{query}', k={self.k}")
            
            # 메일과 파일 청크를 모두 검색
            similar_emails = self.vector_db.search_similar_mails(query, n_results=self.k // 2)
            similar_chunks = self.vector_db.search_similar_file_chunks(query, n_results=self.k // 2)
            
            print(f"📊 검색 결과: 메일 {len(similar_emails)}개, 파일 청크 {len(similar_chunks)}개")
            
            documents = []
            
            # 메일 결과를 Document로 변환
            for email in similar_emails:
                content = f"Subject: {email.get('subject', '')}\nSender: {email.get('sender', '')}\nContent: {email.get('content', '')}"
                metadata = {
                    "source": "mail",
                    "message_id": email.get("message_id", ""),
                    "subject": email.get("subject", ""),
                    "sender": email.get("sender", ""),
                    "similarity_score": email.get("similarity_score", 0.0)
                }
                documents.append(Document(page_content=content, metadata=metadata))
                print(f"📧 메일 문서 추가: {len(content)}자")
            
            # 파일 청크 결과를 Document로 변환
            for chunk in similar_chunks:
                content = chunk.get("content", "")
                metadata = {
                    "source": "file_chunk",
                    "chunk_id": chunk.get("chunk_id", ""),
                    "file_name": chunk.get("file_name", ""),
                    "file_type": chunk.get("file_type", ""),
                    "similarity_score": chunk.get("similarity_score", 0.0)
                }
                documents.append(Document(page_content=content, metadata=metadata))
                print(f"📄 파일 청크 문서 추가: {len(content)}자")
            
            print(f"✅ 총 {len(documents)}개 문서 생성 완료")
            return documents
            
        except Exception as e:
            print(f"❌ Vector DB 검색 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return []


# 전역 인스턴스
cohere_rerank_retriever = None

def get_cohere_rerank_retriever() -> CohereRerankRetriever:
    """Cohere Re-ranking 검색기 인스턴스 반환"""
    global cohere_rerank_retriever
    if cohere_rerank_retriever is None:
        cohere_rerank_retriever = CohereRerankRetriever()
    return cohere_rerank_retriever


def search_with_cohere_rerank(query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Cohere Re-ranking을 활용한 검색 실행 (편의 함수)
    
    Args:
        query: 검색 쿼리
        k: 1차 검색에서 가져올 후보 문서 수
        
    Returns:
        재순위화된 검색 결과 리스트
    """
    retriever = get_cohere_rerank_retriever()
    return retriever.search_with_rerank(query, k)


if __name__ == "__main__":
    # 테스트 코드
    print("🧪 Cohere Re-ranking 시스템 테스트")
    
    try:
        # 검색 테스트
        query = "서버 접속 불가 문제"
        results = search_with_cohere_rerank(query, k=10)
        
        print(f"\n📊 검색 결과: {len(results)}개")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['source']}")
            print(f"   유사도: {result.get('similarity_score', 0.0):.3f}")
            print(f"   내용: {result['content'][:100]}...")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        print("💡 COHERE_API_KEY가 .env 파일에 설정되어 있는지 확인하세요.")
