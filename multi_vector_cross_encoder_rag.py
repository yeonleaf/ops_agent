#!/usr/bin/env python3
"""
Multi-Vector + Cross-Encoder RAG 시스템
1단계: Multi-Vector 전략으로 Vector DB에서 후보 검색
2단계: Cross-Encoder로 Re-ranking
"""

import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from cross_encoder_reranker import MultiVectorReranker

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiVectorCrossEncoderRAG:
    """
    Multi-Vector + Cross-Encoder RAG 시스템
    1단계: Multi-Vector 전략으로 Vector DB에서 후보 검색
    2단계: Cross-Encoder로 Re-ranking
    """
    
    def __init__(self, collection_name: str = "jira_multi_vector_chunks"):
        """
        Multi-Vector Cross-Encoder RAG 초기화
        
        Args:
            collection_name: ChromaDB 컬렉션 이름
        """
        self.collection_name = collection_name
        self.chroma_client = None
        self.collection = None
        self.cross_encoder_reranker = None
        
        # ChromaDB 연결
        self._connect_chromadb()
        
        # Multi-Vector Re-ranker 초기화
        self._init_reranker()
    
    def _connect_chromadb(self):
        """ChromaDB 연결"""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path='./vector_db',
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.chroma_client.get_collection(self.collection_name)
            logger.info(f"✅ ChromaDB 연결 완료: {self.collection_name}")
        except Exception as e:
            logger.error(f"❌ ChromaDB 연결 실패: {e}")
            raise e
    
    def _init_reranker(self):
        """Multi-Vector Re-ranker 초기화"""
        try:
            self.cross_encoder_reranker = MultiVectorReranker()
            logger.info("✅ Multi-Vector Re-ranker 초기화 완료")
        except Exception as e:
            logger.error(f"❌ Multi-Vector Re-ranker 초기화 실패: {e}")
            raise e
    
    def search(self, query: str, n_candidates: int = 50, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Multi-Vector + Cross-Encoder 검색 수행
        
        Args:
            query: 사용자 질문
            n_candidates: 1단계에서 가져올 후보 수
            top_k: 최종 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        try:
            logger.info(f"🚀 Multi-Vector + Cross-Encoder 검색 시작: '{query}'")
            
            # Cross-Encoder Re-ranker를 사용한 검색 및 Re-ranking
            results = self.cross_encoder_reranker.search_and_rerank(
                query=query,
                n_candidates=n_candidates,
                top_k=top_k
            )
            
            # 결과 포맷팅
            formatted_results = []
            for i, result in enumerate(results):
                formatted_results.append({
                    "id": result['ticket_id'],
                    "content": result['text'],
                    "metadata": {
                        'ticket_id': result['ticket_id'],
                        'parent_ticket_id': result['ticket_id'],
                        'chunk_type': 'multi_vector',
                        'cross_encoder_score': result['score'],
                        'search_method': 'multi_vector_cross_encoder'
                    },
                    "similarity_score": result['score'],
                    "source": "multi_vector_cross_encoder",
                    "search_type": "cross_encoder_rerank"
                })
            
            logger.info(f"✅ Multi-Vector + Cross-Encoder 검색 완료: {len(formatted_results)}개 결과")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Multi-Vector + Cross-Encoder 검색 실패: {e}")
            return []
    
    def get_search_info(self) -> Dict[str, Any]:
        """검색 시스템 정보 반환"""
        try:
            # 컬렉션 통계 조회
            collection_count = self.collection.count()
            
            return {
                "search_method": "multi_vector_cross_encoder",
                "collection_name": self.collection_name,
                "collection_count": collection_count,
                "cross_encoder_model": self.cross_encoder_reranker.model_name if self.cross_encoder_reranker else "unknown",
                "pipeline_steps": [
                    "1. Multi-Vector Search (top 50)",
                    "2. Parent Ticket ID Aggregation", 
                    "3. Full Text Collection",
                    "4. Cross-Encoder Re-ranking (top 10)"
                ],
                "features": [
                    "Multi-Vector Representation",
                    "Context-Preserving Comment Chunks",
                    "Cross-Encoder Re-ranking",
                    "Korean Language Support"
                ]
            }
        except Exception as e:
            logger.error(f"❌ 검색 시스템 정보 조회 실패: {e}")
            return {"error": str(e)}


def test_multi_vector_cross_encoder_rag():
    """Multi-Vector Cross-Encoder RAG 테스트"""
    try:
        # RAG 시스템 초기화
        rag = MultiVectorCrossEncoderRAG()
        
        # 시스템 정보 출력
        info = rag.get_search_info()
        print("🔍 Multi-Vector Cross-Encoder RAG 시스템 정보:")
        print(f"   컬렉션: {info.get('collection_name')}")
        print(f"   문서 수: {info.get('collection_count')}")
        print(f"   Cross-Encoder 모델: {info.get('cross_encoder_model')}")
        print()
        
        # 테스트 쿼리
        test_queries = [
            "서버 접속 문제",
            "데이터베이스 오류",
            "배치 작업 실패",
            "로그인 오류",
            "성능 최적화"
        ]
        
        for query in test_queries:
            print(f"🔍 테스트 쿼리: '{query}'")
            print("=" * 60)
            
            results = rag.search(query, n_candidates=20, top_k=5)
            
            for i, result in enumerate(results):
                print(f"{i+1}. 티켓: {result['id']}")
                print(f"   점수: {result['similarity_score']:.4f}")
                print(f"   내용: {result['content'][:100]}...")
                print()
            
            print()
    
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")


if __name__ == "__main__":
    test_multi_vector_cross_encoder_rag()
