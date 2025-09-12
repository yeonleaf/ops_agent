#!/usr/bin/env python3
"""
티켓 AI 추천 시스템
정제된 메일 + description + 유사도 검색 결과를 LLM에게 넘겨서 
티켓 처리 방안을 추천하는 기능
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Azure OpenAI 설정
load_dotenv()

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Multi-Vector + Cross-Encoder RAG import
try:
    from multi_vector_cross_encoder_rag import MultiVectorCrossEncoderRAG
    MULTI_VECTOR_RAG_AVAILABLE = True
except ImportError:
    MULTI_VECTOR_RAG_AVAILABLE = False

# MultiQueryRetriever import (fallback)
try:
    from multi_query_retriever import create_multi_query_search_manager
    MULTI_QUERY_AVAILABLE = True
except ImportError:
    MULTI_QUERY_AVAILABLE = False

# QueryExpansionRetriever import (fallback)
try:
    from query_expansion_retriever import create_query_expansion_retriever
    QUERY_EXPANSION_AVAILABLE = True
except ImportError:
    QUERY_EXPANSION_AVAILABLE = False

# HybridSearchRetriever import (fallback)
try:
    from retrieve_rerank_retriever_whoosh import create_retrieve_rerank_retriever_whoosh
    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    HYBRID_SEARCH_AVAILABLE = False

class TicketAIRecommender:
    """티켓 AI 추천 시스템"""
    
    def __init__(self):
        self.client = None
        self.multi_vector_rag = None
        self.multi_query_search_manager = None
        self.query_expansion_retriever = None
        self.retrieve_rerank_retriever = None
        
        if OPENAI_AVAILABLE:
            self._init_azure_openai()
        
        # Multi-Vector + Cross-Encoder RAG 우선 초기화
        if MULTI_VECTOR_RAG_AVAILABLE:
            self._init_multi_vector_rag()
        
        # 폴백 검색 시스템들
        if MULTI_QUERY_AVAILABLE:
            self._init_multi_query_search()
        
        if QUERY_EXPANSION_AVAILABLE:
            self._init_query_expansion_search()
        
        if HYBRID_SEARCH_AVAILABLE:
            self._init_hybrid_search()
    
    def _init_azure_openai(self):
        """Azure OpenAI 클라이언트 초기화"""
        try:
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
            print("✅ Azure OpenAI 클라이언트 초기화 완료")
        except Exception as e:
            print(f"❌ Azure OpenAI 클라이언트 초기화 실패: {str(e)}")
            self.client = None
    
    def _init_multi_vector_rag(self):
        """Multi-Vector + Cross-Encoder RAG 시스템 초기화"""
        try:
            self.multi_vector_rag = MultiVectorCrossEncoderRAG()
            print("✅ Multi-Vector + Cross-Encoder RAG 시스템 초기화 완료")
        except Exception as e:
            print(f"❌ Multi-Vector + Cross-Encoder RAG 시스템 초기화 실패: {str(e)}")
            self.multi_vector_rag = None
    
    def _init_multi_query_search(self):
        """MultiQuery 검색 관리자 초기화"""
        try:
            from vector_db_models import VectorDBManager
            vector_db = VectorDBManager()
            self.multi_query_search_manager = create_multi_query_search_manager(vector_db)
            print("✅ MultiQuery 검색 관리자 초기화 완료")
        except Exception as e:
            print(f"❌ MultiQuery 검색 관리자 초기화 실패: {str(e)}")
            self.multi_query_search_manager = None
    
    def _init_query_expansion_search(self):
        """QueryExpansion 검색 관리자 초기화"""
        try:
            from vector_db_models import VectorDBManager
            vector_db = VectorDBManager()
            self.query_expansion_retriever = create_query_expansion_retriever(vector_db)
            print("✅ QueryExpansion 검색 관리자 초기화 완료")
        except Exception as e:
            print(f"❌ QueryExpansion 검색 관리자 초기화 실패: {str(e)}")
            self.query_expansion_retriever = None
    
    def _init_hybrid_search(self):
        """하이브리드 검색 관리자 초기화 (Whoosh 기반)"""
        try:
            from vector_db_models import VectorDBManager
            vector_db = VectorDBManager()
            self.retrieve_rerank_retriever = create_retrieve_rerank_retriever_whoosh(vector_db)
            print("✅ 하이브리드 검색 관리자 초기화 완료 (Whoosh 기반)")
        except Exception as e:
            print(f"❌ 하이브리드 검색 관리자 초기화 실패: {str(e)}")
            self.retrieve_rerank_retriever = None
    
    def get_similar_tickets_with_rag(self, ticket_description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Multi-Vector + Cross-Encoder RAG를 사용한 유사 티켓 검색"""
        try:
            if not self.multi_vector_rag:
                print("⚠️ Multi-Vector RAG 사용 불가, 폴백 검색으로 전환")
                return self.get_similar_emails(ticket_description, limit)
            
            print(f"🔍 Multi-Vector + Cross-Encoder RAG 검색 시작: '{ticket_description}'")
            
            # Multi-Vector + Cross-Encoder RAG 검색
            results = self.multi_vector_rag.search(
                query=ticket_description,
                n_candidates=30,  # 1단계 후보 수
                top_k=limit       # 최종 결과 수
            )
            
            if not results:
                print("⚠️ RAG 검색 결과 없음, 폴백 검색으로 전환")
                return self.get_similar_emails(ticket_description, limit)
            
            print(f"✅ Multi-Vector + Cross-Encoder RAG 검색 완료: {len(results)}개 결과")
            
            # 결과를 기존 형식으로 변환
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.get("id", ""),
                    "content": result.get("content", ""),
                    "source": "multi_vector_rag",
                    "similarity_score": result.get("similarity_score", 0.0),
                    "metadata": result.get("metadata", {}),
                    "search_type": "multi_vector_cross_encoder",
                    "ticket_id": result.get("metadata", {}).get("ticket_id", ""),
                    "parent_ticket_id": result.get("metadata", {}).get("parent_ticket_id", ""),
                    "chunk_type": result.get("metadata", {}).get("chunk_type", ""),
                    "cross_encoder_score": result.get("metadata", {}).get("cross_encoder_score", 0.0)
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Multi-Vector RAG 검색 실패: {str(e)}")
            print("🔄 폴백 검색으로 전환...")
            return self.get_similar_emails(ticket_description, limit)
    
    def get_similar_emails(self, ticket_description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Vector DB에서 유사한 메일들을 검색 (QueryExpansion 우선 적용)"""
        try:
            # QueryExpansion 검색 사용 (우선)
            if self.query_expansion_retriever:
                print(f"🔍 QueryExpansion 메일 검색 시작: '{ticket_description}'")
                results = self.query_expansion_retriever.search_with_expansion(
                    ticket_description, k=limit, search_type="mails"
                )
                print(f"✅ QueryExpansion 메일 검색 완료: {len(results)}개 결과")
                
                # 결과를 기존 형식으로 변환
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "message_id": result.get("id", ""),
                        "subject": result.get("metadata", {}).get("subject", ""),
                        "sender": result.get("metadata", {}).get("sender", ""),
                        "refined_content": result.get("content", ""),
                        "content_summary": result.get("metadata", {}).get("content_summary", ""),
                        "key_points": result.get("metadata", {}).get("key_points", []),
                        "similarity_score": result.get("similarity_score", 0.0),
                        "created_at": result.get("metadata", {}).get("created_at", ""),
                        "source_type": "email",
                        "expanded_query": result.get("expanded_query", ""),
                        "query_rank": result.get("query_rank", 1)
                    })
                return formatted_results
            
            # 폴백: MultiQuery 검색 사용
            elif self.multi_query_search_manager:
                print(f"🔍 MultiQuery 메일 검색 시작: '{ticket_description}'")
                results = self.multi_query_search_manager.search_mails(ticket_description, k=limit)
                print(f"✅ MultiQuery 메일 검색 완료: {len(results)}개 결과")
                
                # 결과를 기존 형식으로 변환
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "message_id": result.get("id", ""),
                        "subject": result.get("metadata", {}).get("subject", ""),
                        "sender": result.get("metadata", {}).get("sender", ""),
                        "refined_content": result.get("content", ""),
                        "content_summary": result.get("metadata", {}).get("content_summary", ""),
                        "key_points": result.get("metadata", {}).get("key_points", []),
                        "similarity_score": result.get("similarity_score", 0.0),
                        "created_at": result.get("metadata", {}).get("created_at", ""),
                        "source_type": "email"
                    })
                return formatted_results
            
            # 폴백: 기본 검색
            print("⚠️ MultiQuery 사용 불가, 기본 메일 검색으로 폴백")
            from vector_db_models import VectorDBManager
            
            vector_db = VectorDBManager()
            
            # 유사도 검색 수행
            similar_emails = vector_db.search_similar_mails(
                query=ticket_description,
                n_results=limit
            )
            
            # 결과를 딕셔너리 형태로 변환
            results = []
            for i, email in enumerate(similar_emails):
                # 유사도 점수는 순서에 따라 계산 (첫 번째가 가장 유사)
                similarity_score = max(0.0, 1.0 - (i * 0.1))
                
                results.append({
                    "message_id": email.message_id,
                    "subject": email.subject,
                    "sender": email.sender,
                    "refined_content": email.refined_content,
                    "content_summary": email.content_summary,
                    "key_points": email.key_points,
                    "similarity_score": similarity_score,
                    "created_at": email.created_at,
                    "source_type": "email"  # 소스 타입 추가
                })
            
            print(f"✅ 유사 메일 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            print(f"❌ 유사 메일 검색 실패: {str(e)}")
            return []
    
    def get_similar_file_chunks(self, ticket_description: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Vector DB에서 유사한 파일 청크들을 검색 (MultiQuery 적용)"""
        try:
            # MultiQuery 검색 사용
            if self.multi_query_search_manager:
                print(f"🔍 MultiQuery 파일 청크 검색 시작: '{ticket_description}'")
                results = self.multi_query_search_manager.search_file_chunks(ticket_description, k=limit)
                print(f"✅ MultiQuery 파일 청크 검색 완료: {len(results)}개 결과")
                
                # 결과에 소스 타입 추가
                for result in results:
                    result["source_type"] = "file_chunk"
                
                return results
            
            # 폴백: 기본 검색
            print("⚠️ MultiQuery 사용 불가, 기본 파일 청크 검색으로 폴백")
            from vector_db_models import VectorDBManager
            
            vector_db = VectorDBManager()
            
            # 유사도 검색 수행
            similar_chunks = vector_db.search_similar_file_chunks(
                query=ticket_description,
                n_results=limit
            )
            
            # 결과에 소스 타입 추가
            for chunk in similar_chunks:
                chunk["source_type"] = "file_chunk"
            
            print(f"✅ 유사 파일 청크 검색 완료: {len(similar_chunks)}개 결과")
            return similar_chunks
            
        except Exception as e:
            print(f"❌ 유사 파일 청크 검색 실패: {str(e)}")
            return []
    
    def get_integrated_similar_content(self, ticket_description: str, email_limit: int = 3, chunk_limit: int = 2) -> List[Dict[str, Any]]:
        """Multi-Vector + Cross-Encoder RAG 우선, 폴백으로 하이브리드 검색을 활용한 유사한 콘텐츠 검색"""
        try:
            # Multi-Vector + Cross-Encoder RAG 우선 시도
            if self.multi_vector_rag:
                print(f"🔍 Multi-Vector + Cross-Encoder RAG 통합 검색 시작: '{ticket_description}'")
                rag_results = self.get_similar_tickets_with_rag(ticket_description, limit=5)
                
                if rag_results:
                    print(f"✅ Multi-Vector + Cross-Encoder RAG 검색 완료: {len(rag_results)}개 결과")
                    return rag_results
                else:
                    print("⚠️ Multi-Vector RAG 결과 없음, 폴백 검색으로 전환")
            
            # 폴백: Retrieve then Re-rank 검색 시도 (Vector + BM25 + CohereRerank)
            if self.retrieve_rerank_retriever:
                print(f"🔍 Retrieve then Re-rank 검색 시작: '{ticket_description}'")
                hybrid_results = self.retrieve_rerank_retriever.search(
                    query=ticket_description,
                    k=5
                )
                
                if hybrid_results:
                    print(f"✅ Retrieve then Re-rank 검색 완료: {len(hybrid_results)}개 결과")
                    
                    # 하이브리드 검색 결과를 표준 형식으로 변환
                    formatted_results = []
                    for result in hybrid_results:
                        formatted_result = {
                            "id": result.get("id", ""),
                            "content": result.get("content", ""),
                            "source": result.get("source", "retrieve_rerank_whoosh"),
                            "similarity_score": result.get("similarity_score", 0.0),
                            "metadata": result.get("metadata", {}),
                            "search_type": result.get("search_type", "unknown")
                        }
                        formatted_results.append(formatted_result)
                    
                    return formatted_results
                else:
                    print("⚠️ 하이브리드 검색 결과 없음, QueryExpansion으로 폴백")
            
            # 폴백: QueryExpansion 검색
            if self.query_expansion_retriever:
                print(f"🔍 QueryExpansion 통합 검색 시작: '{ticket_description}'")
                expansion_results = self.query_expansion_retriever.search_with_expansion(
                    query=ticket_description,
                    k=5,
                    search_type="all"
                )
                
                if expansion_results:
                    print(f"✅ QueryExpansion 검색 완료: {len(expansion_results)}개 결과")
                    
                    # QueryExpansion 결과를 표준 형식으로 변환
                    formatted_results = []
                    for result in expansion_results:
                        formatted_result = {
                            "id": result.get("id", ""),
                            "content": result.get("content", ""),
                            "source": result.get("source", "unknown"),
                            "similarity_score": result.get("similarity_score", 0.0),
                            "metadata": result.get("metadata", {}),
                            "expanded_query": result.get("expanded_query", ""),
                            "query_rank": result.get("query_rank", 1)
                        }
                        formatted_results.append(formatted_result)
                    
                    return formatted_results
                else:
                    print("⚠️ QueryExpansion 결과 없음, MultiQuery로 폴백")
            
            # 폴백: MultiQuery 구조적 청킹 검색
            if self.multi_query_search_manager:
                print(f"🔍 MultiQuery 구조적 청킹 검색 시작: '{ticket_description}'")
                structured_results = self.multi_query_search_manager.search_structured_chunks(
                    query=ticket_description,
                    k=5,
                    chunk_types=['header'],  # 헤더 청크만 우선 검색 (Summary + Description)
                    priority_filter=2  # 우선순위 1-2만 (높은 우선순위)
                )
            else:
                # 폴백: 기본 구조적 청킹 검색
                print("⚠️ MultiQuery 사용 불가, 기본 구조적 청킹 검색으로 폴백")
                from vector_db_models import VectorDBManager
                
                vector_db = VectorDBManager()
                
                # 1. 구조적 청킹 검색 우선 시도
                print(f"🔍 구조적 청킹 검색 시작: '{ticket_description}'")
                structured_results = vector_db.search_structured_chunks(
                    query=ticket_description,
                    n_results=5,
                    chunk_types=['header'],  # 헤더 청크만 우선 검색 (Summary + Description)
                    priority_filter=2  # 우선순위 1-2만 (높은 우선순위)
                )
            
            if structured_results:
                print(f"✅ 구조적 청킹 검색 완료: {len(structured_results)}개 결과")
                
                # 구조적 청킹 결과를 표준 형식으로 변환
                formatted_results = []
                for result in structured_results:
                    formatted_result = {
                        "id": result["chunk_id"],
                        "content": result["content"],
                        "source": "structured_chunk",
                        "similarity_score": result["similarity_score"],
                        "metadata": {
                            "ticket_id": result["ticket_id"],
                            "chunk_type": result["chunk_type"],
                            "field_name": result["field_name"],
                            "priority": result["priority"],
                            "file_name": result["file_name"]
                        }
                    }
                    formatted_results.append(formatted_result)
                
                return formatted_results
            
            # 2. 구조적 청킹 결과가 없으면 Cohere Re-ranking 시도
            print("⚠️ 구조적 청킹 결과 없음, Cohere Re-ranking으로 폴백...")
            try:
                from cohere_rerank_module import search_with_cohere_rerank
                
                # 1차 검색에서 더 많은 후보를 가져오기 위해 k 설정
                k = max(email_limit + chunk_limit, 20)
                
                print(f"🔍 Cohere Re-ranking 압축 검색 시작: '{ticket_description}'")
                rerank_results = search_with_cohere_rerank(ticket_description, k=k)
                
                if rerank_results:
                    print(f"✅ Cohere Re-ranking 검색 완료: {len(rerank_results)}개 결과")
                    return rerank_results
                else:
                    print("⚠️ Cohere Re-ranking 결과가 없음, 기본 검색으로 폴백")
                    raise Exception("Cohere Re-ranking 결과 없음")
                    
            except Exception as rerank_error:
                print(f"⚠️ Cohere Re-ranking 실패: {str(rerank_error)}")
                print("🔄 기본 벡터 검색으로 폴백...")
                
                # 폴백: 기존 방식 사용
                similar_emails = self.get_similar_emails(ticket_description, email_limit)
                similar_chunks = self.get_similar_file_chunks(ticket_description, chunk_limit)
                
                # 결과 통합 및 정렬
                all_results = similar_emails + similar_chunks
                
                # 유사도 점수 기준으로 정렬 (높은 순)
                all_results.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
                
                print(f"✅ 기본 통합 검색 완료: 메일 {len(similar_emails)}개, 파일 청크 {len(similar_chunks)}개")
                return all_results
            
        except Exception as e:
            print(f"❌ 통합 검색 실패: {str(e)}")
            return []
    
    def generate_ai_recommendation(self, ticket_data: Dict[str, Any], similar_content: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI를 사용하여 티켓 처리 방안 추천 생성"""
        if not self.client:
            return {
                "success": False,
                "error": "Azure OpenAI 클라이언트가 초기화되지 않았습니다.",
                "recommendation": "AI 추천 기능을 사용할 수 없습니다. Azure OpenAI 설정을 확인해주세요."
            }
        
        try:
            # 프롬프트 구성
            prompt = self._build_recommendation_prompt(ticket_data, similar_content)
            
            # Azure OpenAI API 호출
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 업무 효율성을 높이는 티켓 처리 전문가입니다. 주어진 티켓 정보와 유사한 사례들을 분석하여 구체적이고 실행 가능한 처리 방안을 제시해주세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            recommendation = response.choices[0].message.content
            
            return {
                "success": True,
                "recommendation": recommendation,
                "ticket_id": ticket_data.get("ticket_id"),
                "generated_at": datetime.now().isoformat(),
                "similar_content_count": len(similar_content)
            }
            
        except Exception as e:
            error_str = str(e)
            print(f"❌ AI 추천 생성 실패: {error_str}")
            
            # 콘텐츠 필터 오류 처리
            if "content_filter" in error_str or "content management policy" in error_str:
                print("⚠️ Azure OpenAI 콘텐츠 필터에 의해 차단됨")
                return {
                    "success": False,
                    "error": "콘텐츠 필터",
                    "recommendation": "이 티켓의 내용이 Azure OpenAI 콘텐츠 정책에 의해 필터링되었습니다. 키워드 기반 추천을 사용합니다.",
                    "fallback": True
                }
            
            return {
                "success": False,
                "error": str(e),
                "recommendation": f"AI 추천 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def _generate_keyword_based_recommendation(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """키워드 기반 폴백 추천 생성"""
        try:
            title = ticket_data.get('title', '').lower()
            description = ticket_data.get('description', '').lower()
            content = f"{title} {description}"
            
            # 키워드 기반 추천 로직
            recommendations = []
            
            # 서버 관련 키워드
            if any(keyword in content for keyword in ['서버', 'server', 'api', '점검', '에러', 'error']):
                recommendations.append("• 서버 상태 확인 및 로그 분석을 권장합니다")
                recommendations.append("• API 엔드포인트 테스트를 수행해보세요")
                recommendations.append("• 시스템 모니터링 도구를 활용하세요")
            
            # UI 관련 키워드
            if any(keyword in content for keyword in ['ui', '인터페이스', '화면', '버튼', '체크박스']):
                recommendations.append("• UI/UX 개선사항을 검토해보세요")
                recommendations.append("• 사용자 피드백을 수집하세요")
                recommendations.append("• 디자인 시스템 가이드라인을 확인하세요")
            
            # 데이터베이스 관련 키워드
            if any(keyword in content for keyword in ['데이터베이스', 'database', 'db', '쿼리', 'query']):
                recommendations.append("• 데이터베이스 성능 최적화를 고려하세요")
                recommendations.append("• 쿼리 실행 계획을 분석해보세요")
                recommendations.append("• 인덱스 최적화를 검토하세요")
            
            # 보안 관련 키워드
            if any(keyword in content for keyword in ['보안', 'security', '인증', 'auth', '권한']):
                recommendations.append("• 보안 정책을 재검토하세요")
                recommendations.append("• 접근 권한을 점검해보세요")
                recommendations.append("• 보안 감사를 수행하세요")
            
            # 기본 추천 (키워드가 없는 경우)
            if not recommendations:
                recommendations = [
                    "• 관련 문서를 검토해보세요",
                    "• 팀 내부 검토를 진행하세요",
                    "• 우선순위를 재평가해보세요"
                ]
            
            return {
                "success": True,
                "recommendation": "키워드 기반 추천:\n" + "\n".join(recommendations),
                "ticket_id": ticket_data.get("ticket_id"),
                "generated_at": datetime.now().isoformat(),
                "method": "keyword_based"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"키워드 기반 추천 생성 실패: {str(e)}",
                "recommendation": "추천을 생성할 수 없습니다."
            }
    
    def _build_recommendation_prompt(self, ticket_data: Dict[str, Any], similar_content: List[Dict[str, Any]]) -> str:
        """추천 생성을 위한 프롬프트 구성"""
        
        # 티켓 기본 정보
        ticket_info = f"""
=== 티켓 정보 ===
- ID: {ticket_data.get('ticket_id', 'N/A')}
- 제목: {ticket_data.get('title', 'N/A')}
- 설명: {ticket_data.get('description', 'N/A')}
- 상태: {ticket_data.get('status', 'N/A')}
- 우선순위: {ticket_data.get('priority', 'N/A')}
- 타입: {ticket_data.get('ticket_type', 'N/A')}
- 담당자: {ticket_data.get('reporter', 'N/A')}
- 레이블: {', '.join(ticket_data.get('labels', []))}
"""
        
        # 원본 메일 정보
        original_mail = ticket_data.get('original_mail', {})
        mail_info = f"""
=== 원본 메일 정보 ===
- 발신자: {original_mail.get('sender', 'N/A')}
- 제목: {original_mail.get('subject', 'N/A')}
- 정제된 내용: {original_mail.get('refined_content', 'N/A')}
- 요약: {original_mail.get('content_summary', 'N/A')}
- 핵심 포인트: {', '.join(original_mail.get('key_points', []))}
"""
        
        # 유사 콘텐츠 정보 (RAG 검색 결과 + 메일 + 파일 청크)
        similar_info = ""
        if similar_content:
            similar_info = "\n=== 유사한 사례들 ===\n"
            
            # RAG 검색 결과, 메일, 파일 청크를 분리하여 표시
            rag_results = [item for item in similar_content if item.get('source') == 'multi_vector_rag']
            emails = [item for item in similar_content if item.get('source_type') == 'email']
            file_chunks = [item for item in similar_content if item.get('source_type') == 'file_chunk']
            
            # RAG 검색 결과 정보 (우선 표시)
            if rag_results:
                similar_info += "\n🎯 AI 검색 결과 (Multi-Vector + Cross-Encoder):\n"
                for i, result in enumerate(rag_results[:3], 1):  # 상위 3개 사용
                    content_preview = result.get('content', '')[:300] + "..." if len(result.get('content', '')) > 300 else result.get('content', '')
                    similar_info += f"""
검색 결과 {i}:
- 티켓 ID: {result.get('ticket_id', 'N/A')}
- 청크 타입: {result.get('chunk_type', 'N/A')}
- Cross-Encoder 점수: {result.get('cross_encoder_score', 0.0):.4f}
- 내용: {content_preview}
- 유사도: {result.get('similarity_score', 0.0):.2f}
"""
            
            # 유사 메일 정보
            if emails:
                similar_info += "\n📧 유사한 메일 사례:\n"
                for i, email in enumerate(emails[:2], 1):  # 상위 2개만 사용
                    similar_info += f"""
메일 사례 {i}:
- 제목: {email.get('subject', 'N/A')}
- 발신자: {email.get('sender', 'N/A')}
- 요약: {email.get('content_summary', 'N/A')}
- 유사도: {email.get('similarity_score', 0.0):.2f}
"""
            
            # 유사 파일 청크 정보
            if file_chunks:
                similar_info += "\n📄 관련 문서 내용:\n"
                for i, chunk in enumerate(file_chunks[:2], 1):  # 상위 2개만 사용
                    content_preview = chunk.get('content', '')[:200] + "..." if len(chunk.get('content', '')) > 200 else chunk.get('content', '')
                    similar_info += f"""
문서 사례 {i}:
- 파일명: {chunk.get('file_name', 'N/A')}
- 파일타입: {chunk.get('file_type', 'N/A')}
- 내용: {content_preview}
- 유사도: {chunk.get('similarity_score', 0.0):.2f}
"""
        else:
            similar_info = "\n=== 유사한 사례들 ===\n유사한 사례를 찾을 수 없습니다."
        
        # 최종 프롬프트
        prompt = f"""
{ticket_info}

{mail_info}

{similar_info}

=== 요청사항 ===
위 티켓 정보와 AI 검색 결과(유사한 티켓 사례들)를 분석하여, 이 티켓을 효율적으로 처리하기 위한 구체적인 방안을 제시해주세요.

**특히 AI 검색 결과에서 찾은 유사한 티켓들의 처리 방식을 참고하여** 다음 항목들을 포함하여 답변해주세요:

1. **즉시 처리 방안**: 우선적으로 해야 할 작업들
2. **단계별 처리 계획**: 체계적인 처리 순서 (유사 사례 참고)
3. **주의사항**: 처리 시 고려해야 할 점들
4. **예상 소요시간**: 각 단계별 예상 시간
5. **관련 부서/담당자**: 연락이 필요한 부서나 담당자
6. **참고 문서**: 관련 문서나 자료 활용 방안
7. **유사 사례 활용**: AI 검색 결과의 유사한 티켓 처리 방식을 어떻게 적용할 수 있는지

답변은 구체적이고 실행 가능한 내용으로 작성해주세요.
"""
        
        return prompt
    
    def get_recommendation_for_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """특정 티켓에 대한 AI 추천 생성"""
        try:
            # 티켓 정보 조회
            from sqlite_ticket_models import SQLiteTicketManager
            from vector_db_models import VectorDBManager
            
            ticket_manager = SQLiteTicketManager()
            vector_db = VectorDBManager()
            
            # 티켓 데이터 조회
            ticket = ticket_manager.get_ticket_by_id(ticket_id)
            if not ticket:
                return {
                    "success": False,
                    "error": f"티켓 {ticket_id}를 찾을 수 없습니다.",
                    "recommendation": "티켓을 찾을 수 없습니다."
                }
            
            # 원본 메일 정보 조회
            original_mail = vector_db.get_mail_by_id(ticket.original_message_id)
            mail_data = {}
            if original_mail:
                mail_data = {
                    "sender": original_mail.sender,
                    "subject": original_mail.subject,
                    "refined_content": original_mail.refined_content,
                    "content_summary": original_mail.content_summary,
                    "key_points": original_mail.key_points
                }
            
            # 티켓 데이터 구성
            ticket_data = {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "ticket_type": ticket.ticket_type,
                "reporter": ticket.reporter,
                "labels": ticket.labels,
                "original_mail": mail_data
            }
            
            # 통합 검색 (메일 + 파일 청크)
            search_query = f"{ticket.title} {ticket.description or ''}"
            similar_content = self.get_integrated_similar_content(search_query, email_limit=3, chunk_limit=2)
            
            # AI 추천 생성
            recommendation = self.generate_ai_recommendation(ticket_data, similar_content)
            
            # 콘텐츠 필터 오류가 발생한 경우 키워드 기반 추천으로 폴백
            if not recommendation.get("success") and recommendation.get("fallback"):
                print("🔄 키워드 기반 추천으로 폴백...")
                fallback_recommendation = self._generate_keyword_based_recommendation(ticket_data)
                if fallback_recommendation.get("success"):
                    return fallback_recommendation
            
            return recommendation
            
        except Exception as e:
            print(f"❌ 티켓 추천 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": f"추천 생성 중 오류가 발생했습니다: {str(e)}"
            }

# 전역 인스턴스
ticket_ai_recommender = TicketAIRecommender()

def get_ticket_ai_recommendation(ticket_id: int) -> Dict[str, Any]:
    """티켓 AI 추천을 가져오는 편의 함수"""
    return ticket_ai_recommender.get_recommendation_for_ticket(ticket_id)

if __name__ == "__main__":
    # 테스트 코드
    print("🧪 티켓 AI 추천 시스템 테스트 (Multi-Vector + Cross-Encoder RAG 통합)")
    
    # 첫 번째 티켓으로 테스트
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        tickets = ticket_manager.get_all_tickets()
        
        if tickets:
            test_ticket_id = tickets[0].ticket_id
            print(f"📋 테스트 티켓 ID: {test_ticket_id}")
            
            # RAG 시스템 상태 확인
            recommender = TicketAIRecommender()
            if recommender.multi_vector_rag:
                print("✅ Multi-Vector + Cross-Encoder RAG 시스템 활성화")
            else:
                print("⚠️ Multi-Vector RAG 시스템 비활성화, 폴백 모드")
            
            recommendation = get_ticket_ai_recommendation(test_ticket_id)
            
            if recommendation.get("success"):
                print("✅ AI 추천 생성 성공!")
                print(f"📝 추천 내용:\n{recommendation.get('recommendation', 'N/A')}")
                print(f"🔍 유사 콘텐츠 수: {recommendation.get('similar_content_count', 0)}개")
            else:
                print(f"❌ AI 추천 생성 실패: {recommendation.get('error', 'N/A')}")
        else:
            print("❌ 테스트할 티켓이 없습니다.")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
