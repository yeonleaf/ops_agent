#!/usr/bin/env python3
"""
오케스트레이터 에이전트 (Orchestrator Agent)
전문가 에이전트들의 순차적 협업을 관리하는 슈퍼바이저
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

# 전문가 에이전트 import
from specialist_agents import create_viewing_agent, create_analysis_agent, create_ticketing_agent

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OrchestratorAgent:
    """오케스트레이터 에이전트 - 전문가 에이전트들의 순차적 협업을 관리"""
    
    def __init__(self):
        self.name = "OrchestratorAgent"
        self.llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # 전문가 에이전트 인스턴스 생성
        self.viewing_agent = create_viewing_agent()
        self.analysis_agent = create_analysis_agent()
        self.ticketing_agent = create_ticketing_agent()
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 전문가 에이전트들의 협업을 관리하는 오케스트레이터입니다.

## 역할
사용자의 복잡한 요청을 받아서, 작업을 완료하기 위한 단계별 계획을 수립하고 각 단계를 적절한 전문가에게 순서대로 지시합니다.

## 사용 가능한 전문가들

### 1. ViewingAgent (이메일 조회 전문가)
- **역할**: 이메일을 조회하고 목록을 반환
- **특화 분야**: 이메일 검색, 필터링, 목록 조회
- **출력**: 이메일 목록 (email_list)

### 2. AnalysisAgent (데이터 분석 전문가)
- **역할**: 이메일을 분석하고 분류
- **특화 분야**: 업무/개인 분류, 우선순위 분석, 내용 요약
- **입력**: 이메일 목록 (email_list)
- **출력**: 분류된 메일 목록 (classified_list)

### 3. TicketingAgent (티켓 처리 전문가)
- **역할**: 이메일을 분석하여 티켓 생성
- **특화 분야**: 티켓 생성, 메모리 기반 학습, 복잡한 워크플로우
- **입력**: 분류된 메일 목록 (classified_list)
- **출력**: 티켓 생성 결과

## 오케스트레이션 규칙
1. **계획 수립**: 사용자 요청을 분석하여 필요한 단계들을 파악
2. **순차적 실행**: 각 단계를 적절한 전문가에게 순서대로 지시
3. **결과 전달**: 이전 단계의 결과를 다음 단계의 입력으로 전달
4. **최종 통합**: 모든 단계의 결과를 종합하여 사용자에게 보고

## 응답 형식
- 각 단계의 진행 상황을 명확히 보고
- 전문가들의 협업 과정을 투명하게 공개
- 최종 결과를 구조화된 형태로 제공"""

        # 오케스트레이션 도구들
        self.tools = [
            self._create_plan_workflow_tool(),
            self._create_execute_step_tool(),
            self._create_coordinate_agents_tool()
        ]
        
        # 에이전트 생성
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _create_plan_workflow_tool(self) -> Tool:
        """워크플로우 계획 수립 도구"""
        def plan_workflow_tool(user_query: str) -> str:
            """
            사용자 요청을 분석하여 워크플로우 계획을 수립합니다.
            
            Args:
                user_query: 사용자의 요청
            
            Returns:
                워크플로우 계획
            """
            try:
                logging.info(f"🎯 워크플로우 계획 수립: {user_query}")
                
                # 요청 분석
                query_lower = user_query.lower()
                
                # 단계별 계획 수립
                steps = []
                
                if "안 읽은 메일" in query_lower or "메일" in query_lower:
                    if "가져와" in query_lower or "조회" in query_lower:
                        steps.append({
                            "step": 1,
                            "agent": "ViewingAgent",
                            "action": "안 읽은 메일 조회",
                            "input": "사용자 요청",
                            "output": "email_list"
                        })
                
                if "업무" in query_lower or "분석" in query_lower or "분류" in query_lower:
                    steps.append({
                        "step": 2,
                        "agent": "AnalysisAgent", 
                        "action": "업무 관련 메일 분류",
                        "input": "email_list",
                        "output": "classified_list"
                    })
                
                if "티켓" in query_lower or "생성" in query_lower:
                    steps.append({
                        "step": 3,
                        "agent": "TicketingAgent",
                        "action": "티켓 생성",
                        "input": "classified_list",
                        "output": "ticket_result"
                    })
                
                if not steps:
                    return "요청을 분석할 수 없습니다. 더 구체적인 요청을 해주세요."
                
                # 계획 포맷팅
                plan = f"🎯 워크플로우 계획 수립 완료\n\n"
                plan += f"📋 총 {len(steps)}단계 작업 계획:\n\n"
                
                for step in steps:
                    plan += f"**{step['step']}단계**: {step['agent']}\n"
                    plan += f"   - 작업: {step['action']}\n"
                    plan += f"   - 입력: {step['input']}\n"
                    plan += f"   - 출력: {step['output']}\n\n"
                
                plan += "✅ 계획 수립 완료. 이제 단계별 실행을 시작합니다."
                
                return plan
                
            except Exception as e:
                logging.error(f"❌ 워크플로우 계획 수립 실패: {str(e)}")
                return f"계획 수립 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="plan_workflow_tool",
            description="사용자 요청을 분석하여 워크플로우 계획을 수립합니다. 필요한 단계들과 각 단계를 담당할 전문가를 결정합니다.",
            func=plan_workflow_tool
        )
    
    def _create_execute_step_tool(self) -> Tool:
        """단계별 실행 도구"""
        def execute_step_tool(step_info: str) -> str:
            """
            특정 단계를 실행합니다.
            
            Args:
                step_info: 실행할 단계 정보 (문자열 또는 JSON 형태)
            
            Returns:
                단계 실행 결과
            """
            try:
                logging.info(f"⚡ 단계 실행 요청: {step_info}")
                
                # JSON 파싱 시도
                try:
                    import json
                    step_data = json.loads(step_info)
                    step_num = step_data.get("step", 1)
                    agent_name = step_data.get("agent", "ViewingAgent")
                    action = step_data.get("action", "작업 수행")
                    input_data = step_data.get("input", step_info)
                except (json.JSONDecodeError, TypeError):
                    # JSON 파싱 실패 시 문자열에서 직접 추출
                    logging.info("JSON 파싱 실패, 문자열에서 직접 추출 시도")
                    
                    # 문자열에서 에이전트 이름 추출
                    if "AnalysisAgent" in step_info:
                        agent_name = "AnalysisAgent"
                        input_data = "조회된 메일들을 분석해서 중요한 것만 분류해주세요"
                    elif "TicketingAgent" in step_info:
                        agent_name = "TicketingAgent"
                        input_data = "분석된 메일들을 티켓으로 생성해주세요"
                    elif "ViewingAgent" in step_info:
                        agent_name = "ViewingAgent"
                        input_data = "gmail에서 최근 메일 5개 가져와줘"
                    else:
                        # 기본값으로 ViewingAgent 사용
                        agent_name = "ViewingAgent"
                        input_data = step_info
                    
                    step_num = 1
                    action = f"{agent_name} 작업 수행"
                
                logging.info(f"⚡ {step_num}단계 실행: {agent_name} - {action}")
                
                # 전문가 에이전트 선택 및 실행
                if agent_name == "ViewingAgent":
                    result = self.viewing_agent.execute(input_data)
                elif agent_name == "AnalysisAgent":
                    # AnalysisAgent는 이전 단계의 결과를 컨텍스트로 받아야 함
                    context = {"email_list": getattr(self, '_last_viewing_result', None)}
                    result = self.analysis_agent.execute(input_data, context=context)
                elif agent_name == "TicketingAgent":
                    # TicketingAgent는 이전 단계들의 결과를 컨텍스트로 받아야 함
                    context = {
                        "email_list": getattr(self, '_last_viewing_result', None),
                        "classified_list": getattr(self, '_last_analysis_result', None)
                    }
                    result = self.ticketing_agent.execute(input_data, context=context)
                else:
                    return f"알 수 없는 전문가: {agent_name}"
                
                # 결과 저장 (다음 단계에서 사용)
                if agent_name == "ViewingAgent":
                    self._last_viewing_result = result
                elif agent_name == "AnalysisAgent":
                    self._last_analysis_result = result
                
                # 결과 포맷팅
                step_result = f"✅ {step_num}단계 완료: {agent_name}\n"
                step_result += f"📋 작업: {action}\n"
                step_result += f"📊 결과: {result[:200]}...\n"
                
                return step_result
                
            except Exception as e:
                logging.error(f"❌ 단계 실행 실패: {str(e)}")
                return f"단계 실행 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="execute_step_tool",
            description="특정 단계를 실행합니다. 전문가 에이전트를 선택하고 작업을 수행한 후 결과를 반환합니다.",
            func=execute_step_tool
        )
    
    def _create_coordinate_agents_tool(self) -> Tool:
        """에이전트 협업 조정 도구"""
        def coordinate_agents_tool(workflow_plan: str) -> str:
            """
            전문가 에이전트들을 순차적으로 조정하여 워크플로우를 실행합니다.
            
            Args:
                workflow_plan: 워크플로우 계획
            
            Returns:
                전체 워크플로우 실행 결과
            """
            try:
                logging.info("🤝 에이전트 협업 조정 시작")
                
                # 워크플로우 파싱 (간단한 구현)
                if "안 읽은 메일" in workflow_plan and "업무" in workflow_plan and "티켓" in workflow_plan:
                    return self._execute_email_to_ticket_workflow()
                else:
                    return "지원하지 않는 워크플로우입니다."
                
            except Exception as e:
                logging.error(f"❌ 에이전트 협업 조정 실패: {str(e)}")
                return f"협업 조정 중 오류가 발생했습니다: {str(e)}"
        
        return Tool(
            name="coordinate_agents_tool",
            description="전문가 에이전트들을 순차적으로 조정하여 전체 워크플로우를 실행합니다.",
            func=coordinate_agents_tool
        )
    
    def _execute_email_to_ticket_workflow(self) -> str:
        """이메일 → 티켓 워크플로우 실행"""
        try:
            logging.info("🔄 이메일 → 티켓 워크플로우 시작")
            
            # 워크플로우 상태 추적
            workflow_state = {
                "step": 1,
                "total_steps": 3,
                "results": {},
                "context": {}
            }
            
            # 1단계: ViewingAgent - 안 읽은 메일 조회
            logging.info("📧 1단계: ViewingAgent - 안 읽은 메일 조회")
            print("🎯 [오케스트레이터] 1단계: ViewingAgent에게 안 읽은 메일 조회 지시")
            
            email_result = self.viewing_agent.execute("gmail에서 안 읽은 메일 10개 가져와줘")
            workflow_state["results"]["step1"] = email_result
            workflow_state["context"]["email_list"] = email_result
            
            print("✅ [ViewingAgent] 안 읽은 메일 조회 완료")
            print(f"📊 [오케스트레이터] 1단계 완료: {len(email_result)}자 결과 수신")
            
            # 2단계: AnalysisAgent - 업무 관련 메일 분류
            logging.info("📊 2단계: AnalysisAgent - 업무 관련 메일 분류")
            print("🎯 [오케스트레이터] 2단계: AnalysisAgent에게 업무 관련 메일 분류 지시")
            
            analysis_context = {
                "previous_step": "ViewingAgent",
                "email_list": email_result[:500]  # 컨텍스트로 전달
            }
            analysis_result = self.analysis_agent.execute(
                "조회된 메일들을 분석해서 업무용만 분류해주세요", 
                context=analysis_context
            )
            workflow_state["results"]["step2"] = analysis_result
            workflow_state["context"]["classified_list"] = analysis_result
            
            print("✅ [AnalysisAgent] 업무 관련 메일 분류 완료")
            print(f"📊 [오케스트레이터] 2단계 완료: {len(analysis_result)}자 결과 수신")
            
            # 3단계: TicketingAgent - 티켓 생성
            logging.info("🎫 3단계: TicketingAgent - 티켓 생성")
            print("🎯 [오케스트레이터] 3단계: TicketingAgent에게 티켓 생성 지시")
            
            ticket_context = {
                "previous_steps": ["ViewingAgent", "AnalysisAgent"],
                "email_list": email_result[:300],
                "classified_list": analysis_result[:300]
            }
            ticket_result = self.ticketing_agent.execute(
                "분석된 업무용 메일들을 티켓으로 생성해주세요",
                context=ticket_context
            )
            workflow_state["results"]["step3"] = ticket_result
            
            print("✅ [TicketingAgent] 티켓 생성 완료")
            print(f"📊 [오케스트레이터] 3단계 완료: {len(ticket_result)}자 결과 수신")
            
            # 최종 결과 통합
            final_result = f"""
🤝 에이전트 체인 협업 워크플로우 완료!

## 🎼 오케스트레이터 보고서

### 📋 워크플로우 실행 과정
1. **계획 수립**: 사용자 요청 분석 → 3단계 워크플로우 계획
2. **순차적 실행**: 각 전문가에게 단계별 작업 지시
3. **결과 전달**: 이전 단계 결과를 다음 단계 입력으로 전달
4. **최종 통합**: 모든 단계 결과를 종합하여 보고

### 📧 1단계: ViewingAgent (이메일 조회)
**지시**: "gmail에서 안 읽은 메일 10개 가져와줘"
**결과**: {email_result[:200]}...

### 📊 2단계: AnalysisAgent (업무 관련 분류)  
**지시**: "조회된 메일들을 분석해서 업무용만 분류해주세요"
**컨텍스트**: ViewingAgent 결과 전달
**결과**: {analysis_result[:200]}...

### 🎫 3단계: TicketingAgent (티켓 생성)
**지시**: "분석된 업무용 메일들을 티켓으로 생성해주세요"
**컨텍스트**: ViewingAgent + AnalysisAgent 결과 전달
**결과**: {ticket_result[:200]}...

## ✅ 최종 결과
🎯 **총 3단계 워크플로우 완료**
🤝 **3개 전문가 에이전트 순차적 협업 성공**
📊 **복잡한 다단계 작업을 체계적으로 처리**

전문가 에이전트들이 각자의 전문성을 발휘하여 순차적으로 협업했습니다!
"""
            
            return final_result
            
        except Exception as e:
            logging.error(f"❌ 이메일 → 티켓 워크플로우 실패: {str(e)}")
            return f"워크플로우 실행 중 오류가 발생했습니다: {str(e)}"
    
    def _create_agent(self):
        """오케스트레이터 에이전트 생성"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
    def execute(self, query: str) -> str:
        """오케스트레이터 에이전트 실행"""
        try:
            logging.info(f"🎼 {self.name} 실행: {query}")
            
            # 복잡한 요청인지 판단
            if self._is_complex_request(query):
                # 직접 워크플로우 실행
                return self._execute_email_to_ticket_workflow()
            else:
                # 기존 에이전트 방식으로 처리
                result = self.agent_executor.invoke({"input": query})
                return result.get("output", "처리 결과를 가져올 수 없습니다.")
                
        except Exception as e:
            logging.error(f"❌ {self.name} 실행 실패: {str(e)}")
            return f"오케스트레이터 실행 중 오류가 발생했습니다: {str(e)}"
    
    def _is_complex_request(self, query: str) -> bool:
        """복잡한 요청인지 판단"""
        query_lower = query.lower()
        return (
            ("안 읽은 메일" in query_lower or "메일" in query_lower) and
            ("업무" in query_lower or "분석" in query_lower) and
            ("티켓" in query_lower or "생성" in query_lower)
        )


# 오케스트레이터 에이전트 인스턴스 생성 함수
def create_orchestrator_agent() -> OrchestratorAgent:
    """OrchestratorAgent 인스턴스 생성"""
    return OrchestratorAgent()

if __name__ == "__main__":
    # 테스트
    orchestrator = create_orchestrator_agent()
    
    # 복잡한 요청 테스트
    test_query = "안 읽은 메일 가져와서 업무 관련된 메일만 티켓 생성해줘"
    print(f"🔍 테스트 쿼리: {test_query}")
    result = orchestrator.execute(test_query)
    print(f"📋 결과: {result[:500]}...")
