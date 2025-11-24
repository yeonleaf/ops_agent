#!/usr/bin/env python3
"""
RRF (Reciprocal Rank Fusion) 기반 RAG 시스템
Multi-Query, HyDE, BM25 검색 결과를 순위 기반으로 지능적 융합 (Hybrid Search)
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
import numpy as np
from collections import defaultdict

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 모듈들 import
from intelligent_chunk_weighting import IntelligentChunkWeighting
from hyde_rag_system_mock import MockHyDEGenerator, HyDEConfig

# BM25 관련 import
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ rank_bm25 미설치. BM25 검색 비활성화. 설치: pip install rank-bm25")

# 한국어 형태소 분석기 import
try:
    from kiwipiepy import Kiwi
    KIWI_AVAILABLE = True
except ImportError:
    KIWI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ kiwipiepy 미설치. 기본 토크나이저 사용. 설치: pip install kiwipiepy")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KoreanTokenizer:
    """한국어 형태소 분석 토크나이저 (Kiwipiepy 기반)"""

    def __init__(self, use_kiwi: bool = True):
        """
        토크나이저 초기화

        Args:
            use_kiwi: Kiwipiepy 사용 여부
        """
        self.use_kiwi = use_kiwi and KIWI_AVAILABLE
        self.kiwi = None

        if self.use_kiwi:
            try:
                self.kiwi = Kiwi()
                logger.info("✅ Kiwipiepy 한국어 형태소 분석기 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️ Kiwipiepy 초기화 실패, 기본 토크나이저 사용: {e}")
                self.use_kiwi = False

    def tokenize(self, text: str) -> List[str]:
        """
        텍스트를 토큰으로 분리 (하이픈 복합어 보존)

        Args:
            text: 입력 텍스트

        Returns:
            토큰 리스트
        """
        if not text:
            return []

        if self.use_kiwi and self.kiwi:
            try:
                # Kiwipiepy 형태소 분석
                result = self.kiwi.tokenize(text)

                # 하이픈 복합어 재결합 (예: NCMS-EUXP)
                tokens = []
                i = 0
                while i < len(result):
                    token = result[i]

                    # 영어/숫자 + 하이픈 + 영어/숫자 패턴 감지
                    if (token.tag in ['SL', 'SN'] and
                        i + 2 < len(result) and
                        result[i + 1].form == '-' and
                        result[i + 2].tag in ['SL', 'SN']):
                        # 복합어로 결합: "NCMS" + "-" + "EUXP" → "ncms-euxp"
                        compound = token.form.lower() + '-' + result[i + 2].form.lower()
                        tokens.append(compound)
                        i += 3  # 3개 토큰 건너뛰기
                    elif token.tag in ['NNG', 'NNP', 'VV', 'VA', 'SL', 'SN', 'XR', 'SH']:
                        # 일반 토큰
                        form = token.form.lower() if token.tag in ['SL', 'SN'] else token.form
                        tokens.append(form)
                        i += 1
                    else:
                        i += 1

                return tokens

            except Exception as e:
                logger.warning(f"⚠️ Kiwipiepy 토크나이징 실패, 기본 방식 사용: {e}")

        # 기본 토크나이저 (공백 분리)
        return text.lower().split()


@dataclass
class RRFConfig:
    """RRF 시스템 설정 (Hybrid Search 지원)"""
    # RRF 설정
    rrf_k: int = 60  # RRF 상수 (일반적으로 60 사용)
    multi_query_results: int = 20  # 멀티쿼리 검색 결과 수
    hyde_results: int = 20  # HyDE 검색 결과 수
    bm25_results: int = 20  # BM25 검색 결과 수
    final_candidates: int = 30  # 최종 후보 수

    # 기존 HyDE 설정
    multi_query_count: int = 3
    top_k_per_query: int = 15

    # BM25 설정
    enable_bm25: bool = True  # BM25 검색 활성화 여부
    bm25_tokenizer: str = "korean"  # simple 또는 korean (기본: 한국어 형태소 분석)

    # 티켓 중복 제거 설정
    deduplicate_tickets: bool = True  # 티켓 중복 제거 활성화
    deduplication_strategy: str = "max_score"  # max_score, first, merge, all_scores

class RRFFusionEngine:
    """RRF (Reciprocal Rank Fusion) 융합 엔진"""

    def __init__(self, config: RRFConfig):
        """
        RRF 융합 엔진 초기화

        Args:
            config: RRF 설정
        """
        self.config = config
        logger.info(f"✅ RRF 융합 엔진 초기화 (k={config.rrf_k})")

    def calculate_rrf_scores(self, multi_query_results: List[Dict[str, Any]],
                           hyde_results: List[Dict[str, Any]],
                           bm25_results: Optional[List[Dict[str, Any]]] = None) -> Dict[str, float]:
        """
        RRF 점수 계산 (3-way: Multi-Query + HyDE + BM25)

        Args:
            multi_query_results: 멀티쿼리 검색 결과 (순위 순)
            hyde_results: HyDE 검색 결과 (순위 순)
            bm25_results: BM25 검색 결과 (순위 순, optional)

        Returns:
            문서 ID별 RRF 점수 딕셔너리
        """
        rrf_scores = defaultdict(float)

        # 1. Multi-Query 결과 처리
        logger.info(f"🔄 Multi-Query 결과 RRF 점수 계산: {len(multi_query_results)}개")
        for rank, doc in enumerate(multi_query_results, 1):
            doc_id = doc['id']
            rrf_score = 1.0 / (self.config.rrf_k + rank)
            rrf_scores[doc_id] += rrf_score

            logger.debug(f"  Multi-Query {rank}위: {doc_id} → +{rrf_score:.6f}")

        # 2. HyDE 결과 처리
        logger.info(f"🔄 HyDE 결과 RRF 점수 계산: {len(hyde_results)}개")
        for rank, doc in enumerate(hyde_results, 1):
            doc_id = doc['id']
            rrf_score = 1.0 / (self.config.rrf_k + rank)
            rrf_scores[doc_id] += rrf_score

            logger.debug(f"  HyDE {rank}위: {doc_id} → +{rrf_score:.6f}")

        # 3. BM25 결과 처리 (있는 경우) - 키워드 정확 매칭이므로 6배 가중치
        if bm25_results:
            logger.info(f"🔄 BM25 결과 RRF 점수 계산: {len(bm25_results)}개 (가중치 6.0x)")
            for rank, doc in enumerate(bm25_results, 1):
                doc_id = doc['id']
                rrf_score = 1.0 / (self.config.rrf_k + rank)
                # BM25는 키워드 정확 매칭이므로 6배 가중치 적용
                weighted_score = rrf_score * 6.0
                rrf_scores[doc_id] += weighted_score

                logger.debug(f"  BM25 {rank}위: {doc_id} → +{weighted_score:.6f} (기본:{rrf_score:.6f} x6)")

        logger.info(f"✅ RRF 점수 계산 완료: {len(rrf_scores)}개 고유 문서")
        return dict(rrf_scores)

    def fuse_results(self, multi_query_results: List[Dict[str, Any]],
                    hyde_results: List[Dict[str, Any]],
                    bm25_results: Optional[List[Dict[str, Any]]] = None) -> Tuple[List[str], Dict[str, float]]:
        """
        검색 결과들을 RRF로 융합하여 최종 후보군 생성 (Hybrid Search)

        Args:
            multi_query_results: 멀티쿼리 검색 결과
            hyde_results: HyDE 검색 결과
            bm25_results: BM25 검색 결과 (optional)

        Returns:
            (RRF 점수 순으로 정렬된 문서 ID 리스트, RRF 점수 딕셔너리)
        """
        try:
            # RRF 점수 계산
            rrf_scores = self.calculate_rrf_scores(multi_query_results, hyde_results, bm25_results)

            # RRF 점수 기준으로 정렬
            sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda doc_id: rrf_scores[doc_id], reverse=True)

            # 상위 N개 선택
            final_candidates = sorted_doc_ids[:self.config.final_candidates]

            search_methods = "Multi-Query + HyDE"
            if bm25_results:
                search_methods += " + BM25"
            logger.info(f"🎯 RRF 융합 완료 ({search_methods}): {len(final_candidates)}개 최종 후보")

            # 상위 5개 RRF 점수 출력
            logger.info("📊 상위 5개 RRF 점수:")
            for i, doc_id in enumerate(final_candidates[:5], 1):
                score = rrf_scores[doc_id]
                logger.info(f"  {i}. {doc_id[:12]}... → {score:.6f}")

            return final_candidates, rrf_scores

        except Exception as e:
            logger.error(f"❌ RRF 융합 실패: {e}")
            return [], {}

    def analyze_fusion_effect(self, multi_query_results: List[Dict[str, Any]],
                            hyde_results: List[Dict[str, Any]],
                            final_candidates: List[str]) -> Dict[str, Any]:
        """
        RRF 융합 효과 분석

        Args:
            multi_query_results: 멀티쿼리 검색 결과
            hyde_results: HyDE 검색 결과
            final_candidates: 최종 후보 문서 ID 리스트

        Returns:
            융합 효과 분석 결과
        """
        try:
            # 각 방법별 문서 ID 집합
            multi_ids = set(doc['id'] for doc in multi_query_results)
            hyde_ids = set(doc['id'] for doc in hyde_results)
            final_ids = set(final_candidates)

            # 교집합 및 고유 문서 분석
            both_methods = multi_ids & hyde_ids  # 두 방법 모두에서 발견
            multi_only = multi_ids - hyde_ids   # 멀티쿼리에만 있음
            hyde_only = hyde_ids - multi_ids    # HyDE에만 있음

            # 최종 후보에서의 구성 분석
            final_from_both = final_ids & both_methods
            final_from_multi_only = final_ids & multi_only
            final_from_hyde_only = final_ids & hyde_only

            analysis = {
                'original_stats': {
                    'multi_query_count': len(multi_ids),
                    'hyde_count': len(hyde_ids),
                    'both_methods': len(both_methods),
                    'multi_only': len(multi_only),
                    'hyde_only': len(hyde_only)
                },
                'final_composition': {
                    'total_candidates': len(final_candidates),
                    'from_both_methods': len(final_from_both),
                    'from_multi_only': len(final_from_multi_only),
                    'from_hyde_only': len(final_from_hyde_only)
                },
                'fusion_effectiveness': {
                    'coverage_improvement': len(final_ids) / max(len(multi_ids | hyde_ids), 1),
                    'balance_score': min(len(final_from_multi_only), len(final_from_hyde_only)) / max(len(final_candidates), 1)
                }
            }

            return analysis

        except Exception as e:
            logger.error(f"❌ 융합 효과 분석 실패: {e}")
            return {}

class RRFRAGSystem:
    """RRF 기반 RAG 시스템"""

    def __init__(self, collection_name: str = "file_chunks",
                 rrf_config: Optional[RRFConfig] = None):
        """
        RRF RAG 시스템 초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
            rrf_config: RRF 설정
        """
        self.collection_name = collection_name
        self.config = rrf_config or RRFConfig()

        # 컴포넌트 초기화
        self.client = None
        self.collection = None
        self.hyde_generator = None
        self.weighting_system = None
        self.rrf_engine = None

        # BM25 관련
        self.bm25_index = None
        self.bm25_documents = []  # (doc_id, content) 리스트
        self.bm25_corpus_tokenized = []  # 토크나이즈된 코퍼스
        self.tokenizer = None  # 한국어 토크나이저

        self._init_components()

    def _init_components(self):
        """시스템 컴포넌트 초기화 (Hybrid Search 지원)"""
        try:
            # ChromaDB 연결
            self.client = chromadb.PersistentClient(
                path='./vector_db',
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            self.collection = self.client.get_collection(self.collection_name)

            # Mock HyDE 생성기
            hyde_config = HyDEConfig()
            self.hyde_generator = MockHyDEGenerator(hyde_config)

            # 가중치 시스템
            self.weighting_system = IntelligentChunkWeighting()

            # RRF 융합 엔진
            self.rrf_engine = RRFFusionEngine(self.config)

            # 한국어 토크나이저 초기화
            use_korean_tokenizer = self.config.bm25_tokenizer == "korean"
            self.tokenizer = KoreanTokenizer(use_kiwi=use_korean_tokenizer)

            # BM25 인덱스 초기화
            if self.config.enable_bm25 and BM25_AVAILABLE:
                self._init_bm25_index()

            logger.info(f"✅ RRF RAG 시스템 초기화 완료: {self.collection.count()}개 문서")

        except Exception as e:
            logger.error(f"❌ RRF RAG 시스템 초기화 실패: {e}")
            raise e

    def _init_bm25_index(self):
        """BM25 인덱스 초기화"""
        try:
            logger.info("🔨 BM25 인덱스 구축 시작...")

            # 모든 문서 가져오기
            all_docs = self.collection.get(include=["documents", "metadatas"])

            if not all_docs['ids']:
                logger.warning("⚠️ BM25: 문서가 없어 인덱스 구축 불가")
                return

            # 문서 리스트 구축
            for i, doc_id in enumerate(all_docs['ids']):
                content = all_docs['documents'][i] if all_docs['documents'] else ""
                if content:
                    self.bm25_documents.append((doc_id, content))

            # 토크나이징 (한국어 형태소 분석 또는 공백 기반)
            for doc_id, content in self.bm25_documents:
                tokens = self.tokenizer.tokenize(content)
                self.bm25_corpus_tokenized.append(tokens)

            # BM25 인덱스 생성
            if self.bm25_corpus_tokenized:
                self.bm25_index = BM25Okapi(self.bm25_corpus_tokenized)
                logger.info(f"✅ BM25 인덱스 구축 완료: {len(self.bm25_documents)}개 문서")
            else:
                logger.warning("⚠️ BM25: 토크나이징된 문서가 없음")

        except Exception as e:
            logger.warning(f"⚠️ BM25 인덱스 구축 실패: {e}")
            self.bm25_index = None

    def multi_query_search(self, query: str) -> List[Dict[str, Any]]:
        """
        멀티쿼리 검색 (독립 실행)

        Args:
            query: 검색 쿼리

        Returns:
            멀티쿼리 검색 결과 (순위 순)
        """
        try:
            # 멀티 쿼리 생성
            multi_queries = self.hyde_generator.generate_multi_queries(query)
            all_texts = [query] + multi_queries

            # 각 쿼리로 검색 및 결과 수집
            all_results = []
            for i, text in enumerate(all_texts):
                results = self.collection.query(
                    query_texts=[text],
                    n_results=self.config.top_k_per_query
                )

                if results['ids'][0]:
                    for j in range(len(results['ids'][0])):
                        distance = results['distances'][0][j] if results['distances'][0] else 1.0
                        cosine_score = max(0.0, 1.0 - distance)

                        result = {
                            'id': results['ids'][0][j],
                            'content': results['documents'][0][j] if results['documents'][0] else "",
                            'distance': distance,
                            'cosine_score': cosine_score,
                            'query_index': i,
                            'source_text': text[:50] + "..." if len(text) > 50 else text
                        }
                        all_results.append(result)

            # 중복 제거 및 점수 통합 (최대값 사용)
            unique_results = self._deduplicate_and_score(all_results)

            # 점수 순으로 정렬하여 상위 N개 반환
            sorted_results = sorted(unique_results, key=lambda x: x['cosine_score'], reverse=True)
            final_results = sorted_results[:self.config.multi_query_results]

            logger.info(f"✅ 멀티쿼리 검색 완료: {len(final_results)}개 결과")
            return final_results

        except Exception as e:
            logger.error(f"❌ 멀티쿼리 검색 실패: {e}")
            return []

    def hyde_search(self, query: str) -> List[Dict[str, Any]]:
        """
        HyDE 검색 (독립 실행)

        Args:
            query: 검색 쿼리

        Returns:
            HyDE 검색 결과 (순위 순)
        """
        try:
            # HyDE 문서 생성
            hypothetical_doc = self.hyde_generator.generate_hypothetical_document(query)
            all_texts = [query, hypothetical_doc]

            # 각 텍스트로 검색 및 결과 수집
            all_results = []
            for i, text in enumerate(all_texts):
                results = self.collection.query(
                    query_texts=[text],
                    n_results=self.config.top_k_per_query
                )

                if results['ids'][0]:
                    for j in range(len(results['ids'][0])):
                        distance = results['distances'][0][j] if results['distances'][0] else 1.0
                        cosine_score = max(0.0, 1.0 - distance)

                        result = {
                            'id': results['ids'][0][j],
                            'content': results['documents'][0][j] if results['documents'][0] else "",
                            'distance': distance,
                            'cosine_score': cosine_score,
                            'query_index': i,
                            'source_text': text[:100] + "..." if len(text) > 100 else text
                        }
                        all_results.append(result)

            # 중복 제거 및 점수 통합
            unique_results = self._deduplicate_and_score(all_results)

            # 점수 순으로 정렬하여 상위 N개 반환
            sorted_results = sorted(unique_results, key=lambda x: x['cosine_score'], reverse=True)
            final_results = sorted_results[:self.config.hyde_results]

            logger.info(f"✅ HyDE 검색 완료: {len(final_results)}개 결과")
            return final_results

        except Exception as e:
            logger.error(f"❌ HyDE 검색 실패: {e}")
            return []

    def bm25_search(self, query: str) -> List[Dict[str, Any]]:
        """
        BM25 키워드 검색 (독립 실행)

        Args:
            query: 검색 쿼리

        Returns:
            BM25 검색 결과 (순위 순)
        """
        if not self.bm25_index:
            logger.warning("⚠️ BM25 인덱스가 초기화되지 않음")
            return []

        try:
            # 쿼리 토크나이징 (한국어 형태소 분석)
            query_tokens = self.tokenizer.tokenize(query)

            # BM25 점수 계산
            bm25_scores = self.bm25_index.get_scores(query_tokens)

            # 결과 구성
            results = []
            for idx, score in enumerate(bm25_scores):
                if score > 0:  # 점수가 0보다 큰 것만
                    doc_id, content = self.bm25_documents[idx]
                    results.append({
                        'id': doc_id,
                        'content': content,
                        'bm25_score': float(score),
                        'cosine_score': float(score),  # 호환성을 위해
                        'distance': 1.0 - min(float(score), 1.0)  # 호환성을 위해
                    })

            # BM25 점수 순으로 정렬
            sorted_results = sorted(results, key=lambda x: x['bm25_score'], reverse=True)
            final_results = sorted_results[:self.config.bm25_results]

            logger.info(f"✅ BM25 검색 완료: {len(final_results)}개 결과")
            return final_results

        except Exception as e:
            logger.error(f"❌ BM25 검색 실패: {e}")
            return []

    def _deduplicate_and_score(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """검색 결과 중복 제거 및 점수 통합"""
        unique_docs = {}

        for result in all_results:
            doc_id = result['id']
            cosine_score = result['cosine_score']

            if doc_id not in unique_docs:
                unique_docs[doc_id] = {
                    'id': doc_id,
                    'content': result['content'],
                    'distance': result['distance'],
                    'cosine_score': cosine_score,
                    'scores': [cosine_score],
                    'query_indices': [result['query_index']],
                    'source_texts': [result['source_text']]
                }
            else:
                # 최대 점수로 업데이트
                if cosine_score > unique_docs[doc_id]['cosine_score']:
                    unique_docs[doc_id]['cosine_score'] = cosine_score
                    unique_docs[doc_id]['distance'] = result['distance']

                unique_docs[doc_id]['scores'].append(cosine_score)
                unique_docs[doc_id]['query_indices'].append(result['query_index'])
                unique_docs[doc_id]['source_texts'].append(result['source_text'])

        return list(unique_docs.values())

    def load_documents_by_ids(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        문서 ID 리스트로 전체 문서 정보 로드

        Args:
            doc_ids: 문서 ID 리스트

        Returns:
            문서 정보 리스트 (ID 순서 유지)
        """
        try:
            if not doc_ids:
                return []

            # ChromaDB에서 문서 정보 가져오기
            results = self.collection.get(ids=doc_ids, include=['documents', 'metadatas'])

            # 결과를 ID 순서에 맞게 정렬
            id_to_data = {}
            for i, doc_id in enumerate(results['ids']):
                id_to_data[doc_id] = {
                    'id': doc_id,
                    'content': results['documents'][i] if results['documents'] else "",
                    'metadata': results['metadatas'][i] if results['metadatas'] else {}
                }

            # 원래 순서 유지
            ordered_documents = []
            for doc_id in doc_ids:
                if doc_id in id_to_data:
                    ordered_documents.append(id_to_data[doc_id])

            return ordered_documents

        except Exception as e:
            logger.error(f"❌ 문서 로드 실패: {e}")
            return []

    def rrf_search(self, query: str) -> List[Dict[str, Any]]:
        """
        RRF 기반 하이브리드 검색 (Multi-Query + HyDE + BM25)

        Args:
            query: 검색 쿼리

        Returns:
            RRF 융합된 최종 검색 결과
        """
        try:
            search_methods = []
            logger.info(f"🚀 RRF 기반 하이브리드 검색 시작: '{query}'")

            # 1. 멀티쿼리, HyDE, BM25 검색을 독립적으로 실행
            logger.info("📊 1단계: 독립 검색 실행")
            multi_query_results = self.multi_query_search(query)
            if multi_query_results:
                search_methods.append("Multi-Query")

            hyde_results = self.hyde_search(query)
            if hyde_results:
                search_methods.append("HyDE")

            # BM25 검색 (활성화된 경우)
            bm25_results = []
            if self.config.enable_bm25 and self.bm25_index:
                bm25_results = self.bm25_search(query)
                if bm25_results:
                    search_methods.append("BM25")

            if not multi_query_results and not hyde_results and not bm25_results:
                logger.warning("⚠️ 모든 검색 결과가 비어있음")
                return []

            logger.info(f"🔍 사용된 검색 방식: {' + '.join(search_methods)}")

            # 2. RRF로 결과 융합
            logger.info("🔄 2단계: RRF 융합")
            final_candidate_ids, rrf_scores = self.rrf_engine.fuse_results(
                multi_query_results,
                hyde_results,
                bm25_results if bm25_results else None
            )

            if not final_candidate_ids:
                logger.warning("⚠️ RRF 융합 결과가 비어있음")
                return []

            # 3. 최종 후보 문서 정보 로드
            logger.info("📄 3단계: 후보 문서 로드")
            final_documents = self.load_documents_by_ids(final_candidate_ids)

            # 4. 가중치 적용
            logger.info("⚖️ 4단계: RRF 점수 적용")
            weighted_results = self._apply_weighting_to_documents(final_documents, query, rrf_scores)

            # 5. 융합 효과 분석
            fusion_analysis = self.rrf_engine.analyze_fusion_effect(
                multi_query_results, hyde_results, final_candidate_ids
            )

            logger.info("📈 RRF 융합 효과 분석:")
            if fusion_analysis:
                orig_stats = fusion_analysis['original_stats']
                final_comp = fusion_analysis['final_composition']
                logger.info(f"  원본: Multi({orig_stats['multi_query_count']}) + HyDE({orig_stats['hyde_count']}) → 고유({orig_stats['both_methods'] + orig_stats['multi_only'] + orig_stats['hyde_only']})")
                logger.info(f"  최종: {final_comp['total_candidates']}개 (양쪽:{final_comp['from_both_methods']}, Multi만:{final_comp['from_multi_only']}, HyDE만:{final_comp['from_hyde_only']})")

            # 6. 티켓 중복 제거 (옵션)
            final_results = weighted_results
            if self.config.deduplicate_tickets:
                logger.info("🎯 5단계: 티켓 중복 제거")
                final_results = self.deduplicate_by_ticket(
                    weighted_results,
                    strategy=self.config.deduplication_strategy
                )

            logger.info(f"✅ RRF 기반 검색 완료: {len(final_results)}개 결과")
            return final_results

        except Exception as e:
            logger.error(f"❌ RRF 기반 검색 실패: {e}")
            return []

    def _apply_weighting_to_documents(self, documents: List[Dict[str, Any]], query: str,
                                     rrf_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """문서에 RRF 점수 적용 (청크 타입 가중치는 사용하지 않음)"""
        try:
            if not documents:
                return []

            # RRF 점수를 직접 사용 (청크 타입 가중치 무시)
            final_results = []
            for i, doc in enumerate(documents):
                doc_id = doc['id']
                rrf_score = rrf_scores.get(doc_id, 0.0)
                chunk_type = self._estimate_chunk_type(doc['content'])

                result = {
                    'id': doc_id,
                    'content': doc['content'],
                    'score': rrf_score,  # RRF 점수 직접 사용
                    'chunk_type': chunk_type,
                    'rrf_rank': i + 1,  # RRF 순위 추가
                    'method': 'rrf_fusion',
                    'source': 'rrf_rag_system',
                    'metadata': {
                        **doc.get('metadata', {}),
                        'rrf_enhanced': True,
                        'rrf_score': rrf_score
                    }
                }
                final_results.append(result)

            return final_results

        except Exception as e:
            logger.error(f"❌ 가중치 적용 실패: {e}")
            return []

    def deduplicate_by_ticket(self, results: List[Dict[str, Any]],
                             strategy: str = 'max_score') -> List[Dict[str, Any]]:
        """
        티켓 단위로 중복 제거

        Args:
            results: 검색 결과 리스트
            strategy: 중복 제거 전략
                - 'max_score': 최고 점수 청크만 선택 (기본)
                - 'first': 첫 번째 청크만 선택
                - 'merge': 모든 청크를 하나로 병합
                - 'all_scores': 모든 청크 점수 합산

        Returns:
            티켓 단위로 중복 제거된 결과
        """
        from collections import defaultdict

        # 티켓 ID별로 그룹화
        ticket_groups = defaultdict(list)

        for result in results:
            metadata = result.get('metadata', {})
            # ticket_id 추출
            ticket_id = None
            for key in ['ticket_id', 'ticket_key', 'jira_key', 'issue_key', 'key']:
                if key in metadata:
                    ticket_id = metadata[key]
                    break

            if ticket_id:
                ticket_groups[ticket_id].append(result)
            else:
                # ticket_id가 없는 경우 chunk_id를 그대로 사용
                ticket_groups[result['id']].append(result)

        # 전략에 따라 대표 청크 선택
        deduplicated_results = []

        for ticket_id, chunks in ticket_groups.items():
            if strategy == 'max_score':
                # 최고 점수 청크 선택
                best_chunk = max(chunks, key=lambda x: x.get('score', 0.0))
                deduplicated_results.append(best_chunk)

            elif strategy == 'first':
                # 첫 번째 청크 선택
                deduplicated_results.append(chunks[0])

            elif strategy == 'all_scores':
                # 점수 합산
                best_chunk = max(chunks, key=lambda x: x.get('score', 0.0))
                total_score = sum(c.get('score', 0.0) for c in chunks)
                best_chunk['score'] = total_score
                best_chunk['metadata']['aggregated_chunks'] = len(chunks)
                best_chunk['metadata']['original_score'] = best_chunk.get('score', 0.0)
                deduplicated_results.append(best_chunk)

            elif strategy == 'merge':
                # 모든 청크 내용 병합
                best_chunk = chunks[0].copy()
                merged_content = '\n\n'.join([c['content'] for c in chunks])
                best_chunk['content'] = merged_content
                best_chunk['score'] = max(c.get('score', 0.0) for c in chunks)
                best_chunk['metadata']['merged_chunks'] = len(chunks)
                deduplicated_results.append(best_chunk)

        # 점수 순으로 재정렬
        deduplicated_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        logger.info(f"🔄 티켓 중복 제거: {len(results)}개 청크 → {len(deduplicated_results)}개 티켓 (전략: {strategy})")

        return deduplicated_results

    def _estimate_chunk_type(self, content: str) -> str:
        """chunk_type 추정"""
        content_lower = content.lower()

        if any(pattern in content_lower for pattern in ['제목:', 'title:', '이슈 키:']):
            return 'title'
        elif any(pattern in content_lower for pattern in ['요약:', 'summary:']):
            return 'summary'
        elif any(pattern in content_lower for pattern in ['설명:', 'description:']):
            return 'description'
        elif any(pattern in content_lower for pattern in ['댓글:', 'comment:']):
            return 'comment'
        elif len(content.strip()) < 30:
            return 'title'
        elif len(content.strip()) < 100:
            return 'summary'
        elif len(content.strip()) > 1000:
            return 'body'
        else:
            return 'description'

def compare_rrf_vs_hybrid():
    """RRF vs 기존 하이브리드 방식 비교"""
    print("🔬 RRF vs 하이브리드 검색 방식 비교")
    print("="*80)

    try:
        # RRF 시스템 초기화
        rrf_system = RRFRAGSystem()

        # 기존 하이브리드 시스템 (비교용)
        from comprehensive_hyde_golden_set_test import ComprehensiveHyDETestSystem
        hybrid_system = ComprehensiveHyDETestSystem()

        test_questions = [
            "사용자 인터페이스가 복잡해서 개선이 필요합니다",
            "서버에 접속할 수 없는 문제를 해결하고 싶어요",
            "데이터베이스 연결이 자주 끊어지는 현상을 조사해주세요"
        ]

        for i, query in enumerate(test_questions, 1):
            print(f"\n📝 테스트 {i}: {query}")
            print("-" * 60)

            # RRF 검색
            print("🔄 RRF 방식:")
            rrf_results = rrf_system.rrf_search(query)
            print(f"   결과: {len(rrf_results)}개")

            # 기존 하이브리드 검색
            print("🔄 기존 하이브리드 방식:")
            hybrid_results = hybrid_system.hybrid_search(query, n_results=10)
            print(f"   결과: {len(hybrid_results)}개")

            # 상위 3개 결과 비교
            print(f"\n🏆 상위 3개 결과 비교:")

            print("RRF 방식:")
            for j, result in enumerate(rrf_results[:3], 1):
                score = result.get('score', 0)
                rrf_rank = result.get('rrf_rank', j)
                chunk_type = result.get('chunk_type', 'unknown')
                content_preview = result['content'][:80].replace('\n', ' ') + "..."
                print(f"  {j}. [{chunk_type}] RRF순위:{rrf_rank} 점수:{score:.4f}")
                print(f"     {content_preview}")

            print("\n기존 하이브리드 방식:")
            for j, result in enumerate(hybrid_results[:3], 1):
                score = result.get('score', result.get('raw_score', 0))
                chunk_type = result.get('chunk_type', 'unknown')
                content_preview = result['content'][:80].replace('\n', ' ') + "..."
                print(f"  {j}. [{chunk_type}] 점수:{score:.4f}")
                print(f"     {content_preview}")

        return True

    except Exception as e:
        print(f"❌ 비교 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rrf_system():
    """RRF 시스템 단독 테스트"""
    print("🚀 RRF RAG 시스템 테스트")
    print("="*80)

    try:
        # RRF 시스템 초기화
        rrf_system = RRFRAGSystem()

        test_questions = [
            "사용자 인터페이스가 복잡해서 개선이 필요합니다",
            "API 응답 시간이 너무 느려서 최적화가 필요합니다"
        ]

        for i, query in enumerate(test_questions, 1):
            print(f"\n📝 테스트 {i}: {query}")
            print("="*60)

            # RRF 검색 수행
            results = rrf_system.rrf_search(query)

            if results:
                print(f"✅ {len(results)}개 결과 (RRF + 가중치)")

                # 상위 5개 결과 표시
                for j, result in enumerate(results[:5], 1):
                    score = result.get('score', 0)
                    raw_score = result.get('raw_score', 0)
                    weight = result.get('weight', 1.0)
                    chunk_type = result.get('chunk_type', 'unknown')
                    rrf_rank = result.get('rrf_rank', j)

                    print(f"  {j}. [{chunk_type.upper()}] (RRF순위: {rrf_rank}, 가중치: {weight:.1f})")
                    print(f"     점수: {raw_score:.4f} → {score:.4f}")

                    content_preview = result['content'][:100].replace('\n', ' ') + "..."
                    print(f"     내용: {content_preview}")
                    print()
            else:
                print("❌ 결과 없음")

        return True

    except Exception as e:
        print(f"❌ RRF 시스템 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("RRF RAG 시스템 테스트 선택:")
    print("1. RRF 시스템 단독 테스트")
    print("2. RRF vs 하이브리드 비교 테스트")

    choice = input("\n선택 (1/2): ").strip()

    if choice == "1":
        test_rrf_system()
    elif choice == "2":
        compare_rrf_vs_hybrid()
    else:
        print("RRF 시스템 단독 테스트를 실행합니다.")
        test_rrf_system()