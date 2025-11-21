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

# 로깅 설정 추가
from module.logging_config import setup_logging
import logging

# 로깅 초기화
setup_logging(level="INFO", log_file="logs/fastmcp_chatbot_app.log", console_output=True)
logger = logging.getLogger(__name__)

# LangChain imports
from langchain_openai import AzureChatOpenAI

# 라우터 에이전트 import - 제거됨 (이메일 기능 제거로 불필요)
# from router_agent import create_router_agent

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

# 월간보고 JQL 생성기 import
from utils.prompt_parser import generate_jql_from_prompts, display_jql_results

# 인증 관련 import
from auth_client import auth_client
from auth_ui import check_auth_and_show_ui, show_integration_settings

# 프롬프트 관리 import
from models.report_models import DatabaseManager
from services.prompt_service import PromptService

# 프롬프트 DB 초기화
prompt_db_manager = DatabaseManager(os.getenv('REPORTS_DB_PATH', 'reports.db'))
prompt_db_manager.create_tables()

# Gmail/Outlook 연동 제거됨 (보안 정책)


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
    # 통일: 커스텀 Mem0 백엔드 사용 (llm_client 미전달) + 동일 user_id
    st.session_state.mem0_memory = create_mem0_memory("ticket_ui")

# mem0 메모리를 전역적으로 사용할 수 있도록 설정
import sys
sys.modules['__main__'].mem0_memory = st.session_state.mem0_memory

if 'auto_switch_to_tickets' not in st.session_state:
    st.session_state.auto_switch_to_tickets = False

if 'ticket_message' not in st.session_state:
    st.session_state.ticket_message = ""

# 페이지 설정
st.set_page_config(
    page_title="📧 FastMCP 메일 조회 챗봇",
    page_icon="🤖",
    layout="wide"
)

class RouterAgentClient:
    """라우터 에이전트 클라이언트 래퍼 - RAG 파이프라인 통합 (RRF 지원)"""

    def __init__(self, llm_client):
        self.llm_client = llm_client

        # RRF 시스템 초기화 (우선)
        self.rrf_system = None
        try:
            from rrf_fusion_rag_system import RRFRAGSystem
            self.rrf_system = RRFRAGSystem("jira_chunks")
            print("✅ RAG: RRF 시스템 초기화 완료 (멀티쿼리 + HyDE + RRF 융합)")
        except Exception as e:
            print(f"⚠️ RAG: RRF 시스템 초기화 실패, 기본 검색으로 폴백: {e}")

        # ChromaDB 클라이언트 초기화 (폴백용)
        from chromadb_singleton import get_chromadb_collection
        self.jira_collection = None
        try:
            self.jira_collection = get_chromadb_collection("jira_chunks", create_if_not_exists=False)
            print("✅ RAG: jira_chunks 컬렉션 로드 성공 (폴백용)")
        except Exception as e:
            print(f"⚠️ RAG: jira_chunks 컬렉션 없음 (동기화 필요): {e}")

    def search_knowledge_base(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        ChromaDB에서 관련 문서 검색 (RRF 기반 멀티쿼리 + HyDE)

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 문서 수

        Returns:
            검색된 문서 리스트
        """
        # 1. RRF 시스템 사용 (우선)
        if self.rrf_system:
            try:
                print(f"🚀 RRF 기반 검색: '{query}' (멀티쿼리 + HyDE + Rank Fusion)")
                rrf_results = self.rrf_system.rrf_search(query)

                if rrf_results:
                    # RRF 결과를 기존 형식으로 변환
                    documents = []
                    for result in rrf_results[:top_k]:
                        content = result.get('content', '')
                        metadata = result.get('metadata', {})
                        score = result.get('score', result.get('cosine_score', 0.0))

                        documents.append({
                            "content": content,
                            "metadata": metadata,
                            "distance": 1 - score,  # score -> distance 변환
                            "similarity": score,
                            "rrf_rank": result.get('rrf_rank', 0),
                            "search_method": "rrf_fusion"
                        })

                    print(f"✅ RRF 검색 완료: {len(documents)}개 결과")
                    return documents
                else:
                    print("⚠️ RRF 검색 결과 없음, 폴백 검색 시도")
            except Exception as e:
                print(f"⚠️ RRF 검색 실패, 기본 검색으로 폴백: {e}")

        # 2. 기본 ChromaDB 검색 (폴백)
        if not self.jira_collection:
            return []

        try:
            print(f"🔍 기본 벡터 검색: '{query}'")
            results = self.jira_collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # 결과 파싱
            documents = []
            if results and results.get("documents") and len(results["documents"]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 1.0

                    documents.append({
                        "content": doc,
                        "metadata": metadata,
                        "distance": distance,
                        "similarity": 1 - distance,  # cosine distance -> similarity
                        "search_method": "basic_vector"
                    })

            print(f"✅ 기본 검색 완료: {len(documents)}개 결과")
            return documents
        except Exception as e:
            print(f"❌ RAG 검색 실패: {e}")
            return []

    def build_rag_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        검색된 문서들을 RAG context로 구성

        Args:
            documents: 검색된 문서 리스트

        Returns:
            포맷된 context 문자열
        """
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            metadata = doc.get("metadata", {})
            content = doc.get("content", "")
            similarity = doc.get("similarity", 0)

            # 메타데이터에서 주요 정보 추출
            issue_key = metadata.get("issue_key", "N/A")
            source_type = metadata.get("source_type", "unknown")

            context_parts.append(
                f"[문서 {i}] (유사도: {similarity:.2f})\n"
                f"이슈: {issue_key}\n"
                f"타입: {source_type}\n"
                f"내용: {content}\n"
            )

        return "\n---\n".join(context_parts)

    def call_agent(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """에이전트 호출 - RAG 파이프라인 적용"""
        try:
            # 이메일 관련 기능이 제거되었으므로 안내 메시지 제공
            if any(keyword in user_query.lower() for keyword in ["메일", "email", "이메일", "gmail", "outlook"]):
                message = """
📧 **이메일 연동 기능이 제거되었습니다** (보안 정책)

현재 사용 가능한 기능:
✅ Jira 티켓 조회 및 관리 (RAG 지원)
✅ Kakao 알림 발송
✅ Slack 메시지 발송
📊 월간보고는 웹 인터페이스(http://localhost:8002/editor)를 이용해주세요

다른 기능을 이용해주세요!
                """
                return {
                    "success": True,
                    "message": message.strip(),
                    "data": None,
                    "tools_used": ["info"],
                    "query": user_query
                }

            # RAG: ChromaDB에서 관련 문서 검색
            print(f"🔍 RAG 검색 시작: {user_query}")
            related_docs = self.search_knowledge_base(user_query, top_k=5)

            if related_docs:
                # RAG context 구성
                rag_context = self.build_rag_context(related_docs)
                print(f"📚 RAG: {len(related_docs)}개 문서 검색됨")

                # RAG 프롬프트 템플릿
                rag_prompt = f"""다음은 Jira 이슈 데이터베이스에서 검색된 관련 정보입니다:

{rag_context}

---

위 정보를 참고하여 다음 질문에 답변해주세요:
질문: {user_query}

답변 시 주의사항:
1. 검색된 문서의 내용을 기반으로 정확하게 답변하세요
2. 이슈 키(예: NCMS-1234)를 언급할 때는 정확히 표기하세요
3. 검색된 정보에 없는 내용은 추측하지 말고 "해당 정보를 찾을 수 없습니다"라고 답변하세요
4. 한국어로 자연스럽게 답변하세요
"""

                # LLM 호출 (RAG context 포함)
                response = self.llm_client.invoke(rag_prompt)
                return {
                    "success": True,
                    "message": response.content if hasattr(response, 'content') else str(response),
                    "data": {"related_docs": related_docs},
                    "tools_used": ["rag", "llm"],
                    "query": user_query,
                    "rag_docs_count": len(related_docs)
                }
            else:
                # RAG 검색 결과 없음 - 일반 LLM 응답
                print("⚠️ RAG: 관련 문서 없음, 일반 LLM 응답")
                fallback_prompt = f"""질문: {user_query}

답변: Jira 데이터베이스에서 관련 정보를 찾을 수 없었습니다.
Jira 동기화가 완료되지 않았거나, 검색어와 관련된 이슈가 없을 수 있습니다.

다음을 확인해주세요:
1. Jira 연동이 완료되었는지 확인 (🔧 Jira 관리 탭)
2. Jira 동기화를 실행했는지 확인 (증분 동기화 버튼)
3. 검색어를 다르게 표현해보세요 (예: 이슈 키, 프로젝트명, 키워드 등)

일반적인 질문이라면 답변 가능합니다. 무엇을 도와드릴까요?
"""
                response = self.llm_client.invoke(fallback_prompt)
                return {
                    "success": True,
                    "message": response.content if hasattr(response, 'content') else str(response),
                    "data": None,
                    "tools_used": ["llm"],
                    "query": user_query,
                    "rag_docs_count": 0
                }
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"❌ RAG 처리 중 오류:\n{error_detail}")
            return {
                "success": False,
                "message": f"처리 중 오류가 발생했습니다: {str(e)}",
                "data": None,
                "tools_used": [],
                "error": str(e),
                "query": user_query
            }

    def get_server_status(self) -> Dict[str, Any]:
        """서버 상태 확인"""
        return {
            "status": "running",
            "agent_type": "simplified_agent",
            "available_features": ["Jira", "Kakao", "Slack"],
            "message": "이메일 기능 제거 - Jira/Kakao/Slack 연동 사용 가능. 월간보고는 http://localhost:8002/editor 이용"
        }

# display_correction_ui 함수 제거됨 (Gmail 연동 제거)

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

            # SpecialistAgent에서 이미 세션 상태에 저장됨

            # 티켓 관련 요청인지 확인하고 간단한 메시지로 변경
            simplified_message, should_switch = self._process_ticket_response(user_input, response_message, result.get("data"))
            
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
    
    def _process_ticket_response(self, user_input: str, response_message: str, data: Dict[str, Any] = None) -> tuple[str, bool]:
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
                # SpecialistAgent에서 이미 세션 상태 처리 완료
                return "✅ 티켓 생성 요청을 처리했습니다. 티켓 관리 탭에서 결과를 확인하세요.", True
            
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

    print(f"🍪 인증 성공 - 온보딩 체크 시작")

    # 온보딩 완료 여부 확인
    if 'onboarding_completed' not in st.session_state:
        st.session_state.onboarding_completed = False

    # 온보딩 미완료 시 온보딩 화면만 표시
    if not st.session_state.onboarding_completed:
        print(f"🚀 온보딩 미완료 - 온보딩 UI 표시")
        from onboarding_ui import show_onboarding_process

        # 현재 로그인된 사용자 이메일 가져오기
        user_email = st.session_state.get('user_email', '')

        # 온보딩 프로세스 표시
        is_complete = show_onboarding_process(user_email)

        # 온보딩 완료 시 세션 상태 업데이트
        if is_complete and st.session_state.get('onboarding_completed', False):
            print(f"✅ 온보딩 완료 - 메인 UI로 이동")
            st.rerun()

        return

    print(f"🍪 온보딩 완료 - 메인 UI 표시")

    # 제목
    st.title("🤖 에이전트 네트워크 메일 챗봇")

    st.markdown("---")

    # 챗봇 인스턴스 생성
    chatbot = AgentNetworkChatBot(st.session_state.llm_client)

    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["💬 AI 챗봇", "🎫 티켓 관리", "📚 RAG 데이터 관리자", "🔧 Jira 관리"])

    # 자동 탭 전환 처리
    if st.session_state.auto_switch_to_tickets:
        st.session_state.auto_switch_to_tickets = False
        st.success(st.session_state.ticket_message)
        st.info("🎫 티켓 관리 탭으로 이동합니다...")
        st.rerun()

    with tab1:
        display_chat_interface(chatbot)

    with tab2:
        display_ticket_management_with_async()

    with tab3:
        create_rag_manager_tab()

    with tab4:
        from jira_management_ui import render_jira_management
        from auth_client import AuthClient
        auth_client = AuthClient()
        render_jira_management(auth_client)


def display_chat_interface(chatbot):
    """채팅 인터페이스 표시"""
    # 메인 채팅 인터페이스
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("💬 채팅")
        
        # 디버깅: 세션 상태 확인
        st.markdown("### 🔍 디버깅 정보")
        st.write(f"**non_work_emails 존재**: {hasattr(st.session_state, 'non_work_emails')}")
        st.write(f"**non_work_emails 개수**: {len(st.session_state.get('non_work_emails', []))}")
        st.write(f"**has_non_work_emails**: {st.session_state.get('has_non_work_emails', False)}")

        if hasattr(st.session_state, 'non_work_emails') and st.session_state.non_work_emails:
            st.write(f"**첫 번째 메일 제목**: {st.session_state.non_work_emails[0].get('subject', 'N/A')}")

        # non_work_emails가 있는 경우 새로운 UI로 표시
        if hasattr(st.session_state, 'non_work_emails') and st.session_state.non_work_emails:
            st.markdown("---")
            st.info("📧 메일 연동 기능이 제거되었습니다 (보안 정책)")
        else:
            st.info("📧 현재 업무용이 아닌 메일이 없습니다.")
        
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
            "최근 메일을 가져와서 티켓을 생성해주세요",
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
    
    # 정정 UI 제거됨 (Gmail 연동 제거)
    
    
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

def display_ticket_management_with_async():
    """비동기 기능이 통합된 티켓 관리 인터페이스"""
    st.header("🎫 티켓 관리 시스템")

    # 비동기 티켓 생성 기능 제거됨 (보안 정책)
    st.info("📧 비동기 티켓 생성 기능이 제거되었습니다 (보안 정책)")

    # 기존 티켓 관리 기능 유지
    st.markdown("---")
    st.subheader("📋 티켓 관리")

    # 새로고침 버튼
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔄 새로고침", key="legacy_refresh"):
            st.session_state.refresh_trigger += 1
            st.rerun()

    with col2:
        if st.button("🤖 전체 AI 추천", key="legacy_ai_recommend"):
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
                        st.info("추천할 티켓이 없습니다.")
                else:
                    st.info("추천할 티켓이 없습니다.")

    # 정정 UI 제거됨 (Gmail 연동 제거)

    # 대량 AI 추천 결과 표시
    if "bulk_recommendations" in st.session_state:
        st.subheader("🤖 전체 AI 추천 결과")
        recommendations = st.session_state["bulk_recommendations"]

        for rec in recommendations:
            with st.expander(f"🎫 티켓 #{rec['ticket_id']}: {rec['title']}", expanded=False):
                st.markdown(rec["recommendation"])

        if st.button("🗑️ 추천 결과 지우기", key="clear_bulk_recommendations"):
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

def display_monthly_report_tab():
    """월간보고 JQL 생성기 탭"""
    st.title("📊 월간보고 자동화")

    # 메인 탭: V1(JQL 생성기) / V2(템플릿 기반)
    tab1, tab2 = st.tabs(["📝 JQL 생성기 (V1)", "🎨 템플릿 기반 보고서 (V2)"])

    with tab1:
        display_monthly_report_generation()

    with tab2:
        # 가장 간단한 테스트
        st.title("🎨 템플릿 기반 보고서 V2")
        st.success("✅ 이 메시지가 보이면 tab2가 작동합니다!")

        st.divider()

        st.write("🔍 DEBUG: Tab2 블록 진입")
        st.write(f"🔍 DEBUG: 세션 상태 키들: {list(st.session_state.keys())}")

        # V2 UI 호출
        try:
            st.write("🔍 DEBUG: import 시도 중...")
            from ui.monthly_report_v2_ui import display_monthly_report_v2_tab
            st.write("🔍 DEBUG: import 성공")

            # 디버깅 정보 표시
            user_id = st.session_state.get('user_id')
            llm_client = st.session_state.get('llm_client')

            st.write(f"🔍 DEBUG: user_id={user_id}, llm_client={type(llm_client).__name__ if llm_client else None}")

            if not user_id:
                st.warning("⚠️ 로그인이 필요합니다")
                st.info("좌측 사이드바에서 먼저 로그인해주세요.")
                st.stop()

            if not llm_client:
                st.error("❌ LLM 클라이언트가 초기화되지 않았습니다")
                st.info("Azure OpenAI 설정을 확인해주세요.")
                st.stop()

            st.write("🔍 DEBUG: display_monthly_report_v2_tab 호출 시작")

            # V2 UI 표시
            display_monthly_report_v2_tab(
                llm_client=llm_client,
                user_id=user_id
            )

            st.write("🔍 DEBUG: display_monthly_report_v2_tab 호출 완료")

        except Exception as e:
            st.error(f"❌ V2 UI 로딩 중 오류 발생: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


# ============================================================
# 프롬프트 관리 함수들
# ============================================================

def get_prompt_service():
    """PromptService 인스턴스 생성"""
    session = prompt_db_manager.get_session()
    return PromptService(session), session


def save_prompt_template(prompt_content: str, template_title: str, category: str = "월간보고",
                        system: str = None):
    """프롬프트 템플릿 저장 (단순 텍스트)"""
    if not auth_client.is_logged_in():
        st.error("⚠️ 로그인이 필요합니다")
        return False

    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("⚠️ 사용자 정보를 가져올 수 없습니다")
        return False

    prompt_service, session = get_prompt_service()

    try:
        prompt_data = {
            'title': template_title,
            'category': category,
            'description': '프롬프트 템플릿',
            'prompt_content': prompt_content,
            'is_public': False,
            'order_index': 999,
            'system': system
        }

        prompt_id = prompt_service.create_prompt(user_id, prompt_data)

        st.success(f"✅ 프롬프트 템플릿 '{template_title}'이(가) 저장되었습니다 (ID: {prompt_id})")
        return True
    except Exception as e:
        st.error(f"❌ 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        session.close()


def save_current_prompts_to_template(pages_data: List[Dict], template_title: str, category: str = "월간보고",
                                     system: str = None):
    """현재 입력된 프롬프트들을 템플릿으로 저장"""
    if not auth_client.is_logged_in():
        st.error("⚠️ 로그인이 필요합니다")
        return False

    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("⚠️ 사용자 정보를 가져올 수 없습니다")
        return False

    prompt_service, session = get_prompt_service()

    try:
        # 여러 페이지를 하나의 템플릿으로 저장 (JSON 형식)
        prompt_content = json.dumps(pages_data, ensure_ascii=False, indent=2)

        prompt_data = {
            'title': template_title,
            'category': category,
            'description': f'{len(pages_data)}개 페이지 포함',
            'prompt_content': prompt_content,
            'is_public': False,
            'order_index': 999,
            'system': system
        }

        prompt_id = prompt_service.create_prompt(user_id, prompt_data)

        st.success(f"✅ 프롬프트 템플릿 '{template_title}'이(가) 저장되었습니다 (ID: {prompt_id})")
        return True
    except Exception as e:
        st.error(f"❌ 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        session.close()


def load_saved_prompts(category=None):
    """저장된 프롬프트 템플릿 목록 가져오기

    Args:
        category: 카테고리 이름 (None이면 모든 카테고리)
    """
    if not auth_client.is_logged_in():
        return []

    user_id = st.session_state.get('user_id')
    if not user_id:
        return []

    prompt_service, session = get_prompt_service()

    try:
        result = prompt_service.get_user_prompts(user_id, include_public=False)
        my_prompts = result.get('my_prompts', [])

        # 카테고리 필터링
        if category is not None:
            my_prompts = [p for p in my_prompts if p.get('category') == category]

        return my_prompts
    except Exception as e:
        st.error(f"❌ 프롬프트 불러오기 실패: {str(e)}")
        return []
    finally:
        session.close()


def load_prompt_by_id(prompt_id: int):
    """특정 프롬프트 템플릿 불러오기"""
    if not auth_client.is_logged_in():
        return None

    user_id = st.session_state.get('user_id')
    if not user_id:
        return None

    prompt_service, session = get_prompt_service()

    try:
        prompt = prompt_service.get_prompt_by_id(prompt_id, user_id)
        if prompt:
            return prompt.to_dict(include_content=True)
        return None
    except Exception as e:
        st.error(f"❌ 프롬프트 불러오기 실패: {str(e)}")
        return None
    finally:
        session.close()


def delete_prompt_template(prompt_id: int):
    """프롬프트 템플릿 삭제"""
    if not auth_client.is_logged_in():
        st.error("⚠️ 로그인이 필요합니다")
        return False

    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("⚠️ 사용자 정보를 가져올 수 없습니다")
        return False

    prompt_service, session = get_prompt_service()

    try:
        prompt_service.delete_prompt(user_id, prompt_id)
        st.success("✅ 프롬프트 템플릿이 삭제되었습니다")
        return True
    except Exception as e:
        st.error(f"❌ 삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        session.close()


def update_prompt_template(prompt_id: int, template_title: str, category: str, prompt_content: str):
    """프롬프트 템플릿 수정"""
    if not auth_client.is_logged_in():
        st.error("⚠️ 로그인이 필요합니다")
        return False

    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("⚠️ 사용자 정보를 가져올 수 없습니다")
        return False

    prompt_service, session = get_prompt_service()

    try:
        # 프롬프트 업데이트
        update_data = {
            'title': template_title,
            'category': category,
            'description': '프롬프트 템플릿',
            'prompt_content': prompt_content
        }

        prompt_service.update_prompt(user_id, prompt_id, update_data)

        st.success(f"✅ 프롬프트 템플릿 '{template_title}'이(가) 수정되었습니다")
        return True
    except Exception as e:
        st.error(f"❌ 수정 중 오류 발생: {str(e)}")
        return False
    finally:
        session.close()


def display_monthly_report_generation():
    """월간보고 생성 UI (V1 - 그룹 기능 제거됨)"""

    st.info("ℹ️ V1 (JQL 생성기)는 그룹 기능이 제거되어 현재 사용할 수 없습니다.")
    st.success("✨ **V2 (템플릿 기반 보고서)** 탭을 사용해주세요!")

    st.divider()

    st.markdown("""
    ### 🎨 V2로 이동하세요

    V2에서는 다음 기능을 사용할 수 있습니다:
    - 📝 프롬프트 관리 (CRUD)
    - ▶️ 프롬프트 실행 (캐싱 지원)
    - 📄 템플릿 관리 (Markdown + placeholder)
    - 🎨 보고서 생성 (HTML 출력)
    - 📈 집계/분석 (Jira 이슈 통계)
    """)


    st.info("""
💡 **그룹 협업 기능**
- 팀원들과 함께 그룹을 만들고 프롬프트를 공유할 수 있습니다
- 각 멤버가 담당하는 시스템(NCMS, EUXP, EDMP 등)을 설정할 수 있습니다
- 그룹 보고서를 생성하면 시스템별로 자동 통합됩니다
    """)

    # 세션 상태 초기화
    if 'selected_group_id' not in st.session_state:
        st.session_state.selected_group_id = None
    if 'show_create_group_form' not in st.session_state:
        st.session_state.show_create_group_form = False

    # 그룹 목록 조회
    groups_result = auth_client.get_groups()

    if not groups_result.get("success"):
        st.error(f"그룹 목록을 불러올 수 없습니다: {groups_result.get('message')}")
        return

    groups = groups_result.get("groups", [])

    # 그룹 생성 버튼
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("+ 새 그룹 만들기", use_container_width=True):
            st.session_state.show_create_group_form = True
            st.rerun()

    # 그룹 생성 폼
    if st.session_state.show_create_group_form:
        with st.form("create_group_form"):
            st.subheader("새 그룹 만들기")
            group_name = st.text_input("그룹 이름 *", placeholder="예: OTT운영팀")
            group_description = st.text_area("설명", placeholder="그룹에 대한 간단한 설명")

            col_submit, col_cancel = st.columns(2)
            with col_submit:
                submitted = st.form_submit_button("생성", use_container_width=True)
            with col_cancel:
                if st.form_submit_button("취소", use_container_width=True):
                    st.session_state.show_create_group_form = False
                    st.rerun()

            if submitted:
                if not group_name.strip():
                    st.error("그룹 이름을 입력해주세요")
                else:
                    result = auth_client.create_group(group_name.strip(), group_description.strip() or None)
                    if result.get("success"):
                        st.success(f"✅ 그룹 '{group_name}'이 생성되었습니다!")
                        st.session_state.show_create_group_form = False
                        st.rerun()
                    else:
                        st.error(f"그룹 생성 실패: {result.get('message')}")

    st.markdown("---")

    # 그룹 목록
    if not groups:
        st.info("아직 그룹이 없습니다. 새 그룹을 만들어보세요!")
        return

    # 그룹이 선택되지 않은 경우: 그룹 목록 표시
    if not st.session_state.selected_group_id:
        st.subheader("내 그룹")

        for group in groups:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(f"### {group['name']}")
                    if group.get('description'):
                        st.caption(group['description'])

                with col2:
                    role_emoji = "👑" if group['role'] == 'owner' else "👤"
                    role_text = "Owner" if group['role'] == 'owner' else "Member"
                    st.info(f"{role_emoji} {role_text}")

                with col3:
                    if st.button("상세보기", key=f"view_{group['id']}", use_container_width=True):
                        st.session_state.selected_group_id = group['id']
                        st.rerun()

                # 그룹 정보
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.caption(f"👥 {group.get('member_count', 0)}명")
                with info_col2:
                    st.caption(f"📝 {group.get('prompt_count', 0)}개 프롬프트")

                st.markdown("---")

    # 그룹이 선택된 경우: 그룹 상세 정보
    else:
        if st.button("← 그룹 목록으로"):
            st.session_state.selected_group_id = None
            st.rerun()

        # 그룹 상세 정보 조회
        detail_result = auth_client.get_group_detail(st.session_state.selected_group_id)

        if not detail_result.get("success"):
            st.error(f"그룹 정보를 불러올 수 없습니다: {detail_result.get('message')}")
            st.session_state.selected_group_id = None
            return

        group_data = detail_result.get("data", {})
        group_info = group_data.get("group", {})
        members = group_data.get("members", [])
        prompts = group_data.get("prompts", [])

        st.subheader(f"📁 {group_info.get('name')}")
        if group_info.get('description'):
            st.caption(group_info['description'])

        # 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs(["👥 멤버", "📝 프롬프트", "📂 카테고리", "⚙️ 설정"])

        with tab1:
            st.subheader("그룹 멤버")

            # Owner만 멤버 추가 가능
            if group_info.get('role') == 'owner':
                with st.expander("➕ 멤버 추가"):
                    with st.form("add_member_form"):
                        new_user_id = st.number_input("사용자 ID", min_value=1, step=1)
                        system = st.text_input("담당 시스템 (선택)", placeholder="예: NCMS, EUXP, EDMP")

                        if st.form_submit_button("추가"):
                            result = auth_client.add_group_member(
                                st.session_state.selected_group_id,
                                new_user_id,
                                system.strip() or None
                            )
                            if result.get("success"):
                                st.success("✅ 멤버가 추가되었습니다!")
                                st.rerun()
                            else:
                                st.error(f"멤버 추가 실패: {result.get('message')}")

            # 멤버 목록
            if members:
                for member in members:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                    with col1:
                        role_badge = "👑 Owner" if member['role'] == 'owner' else "👤 Member"
                        username = member.get('username', member.get('email', 'Unknown'))
                        st.markdown(f"**{username}** {role_badge}")
                        st.caption(f"Email: {member.get('email', 'N/A')}")

                    with col2:
                        if member.get('system'):
                            st.info(f"📌 {member['system']}")

                    with col3:
                        st.caption(f"가입: {member['joined_at'][:10]}")

                    with col4:
                        # Owner만 멤버 제거 가능 (본인 제외)
                        if group_info.get('role') == 'owner' and member['role'] != 'owner':
                            if st.button("제거", key=f"remove_{member['user_id']}"):
                                result = auth_client.remove_group_member(
                                    st.session_state.selected_group_id,
                                    member['user_id']
                                )
                                if result.get("success"):
                                    st.success("✅ 멤버가 제거되었습니다!")
                                    st.rerun()
                                else:
                                    st.error(f"멤버 제거 실패: {result.get('message')}")

                    st.markdown("---")
            else:
                st.info("아직 멤버가 없습니다")

        with tab2:
            st.subheader("그룹 프롬프트")

            prompts_by_category = group_data.get("prompts_by_category", {})

            if prompts_by_category:
                for category, category_prompts in prompts_by_category.items():
                    st.markdown(f"### 📂 {category}")

                    for prompt in category_prompts:
                        with st.expander(f"📝 {prompt['title']} ({prompt['owner']})"):
                            if prompt.get('description'):
                                st.caption(prompt['description'])

                            if prompt.get('system'):
                                st.info(f"담당 시스템: {prompt['system']}")

                            if prompt.get('prompt_content'):
                                st.code(prompt['prompt_content'], language="markdown")
                            else:
                                st.warning("프롬프트 내용을 불러올 수 없습니다")

                            st.caption(f"작성일: {prompt.get('created_at', 'N/A')[:10] if prompt.get('created_at') else 'N/A'}")
            else:
                st.info("아직 작성된 프롬프트가 없습니다")
                st.caption("프롬프트 관리 탭에서 그룹 프롬프트를 작성할 수 있습니다")

        with tab3:
            st.subheader("그룹 카테고리")

            st.info("""
💡 **카테고리란?**
- 그룹의 프롬프트를 분류하는 카테고리를 정의할 수 있습니다
- Owner만 카테고리를 추가/수정/삭제할 수 있습니다
- 멤버는 정의된 카테고리 중에서 선택하여 프롬프트를 작성합니다
- 카테고리 순서를 조정하여 보고서 내 표시 순서를 결정합니다
            """)

            # 카테고리 목록 조회
            categories = group_data.get("categories", [])

            # Owner만 카테고리 관리 가능
            if group_data.get("my_role") == 'owner':
                with st.expander("➕ 카테고리 추가"):
                    with st.form("add_category_form"):
                        cat_name = st.text_input("카테고리 이름 *", placeholder="예: 운영지원, BMT, PM")
                        cat_description = st.text_area("설명 (선택)", placeholder="카테고리에 대한 설명")
                        cat_order = st.number_input("순서", min_value=0, value=len(categories), step=1,
                                                   help="낮은 숫자가 먼저 표시됩니다")

                        if st.form_submit_button("추가"):
                            if not cat_name.strip():
                                st.error("카테고리 이름을 입력해주세요")
                            else:
                                result = auth_client.add_group_category(
                                    st.session_state.selected_group_id,
                                    cat_name.strip(),
                                    cat_description.strip() or None,
                                    cat_order
                                )
                                if result.get("success"):
                                    st.success(f"✅ 카테고리 '{cat_name}'이 추가되었습니다!")
                                    st.rerun()
                                else:
                                    st.error(f"카테고리 추가 실패: {result.get('message')}")

            # 카테고리 목록 표시
            if categories:
                st.markdown("### 📂 현재 카테고리")

                for idx, category in enumerate(categories):
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])

                        with col1:
                            st.markdown(f"**{category['name']}** (순서: {category['order_index']})")
                            if category.get('description'):
                                st.caption(category['description'])

                        with col2:
                            # Owner만 편집 가능
                            if group_data.get("my_role") == 'owner':
                                edit_key = f"edit_cat_{category['id']}"
                                if edit_key not in st.session_state:
                                    st.session_state[edit_key] = False

                                if st.button("✏️", key=f"btn_edit_{category['id']}", use_container_width=True):
                                    st.session_state[edit_key] = not st.session_state[edit_key]
                                    st.rerun()

                        with col3:
                            # Owner만 삭제 가능
                            if group_data.get("my_role") == 'owner':
                                if st.button("🗑️", key=f"btn_del_{category['id']}", use_container_width=True):
                                    result = auth_client.delete_group_category(
                                        st.session_state.selected_group_id,
                                        category['id']
                                    )
                                    if result.get("success"):
                                        st.success("✅ 카테고리가 삭제되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error(f"카테고리 삭제 실패: {result.get('message')}")

                        # 편집 폼
                        if group_data.get("my_role") == 'owner' and st.session_state.get(f"edit_cat_{category['id']}", False):
                            with st.form(f"edit_cat_form_{category['id']}"):
                                new_name = st.text_input("카테고리 이름", value=category['name'])
                                new_desc = st.text_area("설명", value=category.get('description', ''))

                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.form_submit_button("저장"):
                                        result = auth_client.update_group_category(
                                            st.session_state.selected_group_id,
                                            category['id'],
                                            new_name.strip() or None,
                                            new_desc.strip() or None
                                        )
                                        if result.get("success"):
                                            st.success("✅ 카테고리가 수정되었습니다!")
                                            st.session_state[f"edit_cat_{category['id']}"] = False
                                            st.rerun()
                                        else:
                                            st.error(f"카테고리 수정 실패: {result.get('message')}")

                                with col_cancel:
                                    if st.form_submit_button("취소"):
                                        st.session_state[f"edit_cat_{category['id']}"] = False
                                        st.rerun()

                        st.markdown("---")
            else:
                st.info("아직 정의된 카테고리가 없습니다")
                if group_data.get("my_role") == 'owner':
                    st.caption("카테고리를 추가하여 프롬프트를 분류하세요")
                else:
                    st.caption("Owner가 카테고리를 정의할 때까지 기다려주세요")

        with tab4:
            st.subheader("그룹 설정")

            # Owner만 수정/삭제 가능
            if group_info.get('role') == 'owner':
                with st.expander("✏️ 그룹 정보 수정"):
                    with st.form("update_group_form"):
                        new_name = st.text_input("그룹 이름", value=group_info.get('name'))
                        new_description = st.text_area("설명", value=group_info.get('description', ''))

                        if st.form_submit_button("수정"):
                            result = auth_client.update_group(
                                st.session_state.selected_group_id,
                                new_name.strip() or None,
                                new_description.strip() or None
                            )
                            if result.get("success"):
                                st.success("✅ 그룹 정보가 수정되었습니다!")
                                st.rerun()
                            else:
                                st.error(f"그룹 수정 실패: {result.get('message')}")

                st.markdown("---")

                with st.expander("🗑️ 그룹 삭제"):
                    st.warning("⚠️ 그룹을 삭제하면 복구할 수 없습니다!")

                    confirm_text = st.text_input("삭제하려면 그룹 이름을 입력하세요")

                    if st.button("그룹 삭제", type="primary"):
                        if confirm_text == group_info.get('name'):
                            result = auth_client.delete_group(st.session_state.selected_group_id)
                            if result.get("success"):
                                st.success("✅ 그룹이 삭제되었습니다!")
                                st.session_state.selected_group_id = None
                                st.rerun()
                            else:
                                st.error(f"그룹 삭제 실패: {result.get('message')}")
                        else:
                            st.error("그룹 이름이 일치하지 않습니다")
            else:
                st.info("👤 멤버는 그룹 설정을 변경할 수 없습니다")


def execute_prompt_with_agent(prompt_content: str, title: str) -> dict:
    """프롬프트를 Agent로 실행"""
    import time
    import os
    from openai import AzureOpenAI

    try:
        user_id = st.session_state.get('user_id')

        # Azure OpenAI 클라이언트 초기화
        azure_client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY") or st.secrets.get("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview",
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT") or st.secrets.get("AZURE_OPENAI_ENDPOINT")
        )

        from agent.monthly_report_agent import MonthlyReportAgent

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME") or st.secrets.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        )

        # 시스템 지시사항 추가
        enhanced_prompt = f"""{prompt_content}

[중요 출력 규칙]
- 반드시 HTML 형식으로 출력하세요 (Markdown이 아닌 순수 HTML)
- 코드 블록(```html 등)이나 추가적인 주석, 설명은 포함하지 마세요
- 바로 사용 가능한 HTML만 출력하세요
- 표를 생성할 때는 반드시 모든 <td> 태그에 contenteditable="true" 속성을 추가하세요
  예시: <td contenteditable="true">데이터</td>
  이렇게 하면 사용자가 최종 보고서에서 표 내용을 직접 편집할 수 있습니다
"""

        start_time = time.time()

        # Agent 실행
        result = agent.generate_page(
            page_title=title,
            user_prompt=enhanced_prompt,
            context={}
        )

        elapsed_time = time.time() - start_time

        if result.get('success'):
            return {
                'success': True,
                'content': result.get('content', ''),
                'elapsed_time': elapsed_time
            }
        else:
            return {
                'success': False,
                'error': result.get('error', '알 수 없는 오류')
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def execute_ad_hoc_prompt(prompt_content: str, title: str) -> dict:
    """일회용 프롬프트 실행 (래퍼 함수)"""
    return execute_prompt_with_agent(prompt_content, title)


def execute_all_prompts_in_sections(sections: list) -> None:
    """섹션의 모든 프롬프트를 실행 (저장된 프롬프트 & 일회용 프롬프트)"""
    import time

    # 실행이 필요한 프롬프트 찾기
    prompts_to_execute = []

    for idx, section in enumerate(sections):
        section_type = section.get('type')

        # 저장된 프롬프트 (아직 실행되지 않음)
        if section_type == 'prompt' and not section.get('executed'):
            prompts_to_execute.append((idx, 'prompt', section))

        # 일회용 프롬프트 (아직 실행되지 않음)
        elif section_type == 'ad_hoc_prompt' and not section.get('executed'):
            prompts_to_execute.append((idx, 'ad_hoc_prompt', section))

    if not prompts_to_execute:
        return  # 실행할 프롬프트가 없음

    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()

    total_prompts = len(prompts_to_execute)

    for current, (idx, ptype, section) in enumerate(prompts_to_execute):
        title = section.get('title', '제목 없음')
        status_text.text(f"🤖 프롬프트 실행 중... ({current + 1}/{total_prompts}) {title}")

        if ptype == 'prompt':
            # 저장된 프롬프트 - prompt_id로부터 내용 가져오기
            prompt_id = section.get('prompt_id')
            if prompt_id:
                try:
                    prompt_data = load_prompt_by_id(prompt_id)
                    prompt_content = prompt_data.get('prompt_content', '')

                    # 프롬프트 실행
                    result = execute_prompt_with_agent(prompt_content, title)

                    if result.get('success'):
                        st.session_state.group_report_sections[idx]['executed'] = True
                        st.session_state.group_report_sections[idx]['result'] = result.get('content', '')
                    else:
                        st.warning(f"⚠️ '{title}' 실행 실패: {result.get('error')}")
                        st.session_state.group_report_sections[idx]['executed'] = False
                        st.session_state.group_report_sections[idx]['result'] = f"<p><em>실행 실패: {result.get('error')}</em></p>"

                except Exception as e:
                    st.error(f"❌ '{title}' 실행 중 오류: {str(e)}")
                    st.session_state.group_report_sections[idx]['executed'] = False
                    st.session_state.group_report_sections[idx]['result'] = f"<p><em>실행 오류: {str(e)}</em></p>"

        elif ptype == 'ad_hoc_prompt':
            # 일회용 프롬프트
            prompt_content = section.get('prompt_content', '')

            result = execute_prompt_with_agent(prompt_content, title)

            if result.get('success'):
                st.session_state.group_report_sections[idx]['executed'] = True
                st.session_state.group_report_sections[idx]['result'] = result.get('content', '')
            else:
                st.warning(f"⚠️ '{title}' 실행 실패: {result.get('error')}")
                st.session_state.group_report_sections[idx]['executed'] = False
                st.session_state.group_report_sections[idx]['result'] = f"<p><em>실행 실패: {result.get('error')}</em></p>"

        # 진행률 업데이트
        progress_bar.progress((current + 1) / total_prompts)

        # API 제한 방지 - 다음 프롬프트 실행 전 대기
        if current < total_prompts - 1:
            time.sleep(2)

    progress_bar.empty()
    status_text.empty()

    st.success(f"✅ {total_prompts}개 프롬프트 실행 완료!")


def render_section_editor(idx: int, section: dict, total_sections: int):
    """섹션 편집기 - 순서 조정, 편집, 삭제"""
    section_type = section.get('type', 'unknown')

    # 섹션 헤더
    col_info, col_actions = st.columns([3, 1])

    with col_info:
        if section_type == 'prompt':
            st.markdown(f"**{idx + 1}. 📝 프롬프트: {section.get('title')}**")
            if section.get('executed'):
                st.caption(f"✅ 실행 완료 | 시스템: {section.get('system', '기타')} | by {section.get('owner', 'Unknown')}")
            else:
                st.caption(f"⏳ 실행 대기 중 | 시스템: {section.get('system', '기타')} | by {section.get('owner', 'Unknown')}")
        elif section_type == 'ad_hoc_prompt':
            st.markdown(f"**{idx + 1}. 🤖 일회용 프롬프트: {section.get('title')}**")
            if section.get('executed'):
                st.caption("✅ 실행 완료")
            else:
                st.caption("⏳ 실행 대기 중")
        elif section_type == 'text':
            st.markdown(f"**{idx + 1}. 📝 텍스트: {section.get('title')}**")
        elif section_type == 'table':
            st.markdown(f"**{idx + 1}. 📊 표: {section.get('title')}**")
        elif section_type == 'divider':
            st.markdown(f"**{idx + 1}. ➖ 구분선**")
        elif section_type == 'page_break':
            st.markdown(f"**{idx + 1}. 📄 페이지 구분**")

    with col_actions:
        col_up, col_down, col_del = st.columns(3)

        # 위로 이동
        with col_up:
            if idx > 0:
                if st.button("⬆️", key=f"up_{idx}", help="위로"):
                    st.session_state.group_report_sections[idx], st.session_state.group_report_sections[idx - 1] = \
                        st.session_state.group_report_sections[idx - 1], st.session_state.group_report_sections[idx]
                    st.rerun()

        # 아래로 이동
        with col_down:
            if idx < total_sections - 1:
                if st.button("⬇️", key=f"down_{idx}", help="아래로"):
                    st.session_state.group_report_sections[idx], st.session_state.group_report_sections[idx + 1] = \
                        st.session_state.group_report_sections[idx + 1], st.session_state.group_report_sections[idx]
                    st.rerun()

        # 삭제
        with col_del:
            if st.button("🗑️", key=f"del_{idx}", help="삭제"):
                st.session_state.group_report_sections.pop(idx)
                st.rerun()

    # 섹션별 편집 UI
    if section_type == 'prompt':
        with st.expander("🚀 프롬프트 실행"):
            st.info(f"**프롬프트 ID**: {section.get('prompt_id')}")

            if st.button("🚀 프롬프트 실행", key=f"exec_saved_{idx}", use_container_width=True, type="primary"):
                # 저장된 프롬프트 실행
                with st.spinner("프롬프트를 실행하는 중..."):
                    prompt_id = section.get('prompt_id')
                    title = section.get('title')

                    try:
                        prompt_data = load_prompt_by_id(prompt_id)
                        prompt_content = prompt_data.get('prompt_content', '')

                        result = execute_prompt_with_agent(prompt_content, title)

                        if result.get('success'):
                            st.session_state.group_report_sections[idx]['executed'] = True
                            st.session_state.group_report_sections[idx]['result'] = result.get('content', '')
                            st.success(f"✅ 실행 완료! ({result.get('elapsed_time', 0):.2f}초)")
                            st.rerun()
                        else:
                            st.error(f"❌ 실행 실패: {result.get('error', '알 수 없는 오류')}")

                    except Exception as e:
                        st.error(f"❌ 실행 중 오류: {str(e)}")

            # 실행 결과 미리보기
            if section.get('executed') and section.get('result'):
                st.markdown("---")
                st.markdown("**📄 실행 결과 미리보기**")
                st.components.v1.html(section.get('result', ''), height=300, scrolling=True)

    elif section_type == 'text':
        with st.expander("✏️ 텍스트 편집"):
            new_title = st.text_input("제목", value=section.get('title', ''), key=f"text_title_{idx}")
            new_content = st.text_area("내용", value=section.get('content', ''), height=150, key=f"text_content_{idx}")
            new_style = st.selectbox("스타일", options=['paragraph', 'heading', 'note'],
                                     index=['paragraph', 'heading', 'note'].index(section.get('style', 'paragraph')),
                                     key=f"text_style_{idx}")

            if st.button("💾 저장", key=f"save_text_{idx}"):
                st.session_state.group_report_sections[idx]['title'] = new_title
                st.session_state.group_report_sections[idx]['content'] = new_content
                st.session_state.group_report_sections[idx]['style'] = new_style
                st.success("저장되었습니다!")
                st.rerun()

    elif section_type == 'table':
        with st.expander("✏️ 표 편집"):
            new_title = st.text_input("제목", value=section.get('title', ''), key=f"table_title_{idx}")

            st.markdown("**표 데이터 (CSV 형식으로 입력)**")
            # 표 데이터를 CSV 형식으로 변환
            current_data = section.get('data', [[]])
            csv_text = '\n'.join([','.join(row) for row in current_data])

            new_data_text = st.text_area("데이터", value=csv_text, height=150, key=f"table_data_{idx}",
                                          help="쉼표로 구분하여 입력하세요. 첫 줄은 헤더입니다.")

            if st.button("💾 저장", key=f"save_table_{idx}"):
                # CSV 텍스트를 표 데이터로 변환
                new_data = [line.split(',') for line in new_data_text.strip().split('\n') if line.strip()]
                st.session_state.group_report_sections[idx]['title'] = new_title
                st.session_state.group_report_sections[idx]['data'] = new_data
                st.success("저장되었습니다!")
                st.rerun()

    elif section_type == 'divider':
        with st.expander("✏️ 구분선 스타일"):
            new_style = st.selectbox("스타일", options=['solid', 'dashed', 'thick'],
                                     index=['solid', 'dashed', 'thick'].index(section.get('style', 'solid')),
                                     key=f"divider_style_{idx}")

            if st.button("💾 저장", key=f"save_divider_{idx}"):
                st.session_state.group_report_sections[idx]['style'] = new_style
                st.success("저장되었습니다!")
                st.rerun()

    elif section_type == 'ad_hoc_prompt':
        with st.expander("✏️ 프롬프트 편집 & 실행"):
            new_title = st.text_input("제목", value=section.get('title', ''), key=f"adhoc_title_{idx}")
            new_prompt = st.text_area("프롬프트 내용", value=section.get('prompt_content', ''),
                                      height=200, key=f"adhoc_prompt_{idx}",
                                      help="Agent가 실행할 프롬프트를 입력하세요. HTML 형식으로 결과가 반환됩니다.")

            col_save, col_exec = st.columns(2)

            with col_save:
                if st.button("💾 저장", key=f"save_adhoc_{idx}", use_container_width=True):
                    st.session_state.group_report_sections[idx]['title'] = new_title
                    st.session_state.group_report_sections[idx]['prompt_content'] = new_prompt
                    st.session_state.group_report_sections[idx]['executed'] = False
                    st.session_state.group_report_sections[idx]['result'] = ''
                    st.success("저장되었습니다!")
                    st.rerun()

            with col_exec:
                if st.button("🚀 프롬프트 실행", key=f"exec_adhoc_{idx}", use_container_width=True, type="primary"):
                    # Agent 실행
                    with st.spinner("프롬프트를 실행하는 중..."):
                        result = execute_ad_hoc_prompt(new_prompt, new_title)

                        if result.get('success'):
                            st.session_state.group_report_sections[idx]['title'] = new_title
                            st.session_state.group_report_sections[idx]['prompt_content'] = new_prompt
                            st.session_state.group_report_sections[idx]['executed'] = True
                            st.session_state.group_report_sections[idx]['result'] = result.get('content', '')
                            st.success(f"✅ 실행 완료! ({result.get('elapsed_time', 0):.2f}초)")
                            st.rerun()
                        else:
                            st.error(f"❌ 실행 실패: {result.get('error', '알 수 없는 오류')}")

            # 실행 결과 미리보기
            if section.get('executed') and section.get('result'):
                st.markdown("---")
                st.markdown("**📄 실행 결과 미리보기**")
                st.components.v1.html(section.get('result', ''), height=300, scrolling=True)


def generate_group_report_html(sections: list, title: str, include_toc: bool, prompts_by_category: dict) -> str:
    """섹션 리스트로부터 최종 HTML 보고서 생성"""
    from datetime import datetime

    # HTML 헤더
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .report-header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #4CAF50;
        }}
        .report-header h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .report-date {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}
        .toc {{
            background-color: #f8f9fa;
            padding: 20px;
            margin-bottom: 30px;
            border-left: 4px solid #4CAF50;
        }}
        .toc h2 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .toc ol {{
            padding-left: 20px;
        }}
        .toc li {{
            margin: 8px 0;
        }}
        .toc a {{
            color: #3498db;
            text-decoration: none;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
        .report-section {{
            margin-bottom: 40px;
        }}
        .report-section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .section-content {{
            margin: 20px 0;
        }}

        /* 텍스트 스타일 */
        .text-paragraph {{
            line-height: 1.8;
            margin: 15px 0;
        }}
        .text-heading {{
            font-size: 1.5em;
            font-weight: 600;
            color: #2c3e50;
            margin: 20px 0 10px 0;
        }}
        .text-note {{
            background-color: #fff9e6;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
        }}

        /* 표 스타일 */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        table td[contenteditable="true"] {{
            cursor: text;
            outline: none;
        }}
        table td[contenteditable="true"]:hover {{
            background-color: #e8f5e9;
        }}
        table td[contenteditable="true"]:focus {{
            background-color: #fff9c4;
            box-shadow: inset 0 0 0 2px #4CAF50;
        }}

        /* 구분선 스타일 */
        .divider-solid {{
            border: none;
            border-top: 1px solid #ccc;
            margin: 30px 0;
        }}
        .divider-dashed {{
            border: none;
            border-top: 1px dashed #ccc;
            margin: 30px 0;
        }}
        .divider-thick {{
            border: none;
            border-top: 3px solid #666;
            margin: 30px 0;
        }}

        /* 페이지 구분 스타일 */
        .page-break {{
            page-break-after: always;
            height: 0;
            margin: 0;
            padding: 0;
        }}

        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
            }}
            .page-break {{
                page-break-after: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>{title}</h1>
            <p class="report-date">{datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
"""

    # 목차 생성
    if include_toc:
        html += '\n<div class="toc">\n'
        html += '<h2>목차</h2>\n'
        html += '<ol>\n'

        section_number = 0
        for section in sections:
            section_type = section.get('type', 'prompt')
            if section_type not in ['divider', 'page_break']:
                section_number += 1
                section_title = section.get('title', '제목 없음')
                html += f'<li><a href="#section-{section_number}">{section_title}</a></li>\n'

        html += '</ol>\n'
        html += '</div>\n'

    # 각 섹션 생성
    section_number = 0
    for section in sections:
        section_type = section.get('type', 'prompt')

        if section_type == 'prompt':
            section_number += 1
            section_title = section.get('title', '제목 없음')

            # 저장된 프롬프트 실행 결과
            if section.get('executed') and section.get('result'):
                prompt_content = section.get('result', '')
            else:
                prompt_content = f"<p><em>[프롬프트 '{section_title}'가 아직 실행되지 않았습니다]</em></p>"

            html += f"""
<section id="section-{section_number}" class="report-section">
    <h2>{section_number}. {section_title}</h2>
    <div class="section-content">
        {prompt_content}
    </div>
</section>
"""

        elif section_type == 'ad_hoc_prompt':
            section_number += 1
            section_title = section.get('title', '제목 없음')

            # 일회용 프롬프트 결과
            if section.get('executed') and section.get('result'):
                prompt_content = section.get('result', '')
            else:
                prompt_content = f"<p><em>[프롬프트 '{section_title}'가 아직 실행되지 않았습니다]</em></p>"

            html += f"""
<section id="section-{section_number}" class="report-section">
    <h2>{section_number}. {section_title}</h2>
    <div class="section-content">
        {prompt_content}
    </div>
</section>
"""

        elif section_type == 'text':
            section_number += 1
            section_title = section.get('title', '텍스트')
            content = section.get('content', '')
            style = section.get('style', 'paragraph')

            # 줄바꿈을 <br>로 변환
            content_html = content.replace('\n', '<br>')
            style_class = f'text-{style}'

            html += f"""
<section id="section-{section_number}" class="report-section">
    <h2>{section_number}. {section_title}</h2>
    <div class="section-content">
        <div class="{style_class}">{content_html}</div>
    </div>
</section>
"""

        elif section_type == 'table':
            section_number += 1
            section_title = section.get('title', '표')
            table_data = section.get('data', [[]])

            # HTML 테이블 생성
            table_html = '<table>\n'

            # 첫 행은 헤더로 처리
            if len(table_data) > 0:
                table_html += '<thead>\n<tr>\n'
                for cell in table_data[0]:
                    table_html += f'<th>{cell}</th>\n'
                table_html += '</tr>\n</thead>\n'

            # 나머지 행은 데이터 (contenteditable 속성 추가)
            if len(table_data) > 1:
                table_html += '<tbody>\n'
                for row in table_data[1:]:
                    table_html += '<tr>\n'
                    for cell in row:
                        table_html += f'<td contenteditable="true">{cell}</td>\n'
                    table_html += '</tr>\n'
                table_html += '</tbody>\n'

            table_html += '</table>\n'

            html += f"""
<section id="section-{section_number}" class="report-section">
    <h2>{section_number}. {section_title}</h2>
    <div class="section-content">
        {table_html}
    </div>
</section>
"""

        elif section_type == 'divider':
            style = section.get('style', 'solid')
            html += f'<hr class="divider-{style}">\n'

        elif section_type == 'page_break':
            html += '<div class="page-break"></div>\n'

    # HTML 푸터
    html += """
    </div>
</body>
</html>
"""

    return html


def display_group_report_builder():
    """그룹 보고서 생성 UI - 드래그 앤 드롭 및 커스텀 컴포넌트 지원"""
    st.header("📊 그룹 보고서 생성")

    if not auth_client.is_logged_in():
        st.warning("⚠️ 로그인이 필요합니다")
        return

    st.info("""
💡 **그룹 보고서 빌더**
- 프롬프트를 선택하여 보고서에 추가할 수 있습니다
- 텍스트, 표, 구분선 등 커스텀 컴포넌트를 추가할 수 있습니다
- 섹션의 순서를 자유롭게 조정할 수 있습니다
    """)

    # 세션 상태 초기화
    if 'group_report_selected_group_id' not in st.session_state:
        st.session_state.group_report_selected_group_id = None
    if 'group_report_sections' not in st.session_state:
        st.session_state.group_report_sections = []
    if 'group_report_html' not in st.session_state:
        st.session_state.group_report_html = None

    # 1단계: 그룹 선택
    st.subheader("1️⃣ 그룹 선택")

    groups_result = auth_client.get_groups()

    if not groups_result.get("success"):
        st.error(f"그룹 목록을 불러올 수 없습니다: {groups_result.get('message')}")
        return

    groups = groups_result.get("groups", [])

    if not groups:
        st.info("아직 그룹이 없습니다. 그룹 관리 탭에서 새 그룹을 만들어보세요!")
        return

    # 그룹 선택 드롭다운
    group_options = {group['id']: f"{group['name']} ({group.get('member_count', 0)}명, {group.get('prompt_count', 0)}개 프롬프트)" for group in groups}

    selected_group_id = st.selectbox(
        "그룹 선택",
        options=list(group_options.keys()),
        format_func=lambda x: group_options[x],
        key="group_report_select"
    )

    if not selected_group_id:
        return

    # 그룹 상세 정보 조회
    detail_result = auth_client.get_group_detail(selected_group_id)

    if not detail_result.get("success"):
        st.error(f"그룹 정보를 불러올 수 없습니다: {detail_result.get('message')}")
        return

    group_data = detail_result.get("data", {})
    group_info = group_data.get("group", {})
    prompts_by_category = group_data.get("prompts_by_category", {})

    if not prompts_by_category:
        st.warning("이 그룹에는 아직 프롬프트가 없습니다. 프롬프트 관리 탭에서 그룹 프롬프트를 작성해주세요.")
        return

    st.markdown("---")

    # 2열 레이아웃: 왼쪽(프롬프트/컴포넌트 선택), 오른쪽(섹션 구성)
    col_left, col_right = st.columns([1, 2])

    # ========================================
    # 왼쪽: 프롬프트 선택 & 컴포넌트 추가
    # ========================================
    with col_left:
        st.subheader("📝 콘텐츠 선택")

        # 프롬프트 추가
        with st.expander("➕ 프롬프트 추가", expanded=True):
            for category, category_prompts in prompts_by_category.items():
                st.markdown(f"**📂 {category}**")

                for prompt in category_prompts:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.caption(f"{prompt['title']} ({prompt.get('system', '기타')})")
                    with col_b:
                        if st.button("➕", key=f"add_prompt_{prompt['id']}", help="섹션에 추가"):
                            st.session_state.group_report_sections.append({
                                'type': 'prompt',
                                'prompt_id': prompt['id'],
                                'title': prompt['title'],
                                'category': prompt.get('category', ''),
                                'system': prompt.get('system', '기타'),
                                'owner': prompt.get('owner', '')
                            })
                            st.rerun()

                st.markdown("---")

        # 커스텀 컴포넌트 추가
        with st.expander("🎨 커스텀 컴포넌트"):
            st.markdown("**컴포넌트 추가**")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📝 텍스트", use_container_width=True, key="add_text_comp"):
                    st.session_state.group_report_sections.append({
                        'type': 'text',
                        'title': '새 텍스트',
                        'content': '여기에 텍스트를 입력하세요...',
                        'style': 'paragraph'
                    })
                    st.rerun()

                if st.button("➖ 구분선", use_container_width=True, key="add_divider_comp"):
                    st.session_state.group_report_sections.append({
                        'type': 'divider',
                        'style': 'solid'
                    })
                    st.rerun()

            with col2:
                if st.button("📊 빈 표", use_container_width=True, key="add_table_comp"):
                    st.session_state.group_report_sections.append({
                        'type': 'table',
                        'title': '새 표',
                        'data': [
                            ['헤더1', '헤더2', '헤더3'],
                            ['데이터1', '데이터2', '데이터3'],
                            ['데이터4', '데이터5', '데이터6']
                        ]
                    })
                    st.rerun()

                if st.button("📄 페이지 구분", use_container_width=True, key="add_page_break_comp"):
                    st.session_state.group_report_sections.append({
                        'type': 'page_break'
                    })
                    st.rerun()

            st.markdown("---")

            # 일회용 프롬프트
            if st.button("🤖 일회용 프롬프트", use_container_width=True, key="add_adhoc_prompt_comp"):
                st.session_state.group_report_sections.append({
                    'type': 'ad_hoc_prompt',
                    'title': '새 프롬프트',
                    'prompt_content': '여기에 프롬프트를 입력하세요...',
                    'executed': False,
                    'result': ''
                })
                st.rerun()

    # ========================================
    # 오른쪽: 섹션 구성 & 순서 조정
    # ========================================
    with col_right:
        st.subheader("📋 섹션 구성")

        if len(st.session_state.group_report_sections) == 0:
            st.info("""
📌 섹션이 비어있습니다

왼쪽에서 프롬프트를 추가하거나 커스텀 컴포넌트를 추가하세요.
            """)
        else:
            st.success(f"✅ {len(st.session_state.group_report_sections)}개 섹션")

            # 전체 초기화 버튼
            if st.button("🗑️ 전체 초기화", key="clear_all_sections"):
                st.session_state.group_report_sections = []
                st.rerun()

            st.markdown("---")

            # 각 섹션 표시
            for idx, section in enumerate(st.session_state.group_report_sections):
                render_section_editor(idx, section, len(st.session_state.group_report_sections))
                st.markdown("---")

    # ========================================
    # 하단: 보고서 설정 & 생성
    # ========================================
    st.markdown("---")
    st.subheader("⚙️ 보고서 설정 & 생성")

    col1, col2, col3 = st.columns(3)
    with col1:
        report_title = st.text_input("보고서 제목", value=f"{group_info.get('name')} 월간보고", key="group_report_title")
    with col2:
        include_toc = st.checkbox("목차 포함", value=True, key="group_include_toc")
    with col3:
        save_report = st.checkbox("히스토리 저장", value=True, key="group_save_report")

    # 보고서 생성 버튼
    if len(st.session_state.group_report_sections) == 0:
        st.warning("⚠️ 최소 1개 이상의 섹션을 추가해주세요")
    else:
        st.caption(f"총 {len(st.session_state.group_report_sections)}개 섹션")

        col_gen1, col_gen2 = st.columns(2)

        with col_gen1:
            if st.button("👁️ 미리보기", use_container_width=True, key="preview_report"):
                html = generate_group_report_html(
                    st.session_state.group_report_sections,
                    report_title,
                    include_toc,
                    prompts_by_category
                )
                st.session_state.group_report_html = html
                st.rerun()

        with col_gen2:
            if st.button("🚀 보고서 생성", type="primary", use_container_width=True, key="generate_report"):
                with st.spinner("프롬프트를 실행하고 보고서를 생성하는 중입니다..."):
                    # 1단계: 모든 프롬프트 실행
                    execute_all_prompts_in_sections(st.session_state.group_report_sections)

                    # 2단계: HTML 생성
                    html = generate_group_report_html(
                        st.session_state.group_report_sections,
                        report_title,
                        include_toc,
                        prompts_by_category
                    )
                    st.session_state.group_report_html = html
                    st.success(f"✅ 보고서가 생성되었습니다!")
                    st.rerun()

    # 미리보기 및 다운로드
    if st.session_state.group_report_html:
        st.markdown("---")
        st.subheader("📄 생성된 보고서")

        from datetime import datetime

        st.info("💡 **표 편집 가능**: 생성된 보고서의 표 셀을 클릭하면 내용을 직접 편집할 수 있습니다. 편집 후 HTML을 다운로드하면 변경사항이 포함됩니다.")

        # 다운로드 버튼
        st.download_button(
            label="💾 HTML 다운로드",
            data=st.session_state.group_report_html,
            file_name=f"group_report_{group_info.get('name')}_{datetime.now().strftime('%Y%m%d')}.html",
            mime="text/html",
            use_container_width=True
        )

        # 미리보기
        with st.expander("미리보기", expanded=True):
            st.components.v1.html(st.session_state.group_report_html, height=600, scrolling=True)


def display_jira_debugging():
    """Jira 디버깅 UI - search_issues와 get_linked_issues 테스트"""
    st.header("🔍 Jira 이슈 검색 디버깅")

    st.info("💡 search_issues와 get_linked_issues 함수를 테스트하여 연결된 이슈 정보를 확인할 수 있습니다.")

    # 중요 안내
    st.warning("""
⚠️ **JQL 작성 시 주의사항**

1. **따옴표**: 필드 값에는 **큰따옴표 `"`** 사용
   - ✅ 올바름: `labels = "NCMS_BMT"`
   - ❌ 잘못됨: `labels = 'NCMS_BMT'`
   - 💡 작은따옴표는 자동으로 큰따옴표로 변환됩니다

2. **fixVersion**: JQL에서는 **단수형** 사용 (중요!)
   - ✅ 올바름: `fixVersion = "25.05"`
   - ❌ 잘못됨: `fixVersions = "25.05"`
   - 📝 참고: fields 파라미터와 반환 데이터는 `fixVersions` (복수형)
    """)

    # 로그인 사용자 정보 확인
    user_info = auth_client.get_current_user()
    if not user_info or 'id' not in user_info:
        st.error("❌ 로그인이 필요합니다.")
        st.stop()

    user_id = user_info['id']
    st.caption(f"👤 로그인 사용자 ID: {user_id}")

    # JQL 입력
    st.subheader("1️⃣ JQL 쿼리")

    # JQL 예시 선택
    with st.expander("📝 JQL 예시 선택"):
        jql_examples = {
            "프로젝트 + 라벨 + 버전": 'project = BTVO AND labels = "NCMS_BMT" AND fixVersion = "25.05"',
            "프로젝트 + 라벨": 'project = BTVO AND labels = "NCMS_BMT"',
            "프로젝트 + 버전": 'project = BTVO AND fixVersion = "25.05"',
            "프로젝트 + 상태": 'project = BTVO AND status = "완료"',
            "프로젝트 + 담당자": 'project = BTVO AND assignee = currentUser()',
            "날짜 범위": 'project = BTVO AND created >= "2025-10-01" AND created <= "2025-10-31"',
            "여러 라벨 (OR)": 'project = BTVO AND labels in ("NCMS_BMT", "NCMS_PM")',
            "여러 버전 (OR)": 'project = BTVO AND fixVersion in ("25.05", "25.06")',
        }

        selected_example = st.selectbox(
            "예시를 선택하면 아래 입력란에 자동으로 채워집니다",
            options=["선택하세요"] + list(jql_examples.keys())
        )

        if selected_example != "선택하세요":
            st.session_state['jql_example'] = jql_examples[selected_example]
            st.rerun()

    # JQL 입력란
    default_jql = st.session_state.pop('jql_example', 'project = BTVO AND labels = "NCMS_BMT" AND fixVersion = "25.05"')

    jql_input = st.text_area(
        "JQL 쿼리를 입력하세요",
        value=default_jql,
        height=100,
        help="Jira Query Language 쿼리 (큰따옴표 사용, fixVersion은 단수형!)"
    )

    max_results = st.number_input(
        "최대 결과 개수",
        min_value=1,
        max_value=100,
        value=10,
        help="조회할 최대 이슈 개수"
    )

    # issuelinks 포함 옵션
    include_issuelinks = st.checkbox(
        "🔗 issuelinks 필드 포함 (연결된 이슈 정보)",
        value=True,
        help="체크하면 원시 API 응답에 issuelinks 필드가 포함됩니다"
    )

    col_search1, col_search2 = st.columns(2)

    with col_search1:
        if st.button("🔍 이슈 검색", type="primary", use_container_width=True):
            with st.spinner("Jira 이슈 검색 중..."):
                try:
                    from tools.jira_query_tool import JiraQueryTool

                    # JiraQueryTool로 직접 검색 (원시 데이터 접근)
                    tool = JiraQueryTool(user_id=user_id)
                    client = tool.client

                    # 필드 설정
                    fields = [
                        "key",
                        "summary",
                        "status",
                        "assignee",
                        "reporter",
                        "created",
                        "updated",
                        "priority",
                        "labels",
                        "components",
                        "issuetype",
                        "fixVersions",
                    ]

                    # issuelinks 추가
                    if include_issuelinks:
                        fields.append("issuelinks")

                    # 원시 API 호출
                    issues_raw = client.search_issues(
                        jql=jql_input,
                        max_results=max_results,
                        fields=fields
                    )

                    # 세션에 저장 (원시 + 파싱 데이터 모두)
                    st.session_state['debug_issues_raw'] = issues_raw
                    st.session_state['debug_jql'] = jql_input

                    # 파싱된 데이터 생성 (UI 표시용)
                    from tools.jira_tools import _parse_issue
                    issues_parsed = []
                    for issue_raw in issues_raw:
                        parsed = _parse_issue(issue_raw)
                        if parsed:
                            issues_parsed.append(parsed)

                    st.session_state['debug_issues'] = issues_parsed

                    if issues_raw:
                        st.success(f"✅ {len(issues_raw)}개 이슈를 찾았습니다!")
                        if include_issuelinks:
                            # issuelinks 통계
                            issues_with_links = sum(
                                1 for issue in issues_raw
                                if issue.get("fields", {}).get("issuelinks")
                            )
                            st.info(f"🔗 {issues_with_links}개 이슈에 연결된 이슈가 있습니다")
                    else:
                        st.warning("⚠️ 조회된 이슈가 없습니다.")

                except Exception as e:
                    st.error(f"❌ 검색 중 오류: {str(e)}")
                    st.exception(e)

    with col_search2:
        if st.button("🗑️ 결과 초기화", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith('debug_'):
                    del st.session_state[key]
            st.rerun()

    # 검색 결과 표시
    if st.session_state.get('debug_issues'):
        issues = st.session_state['debug_issues']

        st.divider()
        st.subheader(f"2️⃣ 검색 결과 ({len(issues)}개)")

        # 통계 정보
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        with col_stat1:
            st.metric("총 이슈 수", len(issues))
        with col_stat2:
            status_counts = {}
            for issue in issues:
                status = issue.get('status', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            st.metric("상태 종류", len(status_counts))
        with col_stat3:
            assignees = set(issue.get('assignee') for issue in issues if issue.get('assignee'))
            st.metric("담당자 수", len(assignees))
        with col_stat4:
            with_labels = sum(1 for issue in issues if issue.get('labels'))
            st.metric("라벨 있는 이슈", with_labels)

        # 이슈 목록을 테이블로 표시
        st.subheader("📋 이슈 목록")

        table_data = []
        for issue in issues:
            table_data.append({
                "Key": issue.get("key", ""),
                "Summary": (issue.get("summary", "")[:60] + "...") if len(issue.get("summary", "")) > 60 else issue.get("summary", ""),
                "Status": issue.get("status", ""),
                "Assignee": issue.get("assignee", "Unassigned"),
                "Created": issue.get("created", "")[:10] if issue.get("created") else "",
                "Labels": ", ".join(issue.get("labels", [])[:3])
            })

        st.dataframe(table_data, use_container_width=True, height=400)

        # 이슈 선택
        st.divider()
        st.subheader("3️⃣ 연결된 이슈 확인")

        issue_keys = [issue.get("key", "") for issue in issues]
        selected_key = st.selectbox(
            "이슈를 선택하여 연결된 이슈를 확인하세요",
            options=["선택하세요"] + issue_keys
        )

        if selected_key and selected_key != "선택하세요":
            # 선택된 이슈 정보 표시
            selected_issue = next((issue for issue in issues if issue.get("key") == selected_key), None)

            if selected_issue:
                st.session_state['debug_selected_issue'] = selected_issue

                col_detail1, col_detail2 = st.columns([2, 1])

                with col_detail1:
                    st.info(f"""
**Key**: {selected_issue.get('key')}
**Summary**: {selected_issue.get('summary')}
**Status**: {selected_issue.get('status')}
**Assignee**: {selected_issue.get('assignee', 'Unassigned')}
**Labels**: {', '.join(selected_issue.get('labels', [])) if selected_issue.get('labels') else 'None'}
                    """)

                with col_detail2:
                    # search 결과에서 issuelinks 먼저 확인
                    raw_issue = None
                    if st.session_state.get('debug_issues_raw'):
                        raw_issue = next(
                            (issue for issue in st.session_state['debug_issues_raw']
                             if issue.get("key") == selected_key),
                            None
                        )

                    # issuelinks가 search 결과에 있으면 바로 표시
                    if raw_issue and raw_issue.get("fields", {}).get("issuelinks"):
                        issuelinks = raw_issue["fields"]["issuelinks"]
                        st.info(f"🔗 Search 결과에 {len(issuelinks)}개 링크 포함")

                        # 자동으로 표시
                        st.session_state['debug_raw_issuelinks'] = issuelinks

                    if st.button("🔗 연결된 이슈 조회 (API)", type="primary", use_container_width=True):
                        with st.spinner("연결된 이슈 조회 중..."):
                            try:
                                from tools.jira_tools import get_linked_issues

                                linked_issues = get_linked_issues(
                                    user_id=user_id,
                                    issue_key=selected_key
                                )

                                st.session_state['debug_linked_issues'] = linked_issues

                                if linked_issues:
                                    st.success(f"✅ {len(linked_issues)}개의 연결된 이슈를 찾았습니다!")
                                else:
                                    st.warning("⚠️ 연결된 이슈가 없습니다.")

                            except Exception as e:
                                st.error(f"❌ 연결된 이슈 조회 중 오류: {str(e)}")
                                st.exception(e)

                # Search 결과에 포함된 issuelinks 표시
                if st.session_state.get('debug_raw_issuelinks'):
                    st.divider()
                    st.subheader("🔗 Search 결과의 issuelinks (원시)")

                    raw_links = st.session_state['debug_raw_issuelinks']

                    for i, link in enumerate(raw_links, 1):
                        link_type = link.get("type", {}).get("name", "Unknown")

                        # outward 또는 inward 확인
                        if "outwardIssue" in link:
                            direction = "outward ➡️"
                            linked_issue = link["outwardIssue"]
                        elif "inwardIssue" in link:
                            direction = "inward ⬅️"
                            linked_issue = link["inwardIssue"]
                        else:
                            continue

                        with st.expander(f"{i}. {linked_issue.get('key')} - {link_type} ({direction})", expanded=True):
                            st.markdown(f"""
**Key**: `{linked_issue.get('key')}`
**Summary**: {linked_issue.get('fields', {}).get('summary', 'N/A')}
**Status**: {linked_issue.get('fields', {}).get('status', {}).get('name', 'N/A')}
**Link Type**: {link_type}
**Direction**: {direction}
                            """)

                            st.caption("원시 link 데이터:")
                            st.json(link)

                # 연결된 이슈 표시 (get_linked_issues API 결과)
                if st.session_state.get('debug_linked_issues'):
                    linked_issues = st.session_state['debug_linked_issues']

                    st.divider()
                    st.subheader(f"🔗 get_linked_issues() API 결과 ({len(linked_issues)}개)")
                    st.caption("get_linked_issues 함수로 조회한 파싱된 데이터")

                    if linked_issues:
                        for i, linked in enumerate(linked_issues, 1):
                            link_type = linked.get('link_type', 'Unknown')
                            link_direction = linked.get('link_direction', 'unknown')

                            direction_icon = "➡️" if link_direction == "outward" else "⬅️"

                            with st.expander(f"{direction_icon} {i}. {linked.get('key')} - {link_type}", expanded=False):
                                col_link1, col_link2 = st.columns([3, 1])

                                with col_link1:
                                    st.markdown(f"""
**Key**: `{linked.get('key')}`
**Summary**: {linked.get('summary')}
**Status**: {linked.get('status')}
**Link Type**: {link_type} ({link_direction})
**Assignee**: {linked.get('assignee', 'Unassigned')}
**Priority**: {linked.get('priority', 'None')}
**Created**: {linked.get('created', '')[:10] if linked.get('created') else 'N/A'}
                                    """)

                                    if linked.get('labels'):
                                        st.markdown(f"**Labels**: {', '.join(linked.get('labels'))}")

                                with col_link2:
                                    st.caption("원시 데이터:")
                                    st.json({
                                        "key": linked.get('key'),
                                        "link_type": link_type,
                                        "link_direction": link_direction,
                                        "status": linked.get('status')
                                    })
                    else:
                        st.info("이 이슈에는 연결된 이슈가 없습니다.")

        # 원시 JSON 데이터 보기
        st.divider()
        st.subheader("🔍 JSON 데이터")

        data_view_tabs = st.tabs(["📋 파싱된 데이터 (UI용)", "🔧 원시 API 응답"])

        with data_view_tabs[0]:
            st.caption("_parse_issue()를 거친 데이터 (필터링됨)")
            st.json(issues)

        with data_view_tabs[1]:
            if st.session_state.get('debug_issues_raw'):
                issues_raw = st.session_state['debug_issues_raw']
                st.caption("Jira API 원본 응답 (필터링 전)")

                # issuelinks 필드 확인
                issues_with_links = []
                for issue in issues_raw:
                    issuelinks = issue.get("fields", {}).get("issuelinks")
                    if issuelinks:
                        issues_with_links.append({
                            "key": issue.get("key"),
                            "link_count": len(issuelinks)
                        })

                if issues_with_links:
                    st.success(f"✅ {len(issues_with_links)}개 이슈에 issuelinks 필드가 있습니다!")
                    st.json({"issues_with_links": issues_with_links})
                else:
                    st.warning("⚠️ 모든 이슈에 issuelinks 필드가 비어있거나 없습니다")

                # 전체 원시 데이터
                st.caption("전체 원시 데이터:")
                st.json(issues_raw)
            else:
                st.info("검색을 실행하면 원시 API 응답을 볼 수 있습니다")


def _validate_report_period(period: str) -> bool:
    """보고 기간 형식 검증 (YYYY-MM)"""
    try:
        parts = period.split('-')
        if len(parts) != 2:
            return False
        year, month = parts
        if len(year) != 4 or not year.isdigit():
            return False
        if len(month) != 2 or not month.isdigit():
            return False
        month_int = int(month)
        if month_int < 1 or month_int > 12:
            return False
        return True
    except:
        return False

if __name__ == "__main__":
    main()
