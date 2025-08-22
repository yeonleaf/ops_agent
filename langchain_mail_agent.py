#!/usr/bin/env python3
"""
LangChain 에이전트를 사용한 메일 조회 시스템
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langchain_mail_tools import AVAILABLE_TOOLS

# 환경변수 로드
load_dotenv()

class MailAgent:
    """메일 조회 에이전트"""
    
    def __init__(self, llm_provider: str = "azure", model_name: str = "gpt-4"):
        """
        Args:
            llm_provider: LLM 제공자 ("azure")
            model_name: 모델 이름 (Azure의 경우 deployment name이 .env에서 자동 로드됨)
        """
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.llm = self._setup_llm()
        self.agent_executor = self._create_agent()
    
    def _setup_llm(self):
        """LLM 설정 - Azure OpenAI만 지원"""
        if self.llm_provider == "azure":
            # Azure OpenAI 설정
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION")
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            
            if not all([endpoint, api_key, api_version, deployment_name]):
                raise ValueError("Azure OpenAI 환경변수가 모두 설정되지 않았습니다. (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT_NAME)")
            
            return AzureChatOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
                azure_deployment=deployment_name,
                temperature=0
            )
        else:
            raise ValueError(f"현재는 Azure OpenAI만 지원합니다. 받은 제공자: {self.llm_provider}")
    
    def _create_agent(self):
        """에이전트 생성"""
        # 프롬프트 템플릿
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 메일 조회와 티켓 관리를 도와주는 AI 어시스턴트입니다.

사용자의 요청을 분석하여 적절한 툴을 사용해 정보를 제공하세요.

주요 기능:
1. **메일 조회**: 안읽은 메일, 전체 메일, 검색, 발신자별 조회
2. **티켓 워크플로우**: 메일→티켓 생성→RDB 저장→벡터 임베딩
3. **작업 관리**: 오늘 처리해야 할 작업 리스트 관리

사용 가능한 툴들:
- get_unread_emails: 안읽은 메일 조회
- get_all_emails: 전체 메일 조회  
- search_emails: 키워드로 메일 검색
- get_emails_by_sender: 특정 발신자 메일 조회
- get_mail_statistics: 메일 통계
- process_todays_tasks: 오늘 처리할 작업 통합 처리 ⭐
- get_todays_unread_emails: 오늘의 안읽은 메일
- create_ticket_from_email: 메일→티켓 생성
- add_mail_to_vector_db: 메일 벡터 임베딩
- check_ticket_exists: 티켓 존재 확인
- get_existing_tickets_by_status: 상태별 티켓 조회

특별 처리 케이스:
- "오늘 처리할 작업/티켓" 요청 → process_todays_tasks() 사용
- "처리해야 할 일" 요청 → process_todays_tasks() 사용  
- 단순 메일 조회 → 기본 메일 툴 사용

응답 가이드라인:
- 사용자 의도에 맞는 툴을 정확히 선택하세요
- 티켓 리스트 요청 시: 간단한 안내 메시지만 제공하고 툴 결과 JSON은 그대로 출력하세요
- 일반 메일 조회 시: 결과를 읽기 쉽게 한국어로 정리하세요
- 한국어로 친근하고 전문적으로 응답하세요

중요: process_todays_tasks 도구 사용 시에는 반드시 도구의 원본 JSON 응답을 그대로 포함하세요."""),
            ("user", "{input}"),
            ("assistant", "{agent_scratchpad}")
        ])
        
        # 툴 호출 에이전트 생성
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=AVAILABLE_TOOLS,
            prompt=prompt
        )
        
        # 에이전트 실행기 생성
        agent_executor = AgentExecutor(
            agent=agent,
            tools=AVAILABLE_TOOLS,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3
        )
        
        return agent_executor
    
    def query(self, user_input: str) -> str:
        """사용자 질문 처리"""
        try:
            result = self.agent_executor.invoke({"input": user_input})
            return result.get("output", "응답을 생성하지 못했습니다.")
        except Exception as e:
            return f"처리 중 오류가 발생했습니다: {str(e)}"

