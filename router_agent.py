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

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RouterAgent:
    """라우터 에이전트 - 전문가 에이전트들을 라우팅하는 최상위 에이전트"""
    
    def __init__(self, llm_client):
        self.name = "RouterAgent"
        self.llm = llm_client
        
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

## 라우팅 규칙
1. **단순 조회 요청** → ViewingAgent
2. **분석/분류 요청** → AnalysisAgent  
3. **티켓 생성/처리 요청** → TicketingAgent
4. **복합 요청** → 워크플로우에 따라 여러 전문가를 순차적으로 활용

## 응답 형식
- 선택한 전문가와 그 이유를 명확히 설명합니다
- 복합 워크플로우의 경우 각 단계별 진행 상황을 안내합니다
- 전문가의 작업 결과를 사용자에게 전달합니다
- 한국어로 친근하고 전문적인 톤으로 응답합니다"""

        # 전문가 에이전트 인스턴스 생성
        self.viewing_agent = create_viewing_agent(llm_client)
        self.analysis_agent = create_analysis_agent(llm_client)
        self.ticketing_agent = create_ticketing_agent(llm_client)
        
        # 전문가 에이전트들을 도구로 변환
        self.tools = [
            self._create_viewing_agent_tool(),
            self._create_analysis_agent_tool(),
            self._create_ticketing_agent_tool()
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
                result = self.viewing_agent.execute(query)
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
                result = self.ticketing_agent.execute(query)
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
    
    def execute(self, query: str) -> str:
        """라우터 에이전트 실행"""
        try:
            logging.info(f"🚀 {self.name} 실행: {query}")
            result = self.agent_executor.invoke({"input": query})
            return result.get("output", "처리 결과를 가져올 수 없습니다.")
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"라우터 에이전트 실행 중 오류가 발생했습니다: {str(e)}"


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
