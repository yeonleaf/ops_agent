#!/usr/bin/env python3
"""
향상된 티켓 UI 데모 앱
"""

import streamlit as st
from enhanced_ticket_ui import demo_ticket_ui

# 페이지 설정
st.set_page_config(
    page_title="🎫 향상된 티켓 UI 데모",
    page_icon="🎫",
    layout="wide"
)

if __name__ == "__main__":
    demo_ticket_ui()