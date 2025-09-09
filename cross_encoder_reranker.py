#!/usr/bin/env python3
"""
Cross-Encoder 기반 Re-ranking 시스템
Multi-Vector 전략의 2단계에서 Whoosh Re-ranker를 대체
"""

import logging
import gc
import torch
from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
import chromadb
from chromadb.config import Settings

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiVectorReranker:
    """Multi-Vector 기반 Re-ranking 클래스 (Cross-Encoder 사용)"""
    
    def __init__(self, model_name: str = "bongsoo/kpf-cross-encoder-v1"):
        """
        Multi-Vector Re-ranker 초기화 (한국어 Cross-Encoder 사용)
        
        Args:
            model_name: 사용할 Cross-Encoder 모델명 (기본값: bongsoo/kpf-cross-encoder-v1)
        """
        self.model_name = model_name
        self.cross_encoder = None
        self.embedding_function = None  # 임베딩 함수 캐싱
        self.chroma_client = None
        self.collection = None
        
        # Cross-Encoder 모델 로드
        self._load_cross_encoder()
        
        # 임베딩 함수 로드 (한 번만)
        self._load_embedding_function()
        
        # ChromaDB 연결
        self._connect_chromadb()
    
    def _load_cross_encoder(self):
        """Cross-Encoder 모델 로드"""
        try:
            logger.info(f"🔄 Cross-Encoder 모델 로딩 중: {self.model_name}")
            self.cross_encoder = CrossEncoder(self.model_name)
            logger.info("✅ Cross-Encoder 모델 로딩 완료")
        except Exception as e:
            logger.error(f"❌ Cross-Encoder 모델 로딩 실패: {e}")
            # 대체 모델 시도
            try:
                logger.info("🔄 대체 모델 시도: cross-encoder/ms-marco-MiniLM-L-6-v2")
                self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("✅ 대체 Cross-Encoder 모델 로딩 완료")
            except Exception as e2:
                logger.error(f"❌ 대체 모델도 로딩 실패: {e2}")
                raise e2
    
    def _load_embedding_function(self):
        """임베딩 함수 로드 (한 번만)"""
        try:
            logger.info("🔄 임베딩 함수 로딩 중...")
            from clean_korean_embedding import CleanKoreanEmbeddingFunction
            self.embedding_function = CleanKoreanEmbeddingFunction()
            logger.info("✅ 임베딩 함수 로딩 완료")
        except Exception as e:
            logger.error(f"❌ 임베딩 함수 로딩 실패: {e}")
            raise e
    
    def _connect_chromadb(self):
        """ChromaDB 연결"""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path='./vector_db',
                settings=Settings(anonymized_telemetry=False)
            )
            # 기존 컬렉션의 임베딩 함수를 사용하여 연결
            from clean_korean_embedding import CleanKoreanEmbeddingFunction
            embedding_function = CleanKoreanEmbeddingFunction()
            
            # 컬렉션 연결 (임베딩 함수 없이)
            self.collection = self.chroma_client.get_collection('jira_multi_vector_chunks')
            logger.info("✅ ChromaDB 연결 완료")
        except Exception as e:
            logger.error(f"❌ ChromaDB 연결 실패: {e}")
            raise e
    
    def _cleanup_memory(self):
        """메모리 정리"""
        try:
            # PyTorch 캐시 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            
            # Python 가비지 컬렉션
            gc.collect()
            
            logger.debug("🧹 메모리 정리 완료")
        except Exception as e:
            logger.warning(f"⚠️ 메모리 정리 실패: {e}")
    
    def get_ticket_full_text(self, parent_ticket_id: str) -> str:
        """
        특정 티켓의 전체 텍스트를 수집 (캐싱된 임베딩 모델 사용)
        
        Args:
            parent_ticket_id: 부모 티켓 ID
            
        Returns:
            티켓의 전체 텍스트 (제목 + 설명 + 댓글)
        """
        try:
            # 해당 티켓의 모든 청크 조회 (캐싱된 임베딩 모델 사용)
            if not self.embedding_function:
                logger.error("❌ 임베딩 함수가 로드되지 않았습니다")
                return ""
            
            results = self.collection.query(
                query_embeddings=[self.embedding_function([""])[0]],  # 빈 쿼리 임베딩
                n_results=1000,  # 충분히 큰 수
                where={"parent_ticket_id": parent_ticket_id}
            )
            
            if not results['documents'] or not results['documents'][0]:
                logger.warning(f"⚠️ 티켓 {parent_ticket_id}의 청크를 찾을 수 없습니다")
                return ""
            
            # 청크 타입별로 텍스트 수집
            title_text = ""
            description_text = ""
            comment_texts = []
            
            for i, metadata in enumerate(results['metadatas'][0]):
                chunk_type = metadata.get('chunk_type', '')
                original_content = metadata.get('original_content', '')
                
                if chunk_type == 'summary':
                    title_text = original_content
                elif chunk_type == 'description':
                    description_text = original_content
                elif chunk_type == 'comment':
                    comment_texts.append(original_content)
            
            # 전체 텍스트 조합
            full_text_parts = []
            
            if title_text:
                full_text_parts.append(f"제목: {title_text}")
            
            if description_text:
                full_text_parts.append(f"설명: {description_text}")
            
            if comment_texts:
                comments_text = "\n".join([f"댓글: {comment}" for comment in comment_texts])
                full_text_parts.append(comments_text)
            
            full_text = "\n\n".join(full_text_parts)
            
            logger.debug(f"📄 티켓 {parent_ticket_id} 전체 텍스트 길이: {len(full_text)}자")
            return full_text
            
        except Exception as e:
            logger.error(f"❌ 티켓 {parent_ticket_id} 텍스트 수집 실패: {e}")
            return ""
    
    
    def search_and_rerank(self, query: str, n_candidates: int = 30, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        올바른 RAG 시스템 구현
        1단계: Indexer (ko-sroberta-multitask)로 후보 검색
        2단계: Expert Grader (bongsoo/kpf-cross-encoder-v1)로 Re-ranking
        
        Args:
            query: 사용자 질문
            n_candidates: 1단계에서 가져올 후보 수
            top_k: 최종 반환할 결과 수
            
        Returns:
            최종 검색 결과
        """
        try:
            logger.info(f"🔍 올바른 RAG 시스템 시작: '{query}'")
            
            # === 1단계: 후보군 검색 (Indexer의 역할) ===
            logger.info(f"📊 1단계: Indexer(ko-sroberta-multitask)로 {n_candidates}개 후보 검색")
            
            # 1. 사용자 질문을 'Indexer'(ko-sroberta-multitask)를 이용해 768차원 벡터로 변환
            if not self.embedding_function:
                logger.error("❌ 임베딩 함수가 로드되지 않았습니다")
                return []
            
            query_embedding = self.embedding_function([query])[0]
            
            # 2. ChromaDB에서 후보 청크 검색 (embedding_function 인자 없이)
            search_results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_candidates
            )
            
            if not search_results['documents'] or not search_results['documents'][0]:
                logger.warning("⚠️ 검색 결과가 없습니다")
                return []
            
            # 3. 후보 청크에서 중복 없는 부모 티켓 ID와 전체 내용 추출
            parent_ticket_ids = set()
            for metadata in search_results['metadatas'][0]:
                parent_ticket_id = metadata.get('parent_ticket_id', '')
                if parent_ticket_id:
                    parent_ticket_ids.add(parent_ticket_id)
            
            candidate_ticket_ids = list(parent_ticket_ids)
            logger.info(f"📊 수집된 고유 티켓 수: {len(candidate_ticket_ids)}개")
            
            # === 2단계: 재정렬 (Expert Grader의 역할) ===
            logger.info(f"🔄 2단계: Expert Grader(bongsoo/kpf-cross-encoder-v1)로 Re-ranking")
            
            # 4. 'Expert Grader'(bongsoo/kpf-cross-encoder-v1) 모델 로드
            if not self.cross_encoder:
                logger.error("❌ Cross-Encoder 모델이 로드되지 않았습니다")
                return []
            
            # 5. [ (질문, 후보 티켓1 내용), (질문, 후보 티켓2 내용), ... ] 형태의 쌍(pair) 생성
            sentence_pairs = []
            candidate_tickets = []
            
            for ticket_id in candidate_ticket_ids:
                full_text = self.get_ticket_full_text(ticket_id)
                if full_text:
                    sentence_pairs.append([query, full_text])
                    candidate_tickets.append({
                        'ticket_id': ticket_id,
                        'full_text': full_text
                    })
            
            if not sentence_pairs:
                logger.warning("⚠️ 후보 티켓의 전체 텍스트를 수집할 수 없습니다")
                return []
            
            # 6. Cross-Encoder로 각 쌍의 관련도 점수 계산
            logger.info(f"🔄 {len(sentence_pairs)}개 쌍에 대해 Cross-Encoder 점수 계산 중...")
            scores = self.cross_encoder.predict(sentence_pairs)
            
            # 7. 점수를 기준으로 후보 티켓들을 내림차순 정렬
            sorted_tickets = sorted(zip(scores, candidate_tickets), key=lambda x: x[0], reverse=True)
            
            # === 3단계: 최종 결과 반환 ===
            final_results = []
            for i, (score, ticket) in enumerate(sorted_tickets[:top_k]):
                final_results.append({
                    'ticket_id': ticket['ticket_id'],
                    'score': float(score),
                    'text': ticket['full_text'][:200] + "..." if len(ticket['full_text']) > 200 else ticket['full_text']
                })
            
            logger.info(f"✅ 올바른 RAG 시스템 완료: 상위 {len(final_results)}개 결과 반환")
            for i, result in enumerate(final_results[:3]):  # 상위 3개만 로그
                logger.info(f"  {i+1}. 티켓: {result['ticket_id']}, 점수: {result['score']:.4f}")
            
            # 메모리 정리
            self._cleanup_memory()
            
            return final_results
            
        except Exception as e:
            logger.error(f"❌ 검색 및 Re-ranking 실패: {e}")
            # 에러 발생 시에도 메모리 정리
            self._cleanup_memory()
            return []


def test_cross_encoder_reranker():
    """Cross-Encoder Re-ranker 테스트"""
    try:
        # Re-ranker 초기화
        reranker = CrossEncoderReranker()
        
        # 테스트 쿼리
        test_queries = [
            "서버 접속 문제",
            "데이터베이스 오류",
            "배치 작업 실패"
        ]
        
        for query in test_queries:
            print(f"\n🔍 테스트 쿼리: '{query}'")
            print("=" * 50)
            
            results = reranker.search_and_rerank(query, n_candidates=20, top_k=5)
            
            for i, result in enumerate(results):
                print(f"{i+1}. 티켓: {result['ticket_id']}")
                print(f"   점수: {result['score']:.4f}")
                print(f"   내용: {result['text']}")
                print()
    
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")


if __name__ == "__main__":
    test_cross_encoder_reranker()
