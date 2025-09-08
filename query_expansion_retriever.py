#!/usr/bin/env python3
"""
질문 확장 + 순차 검색 Retriever
MultiQuery의 질문 확장 기능만 사용하고, 확장된 질문들을 순차적으로 검색
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.documents import Document
from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger(__name__)

class QueryExpansionRetriever:
    """질문 확장 + 순차 검색 Retriever"""
    
    def __init__(self, vector_db_manager, llm=None):
        """
        QueryExpansionRetriever 초기화
        
        Args:
            vector_db_manager: VectorDBManager 인스턴스
            llm: AzureChatOpenAI LLM 인스턴스 (선택사항)
        """
        self.vector_db_manager = vector_db_manager
        self.llm = llm or self._init_llm()
        logger.info("✅ QueryExpansionRetriever 초기화 완료")
    
    def _init_llm(self):
        """AzureChatOpenAI LLM 초기화"""
        try:
            llm = AzureChatOpenAI(
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                temperature=0,  # 일관된 결과를 위해 0으로 설정
                max_tokens=1000
            )
            logger.info("✅ AzureChatOpenAI LLM 초기화 완료")
            return llm
        except Exception as e:
            logger.error(f"❌ LLM 초기화 실패: {e}")
            return None
    
    def expand_query(self, query: str) -> List[str]:
        """
        단일 질문을 여러 관점의 질문으로 확장
        
        Args:
            query: 원본 질문
            
        Returns:
            확장된 질문 리스트
        """
        if not self.llm:
            logger.warning("LLM이 없어서 원본 질문만 반환합니다")
            return [query]
        
        try:
            # 질문 확장을 위한 프롬프트
            prompt = f"""
다음 질문을 다양한 관점에서 3개의 다른 질문으로 확장해주세요.
각 질문은 원본 질문의 핵심을 유지하면서도 서로 다른 접근 방식을 가져야 합니다.

원본 질문: {query}

다음 형식으로 3개의 질문을 생성해주세요:
1. [첫 번째 확장 질문]
2. [두 번째 확장 질문]  
3. [세 번째 확장 질문]

각 질문은 한 줄로 작성하고, 번호와 대괄호는 제외해주세요.
"""
            
            # LLM을 사용하여 질문 확장
            response = self.llm.invoke(prompt)
            expanded_text = response.content.strip()
            
            # 확장된 질문들을 파싱
            expanded_queries = []
            lines = expanded_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('1.', '2.', '3.')):
                    # 번호와 대괄호 제거
                    clean_query = line.replace('[', '').replace(']', '').strip()
                    if clean_query:
                        expanded_queries.append(clean_query)
            
            # 최소 1개, 최대 3개의 질문 보장
            if not expanded_queries:
                expanded_queries = [query]
            elif len(expanded_queries) > 3:
                expanded_queries = expanded_queries[:3]
            
            logger.info(f"✅ 질문 확장 완료: {len(expanded_queries)}개 질문 생성")
            for i, q in enumerate(expanded_queries, 1):
                logger.info(f"   {i}. {q}")
            
            return expanded_queries
            
        except Exception as e:
            logger.error(f"❌ 질문 확장 실패: {e}")
            return [query]
    
    def search_with_expansion(self, query: str, k: int = 5, 
                            search_type: str = "all") -> List[Dict[str, Any]]:
        """
        질문 확장 + 순차 검색 수행
        
        Args:
            query: 원본 질문
            k: 각 검색에서 반환할 결과 수
            search_type: 검색 타입 ("all", "mails", "file_chunks", "structured_chunks")
            
        Returns:
            통합된 검색 결과
        """
        try:
            logger.info(f"🔍 질문 확장 검색 시작: '{query}'")
            
            # 1단계: 질문 확장
            expanded_queries = self.expand_query(query)
            logger.info(f"📝 {len(expanded_queries)}개의 확장된 질문 생성")
            
            # 2단계: 각 확장된 질문으로 순차 검색
            all_results = []
            seen_ids = set()  # 중복 제거용
            
            for i, expanded_query in enumerate(expanded_queries, 1):
                logger.info(f"🔍 확장 질문 {i}/{len(expanded_queries)} 검색: '{expanded_query}'")
                
                # 검색 타입에 따라 다른 검색 수행
                if search_type == "all":
                    results = self._search_all_types(expanded_query, k)
                elif search_type == "mails":
                    results = self._search_mails(expanded_query, k)
                elif search_type == "file_chunks":
                    results = self._search_file_chunks(expanded_query, k)
                elif search_type == "structured_chunks":
                    results = self._search_structured_chunks(expanded_query, k)
                else:
                    results = self._search_all_types(expanded_query, k)
                
                # 중복 제거하면서 결과 추가
                for result in results:
                    result_id = result.get('id', '')
                    if result_id and result_id not in seen_ids:
                        seen_ids.add(result_id)
                        result['expanded_query'] = expanded_query
                        result['query_rank'] = i
                        all_results.append(result)
                
                logger.info(f"✅ 확장 질문 {i} 검색 완료: {len(results)}개 결과")
            
            # 3단계: 결과 정렬 및 제한
            # 유사도 점수와 쿼리 순위를 고려한 정렬
            all_results.sort(key=lambda x: (
                x.get('similarity_score', 0) * 0.7 +  # 유사도 점수 70%
                (1.0 / x.get('query_rank', 1)) * 0.3   # 쿼리 순위 30% (첫 번째 질문이 더 중요)
            ), reverse=True)
            
            # 최종 결과 수 제한
            final_results = all_results[:k]
            
            logger.info(f"✅ 질문 확장 검색 완료: {len(final_results)}개 최종 결과")
            return final_results
            
        except Exception as e:
            logger.error(f"❌ 질문 확장 검색 실패: {e}")
            # 폴백: 기본 검색
            return self._search_all_types(query, k)
    
    def _search_all_types(self, query: str, k: int) -> List[Dict[str, Any]]:
        """모든 타입 검색"""
        results = []
        
        # 메일 검색
        mail_results = self._search_mails(query, k//3 + 1)
        results.extend(mail_results)
        
        # 파일 청크 검색
        file_results = self._search_file_chunks(query, k//3 + 1)
        results.extend(file_results)
        
        # 구조적 청크 검색
        structured_results = self._search_structured_chunks(query, k//3 + 1)
        results.extend(structured_results)
        
        return results
    
    def _search_mails(self, query: str, k: int) -> List[Dict[str, Any]]:
        """메일 검색"""
        try:
            results = self.vector_db_manager.search_similar_mails(query, n_results=k)
            formatted_results = []
            
            for i, result in enumerate(results):
                formatted_results.append({
                    'id': getattr(result, 'message_id', f'mail_{i}'),
                    'content': getattr(result, 'refined_content', ''),
                    'metadata': {
                        'type': 'mail',
                        'subject': getattr(result, 'subject', ''),
                        'sender': getattr(result, 'sender', ''),
                        'status': getattr(result, 'status', ''),
                        'created_at': getattr(result, 'created_at', ''),
                    },
                    'similarity_score': getattr(result, 'similarity_score', 0.0),
                    'source': 'mail'
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"메일 검색 실패: {e}")
            return []
    
    def _search_file_chunks(self, query: str, k: int) -> List[Dict[str, Any]]:
        """파일 청크 검색"""
        try:
            results = self.vector_db_manager.search_similar_file_chunks(query, n_results=k)
            formatted_results = []
            
            for i, result in enumerate(results):
                # result는 딕셔너리이므로 get() 메서드 사용
                formatted_results.append({
                    'id': result.get('chunk_id', f'file_chunk_{i}'),
                    'content': result.get('content', ''),
                    'metadata': {
                        'type': 'file_chunk',
                        'file_name': result.get('file_name', ''),
                        'chunk_index': result.get('chunk_index', 0),
                        'created_at': result.get('created_at', ''),
                    },
                    'similarity_score': result.get('similarity_score', 0.0),
                    'source': 'file_chunk'
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"파일 청크 검색 실패: {e}")
            return []
    
    def _search_structured_chunks(self, query: str, k: int) -> List[Dict[str, Any]]:
        """구조적 청크 검색"""
        try:
            results = self.vector_db_manager.search_structured_chunks(query, n_results=k)
            formatted_results = []
            
            for i, result in enumerate(results):
                formatted_results.append({
                    'id': getattr(result, 'chunk_id', f'structured_chunk_{i}'),
                    'content': getattr(result, 'content', ''),
                    'metadata': {
                        'type': 'structured_chunk',
                        'chunk_type': getattr(result, 'chunk_type', ''),
                        'ticket_id': getattr(result, 'ticket_id', ''),
                        'field_type': getattr(result, 'field_type', ''),
                        'created_at': getattr(result, 'created_at', ''),
                    },
                    'similarity_score': getattr(result, 'similarity_score', 0.0),
                    'source': 'structured_chunk'
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"구조적 청크 검색 실패: {e}")
            return []


def create_query_expansion_retriever(vector_db_manager, llm=None):
    """
    QueryExpansionRetriever 인스턴스 생성
    
    Args:
        vector_db_manager: VectorDBManager 인스턴스
        llm: AzureChatOpenAI LLM 인스턴스 (선택사항)
        
    Returns:
        QueryExpansionRetriever 인스턴스
    """
    return QueryExpansionRetriever(vector_db_manager, llm)


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)
    
    try:
        from vector_db_models import VectorDBManager
        
        # VectorDBManager 생성
        vector_db_manager = VectorDBManager()
        
        # QueryExpansionRetriever 생성
        retriever = create_query_expansion_retriever(vector_db_manager)
        
        # 테스트 검색
        test_query = "서버 접속 문제"
        results = retriever.search_with_expansion(test_query, k=5)
        
        print(f"\n🎉 검색 완료: {len(results)}개 결과")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['content'][:100]}...")
            print(f"   유사도: {result['similarity_score']:.3f}")
            print(f"   소스: {result['source']}")
            print(f"   확장 질문: {result.get('expanded_query', 'N/A')}")
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()
