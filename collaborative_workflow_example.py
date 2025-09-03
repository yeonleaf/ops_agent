#!/usr/bin/env python3
"""
에이전트 협업 워크플로우 예시
3개 에이전트가 순차적으로 협업하는 구조
"""

from router_agent import create_router_agent
from specialist_agents import create_viewing_agent, create_analysis_agent, create_ticketing_agent

def collaborative_workflow_example():
    """에이전트 협업 워크플로우 예시"""
    
    # 1단계: ViewingAgent가 안 읽은 메일 조회
    print("🔍 1단계: ViewingAgent가 안 읽은 메일 조회")
    viewing_agent = create_viewing_agent()
    emails_result = viewing_agent.execute("gmail에서 안 읽은 메일 10개 가져와줘")
    print(f"📧 조회된 메일: {emails_result[:200]}...")
    
    # 2단계: AnalysisAgent가 업무 관련 메일 필터링
    print("\n📊 2단계: AnalysisAgent가 업무 관련 메일 분석")
    analysis_agent = create_analysis_agent()
    analysis_result = analysis_agent.execute("조회된 메일들을 분석해서 업무용만 분류해주세요")
    print(f"📈 분석 결과: {analysis_result[:200]}...")
    
    # 3단계: TicketingAgent가 티켓 생성
    print("\n🎫 3단계: TicketingAgent가 티켓 생성")
    ticketing_agent = create_ticketing_agent()
    ticket_result = ticketing_agent.execute("분석된 업무용 메일들을 티켓으로 생성해주세요")
    print(f"🎫 티켓 생성 결과: {ticket_result[:200]}...")
    
    return {
        "emails": emails_result,
        "analysis": analysis_result,
        "tickets": ticket_result
    }

def enhanced_router_agent():
    """향상된 라우터 에이전트 - 협업 워크플로우 지원"""
    
    # 협업 워크플로우를 위한 새로운 도구 추가
    def collaborative_workflow_tool(query: str) -> str:
        """에이전트 협업 워크플로우 도구"""
        if "안 읽은 메일" in query and "업무 관련" in query and "티켓" in query:
            # 3단계 협업 워크플로우 실행
            result = collaborative_workflow_example()
            return f"""
🤝 에이전트 협업 워크플로우 완료!

📧 ViewingAgent: 안 읽은 메일 조회 완료
📊 AnalysisAgent: 업무 관련 메일 분석 완료  
🎫 TicketingAgent: 티켓 생성 완료

결과 요약:
- 조회된 메일: {len(result['emails'])}개
- 분석 완료: 업무용 메일 분류
- 티켓 생성: 완료
"""
        else:
            return "협업 워크플로우가 필요한 요청이 아닙니다."
    
    return collaborative_workflow_tool

if __name__ == "__main__":
    # 협업 워크플로우 테스트
    print("🤝 에이전트 협업 워크플로우 테스트")
    result = collaborative_workflow_example()
    print("\n✅ 협업 워크플로우 완료!")
