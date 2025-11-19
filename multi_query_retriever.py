#!/usr/bin/env python3
"""
MultiQueryRetriever 구현
사용자의 단일 질문을 LLM을 이용해 여러 개의 다른 관점을 가진 질문으로 확장하여
더 관련성 높은 문서를 찾아내는 RAG 검색 개선 모듈
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# LangChain imports - LangChain 1.0 호환
try:
    # LangChain 1.0+ - retrievers가 langchain_community로 이동
    try:
        from langchain_community.retrievers import MultiQueryRetriever
    except ImportError:
        # LangChain 0.2.x - 구버전 경로
        from langchain.retrievers.multi_query import MultiQueryRetriever

    from langchain_openai import AzureChatOpenAI
    from langchain_core.documents import Document
    from langchain_core.retrievers import BaseRetriever
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ LangChain 모듈 import 실패: {e}")
    LANGCHAIN_AVAILABLE = False
    # Import 실패 시 타입 힌트용 더미 클래스
    BaseRetriever = Any
    MultiQueryRetriever = None
    AzureChatOpenAI = None
    Document = None

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiQueryRetrieverWrapper:
    """MultiQueryRetriever 래퍼 클래스"""
    
    def __init__(self, base_retriever: BaseRetriever, llm: Optional[Any] = None):
        """
        MultiQueryRetriever 초기화
        
        Args:
            base_retriever: 기본 검색기 (ChromaDB 등)
            llm: AzureChatOpenAI LLM 인스턴스
        """
        self.base_retriever = base_retriever
        self.llm = llm
        self.multi_query_retriever = None
        
        if LANGCHAIN_AVAILABLE and self.llm:
            self._setup_multi_query_retriever()
        else:
            logger.warning("LangChain 또는 LLM이 사용 불가능합니다. 기본 검색기만 사용합니다.")
    
    def _setup_multi_query_retriever(self):
        """MultiQueryRetriever 설정"""
        try:
            # MultiQueryRetriever 생성
            self.multi_query_retriever = MultiQueryRetriever.from_llm(
                retriever=self.base_retriever,
                llm=self.llm
            )
            
            # 로깅 활성화 (생성된 질문들 확인용)
            logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)
            
            logger.info("✅ MultiQueryRetriever 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ MultiQueryRetriever 초기화 실패: {e}")
            self.multi_query_retriever = None
    
    def search(self, query: str, k: int = 5) -> List[Document]:
        """
        MultiQueryRetriever를 사용한 검색
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            
        Returns:
            검색된 문서 리스트
        """
        try:
            if self.multi_query_retriever:
                logger.info(f"🔍 MultiQueryRetriever 검색 시작: '{query}'")
                
                # MultiQueryRetriever 사용
                documents = self.multi_query_retriever.invoke(query)
                
                # 결과 수 제한
                if len(documents) > k:
                    documents = documents[:k]
                
                logger.info(f"✅ MultiQueryRetriever 검색 완료: {len(documents)}개 결과")
                return documents
                
            else:
                # 폴백: 기본 검색기 사용
                logger.warning("MultiQueryRetriever 사용 불가, 기본 검색기로 폴백")
                documents = self.base_retriever.invoke(query)
                
                # 결과 수 제한
                if len(documents) > k:
                    documents = documents[:k]
                
                return documents
                
        except Exception as e:
            logger.error(f"❌ MultiQueryRetriever 검색 실패: {e}")
            # 폴백: 기본 검색기 사용
            try:
                documents = self.base_retriever.invoke(query)
                if len(documents) > k:
                    documents = documents[:k]
                return documents
            except Exception as fallback_error:
                logger.error(f"❌ 기본 검색기도 실패: {fallback_error}")
                return []


class ChromaDBRetriever(BaseRetriever):
    """ChromaDB를 위한 BaseRetriever 구현"""
    
    vector_db_manager: Any
    collection_name: str
    k: int
    
    def __init__(self, vector_db_manager, collection_name: str = "mail_collection", **kwargs):
        """
        ChromaDB Retriever 초기화
        
        Args:
            vector_db_manager: VectorDBManager 인스턴스
            collection_name: 검색할 컬렉션 이름
        """
        super().__init__(
            vector_db_manager=vector_db_manager,
            collection_name=collection_name,
            k=5,
            **kwargs
        )
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        ChromaDB에서 관련 문서 검색
        
        Args:
            query: 검색 쿼리
            
        Returns:
            Document 리스트
        """
        try:
            # VectorDBManager가 None인 경우 빈 결과 반환
            if self.vector_db_manager is None:
                logger.warning("VectorDBManager가 None입니다. 빈 결과를 반환합니다.")
                return []
            
            # ChromaDB에서 검색
            if self.collection_name == "mail_collection":
                results = self.vector_db_manager.search_similar_mails(query, n_results=self.k)
            elif self.collection_name == "file_chunks":
                results = self.vector_db_manager.search_similar_file_chunks(query, n_results=self.k)
            elif self.collection_name == "structured_chunks":
                results = self.vector_db_manager.search_structured_chunks(query, n_results=self.k)
            else:
                logger.error(f"알 수 없는 컬렉션: {self.collection_name}")
                return []
            
            # 결과를 Document 형식으로 변환
            documents = []
            for result in results:
                if isinstance(result, dict):
                    # 딕셔너리 형태의 결과
                    content = result.get('content', '')
                    metadata = result.get('metadata', {})
                    metadata['similarity_score'] = result.get('similarity_score', 0.0)
                    metadata['source'] = result.get('source', 'unknown')
                else:
                    # 객체 형태의 결과 (Mail 등)
                    content = getattr(result, 'refined_content', str(result))
                    metadata = {
                        'message_id': getattr(result, 'message_id', ''),
                        'sender': getattr(result, 'sender', ''),
                        'subject': getattr(result, 'subject', ''),
                        'status': getattr(result, 'status', ''),
                        'similarity_score': getattr(result, 'similarity_score', 0.0),
                        'source': 'mail'
                    }
                
                if content:
                    doc = Document(page_content=content, metadata=metadata)
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"ChromaDB 검색 실패: {e}")
            return []
    
    def invoke(self, query: str, config: Optional[Dict] = None) -> List[Document]:
        """invoke 메서드 (LangChain 호환성)"""
        return self._get_relevant_documents(query)
    
    def get_relevant_documents(self, query: str, config: Optional[Dict] = None) -> List[Document]:
        """get_relevant_documents 메서드 (LangChain 호환성)"""
        return self._get_relevant_documents(query)


class AzureChatOpenAIManager:
    """AzureChatOpenAI LLM 관리자"""
    
    def __init__(self):
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """AzureChatOpenAI LLM 초기화"""
        try:
            if not LANGCHAIN_AVAILABLE:
                logger.warning("LangChain이 사용 불가능합니다.")
                return
            
            # Azure OpenAI 설정
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
            
            if not all([api_key, azure_endpoint, deployment_name]):
                logger.warning("Azure OpenAI 설정이 불완전합니다.")
                return
            
            # AzureChatOpenAI 인스턴스 생성
            self.llm = AzureChatOpenAI(
                azure_deployment=deployment_name,
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=api_version,
                temperature=0,  # 일관된 질문 생성을 위해 0으로 설정
                max_tokens=1000
            )
            
            logger.info("✅ AzureChatOpenAI LLM 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ AzureChatOpenAI LLM 초기화 실패: {e}")
            self.llm = None
    
    def get_llm(self) -> Optional[Any]:
        """LLM 인스턴스 반환"""
        return self.llm


class MultiQuerySearchManager:
    """MultiQuery 검색 관리자"""
    
    def __init__(self, vector_db_manager):
        """
        MultiQuery 검색 관리자 초기화
        
        Args:
            vector_db_manager: VectorDBManager 인스턴스
        """
        self.vector_db_manager = vector_db_manager
        self.llm_manager = AzureChatOpenAIManager()
        self.retrievers = {}
        self._setup_retrievers()
    
    def _setup_retrievers(self):
        """각 컬렉션별 MultiQueryRetriever 설정"""
        try:
            llm = self.llm_manager.get_llm()
            
            # 제한된 MultiQuery 사용: 메일 검색에만 적용
            mail_retriever = ChromaDBRetriever(self.vector_db_manager, "mail_collection")
            self.retrievers["mail"] = MultiQueryRetrieverWrapper(mail_retriever, llm)
            logger.info("✅ 메일 MultiQueryRetriever 초기화 완료")
            
            # 파일 청크와 구조적 청크는 기본 검색 사용 (메모리 절약)
            logger.info("⚠️ 파일 청크와 구조적 청크는 기본 검색 사용 (메모리 절약)")
            
            logger.info("✅ MultiQuery 검색 관리자 초기화 완료 (제한된 MultiQuery 활성화)")
            
        except Exception as e:
            logger.error(f"❌ MultiQuery 검색 관리자 초기화 실패: {e}")
            logger.info("⚠️ 기본 검색 모드로 폴백합니다")
    
    def search_mails(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """메일 검색 (MultiQuery 적용)"""
        try:
            if "mail" in self.retrievers:
                logger.info(f"🔍 MultiQuery 메일 검색 시작: '{query}'")
                documents = self.retrievers["mail"].search(query, k)
                results = self._documents_to_dict_list(documents, "mail")
                logger.info(f"✅ MultiQuery 메일 검색 완료: {len(results)}개 결과")
                return results
            else:
                # 폴백: 기본 검색
                logger.info(f"🔍 메일 검색 시작: '{query}' (기본 검색 사용)")
                results = self.vector_db_manager.search_similar_mails(query, n_results=k)
                logger.info(f"✅ 메일 검색 완료: {len(results)}개 결과")
                return results
                
        except Exception as e:
            logger.error(f"메일 검색 실패: {e}")
            # 폴백: 기본 검색
            try:
                logger.info("기본 메일 검색으로 폴백 시도")
                return self.vector_db_manager.search_similar_mails(query, n_results=k)
            except Exception as fallback_error:
                logger.error(f"기본 메일 검색도 실패: {fallback_error}")
                return []
    
    def search_file_chunks(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """파일 청크 검색 (MultiQuery 적용)"""
        try:
            if "file_chunks" in self.retrievers:
                logger.info(f"🔍 MultiQuery 파일 청크 검색 시작: '{query}'")
                documents = self.retrievers["file_chunks"].search(query, k)
                results = self._documents_to_dict_list(documents, "file_chunks")
                logger.info(f"✅ MultiQuery 파일 청크 검색 완료: {len(results)}개 결과")
                return results
            else:
                # 폴백: 기본 검색
                logger.info(f"🔍 파일 청크 검색 시작: '{query}' (기본 검색 사용)")
                results = self.vector_db_manager.search_similar_file_chunks(query, n_results=k)
                logger.info(f"✅ 파일 청크 검색 완료: {len(results)}개 결과")
                return results
                
        except Exception as e:
            logger.error(f"파일 청크 검색 실패: {e}")
            # 폴백: 기본 검색
            try:
                logger.info("기본 파일 청크 검색으로 폴백 시도")
                return self.vector_db_manager.search_similar_file_chunks(query, n_results=k)
            except Exception as fallback_error:
                logger.error(f"기본 파일 청크 검색도 실패: {fallback_error}")
                return []
    
    def search_structured_chunks(self, query: str, k: int = 5, 
                                chunk_types: List[str] = None, 
                                ticket_ids: List[str] = None,
                                priority_filter: int = None) -> List[Dict[str, Any]]:
        """구조적 청크 검색 (MultiQuery 적용)"""
        try:
            if "structured_chunks" in self.retrievers:
                logger.info(f"🔍 MultiQuery 구조적 청크 검색 시작: '{query}'")
                documents = self.retrievers["structured_chunks"].search(query, k)
                results = self._documents_to_dict_list(documents, "structured_chunks")
                
                # 필터 적용
                if chunk_types or ticket_ids or priority_filter:
                    results = self._apply_filters(results, chunk_types, ticket_ids, priority_filter)
                
                logger.info(f"✅ MultiQuery 구조적 청크 검색 완료: {len(results)}개 결과")
                return results
            else:
                # 폴백: 기본 검색
                logger.info(f"🔍 구조적 청크 검색 시작: '{query}' (기본 검색 사용)")
                results = self.vector_db_manager.search_structured_chunks(
                    query, n_results=k, chunk_types=chunk_types, 
                    ticket_ids=ticket_ids, priority_filter=priority_filter
                )
                logger.info(f"✅ 구조적 청크 검색 완료: {len(results)}개 결과")
                return results
                
        except Exception as e:
            logger.error(f"구조적 청크 검색 실패: {e}")
            # 폴백: 기본 검색
            try:
                logger.info("기본 구조적 청크 검색으로 폴백 시도")
                return self.vector_db_manager.search_structured_chunks(
                    query, n_results=k, chunk_types=chunk_types, 
                    ticket_ids=ticket_ids, priority_filter=priority_filter
                )
            except Exception as fallback_error:
                logger.error(f"기본 구조적 청크 검색도 실패: {fallback_error}")
                return []
    
    def _documents_to_dict_list(self, documents: List[Document], source_type: str) -> List[Dict[str, Any]]:
        """Document 리스트를 딕셔너리 리스트로 변환"""
        results = []
        for i, doc in enumerate(documents):
            result = {
                "id": f"multi_query_{source_type}_{i}",
                "content": doc.page_content,
                "source": f"multi_query_{source_type}",
                "similarity_score": doc.metadata.get("similarity_score", 0.0),
                "metadata": doc.metadata
            }
            results.append(result)
        return results
    
    def _apply_filters(self, results: List[Dict[str, Any]], 
                      chunk_types: List[str] = None, 
                      ticket_ids: List[str] = None,
                      priority_filter: int = None) -> List[Dict[str, Any]]:
        """검색 결과에 필터 적용"""
        filtered_results = []
        
        for result in results:
            metadata = result.get("metadata", {})
            
            # 청크 타입 필터
            if chunk_types and metadata.get("chunk_type") not in chunk_types:
                continue
            
            # 티켓 ID 필터
            if ticket_ids and metadata.get("ticket_id") not in ticket_ids:
                continue
            
            # 우선순위 필터
            if priority_filter and metadata.get("priority", 3) > priority_filter:
                continue
            
            filtered_results.append(result)
        
        return filtered_results


def create_multi_query_search_manager(vector_db_manager) -> MultiQuerySearchManager:
    """
    MultiQuery 검색 관리자 생성 (편의 함수)
    
    Args:
        vector_db_manager: VectorDBManager 인스턴스
        
    Returns:
        MultiQuerySearchManager 인스턴스
    """
    return MultiQuerySearchManager(vector_db_manager)


def main():
    """테스트용 메인 함수"""
    print("🧪 MultiQueryRetriever 테스트")
    print("=" * 60)
    
    try:
        # Vector DB 매니저 초기화
        from vector_db_models import VectorDBManager
        vector_db = VectorDBManager()
        
        # MultiQuery 검색 관리자 생성
        search_manager = create_multi_query_search_manager(vector_db)
        
        # 테스트 쿼리
        test_query = "서버 접속 문제 해결 방법"
        print(f"테스트 쿼리: {test_query}")
        
        # 메일 검색 테스트
        print("\n--- 메일 검색 테스트 ---")
        mail_results = search_manager.search_mails(test_query, k=3)
        print(f"메일 검색 결과: {len(mail_results)}개")
        for i, result in enumerate(mail_results, 1):
            print(f"  {i}. {result['content'][:100]}...")
        
        # 파일 청크 검색 테스트
        print("\n--- 파일 청크 검색 테스트 ---")
        chunk_results = search_manager.search_file_chunks(test_query, k=3)
        print(f"파일 청크 검색 결과: {len(chunk_results)}개")
        for i, result in enumerate(chunk_results, 1):
            print(f"  {i}. {result['content'][:100]}...")
        
        # 구조적 청크 검색 테스트
        print("\n--- 구조적 청크 검색 테스트 ---")
        structured_results = search_manager.search_structured_chunks(test_query, k=3)
        print(f"구조적 청크 검색 결과: {len(structured_results)}개")
        for i, result in enumerate(structured_results, 1):
            print(f"  {i}. {result['content'][:100]}...")
        
        print("\n✅ MultiQueryRetriever 테스트 완료")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
