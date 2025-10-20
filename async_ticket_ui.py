#!/usr/bin/env python3
"""
비동기 티켓 생성 UI - Streamlit Frontend
사용자가 티켓 생성을 요청하면 즉시 task_id를 받고, 실시간으로 진행 상황을 확인
"""

import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="🚀 비동기 티켓 생성 시스템",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API 서버 URL (환경에 따라 변경)
API_BASE_URL = "http://localhost:8001"

class AsyncTicketUI:
    """비동기 티켓 생성 UI 클래스"""

    def __init__(self):
        """초기화"""
        # 세션 상태 초기화
        if 'current_task_id' not in st.session_state:
            st.session_state.current_task_id = None
        if 'task_history' not in st.session_state:
            st.session_state.task_history = []
        if 'user_id' not in st.session_state:
            st.session_state.user_id = "default_user"
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
        if 'refresh_interval' not in st.session_state:
            st.session_state.refresh_interval = 3  # 3초마다 새로고침

    def create_ticket_task(self, user_id: str = "default_user", provider_name: str = "gmail",
                          user_query: Optional[str] = None) -> Optional[str]:
        """새로운 티켓 생성 작업 시작"""
        try:
            payload = {
                "user_id": user_id,
                "provider_name": provider_name,
                "user_query": user_query
            }

            logger.info(f"🚀 티켓 생성 작업 요청: {payload}")

            response = requests.post(
                f"{API_BASE_URL}/tasks/create-tickets",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                task_id = result.get("task_id")
                logger.info(f"✅ 작업 생성 성공: task_id={task_id}")
                return task_id
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ 작업 생성 실패: {error_msg}")
                st.error(f"작업 생성 실패: {error_msg}")
                return None

        except requests.exceptions.ConnectionError:
            st.error("❌ API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.")
            st.info("💡 터미널에서 다음 명령어로 API 서버를 시작하세요:")
            st.code("python async_task_api.py")
            return None
        except Exception as e:
            logger.error(f"❌ 작업 생성 중 오류: {str(e)}")
            st.error(f"작업 생성 중 오류가 발생했습니다: {str(e)}")
            return None

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        try:
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/status", timeout=5)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                st.error("❌ 작업을 찾을 수 없습니다.")
                return None
            else:
                st.error(f"상태 조회 실패: HTTP {response.status_code}")
                return None

        except requests.exceptions.ConnectionError:
            st.error("❌ API 서버에 연결할 수 없습니다.")
            return None
        except Exception as e:
            logger.error(f"❌ 상태 조회 중 오류: {str(e)}")
            st.error(f"상태 조회 중 오류: {str(e)}")
            return None

    def display_task_progress(self, task_data: Dict[str, Any]):
        """작업 진행 상황 표시"""
        task_id = task_data.get("task_id", "Unknown")
        overall_status = task_data.get("overall_status", "UNKNOWN")
        steps = task_data.get("steps", [])
        final_result = task_data.get("final_result")
        created_at = task_data.get("created_at", "")
        updated_at = task_data.get("updated_at", "")

        # 전체 상태 표시
        st.subheader(f"🎫 작업 진행 상황")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("작업 ID", task_id[:8] + "...")

        with col2:
            status_colors = {
                "PENDING": "🟡",
                "IN_PROGRESS": "🔵",
                "COMPLETED": "🟢",
                "FAILED": "🔴"
            }
            status_icon = status_colors.get(overall_status, "❓")
            st.metric("전체 상태", f"{status_icon} {overall_status}")

        with col3:
            if created_at:
                try:
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    st.metric("생성 시간", created_time.strftime("%H:%M:%S"))
                except:
                    st.metric("생성 시간", "알 수 없음")

        # 단계별 진행 상황
        st.markdown("---")
        st.subheader("📋 단계별 진행 상황")

        for i, step in enumerate(steps):
            step_name = step.get("step_name", f"단계 {i+1}")
            step_status = step.get("status", "UNKNOWN")
            step_log = step.get("log", "")
            started_at = step.get("started_at")
            completed_at = step.get("completed_at")

            # 단계 상태 아이콘
            step_status_icons = {
                "PENDING": "⏳",
                "IN_PROGRESS": "🔄",
                "COMPLETED": "✅",
                "FAILED": "❌"
            }
            step_icon = step_status_icons.get(step_status, "❓")

            # 단계 정보 표시
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 2])

                with col1:
                    st.write(f"{step_icon} **{step_name}**")
                    if step_log:
                        st.write(f"📄 {step_log}")

                with col2:
                    st.write(f"**{step_status}**")

                with col3:
                    if started_at:
                        try:
                            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                            st.write(f"🕐 시작: {start_time.strftime('%H:%M:%S')}")
                        except:
                            pass

                    if completed_at:
                        try:
                            end_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                            st.write(f"🏁 완료: {end_time.strftime('%H:%M:%S')}")
                        except:
                            pass

        # 최종 결과 표시
        if final_result and overall_status in ["COMPLETED", "FAILED"]:
            st.markdown("---")
            st.subheader("📊 최종 결과")

            if overall_status == "COMPLETED":
                st.success(f"✅ {final_result.get('message', '작업이 성공적으로 완료되었습니다.')}")

                tickets_created = final_result.get("tickets_created", 0)
                existing_tickets = final_result.get("existing_tickets", 0)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("새로 생성된 티켓", tickets_created)
                with col2:
                    st.metric("기존 티켓", existing_tickets)

            elif overall_status == "FAILED":
                st.error(f"❌ {final_result.get('message', '작업이 실패했습니다.')}")

                if final_result.get("error"):
                    with st.expander("오류 상세 정보"):
                        st.code(final_result.get("error"))

    def display_task_creation_form(self):
        """작업 생성 폼 표시"""
        st.header("🚀 새 티켓 생성 작업 시작")

        with st.form("create_task_form"):
            col1, col2 = st.columns(2)

            with col1:
                user_id = st.text_input(
                    "사용자 ID",
                    value=st.session_state.user_id,
                    help="작업을 실행할 사용자 ID"
                )

                provider_name = st.selectbox(
                    "이메일 제공자",
                    ["gmail", "outlook"],
                    index=0,
                    help="사용할 이메일 서비스 제공자"
                )

            with col2:
                user_query = st.text_area(
                    "사용자 쿼리 (선택사항)",
                    placeholder="예: 오늘 받은 업무 관련 메일로 티켓을 생성해주세요",
                    help="티켓 생성에 대한 특별한 요청사항이 있으면 입력하세요"
                )

            submitted = st.form_submit_button("🎫 티켓 생성 작업 시작", type="primary")

            if submitted:
                if user_id.strip():
                    # 사용자 ID 세션에 저장
                    st.session_state.user_id = user_id.strip()

                    # 작업 생성
                    task_id = self.create_ticket_task(
                        user_id=user_id.strip(),
                        provider_name=provider_name,
                        user_query=user_query.strip() if user_query.strip() else None
                    )

                    if task_id:
                        st.session_state.current_task_id = task_id

                        # 작업 히스토리에 추가
                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "created_at": datetime.now().isoformat(),
                            "user_id": user_id.strip(),
                            "provider_name": provider_name,
                            "user_query": user_query.strip() if user_query.strip() else None
                        })

                        st.success(f"✅ 작업이 시작되었습니다! Task ID: {task_id}")
                        st.rerun()
                else:
                    st.error("❌ 사용자 ID를 입력해주세요.")

    def display_current_task(self):
        """현재 실행 중인 작업 표시"""
        if not st.session_state.current_task_id:
            st.info("현재 실행 중인 작업이 없습니다.")
            return

        task_id = st.session_state.current_task_id

        # 작업 상태 조회
        task_data = self.get_task_status(task_id)

        if task_data:
            self.display_task_progress(task_data)

            # 작업이 완료되었거나 실패한 경우 자동 새로고침 중단
            overall_status = task_data.get("overall_status")
            if overall_status in ["COMPLETED", "FAILED"]:
                if st.button("🗑️ 현재 작업 종료", type="secondary"):
                    st.session_state.current_task_id = None
                    st.rerun()
            else:
                # 진행 중인 작업의 경우 새로고침 버튼과 자동 새로고침 옵션
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔄 수동 새로고침", type="secondary"):
                        st.rerun()

                with col2:
                    if st.button("⏹️ 작업 추적 중단", type="secondary"):
                        st.session_state.current_task_id = None
                        st.rerun()

    def display_task_history(self):
        """작업 히스토리 표시"""
        if not st.session_state.task_history:
            st.info("작업 히스토리가 없습니다.")
            return

        st.subheader("📜 작업 히스토리")

        for i, task_info in enumerate(reversed(st.session_state.task_history[-10:])):  # 최근 10개만
            task_id = task_info.get("task_id", "Unknown")
            created_at = task_info.get("created_at", "")
            user_id = task_info.get("user_id", "Unknown")

            with st.expander(f"Task {task_id[:8]}... - {created_at[:19] if created_at else 'Unknown'}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Task ID:** {task_id}")
                    st.write(f"**User ID:** {user_id}")
                    st.write(f"**Provider:** {task_info.get('provider_name', 'gmail')}")

                with col2:
                    if task_info.get('user_query'):
                        st.write(f"**Query:** {task_info.get('user_query')}")

                    if st.button(f"📊 상태 확인", key=f"status_{task_id}"):
                        st.session_state.current_task_id = task_id
                        st.rerun()

    def run(self):
        """메인 UI 실행"""
        st.title("🚀 비동기 티켓 생성 시스템")
        st.markdown("---")

        # 사이드바 설정
        with st.sidebar:
            st.header("⚙️ 설정")

            # 자동 새로고침 설정
            st.session_state.auto_refresh = st.checkbox(
                "자동 새로고침",
                value=st.session_state.auto_refresh,
                help="진행 중인 작업의 상태를 자동으로 업데이트"
            )

            if st.session_state.auto_refresh:
                st.session_state.refresh_interval = st.slider(
                    "새로고침 간격 (초)",
                    min_value=1,
                    max_value=10,
                    value=st.session_state.refresh_interval
                )

            st.markdown("---")
            st.subheader("📊 API 서버 상태")

            # API 서버 상태 확인
            try:
                response = requests.get(f"{API_BASE_URL}/health", timeout=3)
                if response.status_code == 200:
                    st.success("✅ API 서버 정상")
                else:
                    st.error("❌ API 서버 오류")
            except:
                st.error("❌ API 서버 연결 실패")

        # 메인 탭
        tab1, tab2, tab3 = st.tabs(["🎫 새 작업 생성", "📊 현재 작업 상태", "📜 작업 히스토리"])

        with tab1:
            self.display_task_creation_form()

        with tab2:
            self.display_current_task()

            # 자동 새로고침 (진행 중인 작업이 있고 자동 새로고침이 활성화된 경우)
            if (st.session_state.current_task_id and
                st.session_state.auto_refresh and
                st.session_state.current_task_id):

                task_data = self.get_task_status(st.session_state.current_task_id)
                if task_data and task_data.get("overall_status") not in ["COMPLETED", "FAILED"]:
                    time.sleep(st.session_state.refresh_interval)
                    st.rerun()

        with tab3:
            self.display_task_history()


def main():
    """메인 함수"""
    app = AsyncTicketUI()
    app.run()


if __name__ == "__main__":
    main()