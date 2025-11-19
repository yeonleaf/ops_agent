#!/usr/bin/env python3
"""
월간보고 V2 UI - 템플릿 기반 보고서 생성

ReportTemplate CRUD, 프롬프트 실행, 보고서 생성, 집계/분석 UI
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

from models.report_models import DatabaseManager, PromptTemplate, ReportTemplate, PromptExecution
from services.prompt_service import PromptService
from services.template_parser import TemplatePlaceholderParser
from services.execution_service import ExecutionService
from services.aggregation_service import AggregationService
from agent.monthly_report_agent import MonthlyReportAgent


def display_monthly_report_v2_tab(llm_client, user_id: int):
    """월간보고 V2 메인 탭"""

    st.title("📊 월간보고 자동화 V2")
    st.caption("템플릿 기반 보고서 생성 시스템")

    # 서브탭
    tabs = st.tabs([
        "📝 프롬프트 관리",
        "▶️ 프롬프트 실행",
        "📄 템플릿 관리",
        "🎨 보고서 생성",
        "📈 집계/분석"
    ])

    # DB 세션 초기화
    db_manager = DatabaseManager('reports.db')

    with tabs[0]:
        display_prompt_management(db_manager, user_id)

    with tabs[1]:
        display_prompt_execution(db_manager, llm_client, user_id)

    with tabs[2]:
        display_template_management(db_manager, user_id)

    with tabs[3]:
        display_report_generation(db_manager, llm_client, user_id)

    with tabs[4]:
        display_aggregation_dashboard(db_manager, user_id)


# ============================================================
# 1. 프롬프트 관리 UI
# ============================================================

def display_prompt_management(db_manager, user_id: int):
    """프롬프트 관리 UI"""
    st.header("📝 프롬프트 관리")

    session = db_manager.get_session()
    prompt_service = PromptService(session)

    try:
        # 프롬프트 목록 조회
        result = prompt_service.get_user_prompts(user_id, include_public=False)
        my_prompts = result.get('my_prompts', [])
        categories = result.get('categories', [])

        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader(f"내 프롬프트 ({len(my_prompts)}개)")

        with col2:
            if st.button("➕ 새 프롬프트", use_container_width=True):
                st.session_state['show_create_prompt_form'] = True

        # 새 프롬프트 생성 폼
        if st.session_state.get('show_create_prompt_form', False):
            with st.form("create_prompt_form"):
                st.subheader("새 프롬프트 만들기")

                title = st.text_input("제목 *", placeholder="예: BMT 현황")
                category = st.selectbox("카테고리", ["월간보고", "주간보고", "BMT", "PM", "기타"], index=0)
                description = st.text_area("설명", placeholder="프롬프트에 대한 간단한 설명")
                prompt_content = st.text_area(
                    "프롬프트 내용 *",
                    placeholder="예: NCMS_BMT 라벨이 붙은 이슈 중 이번 달에 완료된 작업을 표로 정리해주세요",
                    height=200
                )
                system = st.text_input("시스템", placeholder="예: NCMS, BTV")

                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 저장", use_container_width=True)
                with col2:
                    cancel = st.form_submit_button("❌ 취소", use_container_width=True)

                if cancel:
                    st.session_state['show_create_prompt_form'] = False
                    st.rerun()

                if submit:
                    if not title or not prompt_content:
                        st.error("제목과 프롬프트 내용은 필수입니다")
                    else:
                        try:
                            prompt_id = prompt_service.create_prompt(user_id, {
                                'title': title,
                                'category': category,
                                'description': description,
                                'prompt_content': prompt_content,
                                'system': system
                            })
                            st.success(f"✅ 프롬프트 '{title}' 생성 완료 (ID: {prompt_id})")
                            st.session_state['show_create_prompt_form'] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 생성 실패: {str(e)}")

        # 프롬프트 목록
        if my_prompts:
            for prompt in my_prompts:
                with st.expander(f"📌 {prompt['title']} (ID: {prompt['id']})"):
                    st.markdown(f"**카테고리:** {prompt['category']}")
                    if prompt.get('description'):
                        st.markdown(f"**설명:** {prompt['description']}")
                    if prompt.get('system'):
                        st.markdown(f"**시스템:** {prompt['system']}")

                    st.markdown("**프롬프트 내용:**")
                    st.code(prompt['prompt_content'], language="text")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✏️ 수정", key=f"edit_{prompt['id']}"):
                            st.session_state[f"editing_prompt_{prompt['id']}"] = True
                    with col2:
                        if st.button("🗑️ 삭제", key=f"delete_{prompt['id']}"):
                            try:
                                prompt_service.delete_prompt(user_id, prompt['id'])
                                st.success("삭제 완료")
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {str(e)}")
        else:
            st.info("프롬프트가 없습니다. 새 프롬프트를 만들어보세요!")

    finally:
        session.close()


# ============================================================
# 2. 프롬프트 실행 UI
# ============================================================

def display_prompt_execution(db_manager, llm_client, user_id: int):
    """프롬프트 실행 UI (with caching)"""
    st.header("▶️ 프롬프트 실행")

    session = db_manager.get_session()
    prompt_service = PromptService(session)

    try:
        # Agent 초기화
        import os
        from openai import AzureOpenAI

        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

        # AzureOpenAI 클라이언트 생성 (MonthlyReportAgent는 OpenAI SDK 클라이언트 필요)
        azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        agent = MonthlyReportAgent(
            azure_client=azure_client,
            user_id=user_id,
            deployment_name=deployment_name,
            db_path='tickets.db'
        )

        execution_service = ExecutionService(session, agent)

        # 프롬프트 선택
        result = prompt_service.get_user_prompts(user_id, include_public=False)
        my_prompts = result.get('my_prompts', [])

        if not my_prompts:
            st.warning("실행할 프롬프트가 없습니다. 먼저 프롬프트를 생성해주세요.")
            return

        prompt_options = {p['id']: f"{p['title']} (ID: {p['id']}) - {p['category']}" for p in my_prompts}

        selected_prompt_id = st.selectbox(
            "실행할 프롬프트 선택",
            options=list(prompt_options.keys()),
            format_func=lambda x: prompt_options[x]
        )

        # 선택된 프롬프트 정보 표시
        selected_prompt = next((p for p in my_prompts if p['id'] == selected_prompt_id), None)
        if selected_prompt:
            with st.expander("프롬프트 내용 보기"):
                st.code(selected_prompt['prompt_content'], language="text")

        # 컨텍스트 설정
        st.subheader("실행 컨텍스트")
        col1, col2 = st.columns(2)

        with col1:
            period = st.text_input("보고 기간", value=datetime.now().strftime('%Y-%m'), placeholder="2024-11")

        with col2:
            users = st.text_input("대상 유저 (콤마 구분)", placeholder="user1, user2")

        context = {
            'period': period if period else None,
            'users': [u.strip() for u in users.split(',')] if users else None
        }

        # 실행 버튼
        col1, col2 = st.columns([1, 3])

        with col1:
            execute_button = st.button("▶️ 실행", use_container_width=True, type="primary")

        if execute_button:
            with st.spinner("프롬프트 실행 중..."):
                result = execution_service.execute_prompt(
                    prompt_id=selected_prompt_id,
                    context=context,
                    save_to_cache=True
                )

                if result.get('success'):
                    st.success(f"✅ 실행 완료 (Execution ID: {result['execution_id']})")

                    # HTML 출력 표시
                    st.subheader("생성된 HTML")
                    st.components.v1.html(result['html_output'], height=400, scrolling=True)

                    # 메타데이터 표시
                    with st.expander("실행 정보"):
                        st.json(result['metadata'])

                    # Jira 이슈 표시
                    jira_issues = result.get('jira_issues', [])
                    if jira_issues:
                        with st.expander(f"조회된 Jira 이슈 ({len(jira_issues)}개)"):
                            st.json(jira_issues[:5])  # 최대 5개만 표시
                else:
                    st.error(f"❌ 실행 실패: {result.get('error')}")

        # 실행 이력
        st.divider()
        st.subheader("실행 이력")

        executions = execution_service.get_all_executions(selected_prompt_id)

        if executions:
            for exec_data in executions[:10]:  # 최근 10개만
                with st.expander(f"🕒 {exec_data['executed_at']} ({exec_data['jira_issue_count']}개 이슈)"):
                    st.json(exec_data)
        else:
            st.info("실행 이력이 없습니다")

    finally:
        session.close()


# ============================================================
# 3. 템플릿 관리 UI
# ============================================================

def display_template_management(db_manager, user_id: int):
    """ReportTemplate CRUD UI"""
    st.header("📄 보고서 템플릿 관리")

    session = db_manager.get_session()

    try:
        # 템플릿 목록 조회
        templates = session.query(ReportTemplate)\
            .filter_by(user_id=user_id)\
            .order_by(ReportTemplate.updated_at.desc())\
            .all()

        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader(f"내 템플릿 ({len(templates)}개)")

        with col2:
            if st.button("➕ 새 템플릿", use_container_width=True):
                st.session_state['show_create_template_form'] = True

        # 새 템플릿 생성 폼
        if st.session_state.get('show_create_template_form', False):
            with st.form("create_template_form"):
                st.subheader("새 템플릿 만들기")

                title = st.text_input("제목 *", placeholder="예: 2024년 11월 월간 보고서")
                description = st.text_area("설명", placeholder="템플릿에 대한 설명")

                st.markdown("**템플릿 내용** (Markdown + placeholder)")
                st.caption("프롬프트 삽입: `{{prompt:프롬프트ID}}`")

                template_content = st.text_area(
                    "템플릿",
                    value="""# 월간 보고서

## 주간 요약
{{prompt:1}}

## 주요 성과
{{prompt:2}}

## 다음 달 계획
{{prompt:3}}
""",
                    height=300
                )

                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 저장", use_container_width=True)
                with col2:
                    cancel = st.form_submit_button("❌ 취소", use_container_width=True)

                if cancel:
                    st.session_state['show_create_template_form'] = False
                    st.rerun()

                if submit:
                    if not title or not template_content:
                        st.error("제목과 템플릿 내용은 필수입니다")
                    else:
                        try:
                            template = ReportTemplate(
                                user_id=user_id,
                                title=title,
                                description=description,
                                template_content=template_content
                            )
                            session.add(template)
                            session.commit()
                            session.refresh(template)

                            st.success(f"✅ 템플릿 '{title}' 생성 완료 (ID: {template.id})")
                            st.session_state['show_create_template_form'] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 생성 실패: {str(e)}")

        # 템플릿 목록
        if templates:
            for template in templates:
                with st.expander(f"📄 {template.title} (ID: {template.id})"):
                    if template.description:
                        st.markdown(f"**설명:** {template.description}")

                    st.markdown(f"**생성일:** {template.created_at}")
                    st.markdown(f"**수정일:** {template.updated_at}")

                    st.markdown("**템플릿 내용:**")
                    st.code(template.template_content, language="markdown")

                    # Placeholder 검증
                    parser = TemplatePlaceholderParser(session)
                    validation = parser.validate_template(template.template_content, user_id)

                    if validation['valid']:
                        st.success(f"✅ 유효한 템플릿 (프롬프트: {len(validation['prompt_ids'])}개)")
                    else:
                        st.error("⚠️ 유효성 검사 실패:")
                        for error in validation['errors']:
                            st.error(f"  - {error}")

                    if validation['warnings']:
                        for warning in validation['warnings']:
                            st.warning(f"  - {warning}")

                    # 버튼
                    col1, col2 = st.columns(2)
                    with col1:
                        pass  # 수정 기능 (나중에 구현)
                    with col2:
                        if st.button("🗑️ 삭제", key=f"delete_template_{template.id}"):
                            session.delete(template)
                            session.commit()
                            st.success("삭제 완료")
                            st.rerun()
        else:
            st.info("템플릿이 없습니다. 새 템플릿을 만들어보세요!")

    finally:
        session.close()


# ============================================================
# 4. 보고서 생성 UI
# ============================================================

def display_report_generation(db_manager, llm_client, user_id: int):
    """템플릿 기반 보고서 생성 UI"""
    st.header("🎨 보고서 생성")

    session = db_manager.get_session()

    try:
        # 템플릿 선택
        templates = session.query(ReportTemplate)\
            .filter_by(user_id=user_id)\
            .order_by(ReportTemplate.updated_at.desc())\
            .all()

        if not templates:
            st.warning("생성할 템플릿이 없습니다. 먼저 템플릿을 만들어주세요.")
            return

        template_options = {t.id: f"{t.title} (ID: {t.id})" for t in templates}

        selected_template_id = st.selectbox(
            "템플릿 선택",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x]
        )

        selected_template = next((t for t in templates if t.id == selected_template_id), None)

        if selected_template:
            # 템플릿 미리보기
            with st.expander("템플릿 미리보기"):
                st.code(selected_template.template_content, language="markdown")

            # 보고서 생성 버튼
            if st.button("🎨 보고서 생성", use_container_width=True, type="primary"):
                with st.spinner("보고서 생성 중..."):
                    parser = TemplatePlaceholderParser(session)

                    # 템플릿 파싱 및 HTML 생성
                    result = parser.parse_template(selected_template.template_content)

                    if result['missing_executions']:
                        st.warning(f"⚠️ 일부 프롬프트의 실행 결과가 없습니다: {result['missing_executions']}")

                    # 최종 HTML (CSS 포함)
                    final_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{selected_template.title}</title>
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
        .component {{
            margin: 20px 0;
        }}
        .report-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .report-table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        .report-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        .missing-execution-warning {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="report-container">
        {result['html']}
    </div>
</body>
</html>
"""

                    st.success("✅ 보고서 생성 완료!")

                    # HTML 미리보기
                    st.subheader("미리보기")
                    st.components.v1.html(final_html, height=600, scrolling=True)

                    # 다운로드 버튼
                    st.download_button(
                        label="💾 HTML 다운로드",
                        data=final_html,
                        file_name=f"report_{selected_template.title}_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html",
                        use_container_width=True
                    )

    finally:
        session.close()


# ============================================================
# 5. 집계/분석 대시보드 UI
# ============================================================

def display_aggregation_dashboard(db_manager, user_id: int):
    """캐시 기반 집계/분석 대시보드"""
    st.header("📈 집계/분석 대시보드")

    session = db_manager.get_session()
    aggregation_service = AggregationService(session)

    try:
        # 날짜 범위 선택
        st.subheader("기간 설정")
        col1, col2 = st.columns(2)

        with col1:
            start_date = st.date_input("시작일", value=datetime.now() - timedelta(days=30))

        with col2:
            end_date = st.date_input("종료일", value=datetime.now())

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        if st.button("📊 집계 실행", use_container_width=True, type="primary"):
            with st.spinner("집계 중..."):
                # 기본 집계
                agg_result = aggregation_service.aggregate_by_date_range(
                    start_datetime,
                    end_datetime
                )

                # 완료율
                completion_result = aggregation_service.get_completion_rate(
                    start_datetime,
                    end_datetime
                )

                # 작업량 분포
                workload_result = aggregation_service.get_workload_distribution(
                    start_datetime,
                    end_datetime
                )

                # 결과 표시
                st.success("✅ 집계 완료!")

                # 메트릭 표시
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("총 이슈", agg_result['total_issues'])

                with col2:
                    st.metric("실행 횟수", agg_result['executions_count'])

                with col3:
                    st.metric("완료율", f"{completion_result['completion_rate']*100:.1f}%")

                with col4:
                    st.metric("담당자 수", workload_result['statistics']['total_assignees'])

                # 상세 정보
                tab1, tab2, tab3 = st.tabs(["상태별 분포", "담당자별 작업량", "원본 데이터"])

                with tab1:
                    st.subheader("상태별 이슈 분포")
                    st.bar_chart(agg_result['by_status'])

                    st.subheader("우선순위별 분포")
                    st.bar_chart(agg_result['by_priority'])

                with tab2:
                    st.subheader("담당자별 작업량")
                    for assignee, stats in workload_result['by_assignee'].items():
                        with st.expander(f"👤 {assignee} ({stats['total']}개)"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("완료", stats['done'])
                            with col2:
                                st.metric("진행 중", stats['in_progress'])
                            with col3:
                                st.metric("예정", stats['todo'])

                with tab3:
                    st.json(agg_result)

    finally:
        session.close()
