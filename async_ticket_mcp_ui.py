#!/usr/bin/env python3
"""
MCP 기반 비동기 티켓 생성 UI 컴포넌트
기존 fastmcp_chatbot_app.py에 통합될 수 있는 UI 컴포넌트
"""

import streamlit as st
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from mcp_async_client import get_mcp_async_client

logger = logging.getLogger(__name__)

def _ensure_session_state():
    """세션 상태 초기화 확인"""
    if 'mcp_async_task_id' not in st.session_state:
        st.session_state.mcp_async_task_id = None
    if 'mcp_async_task_history' not in st.session_state:
        st.session_state.mcp_async_task_history = []
    if 'mcp_async_auto_refresh' not in st.session_state:
        st.session_state.mcp_async_auto_refresh = False

class AsyncTicketMCPUI:
    """MCP 기반 비동기 티켓 생성 UI"""

    def __init__(self):
        """초기화"""
        self.mcp_client = get_mcp_async_client()

    def display_async_ticket_creation_section(self):
        """비동기 티켓 생성 섹션 표시"""
        _ensure_session_state()  # 세션 상태 확인

        st.markdown("---")
        st.subheader("🚀 비동기 티켓 생성")

        if not self.mcp_client.is_available():
            st.error("❌ MCP 클라이언트를 사용할 수 없습니다. FastMCP 서버가 실행 중인지 확인하세요.")
            st.info("💡 터미널에서 다음 명령어로 서버를 시작하세요:")
            st.code("python fastmcp_server.py")
            return

        # 현재 실행 중인 작업이 있는지 확인
        if st.session_state.mcp_async_task_id:
            self.display_current_task_status()
        else:
            self.display_create_task_form()

    def display_create_task_form(self):
        """작업 생성 폼 표시"""
        st.write("📧 Gmail에서 메일을 수집하여 자동으로 티켓을 생성합니다.")

        with st.form("mcp_async_ticket_form"):
            col1, col2 = st.columns(2)

            with col1:
                user_id = st.text_input(
                    "사용자 이메일",
                    value="",
                    placeholder="example@gmail.com",
                    help="OAuth 인증에 사용할 Gmail 계정 주소"
                )

                provider_name = st.selectbox(
                    "이메일 제공자",
                    ["gmail", "outlook"],
                    index=0
                )

            with col2:
                user_query = st.text_area(
                    "사용자 쿼리 (선택사항)",
                    placeholder="예: 오늘 받은 업무 관련 메일로 티켓을 생성해주세요",
                    help="특별한 요청사항이 있으면 입력하세요"
                )

            submitted = st.form_submit_button("🎫 비동기 티켓 생성 시작", type="primary")

            if submitted:
                if user_id.strip() and "@" in user_id.strip():
                    with st.spinner("🚀 비동기 작업을 시작하고 있습니다..."):
                        result = self.mcp_client.create_async_ticket_task(
                            user_id=user_id.strip(),
                            provider_name=provider_name,
                            user_query=user_query.strip() if user_query.strip() else None
                        )

                    if result.get("success"):
                        task_id = result.get("task_id")
                        if task_id:
                            st.session_state.mcp_async_task_id = task_id
                            st.session_state.mcp_async_auto_refresh = True

                            # 히스토리에 추가
                            st.session_state.mcp_async_task_history.append({
                                "task_id": task_id,
                                "created_at": datetime.now().isoformat(),
                                "user_id": user_id.strip(),
                                "provider_name": provider_name,
                                "user_query": user_query.strip() if user_query.strip() else None
                            })

                            st.success(f"✅ 비동기 작업이 시작되었습니다!")
                            st.info(f"📋 Task ID: {task_id}")
                            st.rerun()
                        else:
                            # 즉시 완료된 경우
                            tickets_created = result.get("tickets_created", 0)
                            message = result.get("message", "작업이 완료되었습니다.")

                            if tickets_created > 0:
                                st.success(f"✅ {message}")
                                st.info(f"🎫 생성된 티켓: {tickets_created}개")
                            else:
                                st.info(f"ℹ️ {message}")
                    else:
                        error_type = result.get("error", "unknown_error")
                        error_msg = result.get("message", "알 수 없는 오류가 발생했습니다.")

                        if error_type == "authentication_required":
                            # OAuth 인증 오류인 경우 특별한 처리
                            st.error("🔐 **OAuth 재인증이 필요합니다!**")
                            st.warning("Gmail 토큰이 만료되었습니다. 재인증을 완료해주세요.")

                            auth_url = result.get("auth_url")
                            if auth_url:
                                st.markdown(f"👉 **[여기를 클릭하여 Gmail 재인증]({auth_url})**")
                                st.info("💡 재인증 완료 후 이 페이지로 돌아와서 다시 시도해주세요.")

                            # 추가 세부정보 표시 (접을 수 있는 형태)
                            with st.expander("🔍 상세 오류 정보"):
                                st.text(f"오류 유형: {error_type}")
                                st.text(f"상세 메시지: {result.get('details', 'N/A')}")
                        else:
                            # 일반적인 오류 처리
                            st.error(f"❌ 작업 시작 실패: {error_msg}")

                            # 오류 유형별 추가 안내
                            if error_type in ["connection_error", "server_error"]:
                                st.info("💡 서버 연결에 문제가 있을 수 있습니다. 잠시 후 다시 시도해보세요.")
                else:
                    st.error("❌ 유효한 이메일 주소를 입력해주세요.")

    def display_current_task_status(self):
        """현재 실행 중인 작업 상태 표시"""
        _ensure_session_state()  # 세션 상태 확인
        task_id = st.session_state.mcp_async_task_id

        st.write("📊 **현재 실행 중인 작업**")
        st.info(f"Task ID: {task_id}")

        # 상태 조회
        with st.spinner("📊 작업 상태를 조회하고 있습니다..."):
            status_result = self.mcp_client.get_async_task_status(task_id)

        if status_result.get("success"):
            task_data = status_result.get("data", {})
            self.display_task_progress(task_data)
        else:
            st.error(f"❌ 상태 조회 실패: {status_result.get('error', '알 수 없는 오류')}")

        # 컨트롤 버튼들
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 새로고침", type="secondary"):
                st.rerun()

        with col2:
            auto_refresh = st.checkbox("자동 새로고침 (5초)", value=st.session_state.mcp_async_auto_refresh)
            st.session_state.mcp_async_auto_refresh = auto_refresh

        with col3:
            if st.button("⏹️ 작업 추적 중단", type="secondary"):
                st.session_state.mcp_async_task_id = None
                st.session_state.mcp_async_auto_refresh = False
                st.rerun()

        # 자동 새로고침 처리
        if st.session_state.mcp_async_auto_refresh and status_result.get("success"):
            task_data = status_result.get("data", {})
            overall_status = task_data.get("overall_status", "UNKNOWN")

            if overall_status in ["IN_PROGRESS", "PENDING"]:
                time.sleep(5)
                st.rerun()
            elif overall_status in ["COMPLETED", "FAILED"]:
                st.session_state.mcp_async_auto_refresh = False

    def display_task_progress(self, task_data: Dict[str, Any]):
        """작업 진행 상황 표시"""
        overall_status = task_data.get("overall_status", "UNKNOWN")
        steps = task_data.get("steps", [])
        final_result = task_data.get("final_result")

        # 전체 상태 표시
        status_colors = {
            "PENDING": "🟡",
            "IN_PROGRESS": "🔵",
            "COMPLETED": "🟢",
            "FAILED": "🔴"
        }
        status_icon = status_colors.get(overall_status, "❓")

        st.markdown(f"**전체 상태:** {status_icon} {overall_status}")

        # 단계별 진행 상황
        if steps:
            st.markdown("**단계별 진행 상황:**")

            for step in steps:
                step_name = step.get("step_name", "알 수 없는 단계")
                step_status = step.get("status", "UNKNOWN")
                step_log = step.get("log", "")

                step_icon = status_colors.get(step_status, "❓")

                with st.container():
                    st.markdown(f"• {step_icon} **{step_name}**: {step_status}")
                    if step_log:
                        st.markdown(f"  └ {step_log}")

        # 최종 결과 표시
        if final_result and overall_status in ["COMPLETED", "FAILED"]:
            st.markdown("---")

            if overall_status == "COMPLETED":
                st.success("✅ 작업이 성공적으로 완료되었습니다!")

                tickets_created = final_result.get("tickets_created", 0)
                existing_tickets = final_result.get("existing_tickets", 0)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("새로 생성된 티켓", tickets_created)
                with col2:
                    st.metric("기존 티켓", existing_tickets)

                message = final_result.get("message", "")
                if message:
                    st.info(f"ℹ️ {message}")

            elif overall_status == "FAILED":
                st.error("❌ 작업이 실패했습니다.")

                error_msg = final_result.get("error", "알 수 없는 오류")
                st.error(f"오류: {error_msg}")

                details = final_result.get("details", "")
                if details:
                    with st.expander("상세 오류 정보"):
                        st.code(details)

    def display_task_history(self):
        """작업 히스토리 표시 (선택사항)"""
        _ensure_session_state()  # 세션 상태 확인
        if not st.session_state.mcp_async_task_history:
            return

        st.markdown("---")
        st.subheader("📜 작업 히스토리")

        for i, task_info in enumerate(reversed(st.session_state.mcp_async_task_history[-5:])):  # 최근 5개
            task_id = task_info.get("task_id", "Unknown")
            created_at = task_info.get("created_at", "")
            user_id = task_info.get("user_id", "Unknown")

            with st.expander(f"Task {task_id[:8]}... ({created_at[:19] if created_at else 'Unknown'})"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**User ID:** {user_id}")
                    st.write(f"**Provider:** {task_info.get('provider_name', 'gmail')}")

                with col2:
                    if task_info.get('user_query'):
                        st.write(f"**Query:** {task_info.get('user_query')}")

                    if st.button(f"📊 상태 확인", key=f"history_status_{task_id}"):
                        st.session_state.mcp_async_task_id = task_id
                        st.rerun()

# 전역 UI 인스턴스
_async_ticket_mcp_ui = None

def get_async_ticket_mcp_ui() -> AsyncTicketMCPUI:
    """싱글톤 패턴으로 UI 인스턴스 반환"""
    global _async_ticket_mcp_ui
    if _async_ticket_mcp_ui is None:
        _async_ticket_mcp_ui = AsyncTicketMCPUI()
    return _async_ticket_mcp_ui

def display_async_ticket_section():
    """비동기 티켓 생성 섹션을 표시하는 편의 함수"""
    _ensure_session_state()  # 세션 상태 확인
    ui = get_async_ticket_mcp_ui()
    ui.display_async_ticket_creation_section()