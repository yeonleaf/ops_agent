#!/usr/bin/env python3
"""
인증 없이 비동기 티켓 기능만 테스트
"""

import streamlit as st
from async_ticket_mcp_ui import get_async_ticket_mcp_ui

# 페이지 설정
st.set_page_config(
    page_title="🚀 비동기 티켓 테스트",
    page_icon="🎫",
    layout="wide"
)

def main():
    """메인 함수"""
    st.title("🚀 비동기 티켓 생성 테스트")
    st.markdown("---")

    # 비동기 티켓 UI 표시
    try:
        ui = get_async_ticket_mcp_ui()
        ui.display_async_ticket_creation_section()

        # 작업 히스토리도 표시
        ui.display_task_history()

    except Exception as e:
        st.error(f"❌ 오류: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()