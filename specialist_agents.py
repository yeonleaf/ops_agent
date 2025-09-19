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
from langchain.schema import SystemMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ViewingAgent:
    """이메일 조회 전문가 에이전트"""
    
    def __init__(self, llm_client):
        self.name = "ViewingAgent"
        self.llm = llm_client
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 이메일 조회 전문가입니다. 

## 역할
- 사용자의 요청에 따라 이메일을 찾아서 목록을 보여주는 역할만 수행합니다
- 이메일 필터링, 검색, 정렬 등의 조회 작업에 특화되어 있습니다
- 복잡한 분석이나 티켓 생성은 다른 전문가에게 위임합니다

## 사용 가능한 도구
- view_emails_tool: 이메일을 조회하고 목록을 반환합니다

## 중요: 발신자 정보 해석 주의사항
- 이메일 조회 결과에서 "발신자" 필드에 표시된 정보를 정확히 그대로 사용하세요
- 실제 발신자 이메일 주소나 이름을 확인하고, 추측하지 마세요
- 예: 발신자가 "조주연 <juyeonjo633@gmail.com>"로 표시되면, "조주연" 또는 "juyeonjo633@gmail.com"에서 보낸 것으로 정확히 표시하세요
- Microsoft, Google 등의 회사명으로 추측하지 말고, 실제 발신자 정보만 사용하세요

## 응답 형식
- 조회된 이메일 목록을 명확하고 읽기 쉽게 정리하여 제공합니다
- 각 이메일의 제목, 발신자, 날짜, 읽음 상태 등을 포함합니다
- 발신자 정보는 도구에서 반환된 정확한 정보를 그대로 사용하세요
- 한국어로 친근하고 전문적인 톤으로 응답합니다"""

        # 도구 정의
        self.tools = [self._create_view_emails_tool()]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_view_emails_tool(self) -> Tool:
        """이메일 조회 도구 생성"""
        # ViewingAgent 인스턴스에 대한 참조 저장
        viewing_agent_instance = self

        def view_emails_tool(query: str, cookies: str = "") -> str:
            """
            이메일을 조회하고 목록을 반환합니다.
            
            Args:
                query: 사용자 쿼리 (예: "안 읽은 메일 3개", "gmail에서 읽지 않은 메일")
                cookies: OAuth 토큰이 포함된 쿠키 문자열 (우선 사용)
            
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
                
                # 1. 먼저 전달받은 토큰 확인 (우선순위)
                access_token = None
                
                if cookies and provider_name == "gmail":
                    print("🍪 전달받은 토큰에서 Gmail access_token 추출 시도")
                    try:
                        # 쿠키에서 gmail_access_token 추출
                        for cookie in cookies.split(';'):
                            if 'gmail_access_token=' in cookie:
                                access_token = cookie.split('gmail_access_token=')[1].strip()
                                print(f"🍪 전달받은 토큰에서 추출된 access_token: {access_token[:20]}...")
                                break
                    except Exception as e:
                        print(f"🍪 전달받은 토큰에서 추출 실패: {e}")
                
                # 2. 전달받은 토큰이 없으면 DB에서 확인
                if not access_token and provider_name == "gmail":
                    print("🍪 전달받은 토큰이 없음 - DB에서 Gmail 연동 정보 확인")
                    try:
                        from auth_client import auth_client
                        from gmail_provider import refresh_gmail_token
                        
                        # 사용자가 로그인되어 있는지 확인
                        if auth_client.is_logged_in():
                            print("🍪 사용자가 로그인됨 - DB에서 Google 연동 정보 확인")
                            result = auth_client.get_google_integration()
                            if result.get("success") and result.get("has_token"):
                                print("🍪 DB에 Google 토큰이 저장되어 있음 - refresh_token으로 access_token 재발급 시도")
                                
                                # refresh_token으로 access_token 재발급 시도
                                refresh_result = refresh_gmail_token()
                                if refresh_result.get("success"):
                                    access_token = refresh_result.get("access_token")
                                    print(f"🍪 DB에서 재발급된 access_token: {access_token[:20]}...")
                                else:
                                    print("🍪 DB 토큰으로 access_token 재발급 실패")
                            else:
                                print("🍪 DB에 Google 토큰이 없음")
                        else:
                            print("🍪 사용자가 로그인되지 않음")
                    except Exception as e:
                        print(f"🍪 DB 토큰 확인 실패: {e}")
                
                if not access_token:
                    print("🍪 view_emails_tool에서 토큰을 찾을 수 없음")

                # 🚀 LLM 기반 쿼리 파싱 사용 (NCMS, 복잡한 검색 지원)
                # 인증 전에 먼저 쿼리 파싱을 수행하여 동적 쿼리 테스트 가능
                try:
                    print(f"🧠 ViewingAgent: LLM 기반 쿼리 파싱 시도 - '{query}'")

                    # 저장된 ViewingAgent 인스턴스 참조 사용
                    parsed_params = viewing_agent_instance._parse_query_with_llm_internal(query)

                    if parsed_params:
                        # LLM이 'filters' 키 없이 바로 필터 정보를 반환한 경우도 처리
                        if 'filters' in parsed_params:
                            filters = parsed_params['filters']
                        else:
                            filters = parsed_params

                        # None 값들을 제거하여 깔끔하게 정리
                        filters = {k: v for k, v in filters.items() if v is not None}
                        print(f"✅ LLM 파싱 성공: {filters}")
                    else:
                        print("⚠️ LLM 파싱 실패 - 규칙 기반으로 폴백")
                        filters = viewing_agent_instance._parse_query_with_rules(query)

                except Exception as e:
                    print(f"⚠️ LLM 파싱 실패: {e} - 규칙 기반으로 폴백")
                    # 기본 규칙 기반 파싱 사용
                    filters = viewing_agent_instance._parse_query_with_rules(query)

                # OAuth 인증이 필요한 경우 확인 (LLM 파싱 후 실행)
                try:
                    # 테스트용으로 이메일 서비스 초기화 시도
                    from unified_email_service import UnifiedEmailService
                    test_service = UnifiedEmailService(provider_name=provider_name, access_token=access_token)
                except ValueError as e:
                    # OAuth 인증이 필요한 경우
                    oauth_links = {
                        "gmail": "http://localhost:8000/auth/login/gmail",
                        "graph": "http://localhost:8000/auth/login/microsoft"
                    }

                    auth_link = oauth_links.get(provider_name, oauth_links["gmail"])

                    return f"""
🔐 **이메일 계정 인증이 필요합니다**

{provider_name.upper()} 계정에 접근하려면 OAuth2 인증을 완료해야 합니다.

**🧠 동적 쿼리 파싱 결과**: {filters}

**인증 방법:**
1. 아래 링크를 클릭하여 인증을 진행하세요
2. Google/Microsoft 계정으로 로그인
3. 권한 승인 후 자동으로 돌아옵니다

**🔗 인증 링크:** {auth_link}

**또는 브라우저에서 직접 접속:**
- Gmail: http://localhost:8000/auth/login/gmail
- Outlook: http://localhost:8000/auth/login/microsoft

인증이 완료되면 다시 이메일 조회를 요청해주세요! 📧
                    """

                # UnifiedEmailService를 사용하여 이메일 가져오기
                service = UnifiedEmailService(provider_name=provider_name, access_token=access_token)
                emails = service.fetch_emails(filters)
                
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

    def _parse_query_with_rules(self, query: str) -> dict:
        """규칙 기반 쿼리 파싱 (폴백용)"""
        filters = {}
        query_lower = query.lower()

        # 읽음 상태 필터
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

        # NCMS 키워드 검색 지원 추가
        if "ncms" in query_lower:
            filters['subject'] = 'NCMS'
        elif "업무" in query_lower:
            filters['subject'] = '업무'

        return filters

    def _parse_query_with_llm_internal(self, query: str) -> dict:
        """내부 LLM 기반 쿼리 파싱 (import 문제 회피용)"""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            system_prompt = """당신은 Gmail API 쿼리 생성 전문가입니다.
사용자의 자연어 요청을 Gmail API 파라미터로 변환해주세요.

특별 키워드 처리:
- "최근 일주일" → date_after: 7일 전 날짜
- "NCMS" → subject: "NCMS"
- "업무" → subject: "업무"
- "안 읽은" → is_read: false
- "N개" → limit: N

응답은 정확히 다음 JSON 형식으로만 해주세요:
{
    "filters": {
        "is_read": true/false,
        "limit": 숫자,
        "subject": "검색할 제목",
        "date_after": "YYYY-MM-DD"
    }
}"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"쿼리: {query}")
            ]

            response = self.llm.invoke(messages)

            # JSON 파싱
            import json
            import re

            # JSON 블록 추출
            content = response.content
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                return parsed_data
            else:
                print(f"⚠️ LLM 응답에서 JSON을 찾을 수 없음: {content[:100]}")
                return {}

        except Exception as e:
            print(f"⚠️ _parse_query_with_llm_internal 실패: {e}")
            return {}

    def _create_agent(self):
        """에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None, cookies: str = "") -> str:
        """에이전트 실행"""
        try:
            logging.info(f"🔍 {self.name} 실행: {query}")
            
            # 컨텍스트가 있으면 쿼리에 추가
            if context:
                enhanced_query = f"{query}\n\n컨텍스트 정보: {context}"
            else:
                enhanced_query = query
            
            # 쿠키를 도구에 전달하기 위해 컨텍스트에 추가
            if cookies:
                enhanced_query += f"\n\n쿠키 정보: {cookies}"
            
            # 쿠키가 있으면 view_emails_tool을 직접 호출
            if cookies and "안 읽은 메일" in query:
                print(f"🍪 ViewingAgent에서 직접 view_emails_tool 호출: {cookies[:100]}...")
                try:
                    # view_emails_tool을 직접 호출
                    view_emails_tool_func = None
                    for tool in self.tools:
                        if tool.name == "view_emails_tool":
                            view_emails_tool_func = tool.func
                            break
                    
                    if view_emails_tool_func:
                        result = view_emails_tool_func(query, cookies)
                        return result
                    else:
                        print("🍪 view_emails_tool을 찾을 수 없음")
                except Exception as e:
                    print(f"🍪 직접 호출 실패: {e}")
            
            # 도구 호출 시 쿠키 전달을 위한 컨텍스트 설정
            invoke_context = {"input": enhanced_query}
            if cookies:
                invoke_context["cookies"] = cookies
                
            result = self.agent_executor.invoke(invoke_context)
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"


class AnalysisAgent:
    """이메일 분석 전문가 에이전트"""
    
    def __init__(self, llm_client):
        self.name = "AnalysisAgent"
        self.llm = llm_client
        
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
        def classify_emails_tool(emails_data: str = "") -> str:
            """
            ViewingAgent로부터 받은 이메일 데이터를 분석하고 분류합니다.
            
            Args:
                emails_data: ViewingAgent로부터 받은 이메일 데이터 (JSON 문자열 또는 텍스트)
            
            Returns:
                이메일 분석 및 분류 결과
            """
            try:
                import json
                
                # 이메일 데이터 파싱
                if not emails_data:
                    return "분석할 이메일 데이터가 제공되지 않았습니다. ViewingAgent로부터 이메일 데이터를 받아야 합니다."
                
                # JSON 형태인지 확인
                try:
                    if isinstance(emails_data, str) and emails_data.strip().startswith('['):
                        emails_list = json.loads(emails_data)
                    else:
                        # 텍스트 형태인 경우 파싱 시도
                        emails_list = [emails_data]
                except (json.JSONDecodeError, TypeError):
                    # JSON이 아닌 경우 문자열로 처리
                    emails_list = [emails_data]
                
                if not emails_list:
                    return "분석할 이메일 데이터가 없습니다."
                
                # LLM을 사용하여 이메일 분석
                analysis_prompt = f"""
다음 {len(emails_list)}개의 이메일들을 분석하여 업무 관련성을 판단하고 분류해주세요:

이메일 데이터:
{emails_list}

각 이메일에 대해 다음을 분석해주세요:
1. 업무 관련성 (업무용/개인용)
2. 우선순위 (High/Medium/Low)  
3. 핵심 내용 요약
4. 필요한 조치사항

분석 결과를 다음과 같은 형식으로 정리해주세요:

📧 이메일 분석 결과 ({len(emails_list)}개)

**업무용 이메일:**
- [이메일 제목]: [우선순위] - [핵심 내용 요약]

**개인용 이메일:**
- [이메일 제목]: [핵심 내용 요약]

**권장사항:**
- 업무용 이메일 중 티켓 생성이 필요한 항목들을 명시해주세요."""

                # LLM 호출
                response = self.llm.invoke([HumanMessage(content=analysis_prompt)])
                return response.content
                
            except Exception as e:
                logging.error(f"❌ 이메일 분석 실패: {str(e)}")
                return f"이메일 분석 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="classify_emails_tool",
            description="ViewingAgent로부터 받은 이메일 데이터를 분석하여 업무용과 개인용으로 분류하고, 업무 관련성, 우선순위, 핵심 내용을 분석합니다.",
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
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None, cookies: str = "") -> str:
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
    
    def __init__(self, llm_client):
        self.name = "TicketingAgent"
        self.llm = llm_client
        self.ticket_creation_mode = False  # 티켓 생성 전용 모드 플래그
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 Jira 티켓 처리 전문가입니다.

## 역할
- 이메일을 분석하여 티켓을 생성하고, 과거의 사용자 피드백(메모리)을 참고하여 최적의 판단을 내립니다
- 복잡한 워크플로우와 메모리 기반 학습을 통한 티켓 처리를 전담합니다
- 기존 티켓 조회, 수정, 상태 변경 등의 티켓 관리 작업을 수행합니다
- 가장 복잡하고 중요한 업무를 담당합니다

## 사용 가능한 도구
- read_emails_tool: ViewingAgent를 통해 메일을 읽고 목록을 조회합니다 (메일 조회가 아직 안 된 경우에만 사용)
- process_tickets_tool: 이메일을 분석하여 티켓을 생성하고 처리합니다 (주요 도구)
- memory_tool: 티켓 조회 및 과거 사용자 피드백과 메모리를 조회합니다
- correction_tool: 업무용이 아니라고 판단된 메일을 정정하여 티켓을 생성합니다

## 중요: 중복 메일 조회 방지
- RouterAgent에서 "최근에 수신된 이메일 N건을 티켓으로 생성" 같은 요청이 오면, 이미 ViewingAgent가 메일을 조회했다는 뜻입니다
- 이 경우 read_emails_tool을 사용하지 말고 바로 process_tickets_tool을 사용하여 티켓을 생성하세요
- 불필요한 메일 중복 조회로 인한 성능 저하와 잘못된 결과를 방지합니다

## 중요: 티켓 생성 워크플로우
- 티켓 생성 요청("안읽은 메일을 바탕으로 티켓을 생성해줘", "메일을 티켓으로 만들어줘") 처리 시:
  1. RouterAgent가 이미 ViewingAgent를 통해 메일을 조회했다면, read_emails_tool을 사용하지 말고 바로 process_tickets_tool을 사용해 티켓 생성
  2. 만약 메일 조회가 필요한 경우에만 read_emails_tool을 사용
- 중복 메일 조회를 방지하여 불필요한 API 호출을 줄입니다

## 중요: 티켓 조회 시 주의사항
- memory_tool에서 "📋 전체 티켓 목록"으로 시작하는 결과가 나오면, 이는 실제 데이터베이스에 저장된 티켓 목록입니다
- 이 경우 "생성된 티켓이 없습니다"라고 답하지 말고, 실제 티켓 목록을 사용자에게 보여주세요
- 사용자 액션 기록만 보고 티켓이 없다고 판단하지 마세요

## 응답 형식
- 티켓 생성/처리 결과를 상세하고 구조화된 형태로 제공합니다
- 메모리 기반 판단 근거를 포함합니다
- 한국어로 전문적이고 신뢰할 수 있는 톤으로 응답합니다"""

        # 도구 정의 (쿠키 저장을 위한 인스턴스 변수)
        self.current_cookies = ""
        self.viewing_agent = None  # ViewingAgent 참조를 위한 변수
        self.tools = self._get_tools()

        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def set_viewing_agent(self, viewing_agent):
        """ViewingAgent 참조 설정"""
        self.viewing_agent = viewing_agent

    def _get_tools(self):
        """모드에 따라 도구 목록을 동적으로 반환"""
        tools = [self._create_process_tickets_tool(), self._create_memory_tool(), self._create_correction_tool()]

        # 티켓 생성 전용 모드가 아닐 때만 read_emails_tool 포함
        if not self.ticket_creation_mode:
            tools.insert(0, self._create_read_emails_tool())

        return tools

    def set_ticket_creation_mode(self, enabled: bool):
        """티켓 생성 전용 모드 설정"""
        self.ticket_creation_mode = enabled
        # 도구 목록 재구성
        self.tools = self._get_tools()
        # 에이전트 재생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_read_emails_tool(self) -> Tool:
        """메일 읽기 도구 생성 (ViewingAgent 위임)"""
        def read_emails_tool(query: str) -> str:
            """
            ViewingAgent를 통해 메일을 읽고 목록을 반환합니다.
            
            Args:
                query: 메일 조회 쿼리 (예: "안 읽은 메일", "gmail 메일 조회")
            
            Returns:
                메일 목록 정보
            """
            try:
                if not self.viewing_agent:
                    return "ViewingAgent가 설정되지 않았습니다. 메일을 직접 조회할 수 없습니다."
                
                print(f"🔄 TicketingAgent가 ViewingAgent에게 메일 읽기 요청: {query}")
                
                # ViewingAgent를 통해 메일 조회
                result = self.viewing_agent.execute(query, cookies=self.current_cookies)
                
                print(f"✅ ViewingAgent로부터 메일 데이터 수신 완료")
                return result
                
            except Exception as e:
                logging.error(f"❌ ViewingAgent를 통한 메일 읽기 실패: {str(e)}")
                return f"메일 읽기 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="read_emails_tool",
            description="ViewingAgent를 통해 메일을 읽고 목록을 조회합니다. 주의: RouterAgent에서 이미 메일을 조회한 경우에는 사용하지 마세요. 독립적인 메일 조회가 필요한 경우에만 사용합니다.",
            func=read_emails_tool
        )
    
    def _create_process_tickets_tool(self) -> Tool:
        """티켓 처리 도구 생성"""
        def process_tickets_tool(query: str) -> str:
            print(f"🎫 process_tickets_tool 호출됨! query: {query[:100]}")
            """
            이메일을 분석하여 티켓을 생성하고 처리합니다.
            
            Args:
                query: 사용자 쿼리 (예: "안 읽은 메일을 티켓으로 만들어줘", "gmail에서 티켓 생성")
            
            Returns:
                티켓 생성 및 처리 결과
            """
            try:
                # 🚨 메일 중복 조회 방지: ViewingAgent가 이미 조회한 메일 데이터 재사용
                print("🔍 이미 조회된 메일 데이터를 기반으로 티켓 생성 시작")

                # TODO: ViewingAgent 조회 결과를 직접 사용하는 로직으로 교체 필요
                # 현재는 임시로 기존 로직 사용하되 캐시 활용 강화
                from unified_email_service import process_emails_with_ticket_logic

                # 쿼리에서 provider_name 추출
                provider_name = "gmail"  # 기본값
                query_lower = query.lower()
                if "gmail" in query_lower:
                    provider_name = "gmail"
                elif "outlook" in query_lower or "graph" in query_lower:
                    provider_name = "graph"

                # ViewingAgent가 이미 조회했음을 알리는 플래그 설정
                print("⚠️ 주의: ViewingAgent가 이미 메일을 조회했으므로 중복 조회를 최소화합니다")

                # mem0_memory를 전역에서 가져오기 시도
                mem0_memory = None
                try:
                    import sys
                    if hasattr(sys.modules['__main__'], 'mem0_memory'):
                        mem0_memory = sys.modules['__main__'].mem0_memory
                except:
                    pass
                
                # 토큰 추출 (인스턴스 변수에서) - ViewingAgent와 동일한 방식 적용
                access_token = None
                cookies = self.current_cookies  # 인스턴스 변수에서 쿠키 가져오기
                print(f"🍪 TicketAgent process_tickets_tool: current_cookies = {'있음' if cookies else '없음'}")
                if cookies:
                    print(f"🍪 TicketAgent process_tickets_tool: cookies 내용 = {cookies[:100]}...")
                
                if cookies and provider_name == "gmail":
                    print("🍪 TicketAgent: 전달받은 토큰에서 Gmail access_token 추출 시도")
                    try:
                        # 쿠키에서 gmail_access_token 추출
                        for cookie in cookies.split(';'):
                            if 'gmail_access_token=' in cookie:
                                access_token = cookie.split('gmail_access_token=')[1].strip()
                                print(f"🍪 TicketAgent: 전달받은 토큰에서 추출된 access_token: {access_token[:20]}...")
                                break
                        
                        if not access_token:
                            print("🍪 TicketAgent: 전달받은 토큰에 gmail_access_token이 없음")
                    except Exception as e:
                        print(f"🍪 TicketAgent: 토큰 추출 중 오류: {e}")
                
                # 토큰이 없으면 refresh token으로 새로 발급
                if not access_token:
                    print(f"🔄 TicketAgent: {provider_name} access_token이 없어서 새로 발급 시도")
                    try:
                        from gmail_provider import get_gmail_access_token_from_refresh_token
                        access_token = get_gmail_access_token_from_refresh_token()
                        if access_token:
                            print(f"🔄 TicketAgent: refresh token으로 새 access_token 발급 성공: {access_token[:20]}...")
                        else:
                            print("🔄 TicketAgent: refresh token으로 access_token 발급 실패")
                    except Exception as e:
                        print(f"🔄 TicketAgent: refresh token 처리 중 오류: {e}")
                
                print(f"🍪 TicketAgent 최종 토큰 상태: {'성공' if access_token else '실패'}")
                
                print(f"🔍 SpecialistAgent: process_emails_with_ticket_logic 호출 시작")
                result = process_emails_with_ticket_logic(provider_name, query, mem0_memory, access_token)
                print(f"🔍 SpecialistAgent: process_emails_with_ticket_logic 결과: {type(result)}, display_mode: {result.get('display_mode')}")
                print(f"🔍 SpecialistAgent: non_work_emails 개수: {len(result.get('non_work_emails', []))}")
                
                if result.get('display_mode') == 'tickets':
                    tickets = result.get('tickets', [])
                    non_work_emails = result.get('non_work_emails', [])
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
                    
                    # 업무용이 아니라고 판단된 메일들 추가
                    if non_work_emails:
                        response += f"\n🔍 업무용이 아니라고 판단된 메일 ({len(non_work_emails)}개):\n"
                        response += "※ confidence가 높은 메일들입니다. 티켓 생성이 필요하다면 정정 요청을 해주세요.\n\n"
                        
                        for i, email in enumerate(non_work_emails[:3], 1):
                            response += f"{i}. {email.get('subject', '제목 없음')}\n"
                            response += f"   발신자: {email.get('sender', 'N/A')}\n"
                            response += f"   신뢰도: {email.get('confidence', 0):.2f}\n"
                            response += f"   판단 근거: {email.get('reason', 'N/A')[:100]}...\n\n"
                        
                        if len(non_work_emails) > 3:
                            response += f"... 외 {len(non_work_emails) - 3}개 더\n"
                    
                    # Streamlit 세션에 non_work_emails 저장 (전역 접근)
                    import streamlit as st
                    if hasattr(st, 'session_state'):
                        st.session_state.non_work_emails = non_work_emails
                        st.session_state.has_non_work_emails = len(non_work_emails) > 0
                        print(f"✅ SpecialistAgent에서 non_work_emails 세션에 저장: {len(non_work_emails)}개")

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
        def memory_tool(query: str = "", ticket_id: str = None) -> str:
            """
            과거 사용자 피드백과 메모리를 조회합니다.
            
            Args:
                ticket_id: 특정 티켓 ID (선택사항)
                query: 검색 쿼리
            
            Returns:
                메모리 조회 결과
            """
            try:
                # 티켓 조회 요청인지 확인 (더 넓은 키워드 매칭)
                if query and any(keyword in query.lower() for keyword in [
                    "티켓 조회", "전체 티켓", "티켓 목록", "생성된 티켓", "티켓", "조회", "목록", "전체"
                ]):
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
                        result += f"{i}. {action.action_type or 'N/A'}\n"
                        result += f"   이전 값: {action.old_value or 'N/A'}\n"
                        result += f"   새 값: {action.new_value or 'N/A'}\n"
                        result += f"   시간: {action.created_at or 'N/A'}\n\n"
                    
                    return result
                else:
                    # 전체 사용자 액션 조회
                    user_actions = db_manager.get_all_user_actions()
                    
                    if not user_actions:
                        return "사용자 액션이 없습니다."
                    
                    result = f"📋 전체 사용자 액션 ({len(user_actions)}개):\n\n"
                    for i, action in enumerate(user_actions[:10], 1):  # 최대 10개만 표시
                        result += f"{i}. {action.action_type or 'N/A'}\n"
                        result += f"   티켓 ID: {action.ticket_id or 'N/A'}\n"
                        result += f"   이전 값: {action.old_value or 'N/A'}\n"
                        result += f"   새 값: {action.new_value or 'N/A'}\n"
                        result += f"   시간: {action.created_at or 'N/A'}\n\n"
                    
                    if len(user_actions) > 10:
                        result += f"... 외 {len(user_actions) - 10}개 더\n"
                    
                    return result
                
            except Exception as e:
                logging.error(f"❌ 메모리 조회 실패: {str(e)}")
                return f"메모리 조회 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="memory_tool",
            description="티켓 조회 및 사용자 액션 기록을 조회합니다. query 파라미터에 '티켓 조회', '전체 티켓', '생성된 티켓' 등을 입력하면 실제 데이터베이스에서 티켓 목록을 반환합니다. ticket_id 파라미터에 특정 티켓 ID를 입력하면 해당 티켓의 사용자 액션을 조회합니다.",
            func=memory_tool
        )
    
    def _create_correction_tool(self) -> Tool:
        """정정 도구 생성"""
        def correction_tool(email_id: str, email_subject: str, email_sender: str, email_body: str) -> str:
            """
            업무용이 아니라고 판단된 메일을 정정하여 티켓을 생성합니다.
            
            Args:
                email_id: 이메일 ID
                email_subject: 이메일 제목
                email_sender: 이메일 발신자
                email_body: 이메일 본문
            
            Returns:
                정정 결과 및 티켓 생성 정보
            """
            try:
                from unified_email_service import create_ticket_from_single_email
                
                # 이메일 데이터를 티켓 생성 함수에 전달할 형태로 변환
                email_data = {
                    'id': email_id,
                    'subject': email_subject,
                    'sender': email_sender,
                    'body': email_body,
                    'force_create': True  # 정정 요청이므로 강제 생성
                }
                
                # unified_email_service의 create_ticket_from_single_email 사용
                # force_create=True로 설정하여 분류기 우회
                result = create_ticket_from_single_email(
                    email_data=email_data,
                    force_create=True,
                    correction_reason="사용자 요청으로 정정 생성"
                )
                
                if result.get('success'):
                    ticket_id = result.get('ticket_id')
                    return f"✅ 정정 완료!\n\n📋 생성된 티켓:\n- ID: {ticket_id}\n- 제목: {email_subject}\n- 상태: pending\n- 우선순위: Medium\n- 레이블: 정정요청, 사용자판단\n\n💾 정정 행동이 학습 데이터로 저장되었습니다."
                else:
                    return f"❌ 정정 실패: {result.get('error', '알 수 없는 오류')}"
                
            except Exception as e:
                logging.error(f"❌ 정정 실패: {str(e)}")
                return f"정정 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="correction_tool",
            description="업무용이 아니라고 판단된 메일을 정정하여 티켓을 생성합니다. 사용자가 AI의 판단을 수정하고 싶을 때 사용합니다.",
            func=correction_tool
        )
    
    def _create_agent(self):
        """에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, context: Optional[Dict[str, Any]] = None, cookies: str = "") -> str:
        """에이전트 실행"""
        try:
            logging.info(f"🎫 {self.name} 실행: {query}")
            print(f"🍪 TicketingAgent.execute에서 전달받은 cookies: {'있음' if cookies else '없음'}")
            
            # 컨텍스트가 있으면 쿼리에 추가
            if context:
                enhanced_query = f"{query}\n\n컨텍스트 정보: {context}"
            else:
                enhanced_query = query
            
            # 쿠키 정보를 인스턴스 변수에 저장하여 도구에서 접근 가능하게 함
            if cookies:
                self.current_cookies = cookies
                print(f"🍪 TicketingAgent: 인스턴스 변수에 쿠키 저장됨")
            else:
                self.current_cookies = ""
                
            result = self.agent_executor.invoke({"input": enhanced_query})
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"


# 에이전트 인스턴스 생성 함수
def create_viewing_agent(llm_client) -> ViewingAgent:
    """ViewingAgent 인스턴스 생성"""
    return ViewingAgent(llm_client)

def create_analysis_agent(llm_client) -> AnalysisAgent:
    """AnalysisAgent 인스턴스 생성"""
    return AnalysisAgent(llm_client)

def create_ticketing_agent(llm_client) -> TicketingAgent:
    """TicketingAgent 인스턴스 생성"""
    return TicketingAgent(llm_client)

if __name__ == "__main__":
    # 테스트용 LLM 클라이언트 생성
    test_llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0.1
    )
    
    # 테스트
    viewing_agent = create_viewing_agent(test_llm)
    result = viewing_agent.execute("안 읽은 메일 3개 보여주세요")
    print("ViewingAgent 결과:", result)
