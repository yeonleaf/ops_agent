#!/usr/bin/env python3
"""
HyDE (Hypothetical Document Embeddings) 기반 RAG 시스템
멀티 쿼리와 HyDE를 결합한 하이브리드 검색 전략 구현
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import numpy as np

# Azure OpenAI 설정
load_dotenv()

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 기존 모듈들 import
from setup_korean_embedding import KoreanEmbeddingFunction
from intelligent_chunk_weighting import IntelligentChunkWeighting

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HyDEConfig:
    """HyDE 시스템 설정"""
    # LLM 설정
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    azure_openai_deployment_name: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")

    # 검색 설정
    multi_query_count: int = 3  # 멀티 쿼리 개수
    hyde_document_count: int = 1  # HyDE 문서 개수
    top_k_per_query: int = 15  # 쿼리당 검색 결과 수
    final_candidates: int = 50  # 최종 후보 수

class HyDEPromptTemplate:
    """HyDE 프롬프트 템플릿 관리 클래스"""

    # 기본 HyDE 프롬프트 템플릿
    HYDE_PROMPT_TEMPLATE = """다음 사용자 질문에 대해, 가장 완벽하고 이상적인 답변을 Jira 티켓 형식으로 생성해주세요.
실제 정보가 없어도 괜찮습니다. 질문의 핵심 의도를 파악하여 가장 관련성 높은 가상의 문서를 만들어내는 것이 목표입니다.
답변은 간결하고 명확하게 작성해주세요.

사용자 질문: "{question}"

가상의 답변 (Jira 티켓 내용):
"""

    # 멀티 쿼리 생성 프롬프트
    MULTI_QUERY_PROMPT_TEMPLATE = """사용자의 질문을 바탕으로, 의미는 유사하지만 다른 표현의 검색 쿼리 3개를 생성해주세요.
각 쿼리는 원본 질문과 같은 정보를 찾을 수 있지만, 다른 키워드나 표현을 사용해야 합니다.

원본 질문: "{question}"

검색 쿼리 1:
검색 쿼리 2:
검색 쿼리 3:
"""

    @classmethod
    def create_hyde_prompt(cls, question: str) -> str:
        """HyDE 문서 생성용 프롬프트 생성"""
        return cls.HYDE_PROMPT_TEMPLATE.format(question=question)

    @classmethod
    def create_multi_query_prompt(cls, question: str) -> str:
        """멀티 쿼리 생성용 프롬프트 생성"""
        return cls.MULTI_QUERY_PROMPT_TEMPLATE.format(question=question)

class HyDEDocumentGenerator:
    """HyDE 가상 문서 생성기"""

    def __init__(self, config: HyDEConfig):
        """
        HyDE 문서 생성기 초기화

        Args:
            config: HyDE 설정
        """
        self.config = config
        self.llm_client = None
        self._init_llm_client()

    def _init_llm_client(self):
        """Azure OpenAI 클라이언트 초기화"""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai 라이브러리가 설치되지 않았습니다.")

        if not all([
            self.config.azure_openai_api_key,
            self.config.azure_openai_endpoint,
            self.config.azure_openai_deployment_name
        ]):
            raise ValueError("Azure OpenAI 환경변수가 설정되지 않았습니다.")

        self.llm_client = AzureOpenAI(
            api_key=self.config.azure_openai_api_key,
            api_version=self.config.azure_openai_api_version,
            azure_endpoint=self.config.azure_openai_endpoint
        )

        logger.info("✅ Azure OpenAI 클라이언트 초기화 완료")

    def generate_hypothetical_document(self, question: str) -> str:
        """
        HyDE 가상 문서 생성

        Args:
            question: 사용자 질문

        Returns:
            생성된 가상 문서
        """
        try:
            prompt = HyDEPromptTemplate.create_hyde_prompt(question)

            response = self.llm_client.chat.completions.create(
                model=self.config.azure_openai_deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 Jira 티켓 내용을 생성하는 전문가입니다. 사용자의 질문에 대해 가장 이상적인 답변을 담은 가상의 문서를 생성하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )

            hypothetical_doc = response.choices[0].message.content.strip()

            logger.info(f"✅ HyDE 문서 생성 완료: {len(hypothetical_doc)}자")
            return hypothetical_doc

        except Exception as e:
            logger.error(f"❌ HyDE 문서 생성 실패: {e}")
            # 실패 시 원본 질문을 기반으로 간단한 가상 문서 생성
            return f"질문 '{question}'에 대한 해결 방법과 상세한 설명이 포함된 문서입니다."

    def generate_multi_queries(self, question: str) -> List[str]:
        """
        멀티 쿼리 생성

        Args:
            question: 사용자 질문

        Returns:
            생성된 멀티 쿼리 리스트
        """
        try:
            prompt = HyDEPromptTemplate.create_multi_query_prompt(question)

            response = self.llm_client.chat.completions.create(
                model=self.config.azure_openai_deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 검색 쿼리 생성 전문가입니다. 주어진 질문과 의미는 같지만 다른 표현의 검색 쿼리를 생성하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=200
            )

            response_text = response.choices[0].message.content.strip()

            # 응답에서 쿼리 추출
            queries = []
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()
                if line and ('검색 쿼리' in line or line.startswith(('1.', '2.', '3.', '-', '*'))):
                    # 번호나 기호 제거
                    clean_query = line.split(':', 1)[-1].strip()
                    if clean_query and len(clean_query) > 5:  # 너무 짧은 쿼리 제외
                        queries.append(clean_query)

            # 3개 미만이면 원본 질문 변형으로 보완
            while len(queries) < self.config.multi_query_count:
                if len(queries) == 0:
                    queries.append(f"{question} 문제")
                elif len(queries) == 1:
                    queries.append(f"{question} 해결")
                elif len(queries) == 2:
                    queries.append(f"{question} 방법")

            queries = queries[:self.config.multi_query_count]

            logger.info(f"✅ 멀티 쿼리 생성 완료: {len(queries)}개")
            return queries

        except Exception as e:
            logger.error(f"❌ 멀티 쿼리 생성 실패: {e}")
            # 실패 시 간단한 변형 쿼리 생성
            return [
                f"{question} 문제",
                f"{question} 해결",
                f"{question} 방법"
            ]

class HyDERAGSystem:
    """HyDE 기반 RAG 시스템"""

    def __init__(self, collection_name: str = "file_chunks", config: Optional[HyDEConfig] = None):
        """
        HyDE RAG 시스템 초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
            config: HyDE 설정
        """
        self.collection_name = collection_name
        self.config = config or HyDEConfig()

        # 컴포넌트 초기화
        self.client = None
        self.collection = None
        self.embedding_function = None
        self.hyde_generator = None
        self.weighting_system = None

        self._init_components()

    def _init_components(self):
        """시스템 컴포넌트 초기화"""
        try:
            # ChromaDB 연결
            self.client = chromadb.PersistentClient(
                path='./vector_db',
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            self.collection = self.client.get_collection(self.collection_name)

            # 한국어 임베딩 함수 (기존 컬렉션과 호환되도록 384차원 사용)
            self.embedding_function = KoreanEmbeddingFunction()

            # HyDE 문서 생성기
            self.hyde_generator = HyDEDocumentGenerator(self.config)

            # 가중치 시스템
            self.weighting_system = IntelligentChunkWeighting()

            logger.info(f"✅ HyDE RAG 시스템 초기화 완료: {self.collection.count()}개 문서")

        except Exception as e:
            logger.error(f"❌ HyDE RAG 시스템 초기화 실패: {e}")
            raise e

    def search(self, query: str, use_hyde: bool = True, use_multi_query: bool = True) -> List[Dict[str, Any]]:
        """
        HyDE 기반 하이브리드 검색

        Args:
            query: 사용자 질문
            use_hyde: HyDE 사용 여부
            use_multi_query: 멀티 쿼리 사용 여부

        Returns:
            검색 결과 리스트
        """
        try:
            logger.info(f"🚀 HyDE RAG 검색 시작: '{query}'")

            # 1. 검색할 텍스트 리스트 준비
            texts_to_embed = [query]  # 원본 질문은 항상 포함

            # 2. 멀티 쿼리 생성 (옵션)
            if use_multi_query:
                multi_queries = self.hyde_generator.generate_multi_queries(query)
                texts_to_embed.extend(multi_queries)
                logger.info(f"📝 멀티 쿼리: {multi_queries}")

            # 3. HyDE 문서 생성 (옵션)
            if use_hyde:
                hypothetical_doc = self.hyde_generator.generate_hypothetical_document(query)
                texts_to_embed.append(hypothetical_doc)
                logger.info(f"🎯 HyDE 문서: {hypothetical_doc[:100]}...")

            logger.info(f"🔍 총 {len(texts_to_embed)}개 텍스트로 검색 수행")

            # 4. 각 텍스트로 벡터 검색 수행
            all_results = []
            for i, text in enumerate(texts_to_embed):
                try:
                    # 검색 수행 (기존 컬렉션의 임베딩 함수 사용)
                    results = self.collection.query(
                        query_texts=[text],
                        n_results=self.config.top_k_per_query
                    )

                    # 결과 처리
                    if results['ids'][0]:
                        for j in range(len(results['ids'][0])):
                            result = {
                                'id': results['ids'][0][j],
                                'content': results['documents'][0][j] if results['documents'][0] else "",
                                'distance': results['distances'][0][j] if results['distances'][0] else 1.0,
                                'metadata': results['metadatas'][0][j] if results['metadatas'][0] else {},
                                'query_type': 'original' if i == 0 else ('multi' if i < len(texts_to_embed) - (1 if use_hyde else 0) else 'hyde'),
                                'query_index': i,
                                'source_text': text[:100] + "..." if len(text) > 100 else text
                            }
                            all_results.append(result)

                    logger.info(f"   쿼리 {i+1}: {len(results['ids'][0]) if results['ids'][0] else 0}개 결과")

                except Exception as e:
                    logger.error(f"❌ 쿼리 {i+1} 검색 실패: {e}")
                    continue

            # 5. 결과 통합 및 중복 제거
            unique_results = self._process_and_deduplicate(all_results, query)

            logger.info(f"✅ HyDE RAG 검색 완료: {len(unique_results)}개 고유 결과")
            return unique_results

        except Exception as e:
            logger.error(f"❌ HyDE RAG 검색 실패: {e}")
            return []

    def _process_and_deduplicate(self, all_results: List[Dict[str, Any]], original_query: str) -> List[Dict[str, Any]]:
        """
        검색 결과 처리 및 중복 제거

        Args:
            all_results: 모든 검색 결과
            original_query: 원본 질문

        Returns:
            중복 제거된 최종 결과
        """
        try:
            # 1. ID 기반 중복 제거 및 점수 통합
            unique_docs = {}

            for result in all_results:
                doc_id = result['id']
                distance = result['distance']
                cosine_score = max(0.0, 1.0 - distance)

                if doc_id not in unique_docs:
                    unique_docs[doc_id] = {
                        'id': doc_id,
                        'content': result['content'],
                        'metadata': result['metadata'],
                        'scores': [],
                        'query_types': [],
                        'source_texts': []
                    }

                unique_docs[doc_id]['scores'].append(cosine_score)
                unique_docs[doc_id]['query_types'].append(result['query_type'])
                unique_docs[doc_id]['source_texts'].append(result['source_text'])

            # 2. 점수 통합 (최대값 사용)
            processed_results = []
            for doc_id, doc_data in unique_docs.items():
                max_score = max(doc_data['scores'])

                # chunk_type 추정
                chunk_type = self._estimate_chunk_type(doc_data['metadata'], doc_data['content'])

                # 가중치 적용을 위한 형식으로 변환
                search_result = {
                    'id': doc_id,
                    'content': doc_data['content'],
                    'chunk_type': chunk_type,
                    'cosine_score': max_score,
                    'embedding': [],
                    'metadata': {
                        **doc_data['metadata'],
                        'query_types': doc_data['query_types'],
                        'source_texts': doc_data['source_texts'],
                        'scores': doc_data['scores'],
                        'max_score': max_score,
                        'hyde_enhanced': True
                    }
                }
                processed_results.append(search_result)

            # 3. 가중치 적용
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()
            weighted_results = self.weighting_system.apply_weighted_scoring(
                processed_results, mock_query_embedding
            )

            # 4. 최종 형식으로 변환
            final_results = []
            for weighted_result in weighted_results[:self.config.final_candidates]:
                result = {
                    "id": weighted_result.id,
                    "content": weighted_result.content,
                    "score": weighted_result.weighted_score,
                    "raw_score": weighted_result.cosine_score,
                    "weight": weighted_result.weight,
                    "chunk_type": weighted_result.chunk_type,
                    "source": "hyde_rag_system",
                    "metadata": {
                        **weighted_result.metadata,
                        "hyde_enhanced": True,
                        "weight_applied": True
                    }
                }
                final_results.append(result)

            return final_results

        except Exception as e:
            logger.error(f"❌ 결과 처리 실패: {e}")
            return []

    def _estimate_chunk_type(self, metadata: Dict[str, Any], content: str) -> str:
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

def test_hyde_system():
    """HyDE 시스템 테스트"""
    print("🚀 HyDE RAG 시스템 테스트")
    print("="*80)

    try:
        # HyDE 시스템 초기화
        hyde_rag = HyDERAGSystem(collection_name="file_chunks")

        # 테스트 질문들
        test_questions = [
            "사용자 인터페이스가 복잡해서 개선이 필요합니다",
            "서버에 접속할 수 없는 문제를 해결하고 싶어요",
            "데이터베이스 연결이 자주 끊어지는 현상을 조사해주세요",
            "API 응답 시간이 너무 느려서 최적화가 필요합니다"
        ]

        for i, question in enumerate(test_questions, 1):
            print(f"\n📝 테스트 {i}: {question}")
            print("-" * 60)

            # HyDE 검색 수행
            results = hyde_rag.search(question)

            if results:
                print(f"✅ {len(results)}개 결과 (HyDE + 멀티쿼리 + 가중치)")

                # 상위 3개 결과 표시
                for j, result in enumerate(results[:3], 1):
                    score = result.get('score', 0)
                    raw_score = result.get('raw_score', 0)
                    weight = result.get('weight', 1.0)
                    chunk_type = result.get('chunk_type', 'unknown')

                    print(f"  {j}. [{chunk_type.upper()}] (가중치: {weight:.1f})")
                    print(f"     점수: {raw_score:.4f} → {score:.4f}")

                    # 내용 미리보기
                    content = result.get('content', '')
                    preview = content[:100].replace('\n', ' ') + "..."
                    print(f"     내용: {preview}")

                    # HyDE 정보
                    metadata = result.get('metadata', {})
                    if metadata.get('query_types'):
                        query_types = set(metadata['query_types'])
                        print(f"     검색 타입: {', '.join(query_types)}")
                    print()
            else:
                print("❌ 결과 없음")

        return True

    except Exception as e:
        print(f"❌ HyDE 시스템 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_hyde_system()