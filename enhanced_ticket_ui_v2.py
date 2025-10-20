#!/usr/bin/env python3
"""
Enhanced Ticket UI v2 - 개선된 티켓 관리 시스템
- 버튼 리스트 형태로 티켓 표시
- 상세 정보 표시 (제목, 원본 메일, description, 레이블)
- 레이블 편집 기능 (띄어쓰기로 구분, mem0에 반영)
"""

import streamlit as st
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import threading
import logging
from vector_db_models import VectorDBManager
from sqlite_ticket_models import SQLiteTicketManager, Ticket
from mem0_memory_adapter import create_mem0_memory, add_ticket_event
from module.logging_config import setup_logging

# 로깅 설정 초기화
setup_logging(level="INFO", log_file="logs/ticket_ui.log", console_output=True)
logger = logging.getLogger(__name__)

# ticket_ai_recommender는 lazy import로 처리
def get_ticket_ai_recommendation(*args, **kwargs):
    """AI 추천 기능 (lazy import)"""
    try:
        from ticket_ai_recommender import get_ticket_ai_recommendation as _get_recommendation
        return _get_recommendation(*args, **kwargs)
    except (ImportError, KeyError, Exception) as e:
        print(f"⚠️ ticket_ai_recommender 사용 불가: {e}")
        return {"recommendation": "AI 추천 기능을 사용할 수 없습니다.", "confidence": 0.0}

# 페이지 설정 (메인 앱에서만 사용)
# st.set_page_config(
#     page_title="Enhanced Ticket Management v2",
#     page_icon="🎫",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# 세션 상태 초기화
if 'selected_ticket' not in st.session_state:
    st.session_state.selected_ticket = None
if 'tickets' not in st.session_state:
    st.session_state.tickets = []

# mem0_memory 초기화
mem0_memory = None
try:
    import sys
    if hasattr(sys.modules['__main__'], 'mem0_memory'):
        mem0_memory = sys.modules['__main__'].mem0_memory
    else:
        # mem0_memory가 없으면 새로 생성
        mem0_memory = create_mem0_memory("ticket_ui")
        # 전역 변수로 설정하여 다른 모듈에서도 사용할 수 있도록 함
        sys.modules['__main__'].mem0_memory = mem0_memory
        print(f"✅ mem0_memory 초기화 완료: {mem0_memory}")
except Exception as e:
    print(f"❌ mem0_memory 초기화 실패: {e}")
    mem0_memory = None

def load_tickets_from_db() -> List[Ticket]:
    """데이터베이스에서 티켓을 로드합니다."""
    try:
        ticket_manager = SQLiteTicketManager()
        tickets = ticket_manager.get_all_tickets()
        return tickets
    except Exception as e:
        st.error(f"티켓 로드 중 오류: {str(e)}")
        return []

def update_ticket_status(ticket_id: int, new_status: str, old_status: str) -> bool:
    """티켓 상태를 업데이트합니다. (pending에서만 approved/rejected로 변경 가능)"""
    try:
        # 상태 변경 제한 검증
        if old_status in ["approved", "rejected"]:
            st.error(f"❌ '{old_status}' 상태의 티켓은 더 이상 상태를 변경할 수 없습니다.")
            return False
        
        if old_status != "pending" and new_status in ["approved", "rejected"]:
            st.error(f"❌ pending 상태가 아닌 티켓은 approved/rejected로 변경할 수 없습니다.")
            return False
        
        st.info(f"🔄 상태 변경 시도: 티켓 #{ticket_id}, '{old_status}' → '{new_status}'")
        # 터미널 보장 로그
        try:
            import sys
            print(f"[UI] 상태 변경 시도 -> ticket_id={ticket_id}, {old_status} → {new_status}")
            sys.stdout.flush()
        except Exception:
            pass
        ticket_manager = SQLiteTicketManager()
        success = ticket_manager.update_ticket_status(ticket_id, new_status, old_status)
        if success:
            st.info(f"📝 데이터베이스에서 티켓 #{ticket_id} 상태를 '{old_status}'에서 '{new_status}'로 변경했습니다.")
            try:
                import sys
                print(f"[UI] DB 업데이트 성공 -> ticket_id={ticket_id}, new_status={new_status}")
                sys.stdout.flush()
            except Exception:
                pass
            
            # pending -> approved 상태 변경 시 Jira 업로드
            if old_status.lower() == 'pending' and new_status.lower() == 'approved':
                logger.info(f"🚀 JIRA 업로드 시작: 티켓 #{ticket_id}")
                st.info(f"🚀 티켓 #{ticket_id}를 JIRA에 업로드 중입니다...")
                upload_to_jira_async(ticket_id)
        else:
            st.warning(f"⚠️ 데이터베이스 업데이트가 실패했습니다.")
        return success
    except Exception as e:
        st.error(f"상태 업데이트 중 오류: {str(e)}")
        import traceback
        st.error(f"상세 오류: {traceback.format_exc()}")
        return False

def record_status_change_to_mem0(ticket: Ticket, old_status: str, new_status: str):
    """상태 변경을 mem0에 기록합니다."""
    try:
        # 상태 변경 이벤트 생성
        status_change_event = f"티켓 #{ticket.ticket_id} 상태 변경: '{old_status}' → '{new_status}'"
        
        # mem0에 이벤트 기록
        # 터미널 보장 로그 (시작)
        try:
            import sys
            print(f"[UI] mem0 기록 시작 -> ticket_id={ticket.ticket_id}, event={old_status}->{new_status}")
            sys.stdout.flush()
        except Exception:
            pass

        mem = mem0_memory
        if not mem:
            try:
                from mem0_memory_adapter import create_mem0_memory
                mem = create_mem0_memory("ticket_ui")
                # 전역에도 반영
                import sys as _sys
                _sys.modules['__main__'].mem0_memory = mem
                print(f"[UI] mem0가 없어서 새로 생성했습니다: {mem}")
            except Exception as _e:
                print(f"[UI] mem0 생성 실패: {_e}")
                mem = None

        if mem:
            # 옵션 A: approve/reject를 별도 이벤트로 저장
            if new_status == "approved":
                _mid = add_ticket_event(
                    memory=mem,
                    event_type="ticket_approved",
                    description=status_change_event,
                    ticket_id=str(ticket.ticket_id),
                    message_id=ticket.original_message_id,
                    old_value=old_status,
                    new_value=new_status
                )
                try:
                    import sys
                    print(f"✅ mem0 저장 완료(approved): memory_id={_mid}")
                    sys.stdout.flush()
                except Exception:
                    pass
            elif new_status == "rejected":
                memory_id = add_ticket_event(
                    memory=mem,
                    event_type="ticket_rejected",
                    description=status_change_event,
                    ticket_id=str(ticket.ticket_id),
                    message_id=ticket.original_message_id,
                    old_value=old_status,
                    new_value=new_status
                )
                print(f"✅ 티켓 reject 이벤트가 mem0에 저장되었습니다: {memory_id}")
                logging.info(f"✅ 티켓 #{ticket.ticket_id} reject 이벤트가 mem0에 저장됨: {memory_id}")
            else:
                _mid = add_ticket_event(
                    memory=mem,
                    event_type="status_change",
                    description=status_change_event,
                    ticket_id=str(ticket.ticket_id),
                    message_id=ticket.original_message_id,
                    old_value=old_status,
                    new_value=new_status
                )
                try:
                    import sys
                    print(f"✅ mem0 저장 완료(status_change): memory_id={_mid}")
                    sys.stdout.flush()
                except Exception:
                    pass
        
        st.info(f"🧠 mem0에 상태 변경 이벤트를 기록했습니다: {status_change_event}")
        try:
            import sys
            print(f"[UI] mem0 기록 완료 -> ticket_id={ticket.ticket_id}, event={old_status}->{new_status}")
            sys.stdout.flush()
        except Exception:
            pass
        
    except Exception as e:
        st.error(f"mem0 기록 중 오류: {str(e)}")
        try:
            import sys, traceback as _tb
            print(f"[UI] mem0 기록 오류: {e}\n{_tb.format_exc()}")
            sys.stdout.flush()
        except Exception:
            pass

def display_ticket_button_list(tickets: List[Ticket]):
    """버튼 리스트 형태로 티켓 목록을 표시합니다."""
    if not tickets:
        st.info("등록된 티켓이 없습니다.")
        return
    
    st.subheader("📋 티켓 목록")
    
    # 상태별로 그룹화
    status_groups = {}
    for ticket in tickets:
        status = ticket.status
        if status not in status_groups:
            status_groups[status] = []
        status_groups[status].append(ticket)
    
    # 각 상태별로 티켓 표시
    for status, status_tickets in status_groups.items():
        with st.expander(f"📊 {status.upper()} ({len(status_tickets)}개)", expanded=True):
            for ticket in status_tickets:
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    # 티켓 기본 정보
                    st.write(f"**{ticket.title}**")
                    st.write(f"📅 {ticket.created_at[:10]} | 🏷️ {', '.join(ticket.labels) if ticket.labels else '레이블 없음'}")
                    if ticket.description and len(ticket.description) > 100:
                        st.write(f"📝 {ticket.description[:100]}...")
                    elif ticket.description:
                        st.write(f"📝 {ticket.description}")
                
                with col2:
                    # 상세보기 버튼
                    if st.button("상세보기", key=f"detail_{ticket.ticket_id}"):
                        logger.info(f"🔍 상세보기 버튼 클릭: 티켓 #{ticket.ticket_id}")
                        st.session_state.selected_ticket = ticket
                        logger.info(f"✅ 선택된 티켓 설정 완료: {ticket.ticket_id}")
                        st.rerun()
                
                with col3:
                    # 상태 표시
                    status_colors = {
                        'pending': '🟡',
                        'approved': '🟢', 
                        'rejected': '🔴'
                    }
                    status_icon = status_colors.get(status, '❓')
                    st.write(f"{status_icon} {status}")
                
                st.divider()

def display_ticket_detail(ticket: Ticket):
    """선택된 티켓의 상세 정보를 표시합니다."""
    logger.info(f"🎯 display_ticket_detail 함수 호출됨: 티켓 #{ticket.ticket_id if ticket else 'None'}")
    if not ticket:
        logger.warning("⚠️ 티켓이 None임")
        st.warning("표시할 티켓이 선택되지 않았습니다.")
        return

    logger.info(f"   - 제목: {ticket.title}")
    logger.info(f"   - 상태: {ticket.status}")
    logger.info(f"   - 생성일: {ticket.created_at}")
    
    st.subheader("🎫 티켓 상세 정보")
    
    # 기본 정보 섹션
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**ID:** {ticket.ticket_id}")
        st.write(f"**제목:** {ticket.title}")
        
        # 상태 변경 섹션
        st.write("**상태:**")
        current_status = ticket.status
        
        # 상태별 표시 및 변경 가능 여부 결정
        if current_status == "pending":
            # pending 상태: approved/rejected로만 변경 가능
            status_options = ["pending", "approved", "rejected"]
            current_index = 0  # pending이 기본값
            can_change = True
            help_text = "pending 상태에서 approved 또는 rejected로 변경할 수 있습니다."
            status_color = "🟡"
        elif current_status in ["approved", "rejected"]:
            # approved/rejected 상태: 변경 불가
            status_options = [current_status]  # 현재 상태만 표시
            current_index = 0
            can_change = False
            if current_status == "approved":
                help_text = "승인된 티켓은 더 이상 상태를 변경할 수 없습니다."
                status_color = "🟢"
            else:  # rejected
                help_text = "반려된 티켓은 더 이상 상태를 변경할 수 없습니다."
                status_color = "🔴"
        else:
            # 기타 상태
            status_options = [current_status]
            current_index = 0
            can_change = False
            help_text = "이 상태에서는 변경이 불가능합니다."
            status_color = "⚪"
        
        # 상태 표시 (색상 아이콘과 함께)
        st.write(f"{status_color} **{current_status.upper()}**")
        
        # 상태 변경 UI (변경 가능한 경우에만)
        if can_change:
            new_status = st.selectbox(
                "티켓 상태 변경",
                options=status_options,
                index=current_index,
                key=f"status_select_{ticket.ticket_id}",
                help=help_text
            )
            
            if new_status != current_status:
                if st.button("🔄 상태 변경", key=f"change_status_{ticket.ticket_id}", type="primary"):
                    success = update_ticket_status(ticket.ticket_id, new_status, current_status)
                    if success:
                        st.success(f"✅ 상태가 '{current_status}'에서 '{new_status}'로 변경되었습니다!")
                        # mem0에 상태 변경 이벤트 기록
                        record_status_change_to_mem0(ticket, current_status, new_status)
                        st.rerun()
                    else:
                        st.error("❌ 상태 변경에 실패했습니다.")
        else:
            # 변경 불가능한 경우 안내 메시지
            st.info(f"ℹ️ {help_text}")
            # 현재 상태만 표시하는 selectbox (비활성화)
            st.selectbox(
                "티켓 상태",
                options=status_options,
                index=current_index,
                key=f"status_display_{ticket.ticket_id}",
                disabled=True,
                help=help_text
            )
        
        st.write(f"**우선순위:** {ticket.priority}")
        st.write(f"**타입:** {ticket.ticket_type}")
    
    with col2:
        st.write(f"**생성일:** {ticket.created_at}")
        st.write(f"**수정일:** {ticket.updated_at}")
        st.write(f"**담당자:** {ticket.reporter}")
        st.write(f"**이메일:** {ticket.reporter_email}")
        
        # Jira 프로젝트 섹션
        st.write("**Jira 프로젝트:**")
        current_project = ticket.jira_project or ""
        
        # 프로젝트가 설정되지 않은 경우 LLM 추천
        if not current_project:
            with st.spinner("🤖 LLM이 적합한 프로젝트를 추천하는 중..."):
                recommended_project = recommend_jira_project_with_llm(ticket)
                st.info(f"💡 추천 프로젝트: {recommended_project}")
                
                if st.button("✅ 추천 프로젝트 적용", key=f"apply_recommended_project_{ticket.ticket_id}"):
                    success = update_ticket_jira_project(ticket.ticket_id, recommended_project, current_project)
                    if success:
                        st.success(f"✅ 프로젝트가 '{recommended_project}'로 설정되었습니다!")
                        st.rerun()
                        st.rerun()
                    else:
                        st.error("❌ 프로젝트 설정에 실패했습니다.")
        
        # 사용 가능한 프로젝트 목록 조회 (참고용)
        available_projects = []
        try:
            from jira_connector import JiraConnector
            with JiraConnector() as jira:
                projects = jira.jira.projects()
                available_projects = [p.key for p in projects]
        except Exception as e:
            available_projects = ["BPM"]  # 기본값

        # 프로젝트 변경 UI - text_input 사용
        if available_projects:
            help_text = f"사용 가능한 프로젝트: {', '.join(available_projects)}"
        else:
            help_text = "Jira 프로젝트 키를 직접 입력하세요 (예: BPM, PROJ, DEV)"

        new_project = st.text_input(
            "Jira 프로젝트 변경",
            value=current_project,
            key=f"project_input_{ticket.ticket_id}",
            help=help_text,
            placeholder="프로젝트 키를 입력하세요 (예: BPM)"
        )
        
        if new_project.strip() != current_project.strip() and new_project.strip():
            if st.button("🔄 프로젝트 변경", key=f"change_project_{ticket.ticket_id}", type="secondary"):
                success = update_ticket_jira_project(ticket.ticket_id, new_project.strip(), current_project)
                if success:
                    st.success(f"✅ 프로젝트가 '{current_project or '미설정'}'에서 '{new_project}'로 변경되었습니다!")
                    st.rerun()
                    st.rerun()
                else:
                    st.error("❌ 프로젝트 변경에 실패했습니다.")
        
        # 시작일 표시
        if ticket.start_date:
            st.write(f"**시작일:** {ticket.start_date}")
        else:
            st.write("**시작일:** 미설정")
    
    # 설명 섹션
    st.subheader("📝 설명")
    
    # 설명 편집 기능
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if ticket.description:
            edited_description = st.text_area(
                "설명 편집:",
                value=ticket.description,
                height=150,
                key=f"description_edit_{ticket.ticket_id}"
            )
        else:
            edited_description = st.text_area(
                "설명 편집:",
                placeholder="설명을 입력하세요...",
                height=150,
                key=f"description_edit_{ticket.ticket_id}"
            )
    
    with col2:
        st.write("")  # 공간 확보
        st.write("")  # 공간 확보
        if st.button("💾 저장", key=f"save_description_{ticket.ticket_id}"):
            if edited_description != ticket.description:
                # description 업데이트
                old_description = ticket.description or ""
                success = update_ticket_description(ticket.ticket_id, edited_description, old_description)
                
                if success:
                    # mem0에 변경사항 기록
                    record_description_change_to_mem0(ticket, old_description, edited_description)
                    
                    # 티켓 객체 업데이트
                    ticket.description = edited_description
                    
                    st.success("✅ 설명이 업데이트되었습니다!")
                    logger.info(f"✅ 티켓 {ticket.ticket_id} description 업데이트 완료")
                    st.rerun()
                else:
                    st.error("❌ 설명 업데이트에 실패했습니다.")
            else:
                st.info("ℹ️ 변경사항이 없습니다.")
    
    # AI 추천 섹션
    st.subheader("🤖 AI 추천")
    
    if st.button("AI 추천 생성", type="primary", key="ai_recommend_button"):
        try:
            with st.spinner("🤖 AI 추천을 생성하고 있습니다..."):
                logger.info("🤖 AI 추천 생성 시작")
                # AI 추천 생성
                from ticket_ai_recommender import get_ticket_ai_recommendation
                
                # 메일 내용 가져오기
                mail_content = ""
                message_id = ticket.original_message_id
                if message_id:
                    try:
                        vector_db = VectorDBManager()
                        mail = vector_db.get_mail_by_id(message_id)
                        if mail:
                            mail_content = mail.original_content or mail.refined_content or ""
                    except Exception as e:
                        st.warning(f"메일 내용 조회 실패: {str(e)}")
                
                # 티켓 히스토리 (간단한 형태)
                ticket_history = f"티켓 ID: {ticket.ticket_id}, 상태: {ticket.status}, 우선순위: {ticket.priority}, 제목: {ticket.title}"
                
                # AI 추천 생성
                logger.info(f"🤖 AI 추천 호출 - description: {len(ticket.description or '')} chars, mail_content: {len(mail_content)} chars")
                recommendation_result = get_ticket_ai_recommendation(
                    ticket_description=ticket.description or "",
                    mail_content=mail_content,
                    ticket_history=ticket_history
                )
                logger.info(f"🤖 AI 추천 결과: {recommendation_result}")
                
                if recommendation_result and "recommendation" in recommendation_result:
                    st.success("✅ AI 추천이 생성되었습니다!")
                    st.markdown("---")
                    st.subheader("🤖 AI 추천 해결방법")
                    st.markdown(recommendation_result["recommendation"])
                    
                    # 신뢰도 표시 (있는 경우)
                    if "confidence" in recommendation_result:
                        confidence = recommendation_result["confidence"]
                        st.info(f"📊 신뢰도: {confidence:.2f}")
                else:
                    st.error("❌ AI 추천 생성에 실패했습니다.")
                
        except Exception as e:
            logger.error(f"❌ AI 추천 생성 중 오류: {str(e)}")
            st.error(f"AI 추천 생성 중 오류가 발생했습니다: {str(e)}")
            st.info("💡 Azure OpenAI 설정을 확인해주세요.")
            import traceback
            st.code(traceback.format_exc())
    
    # 레이블 관리 섹션
    st.subheader("🏷️ 레이블 관리")
    
    # 현재 레이블 표시
    current_labels = ticket.labels if ticket.labels else []
    if current_labels:
        st.write("**현재 레이블:**")
        for i, label in enumerate(current_labels):
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("❌", key=f"delete_label_{ticket.ticket_id}_{i}"):
                    delete_label_from_ticket(ticket.ticket_id, label)
                    st.rerun()
                    st.rerun()
            with col2:
                st.write(f"• {label}")
    else:
        st.write("**현재 레이블:** 없음")
    
    # 레이블 편집
    st.write("**레이블 편집:**")
    st.write("💡 레이블을 띄어쓰기로 구분하여 입력하세요. 예: 버그 긴급 서버오류")
    
    new_labels_text = st.text_input(
        "새 레이블 입력:",
        value=" ".join(current_labels) if current_labels else "",
        key=f"label_input_{ticket.ticket_id}",
        help="띄어쓰기로 구분하여 여러 레이블을 입력할 수 있습니다."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("레이블 저장", key=f"save_labels_{ticket.ticket_id}"):
            # 띄어쓰기로 구분하여 레이블 리스트 생성
            new_labels = [label.strip() for label in new_labels_text.split() if label.strip()]
            
            # 기존 레이블과 비교하여 변경사항 확인
            old_labels = current_labels.copy()
            
            if new_labels != old_labels:
                success = update_ticket_labels(ticket.ticket_id, new_labels, old_labels)
                if success:
                    st.success("✅ 레이블이 업데이트되었습니다!")
                    # mem0에 레이블 변경 이벤트 기록
                    record_label_change_to_mem0(ticket, old_labels, new_labels)
                    st.rerun()
                    st.rerun()
                else:
                    st.error("❌ 레이블 업데이트에 실패했습니다.")
            else:
                st.info("변경사항이 없습니다.")
    
    with col2:
        if st.button("취소", key=f"cancel_labels_{ticket.ticket_id}"):
            st.rerun()
            st.rerun()
    
    # 원본 메일 섹션 제거됨 - 정제된 내용만 필요
    
    # 뒤로가기 버튼
    if st.button("← 목록으로 돌아가기", key=f"back_{ticket.ticket_id}"):
        logger.info("🔙 뒤로가기 버튼 클릭")
        st.session_state.selected_ticket = None
        logger.info("✅ 선택된 티켓 초기화 완료")
        st.rerun()

def update_ticket_labels(ticket_id: int, new_labels: List[str], old_labels: List[str]) -> bool:
    """티켓 레이블을 업데이트합니다."""
    try:
        ticket_manager = SQLiteTicketManager()
        success = ticket_manager.update_ticket_labels(ticket_id, new_labels, old_labels)
        return success
    except Exception as e:
        st.error(f"레이블 업데이트 중 오류: {str(e)}")
        return False

def delete_label_from_ticket(ticket_id: int, label: str):
    """티켓에서 특정 레이블을 삭제합니다."""
    try:
        ticket_manager = SQLiteTicketManager()
        current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
        
        if current_ticket and current_ticket.labels:
            old_labels = current_ticket.labels.copy()
            if label in old_labels:
                old_labels.remove(label)
                success = ticket_manager.update_ticket_labels(ticket_id, old_labels, current_ticket.labels)
                if success:
                    st.success(f"✅ 레이블 '{label}'이 삭제되었습니다!")
                    # mem0에 레이블 삭제 이벤트 기록
                    record_label_change_to_mem0(current_ticket, current_ticket.labels, old_labels)
                    st.rerun()
                    st.rerun()
                else:
                    st.error("❌ 레이블 삭제에 실패했습니다.")
            else:
                st.warning(f"레이블 '{label}'을 찾을 수 없습니다.")
        else:
            st.warning("티켓을 찾을 수 없거나 레이블이 없습니다.")
    except Exception as e:
        st.error(f"레이블 삭제 중 오류: {str(e)}")

def update_ticket_description(ticket_id: int, new_description: str, old_description: str) -> bool:
    """티켓 description을 업데이트합니다."""
    try:
        ticket_manager = SQLiteTicketManager()
        success = ticket_manager.update_ticket_description(ticket_id, new_description, old_description)
        return success
    except Exception as e:
        st.error(f"Description 업데이트 중 오류: {str(e)}")
        return False

def record_description_change_to_mem0(ticket: Ticket, old_description: str, new_description: str):
    """Description 변경을 mem0에 기록합니다."""
    try:
        mem0_memory = mem0_memory
        if not mem0_memory:
            return
            
        event_description = f"사용자가 티켓 #{ticket.ticket_id} '{ticket.title}'의 설명을 수정함"
        add_ticket_event(
            memory=mem0_memory,
            event_type="description_updated",
            description=event_description,
            ticket_id=str(ticket.ticket_id),
            message_id=ticket.original_message_id,
            old_value=old_description[:200] + "..." if len(old_description) > 200 else old_description,
            new_value=new_description[:200] + "..." if len(new_description) > 200 else new_description,
            user_id="ui_user"
        )
        
        print(f"✅ Description 변경사항이 mem0에 기록되었습니다: ticket_id={ticket.ticket_id}")
        
    except Exception as e:
        print(f"⚠️ mem0 Description 변경 기록 실패: {str(e)}")

def record_label_change_to_mem0(ticket: Ticket, old_labels: List[str], new_labels: List[str]):
    """레이블 변경을 mem0에 기록합니다."""
    try:
        mem0_memory = mem0_memory
        if not mem0_memory:
            return
            
        # 변경사항 분석
        added_labels = [label for label in new_labels if label not in old_labels]
        removed_labels = [label for label in old_labels if label not in new_labels]
        
        # 추가된 레이블 기록
        for label in added_labels:
            event_description = f"사용자가 티켓 #{ticket.ticket_id} '{ticket.title}'에 레이블 '{label}'을 추가함"
            add_ticket_event(
                memory=mem0_memory,
                event_type="label_added",
                description=event_description,
                ticket_id=str(ticket.ticket_id),
                message_id=ticket.original_message_id,
                old_value="",
                new_value=label,
                user_id="ui_user"
            )
        
        # 삭제된 레이블 기록
        for label in removed_labels:
            event_description = f"사용자가 티켓 #{ticket.ticket_id} '{ticket.title}'에서 레이블 '{label}'을 삭제함"
            add_ticket_event(
                memory=mem0_memory,
                event_type="label_deleted",
                description=event_description,
                ticket_id=str(ticket.ticket_id),
                message_id=ticket.original_message_id,
                old_value=label,
                new_value="",
                user_id="ui_user"
            )
        
        print(f"✅ 레이블 변경사항이 mem0에 기록되었습니다: 추가={added_labels}, 삭제={removed_labels}")
        
    except Exception as e:
        print(f"⚠️ mem0 레이블 변경 기록 실패: {str(e)}")

def upload_to_jira_async(ticket_id: int):
    """백그라운드에서 비동기적으로 Jira에 티켓 업로드"""
    def _upload_worker():
        try:
            logger.info(f"🎫 JIRA 업로드 워커 시작: 티켓 #{ticket_id}")
            print(f"🎫 JIRA 업로드 워커 시작: 티켓 #{ticket_id}")
            
            # 티켓 정보 조회
            ticket_manager = SQLiteTicketManager()
            ticket = ticket_manager.get_ticket_by_id(ticket_id)
            
            if not ticket:
                logger.error(f"❌ 티켓 ID {ticket_id}를 찾을 수 없습니다.")
                print(f"❌ 티켓 ID {ticket_id}를 찾을 수 없습니다.")
                return
                
            # Jira 연동 상태 확인 (.env 파일에서 직접 읽기)
            import os
            from dotenv import load_dotenv
            
            # .env 파일 로드
            load_dotenv()
            
            jira_endpoint = os.getenv("JIRA_ENDPOINT")
            jira_token = os.getenv("JIRA_TOKEN")
            jira_account = os.getenv("JIRA_ACCOUNT")
            
            logger.info(f"🔗 JIRA 설정 확인 중...")
            if not all([jira_endpoint, jira_token, jira_account]):
                logger.error(f"❌ JIRA 설정이 .env 파일에 없습니다. JIRA_ENDPOINT, JIRA_TOKEN, JIRA_ACCOUNT를 확인해주세요.")
                print(f"❌ JIRA 설정이 .env 파일에 없습니다. JIRA_ENDPOINT, JIRA_TOKEN, JIRA_ACCOUNT를 확인해주세요.")
                return
            
            logger.info(f"✅ JIRA 설정 확인 완료: {jira_endpoint}")
            print(f"✅ JIRA 설정 확인 완료: {jira_endpoint}")
            
            logger.info(f"🎫 티켓 #{ticket_id} Jira 업로드 시작...")
            print(f"🎫 티켓 #{ticket_id} Jira 업로드 시작...")
            
            # Jira 커넥터 초기화 (.env 파일에서 자동으로 설정 읽음)
            logger.info(f"🔧 JIRA 커넥터 초기화 중...")
            from jira_connector import JiraConnector
            
            # JiraConnector는 .env 파일에서 자동으로 설정을 읽습니다
            with JiraConnector() as jira:
                # 티켓 데이터 준비
                ticket_data = {
                    'summary': f"[OPS-AGENT] {ticket.title or 'Unknown Title'}",
                    'description': f"""
원본 메일 제목: {ticket.title or 'Unknown'}
받은 사람: {ticket.recipient or 'Unknown'}
보낸 사람: {ticket.sender or 'Unknown'}

상세 내용:
{ticket.description or 'No description available'}

Labels: {', '.join(ticket.labels) if ticket.labels else 'None'}
시작일: {ticket.start_date or 'Not set'}
생성 시간: {ticket.created_at}
승인 시간: {datetime.now().isoformat()}
""",
                    'priority': 'Medium',  # 기본 우선순위
                    'start_date': ticket.start_date  # 시작일 필드 추가
                }
                
                # 프로젝트 키 결정
                project_key = ticket.jira_project or "BPM"  # 기본값
                
                # Jira에 이슈 생성
                result = jira.create_jira_issue(ticket_data, project_key)
                
                if result.get('success'):
                    print(f"✅ 티켓 #{ticket_id} Jira 업로드 성공: {result.get('issue_key')}")
                    print(f"🔗 Jira URL: {result.get('issue_url')}")
                    
                    # 성공 메시지를 Streamlit에 표시 (가능한 경우)
                    try:
                        st.success(f"✅ 티켓 #{ticket_id}이(가) Jira에 업로드되었습니다!")
                        st.info(f"🔗 Jira 이슈: [{result.get('issue_key')}]({result.get('issue_url')})")
                    except:
                        pass  # Streamlit 컨텍스트가 없는 경우 무시
                        
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"❌ 티켓 #{ticket_id} Jira 업로드 실패: {error_msg}")
                    
                    # 실패 메시지를 Streamlit에 표시 (가능한 경우)
                    try:
                        st.error(f"❌ 티켓 #{ticket_id} Jira 업로드 실패: {error_msg}")
                    except:
                        pass  # Streamlit 컨텍스트가 없는 경우 무시
                        
        except Exception as e:
            print(f"❌ Jira 업로드 중 오류 발생: {str(e)}")
            try:
                st.error(f"❌ Jira 업로드 중 오류 발생: {str(e)}")
            except:
                pass  # Streamlit 컨텍스트가 없는 경우 무시
    
    # 백그라운드 스레드에서 실행
    logger.info(f"🧵 JIRA 업로드 스레드 시작: 티켓 #{ticket_id}")
    thread = threading.Thread(target=_upload_worker, daemon=True)
    thread.start()
    logger.info(f"✅ JIRA 업로드 스레드 시작 완료: 티켓 #{ticket_id}")
    
    # 사용자에게 즉시 알림 표시
    st.info(f"🚀 티켓 #{ticket_id} Jira 업로드를 시작합니다... (백그라운드 처리)")

def recommend_jira_project_with_llm(ticket: Ticket) -> str:
    """LLM과 mem0를 사용해 티켓에 적합한 Jira 프로젝트를 추천"""
    try:
        # 사용 가능한 Jira 프로젝트 목록 조회
        from jira_connector import JiraConnector
        
        available_projects = []
        try:
            with JiraConnector() as jira:
                projects = jira.jira.projects()
                available_projects = [{"key": p.key, "name": p.name} for p in projects]
        except Exception as e:
            print(f"⚠️ Jira 프로젝트 목록 조회 실패: {e}")
            return "BPM"  # 기본값
        
        if not available_projects:
            return "BPM"  # 기본값
        
        # mem0에서 관련 기록 검색
        mem0_context = ""
        if False:  # mem0 memory disabled
            try:
                # 티켓 관련 기록 검색
                search_query = f"티켓 {ticket.title} {ticket.description[:100]} 프로젝트"
                related_memories = mem0_memory.search(search_query, limit=5)
                
                if related_memories:
                    mem0_context = "\n".join([
                        f"- {memory.get('memory', '')}" 
                        for memory in related_memories
                    ])
            except Exception as e:
                print(f"⚠️ mem0 검색 실패: {e}")
        
        # LLM 프롬프트 구성
        prompt = f"""다음 티켓에 가장 적합한 Jira 프로젝트를 추천해주세요.

티켓 정보:
- 제목: {ticket.title}
- 설명: {ticket.description[:500]}
- 라벨: {', '.join(ticket.labels) if ticket.labels else 'None'}
- 티켓 타입: {ticket.ticket_type}
- 우선순위: {ticket.priority}

사용 가능한 Jira 프로젝트:
{chr(10).join([f"- {p['key']}: {p['name']}" for p in available_projects])}

관련 기록 (mem0):
{mem0_context if mem0_context else '관련 기록 없음'}

지침:
1. 티켓의 내용과 성격을 분석하여 가장 적합한 프로젝트를 선택하세요
2. 과거 기록이 있다면 참고하세요
3. 프로젝트 키만 반환하세요 (예: BPM, PROJ 등)
4. 확실하지 않다면 BPM을 기본값으로 사용하세요

추천 프로젝트 키:"""

        # Azure OpenAI API 호출
        try:
            import os
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
            
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
                messages=[
                    {"role": "system", "content": "당신은 Jira 프로젝트 관리 전문가입니다. 티켓의 내용을 분석하여 적합한 프로젝트를 추천합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            recommended_project = response.choices[0].message.content.strip()
            
            # 추천된 프로젝트가 사용 가능한 목록에 있는지 확인
            project_keys = [p['key'] for p in available_projects]
            if recommended_project in project_keys:
                print(f"🤖 LLM이 추천한 프로젝트: {recommended_project}")
                return recommended_project
            else:
                print(f"⚠️ LLM이 추천한 프로젝트 '{recommended_project}'가 사용 가능한 목록에 없음. 기본값 사용.")
                return project_keys[0] if project_keys else "BPM"
                
        except Exception as e:
            print(f"⚠️ LLM 프로젝트 추천 실패: {e}")
            return available_projects[0]['key'] if available_projects else "BPM"
            
    except Exception as e:
        print(f"❌ 프로젝트 추천 중 오류: {e}")
        return "BPM"  # 기본값

def update_ticket_jira_project(ticket_id: int, new_project: str, old_project: str) -> bool:
    """티켓의 Jira 프로젝트를 업데이트하고 mem0에 기록"""
    try:
        # 데이터베이스 업데이트
        with sqlite3.connect("tickets.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tickets 
                SET jira_project = ?, updated_at = ?
                WHERE ticket_id = ?
            """, (new_project, datetime.now().isoformat(), ticket_id))
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ 티켓 #{ticket_id} Jira 프로젝트 변경: {old_project} → {new_project}")
                
                # mem0에 변경사항 기록
                if False:  # mem0 memory disabled
                    try:
                        add_ticket_event(
                            memory=mem0_memory,
                            event_type="jira_project_change",
                            description=f"티켓 #{ticket_id} Jira 프로젝트 변경: '{old_project}' → '{new_project}'",
                            ticket_id=str(ticket_id),
                            message_id="",
                            old_value=old_project or "",
                            new_value=new_project
                        )
                        print(f"🧠 mem0에 프로젝트 변경 이벤트 기록 완료")
                    except Exception as e:
                        print(f"⚠️ mem0 기록 실패: {e}")
                
                return True
            else:
                return False
                
    except Exception as e:
        print(f"❌ 프로젝트 업데이트 실패: {e}")
        return False

def recommend_jira_project_with_llm_standalone(ticket: Ticket) -> str:
    """Streamlit 없이 동작하는 LLM 기반 프로젝트 추천 (티켓 생성 시 사용)"""
    try:
        # 사용 가능한 Jira 프로젝트 목록 조회
        from jira_connector import JiraConnector
        
        available_projects = []
        try:
            with JiraConnector() as jira:
                projects = jira.jira.projects()
                available_projects = [{"key": p.key, "name": p.name} for p in projects]
        except Exception as e:
            print(f"⚠️ Jira 프로젝트 목록 조회 실패: {e}")
            return "BPM"  # 기본값
        
        if not available_projects:
            return "BPM"  # 기본값
        
        # mem0에서 관련 기록 검색 (Streamlit 없이)
        mem0_context = ""
        try:
            from mem0_memory_adapter import create_mem0_memory
            mem0_memory = create_mem0_memory("ticket_ui")
            
            # 티켓 관련 기록 검색
            search_query = f"티켓 {ticket.title} {ticket.description[:100]} 프로젝트"
            related_memories = mem0_memory.search(search_query, limit=5)
            
            if related_memories:
                mem0_context = "\n".join([
                    f"- {memory.get('memory', '')}" 
                    for memory in related_memories
                ])
        except Exception as e:
            print(f"⚠️ mem0 검색 실패: {e}")
        
        # LLM 프롬프트 구성
        prompt = f"""다음 티켓에 가장 적합한 Jira 프로젝트를 추천해주세요.

티켓 정보:
- 제목: {ticket.title}
- 설명: {ticket.description[:500]}
- 라벨: {', '.join(ticket.labels) if ticket.labels else 'None'}
- 티켓 타입: {ticket.ticket_type}
- 우선순위: {ticket.priority}

사용 가능한 Jira 프로젝트:
{chr(10).join([f"- {p['key']}: {p['name']}" for p in available_projects])}

관련 기록 (mem0):
{mem0_context if mem0_context else '관련 기록 없음'}

지침:
1. 티켓의 내용과 성격을 분석하여 가장 적합한 프로젝트를 선택하세요
2. 과거 기록이 있다면 참고하세요
3. 프로젝트 키만 반환하세요 (예: BPM, PROJ 등)
4. 확실하지 않다면 BPM을 기본값으로 사용하세요

추천 프로젝트 키:"""

        # Azure OpenAI API 호출
        try:
            import os
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
            
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
                messages=[
                    {"role": "system", "content": "당신은 Jira 프로젝트 관리 전문가입니다. 티켓의 내용을 분석하여 적합한 프로젝트를 추천합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            recommended_project = response.choices[0].message.content.strip()
            
            # 추천된 프로젝트가 사용 가능한 목록에 있는지 확인
            project_keys = [p['key'] for p in available_projects]
            if recommended_project in project_keys:
                print(f"🤖 LLM이 추천한 프로젝트: {recommended_project}")
                return recommended_project
            else:
                print(f"⚠️ LLM이 추천한 프로젝트 '{recommended_project}'가 사용 가능한 목록에 없음. 기본값 사용.")
                return project_keys[0] if project_keys else "BPM"
                
        except Exception as e:
            print(f"⚠️ LLM 프로젝트 추천 실패: {e}")
            return available_projects[0]['key'] if available_projects else "BPM"
            
    except Exception as e:
        print(f"❌ 프로젝트 추천 중 오류: {e}")
        return "BPM"  # 기본값

def main():
    st.title("🎫 Enhanced Ticket Management System v2")

    # 메인 컨텐츠
    logger.info(f"🔍 메인 화면 진입 - 선택된 티켓: {st.session_state.selected_ticket}")
    if st.session_state.selected_ticket:
        logger.info(f"📄 상세보기 표시: 티켓 #{st.session_state.selected_ticket.ticket_id}")
        display_ticket_detail(st.session_state.selected_ticket)
    else:
        # 티켓 목록 표시
        tickets = load_tickets_from_db()
        display_ticket_button_list(tickets)

# 메인 앱에서 import할 때는 실행하지 않음
# if __name__ == "__main__":
#     main()
