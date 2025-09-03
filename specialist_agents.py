#!/usr/bin/env python3
"""
전문가 에이전트들 (Specialist Agents)
ViewingAgent, AnalysisAgent, TicketingAgent를 정의
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# LangChain imports
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ViewingAgent:
    """이메일 조회 전문가 에이전트"""
    
    def __init__(self):
        self.name = "ViewingAgent"
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 이메일 조회 전문가입니다. 

## 역할
- 사용자의 요청에 따라 이메일을 찾아서 목록을 보여주는 역할만 수행합니다
- 이메일 필터링, 검색, 정렬 등의 조회 작업에 특화되어 있습니다
- 복잡한 분석이나 티켓 생성은 다른 전문가에게 위임합니다

## 사용 가능한 도구
- view_emails_tool: 이메일을 조회하고 목록을 반환합니다

## 응답 형식
- 조회된 이메일 목록을 명확하고 읽기 쉽게 정리하여 제공합니다
- 각 이메일의 제목, 발신자, 날짜, 읽음 상태 등을 포함합니다
- 한국어로 친근하고 전문적인 톤으로 응답합니다"""

        # 도구 정의
        self.tools = [self._create_view_emails_tool()]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_view_emails_tool(self) -> Tool:
        """이메일 조회 도구 생성"""
        def view_emails_tool(query: str) -> str:
            """
            이메일을 조회하고 목록을 반환합니다.
            
            Args:
                query: 사용자 쿼리 (예: "안 읽은 메일 3개", "gmail에서 읽지 않은 메일")
            
            Returns:
                조회된 이메일 목록
            """
            try:
                from unified_email_service import get_raw_emails
                
                # 쿼리에서 provider_name과 filters 추출
                provider_name = "gmail"  # 기본값
                filters = {}
                
                # 쿼리 분석하여 provider_name 추출
                query_lower = query.lower()
                if "gmail" in query_lower:
                    provider_name = "gmail"
                elif "outlook" in query_lower or "graph" in query_lower:
                    provider_name = "graph"
                
                # 쿼리 분석하여 filters 설정
                if "안 읽은" in query_lower or "unread" in query_lower:
                    filters['is_read'] = False
                elif "읽은" in query_lower and "안" not in query_lower:
                    filters['is_read'] = True
                
                # 개수 제한 추출
                import re
                limit_match = re.search(r'(\d+)개', query)
                if limit_match:
                    filters['limit'] = int(limit_match.group(1))
                else:
                    filters['limit'] = 10  # 기본값
                
                emails = get_raw_emails(provider_name, filters)
                
                if not emails:
                    return "조건에 맞는 이메일을 찾을 수 없습니다."
                
                result = f"✅ {len(emails)}개의 이메일을 찾았습니다.\n\n"
                for i, email in enumerate(emails[:10], 1):  # 최대 10개만 표시
                    # EmailMessage 객체인 경우 딕셔너리로 변환
                    if hasattr(email, 'model_dump'):
                        email_dict = email.model_dump()
                    elif hasattr(email, '__dict__'):
                        email_dict = email.__dict__
                    else:
                        email_dict = email
                    
                    result += f"{i}. {email_dict.get('subject', '제목 없음')}\n"
                    result += f"   발신자: {email_dict.get('sender', 'N/A')}\n"
                    result += f"   읽음 상태: {'읽음' if email_dict.get('is_read') else '안 읽음'}\n"
                    result += f"   수신일: {email_dict.get('received_date', 'N/A')}\n\n"
                
                if len(emails) > 10:
                    result += f"... 외 {len(emails) - 10}개 더\n"
                
                return result
                
            except Exception as e:
                logging.error(f"❌ 이메일 조회 실패: {str(e)}")
                return f"이메일 조회 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="view_emails_tool",
            description="이메일을 조회하고 목록을 반환합니다. 쿼리에서 자동으로 이메일 제공자(gmail, outlook)와 필터 조건(안 읽은 메일, 개수 등)을 추출합니다.",
            func=view_emails_tool
        )
    
    def _create_agent(self):
        """에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """에이전트 실행"""
        try:
            logging.info(f"🔍 {self.name} 실행: {query}")
            
            # 컨텍스트가 있으면 쿼리에 추가
            if context:
                enhanced_query = f"{query}\n\n컨텍스트 정보: {context}"
            else:
                enhanced_query = query
                
            result = self.agent_executor.invoke({"input": enhanced_query})
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"


class AnalysisAgent:
    """이메일 분석 전문가 에이전트"""
    
    def __init__(self):
        self.name = "AnalysisAgent"
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 이메일 분류 전문가입니다.

## 역할
- 주어진 이메일의 내용을 분석하여 업무 관련성을 판단하고 요약합니다
- 이메일을 '업무용'과 '개인용'으로 분류합니다
- 이메일의 우선순위, 중요도, 핵심 내용을 분석합니다
- 복잡한 분석과 분류 작업에 특화되어 있습니다

## 사용 가능한 도구
- classify_emails_tool: 이메일을 분석하고 분류합니다

## 응답 형식
- 분석 결과를 명확하고 구조화된 형태로 제공합니다
- 업무 관련성, 우선순위, 핵심 내용을 포함합니다
- 한국어로 전문적이고 분석적인 톤으로 응답합니다"""

        # 도구 정의
        self.tools = [self._create_classify_emails_tool()]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_classify_emails_tool(self) -> Tool:
        """이메일 분류 도구 생성"""
        def classify_emails_tool(emails_json: str) -> str:
            """
            이메일을 분석하고 분류합니다.
            
            Args:
                emails_json: 분석할 이메일 데이터 (JSON 문자열)
            
            Returns:
                이메일 분석 및 분류 결과
            """
            try:
                import json
                
                # 이메일 데이터 파싱
                try:
                    emails_data = json.loads(emails_json)
                except (json.JSONDecodeError, TypeError):
                    # JSON이 아닌 경우 문자열로 처리
                    emails_data = emails_json
                
                if not emails_data:
                    return "분석할 이메일 데이터가 없습니다."
                
                # LLM을 사용하여 이메일 분석
                analysis_prompt = f"""
다음 이메일들을 분석하여 업무 관련성을 판단하고 분류해주세요:

이메일 데이터: {emails_data}

각 이메일에 대해 다음을 분석해주세요:
1. 업무 관련성 (업무용/개인용)
2. 우선순위 (High/Medium/Low)  
3. 핵심 내용 요약
4. 필요한 조치사항

분석 결과를 명확하고 구체적으로 설명해주세요."""

                # LLM 호출
                response = self.llm.invoke([HumanMessage(content=analysis_prompt)])
                return response.content
                
            except Exception as e:
                logging.error(f"❌ 이메일 분석 실패: {str(e)}")
                return f"이메일 분석 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="classify_emails_tool",
            description="이메일을 분석하고 업무 관련성, 우선순위, 핵심 내용을 분류합니다.",
            func=classify_emails_tool
        )
    
    def _create_agent(self):
        """에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """에이전트 실행"""
        try:
            logging.info(f"📊 {self.name} 실행: {query}")
            
            # 컨텍스트가 있으면 쿼리에 추가
            if context:
                enhanced_query = f"{query}\n\n컨텍스트 정보: {context}"
            else:
                enhanced_query = query
                
            result = self.agent_executor.invoke({"input": enhanced_query})
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"


class TicketingAgent:
    """Jira 티켓 처리 전문가 에이전트"""
    
    def __init__(self):
        self.name = "TicketingAgent"
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 Jira 티켓 처리 전문가입니다.

## 역할
- 이메일을 분석하여 티켓을 생성하고, 과거의 사용자 피드백(메모리)을 참고하여 최적의 판단을 내립니다
- 복잡한 워크플로우와 메모리 기반 학습을 통한 티켓 처리를 전담합니다
- 기존 티켓 조회, 수정, 상태 변경 등의 티켓 관리 작업을 수행합니다
- 가장 복잡하고 중요한 업무를 담당합니다

## 사용 가능한 도구
- process_tickets_tool: 이메일을 분석하여 티켓을 생성하고 처리합니다
- memory_tool: 과거 사용자 피드백과 메모리를 조회합니다

## 응답 형식
- 티켓 생성/처리 결과를 상세하고 구조화된 형태로 제공합니다
- 메모리 기반 판단 근거를 포함합니다
- 한국어로 전문적이고 신뢰할 수 있는 톤으로 응답합니다"""

        # 도구 정의
        self.tools = [self._create_process_tickets_tool(), self._create_memory_tool()]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_process_tickets_tool(self) -> Tool:
        """티켓 처리 도구 생성"""
        def process_tickets_tool(query: str) -> str:
            """
            이메일을 분석하여 티켓을 생성하고 처리합니다.
            
            Args:
                query: 사용자 쿼리 (예: "안 읽은 메일을 티켓으로 만들어줘", "gmail에서 티켓 생성")
            
            Returns:
                티켓 생성 및 처리 결과
            """
            try:
                from unified_email_service import process_emails_with_ticket_logic
                
                # 쿼리에서 provider_name 추출
                provider_name = "gmail"  # 기본값
                query_lower = query.lower()
                if "gmail" in query_lower:
                    provider_name = "gmail"
                elif "outlook" in query_lower or "graph" in query_lower:
                    provider_name = "graph"
                
                result = process_emails_with_ticket_logic(provider_name, query)
                
                if result.get('display_mode') == 'tickets':
                    tickets = result.get('tickets', [])
                    new_tickets = result.get('new_tickets_created', 0)
                    existing_tickets = result.get('existing_tickets_found', 0)
                    
                    response = f"✅ 티켓 처리 완료!\n"
                    response += f"📊 총 {len(tickets)}개의 티켓을 처리했습니다.\n"
                    response += f"🆕 새로 생성된 티켓: {new_tickets}개\n"
                    response += f"📋 기존 티켓: {existing_tickets}개\n\n"
                    
                    if tickets:
                        response += "📋 처리된 티켓 목록:\n"
                        for i, ticket in enumerate(tickets[:5], 1):
                            response += f"{i}. {ticket.get('title', '제목 없음')}\n"
                            response += f"   상태: {ticket.get('status', 'N/A')}\n"
                            response += f"   우선순위: {ticket.get('priority', 'N/A')}\n"
                            response += f"   레이블: {', '.join(ticket.get('labels', []))}\n\n"
                        
                        if len(tickets) > 5:
                            response += f"... 외 {len(tickets) - 5}개 더\n"
                    
                    return response
                else:
                    return result.get('message', '티켓 처리 결과를 가져올 수 없습니다.')
                
            except Exception as e:
                logging.error(f"❌ 티켓 처리 실패: {str(e)}")
                return f"티켓 처리 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="process_tickets_tool",
            description="이메일을 분석하여 Jira 티켓을 생성하고 처리합니다. 쿼리에서 자동으로 이메일 제공자를 추출하고, 메모리 기반 학습을 통해 최적의 레이블과 우선순위를 결정합니다.",
            func=process_tickets_tool
        )
    
    def _create_memory_tool(self) -> Tool:
        """메모리 조회 도구 생성"""
        def memory_tool(ticket_id: str = None, query: str = "") -> str:
            """
            과거 사용자 피드백과 메모리를 조회합니다.
            
            Args:
                ticket_id: 특정 티켓 ID (선택사항)
                query: 검색 쿼리
            
            Returns:
                메모리 조회 결과
            """
            try:
                # 티켓 조회 요청인지 확인
                if query and any(keyword in query.lower() for keyword in ["티켓 조회", "전체 티켓", "티켓 목록", "생성된 티켓"]):
                    from sqlite_ticket_models import SQLiteTicketManager
                    
                    ticket_manager = SQLiteTicketManager()
                    tickets = ticket_manager.get_all_tickets()
                    
                    if not tickets:
                        return "생성된 티켓이 없습니다."
                    
                    result = f"📋 전체 티켓 목록 ({len(tickets)}개):\n\n"
                    for i, ticket in enumerate(tickets[:10], 1):  # 최대 10개만 표시
                        result += f"{i}. {ticket.title}\n"
                        result += f"   ID: {ticket.ticket_id}\n"
                        result += f"   상태: {ticket.status}\n"
                        result += f"   우선순위: {ticket.priority}\n"
                        result += f"   레이블: {', '.join(ticket.labels) if ticket.labels else '없음'}\n"
                        result += f"   생성일: {ticket.created_at[:10]}\n\n"
                    
                    if len(tickets) > 10:
                        result += f"... 외 {len(tickets) - 10}개 더\n"
                    
                    return result
                
                # 기존 메모리 조회 로직
                from database_models import DatabaseManager
                
                db_manager = DatabaseManager()
                
                if ticket_id and ticket_id.isdigit():
                    # 특정 티켓의 사용자 액션 조회
                    user_actions = db_manager.get_user_actions_by_ticket_id(int(ticket_id))
                    
                    if not user_actions:
                        return f"티켓 ID {ticket_id}에 대한 사용자 액션이 없습니다."
                    
                    result = f"📋 티켓 ID {ticket_id}의 사용자 액션:\n\n"
                    for i, action in enumerate(user_actions, 1):
                        result += f"{i}. {action.get('action_type', 'N/A')}\n"
                        result += f"   이전 값: {action.get('old_value', 'N/A')}\n"
                        result += f"   새 값: {action.get('new_value', 'N/A')}\n"
                        result += f"   시간: {action.get('created_at', 'N/A')}\n\n"
                    
                    return result
                else:
                    # 전체 사용자 액션 조회
                    user_actions = db_manager.get_all_user_actions()
                    
                    if not user_actions:
                        return "사용자 액션이 없습니다."
                    
                    result = f"📋 전체 사용자 액션 ({len(user_actions)}개):\n\n"
                    for i, action in enumerate(user_actions[:10], 1):  # 최대 10개만 표시
                        result += f"{i}. {action.get('action_type', 'N/A')}\n"
                        result += f"   티켓 ID: {action.get('ticket_id', 'N/A')}\n"
                        result += f"   이전 값: {action.get('old_value', 'N/A')}\n"
                        result += f"   새 값: {action.get('new_value', 'N/A')}\n"
                        result += f"   시간: {action.get('created_at', 'N/A')}\n\n"
                    
                    if len(user_actions) > 10:
                        result += f"... 외 {len(user_actions) - 10}개 더\n"
                    
                    return result
                
            except Exception as e:
                logging.error(f"❌ 메모리 조회 실패: {str(e)}")
                return f"메모리 조회 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="memory_tool",
            description="과거 사용자 피드백과 메모리를 조회합니다. 특정 티켓의 사용자 액션이나 전체 사용자 액션을 조회할 수 있습니다. 티켓 조회 요청도 처리합니다.",
            func=memory_tool
        )
    
    def _create_agent(self):
        """에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """에이전트 실행"""
        try:
            logging.info(f"🎫 {self.name} 실행: {query}")
            
            # 컨텍스트가 있으면 쿼리에 추가
            if context:
                enhanced_query = f"{query}\n\n컨텍스트 정보: {context}"
            else:
                enhanced_query = query
                
            result = self.agent_executor.invoke({"input": enhanced_query})
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"


# 에이전트 인스턴스 생성 함수
def create_viewing_agent() -> ViewingAgent:
    """ViewingAgent 인스턴스 생성"""
    return ViewingAgent()

def create_analysis_agent() -> AnalysisAgent:
    """AnalysisAgent 인스턴스 생성"""
    return AnalysisAgent()

def create_ticketing_agent() -> TicketingAgent:
    """TicketingAgent 인스턴스 생성"""
    return TicketingAgent()

if __name__ == "__main__":
    # 테스트
    viewing_agent = create_viewing_agent()
    result = viewing_agent.execute("안 읽은 메일 3개 보여주세요")
    print("ViewingAgent 결과:", result)
