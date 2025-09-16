#!/usr/bin/env python3
"""
FastMCP 기반 메일 조회 챗봇 앱
기존 chatbot_app.py를 FastMCP 서버와 연동하도록 수정
"""

import streamlit as st
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
# 쿠키 대신 URL 파라미터와 세션 상태 사용

# LangChain imports
from langchain_openai import AzureChatOpenAI

# 라우터 에이전트 import
from router_agent import create_router_agent

# 새로운 UI import
from enhanced_ticket_ui_v2 import (
    load_tickets_from_db, 
    display_ticket_button_list, 
    display_ticket_detail
)

# mem0 memory import
from mem0_memory_adapter import create_mem0_memory

# 환경 변수 로드
load_dotenv()

# AI 추천 기능 import
from ticket_ai_recommender import get_ticket_ai_recommendation

# RAG 데이터 관리자 import
from rag_data_manager import create_rag_manager_tab

# 인증 관련 import
from auth_client import auth_client
from auth_ui import check_auth_and_show_ui, show_integration_settings

# --- 1. 토큰 복원 로직 (URL 파라미터 → DB 순서) ---
# 세션에 토큰이 없을 때 복원 시도
if 'gmail_access_token' not in st.session_state:
    print("🍪 세션 토큰 없음. 토큰 복원 시도...")
    
    # 1단계: URL 파라미터에서 토큰 확인
    access_token = st.query_params.get('access_token')
    refresh_token = st.query_params.get('refresh_token')
    
    if access_token and refresh_token:
        # URL 파라미터에서 토큰을 받았으면 세션에 저장
        st.session_state['gmail_access_token'] = access_token
        st.session_state['gmail_refresh_token'] = refresh_token
        print("✅ URL 파라미터에서 세션으로 토큰 복원 완료.")
        
        # URL 파라미터 제거 (보안상)
        st.query_params.clear()
    else:
        print("🍪 URL 파라미터에 토큰이 없음 - DB에서 확인 시도...")
        
        # 2단계: DB에서 저장된 refresh_token으로 access_token 재발급 시도
        try:
            from auth_client import auth_client
            if auth_client.is_logged_in():
                print("🔍 DB에서 Google 연동 정보 확인 중...")
                result = auth_client.get_google_integration()
                if result.get("success") and result.get("has_token"):
                    print("✅ DB에 Google 토큰이 저장되어 있음")
                    print("🔄 refresh_token으로 access_token 재발급 시도...")
                    
                    # refresh_token으로 access_token 재발급 시도
                    try:
                        from gmail_provider import refresh_gmail_token
                        refresh_result = refresh_gmail_token()
                        if refresh_result.get("success"):
                            access_token = refresh_result.get("access_token")
                            refresh_token = refresh_result.get("refresh_token")
                            
                            # 세션에 저장
                            st.session_state['gmail_access_token'] = access_token
                            st.session_state['gmail_refresh_token'] = refresh_token
                            print("✅ refresh_token으로 access_token 재발급 성공")
                        else:
                            print("❌ refresh_token으로 access_token 재발급 실패")
                            print("ℹ️ Gmail 기능을 사용하려면 OAuth 인증이 필요합니다.")
                            print("ℹ️ 사이드바의 'Gmail 로그인' 버튼을 클릭하세요.")
                    except Exception as refresh_error:
                        print(f"❌ 토큰 재발급 실패: {refresh_error}")
                        print("ℹ️ Gmail 기능을 사용하려면 OAuth 인증이 필요합니다.")
                        print("ℹ️ 사이드바의 'Gmail 로그인' 버튼을 클릭하세요.")
                else:
                    print("🍪 DB에 Google 토큰이 없음 - 로그인 필요")
            else:
                print("🍪 사용자가 로그인되지 않음 - 로그인 필요")
        except Exception as e:
            print(f"🍪 DB 토큰 확인 실패: {e}")
            print("🍪 로그인 필요")


def create_llm_client():
    """Azure OpenAI LLM 클라이언트 생성"""
    try:
        llm_client = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            temperature=0.1,
            max_tokens=2000
        )
        print("✅ Azure OpenAI LLM 클라이언트 생성 성공")
        return llm_client
    except Exception as e:
        print(f"❌ LLM 클라이언트 생성 실패: {e}")
        raise e

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

if 'selected_ticket' not in st.session_state:
    st.session_state.selected_ticket = None

if 'llm_client' not in st.session_state:
    st.session_state.llm_client = create_llm_client()

if 'mem0_memory' not in st.session_state:
    st.session_state.mem0_memory = create_mem0_memory(st.session_state.llm_client, "chatbot_user")

# mem0 메모리를 전역적으로 사용할 수 있도록 설정
import sys
sys.modules['__main__'].mem0_memory = st.session_state.mem0_memory

if 'auto_switch_to_tickets' not in st.session_state:
    st.session_state.auto_switch_to_tickets = False

if 'ticket_message' not in st.session_state:
    st.session_state.ticket_message = ""

if 'non_work_emails' not in st.session_state:
    st.session_state.non_work_emails = []

# 페이지 설정
st.set_page_config(
    page_title="📧 FastMCP 메일 조회 챗봇",
    page_icon="🤖",
    layout="wide"
)

class RouterAgentClient:
    """라우터 에이전트 클라이언트 래퍼"""
    
    def __init__(self, llm_client):
        self.router_agent = create_router_agent(llm_client)
    
    def call_agent(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """라우터 에이전트 호출"""
        try:
            # 토큰 가져오기 (URL 파라미터 우선)
            tokens = ""
            try:
                # 1. URL 파라미터에서 토큰 확인 (최우선)
                if hasattr(st, 'query_params'):
                    access_token = st.query_params.get('access_token', '')
                    refresh_token = st.query_params.get('refresh_token', '')
                    print(f"🍪 URL 파라미터 확인: access_token={'있음' if access_token else '없음'}, refresh_token={'있음' if refresh_token else '없음'}")
                    if access_token and refresh_token:
                        # 1. 세션 상태에 저장 (앱의 현재 상태)
                        st.session_state['gmail_access_token'] = access_token
                        st.session_state['gmail_refresh_token'] = refresh_token
                        print(f"🍪 세션 상태에 토큰 저장 완료")
                        
                        # 2. URL 파라미터로 리다이렉트 (영속적 백업)
                        # 토큰을 URL 파라미터로 포함하여 리다이렉트
                        st.rerun()
                        print(f"🍪 URL 파라미터로 토큰 전달 완료")
                        
                        tokens = f"gmail_access_token={access_token}; gmail_refresh_token={refresh_token}"
                        print(f"🍪 URL 파라미터에서 토큰 가져옴: {access_token[:20]}...")
                        # URL 파라미터 제거 (보안상)
                        st.query_params.clear()
                
                # 2. 세션 상태에서 토큰 확인 (진실의 원천)
                if not tokens:
                    print(f"🍪 세션 상태에서 토큰 확인 시도...")
                    access_token = st.session_state.get('gmail_access_token', '')
                    refresh_token = st.session_state.get('gmail_refresh_token', '')
                    print(f"🍪 세션 상태 확인 결과: access_token={'있음' if access_token else '없음'}, refresh_token={'있음' if refresh_token else '없음'}")
                    if access_token and refresh_token:
                        tokens = f"gmail_access_token={access_token}; gmail_refresh_token={refresh_token}"
                        print(f"🍪 세션 상태에서 토큰 가져옴: {access_token[:20]}...")
                    else:
                        print(f"🍪 세션 상태에 토큰이 없음")
                
                if not tokens:
                    print("🍪 토큰을 찾을 수 없음")
                    
            except Exception as e:
                print(f"🍪 토큰 가져오기 실패: {e}")
            
            print(f"🍪 최종 토큰: {tokens[:100] if tokens else '없음'}...")
            
            # 토큰을 라우터 에이전트에 전달
            result = self.router_agent.execute(user_query, cookies=tokens)
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

def display_correction_ui(non_work_emails: List[Dict[str, Any]]):
    """업무용이 아니라고 판단된 메일들의 정정 UI를 표시합니다."""
    if not non_work_emails:
        return
    
    st.markdown("---")
    st.markdown("### 🔍 업무용이 아니라고 판단된 메일")
    st.markdown("※ confidence가 높은 메일들입니다. 티켓 생성이 필요하다면 정정 버튼을 클릭하세요.")
    
    for i, email in enumerate(non_work_emails):
        with st.expander(f"📧 {email.get('subject', '제목 없음')} (신뢰도: {email.get('confidence', 0):.2f})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**발신자:** {email.get('sender', 'N/A')}")
                st.markdown(f"**수신일:** {email.get('received_date', 'N/A')}")
                st.markdown(f"**판단 근거:** {email.get('reason', 'N/A')}")
                st.markdown(f"**내용 미리보기:** {email.get('body', 'N/A')}")
            
            with col2:
                if st.button(f"정정", key=f"correction_{i}", type="primary"):
                    # 정정 요청 처리
                    try:
                        from specialist_agents import create_ticketing_agent
                        
                        ticketing_agent = create_ticketing_agent()
                        correction_result = ticketing_agent.execute(
                            f"correction_tool을 사용해서 다음 메일을 정정해주세요: "
                            f"email_id={email.get('id')}, "
                            f"email_subject='{email.get('subject')}', "
                            f"email_sender='{email.get('sender')}', "
                            f"email_body='{email.get('body')}'"
                        )
                        
                        st.success("✅ 정정 완료!")
                        st.info(correction_result)
                        
                        # non_work_emails에서 해당 메일 제거
                        if hasattr(st.session_state, 'non_work_emails') and st.session_state.non_work_emails:
                            st.session_state.non_work_emails = [
                                e for e in st.session_state.non_work_emails 
                                if e.get('id') != email.get('id')
                            ]
                            
                            # 모든 메일이 정정된 경우 목록 초기화
                            if not st.session_state.non_work_emails:
                                st.session_state.has_non_work_emails = False
                        
                        # 세션 상태 업데이트
                        st.session_state.refresh_trigger += 1
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ 정정 실패: {str(e)}")

class AgentNetworkChatBot:
    """에이전트 네트워크 기반 챗봇 클래스"""
    
    def __init__(self, llm_client):
        self.router_client = RouterAgentClient(llm_client)
        self.conversation_history = st.session_state.conversation_history
    
    def process_user_input(self, user_input: str) -> str:
        """사용자 입력 처리"""
        try:
            # 라우터 에이전트 호출
            result = self.router_client.call_agent(user_input)
            
            # 응답 메시지 가져오기
            response_message = result.get("message", "응답을 생성할 수 없습니다.")
            
            # 티켓 관련 요청인지 확인하고 간단한 메시지로 변경
            simplified_message, should_switch = self._process_ticket_response(user_input, response_message)
            
            # 대화 기록에 추가
            self.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user": user_input,
                "assistant": simplified_message,
                "success": result.get("success", False),
                "tools_used": result.get("tools_used", []),
                "data": result.get("data")
            })
            
            # 세션 상태 업데이트
            st.session_state.conversation_history = self.conversation_history
            
            # 티켓 관리 탭으로 자동 전환 설정
            if should_switch:
                st.session_state.auto_switch_to_tickets = True
                st.session_state.ticket_message = simplified_message
            
            return simplified_message
            
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
    
    def _process_ticket_response(self, user_input: str, response_message: str) -> tuple[str, bool]:
        """티켓 관련 응답을 처리하고 간단한 메시지로 변경"""
        user_input_lower = user_input.lower()
        
        # 티켓 관련 키워드 확인 (OAuth 인증이 필요한 이메일 조회는 제외)
        ticket_keywords = [
            "티켓", "ticket", "메일 처리", "메일 가져와서", 
            "티켓으로", "티켓 만들어", "티켓 생성", "티켓 조회", "티켓 보여"
        ]
        
        is_ticket_request = any(keyword in user_input_lower for keyword in ticket_keywords)
        
        # OAuth 인증 메시지인지 확인 (OAuth 인증 메시지는 그대로 반환)
        oauth_keywords = ["인증", "oauth", "gmail", "로그인", "권한", "승인"]
        is_oauth_message = any(keyword in response_message.lower() for keyword in oauth_keywords)
        
        if is_oauth_message:
            # OAuth 인증 메시지는 그대로 반환
            return response_message, False
        
        if is_ticket_request:
            # 티켓 생성 요청인지 확인
            if any(keyword in user_input_lower for keyword in ["만들어", "생성", "처리", "가져와서"]):
                # Gmail API 중복 호출 방지: process_emails_with_ticket_logic 내부에서 캐싱 처리
                try:
                    from unified_email_service import process_emails_with_ticket_logic
                    result = process_emails_with_ticket_logic("gmail", user_input, st.session_state.mem0_memory)
                    non_work_emails = result.get('non_work_emails', [])
                    
                    if non_work_emails:
                        # confidence가 높은 상위 10개만 선택
                        top_non_work_emails = non_work_emails[:10]
                        
                        # 응답 메시지에 non_work_emails 정보 포함
                        response = "✅ 티켓 생성 요청을 처리했습니다.\n\n"
                        response += f"🔍 업무용이 아니라고 판단된 메일 ({len(top_non_work_emails)}개):\n\n"
                        
                        for i, email in enumerate(top_non_work_emails, 1):
                            response += f"{i}. **{email.get('subject', '제목 없음')}**\n"
                            response += f"   - 발신자: {email.get('sender', 'N/A')}\n"
                            response += f"   - 신뢰도: {email.get('confidence', 0):.2f}\n"
                            response += f"   - 판단 근거: {email.get('reason', 'N/A')}\n"
                            response += f"   - 내용 미리보기: {email.get('body', 'N/A')[:100]}...\n\n"
                        
                        # 세션 상태에 저장
                        st.session_state.non_work_emails = top_non_work_emails
                        st.session_state.has_non_work_emails = True
                        
                        return response, True
                    else:
                        st.session_state.has_non_work_emails = False
                        return "✅ 티켓 생성 요청을 처리했습니다. 티켓 관리 탭에서 결과를 확인하세요.", True
                        
                except Exception as e:
                    st.session_state.has_non_work_emails = False
                    return f"✅ 티켓 생성 요청을 처리했습니다. (오류: {str(e)}) 티켓 관리 탭에서 결과를 확인하세요.", True
            
            # 티켓 조회 요청인지 확인
            elif any(keyword in user_input_lower for keyword in ["조회", "보여", "보여줘", "확인"]):
                return "✅ 티켓 조회 요청을 처리했습니다. 티켓 관리 탭에서 티켓 목록을 확인하세요.", True
            
            # 기타 티켓 관련 요청
            else:
                return "✅ 티켓 관련 요청을 처리했습니다. 티켓 관리 탭에서 결과를 확인하세요.", True
        
        # 티켓 관련 요청이 아닌 경우 원본 응답 반환
        return response_message, False
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """대화 기록 반환"""
        return self.conversation_history
    
    def clear_conversation(self):
        """대화 기록 초기화"""
        self.conversation_history = []
        st.session_state.conversation_history = []

def main():
    """메인 애플리케이션"""
    
    print(f"🍪 main() 함수 시작")
    print(f"🍪 check_auth_and_show_ui() 호출 전")
    
    # 인증 체크 - 로그인하지 않은 사용자는 인증 UI만 표시
    if not check_auth_and_show_ui():
        print(f"🍪 인증 실패 - main() 함수 종료")
        return
    
    print(f"🍪 인증 성공 - 메인 UI 표시")
    
    # 제목
    st.title("🤖 에이전트 네트워크 메일 챗봇")
    
    st.markdown("---")
    
    # 챗봇 인스턴스 생성
    chatbot = AgentNetworkChatBot(st.session_state.llm_client)
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["💬 AI 챗봇", "🎫 티켓 관리", "📚 RAG 데이터 관리자"])
    
    # 자동 탭 전환 처리
    if st.session_state.auto_switch_to_tickets:
        st.session_state.auto_switch_to_tickets = False
        st.success(st.session_state.ticket_message)
        st.info("🎫 티켓 관리 탭으로 이동합니다...")
        st.rerun()
    
    with tab1:
        display_chat_interface(chatbot)
    
    with tab2:
        display_ticket_management()
    
    with tab3:
        create_rag_manager_tab()
    

def display_chat_interface(chatbot):
    """채팅 인터페이스 표시"""
    # 메인 채팅 인터페이스
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("💬 채팅")
        
        # non_work_emails가 있는 경우 별도 섹션으로 표시
        if hasattr(st.session_state, 'non_work_emails') and st.session_state.non_work_emails:
            st.markdown("---")
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.markdown("### 🔍 업무용이 아니라고 판단된 메일")
                st.markdown(f"※ confidence가 높은 메일 {len(st.session_state.non_work_emails)}개입니다.")
            with col_header2:
                if st.button("🗑️ 목록 지우기", key="clear_non_work_emails"):
                    st.session_state.non_work_emails = []
                    st.session_state.has_non_work_emails = False
                    # 이메일 캐시도 초기화
                    from unified_email_service import clear_email_cache
                    clear_email_cache()
                    st.rerun()
            
            for i, email in enumerate(st.session_state.non_work_emails, 1):
                with st.expander(f"📧 {i}. {email.get('subject', '제목 없음')} (신뢰도: {email.get('confidence', 0):.2f})"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**발신자:** {email.get('sender', 'N/A')}")
                        st.markdown(f"**수신일:** {email.get('received_date', 'N/A')}")
                        st.markdown(f"**판단 근거:** {email.get('reason', 'N/A')}")
                        st.markdown(f"**우선순위:** {email.get('priority', 'N/A')}")
                        st.markdown(f"**제안 라벨:** {', '.join(email.get('suggested_labels', []))}")
                    
                    with col2:
                        st.markdown(f"**신뢰도:** {email.get('confidence', 0):.2f}")
                        st.markdown(f"**티켓 타입:** {email.get('ticket_type', 'N/A')}")
                        
                        if st.button(f"정정", key=f"chat_correction_{i}", type="primary"):
                            try:
                                from specialist_agents import create_ticketing_agent
                                
                                ticketing_agent = create_ticketing_agent()
                                correction_result = ticketing_agent.execute(
                                    f"correction_tool을 사용해서 다음 메일을 정정해주세요: "
                                    f"email_id={email.get('id')}, "
                                    f"email_subject='{email.get('subject')}', "
                                    f"email_sender='{email.get('sender')}', "
                                    f"email_body='{email.get('body')}'"
                                )
                                
                                st.success("✅ 정정 완료!")
                                st.info(correction_result)
                                
                                # non_work_emails에서 해당 메일 제거
                                if hasattr(st.session_state, 'non_work_emails') and st.session_state.non_work_emails:
                                    st.session_state.non_work_emails = [
                                        e for e in st.session_state.non_work_emails 
                                        if e.get('id') != email.get('id')
                                    ]
                                    
                                    # 모든 메일이 정정된 경우 목록 초기화
                                    if not st.session_state.non_work_emails:
                                        st.session_state.has_non_work_emails = False
                                
                                # 세션 상태 업데이트
                                st.session_state.refresh_trigger += 1
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ 정정 실패: {str(e)}")
                    
                    # 메일 내용 미리보기
                    st.markdown("**내용 미리보기:**")
                    st.text_area("메일 내용", email.get('body', 'N/A'), height=100, key=f"preview_{i}", label_visibility="collapsed")
            
            st.markdown("---")
        
        # 대화 기록 표시
        for i, message in enumerate(chatbot.get_conversation_history()):
            with st.expander(f"💬 대화 {i+1} - {message['timestamp'][:19]}"):
                st.markdown(f"**👤 사용자:** {message['user']}")
                
                # 어시스턴트 응답 표시 (non_work_emails가 포함된 경우 특별 처리)
                assistant_response = message['assistant']
                if "업무용이 아니라고 판단된 메일" in assistant_response:
                    # non_work_emails가 포함된 응답인 경우 마크다운으로 렌더링
                    st.markdown(assistant_response)
                else:
                    st.markdown(f"**🤖 어시스턴트:** {assistant_response}")
                
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
            "안 읽은 메일을 가져와서 티켓을 생성해주세요",
            "안 읽은 메일 3개만 가져와서 보여주세요"
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

def display_ticket_management():
    """티켓 관리 인터페이스 표시"""
    st.header("🎫 티켓 관리 시스템")
    
    # 새로고침 버튼
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔄 새로고침"):
            st.session_state.refresh_trigger += 1
            st.rerun()
    
    with col2:
        if st.button("🤖 전체 AI 추천"):
            with st.spinner("모든 티켓에 대한 AI 추천을 생성하고 있습니다..."):
                tickets = load_tickets_from_db()
                if tickets:
                    recommendations = []
                    for ticket in tickets[:3]:  # 최대 3개 티켓만 처리
                        recommendation = get_ticket_ai_recommendation(ticket.ticket_id)
                        if recommendation.get("success"):
                            recommendations.append({
                                "ticket_id": ticket.ticket_id,
                                "title": ticket.title,
                                "recommendation": recommendation.get("recommendation", "")
                            })
                    
                    if recommendations:
                        st.session_state["bulk_recommendations"] = recommendations
                        st.success(f"✅ {len(recommendations)}개 티켓의 AI 추천이 생성되었습니다!")
                    else:
                        st.warning("AI 추천을 생성할 수 없습니다.")
                else:
                    st.info("추천할 티켓이 없습니다.")
    
    # 정정 UI 표시 (non_work_emails가 있는 경우)
    if hasattr(st.session_state, 'has_non_work_emails') and st.session_state.has_non_work_emails:
        # 세션 상태에 저장된 non_work_emails 데이터 사용 (중복 실행 방지)
        non_work_emails = st.session_state.get('non_work_emails', [])
        if non_work_emails:
            display_correction_ui(non_work_emails)
    
    
    # 대량 AI 추천 결과 표시
    if "bulk_recommendations" in st.session_state:
        st.subheader("🤖 전체 AI 추천 결과")
        recommendations = st.session_state["bulk_recommendations"]
        
        for rec in recommendations:
            with st.expander(f"🎫 티켓 #{rec['ticket_id']}: {rec['title']}", expanded=False):
                st.markdown(rec["recommendation"])
        
        if st.button("🗑️ 추천 결과 지우기"):
            del st.session_state["bulk_recommendations"]
            st.rerun()
    
    # 티켓 목록 또는 상세 보기
    if st.session_state.selected_ticket:
        display_ticket_detail(st.session_state.selected_ticket)
    else:
        # 티켓 목록 표시
        tickets = load_tickets_from_db()
        st.session_state.tickets = tickets
        display_ticket_button_list(tickets)

if __name__ == "__main__":
    main()
