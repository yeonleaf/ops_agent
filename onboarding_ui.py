#!/usr/bin/env python3
"""
신규 가입자를 위한 온보딩 UI
Atlassian 연동과 메일 연동을 완료하도록 유도
"""

import streamlit as st
from auth_client import AuthClient
import webbrowser
from typing import Optional
from jira_onboarding_ui import render_jira_onboarding_tab

def show_onboarding_process(email: str) -> bool:
    """
    온보딩 프로세스 UI 표시

    Args:
        email: 현재 로그인된 사용자의 이메일

    Returns:
        bool: 모든 연동이 완료되면 True, 아니면 False
    """
    # 세션 상태 확인
    if 'session_id' not in st.session_state:
        st.error("⚠️ 세션이 만료되었습니다.")
        st.info("다시 로그인 페이지로 이동합니다...")

        # 로그인 상태 초기화
        st.session_state.is_logged_in = False
        if 'user_email' in st.session_state:
            del st.session_state.user_email

        # 페이지 새로고침하여 로그인 화면으로 돌아감
        st.rerun()
        return False

    auth_client = AuthClient()

    # 세션 상태 초기화
    if 'atlassian_connected' not in st.session_state:
        st.session_state.atlassian_connected = False
    if 'kakao_connected' not in st.session_state:
        st.session_state.kakao_connected = False
    if 'slack_connected' not in st.session_state:
        st.session_state.slack_connected = False

    # DB에서 연동 상태 확인
    _check_integration_status(auth_client)

    # 제목
    st.title("🚀 환영합니다!")
    st.markdown("서비스를 시작하기 위해 필수 연동을 완료해주세요.")

    # 진행률 표시
    total_steps = 1  # Atlassian만 필수
    completed_steps = sum([
        st.session_state.atlassian_connected
    ])
    progress = completed_steps / total_steps

    st.progress(progress)
    st.markdown(f"**진행률: {completed_steps}/{total_steps} 완료 (필수 연동)**")

    # 탭 생성 (카카오, 슬랙은 선택 사항)
    tab1, tab2, tab3 = st.tabs([
        "🔧 Atlassian 연동" + (" ✅" if st.session_state.atlassian_connected else ""),
        "💬 카카오 연동 (선택)" + (" ✅" if st.session_state.kakao_connected else ""),
        "💼 슬랙 연동 (선택)" + (" ✅" if st.session_state.slack_connected else "")
    ])

    # 탭 1: Atlassian 연동 (새로운 4단계 온보딩 UI 사용)
    with tab1:
        render_jira_onboarding_tab(auth_client, email)

    # 탭 2: 카카오 연동 (선택 사항)
    with tab2:
        _render_kakao_tab(auth_client, email)

    # 탭 3: 슬랙 연동 (선택 사항)
    with tab3:
        _render_slack_tab(auth_client, email)

    # 완료 조건 체크
    all_completed = st.session_state.atlassian_connected

    if all_completed:
        st.success("🎉 모든 연동이 완료되었습니다! 이제 서비스를 시작할 수 있습니다.")
        if st.button("시작하기", type="primary", use_container_width=True):
            st.session_state.onboarding_completed = True
            st.rerun()

    return all_completed


def _check_integration_status(auth_client: AuthClient):
    """DB에서 연동 상태 확인하여 세션 상태 업데이트"""

    # Atlassian(Jira) 연동 상태 확인 - 새로운 온보딩 프로세스 확인
    # endpoint, token, project, labels 모두 있어야 완전 연동으로 간주
    jira_status = auth_client.get_jira_integration()
    if jira_status.get("success") and jira_status.get("has_api_token"):
        st.session_state.atlassian_connected = True

    # 카카오 연동 상태 확인
    kakao_status = auth_client.get_kakao_integration()
    if kakao_status.get("success") and kakao_status.get("linked"):
        st.session_state.kakao_connected = True

    # 슬랙 연동 상태 확인
    slack_status = auth_client.get_slack_integration()
    if slack_status.get("success") and slack_status.get("linked"):
        st.session_state.slack_connected = True


def _render_kakao_tab(auth_client: AuthClient, email: str):
    """카카오 연동 탭 렌더링"""

    if st.session_state.kakao_connected:
        st.success("✅ 카카오 연동이 완료되었습니다.")

        # 연동 정보 표시
        kakao_info = auth_client.get_kakao_integration()
        if kakao_info.get("success"):
            if kakao_info.get("kakao_email"):
                st.info(f"**연동된 카카오 이메일:** {kakao_info['kakao_email']}")
            if kakao_info.get("kakao_nickname"):
                st.info(f"**카카오 닉네임:** {kakao_info['kakao_nickname']}")

        # 재설정 옵션
        if st.button("다시 설정하기", key="reset_kakao"):
            st.session_state.kakao_connected = False
            st.rerun()
    else:
        st.markdown("### 카카오 계정 연동 (선택 사항)")
        st.markdown("카카오톡으로 티켓 알림을 받고 싶다면 카카오 계정을 연동해주세요.")

        st.markdown("#### 💬 카카오 연동 혜택")
        st.markdown("- 카카오톡으로 티켓 생성 알림 받기")
        st.markdown("- 카카오톡으로 티켓 상태 변경 알림 받기")
        st.markdown("- 카카오톡에서 간편하게 티켓 확인하기")

        st.markdown("---")

        # 세션 상태 초기화
        if 'kakao_auth_data' not in st.session_state:
            st.session_state.kakao_auth_data = None
        if 'kakao_auth_code' not in st.session_state:
            st.session_state.kakao_auth_code = None

        # 디버깅: 현재 세션 정보 표시
        with st.expander("🔍 디버깅: 세션 정보", expanded=False):
            st.write("**세션 ID:**", st.session_state.get('session_id', '없음'))
            st.write("**사용자 이메일:**", st.session_state.get('user_email', '없음'))

            # 사용자 정보 가져오기
            user_info = auth_client.get_current_user()
            if user_info:
                st.write("**사용자 ID (from API):**", user_info.get('user_id', '없음'))
                st.write("**전체 사용자 정보:**", user_info)
            else:
                st.write("**사용자 정보:**", "API에서 가져올 수 없음")

        if st.button("💬 카카오 연동하기", key="kakao_connect", use_container_width=True, type="primary"):
            # OAuth URL 생성 (세션 ID 포함)
            session_id = st.session_state.get('session_id', '')
            oauth_url = f"http://localhost:8002/settings/link/kakao?session_id={session_id}"
            st.markdown(f"[카카오 연동 페이지로 이동]({oauth_url})")
            st.info("새 창에서 카카오 인증을 완료한 후 아래 '연동 완료 확인' 버튼을 클릭해주세요.")

        # 세션 ID 수동 입력 (더 간단하게)
        st.markdown("---")
        st.markdown("### 📥 카카오 인증 정보 가져오기")

        with st.expander("🔧 세션 ID 입력", expanded=True):
            st.info("카카오 인증 완료 페이지에 표시된 세션 ID를 복사하여 입력하세요.")

            kakao_session_id_input = st.text_input(
                "카카오 세션 ID (전체)",
                key="kakao_session_id_input",
                placeholder="예: 12345678-1234-5678-1234-567812345678",
                help="카카오 인증 완료 창에 ' 세션 ID: 12345678...' 형태로 표시됩니다"
            )

            if st.button("🔍 카카오 정보 가져오기", key="fetch_by_session", use_container_width=True, type="primary"):
                if kakao_session_id_input:
                    with st.spinner("임시 저장소에서 카카오 정보 조회 중..."):
                        result = auth_client.get_kakao_temp_data(kakao_session_id_input)

                        # 디버깅: API 응답 표시
                        with st.expander("🔍 API 응답 (디버깅)", expanded=True):
                            st.json(result)

                        if result.get("success"):
                            data = result.get("data", {})

                            # 데이터가 비어있는지 확인
                            if not data:
                                st.error("❌ 임시 저장소에 데이터가 없습니다. 카카오 인증을 다시 시도해주세요.")
                            else:
                                st.session_state.kakao_auth_data = {
                                    'kakao_id': data.get('kakao_id', ''),
                                    'user_id': data.get('user_id', '')
                                }
                                st.session_state.kakao_session_id = kakao_session_id_input

                                # 성공 메시지와 함께 데이터 미리보기
                                st.success("✅ 카카오 정보를 성공적으로 가져왔습니다!")
                                st.write("**카카오 ID:**", data.get('kakao_id', '없음'))
                                st.write("**User ID:**", data.get('user_id', '없음'))

                                st.info("아래로 스크롤하여 연동 완료 버튼을 눌러주세요.")
                                st.rerun()
                        else:
                            st.error(f"❌ 오류: {result.get('message', '알 수 없는 오류')}")
                            st.info("💡 팁: 카카오 인증을 다시 시도하거나, 세션 ID를 정확히 입력했는지 확인해주세요.")
                else:
                    st.warning("⚠️ 세션 ID를 입력해주세요.")

        # 카카오 인증 정보가 있는 경우 표시
        if st.session_state.kakao_auth_data:
            kakao_data = st.session_state.kakao_auth_data
            st.success("✅ 카카오 인증이 완료되었습니다!")

            # 디버깅: API에서 받아온 카카오 정보 표시
            with st.expander("🔍 디버깅: API 응답 데이터", expanded=True):
                st.write("**카카오 ID:**", kakao_data.get('kakao_id', '없음'))
                st.write("**전체 데이터:**", kakao_data)

                # 사용자 정보도 함께 표시
                user_info = auth_client.get_current_user()
                if user_info:
                    st.write("**현재 로그인된 사용자 ID:**", user_info.get('user_id', '없음'))
                    st.write("**현재 로그인된 이메일:**", user_info.get('email', '없음'))

            st.info(f"**카카오 ID:** {kakao_data.get('kakao_id', '정보 없음')}")

            st.markdown("---")
            st.markdown("위 정보로 연동을 완료하시겠습니까?")

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("✅ 연동 완료", key="save_kakao", use_container_width=True, type="primary"):
                    with st.spinner("카카오 연동 저장 중..."):
                        result = auth_client.save_kakao_integration(
                            kakao_id=kakao_data.get('kakao_id', '')
                        )

                        if result.get("success"):
                            # 임시 저장소에서 삭제
                            if 'kakao_session_id' in st.session_state:
                                delete_result = auth_client.delete_kakao_temp_data(st.session_state.kakao_session_id)
                                if delete_result.get("success"):
                                    st.info("임시 데이터 삭제 완료")

                            st.session_state.kakao_connected = True
                            st.session_state.kakao_auth_data = None
                            st.session_state.pop('kakao_session_id', None)
                            st.success("✅ 카카오 연동이 완료되었습니다!")
                            st.rerun()
                        else:
                            st.error(f"❌ 연동 실패: {result.get('message', '알 수 없는 오류')}")

            with col_cancel:
                if st.button("❌ 취소", key="cancel_kakao", use_container_width=True):
                    st.session_state.kakao_auth_data = None
                    st.rerun()
        else:
            # 연동 상태 확인 버튼 (인증 정보가 없을 때만 표시)
            if st.button("연동 상태 확인", key="check_kakao"):
                # DB에서 연동 상태 확인
                _check_integration_status(auth_client)
                if st.session_state.kakao_connected:
                    st.success("✅ 카카오 연동이 완료되었습니다!")
                    st.rerun()
                else:
                    # 임시로 카카오 인증 데이터를 세션에 저장 (실제로는 OAuth 콜백에서 받아와야 함)
                    # 여기서는 임시 테스트용으로 입력 폼 제공
                    st.info("카카오 인증 창에서 인증을 완료하셨나요?")

                    with st.expander("카카오 정보 수동 입력 (테스트용)", expanded=False):
                        kakao_email_input = st.text_input("카카오 이메일", key="kakao_email_input")
                        kakao_nickname_input = st.text_input("카카오 닉네임", key="kakao_nickname_input")
                        kakao_id_input = st.text_input("카카오 ID", key="kakao_id_input")

                        if st.button("정보 입력 완료", key="submit_kakao_manual"):
                            if kakao_email_input or kakao_nickname_input:
                                st.session_state.kakao_auth_data = {
                                    'kakao_id': kakao_id_input or 'test_id',
                                    'kakao_email': kakao_email_input,
                                    'kakao_nickname': kakao_nickname_input
                                }
                                st.rerun()
                            else:
                                st.warning("최소한 이메일 또는 닉네임을 입력해주세요.")

        st.markdown("---")
        st.markdown("**참고사항:**")
        st.markdown("- 카카오 연동은 선택 사항입니다.")
        st.markdown("- 나중에 계정 설정에서 언제든 연동할 수 있습니다.")
        st.markdown("- 카카오 계정 정보는 안전하게 암호화되어 저장됩니다.")


def _render_slack_tab(auth_client: AuthClient, email: str):
    """슬랙 연동 탭 렌더링"""

    if st.session_state.slack_connected:
        st.success("✅ 슬랙 연동이 완료되었습니다.")

        # 연동 정보 표시
        slack_info = auth_client.get_slack_integration()
        if slack_info.get("success"):
            if slack_info.get("slack_user_id"):
                st.info(f"**연동된 슬랙 사용자 ID:** {slack_info['slack_user_id']}")

        # 재설정 옵션
        if st.button("다시 설정하기", key="reset_slack"):
            st.session_state.slack_connected = False
            st.rerun()
    else:
        st.markdown("### 슬랙 계정 연동 (선택 사항)")
        st.markdown("슬랙으로 티켓 알림을 받고 싶다면 슬랙 계정을 연동해주세요.")

        st.markdown("#### 💼 슬랙 연동 혜택")
        st.markdown("- 슬랙으로 티켓 생성 알림 받기")
        st.markdown("- 슬랙으로 티켓 상태 변경 알림 받기")
        st.markdown("- 슬랙에서 간편하게 티켓 확인하기")
        st.markdown("- 슬랙 멘션으로 티켓 생성하기")

        st.markdown("---")

        if st.button("💼 슬랙 연동하기", key="slack_connect", use_container_width=True, type="primary"):
            # OAuth URL 생성 (세션 ID 포함)
            session_id = st.session_state.get('session_id', '')
            oauth_url = f"http://localhost:8002/settings/link/slack?session_id={session_id}"
            st.markdown(f"[슬랙 연동 페이지로 이동]({oauth_url})")
            st.info("새 창에서 슬랙 인증을 완료한 후 아래 '연동 완료 확인' 버튼을 클릭해주세요.")

        # 연동 상태 확인 버튼
        if st.button("연동 상태 확인", key="check_slack"):
            _check_integration_status(auth_client)
            if st.session_state.slack_connected:
                st.success("✅ 슬랙 연동이 완료되었습니다!")
                st.rerun()
            else:
                st.warning("아직 연동이 완료되지 않았습니다.")

        st.markdown("---")
        st.markdown("**참고사항:**")
        st.markdown("- 슬랙 연동은 선택 사항입니다.")
        st.markdown("- 나중에 계정 설정에서 언제든 연동할 수 있습니다.")
        st.markdown("- 슬랙 계정 정보는 안전하게 암호화되어 저장됩니다.")
        st.markdown("- 슬랙 워크스페이스에서 앱을 설치해야 합니다.")
