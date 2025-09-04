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

class TicketAIRecommender:
    """티켓 AI 추천 시스템"""
    
    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE:
            self._init_azure_openai()
    
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
    
    def get_similar_emails(self, ticket_description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Vector DB에서 유사한 메일들을 검색"""
        try:
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
                    "created_at": email.created_at
                })
            
            print(f"✅ 유사 메일 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            print(f"❌ 유사 메일 검색 실패: {str(e)}")
            return []
    
    def generate_ai_recommendation(self, ticket_data: Dict[str, Any], similar_emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI를 사용하여 티켓 처리 방안 추천 생성"""
        if not self.client:
            return {
                "success": False,
                "error": "Azure OpenAI 클라이언트가 초기화되지 않았습니다.",
                "recommendation": "AI 추천 기능을 사용할 수 없습니다. Azure OpenAI 설정을 확인해주세요."
            }
        
        try:
            # 프롬프트 구성
            prompt = self._build_recommendation_prompt(ticket_data, similar_emails)
            
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
                "similar_emails_count": len(similar_emails)
            }
            
        except Exception as e:
            print(f"❌ AI 추천 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": f"AI 추천 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def _build_recommendation_prompt(self, ticket_data: Dict[str, Any], similar_emails: List[Dict[str, Any]]) -> str:
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
        
        # 유사 메일 정보
        similar_info = ""
        if similar_emails:
            similar_info = "\n=== 유사한 사례들 ===\n"
            for i, email in enumerate(similar_emails[:3], 1):  # 상위 3개만 사용
                similar_info += f"""
사례 {i}:
- 제목: {email.get('subject', 'N/A')}
- 발신자: {email.get('sender', 'N/A')}
- 요약: {email.get('content_summary', 'N/A')}
- 유사도: {email.get('similarity_score', 0.0):.2f}
"""
        else:
            similar_info = "\n=== 유사한 사례들 ===\n유사한 사례를 찾을 수 없습니다."
        
        # 최종 프롬프트
        prompt = f"""
{ticket_info}

{mail_info}

{similar_info}

=== 요청사항 ===
위 티켓 정보와 유사한 사례들을 분석하여, 이 티켓을 효율적으로 처리하기 위한 구체적인 방안을 제시해주세요.

다음 항목들을 포함하여 답변해주세요:
1. **즉시 처리 방안**: 우선적으로 해야 할 작업들
2. **단계별 처리 계획**: 체계적인 처리 순서
3. **주의사항**: 처리 시 고려해야 할 점들
4. **예상 소요시간**: 각 단계별 예상 시간
5. **관련 부서/담당자**: 연락이 필요한 부서나 담당자

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
            
            # 유사 메일 검색
            search_query = f"{ticket.title} {ticket.description or ''}"
            similar_emails = self.get_similar_emails(search_query, limit=5)
            
            # AI 추천 생성
            recommendation = self.generate_ai_recommendation(ticket_data, similar_emails)
            
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
    print("🧪 티켓 AI 추천 시스템 테스트")
    
    # 첫 번째 티켓으로 테스트
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        tickets = ticket_manager.get_all_tickets()
        
        if tickets:
            test_ticket_id = tickets[0].ticket_id
            print(f"📋 테스트 티켓 ID: {test_ticket_id}")
            
            recommendation = get_ticket_ai_recommendation(test_ticket_id)
            
            if recommendation.get("success"):
                print("✅ AI 추천 생성 성공!")
                print(f"📝 추천 내용:\n{recommendation.get('recommendation', 'N/A')}")
            else:
                print(f"❌ AI 추천 생성 실패: {recommendation.get('error', 'N/A')}")
        else:
            print("❌ 테스트할 티켓이 없습니다.")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
