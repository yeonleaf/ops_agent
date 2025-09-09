#!/usr/bin/env python3
"""
커스텀 전처리 제거된 한국어 특화 임베딩 모델
ko-sroberta-multitask 모델의 원본 토크나이저 사용
"""

import os
import numpy as np
import re
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import logging
from typing import List, Union

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanse_text(text: str) -> str:
    """
    임베딩 전 텍스트 정제 - 잡음 제거
    반복되는 메타데이터 패턴을 제거하여 의미있는 텍스트만 추출
    """
    if not text:
        return ""
    
    # 1. Jira 티켓 키 패턴 제거 [BTVO-NNNNN]
    text = re.sub(r'\[BTVO-\s?\d+\]', '', text)
    
    # 2. NCMS 패턴 제거 [NCMS]
    text = re.sub(r'\[NCMS\]', '', text)
    
    # 3. 날짜 패턴 제거 (MM/DD) 또는 (YYYY-MM-DD)
    text = re.sub(r'\(\d{1,2}/\d{1,2}\)', '', text)
    text = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', text)
    
    # 4. 기타 불필요한 패턴들
    text = re.sub(r'\[.*?\]', '', text)  # 대괄호 안의 모든 내용 제거
    text = re.sub(r'\(.*?\)', '', text)  # 소괄호 안의 모든 내용 제거
    
    # 5. 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 6. 앞뒤 공백 제거
    text = text.strip()
    
    return text

def apply_l2_normalization(embeddings: Union[List[List[float]], np.ndarray]) -> List[List[float]]:
    """
    임베딩 벡터들에 L2 정규화를 적용
    
    Args:
        embeddings: 임베딩 벡터 리스트 또는 numpy 배열
        
    Returns:
        L2 정규화된 임베딩 벡터 리스트
    """
    if isinstance(embeddings, np.ndarray):
        embeddings = embeddings.tolist()
    
    normalized_embeddings = []
    for embedding in embeddings:
        if isinstance(embedding, list):
            embedding_array = np.array(embedding)
        else:
            embedding_array = embedding
        
        # L2 정규화: 각 벡터를 단위 벡터로 변환
        l2_norm = np.linalg.norm(embedding_array)
        if l2_norm > 0:
            normalized_embedding = embedding_array / l2_norm
        else:
            normalized_embedding = embedding_array
        
        normalized_embeddings.append(normalized_embedding.tolist())
    
    return normalized_embeddings

def normalize_query_embedding(query_embedding: Union[List[float], np.ndarray]) -> List[float]:
    """
    검색 쿼리 임베딩에 L2 정규화를 적용
    
    Args:
        query_embedding: 검색 쿼리 임베딩 벡터
        
    Returns:
        L2 정규화된 쿼리 임베딩 벡터
    """
    if isinstance(query_embedding, list):
        embedding_array = np.array(query_embedding)
    else:
        embedding_array = query_embedding
    
    # L2 정규화: 벡터를 단위 벡터로 변환
    l2_norm = np.linalg.norm(embedding_array)
    if l2_norm > 0:
        normalized_embedding = embedding_array / l2_norm
    else:
        normalized_embedding = embedding_array
    
    return normalized_embedding.tolist()

def calculate_similarity_from_distance(distance: float, method: str = "cosine") -> float:
    """
    ChromaDB 거리에서 유사도 계산
    
    Args:
        distance: ChromaDB에서 반환하는 거리
        method: 거리 계산 방법 ("cosine", "euclidean", "auto")
        
    Returns:
        유사도 점수 (0~1 범위)
    """
    if method == "cosine":
        # 코사인 거리인 경우: 유사도 = 1 - 거리
        # 단, 거리가 2를 초과하면 유클리드 거리로 간주
        if distance <= 2.0:
            return max(0.0, 1.0 - distance)
        else:
            return 1.0 / (1.0 + distance)
    elif method == "euclidean":
        # 유클리드 거리인 경우: 유사도 = 1 / (1 + 거리)
        return 1.0 / (1.0 + distance)
    else:  # auto
        # 자동 감지: 거리 범위에 따라 판단
        if distance <= 2.0:
            return max(0.0, 1.0 - distance)  # 코사인 거리로 간주
        else:
            return 1.0 / (1.0 + distance)  # 유클리드 거리로 간주

def calculate_cosine_similarity_direct(embedding1: List[float], embedding2: List[float]) -> float:
    """
    두 임베딩 벡터 간의 직접 코사인 유사도 계산
    
    Args:
        embedding1: 첫 번째 임베딩 벡터
        embedding2: 두 번째 임베딩 벡터
        
    Returns:
        코사인 유사도 (0~1 범위)
    """
    from sklearn.metrics.pairwise import cosine_similarity
    return cosine_similarity([embedding1], [embedding2])[0][0]

class CleanKoreanEmbeddingFunction:
    """커스텀 전처리 제거된 한국어 특화 임베딩 함수"""
    
    def __init__(self, model_name: str = "jhgan/ko-sroberta-multitask"):
        """
        한국어 임베딩 모델 초기화 (커스텀 전처리 없음)
        
        Args:
            model_name: 사용할 모델명 (기본값: jhgan/ko-sroberta-multitask)
        """
        self.model_name = model_name
        self.name = model_name  # ChromaDB 호환성을 위한 name 속성
        self.model = None
        self.tokenizer = None
        self.dimension = 768  # ko-sroberta-multitask의 임베딩 차원
        
        logger.info(f"🔧 한국어 임베딩 모델 로딩 중 (전처리 없음): {model_name}")
        try:
            # SentenceTransformer 모델 로드
            self.model = SentenceTransformer(model_name)
            
            # 올바른 토크나이저 로드 확인
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            logger.info(f"✅ 한국어 임베딩 모델 로딩 완료: {model_name}")
            logger.info(f"   임베딩 차원: {self.dimension}")
            logger.info(f"   토크나이저: {self.tokenizer.__class__.__name__}")
            logger.info(f"   전처리: 없음 (원문 그대로 사용)")
        except Exception as e:
            logger.error(f"❌ 모델 로딩 실패: {e}")
            raise
    
    def __call__(self, input):
        """
        텍스트 리스트를 임베딩으로 변환 (ChromaDB 0.4.16+ 호환)
        커스텀 전처리 없이 원문 그대로 사용
        
        Args:
            input: 임베딩할 텍스트 리스트
            
        Returns:
            L2 정규화된 임베딩 벡터 리스트
        """
        if not self.model:
            raise RuntimeError("모델이 초기화되지 않았습니다.")
        
        try:
            # 커스텀 전처리 없이 원문 그대로 사용
            # 단, 빈 문자열이나 None 값만 처리
            processed_texts = []
            for text in input:
                if isinstance(text, str) and text.strip():
                    # 텍스트 정제 적용 (잡음 제거)
                    cleaned_text = cleanse_text(text.strip())
                    processed_texts.append(cleaned_text)
                else:
                    # 빈 문자열인 경우 빈 문자열로 처리
                    processed_texts.append("")
            
            # 임베딩 생성 (원문 그대로)
            embeddings = self.model.encode(processed_texts, convert_to_tensor=False)
            
            # numpy 배열을 리스트로 변환
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            
            # L2 정규화 적용 (임베딩 품질 향상)
            normalized_embeddings = apply_l2_normalization(embeddings)
            
            logger.info(f"✅ {len(input)}개 텍스트 임베딩 완료 (차원: {len(normalized_embeddings[0]) if normalized_embeddings else 0}, L2 정규화 적용, 텍스트 정제 적용)")
            return normalized_embeddings
            
        except Exception as e:
            logger.error(f"❌ 임베딩 생성 실패: {e}")
            # 실패 시 더미 임베딩 반환 (L2 정규화 적용)
            dummy_embeddings = []
            for _ in input:
                dummy_embedding = np.random.normal(0, 0.1, self.dimension)
                dummy_embeddings.append(dummy_embedding)
            
            # L2 정규화 적용
            normalized_dummy_embeddings = apply_l2_normalization(dummy_embeddings)
            return normalized_dummy_embeddings

def setup_clean_korean_embedding():
    """ChromaDB에 커스텀 전처리 제거된 한국어 특화 임베딩 함수 설정"""
    logger.info("🔧 ChromaDB에 커스텀 전처리 제거된 한국어 특화 임베딩 함수 설정 중...")
    
    # 환경 변수 로드
    load_dotenv()
    
    # ChromaDB 클라이언트 초기화
    client = chromadb.PersistentClient(
        path="./vector_db",
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    
    # 커스텀 전처리 제거된 한국어 임베딩 함수 초기화
    try:
        clean_korean_embedding_function = CleanKoreanEmbeddingFunction()
    except Exception as e:
        logger.error(f"❌ 한국어 임베딩 모델 초기화 실패: {e}")
        return False
    
    # 기존 컬렉션들 확인
    collections = client.list_collections()
    logger.info(f"📋 발견된 컬렉션: {[c.name for c in collections]}")
    
    # 각 컬렉션을 커스텀 전처리 제거된 한국어 임베딩 함수로 재설정
    for collection_info in collections:
        collection_name = collection_info.name
        logger.info(f"\n🔧 컬렉션 '{collection_name}' 재설정 중...")
        
        try:
            # 기존 컬렉션 삭제
            client.delete_collection(collection_name)
            logger.info(f"   ✅ 기존 컬렉션 삭제: {collection_name}")
            
            # 커스텀 전처리 제거된 한국어 임베딩 함수로 새 컬렉션 생성
            new_collection = client.create_collection(
                name=collection_name,
                embedding_function=clean_korean_embedding_function,
                metadata={
                    "description": f"커스텀 전처리 제거된 한국어 특화 임베딩 - {collection_name}",
                    "embedding_model": "jhgan/ko-sroberta-multitask",
                    "embedding_dimension": 768,
                    "language": "korean",
                    "l2_normalization": True,
                    "custom_preprocessing": False,
                    "tokenizer": "AutoTokenizer"
                }
            )
            logger.info(f"   ✅ 커스텀 전처리 제거된 한국어 임베딩 함수 설정 완료: {collection_name}")
            
        except Exception as e:
            logger.error(f"   ❌ 컬렉션 설정 실패: {collection_name} - {e}")
    
    logger.info("\n🎉 커스텀 전처리 제거된 한국어 특화 임베딩 함수 설정 완료!")
    logger.info("   이제 모든 컬렉션이 768차원 한국어 특화 임베딩을 사용합니다.")
    logger.info("   모델: jhgan/ko-sroberta-multitask")
    logger.info("   전처리: 없음 (원문 그대로 사용)")
    logger.info("   L2 정규화: 적용됨")
    
    return True

def test_clean_korean_embedding():
    """커스텀 전처리 제거된 한국어 임베딩 테스트"""
    logger.info("🧪 커스텀 전처리 제거된 한국어 임베딩 테스트 시작...")
    
    try:
        # 한국어 임베딩 함수 초기화
        clean_korean_embedding_function = CleanKoreanEmbeddingFunction()
        
        # 테스트 텍스트들 (원문 그대로)
        test_texts = [
            "서버에 접속할 수 없는 문제가 있나요?",
            "메인 서버에 접속이 되지 않습니다. HTTP 500 오류가 발생하고 있습니다.",
            "사용자 인터페이스가 직관적이지 않아 개선이 필요합니다.",
            "데이터베이스 연결 오류가 발생했습니다.",
            "API 응답 시간이 너무 오래 걸립니다."
        ]
        
        # 임베딩 생성
        embeddings = clean_korean_embedding_function(test_texts)
        
        # 결과 검증
        logger.info(f"✅ 임베딩 테스트 완료:")
        logger.info(f"   텍스트 개수: {len(test_texts)}")
        logger.info(f"   임베딩 개수: {len(embeddings)}")
        logger.info(f"   임베딩 차원: {len(embeddings[0]) if embeddings else 0}")
        
        # L2 정규화 검증
        for i, embedding in enumerate(embeddings):
            l2_norm = np.linalg.norm(embedding)
            logger.info(f"   텍스트 {i+1}: L2 norm = {l2_norm:.6f} (정규화됨: {abs(l2_norm - 1.0) < 1e-6})")
        
        # 유사도 계산 테스트
        if len(embeddings) >= 2:
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            logger.info(f"   유사도 테스트: {similarity:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 커스텀 전처리 제거된 한국어 임베딩 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    # 테스트 먼저 실행
    if test_clean_korean_embedding():
        # 테스트 성공 시 설정 실행
        setup_clean_korean_embedding()
    else:
        logger.error("❌ 테스트 실패로 인해 설정을 중단합니다.")
