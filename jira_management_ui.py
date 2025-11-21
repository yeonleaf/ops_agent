#!/usr/bin/env python3
"""
Jira 연동 관리 UI

저장된 JQL 표시, 수동 동기화 트리거, 동기화 이력 조회
"""

import streamlit as st
from auth_client import AuthClient
from typing import Dict, Any
from datetime import datetime


def render_jira_management(auth_client: AuthClient):
    """
    Jira 연동 관리 페이지

    Args:
        auth_client: AuthClient 인스턴스
    """
    st.markdown("## Jira 연동 관리")

    # Jira 연동 상태 확인
    jira_status = auth_client.get_jira_integration()

    if not jira_status.get("success") or not jira_status.get("is_complete"):
        st.warning("⚠️ Jira 연동이 완료되지 않았습니다.")
        st.info("먼저 'Jira 연동 설정' 탭에서 연동을 완료해주세요.")
        return

    # 연동된 Jira 정보 표시
    st.success("✅ Jira 연동이 완료되었습니다.")

    if jira_status.get("jira_endpoint"):
        st.info(f"**연동된 Jira 엔드포인트:** {jira_status['jira_endpoint']}")

    st.markdown("---")

    # 저장된 JQL 표시
    st.markdown("### 📝 저장된 JQL 쿼리")

    # JQL 조회
    if jira_status.get("has_jql") and jira_status.get("jql"):
        st.code(jira_status["jql"], language="sql")
        st.caption("이 JQL 쿼리로 Jira 이슈를 동기화합니다.")
    elif jira_status.get("has_projects") and jira_status.get("has_labels"):
        st.info("기존 방식(프로젝트-레이블)으로 연동되었습니다. JQL 방식으로 전환하려면 재설정하세요.")
    else:
        st.warning("저장된 JQL 쿼리가 없습니다.")

    st.markdown("---")

    # 수동 동기화 섹션
    st.markdown("### 🔄 수동 동기화")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 증분 동기화", key="incremental_sync", use_container_width=True, type="primary"):
            with st.spinner("Jira 동기화 시작 중..."):
                result = auth_client.trigger_jira_sync(force_full_sync=False)

                if result.get("success"):
                    st.success("✅ 증분 동기화가 시작되었습니다!")
                    st.info("마지막 동기화 이후 업데이트된 이슈만 가져옵니다.")
                else:
                    st.error(f"❌ 동기화 시작 실패: {result.get('message', '알 수 없는 오류')}")

    with col2:
        if st.button("🔄 전체 재동기화", key="full_sync", use_container_width=True):
            st.warning("⚠️ 전체 재동기화는 모든 이슈를 다시 가져옵니다. 시간이 오래 걸릴 수 있습니다.")

            if st.button("확인 - 전체 재동기화 시작", key="confirm_full_sync", type="primary"):
                with st.spinner("전체 재동기화 시작 중..."):
                    result = auth_client.trigger_jira_sync(force_full_sync=True)

                    if result.get("success"):
                        st.success("✅ 전체 재동기화가 시작되었습니다!")
                        st.info("모든 이슈를 다시 가져옵니다. 완료까지 시간이 소요됩니다.")
                    else:
                        st.error(f"❌ 동기화 시작 실패: {result.get('message', '알 수 없는 오류')}")

    st.markdown("---")

    # 동기화 상태 섹션
    st.markdown("### 📊 동기화 상태")

    # 상태 조회 버튼
    if st.button("🔍 최신 상태 조회", key="refresh_status"):
        st.rerun()

    # 동기화 상태 조회
    with st.spinner("동기화 상태 조회 중..."):
        sync_status = auth_client.get_jira_sync_status()

    if sync_status.get("success"):
        last_run_at = sync_status.get("last_run_at")
        status = sync_status.get("status")
        processed_count = sync_status.get("processed_count", 0)
        error_message = sync_status.get("error_message")
        is_running = sync_status.get("is_running", False)

        # 상태 표시
        if is_running:
            st.info("🔄 동기화가 실행 중입니다...")
        elif status == "success":
            st.success(f"✅ 마지막 동기화 성공")
        elif status == "failed":
            st.error(f"❌ 마지막 동기화 실패")
        else:
            st.info("ℹ️ 아직 동기화 이력이 없습니다.")

        # 상세 정보 표시
        if last_run_at:
            col1, col2 = st.columns(2)

            with col1:
                st.metric("마지막 실행 시각", format_datetime(last_run_at))
                st.metric("처리된 청크 수", f"{processed_count}개")

            with col2:
                st.metric("상태", "성공" if status == "success" else "실패")
                if error_message:
                    st.error(f"오류 메시지: {error_message}")

        # 동기화 이력 표시 (테이블)
        if last_run_at:
            with st.expander("📋 상세 정보 보기"):
                st.json({
                    "last_run_at": last_run_at,
                    "status": status,
                    "processed_count": processed_count,
                    "error_message": error_message,
                    "is_running": is_running
                })
    else:
        st.error(f"❌ 상태 조회 실패: {sync_status.get('message', '알 수 없는 오류')}")

    st.markdown("---")

    # 재설정 섹션
    st.markdown("### ⚙️ 연동 설정")

    with st.expander("위험: 연동 재설정"):
        st.warning("⚠️ Jira 연동을 재설정하면 모든 설정이 삭제됩니다.")
        st.info("재설정 후 다시 연동을 진행해야 합니다.")

        if st.button("🗑️ Jira 연동 재설정", key="reset_jira", type="secondary"):
            with st.spinner("Jira 연동 정보 삭제 중..."):
                reset_result = auth_client.reset_jira_integration()

                if reset_result.get("success"):
                    st.success("✅ Jira 연동 정보가 삭제되었습니다.")
                    st.info("'Jira 연동 설정' 탭에서 다시 연동을 진행해주세요.")
                    st.rerun()
                else:
                    st.error(f"❌ 삭제 실패: {reset_result.get('message', '알 수 없는 오류')}")


def format_datetime(dt_str: str) -> str:
    """
    ISO 형식 날짜 문자열을 읽기 쉬운 형식으로 변환

    Args:
        dt_str: ISO 형식 날짜 문자열

    Returns:
        포맷된 날짜 문자열
    """
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_str


if __name__ == "__main__":
    # 테스트용
    st.set_page_config(page_title="Jira 연동 관리", page_icon="🔧")

    # 더미 AuthClient (테스트용)
    class DummyAuthClient:
        def get_jira_integration(self):
            return {
                "success": True,
                "is_complete": True,
                "jira_endpoint": "https://jira.example.com"
            }

        def trigger_jira_sync(self, force_full_sync=False):
            return {"success": True, "message": "동기화 시작됨"}

        def get_jira_sync_status(self):
            return {
                "success": True,
                "last_run_at": "2025-11-21T10:30:00",
                "status": "success",
                "processed_count": 42,
                "error_message": None,
                "is_running": False
            }

        def reset_jira_integration(self):
            return {"success": True, "message": "삭제됨"}

    render_jira_management(DummyAuthClient())
