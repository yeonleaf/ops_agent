#!/usr/bin/env python3
"""
Jira 최초 연동을 위한 4단계 온보딩 UI 컴포넌트
"""

import streamlit as st
from auth_client import AuthClient
from typing import Dict, List, Any
import json


def render_jira_onboarding_tab(auth_client: AuthClient, email: str):
    """
    Jira 4단계 온보딩 탭 렌더링

    Step 1: Endpoint & Token 입력
    Step 2: /myself API 검증 및 저장
    Step 3: /project API 호출 및 프로젝트 선택
    Step 4: 레이블 입력 및 /jql 검증

    Args:
        auth_client: AuthClient 인스턴스
        email: 현재 로그인된 사용자 이메일
    """

    # 세션 상태 확인
    if 'session_id' not in st.session_state:
        st.error("⚠️ 세션이 만료되었습니다.")
        st.info("다시 로그인 페이지로 이동합니다...")

        # 로그인 상태 초기화
        st.session_state.is_logged_in = False
        if 'user_email' in st.session_state:
            del st.session_state.user_email

        # 페이지 새로고침
        st.rerun()
        return

    # 세션 상태 초기화
    if 'jira_onboarding_step' not in st.session_state:
        st.session_state.jira_onboarding_step = 1
    if 'jira_endpoint' not in st.session_state:
        st.session_state.jira_endpoint = ""
    if 'jira_api_token' not in st.session_state:
        st.session_state.jira_api_token = ""
    if 'jira_user_info' not in st.session_state:
        st.session_state.jira_user_info = None
    if 'jira_available_projects' not in st.session_state:
        st.session_state.jira_available_projects = []
    if 'jira_selected_projects' not in st.session_state:
        st.session_state.jira_selected_projects = []
    if 'jira_labels_config' not in st.session_state:
        st.session_state.jira_labels_config = {}

    # 연동 완료 상태 확인 (모든 단계가 완료되었는지 확인)
    jira_status = auth_client.get_jira_integration()
    if jira_status.get("success") and jira_status.get("is_complete"):
        st.success("✅ Jira 연동이 완료되었습니다.")

        # 연동 정보 표시
        if jira_status.get("jira_endpoint"):
            st.info(f"**연동된 Jira 엔드포인트:** {jira_status['jira_endpoint']}")

        # 재설정 옵션
        if st.button("다시 설정하기", key="reset_jira_onboarding"):
            # 세션 ID 확인
            if 'session_id' not in st.session_state:
                st.error("⚠️ 세션이 만료되었습니다. 다시 로그인해주세요.")
                return

            with st.spinner("Jira 연동 정보 삭제 중..."):
                # DB에서 Jira 연동 정보 삭제
                st.write(f"디버깅: session_id = {st.session_state.session_id[:10]}...")
                reset_result = auth_client.reset_jira_integration()
                st.write(f"디버깅: reset_result = {reset_result}")

                if reset_result.get("success"):
                    # 세션 상태 초기화
                    st.session_state.jira_onboarding_step = 1
                    st.session_state.jira_endpoint = ""
                    st.session_state.jira_api_token = ""
                    st.session_state.jira_user_info = None
                    st.session_state.jira_available_projects = []
                    st.session_state.jira_selected_projects = []
                    st.session_state.jira_labels_config = {}
                    st.session_state.atlassian_connected = False

                    st.success("✅ Jira 연동 정보가 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error(f"❌ 삭제 실패: {reset_result.get('message', '알 수 없는 오류')}")
        return

    # 진행 단계 표시
    st.markdown("### Jira 연동 설정")
    current_step = st.session_state.jira_onboarding_step
    st.progress(current_step / 4)
    st.markdown(f"**진행 단계: {current_step}/4**")

    # 디버깅 정보
    with st.expander("🔍 디버깅 정보"):
        st.write(f"현재 단계: {current_step}")
        st.write(f"endpoint: {st.session_state.jira_endpoint}")
        st.write(f"token 저장됨: {bool(st.session_state.jira_api_token)}")
        st.write(f"user_info: {st.session_state.jira_user_info}")
        st.write(f"선택된 프로젝트: {st.session_state.jira_selected_projects}")
        st.write(f"레이블 설정: {st.session_state.jira_labels_config}")

    # 단계별 UI 렌더링
    if current_step == 1:
        _render_step1_credentials(auth_client)
    elif current_step == 2:
        _render_step2_validation(auth_client)
    elif current_step == 3:
        _render_step3_projects(auth_client)
    elif current_step == 4:
        _render_step4_labels(auth_client)


def _render_step1_credentials(auth_client: AuthClient):
    """Step 1: Endpoint & Token 입력"""

    st.markdown("#### Step 1: Jira 인증 정보 입력")
    st.markdown("Jira 엔드포인트와 API 토큰을 입력해주세요.")

    with st.form("jira_credentials_form"):
        jira_endpoint = st.text_input(
            "Jira 엔드포인트",
            value=st.session_state.jira_endpoint,
            placeholder="https://your-domain.atlassian.net",
            help="Atlassian 클라우드의 도메인을 입력하세요."
        )

        jira_api_token = st.text_input(
            "API 토큰",
            value=st.session_state.jira_api_token,
            type="password",
            help="Atlassian 계정 설정에서 생성한 API 토큰을 입력하세요."
        )

        st.markdown("---")
        st.markdown("**API 토큰 생성 방법:**")
        st.markdown("1. [Atlassian 계정 설정](https://id.atlassian.com/manage-profile/security/api-tokens)으로 이동")
        st.markdown("2. 'API 토큰 생성' 클릭")
        st.markdown("3. 생성된 토큰을 복사하여 위에 붙여넣기")

        submitted = st.form_submit_button("다음 단계", type="primary", use_container_width=True)

        if submitted:
            if not jira_endpoint or not jira_api_token:
                st.error("모든 항목을 입력해주세요.")
            elif not jira_endpoint.startswith("https://"):
                st.error("Jira 엔드포인트는 https://로 시작해야 합니다.")
            else:
                # 세션에 저장
                st.session_state.jira_endpoint = jira_endpoint
                st.session_state.jira_api_token = jira_api_token
                st.session_state.jira_onboarding_step = 2
                st.rerun()


def _render_step2_validation(auth_client: AuthClient):
    """Step 2: /myself API 검증 및 저장"""

    st.markdown("#### Step 2: Jira 인증 정보 검증")
    st.markdown("입력하신 정보로 Jira에 연결을 시도합니다.")

    # 입력된 정보 표시
    st.info(f"**Jira 엔드포인트:** {st.session_state.jira_endpoint}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← 이전 단계", key="back_to_step1", use_container_width=True):
            st.session_state.jira_onboarding_step = 1
            st.rerun()

    with col2:
        if st.button("인증 검증하기", key="validate_jira", type="primary", use_container_width=True):
            with st.spinner("Jira 인증 정보 검증 중..."):
                # 디버깅 정보
                st.write(f"🔍 디버깅: endpoint = {st.session_state.jira_endpoint}")
                st.write(f"🔍 디버깅: token 길이 = {len(st.session_state.jira_api_token)}")

                # /myself API 호출
                result = auth_client.validate_jira_credentials(
                    st.session_state.jira_endpoint,
                    st.session_state.jira_api_token
                )

                st.write(f"🔍 디버깅: validate 결과 = {result}")

                if result.get("success"):
                    st.success(f"✅ 인증 성공: {result.get('message', '연결되었습니다.')}")

                    # 사용자 정보 저장
                    st.session_state.jira_user_info = result.get("user_info", {})
                    st.write(f"🔍 디버깅: user_info = {st.session_state.jira_user_info}")

                    # Integration 테이블에 저장
                    save_result = auth_client.save_jira_credentials(
                        st.session_state.jira_endpoint,
                        st.session_state.jira_api_token
                    )

                    st.write(f"🔍 디버깅: save 결과 = {save_result}")

                    if save_result.get("success"):
                        st.info("인증 정보가 저장되었습니다.")
                        st.write("🔍 디버깅: Step 3으로 이동합니다...")
                        st.session_state.jira_onboarding_step = 3
                        st.rerun()
                    else:
                        st.error(f"❌ 저장 실패: {save_result.get('message', '알 수 없는 오류')}")
                else:
                    st.error(f"❌ 인증 실패: {result.get('message', '알 수 없는 오류')}")
                    if "error" in result:
                        st.error(f"상세 오류: {result['error']}")


def _render_step3_projects(auth_client: AuthClient):
    """Step 3: /project API 호출 및 프로젝트 선택"""

    st.markdown("#### Step 3: 연동할 프로젝트 선택")
    st.markdown("연동할 Jira 프로젝트를 선택해주세요.")

    # 프로젝트 목록 조회 (최초 1회만)
    if not st.session_state.jira_available_projects:
        with st.spinner("Jira 프로젝트 목록 조회 중..."):
            result = auth_client.get_jira_projects()

            if result.get("success"):
                st.session_state.jira_available_projects = result.get("projects", [])
                st.success(f"✅ {len(st.session_state.jira_available_projects)}개의 프로젝트를 찾았습니다.")
            else:
                st.error(f"❌ 프로젝트 조회 실패: {result.get('message', '알 수 없는 오류')}")
                if st.button("← 이전 단계로 돌아가기", key="back_to_step2_error"):
                    st.session_state.jira_onboarding_step = 2
                    st.rerun()
                return

    # 프로젝트 선택 UI
    if st.session_state.jira_available_projects:
        st.markdown(f"**접근 가능한 프로젝트: {len(st.session_state.jira_available_projects)}개**")

        # 프로젝트 선택 (다중 선택)
        selected_keys = st.multiselect(
            "연동할 프로젝트 선택 (다중 선택 가능)",
            options=[p["key"] for p in st.session_state.jira_available_projects],
            default=st.session_state.jira_selected_projects,
            format_func=lambda key: f"{key} - {next((p['name'] for p in st.session_state.jira_available_projects if p['key'] == key), key)}",
            help="하나 이상의 프로젝트를 선택하세요."
        )

        st.session_state.jira_selected_projects = selected_keys

        col1, col2 = st.columns(2)

        with col1:
            if st.button("← 이전 단계", key="back_to_step2", use_container_width=True):
                st.session_state.jira_onboarding_step = 2
                st.rerun()

        with col2:
            if st.button("다음 단계", key="next_to_step4", type="primary", use_container_width=True, disabled=not selected_keys):
                if not selected_keys:
                    st.error("최소 하나의 프로젝트를 선택해주세요.")
                else:
                    # 프로젝트 저장
                    save_result = auth_client.save_jira_projects(selected_keys)

                    if save_result.get("success"):
                        st.session_state.jira_onboarding_step = 4
                        st.rerun()
                    else:
                        st.error(f"❌ 프로젝트 저장 실패: {save_result.get('message', '알 수 없는 오류')}")


def _render_step4_labels(auth_client: AuthClient):
    """Step 4: 레이블 입력 및 /jql 검증"""

    st.markdown("#### Step 4: 프로젝트별 레이블 설정")
    st.markdown("각 프로젝트에서 필터링할 레이블을 입력하세요.")

    if not st.session_state.jira_selected_projects:
        st.error("선택된 프로젝트가 없습니다.")
        if st.button("← 이전 단계로 돌아가기", key="back_to_step3_no_projects"):
            st.session_state.jira_onboarding_step = 3
            st.rerun()
        return

    # 각 프로젝트별 레이블 입력
    st.markdown("**선택된 프로젝트:**")
    for i, project_key in enumerate(st.session_state.jira_selected_projects):
        project_name = next(
            (p["name"] for p in st.session_state.jira_available_projects if p["key"] == project_key),
            project_key
        )

        with st.expander(f"📁 {project_key} - {project_name}", expanded=True):
            # 기존 레이블 가져오기
            current_labels = st.session_state.jira_labels_config.get(project_key, [])

            # 레이블 입력 (쉼표로 구분)
            labels_input = st.text_input(
                f"레이블 입력 (쉼표로 구분)",
                value=", ".join(current_labels) if current_labels else "",
                key=f"labels_input_{project_key}",
                placeholder="예: bug, enhancement, high-priority",
                help="레이블을 쉼표(,)로 구분하여 입력하세요. 레이블을 입력하지 않으면 모든 이슈를 가져옵니다."
            )

            # 검증 버튼
            if st.button(f"🔍 레이블 검증", key=f"validate_{project_key}", use_container_width=True):
                # 입력된 레이블 파싱
                labels = [label.strip() for label in labels_input.split(",") if label.strip()]

                with st.spinner(f"{project_key} 프로젝트의 레이블 검증 중..."):
                    # /jql API 호출
                    result = auth_client.validate_jira_labels(project_key, labels)

                    if result.get("success"):
                        issue_count = result.get("issue_count", 0)
                        if issue_count > 0:
                            st.success(f"✅ 검증 완료: {issue_count}개의 이슈를 찾았습니다.")
                            # 레이블 저장
                            st.session_state.jira_labels_config[project_key] = labels
                        else:
                            st.warning("⚠️ 조회된 이슈가 없습니다. 레이블을 확인해주세요.")
                            st.info(f"생성된 JQL 쿼리: {result.get('jql_query', 'N/A')}")
                    else:
                        st.error(f"❌ 검증 실패: {result.get('message', '알 수 없는 오류')}")

            # 현재 저장된 레이블 표시
            if project_key in st.session_state.jira_labels_config:
                saved_labels = st.session_state.jira_labels_config[project_key]
                if saved_labels:
                    st.info(f"✅ 검증된 레이블: {', '.join(saved_labels)}")
                else:
                    st.info("✅ 모든 이슈 가져오기 (레이블 필터 없음)")

    # 네비게이션 버튼
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← 이전 단계", key="back_to_step3", use_container_width=True):
            st.session_state.jira_onboarding_step = 3
            st.rerun()

    with col2:
        # 모든 프로젝트의 레이블이 검증되었는지 확인
        all_validated = all(
            project_key in st.session_state.jira_labels_config
            for project_key in st.session_state.jira_selected_projects
        )

        if st.button(
            "연동 완료",
            key="complete_onboarding",
            type="primary",
            use_container_width=True,
            disabled=not all_validated
        ):
            if not all_validated:
                st.error("모든 프로젝트의 레이블을 검증해주세요.")
            else:
                with st.spinner("Jira 레이블 설정 저장 중..."):
                    # 레이블 설정 저장
                    result = auth_client.save_jira_labels(st.session_state.jira_labels_config)

                    if result.get("success"):
                        st.success("🎉 Jira 연동이 완료되었습니다!")
                        # 세션 상태 초기화
                        st.session_state.jira_onboarding_step = 1
                        st.session_state.jira_endpoint = ""
                        st.session_state.jira_api_token = ""
                        st.session_state.jira_user_info = None
                        st.session_state.jira_available_projects = []
                        st.session_state.jira_selected_projects = []
                        st.session_state.jira_labels_config = {}
                        st.rerun()
                    else:
                        st.error(f"❌ 레이블 저장 실패: {result.get('message', '알 수 없는 오류')}")

    # 안내 메시지
    if not all_validated:
        st.warning("⚠️ 모든 프로젝트의 레이블을 검증한 후 '연동 완료' 버튼을 눌러주세요.")
