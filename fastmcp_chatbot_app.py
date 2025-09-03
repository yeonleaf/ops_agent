#!/usr/bin/env python3
"""
FastMCP 기반 메일 조회 챗봇 앱
기존 chatbot_app.py를 FastMCP 서버와 연동하도록 수정
"""

import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# 라우터 에이전트 import
from router_agent import create_router_agent

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

# 페이지 설정
st.set_page_config(
    page_title="📧 FastMCP 메일 조회 챗봇",
    page_icon="🤖",
    layout="wide"
)

class RouterAgentClient:
    """라우터 에이전트 클라이언트 래퍼"""
    
    def __init__(self):
        self.router_agent = create_router_agent()
    
    def call_agent(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """라우터 에이전트 호출"""
        try:
            result = self.router_agent.execute(user_query)
            return {
                "success": True,
                "message": result,
                "data": None,
                "tools_used": ["router_agent"],
                "query": user_query
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"에이전트 실행 중 오류가 발생했습니다: {str(e)}",
                "data": None,
                "tools_used": [],
                "error": str(e),
                "query": user_query
            }
    
    def get_server_status(self) -> Dict[str, Any]:
        """서버 상태 확인"""
        return {
            "status": "running",
            "agent_type": "router_agent",
            "available_agents": ["ViewingAgent", "AnalysisAgent", "TicketingAgent"],
            "message": "에이전트 네트워크가 정상적으로 실행 중입니다."
        }

class AgentNetworkChatBot:
    """에이전트 네트워크 기반 챗봇 클래스"""
    
    def __init__(self):
        self.router_client = RouterAgentClient()
        self.conversation_history = st.session_state.conversation_history
    
    def process_user_input(self, user_input: str) -> str:
        """사용자 입력 처리"""
        try:
            # 라우터 에이전트 호출
            result = self.router_client.call_agent(user_input)
            
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
    st.title("🤖 에이전트 네트워크 메일 챗봇")
    st.markdown("---")
    
    # 챗봇 인스턴스 생성
    chatbot = AgentNetworkChatBot()
    
    # 사이드바 - 서버 상태 및 도구
    with st.sidebar:
        st.header("🔧 서버 상태")
        
        # 서버 상태 확인
        if st.button("에이전트 네트워크 상태 확인"):
            status = chatbot.router_client.get_server_status()
            if status.get("status") == "running":
                st.success("✅ 에이전트 네트워크 정상")
                st.json(status)
            else:
                st.error(f"❌ 에이전트 네트워크 오류: {status.get('message', '알 수 없는 오류')}")
        
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
        
        elif selected_tool == "process_emails_with_ticket_logic":
            provider_name = st.text_input("Provider Name", value="gmail")
            user_query = st.text_input("User Query", value="안 읽은 메일 처리해주세요")
            
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {
                    "provider_name": provider_name,
                    "user_query": user_query
                })
                st.json(result)
        
        elif selected_tool == "get_email_provider_status":
            provider_name = st.text_input("Provider Name (선택사항)", value="")
            
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {
                    "provider_name": provider_name if provider_name else None
                })
                st.json(result)
        
        elif selected_tool == "get_mail_content_by_id":
            message_id = st.text_input("Message ID", value="")
            
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {
                    "message_id": message_id
                })
                st.json(result)
        
        elif selected_tool == "create_ticket_from_single_email":
            email_data = st.text_area("Email Data (JSON)", value='{"id": "test", "subject": "테스트", "sender": "test@example.com", "body": "테스트 내용"}')
            
            if st.button("도구 실행"):
                try:
                    email_data_dict = json.loads(email_data)
                    result = chatbot.mcp_client.call_tool(selected_tool, {
                        "email_data": email_data_dict
                    })
                    st.json(result)
                except json.JSONDecodeError:
                    st.error("JSON 형식이 올바르지 않습니다.")
        
        elif selected_tool == "fetch_emails_sync":
            provider_name = st.text_input("Provider Name", value="gmail")
            use_classifier = st.checkbox("Use Classifier", value=False)
            max_results = st.number_input("Max Results", value=50, min_value=1, max_value=1000)
            
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {
                    "provider_name": provider_name,
                    "use_classifier": use_classifier,
                    "max_results": max_results
                })
                st.json(result)
        
        elif selected_tool in ["get_available_providers", "get_default_provider", "test_work_related_filtering", "get_server_status"]:
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {})
                st.json(result)
        
        elif selected_tool in ["test_email_fetch_logic", "test_ticket_creation_logic"]:
            provider_name = st.text_input("Provider Name", value="gmail")
            
            if st.button("도구 실행"):
                result = chatbot.mcp_client.call_tool(selected_tool, {
                    "provider_name": provider_name
                })
                st.json(result)
        
        st.markdown("---")
        
        # 대화 기록 초기화
        if st.button("🗑️ 대화 기록 초기화"):
            chatbot.clear_conversation()
            st.success("대화 기록이 초기화되었습니다.")
            st.rerun()
    
    # 메인 채팅 인터페이스
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("💬 채팅")
        
        # 대화 기록 표시
        for i, message in enumerate(chatbot.get_conversation_history()):
            with st.expander(f"💬 대화 {i+1} - {message['timestamp'][:19]}"):
                st.markdown(f"**👤 사용자:** {message['user']}")
                st.markdown(f"**🤖 어시스턴트:** {message['assistant']}")
                
                if message.get('tools_used'):
                    st.markdown(f"**🛠️ 사용된 도구:** {', '.join(message['tools_used'])}")
                
                if message.get('data'):
                    with st.expander("📊 상세 데이터"):
                        st.json(message['data'])
                
                if not message.get('success', True):
                    st.error("❌ 처리 실패")
    
    with col2:
        st.header("📝 새 메시지")
        
        # 사용자 입력
        user_input = st.text_area(
            "메시지를 입력하세요:",
            height=100,
            placeholder="예: 안 읽은 메일을 처리해주세요"
        )
        
        # 전송 버튼
        if st.button("📤 전송", type="primary"):
            if user_input.strip():
                with st.spinner("처리 중..."):
                    response = chatbot.process_user_input(user_input)
                    st.success("응답이 생성되었습니다!")
                    st.rerun()
            else:
                st.warning("메시지를 입력해주세요.")
        
        # 빠른 명령어 버튼들
        st.markdown("**🚀 빠른 명령어:**")
        
        quick_commands = [
            "안 읽은 메일을 처리해주세요",
            "Gmail 연결 상태를 확인해주세요",
            "사용 가능한 이메일 제공자를 보여주세요",
            "서버 상태를 확인해주세요"
        ]
        
        for cmd in quick_commands:
            if st.button(f"📌 {cmd}", key=f"quick_{cmd}"):
                with st.spinner("처리 중..."):
                    response = chatbot.process_user_input(cmd)
                    st.success("응답이 생성되었습니다!")
                    st.rerun()
    
    # 푸터
    st.markdown("---")
    st.markdown("**FastMCP 기반 이메일 서비스 챗봇** | 🤖 AI-Powered Email Management")

if __name__ == "__main__":
    main()
