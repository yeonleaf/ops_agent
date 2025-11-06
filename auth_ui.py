#!/usr/bin/env python3
"""
Streamlit 앱에서 사용할 인증 UI 컴포넌트
로그인, 회원가입, 연동 설정 등의 UI를 제공
"""

import streamlit as st
from auth_client import auth_client
from typing import Optional

def show_login_form():
    """로그인 폼 표시"""
    # 탭으로 로그인/회원가입 분리
    tab1, tab2 = st.tabs(["로그인", "회원가입"])

    with tab1:
        with st.form("login_form"):
            st.subheader("🔐 로그인")

            email = st.text_input("이메일", placeholder="user@example.com", key="login_email")
            password = st.text_input("비밀번호", type="password", key="login_password")

            login_clicked = st.form_submit_button("로그인", type="primary", use_container_width=True)

            if login_clicked:
                if not email or not password:
                    st.error("이메일과 비밀번호를 입력해주세요.")
                else:
                    with st.spinner("로그인 중..."):
                        result = auth_client.login(email, password)
                        if result.get("success"):
                            st.success("로그인 성공!")
                            st.rerun()
                        else:
                            st.error(f"로그인 실패: {result.get('message', '알 수 없는 오류')}")

    with tab2:
        with st.form("signup_form"):
            st.subheader("📝 회원가입")

            email = st.text_input("이메일", placeholder="user@example.com", key="signup_email")
            password = st.text_input("비밀번호", type="password", key="signup_password")
            password_confirm = st.text_input("비밀번호 확인", type="password", key="signup_password_confirm")

            col1, col2 = st.columns(2)
            with col1:
                user_name = st.text_input("이름", placeholder="홍길동", key="signup_user_name")
            with col2:
                system_name = st.text_input("담당 시스템 (선택)", placeholder="NCMS, EUXP 등", key="signup_system_name")

            signup_clicked = st.form_submit_button("회원가입", type="primary", use_container_width=True)

            if signup_clicked:
                if not email or not password or not user_name:
                    st.error("이메일, 비밀번호, 이름을 모두 입력해주세요.")
                elif password != password_confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    with st.spinner("회원가입 중..."):
                        result = auth_client.signup(email, password, user_name, system_name or None)
                        if result.get("success"):
                            st.success("회원가입 성공! 이제 로그인 탭에서 로그인해주세요.")
                        else:
                            st.error(f"회원가입 실패: {result.get('message', '알 수 없는 오류')}")

def show_user_info():
    """사용자 정보 및 연동 상태 표시"""
    user_info = auth_client.get_current_user()
    if not user_info:
        return
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 사용자 정보")
    st.sidebar.write(f"**이메일:** {user_info.get('email', 'N/A')}")
    

def show_integration_settings():
    """연동 설정 UI"""
    st.subheader("🔗 서비스 연동 설정")
    
    # Jira 연동 설정
    with st.expander("Jira 연동 설정", expanded=True):
        st.write("Jira API 토큰을 입력하여 티켓을 자동으로 생성할 수 있습니다.")
        
        with st.form("jira_integration_form"):
            jira_endpoint = st.text_input(
                "Jira Endpoint", 
                placeholder="https://your-domain.atlassian.net",
                help="Jira 인스턴스의 기본 URL"
            )
            jira_api_token = st.text_input(
                "Jira API Token", 
                type="password",
                help="Jira에서 생성한 API 토큰"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                save_jira = st.form_submit_button("Jira 연동 저장", type="primary")
            with col2:
                check_jira = st.form_submit_button("연동 상태 확인")
            
            if save_jira:
                if jira_endpoint and jira_api_token:
                    with st.spinner("Jira 연동 정보 저장 중..."):
                        result = auth_client.update_jira_integration(jira_endpoint, jira_api_token)
                        if result.get("success"):
                            st.success("Jira 연동 정보가 저장되었습니다!")
                        else:
                            st.error(f"저장 실패: {result.get('message', '알 수 없는 오류')}")
                else:
                    st.error("Jira Endpoint와 API Token을 모두 입력해주세요.")

            if check_jira:
                with st.spinner("Jira 연동 상태 확인 중..."):
                    result = auth_client.get_jira_integration()
                    if result.get("success"):
                        st.success(f"Jira 연동됨: {result.get('jira_endpoint')}")
                    else:
                        st.warning("Jira가 연동되지 않았습니다.")


def show_auth_required_message():
    """인증 필요 메시지 표시"""
    st.error("🔐 로그인이 필요합니다.")
    st.info("이 기능을 사용하려면 먼저 로그인해주세요.")
    
    # 로그인 폼 표시
    show_login_form()

def check_auth_and_show_ui():
    """인증 상태 확인 및 UI 표시"""
    print(f"🍪 check_auth_and_show_ui() 호출됨")

    # 세션 ID 체크 - 없으면 로그인 상태 초기화
    if 'session_id' not in st.session_state:
        print(f"🍪 세션 ID 없음 - 로그인 상태 초기화")
        st.session_state.is_logged_in = False
        if 'user_email' in st.session_state:
            del st.session_state.user_email

    print(f"🍪 auth_client.is_logged_in() 호출 전")

    if not auth_client.is_logged_in():
        print(f"🍪 로그인되지 않음 - 인증 UI 표시")
        show_auth_required_message()
        return False
    else:
        print(f"🍪 로그인됨 - 사용자 정보 UI 표시")
        # get_current_user()에서 이미 세션에 이메일을 저장하므로 중복 제거
        show_user_info()
        return True
 