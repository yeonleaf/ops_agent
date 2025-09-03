#!/usr/bin/env python3
"""
Memory-Based Ticket Processor Tool

장기 기억(Long-term Memory)을 활용한 HITL(Human-in-the-Loop) 티켓 생성 도구
사용자의 피드백을 기억하고 다음 결정에 활용하는 스스로 학습하는 시스템
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field

# LangChain imports
from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 프로젝트 내부 모듈들
from database_models import DatabaseManager, UserAction, Ticket, TicketEvent
from vector_db_models import VectorDBManager, UserActionVectorDBManager
from jira_connector import JiraConnector
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class TicketDecisionInput(BaseModel):
    """티켓 처리 도구 입력 모델"""
    email_content: str = Field(description="처리할 이메일 내용")
    email_subject: str = Field(description="이메일 제목")
    email_sender: str = Field(description="이메일 발신자")
    message_id: str = Field(description="이메일 메시지 ID")

class MemoryBasedTicketProcessorTool(BaseTool):
    """장기 기억을 활용한 티켓 처리 도구"""
    
    name: str = "memory_based_ticket_processor"
    description: str = """
    장기 기억(Long-term Memory)을 활용하여 이메일에서 Jira 티켓 생성 여부를 결정하고 실행하는 도구입니다.
    
    4단계 워크플로우:
    1. 검색(Retrieval): 유사 메일 검색 → 과거 티켓 조회 → 사용자 피드백 기억 수집
    2. 추론(Reasoning): AI가 티켓 생성 여부 판단 → 최적 레이블 추천
    3. 실행(Action): 실제 Jira 티켓 생성 또는 생성하지 않음
    4. 통합된 기억 저장(Unified Memorization): AI 결정과 사용자 피드백을 표준화된 문장으로 저장
    
    입력: email_content, email_subject, email_sender, message_id
    출력: 티켓 생성 결과 및 AI 판단 과정
    """
    args_schema: Type[BaseModel] = TicketDecisionInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def _get_db_manager(self) -> DatabaseManager:
        """데이터베이스 매니저 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_db_manager'):
            self._db_manager = DatabaseManager()
        return self._db_manager
    
    def _get_vector_db(self) -> VectorDBManager:
        """Vector DB 매니저 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_vector_db'):
            self._vector_db = VectorDBManager()
        return self._vector_db
    
    def _get_user_action_vector_db(self) -> UserActionVectorDBManager:
        """사용자 액션 Vector DB 매니저 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_user_action_vector_db'):
            self._user_action_vector_db = UserActionVectorDBManager()
        return self._user_action_vector_db
    
    def _get_llm(self) -> AzureChatOpenAI:
        """Azure OpenAI LLM 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_llm'):
            self._llm = self._setup_llm()
        return self._llm
    
    def _get_jira_connector(self) -> Optional[JiraConnector]:
        """Jira 커넥터 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_jira_connector'):
            try:
                self._jira_connector = JiraConnector()
            except Exception as e:
                print(f"⚠️ Jira 연동 설정 실패: {e}")
                self._jira_connector = None
        return self._jira_connector
    
    def _setup_llm(self) -> AzureChatOpenAI:
        """Azure OpenAI LLM 설정"""
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        
        if not all([azure_endpoint, deployment_name, api_key]):
            raise ValueError("Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        
        return AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            deployment_name=deployment_name,
            openai_api_key=api_key,
            openai_api_version=api_version,
            temperature=0.3
        )
    
    def _run(
        self,
        email_content: str,
        email_subject: str, 
        email_sender: str,
        message_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        메인 실행 메서드 - 4단계 워크플로우 구현
        """
        try:
            print(f"🚀 MemoryBasedTicketProcessorTool 실행 시작: {email_subject}")
            
            # 1단계: 검색 (Retrieval)
            print("🔍 1단계: 검색 (Retrieval) 시작")
            retrieval_result = self._retrieval_phase(email_content, email_subject, message_id)
            
            # 2단계: 추론 (Reasoning)
            print("🧠 2단계: 추론 (Reasoning) 시작")
            reasoning_result = self._reasoning_phase(email_content, email_subject, email_sender, retrieval_result)
            
            # 3단계: 실행 (Action)
            print("⚡ 3단계: 실행 (Action) 시작")
            action_result = self._action_phase(reasoning_result, message_id)
            
            # 4단계: 통합된 기억 저장 (Unified Memorization)
            print("💾 4단계: 통합된 기억 저장 (Unified Memorization) 시작")
            self._unified_memorization_phase(reasoning_result, action_result, message_id)
            
            # 최종 결과 반환 (JSON 직렬화 가능하도록 변환)
            def convert_to_serializable(obj):
                """객체를 JSON 직렬화 가능한 형태로 변환"""
                if isinstance(obj, dict):
                    return {key: convert_to_serializable(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_serializable(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    # 객체를 딕셔너리로 변환
                    return {key: str(value) if not isinstance(value, (str, int, float, bool, list, dict)) else convert_to_serializable(value) 
                           for key, value in obj.__dict__.items()}
                else:
                    return str(obj) if not isinstance(obj, (str, int, float, bool, list, dict)) else obj
            
            final_result = {
                "success": True,
                "workflow_steps": {
                    "retrieval": convert_to_serializable(retrieval_result),
                    "reasoning": convert_to_serializable(reasoning_result),
                    "action": convert_to_serializable(action_result)
                },
                "decision": convert_to_serializable(reasoning_result),
                "action": convert_to_serializable(action_result),
                "timestamp": datetime.now().isoformat()
            }
            
            print("✅ MemoryBasedTicketProcessorTool 실행 완료")
            return json.dumps(final_result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            print(f"❌ MemoryBasedTicketProcessorTool 실행 실패: {e}")
            return json.dumps(error_result, ensure_ascii=False, indent=2)
    
    def _retrieval_phase(self, email_content: str, email_subject: str, message_id: str) -> Dict[str, Any]:
        """1단계: 검색 (Retrieval) - 유사 메일, 과거 티켓, 사용자 피드백 조회"""
        try:
            print("  🔍 1a. 유사 메일 검색 시작")
            print(f"    📧 검색 대상: {email_subject[:50]}...")
            
            # Vector DB에서 유사한 과거 메일 검색
            vector_db = self._get_vector_db()
            similar_mails = vector_db.search_similar_mails(email_content, n_results=5)
            
            print(f"  ✅ 유사 메일 {len(similar_mails)}개 발견")
            
            # 유사 메일 상세 정보 출력
            for i, mail in enumerate(similar_mails, 1):
                # Mail 객체의 속성에 직접 접근
                subject = getattr(mail, 'subject', 'N/A')
                mail_message_id = getattr(mail, 'message_id', 'N/A')
                print(f"    📋 유사 메일 {i}: {subject[:40] if subject else 'N/A'}... (ID: {mail_message_id})")
            
            # 1b. 과거 티켓 조회
            print("  🔍 1b. 과거 티켓 조회 시작")
            db_manager = self._get_db_manager()
            
            related_tickets = []
            for i, mail in enumerate(similar_mails, 1):
                mail_message_id = getattr(mail, 'message_id', None)
                if mail_message_id:
                    print(f"    🔎 메일 {i}의 티켓 조회 중: {mail_message_id}")
                    tickets = db_manager.get_tickets_by_message_id(mail_message_id)
                    print(f"    📊 메일 {i}에서 {len(tickets)}개 티켓 발견")
                    related_tickets.extend(tickets)
                    
                    # 발견된 티켓 정보 출력
                    for j, ticket in enumerate(tickets, 1):
                        ticket_id = getattr(ticket, 'ticket_id', None) if hasattr(ticket, 'ticket_id') else ticket.get('ticket_id', None)
                        title = getattr(ticket, 'title', 'N/A') if hasattr(ticket, 'title') else ticket.get('title', 'N/A')
                        print(f"      🎫 티켓 {j}: ID {ticket_id} - {title[:30] if title else 'N/A'}...")
            
            print(f"  ✅ 관련 티켓 {len(related_tickets)}개 발견")
            
            # 1c. 사용자 피드백(기억) 조회
            print("  🔍 1c. 사용자 피드백 기억 조회 시작")
            
            related_memories = []
            for i, ticket in enumerate(related_tickets, 1):
                # Ticket 객체에서 ticket_id 추출
                ticket_id = getattr(ticket, 'ticket_id', None) if hasattr(ticket, 'ticket_id') else (ticket.get('ticket_id') if hasattr(ticket, 'get') else None)
                
                if ticket_id:
                    print(f"    🔍 티켓 {i} (ID: {ticket_id})의 사용자 액션 조회 중...")
                    
                    # SQLite RDB에서 직접 user_actions 조회
                    try:
                        from database_models import DatabaseManager
                        db_manager = DatabaseManager()
                        user_actions = db_manager.get_user_actions_by_ticket_id(ticket_id)
                        
                        print(f"    📊 티켓 {i}에서 {len(user_actions)}개 액션 발견")
                        
                        action_count = 0
                        for action in user_actions:
                            if action.action_type in ['label_added', 'label_removed', 'priority_changed', 'status_changed']:
                                action_count += 1
                                # UUID를 문자열로 변환하여 JSON 직렬화 가능하게 만듦
                                def convert_uuid_to_str(obj):
                                    if hasattr(obj, '__str__'):
                                        return str(obj)
                                    return obj
                                
                                memory_dict = {
                                    'memory_sentence': f"{action.action_type}: {action.action_description}",
                                    'action_type': action.action_type,
                                    'old_value': convert_uuid_to_str(action.old_value),
                                    'new_value': convert_uuid_to_str(action.new_value),
                                    'context': convert_uuid_to_str(action.context),
                                    'created_at': convert_uuid_to_str(action.created_at)
                                }
                                related_memories.append(memory_dict)
                                print(f"      📝 액션 {action_count}: {action.action_type} - {action.action_description}")
                                if action.old_value and action.new_value:
                                    print(f"        변경: {action.old_value} → {action.new_value}")
                                elif action.new_value:
                                    print(f"        추가: {action.new_value}")
                                elif action.old_value:
                                    print(f"        삭제: {action.old_value}")
                    except Exception as e:
                        print(f"    ⚠️ 티켓 {i} 사용자 액션 조회 실패: {e}")
            
            print(f"  ✅ 관련 기억 {len(related_memories)}개 발견")
            
            # 기억 요약 출력
            if related_memories:
                print("  📋 발견된 사용자 액션 요약:")
                for i, memory in enumerate(related_memories, 1):
                    print(f"    {i}. {memory['memory_sentence']}")
            else:
                print("  ℹ️ 관련된 사용자 액션이 없습니다.")
            
            # Mail 객체를 딕셔너리로 변환
            def convert_mail_to_dict(mail):
                if hasattr(mail, '__dict__'):
                    return {key: str(value) if not isinstance(value, (str, int, float, bool, list, dict)) else value 
                           for key, value in mail.__dict__.items()}
                else:
                    return {"message_id": str(mail), "subject": "Unknown", "sender": "Unknown"}
            
            # 유사 메일을 딕셔너리로 변환
            similar_mails_dict = [convert_mail_to_dict(mail) for mail in similar_mails]
            
            return {
                "similar_mails": similar_mails_dict,
                "related_tickets": related_tickets,
                "related_memories": related_memories,
                "search_summary": {
                    "similar_mails_count": len(similar_mails),
                    "related_tickets_count": len(related_tickets),
                    "related_memories_count": len(related_memories)
                }
            }
            
        except Exception as e:
            print(f"  ❌ 검색 단계 실패: {e}")
            return {
                "similar_mails": [],
                "related_tickets": [],
                "related_memories": [],
                "search_summary": {"error": str(e)}
            }
    
    def _reasoning_phase(self, email_content: str, email_subject: str, email_sender: str, retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: 추론 (Reasoning) - AI가 티켓 생성 여부와 레이블 결정"""
        try:
            print("  🧠 2a. 티켓 생성 여부 판단 시작")
            
            # LLM에게 검색된 기억과 함께 판단 요청
            llm = self._get_llm()
            
            # 검색된 기억들을 요약
            memory_summary = self._summarize_memories(retrieval_result.get("related_memories", []))
            
            print(f"  📋 AI 판단에 활용할 기억 요약:")
            print(f"    {memory_summary}")
            
            # 판단 프롬프트 생성
            decision_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 이메일을 분석하여 Jira 티켓 생성 여부를 결정하는 AI 어시스턴트입니다.

과거 기억과 사용자 피드백을 바탕으로 판단해야 합니다.

**판단 기준:**
1. 업무 관련성: 실제 업무 처리나 문제 해결이 필요한지
2. 액션 필요성: 사용자나 시스템이 취해야 할 구체적인 액션이 있는지
3. 우선순위: 긴급하거나 중요한 이슈인지
4. 과거 패턴: 유사한 이메일이 어떻게 처리되었는지

**출력 형식:**
다음 형식으로 응답해주세요:

decision: create_ticket 또는 no_ticket
reason: 판단 이유 (한국어로 상세히)
confidence: 0.0-1.0 사이의 신뢰도
priority: Low/Medium/High/Highest
labels: 레이블1, 레이블2
ticket_type: Bug/Feature/Task/Improvement"""),
                ("human", f"""이메일을 분석하여 티켓 생성 여부를 판단해주세요.

**이메일 정보:**
- 제목: {email_subject.replace('{', '{{').replace('}', '}}')}
- 발신자: {email_sender.replace('{', '{{').replace('}', '}}')}
- 내용: {email_content[:500].replace('{', '{{').replace('}', '}}')}...

**과거 기억 및 피드백:**
{memory_summary.replace('{', '{{').replace('}', '}}')}

**판단 요청:**
이 이메일에 대해 Jira 티켓을 생성해야 할까요? 과거 기억을 바탕으로 판단해주세요.""")
            ])
            
            # LLM 실행 (스트리밍 버전)
            decision_chain = decision_prompt | llm | StrOutputParser()
            
            # 스트리밍 처리
            current_result = ""
            final_result = None
            
            for chunk in decision_chain.stream({}):
                current_result += chunk
                final_result = current_result
            
            decision_result = final_result if final_result else ""
            
            # 텍스트 응답 파싱
            try:
                decision_data = self._parse_text_response(decision_result)
            except Exception:
                # 파싱 실패 시 기본값 사용
                decision_data = {
                    "decision": "create_ticket",
                    "reason": "AI 판단 실패로 인한 기본값",
                    "confidence": 0.5,
                    "priority": "Medium",
                    "labels": ["auto-generated"],
                    "ticket_type": "Task"
                }
            
            print(f"  ✅ AI 판단 완료: {decision_data.get('decision')}")
            
            return {
                "ticket_creation_decision": decision_data,
                "analysis_context": {
                    "email_content_length": len(email_content),
                    "has_attachments": "첨부파일" in email_content.lower(),
                    "urgency_indicators": self._detect_urgency_indicators(email_content, email_subject)
                }
            }
            
        except Exception as e:
            print(f"  ❌ 추론 단계 실패: {e}")
            return {
                "ticket_creation_decision": {
                    "decision": "create_ticket",
                    "reason": f"AI 판단 실패: {str(e)}",
                    "confidence": 0.3,
                    "priority": "Medium",
                    "labels": ["error-fallback"],
                    "ticket_type": "Task"
                },
                "analysis_context": {"error": str(e)}
            }
    
    def _action_phase(self, reasoning_result: Dict[str, Any], message_id: str) -> Dict[str, Any]:
        """3단계: 실행 (Action) - AI 판단에 따라 실제 티켓 생성"""
        try:
            print("  ⚡ 3단계: 실행 (Action) 시작")
            
            decision = reasoning_result.get("ticket_creation_decision", {})
            decision_type = decision.get("decision", "no_ticket")
            
            if decision_type == "create_ticket":
                print("  🎫 티켓 생성 시작")
                
                # 티켓 데이터 준비
                ticket_data = {
                    "title": decision.get("title", "AI 생성 티켓"),
                    "description": decision.get("description", ""),
                    "priority": decision.get("priority", "Medium"),
                    "labels": decision.get("labels", []),
                    "ticket_type": decision.get("ticket_type", "Task"),
                    "status": "new",
                    "created_at": datetime.now().isoformat()
                }
                
                # 데이터베이스에 티켓 저장
                db_manager = self._get_db_manager()
                ticket_id = db_manager.insert_ticket(Ticket(**ticket_data))
                
                print(f"  ✅ 티켓 생성 완료: T-{ticket_id}")
                
                return {
                    "action_taken": "ticket_created",
                    "ticket_id": ticket_id,
                    "ticket_data": ticket_data,
                    "success": True
                }
            else:
                print("  ❌ 티켓 생성 불필요로 판단")
                return {
                    "action_taken": "no_ticket_created",
                    "reason": decision.get("reason", "AI가 티켓 생성 불필요로 판단"),
                    "success": True
                }
                
        except Exception as e:
            print(f"  ❌ 실행 단계 실패: {e}")
            return {
                "action_taken": "error",
                "error": str(e),
                "success": False
            }
    
    def _unified_memorization_phase(self, reasoning_result: Dict[str, Any], action_result: Dict[str, Any], message_id: str):
        """4단계: 통합된 기억 저장 - AI 결정과 사용자 피드백을 표준화된 문장으로 저장"""
        try:
            print("  💾 4단계: 통합된 기억 저장 시작")
            
            # AI 결정을 기억 문장으로 변환
            decision = reasoning_result.get("ticket_creation_decision", {})
            action = action_result.get("action_taken", "unknown")
            
            if action == "ticket_created":
                memory_sentence = f"AI Action: 제목 '{decision.get('title', '')}' 이메일에 대해 '{decision.get('priority', '')}', '{', '.join(decision.get('labels', []))}' 레이블로 티켓 T-{action_result.get('ticket_id', '')}를 생성함."
            else:
                memory_sentence = f"AI Decision: '{decision.get('reason', '')}' 이유로 티켓 생성하지 않음."
            
            # UserAction 객체 생성
            user_action = UserAction(
                action_id=None,
                ticket_id=action_result.get('ticket_id'),
                message_id=message_id,
                action_type="ai_decision",
                action_description=memory_sentence,
                old_value="",
                new_value=action,
                context=f"AI 판단: {decision.get('reason', '')}",
                created_at=datetime.now().isoformat(),
                user_id="ai_system"
            )
            
            # RDB에 저장
            db_manager = self._get_db_manager()
            action_id = db_manager.insert_user_action(user_action)
            
            # Vector DB에 저장
            user_action_db = self._get_user_action_vector_db()
            user_action_db.save_action_memory(str(action_id), memory_sentence, "ai_decision", 
                                            ticket_id=action_result.get('ticket_id'), 
                                            message_id=message_id, 
                                            user_id="ai_system")
            
            print(f"  ✅ 기억 저장 완료: {action_id}")
            
        except Exception as e:
            print(f"  ❌ 기억 저장 단계 실패: {e}")
    
    def _summarize_memories(self, memories: List[Dict[str, Any]]) -> str:
        """과거 기억들을 요약하여 문자열로 반환"""
        if not memories:
            return "관련 과거 기억이 없습니다."
        
        summary_parts = []
        for i, memory in enumerate(memories[:3], 1):  # 최대 3개만 사용
            memory_text = memory.get('memory_sentence', '')
            if memory_text:
                summary_parts.append(f"{i}. {memory_text}")
        
        return "\n".join(summary_parts) if summary_parts else "관련 과거 기억이 없습니다."
    
    def _detect_urgency_indicators(self, content: str, subject: str) -> List[str]:
        """긴급성 지표 감지"""
        urgency_keywords = ["긴급", "urgent", "즉시", "바로", "중요", "important", "장애", "error", "fail", "broken"]
        detected_indicators = []
        
        full_text = f"{subject} {content}".lower()
        for keyword in urgency_keywords:
            if keyword.lower() in full_text:
                detected_indicators.append(keyword)
        
        return detected_indicators
    
    def _parse_text_response(self, response_text: str) -> Dict[str, Any]:
        """텍스트 응답을 파싱하여 딕셔너리로 변환"""
        try:
            lines = response_text.strip().split('\n')
            decision_data = {}
            
            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == 'decision':
                        decision_data['decision'] = value
                    elif key == 'reason':
                        decision_data['reason'] = value
                    elif key == 'confidence':
                        try:
                            decision_data['confidence'] = float(value)
                        except ValueError:
                            decision_data['confidence'] = 0.5
                    elif key == 'priority':
                        decision_data['priority'] = value
                    elif key == 'labels':
                        # 쉼표로 구분된 레이블을 리스트로 변환
                        labels = [label.strip() for label in value.split(',')]
                        decision_data['labels'] = labels
                    elif key == 'ticket_type':
                        decision_data['ticket_type'] = value
            
            # 필수 필드가 없으면 기본값 설정
            if 'decision' not in decision_data:
                decision_data['decision'] = 'create_ticket'
            if 'reason' not in decision_data:
                decision_data['reason'] = 'AI 판단 완료'
            if 'confidence' not in decision_data:
                decision_data['confidence'] = 0.5
            if 'priority' not in decision_data:
                decision_data['priority'] = 'Medium'
            if 'labels' not in decision_data:
                decision_data['labels'] = ['auto-generated']
            if 'ticket_type' not in decision_data:
                decision_data['ticket_type'] = 'Task'
            
            return decision_data
            
        except Exception as e:
            print(f"텍스트 응답 파싱 실패: {e}")
            # 기본값 반환
            return {
                "decision": "create_ticket",
                "reason": f"파싱 실패: {str(e)}",
                "confidence": 0.3,
                "priority": "Medium",
                "labels": ["error-fallback"],
                "ticket_type": "Task"
            }

def create_memory_based_ticket_processor():
    """MemoryBasedTicketProcessorTool 인스턴스 생성 헬퍼 함수"""
    return MemoryBasedTicketProcessorTool()

def record_user_correction(ticket_id: Any, old_label: str, new_label: str, user_id: str = "user") -> bool:
    """사용자 피드백을 장기 기억에 저장하는 헬퍼 함수"""
    try:
        from database_models import DatabaseManager, UserAction
        from vector_db_models import UserActionVectorDBManager
        from datetime import datetime
        
        # RDB에 사용자 액션 저장
        db_manager = DatabaseManager()
        user_action = UserAction(
            action_id=None,
            ticket_id=ticket_id,
            message_id=None,
            action_type="user_correction",
            action_description=f"User Correction: 티켓 {ticket_id}의 레이블을 '{old_label}'에서 '{new_label}'으로 수정함.",
            old_value=old_label,
            new_value=new_label,
            context=f"사용자 피드백: {old_label} → {new_label}",
            created_at=datetime.now().isoformat(),
            user_id=user_id
        )
        
        action_id = db_manager.insert_user_action(user_action)
        
        # Vector DB에 저장
        user_action_db = UserActionVectorDBManager()
        memory_sentence = f"User Correction: 티켓 {ticket_id}의 레이블을 '{old_label}'에서 '{new_label}'으로 수정함."
        user_action_db.save_action_memory(str(action_id), memory_sentence, "user_correction", 
                                        ticket_id=ticket_id, user_id=user_id)
        
        print(f"✅ 사용자 피드백 저장 완료: {action_id}")
        return True
        
    except Exception as e:
        print(f"❌ 사용자 피드백 저장 실패: {e}")
        return False
