#!/usr/bin/env python3
"""
에이전트 네트워크 기반 메일 챗봇 앱
라우터 에이전트와 전문가 에이전트들을 활용한 챗봇
"""

import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# 오케스트레이터 에이전트 import
from orchestrator_agent import create_orchestrator_agent

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

# 페이지 설정
st.set_page_config(
    page_title="🤖 에이전트 네트워크 메일 챗봇",
    page_icon="🤖",
    layout="wide"
)

class OrchestratorAgentClient:
    """오케스트레이터 에이전트 클라이언트 래퍼"""
    
    def __init__(self):
        self.orchestrator_agent = create_orchestrator_agent()
    
    def call_agent(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """오케스트레이터 에이전트 호출"""
        try:
            result = self.orchestrator_agent.execute(user_query)
            return {
                "success": True,
                "message": result,
                "data": None,
                "tools_used": ["orchestrator_agent"],
                "query": user_query
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"오케스트레이터 실행 중 오류가 발생했습니다: {str(e)}",
                "data": None,
                "tools_used": [],
                "error": str(e),
                "query": user_query
            }
    
    def get_server_status(self) -> Dict[str, Any]:
        """서버 상태 확인"""
        return {
            "status": "running",
            "agent_type": "orchestrator_agent",
            "available_agents": ["ViewingAgent", "AnalysisAgent", "TicketingAgent"],
            "collaboration_mode": "sequential_chain",
            "message": "오케스트레이터 에이전트가 전문가 에이전트들의 협업을 관리하고 있습니다."
        }

class AgentNetworkChatBot:
    """에이전트 네트워크 기반 챗봇 클래스"""
    
    def __init__(self):
        self.orchestrator_client = OrchestratorAgentClient()
        self.conversation_history = st.session_state.conversation_history
    
    def process_user_input(self, user_input: str) -> str:
        """사용자 입력 처리"""
        try:
            # 오케스트레이터 에이전트 호출
            result = self.orchestrator_client.call_agent(user_input)
            
            # 대화 기록에 추가
            self.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user": user_input,
                "assistant": result.get("message", "응답을 생성할 수 없습니다."),
                "success": result.get("success", False),
                "tools_used": result.get("tools_used", []),
                "data": result.get("data")
            })
            
            # 세션 상태 업데이트
            st.session_state.conversation_history = self.conversation_history
            st.session_state.refresh_trigger += 1
            
            return result.get("message", "응답을 생성할 수 없습니다.")
            
        except Exception as e:
            error_message = f"입력 처리 중 오류가 발생했습니다: {str(e)}"
            self.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user": user_input,
                "assistant": error_message,
                "success": False,
                "tools_used": [],
                "data": None
            })
            return error_message
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """대화 기록 반환"""
        return self.conversation_history
    
    def clear_conversation(self):
        """대화 기록 초기화"""
        self.conversation_history = []
        st.session_state.conversation_history = []

def main():
    """메인 애플리케이션"""
    
    # 제목
    st.title("🎼 오케스트레이터 에이전트 메일 챗봇")
    st.markdown("---")
    
    # 챗봇 인스턴스 생성
    chatbot = AgentNetworkChatBot()
    
    # 사이드바 - 서버 상태 및 전문가 에이전트
    with st.sidebar:
        st.header("🔧 에이전트 네트워크 상태")
        
        # 서버 상태 확인
        if st.button("오케스트레이터 에이전트 상태 확인"):
            status = chatbot.orchestrator_client.get_server_status()
            if status.get("status") == "running":
                st.success("✅ 오케스트레이터 에이전트 정상")
                st.json(status)
            else:
                st.error(f"❌ 오케스트레이터 에이전트 오류: {status.get('message', '알 수 없는 오류')}")
        
        st.markdown("---")
        
        st.header("🤖 전문가 에이전트 직접 호출")
        
        # 전문가 에이전트 선택
        agent_options = [
            "ViewingAgent (이메일 조회 전문가)",
            "AnalysisAgent (데이터 분석 전문가)", 
            "TicketingAgent (티켓 처리 전문가)"
        ]
        
        selected_agent = st.selectbox("전문가 에이전트 선택", agent_options)
        
        # 에이전트별 쿼리 입력
        if selected_agent:
            agent_query = st.text_area("전문가 에이전트에게 보낼 쿼리", value="안 읽은 메일을 보여주세요")
            
            if st.button("전문가 에이전트 실행"):
                try:
                    # 선택된 에이전트에 따라 직접 호출
                    if "ViewingAgent" in selected_agent:
                        from specialist_agents import create_viewing_agent
                        agent = create_viewing_agent()
                        result = agent.execute(agent_query)
                    elif "AnalysisAgent" in selected_agent:
                        from specialist_agents import create_analysis_agent
                        agent = create_analysis_agent()
                        result = agent.execute(agent_query)
                    elif "TicketingAgent" in selected_agent:
                        from specialist_agents import create_ticketing_agent
                        agent = create_ticketing_agent()
                        result = agent.execute(agent_query)
                    
                    st.success(f"✅ {selected_agent} 실행 완료")
                    st.text_area("결과", value=result, height=200)
                except Exception as e:
                    st.error(f"❌ 에이전트 실행 실패: {str(e)}")
        
        st.markdown("---")
        
        # 대화 기록 관리
        st.header("💬 대화 기록")
        if st.button("대화 기록 초기화"):
            chatbot.clear_conversation()
            st.success("대화 기록이 초기화되었습니다.")
            st.rerun()
    
    # 메인 채팅 인터페이스
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("💬 채팅")
        
        # 사용자 입력
        user_input = st.text_input("메시지를 입력하세요:", placeholder="예: 안 읽은 메일을 처리해주세요")
        
        col_send, col_clear = st.columns([1, 1])
        
        with col_send:
            if st.button("전송", type="primary"):
                if user_input:
                    with st.spinner("처리 중..."):
                        response = chatbot.process_user_input(user_input)
                        st.rerun()
        
        with col_clear:
            if st.button("대화 초기화"):
                chatbot.clear_conversation()
                st.rerun()
    
    with col2:
        st.header("📊 오케스트레이터 정보")
        
        st.markdown("""
        ### 🎼 오케스트레이터 에이전트
        
        **🎯 역할**
        - 전문가 에이전트들의 협업 관리
        - 복잡한 워크플로우 계획 수립
        - 순차적 작업 조정
        
        ### 🤖 전문가 에이전트들
        
        **🔍 ViewingAgent**
        - 이메일 조회 및 필터링
        - 단순한 목록 표시 작업
        
        **📊 AnalysisAgent** 
        - 이메일 분석 및 분류
        - 업무/개인 구분
        
        **🎫 TicketingAgent**
        - Jira 티켓 생성 및 관리
        - 메모리 기반 학습
        
        ### 🔄 협업 워크플로우
        1. **계획 수립** → 2. **순차적 실행** → 3. **결과 통합**
        """)
    
    # 대화 기록 표시
    st.markdown("---")
    st.header("📝 대화 기록")
    
    conversation_history = chatbot.get_conversation_history()
    
    if conversation_history:
        for i, entry in enumerate(reversed(conversation_history[-10:])):  # 최근 10개만 표시
            with st.expander(f"💬 {entry['timestamp'][:19]} - {entry['user'][:50]}..."):
                st.markdown(f"**👤 사용자:** {entry['user']}")
                st.markdown(f"**🤖 어시스턴트:** {entry['assistant']}")
                
                if entry.get('tools_used'):
                    st.markdown(f"**🛠️ 사용된 도구:** {', '.join(entry['tools_used'])}")
                
                if entry.get('success'):
                    st.success("✅ 처리 성공")
                else:
                    st.error("❌ 처리 실패")
    else:
        st.info("아직 대화 기록이 없습니다. 위에서 메시지를 입력해보세요!")

if __name__ == "__main__":
    main()
