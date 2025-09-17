#!/usr/bin/env python3
"""
지능형 청크 가중치 부여 시스템 (Intelligent Chunk Weighting)
chunk_type별로 다른 가중치를 적용하여 검색 품질을 향상시킵니다.
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from sklearn.metrics.pairwise import cosine_similarity

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ChunkData:
    """청크 데이터 구조"""
    id: str
    content: str
    chunk_type: str
    embedding: List[float]
    metadata: Dict[str, Any] = None

@dataclass
class SearchResult:
    """검색 결과 구조"""
    id: str
    content: str
    chunk_type: str
    cosine_score: float
    weight: float
    weighted_score: float
    metadata: Dict[str, Any] = None

class ChunkWeightingConfig:
    """청크 타입별 가중치 설정"""

    # 기본 가중치 설정 (chunk_type -> weight)
    DEFAULT_WEIGHTS = {
        'title': 1.5,        # 제목: 가장 높은 가중치
        'summary': 1.3,      # 요약: 높은 가중치
        'description': 1.2,  # 설명: 중간-높은 가중치
        'header': 1.1,       # 헤더: 중간 가중치
        'body': 1.0,         # 본문: 기본 가중치
        'comment': 0.8,      # 댓글: 낮은 가중치
        'attachment': 0.6,   # 첨부파일: 가장 낮은 가중치
        'metadata': 0.7      # 메타데이터: 낮은 가중치
    }

    @classmethod
    def get_weight(cls, chunk_type: str) -> float:
        """chunk_type에 따른 가중치 반환"""
        return cls.DEFAULT_WEIGHTS.get(chunk_type.lower(), 1.0)

    @classmethod
    def update_weights(cls, custom_weights: Dict[str, float]):
        """가중치 업데이트"""
        cls.DEFAULT_WEIGHTS.update(custom_weights)
        logger.info(f"가중치 업데이트됨: {custom_weights}")

class IntelligentChunkWeighting:
    """지능형 청크 가중치 부여 시스템"""

    def __init__(self, config: ChunkWeightingConfig = None):
        """
        초기화

        Args:
            config: 가중치 설정 (기본값: ChunkWeightingConfig)
        """
        self.config = config or ChunkWeightingConfig()
        logger.info("🔧 지능형 청크 가중치 시스템 초기화 완료")

    def add_chunks_with_weights(self, chunks: List[ChunkData]) -> List[ChunkData]:
        """
        1. 메타데이터 확장: chunk_type에 따른 weight 필드 추가

        Args:
            chunks: 원본 청크 데이터 리스트

        Returns:
            가중치가 추가된 청크 데이터 리스트
        """
        weighted_chunks = []

        for chunk in chunks:
            # 가중치 계산
            weight = self.config.get_weight(chunk.chunk_type)

            # 메타데이터에 weight 추가
            if chunk.metadata is None:
                chunk.metadata = {}
            chunk.metadata['weight'] = weight
            chunk.metadata['original_chunk_type'] = chunk.chunk_type

            weighted_chunks.append(chunk)

        logger.info(f"✅ {len(chunks)}개 청크에 가중치 메타데이터 추가 완료")
        return weighted_chunks

    def apply_weighted_scoring(self, search_results: List[Dict[str, Any]],
                             query_embedding: List[float]) -> List[SearchResult]:
        """
        2. 1단계 검색 결과 보정: cosine_score에 weight를 적용하여 재점수화

        Args:
            search_results: 기본 검색 결과 (id, content, chunk_type, embedding 포함)
            query_embedding: 쿼리 임베딩

        Returns:
            가중치가 적용된 검색 결과 리스트 (점수 순으로 정렬됨)
        """
        weighted_results = []

        for result in search_results:
            # 기본 정보 추출
            chunk_id = result.get('id', '')
            content = result.get('content', '')
            chunk_type = result.get('chunk_type', 'body')
            embedding = result.get('embedding', [])
            metadata = result.get('metadata', {})

            # 코사인 유사도 계산
            if embedding and query_embedding:
                cosine_score = cosine_similarity([query_embedding], [embedding])[0][0]
            else:
                cosine_score = result.get('cosine_score', 0.0)

            # 가중치 계산
            weight = metadata.get('weight') or self.config.get_weight(chunk_type)

            # 가중치 적용된 최종 점수 계산
            weighted_score = cosine_score * weight

            # 결과 객체 생성
            weighted_result = SearchResult(
                id=chunk_id,
                content=content,
                chunk_type=chunk_type,
                cosine_score=cosine_score,
                weight=weight,
                weighted_score=weighted_score,
                metadata=metadata
            )

            weighted_results.append(weighted_result)

        # 가중치 적용된 점수로 정렬 (내림차순)
        weighted_results.sort(key=lambda x: x.weighted_score, reverse=True)

        logger.info(f"✅ {len(search_results)}개 검색 결과에 가중치 적용 및 재정렬 완료")
        return weighted_results

    def prepare_reranker_input(self, weighted_results: List[SearchResult],
                              query: str) -> List[Dict[str, Any]]:
        """
        3. 2단계 Re-ranking 개선: Cross-Encoder 입력에 weight feature 추가

        Args:
            weighted_results: 가중치 적용된 검색 결과
            query: 원본 쿼리

        Returns:
            Re-ranker 입력용 데이터 (weight를 feature로 포함)
        """
        reranker_inputs = []

        for result in weighted_results:
            reranker_input = {
                'query': query,
                'passage': result.content,
                'chunk_type': result.chunk_type,
                'weight': result.weight,
                'cosine_score': result.cosine_score,
                'weighted_score': result.weighted_score,
                'id': result.id,
                'metadata': result.metadata,
                # Cross-Encoder가 활용할 수 있는 추가 features
                'features': {
                    'chunk_weight': result.weight,
                    'base_similarity': result.cosine_score,
                    'chunk_priority': self._get_chunk_priority(result.chunk_type)
                }
            }
            reranker_inputs.append(reranker_input)

        logger.info(f"✅ Re-ranker 입력 데이터 {len(reranker_inputs)}개 준비 완료")
        return reranker_inputs

    def _get_chunk_priority(self, chunk_type: str) -> int:
        """chunk_type의 우선순위 반환 (1=최고, 숫자가 클수록 낮음)"""
        priority_map = {
            'title': 1,
            'summary': 2,
            'description': 3,
            'header': 4,
            'body': 5,
            'comment': 6,
            'metadata': 7,
            'attachment': 8
        }
        return priority_map.get(chunk_type.lower(), 5)

def create_mock_data() -> Tuple[List[ChunkData], List[float]]:
    """테스트용 Mock 데이터 생성"""

    # 가상의 임베딩 벡터 생성 (768차원)
    np.random.seed(42)

    chunks = [
        ChunkData(
            id="doc1_title",
            content="서버 접속 오류 해결 방법",
            chunk_type="title",
            embedding=np.random.normal(0.8, 0.1, 768).tolist()  # title과 유사도 높게
        ),
        ChunkData(
            id="doc1_desc",
            content="메인 서버에 접속할 수 없을 때 확인해야 할 사항들을 설명합니다.",
            chunk_type="description",
            embedding=np.random.normal(0.6, 0.1, 768).tolist()  # 중간 유사도
        ),
        ChunkData(
            id="doc1_comment",
            content="저도 같은 문제가 있었는데 네트워크 설정을 바꾸니까 해결됐어요",
            chunk_type="comment",
            embedding=np.random.normal(0.4, 0.1, 768).tolist()  # 낮은 유사도
        ),
        ChunkData(
            id="doc2_summary",
            content="서버 연결 문제 해결 가이드 요약",
            chunk_type="summary",
            embedding=np.random.normal(0.7, 0.1, 768).tolist()  # 높은 유사도
        ),
        ChunkData(
            id="doc2_body",
            content="서버에 접속하는 방법과 일반적인 문제 해결 절차에 대해 자세히 설명합니다.",
            chunk_type="body",
            embedding=np.random.normal(0.5, 0.1, 768).tolist()  # 중간 유사도
        )
    ]

    # 쿼리 임베딩 (서버 접속 문제와 관련)
    query_embedding = np.random.normal(0.7, 0.1, 768).tolist()

    return chunks, query_embedding

def demonstrate_intelligent_weighting():
    """지능형 청크 가중치 시스템 데모"""
    print("="*80)
    print("🚀 지능형 청크 가중치 부여 시스템 데모")
    print("="*80)

    # 1. Mock 데이터 생성
    chunks, query_embedding = create_mock_data()
    print(f"\n📊 테스트 데이터: {len(chunks)}개 청크")

    # 2. 가중치 시스템 초기화
    weighting_system = IntelligentChunkWeighting()

    # 3. 청크에 가중치 메타데이터 추가
    weighted_chunks = weighting_system.add_chunks_with_weights(chunks)

    # 4. 기본 검색 결과 생성 (가중치 적용 전)
    basic_results = []
    for chunk in weighted_chunks:
        cosine_score = cosine_similarity([query_embedding], [chunk.embedding])[0][0]
        basic_results.append({
            'id': chunk.id,
            'content': chunk.content,
            'chunk_type': chunk.chunk_type,
            'embedding': chunk.embedding,
            'cosine_score': cosine_score,
            'metadata': chunk.metadata
        })

    # 기본 점수로 정렬
    basic_results.sort(key=lambda x: x['cosine_score'], reverse=True)

    print("\n📋 Before weighting (기본 코사인 유사도 순):")
    print("-" * 60)
    for i, result in enumerate(basic_results, 1):
        weight = result['metadata'].get('weight', 1.0)
        print(f"{i}. {result['id']} ({result['chunk_type']})")
        print(f"   Content: {result['content'][:50]}...")
        print(f"   Cosine Score: {result['cosine_score']:.4f}")
        print(f"   Weight: {weight:.1f}")
        print()

    # 5. 가중치 적용된 검색 결과
    weighted_results = weighting_system.apply_weighted_scoring(basic_results, query_embedding)

    print("📋 After weighting (가중치 적용된 점수 순):")
    print("-" * 60)
    for i, result in enumerate(weighted_results, 1):
        print(f"{i}. {result.id} ({result.chunk_type})")
        print(f"   Content: {result.content[:50]}...")
        print(f"   Cosine Score: {result.cosine_score:.4f}")
        print(f"   Weight: {result.weight:.1f}")
        print(f"   Weighted Score: {result.weighted_score:.4f} ⭐")
        print()

    # 6. 순위 변화 분석
    print("📈 순위 변화 분석:")
    print("-" * 60)

    basic_ranking = {result['id']: i+1 for i, result in enumerate(basic_results)}
    weighted_ranking = {result.id: i+1 for i, result in enumerate(weighted_results)}

    for chunk_id in basic_ranking:
        basic_rank = basic_ranking[chunk_id]
        weighted_rank = weighted_ranking[chunk_id]
        rank_change = basic_rank - weighted_rank

        change_symbol = "📈" if rank_change > 0 else "📉" if rank_change < 0 else "➡️"
        print(f"{chunk_id}: {basic_rank} → {weighted_rank} {change_symbol}")

    # 7. Re-ranker 입력 데이터 준비
    query = "서버에 접속할 수 없는 문제를 해결하는 방법"
    reranker_inputs = weighting_system.prepare_reranker_input(weighted_results, query)

    print(f"\n🔧 Re-ranker 입력 데이터 준비 완료:")
    print("-" * 60)
    print(f"입력 개수: {len(reranker_inputs)}")
    print(f"각 입력에 포함된 features:")
    if reranker_inputs:
        features = reranker_inputs[0]['features']
        for key, value in features.items():
            print(f"  - {key}: {value}")

    # 8. 가중치 효과 요약
    print(f"\n📊 가중치 효과 요약:")
    print("-" * 60)

    # 가중치별 평균 점수 향상 계산
    weight_effects = {}
    for result in weighted_results:
        chunk_type = result.chunk_type
        improvement = result.weighted_score - result.cosine_score
        if chunk_type not in weight_effects:
            weight_effects[chunk_type] = []
        weight_effects[chunk_type].append(improvement)

    for chunk_type, improvements in weight_effects.items():
        avg_improvement = np.mean(improvements)
        weight = weighting_system.config.get_weight(chunk_type)
        print(f"{chunk_type}: 가중치 {weight:.1f} → 평균 점수 변화 {avg_improvement:+.4f}")

    print("\n🎉 지능형 청크 가중치 시스템 데모 완료!")
    return weighted_results, reranker_inputs

class EnhancedCrossEncoderReranker:
    """가중치를 활용하는 향상된 Cross-Encoder Re-ranker"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Re-ranker 초기화

        Args:
            model_name: Cross-Encoder 모델명
        """
        self.model_name = model_name
        # 실제 환경에서는 sentence_transformers.CrossEncoder 사용
        # self.model = CrossEncoder(model_name)
        logger.info(f"🔧 Enhanced Cross-Encoder Re-ranker 초기화: {model_name}")

    def rerank_with_weights(self, reranker_inputs: List[Dict[str, Any]],
                          weight_boost: float = 0.1) -> List[Dict[str, Any]]:
        """
        가중치를 고려한 Re-ranking

        Args:
            reranker_inputs: Re-ranker 입력 데이터
            weight_boost: 가중치 부스트 계수

        Returns:
            Re-ranking된 결과
        """
        enhanced_results = []

        for item in reranker_inputs:
            # Mock Cross-Encoder 점수 (실제로는 모델 예측 사용)
            # cross_encoder_score = self.model.predict([(item['query'], item['passage'])])[0]

            # Mock 점수 생성 (기존 weighted_score 기반)
            base_score = item.get('weighted_score', 0.5)
            mock_cross_encoder_score = base_score + np.random.normal(0, 0.1)
            mock_cross_encoder_score = max(0, min(1, mock_cross_encoder_score))

            # 가중치를 활용한 최종 점수 계산
            weight_factor = item['features']['chunk_weight']
            final_score = mock_cross_encoder_score + (weight_factor - 1.0) * weight_boost

            enhanced_result = {
                **item,
                'cross_encoder_score': mock_cross_encoder_score,
                'final_score': final_score,
                'weight_boost_applied': (weight_factor - 1.0) * weight_boost
            }

            enhanced_results.append(enhanced_result)

        # 최종 점수로 정렬
        enhanced_results.sort(key=lambda x: x['final_score'], reverse=True)

        logger.info(f"✅ 가중치 기반 Re-ranking 완료: {len(enhanced_results)}개 결과")
        return enhanced_results

def demonstrate_enhanced_reranking():
    """향상된 Re-ranking 시스템 데모"""
    print("\n" + "="*80)
    print("🔧 향상된 Cross-Encoder Re-ranking 데모")
    print("="*80)

    # 기본 가중치 결과 가져오기
    weighted_results, reranker_inputs = demonstrate_intelligent_weighting()

    # Enhanced Re-ranker 초기화
    enhanced_reranker = EnhancedCrossEncoderReranker()

    # 가중치를 고려한 Re-ranking 수행
    final_results = enhanced_reranker.rerank_with_weights(reranker_inputs)

    print("\n📋 Final Results (Enhanced Re-ranking 후):")
    print("-" * 60)
    for i, result in enumerate(final_results, 1):
        print(f"{i}. {result['id']} ({result['chunk_type']})")
        print(f"   Cross-Encoder Score: {result['cross_encoder_score']:.4f}")
        print(f"   Weight Boost: {result['weight_boost_applied']:+.4f}")
        print(f"   Final Score: {result['final_score']:.4f} ⭐")
        print()

    return final_results

if __name__ == "__main__":
    # 기본 가중치 시스템 데모
    demonstrate_intelligent_weighting()

    # 향상된 Re-ranking 데모
    demonstrate_enhanced_reranking()