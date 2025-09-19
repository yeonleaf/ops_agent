#!/usr/bin/env python3
"""
라우터 에이전트 (Router Agent)
전문가 에이전트들을 도구로 변환하고 라우팅하는 최상위 에이전트
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# LangChain imports
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 전문가 에이전트 import
from specialist_agents import create_viewing_agent, create_analysis_agent, create_ticketing_agent

# OAuth 인증 에이전트 import
from oauth_auth_agent import get_oauth_agent

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RouterAgent:
    """라우터 에이전트 - 전문가 에이전트들을 라우팅하는 최상위 에이전트"""
    
    def __init__(self, llm_client):
        self.name = "RouterAgent"
        self.llm = llm_client
        self.oauth_agent = get_oauth_agent()
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 유능한 프로젝트 매니저입니다.

## 역할
사용자의 요청을 분석하여, 가장 적합한 전문가에게 작업을 위임하는 역할을 합니다.

## 사용 가능한 전문가들

### 1. ViewingAgent (이메일 조회 전문가)
- **역할**: 이메일을 필터링하고 목록을 보여주는 단순 조회 작업만 담당
- **특화 분야**: 이메일 검색, 필터링, 정렬, 목록 조회
- **사용 시기**: "메일 보여줘", "안 읽은 메일 찾아줘", "특정 발신자 메일 조회" 등

### 2. AnalysisAgent (데이터 분석 전문가)
- **역할**: 이메일 내용을 분석하고 '업무/개인'으로 분류하는 등, 데이터 분석 작업을 담당
- **특화 분야**: 이메일 분류, 우선순위 분석, 내용 요약, 업무 관련성 판단
- **사용 시기**: "이메일 분석해줘", "업무용 메일만 분류해줘", "우선순위 정해줘" 등

### 3. TicketingAgent (티켓 처리 전문가)
- **역할**: Jira 티켓 생성, 기존 티켓 조회, 메모리 활용 등 가장 복잡한 워크플로우를 전담
- **특화 분야**: 티켓 생성, 메모리 기반 학습, 복잡한 워크플로우 처리
- **사용 시기**: "티켓 만들어줘", "안 읽은 메일 처리해줘", "메모리 확인해줘" 등

## 복합 워크플로우 처리
복잡한 요청의 경우 여러 전문가를 순차적으로 활용할 수 있습니다:

1. **"새로운 메일들을 업무용과 개인용으로 분류하고, 업무용만 티켓으로 만들어줘"**
   - 1단계: ViewingAgent로 새로운 메일 조회
   - 2단계: AnalysisAgent로 조회된 메일을 업무용/개인용으로 분류
   - 3단계: TicketingAgent로 분류된 업무용 메일만 티켓으로 생성

2. **에이전트 간 데이터 전달**
   - ViewingAgent의 결과를 AnalysisAgent에게 전달
   - AnalysisAgent의 분류 결과를 TicketingAgent에게 전달

## OAuth 인증 도구들

### 4. oauth_check (인증 상태 확인)
- **역할**: 이메일 서비스 사용 전 인증 상태를 확인
- **사용 시기**: 이메일 관련 작업을 시작하기 전에 항상 먼저 확인

### 5. oauth_login (OAuth 로그인)
- **역할**: OAuth 인증이 필요한 경우 로그인 URL을 생성
- **사용 시기**: 인증이 필요하다고 확인된 경우

### 6. oauth_callback (OAuth 콜백 처리)
- **역할**: OAuth 인증 완료 후 토큰을 받아서 저장
- **사용 시기**: 사용자가 OAuth 인증을 완료한 후

### 7. oauth_refresh (토큰 재발급)
- **역할**: 만료된 토큰을 새로 발급받기
- **사용 시기**: 토큰이 만료되었을 때

## 라우팅 규칙
1. **이메일 관련 요청** → 먼저 oauth_check 실행 → 인증 필요시 oauth_login → 인증 완료 후 전문가 도구 사용
2. **단순 조회 요청** → ViewingAgent
3. **분석/분류 요청** → AnalysisAgent  
4. **티켓 생성/처리 요청** → TicketingAgent
5. **복합 요청** → 워크플로우에 따라 여러 전문가를 순차적으로 활용

## 이메일 관련 키워드 감지
- "메일", "이메일", "mail", "email"
- "안 읽은", "읽지 않은", "unread"
- "받은편지함", "inbox"
- "보낸편지함", "sent"
- "메일 조회", "이메일 조회"

## 중요 규칙
- **이메일 관련 작업을 시작하기 전에 반드시 oauth_check를 먼저 실행하세요**
- 인증이 필요한 경우 oauth_login을 사용하여 로그인 URL을 제공하세요
- 사용자가 OAuth 인증을 완료한 경우 oauth_callback을 사용하여 토큰을 저장하세요

## 응답 형식
- 선택한 전문가와 그 이유를 명확히 설명합니다
- 복합 워크플로우의 경우 각 단계별 진행 상황을 안내합니다
- 전문가의 작업 결과를 사용자에게 전달합니다
- 한국어로 친근하고 전문적인 톤으로 응답합니다"""

        # 전문가 에이전트 인스턴스 생성
        self.viewing_agent = create_viewing_agent(llm_client)
        self.analysis_agent = create_analysis_agent(llm_client)
        self.ticketing_agent = create_ticketing_agent(llm_client)
        
        # TicketingAgent에 ViewingAgent 참조 설정
        self.ticketing_agent.set_viewing_agent(self.viewing_agent)
        
        # 전문가 에이전트들을 도구로 변환
        self.tools = [
            self._create_viewing_agent_tool(),
            self._create_analysis_agent_tool(),
            self._create_ticketing_agent_tool(),
            self._create_oauth_check_tool(),
            self._create_oauth_login_tool(),
            self._create_oauth_callback_tool(),
            self._create_oauth_refresh_tool()
        ]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_viewing_agent_tool(self) -> Tool:
        """ViewingAgent를 도구로 변환"""
        def viewing_agent_tool(query: str) -> str:
            """
            이메일 조회 전문가에게 작업을 위임합니다.
            
            이 도구는 다음과 같은 작업에 특화되어 있습니다:
            - 이메일 검색 및 필터링
            - 읽음/안 읽음 상태별 조회
            - 발신자, 제목, 날짜별 필터링
            - 이메일 목록 정렬 및 표시
            
            Args:
                query: 이메일 조회 관련 사용자 요청
            
            Returns:
                조회된 이메일 목록 및 상세 정보
            """
            try:
                logging.info(f"🔍 ViewingAgent에게 작업 위임: {query}")
                # 현재 컨텍스트에서 쿠키 정보 가져오기
                cookies = getattr(self, '_current_context', {}).get('cookies', '')
                print(f"🍪 RouterAgent에서 ViewingAgent로 쿠키 전달: {'있음' if cookies else '없음'}")
                # 쿠키를 ViewingAgent에 전달
                result = self.viewing_agent.execute(query, cookies=cookies)
                return f"📧 이메일 조회 전문가 결과:\n{result}"
            except Exception as e:
                logging.error(f"❌ ViewingAgent 실행 실패: {str(e)}")
                return f"이메일 조회 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="viewing_agent_tool",
            description="이메일 조회 전문가에게 작업을 위임합니다. 이메일 검색, 필터링, 목록 조회 등 단순한 조회 작업에 특화되어 있습니다. '메일 보여줘', '안 읽은 메일 찾아줘', '특정 발신자 메일 조회' 등의 요청에 사용합니다.",
            func=viewing_agent_tool
        )
    
    def _create_analysis_agent_tool(self) -> Tool:
        """AnalysisAgent를 도구로 변환"""
        def analysis_agent_tool(query: str) -> str:
            """
            이메일 분석 전문가에게 작업을 위임합니다.
            
            이 도구는 다음과 같은 작업에 특화되어 있습니다:
            - 이메일 내용 분석 및 분류
            - 업무/개인 메일 구분
            - 우선순위 및 중요도 분석
            - 이메일 내용 요약 및 핵심 포인트 추출
            
            Args:
                query: 이메일 분석 관련 사용자 요청
            
            Returns:
                이메일 분석 결과 및 분류 정보
            """
            try:
                logging.info(f"📊 AnalysisAgent에게 작업 위임: {query}")
                result = self.analysis_agent.execute(query)
                return f"📈 이메일 분석 전문가 결과:\n{result}"
            except Exception as e:
                logging.error(f"❌ AnalysisAgent 실행 실패: {str(e)}")
                return f"이메일 분석 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="analysis_agent_tool",
            description="이메일 분석 전문가에게 작업을 위임합니다. 이메일 분류, 우선순위 분석, 내용 요약 등 데이터 분석 작업에 특화되어 있습니다. '이메일 분석해줘', '업무용 메일만 분류해줘', '우선순위 정해줘' 등의 요청에 사용합니다.",
            func=analysis_agent_tool
        )
    
    def _create_ticketing_agent_tool(self) -> Tool:
        """TicketingAgent를 도구로 변환"""
        def ticketing_agent_tool(query: str) -> str:
            """
            티켓 처리 전문가에게 작업을 위임합니다.
            
            이 도구는 다음과 같은 작업에 특화되어 있습니다:
            - Jira 티켓 생성 및 관리
            - 메모리 기반 학습을 통한 최적 판단
            - 복잡한 워크플로우 처리
            - 기존 티켓 조회, 수정, 상태 변경
            - 사용자 피드백 기반 레이블 추천
            
            Args:
                query: 티켓 처리 관련 사용자 요청
            
            Returns:
                티켓 생성/처리 결과 및 메모리 기반 판단 정보
            """
            try:
                logging.info(f"🎫 TicketingAgent에게 작업 위임: {query}")

                # 티켓 생성 관련 쿼리인지 확인
                ticket_creation_keywords = ["티켓으로 생성", "티켓을 생성", "티켓 만들어", "이메일을 티켓으로", "메일을 티켓으로", "수신된 이메일"]
                is_ticket_creation = any(keyword in query for keyword in ticket_creation_keywords)

                if is_ticket_creation:
                    print("🔒 티켓 생성 전용 모드 활성화 - read_emails_tool 차단")
                    self.ticketing_agent.set_ticket_creation_mode(True)
                else:
                    self.ticketing_agent.set_ticket_creation_mode(False)

                # 현재 컨텍스트에서 쿠키 정보 가져오기
                cookies = getattr(self, '_current_context', {}).get('cookies', '')
                print(f"🍪 RouterAgent에서 TicketingAgent로 쿠키 전달: {'있음' if cookies else '없음'}")
                if cookies:
                    print(f"🍪 RouterAgent에서 전달할 쿠키 내용: {cookies[:100]}...")
                result = self.ticketing_agent.execute(query, cookies=cookies)

                # 작업 완료 후 모드 초기화
                self.ticketing_agent.set_ticket_creation_mode(False)
                return f"🎫 티켓 처리 전문가 결과:\n{result}"
            except Exception as e:
                logging.error(f"❌ TicketingAgent 실행 실패: {str(e)}")
                return f"티켓 처리 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="ticketing_agent_tool",
            description="티켓 처리 전문가에게 작업을 위임합니다. Jira 티켓 생성, 메모리 기반 학습, 복잡한 워크플로우 처리 등 가장 복잡하고 중요한 작업에 특화되어 있습니다. '티켓 만들어줘', '안 읽은 메일 처리해줘', '메모리 확인해줘' 등의 요청에 사용합니다.",
            func=ticketing_agent_tool
        )
    
    def _create_agent(self):
        """라우터 에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str, cookies: str = "") -> str:
        """라우터 에이전트 실행"""
        try:
            logging.info(f"🚀 {self.name} 실행: {query}")
            
            # 이메일 관련 쿼리이고 쿠키가 있으면 ViewingAgent를 직접 호출 (티켓 생성 요청 제외)
            if cookies and any(keyword in query.lower() for keyword in ["메일", "이메일", "안 읽은", "읽지 않은", "gmail", "outlook"]) and "티켓" not in query.lower():
                print(f"🍪 RouterAgent에서 직접 ViewingAgent 호출: {cookies[:100]}...")
                try:
                    result = self.viewing_agent.execute(query, cookies=cookies)
                    logging.info(f"✅ {self.name} 응답 (직접 호출): {result}")
                    return result
                except Exception as e:
                    print(f"🍪 직접 호출 실패: {e}")
                    logging.error(f"❌ ViewingAgent 직접 호출 실패: {str(e)}")
            
            # 쿠키 정보를 컨텍스트에 포함
            context = {"input": query, "cookies": cookies}
            self._current_context = context  # 도구에서 접근할 수 있도록 저장
            result = self.agent_executor.invoke(context)
            
            # 응답 처리 개선
            if isinstance(result, dict):
                # output 키가 있는 경우
                if "output" in result:
                    response = result["output"]
                    logging.info(f"✅ {self.name} 응답: {response}")
                    return response
                # messages 키가 있는 경우 (LangChain 최신 버전)
                elif "messages" in result and result["messages"]:
                    response = result["messages"][-1].content
                    logging.info(f"✅ {self.name} 응답: {response}")
                    return response
                # 기타 키들 확인
                else:
                    logging.warning(f"⚠️ 예상치 못한 응답 구조: {result.keys()}")
                    # 첫 번째 문자열 값 반환
                    for key, value in result.items():
                        if isinstance(value, str) and value.strip():
                            logging.info(f"✅ {self.name} 응답 ({key}): {value}")
                            return value
            elif isinstance(result, str):
                logging.info(f"✅ {self.name} 응답: {result}")
                return result
            
            logging.error(f"❌ 처리할 수 없는 응답 타입: {type(result)}")
            return "처리 결과를 가져올 수 없습니다."
            
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"라우터 에이전트 실행 중 오류가 발생했습니다: {str(e)}"
    
    def _create_oauth_check_tool(self) -> Tool:
        """OAuth 인증 상태 확인 도구"""
        def oauth_check_tool(query: str = "") -> str:
            """
            OAuth 인증 상태를 확인합니다.
            
            Args:
                query: 사용자 쿼리 (이메일 관련 키워드에서 제공자 추출)
            
            Returns:
                인증 상태 정보
            """
            try:
                # 쿼리에서 제공자 추출
                provider = self._extract_provider_from_query(query)
                
                # DB에서 연동 정보 확인 (Gmail의 경우)
                if provider == "gmail":
                    print("🍪 DB에서 Gmail 연동 정보 확인")
                    try:
                        from auth_client import auth_client
                        
                        # 사용자가 로그인되어 있는지 확인
                        if auth_client.is_logged_in():
                            print("🍪 사용자가 로그인됨 - DB에서 Google 연동 정보 확인")
                            result = auth_client.get_google_integration()
                            if result.get("success") and result.get("has_token"):
                                return f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 완료되었습니다."
                            else:
                                return f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 필요합니다."
                        else:
                            return f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 필요합니다."
                    except Exception as e:
                        print(f"🍪 DB 토큰 확인 실패: {e}")
                        return f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 필요합니다."
                else:
                    return f"🔍 {provider.upper()} 인증 상태: {provider.upper()} 인증이 필요합니다."
                    
            except Exception as e:
                return f"❌ 인증 상태 확인 실패: {e}"
        
        return Tool(
            name="oauth_check",
            description="OAuth 인증 상태를 확인합니다. 이메일 서비스 사용 전에 인증이 필요한지 확인할 수 있습니다.",
            func=oauth_check_tool
        )
    
    def _create_oauth_login_tool(self) -> Tool:
        """OAuth 로그인 URL 생성 도구"""
        def oauth_login_tool(query: str = "") -> str:
            """
            OAuth 로그인 URL을 생성합니다.
            
            Args:
                query: 사용자 쿼리 (이메일 관련 키워드에서 제공자 추출)
            
            Returns:
                OAuth 로그인 URL과 안내 메시지
            """
            try:
                # 쿼리에서 제공자 추출
                provider = self._extract_provider_from_query(query)
                
                result = self.oauth_agent.generate_auth_url(provider)
                if result["success"]:
                    return f"""
🔐 {provider.upper()} OAuth 인증이 필요합니다.

**인증 방법:**
1. 아래 URL을 브라우저에서 열어주세요
2. {provider.upper()} 계정으로 로그인
3. 권한 승인 후 authorization_code를 받아주세요

**🔗 인증 URL:** {result['auth_url']}

**상태 토큰:** {result['state']}

인증이 완료되면 다시 이메일 조회를 요청해주세요! 📧
                    """
                else:
                    return f"❌ OAuth URL 생성 실패: {result['error']}"
            except Exception as e:
                return f"❌ OAuth 로그인 도구 실행 실패: {e}"
        
        return Tool(
            name="oauth_login",
            description="OAuth 로그인 URL을 생성합니다. 이메일 서비스 사용을 위해 인증이 필요할 때 사용합니다.",
            func=oauth_login_tool
        )
    
    def _create_oauth_callback_tool(self) -> Tool:
        """OAuth 콜백 처리 도구"""
        def oauth_callback_tool(provider: str, code: str, state: str) -> str:
            """
            OAuth 콜백을 처리하여 access_token을 받습니다.
            
            Args:
                provider: 이메일 제공자 (gmail, microsoft)
                code: OAuth 인증 후 받은 authorization_code
                state: OAuth 인증 시 생성된 상태 토큰
            
            Returns:
                인증 완료 메시지와 토큰 정보
            """
            try:
                result = self.oauth_agent.process_callback(provider, code, state)
                if result["success"]:
                    return f"""
✅ {provider.upper()} OAuth 인증이 완료되었습니다!

**토큰 정보:**
- Access Token: {result['access_token'][:20]}...
- Refresh Token: {result['refresh_token'][:20] if result['refresh_token'] else 'None'}...

이제 이메일 서비스를 사용할 수 있습니다! 📧
                    """
                else:
                    return f"❌ OAuth 콜백 처리 실패: {result['error']}"
            except Exception as e:
                return f"❌ OAuth 콜백 도구 실행 실패: {e}"
        
        return Tool(
            name="oauth_callback",
            description="OAuth 콜백을 처리하여 access_token을 받습니다. OAuth 인증 완료 후 사용합니다.",
            func=oauth_callback_tool
        )
    
    def _create_oauth_refresh_tool(self) -> Tool:
        """OAuth 토큰 재발급 도구"""
        def oauth_refresh_tool(provider: str = "gmail") -> str:
            """
            OAuth 토큰을 재발급합니다.
            
            Args:
                provider: 이메일 제공자 (gmail, microsoft)
            
            Returns:
                토큰 재발급 결과
            """
            try:
                result = self.oauth_agent.refresh_token(provider)
                if result["success"]:
                    return f"""
✅ {provider.upper()} 토큰이 성공적으로 재발급되었습니다!

**새 토큰 정보:**
- Access Token: {result['access_token'][:20]}...
- Refresh Token: {result['refresh_token'][:20] if result['refresh_token'] else 'None'}...

이제 이메일 서비스를 계속 사용할 수 있습니다! 📧
                    """
                else:
                    return f"❌ 토큰 재발급 실패: {result['error']}"
            except Exception as e:
                return f"❌ OAuth 토큰 재발급 도구 실행 실패: {e}"
        
        return Tool(
            name="oauth_refresh",
            description="OAuth 토큰을 재발급합니다. 토큰이 만료되었을 때 사용합니다.",
            func=oauth_refresh_tool
        )
    
    def _extract_provider_from_query(self, query: str) -> str:
        """쿼리에서 이메일 제공자를 추출합니다."""
        if not query:
            return "gmail"  # 기본값
        
        query_lower = query.lower()
        
        # Gmail 관련 키워드
        gmail_keywords = ["gmail", "google", "구글"]
        if any(keyword in query_lower for keyword in gmail_keywords):
            return "gmail"
        
        # Microsoft/Outlook 관련 키워드
        microsoft_keywords = ["outlook", "microsoft", "ms", "마이크로소프트", "아웃룩"]
        if any(keyword in query_lower for keyword in microsoft_keywords):
            return "microsoft"
        
        # 기본값은 Gmail
        return "gmail"


# 라우터 에이전트 인스턴스 생성 함수
def create_router_agent(llm_client) -> RouterAgent:
    """RouterAgent 인스턴스 생성"""
    return RouterAgent(llm_client)

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
    router_agent = create_router_agent(test_llm)
    
    # 다양한 쿼리 테스트
    test_queries = [
        "안 읽은 메일 3개 보여주세요",
        "이메일들을 분석해서 업무용만 분류해주세요", 
        "안 읽은 메일을 처리해서 티켓을 만들어주세요"
    ]
    
    for query in test_queries:
        print(f"\n🔍 테스트 쿼리: {query}")
        result = router_agent.execute(query)
        print(f"📋 결과: {result[:200]}...")
        print("-" * 50)
