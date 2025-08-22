#!/usr/bin/env python3
"""
메일 조회 챗봇 앱
사용자와 LLM이 대화하면서 MCP 툴을 호출하여 메일 정보를 제공
"""

import streamlit as st
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from mcp_client import SimpleMCPClient

# 페이지 설정
st.set_page_config(
    page_title="📧 메일 조회 챗봇",
    page_icon="🤖",
    layout="wide"
)

class MCPToolCaller:
    """MCP 툴 호출 클래스"""
    
    def __init__(self, mcp_server_script: str = "json_mail_mcp_server.py"):
        self.mcp_client = SimpleMCPClient(mcp_server_script)
    
    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """MCP 툴 호출 (동기 방식)"""
        return self.mcp_client.call_tool(tool_name, arguments)

class ChatBot:
    """챗봇 클래스"""
    
    def __init__(self):
        self.mcp_caller = MCPToolCaller()
        self.conversation_history = []
    
    def parse_user_intent(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력에서 의도 파악"""
        user_input_lower = user_input.lower()
        
        # 안읽은 메일 요청
        if any(keyword in user_input_lower for keyword in ["안읽은", "안 읽은", "새", "새로운", "unread"]):
            return {
                "tool": "get_unread_emails",
                "arguments": {}
            }
        
        # 전체 메일 요청
        elif any(keyword in user_input_lower for keyword in ["전체", "모든", "all", "전부"]):
            return {
                "tool": "get_all_emails", 
                "arguments": {}
            }
        
        # 검색 요청 (키워드 포함)
        elif any(keyword in user_input_lower for keyword in ["찾", "검색", "search", "관련"]):
            # 검색 키워드 추출 (간단한 방식)
            search_keywords = []
            for word in user_input.split():
                if len(word) > 1 and word not in ["메일", "이메일", "찾아", "검색", "보여줘", "해줘"]:
                    search_keywords.append(word)
            
            if search_keywords:
                return {
                    "tool": "search_emails",
                    "arguments": {"query": " ".join(search_keywords)}
                }
        
        # 발신자별 메일 요청
        elif any(keyword in user_input_lower for keyword in ["에서", "가 보낸", "로부터", "from"]):
            # 발신자 이름 추출 시도
            import re
            # "XX에서 온 메일" 패턴
            match = re.search(r'(\w+)에서', user_input)
            if match:
                return {
                    "tool": "get_emails_by_sender",
                    "arguments": {"sender": match.group(1)}
                }
            
            # "XX가 보낸" 패턴  
            match = re.search(r'(\w+)가?\s*보낸', user_input)
            if match:
                return {
                    "tool": "get_emails_by_sender",
                    "arguments": {"sender": match.group(1)}
                }
        
        # 기본값: 안읽은 메일
        return {
            "tool": "get_unread_emails",
            "arguments": {}
        }
    
    def process_user_message(self, user_input: str) -> str:
        """사용자 메시지 처리"""
        try:
            # 사용자 의도 파악
            intent = self.parse_user_intent(user_input)
            
            # MCP 툴 호출 (동기 방식)
            tool_result = self.mcp_caller.call_mcp_tool(
                intent["tool"], 
                intent["arguments"]
            )
            
            # 대화 기록 저장
            self.conversation_history.append({
                "user": user_input,
                "bot": tool_result,
                "timestamp": datetime.now().isoformat(),
                "tool_used": intent["tool"]
            })
            
            return tool_result
            
        except Exception as e:
            error_msg = f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}"
            self.conversation_history.append({
                "user": user_input,
                "bot": error_msg,
                "timestamp": datetime.now().isoformat(),
                "tool_used": "error"
            })
            return error_msg

def init_session_state():
    """세션 상태 초기화"""
    if 'chatbot' not in st.session_state:
        st.session_state.chatbot = ChatBot()
    if 'messages' not in st.session_state:
        st.session_state.messages = []

def main():
    st.title("🤖 메일 조회 챗봇")
    st.markdown("안녕하세요! 메일에 대해 궁금한 것을 자연어로 물어보세요.")
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바 - 도움말
    with st.sidebar:
        st.header("💡 사용 예시")
        st.markdown("""
        **안읽은 메일 조회:**
        - "안읽은 메일 보여줘"
        - "새 메일 있어?"
        - "읽지 않은 메일"
        
        **전체 메일 조회:**
        - "전체 메일 보여줘"
        - "모든 메일"
        
        **메일 검색:**
        - "회의 관련 메일 찾아줘"
        - "프로젝트 메일 검색"
        - "중요한 메일"
        
        **발신자별 조회:**
        - "Microsoft에서 온 메일"
        - "Nilesh가 보낸 메일"
        """)
        
        st.header("📊 대화 통계")
        total_messages = len(st.session_state.messages)
        st.metric("총 대화 수", total_messages)
        
        if st.button("🗑️ 대화 기록 삭제"):
            st.session_state.messages = []
            st.session_state.chatbot = ChatBot()
            st.rerun()
    
    # 메인 채팅 영역
    chat_container = st.container()
    
    # 대화 기록 표시
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # 사용자 입력
    if prompt := st.chat_input("메일에 대해 물어보세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
        
        # 봇 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("메일을 확인하고 있습니다..."):
                # 동기 방식으로 처리
                response = st.session_state.chatbot.process_user_message(prompt)
                st.markdown(response)
        
        # 봇 응답을 세션에 저장
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # 하단 정보
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("💬 자연어로 편하게 물어보세요!")
    
    with col2:
        st.info("🔍 메일 검색, 필터링 지원")
    
    with col3:
        st.info("📊 실시간 메일 데이터 조회")

if __name__ == "__main__":
    main()