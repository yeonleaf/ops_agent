#!/usr/bin/env python3
"""
Memory-Based Ticket Processor Tool (Mem0 리팩토링 버전)

mem0 라이브러리를 사용하여 장기 기억(Long-term Memory)을 활용한 HITL(Human-in-the-Loop) 티켓 생성 도구
기존의 복잡한 Vector DB + RDB 조회 로직을 mem0의 단순한 API로 교체
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
from mem0_memory_adapter import Mem0Memory, create_mem0_memory, add_ticket_event, search_related_memories
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
    """장기 기억을 활용한 티켓 처리 도구 (Mem0 리팩토링 버전)"""
    
    name: str = "memory_based_ticket_processor"
    description: str = """
    mem0 라이브러리를 사용한 장기 기억(Long-term Memory)을 활용하여 이메일에서 Jira 티켓 생성 여부를 결정하고 실행하는 도구입니다.
    
    4단계 워크플로우 (단순화됨):
    1. 검색(Retrieval): mem0을 사용한 관련 기억 검색
    2. 추론(Reasoning): AI가 티켓 생성 여부 판단 → 최적 레이블 추천
    3. 실행(Action): 실제 Jira 티켓 생성 또는 생성하지 않음
    4. 통합된 기억 저장(Unified Memorization): mem0에 AI 결정 저장
    
    입력: email_content, email_subject, email_sender, message_id
    출력: 티켓 생성 결과 및 AI 판단 과정
    """
    args_schema: Type[BaseModel] = TicketDecisionInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Mem0Memory 인스턴스는 lazy loading으로 초기화
    
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
    
    def _get_mem0_memory(self) -> Mem0Memory:
        """Mem0Memory 인스턴스 반환 (lazy loading)"""
        if not hasattr(self, '_mem0_memory') or self._mem0_memory is None:
            try:
                self._mem0_memory = create_mem0_memory("ai_system")
                print("✅ Mem0Memory 인스턴스 초기화 완료")
            except Exception as e:
                print(f"❌ Mem0Memory 초기화 실패: {e}")
                raise e
        return self._mem0_memory
    
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
        """1단계: 검색 (Retrieval) - mem0을 사용한 관련 기억 검색 (단순화됨)"""
        try:
            print("  🔍 1단계: mem0 기반 관련 기억 검색 시작")
            print(f"    📧 검색 대상: {email_subject[:50]}...")
            
            # mem0에서 관련 기억 검색 (기존의 복잡한 Vector DB + RDB 조회를 단 한 줄로 교체)
            mem0_memory = self._get_mem0_memory()
            related_memories = search_related_memories(
                memory=mem0_memory,
                email_content=email_content,
                limit=5
            )
            
            print(f"  ✅ 관련 기억 {len(related_memories)}개 발견")
            
            # 발견된 기억 상세 정보 출력
            for i, memory in enumerate(related_memories, 1):
                memory_text = memory.get('memory', 'N/A')
                score = memory.get('score', 0.0)
                metadata = memory.get('metadata', {})
                action_type = metadata.get('action_type', 'unknown')
                
                print(f"    📋 관련 기억 {i}: {memory_text[:60]}...")
                print(f"      점수: {score:.3f}, 액션 타입: {action_type}")
                
                if metadata.get('ticket_id'):
                    print(f"      관련 티켓: {metadata['ticket_id']}")
                if metadata.get('message_id'):
                    print(f"      관련 메일: {metadata['message_id']}")
            
            # 기억 요약 출력
            if related_memories:
                print("  📋 발견된 관련 기억 요약:")
                for i, memory in enumerate(related_memories, 1):
                    memory_text = memory.get('memory', '')
                    print(f"    {i}. {memory_text}")
            else:
                print("  ℹ️ 관련된 기억이 없습니다.")
            
            return {
                "related_memories": related_memories,
                "search_summary": {
                    "related_memories_count": len(related_memories),
                    "search_method": "mem0_semantic_search"
                }
            }
            
        except Exception as e:
            print(f"  ❌ mem0 검색 단계 실패: {e}")
            return {
                "related_memories": [],
                "search_summary": {"error": str(e), "search_method": "mem0_semantic_search"}
            }
    
    def _reasoning_phase(self, email_content: str, email_subject: str, email_sender: str, retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: 추론 (Reasoning) - AI가 티켓 생성 여부와 레이블 결정"""
        try:
            print("  🧠 2a. 티켓 생성 여부 판단 시작")
            
            # LLM에게 검색된 기억과 함께 판단 요청
            llm = self._get_llm()
            
            # mem0에서 검색된 기억들을 요약
            memory_summary = self._summarize_mem0_memories(retrieval_result.get("related_memories", []))
            
            print(f"  📋 AI 판단에 활용할 mem0 기억 요약:")
            print(f"    {memory_summary}")
            
            # 판단 프롬프트 생성 (mem0 기반으로 업데이트)
            decision_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 이메일을 분석하여 Jira 티켓 생성 여부를 결정하는 AI 어시스턴트입니다.

mem0에서 검색된 '관련 기억'들을 참고하여 판단해야 합니다. 이 기억들은 과거의 사용자 행동과 AI 결정을 요약한 맥락화된 정보입니다.

**판단 기준:**
1. 업무 관련성: 실제 업무 처리나 문제 해결이 필요한지
2. 액션 필요성: 사용자나 시스템이 취해야 할 구체적인 액션이 있는지
3. 우선순위: 긴급하거나 중요한 이슈인지
4. 과거 패턴: mem0 기억에서 유사한 이메일이 어떻게 처리되었는지

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

**mem0 관련 기억:**
{memory_summary.replace('{', '{{').replace('}', '}}')}

**판단 요청:**
주어진 '관련 기억'들을 참고하여, 새로운 이메일에 가장 적합한 레이블을 추천하고 티켓 생성 여부를 판단해주세요.""")
            ])
            
            # LLM 실행 (스트리밍 버전) - Content Filter 오류 처리 포함
            decision_chain = decision_prompt | llm | StrOutputParser()
            
            # 스트리밍 처리
            current_result = ""
            final_result = None
            
            try:
                for chunk in decision_chain.stream({}):
                    current_result += chunk
                    final_result = current_result
                
                decision_result = final_result if final_result else ""
                
            except Exception as llm_error:
                # Content Filter 오류 또는 기타 LLM 오류 처리
                error_str = str(llm_error)
                if "content_filter" in error_str or "ResponsibleAIPolicyViolation" in error_str:
                    print(f"  ⚠️ Content Filter 오류 감지: {error_str}")
                    print(f"  🔄 기본 키워드 기반 분석으로 폴백")
                    
                    # Content Filter 오류 시 기본 키워드 기반 분석 수행
                    decision_result = self._fallback_keyword_analysis(email_content, email_subject, email_sender)
                else:
                    # 기타 LLM 오류는 그대로 전파
                    raise llm_error
            
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
        """4단계: 통합된 기억 저장 - mem0을 사용한 AI 결정 저장 (단순화됨)"""
        try:
            print("  💾 4단계: mem0 기반 기억 저장 시작")
            
            # AI 결정을 기억 문장으로 변환
            decision = reasoning_result.get("ticket_creation_decision", {})
            action = action_result.get("action_taken", "unknown")
            
            if action == "ticket_created":
                memory_sentence = f"AI Action: 제목 '{decision.get('title', '')}' 이메일에 대해 '{decision.get('priority', '')}', '{', '.join(decision.get('labels', []))}' 레이블로 티켓 T-{action_result.get('ticket_id', '')}를 생성함."
            else:
                memory_sentence = f"AI Decision: '{decision.get('reason', '')}' 이유로 티켓 생성하지 않음."
            
            # mem0에 기억 저장 (기존의 복잡한 RDB + Vector DB 저장을 단 한 줄로 교체)
            mem0_memory = self._get_mem0_memory()
            memory_id = add_ticket_event(
                memory=mem0_memory,
                event_type="ai_decision",
                description=memory_sentence,
                ticket_id=action_result.get('ticket_id'),
                message_id=message_id,
                old_value="",
                new_value=action
            )
            
            print(f"  ✅ mem0 기억 저장 완료: {memory_id}")
            
        except Exception as e:
            print(f"  ❌ mem0 기억 저장 단계 실패: {e}")
    
    def _summarize_mem0_memories(self, memories: List[Dict[str, Any]]) -> str:
        """mem0에서 검색된 기억들을 요약하여 문자열로 반환"""
        if not memories:
            return "관련 과거 기억이 없습니다."
        
        summary_parts = []
        for i, memory in enumerate(memories[:3], 1):  # 최대 3개만 사용
            memory_text = memory.get('memory', '')
            score = memory.get('score', 0.0)
            metadata = memory.get('metadata', {})
            action_type = metadata.get('action_type', 'unknown')
            
            if memory_text:
                summary_parts.append(f"{i}. {memory_text} (신뢰도: {score:.3f}, 타입: {action_type})")
        
        return "\n".join(summary_parts) if summary_parts else "관련 과거 기억이 없습니다."
    
    def _summarize_memories(self, memories: List[Dict[str, Any]]) -> str:
        """과거 기억들을 요약하여 문자열로 반환 (하위 호환성용)"""
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
    
    def _fallback_keyword_analysis(self, email_content: str, email_subject: str, email_sender: str) -> str:
        """Content Filter 오류 시 사용할 기본 키워드 기반 분석"""
        print("  🔍 키워드 기반 폴백 분석 시작")
        
        # 업무 관련 키워드 패턴
        work_keywords = [
            'bug', 'error', 'issue', 'problem', 'fix', 'urgent', 'important',
            'meeting', 'schedule', 'deadline', 'project', 'task', 'request',
            'approve', 'review', 'feedback', 'action', 'required', 'help',
            'support', 'service', 'system', 'server', 'database', 'api',
            '버그', '오류', '문제', '수정', '긴급', '중요', '회의', '일정',
            '마감', '프로젝트', '작업', '요청', '승인', '검토', '피드백',
            '액션', '필요', '도움', '지원', '서비스', '시스템', '서버', '데이터베이스'
        ]
        
        # 개인/마케팅 관련 키워드 패턴
        personal_keywords = [
            'newsletter', 'marketing', 'promotion', 'sale', 'discount',
            'personal', 'private', 'spam', 'unsubscribe', 'advertisement',
            '뉴스레터', '마케팅', '프로모션', '세일', '할인', '개인', '사적',
            '스팸', '구독취소', '광고', '지옥', '고백', 'MZ', '숏폼'
        ]
        
        # 텍스트 분석
        full_text = f"{email_subject} {email_content}".lower()
        
        work_score = sum(1 for keyword in work_keywords if keyword.lower() in full_text)
        personal_score = sum(1 for keyword in personal_keywords if keyword.lower() in full_text)
        
        # 판단 로직
        if work_score > personal_score and work_score > 0:
            decision = "create_ticket"
            reason = f"키워드 분석: 업무 관련 키워드 {work_score}개 발견 (개인/마케팅 키워드 {personal_score}개)"
            confidence = min(0.7, 0.3 + (work_score * 0.1))
            priority = "High" if work_score >= 3 else "Medium"
            labels = ["키워드-분석", "업무-관련"]
            ticket_type = "Bug" if any(kw in full_text for kw in ['bug', 'error', '오류', '버그']) else "Task"
        else:
            decision = "no_ticket"
            reason = f"키워드 분석: 개인/마케팅 키워드 {personal_score}개 발견 (업무 키워드 {work_score}개)"
            confidence = min(0.6, 0.3 + (personal_score * 0.1))
            priority = "Low"
            labels = ["키워드-분석", "개인-관련"]
            ticket_type = "Task"
        
        # 결과 포맷팅
        result = f"""decision: {decision}
reason: {reason}
confidence: {confidence:.2f}
priority: {priority}
labels: {', '.join(labels)}
ticket_type: {ticket_type}"""
        
        print(f"  ✅ 키워드 분석 완료: {decision} (신뢰도: {confidence:.2f})")
        return result

def create_memory_based_ticket_processor():
    """MemoryBasedTicketProcessorTool 인스턴스 생성 헬퍼 함수"""
    return MemoryBasedTicketProcessorTool()

def record_user_correction(ticket_id: Any, old_label: str, new_label: str, user_id: str = "user") -> bool:
    """사용자 피드백을 mem0 장기 기억에 저장하는 헬퍼 함수 (단순화됨)"""
    try:
        from mem0_memory_adapter import create_mem0_memory, add_ticket_event
        
        # mem0에 사용자 피드백 저장 (기존의 복잡한 RDB + Vector DB 저장을 단 한 줄로 교체)
        mem0_memory = create_mem0_memory(user_id)
        memory_id = add_ticket_event(
            memory=mem0_memory,
            event_type="user_correction",
            description=f"User Correction: 티켓 {ticket_id}의 레이블을 '{old_label}'에서 '{new_label}'으로 수정함.",
            ticket_id=str(ticket_id),
            old_value=old_label,
            new_value=new_label
        )
        
        print(f"✅ mem0 사용자 피드백 저장 완료: {memory_id}")
        return True
        
    except Exception as e:
        print(f"❌ mem0 사용자 피드백 저장 실패: {e}")
        return False
