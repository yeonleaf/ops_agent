#!/usr/bin/env python3
"""
메일 리스트 UI 컴포넌트
티켓이 아닌 메일 리스트 형태로 표시
"""

import streamlit as st
from typing import List, Dict, Any
from datetime import datetime

def display_mail_list(mail_list: List[Dict[str, Any]], title: str = "메일 목록"):
    """
    메일을 리스트 형태로 표시
    
    Args:
        mail_list: 메일 목록
        title: 표시할 제목
    """
    if not mail_list:
        st.info("표시할 메일이 없습니다.")
        return
    
    st.subheader(f"📧 {title} ({len(mail_list)}개)")
    
    # 메일 목록을 카드 형태로 표시
    for i, mail in enumerate(mail_list):
        with st.container():
            # 메일 카드 스타일
            st.markdown("---")
            
            # 메일 헤더
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                # 제목과 발신자
                st.markdown(f"**{mail.get('subject', '제목 없음')}**")
                st.caption(f"👤 {mail.get('sender_name', mail.get('sender', '알 수 없음'))}")
            
            with col2:
                # 수신 시간
                received_date = mail.get('received_date', '')
                if received_date:
                    try:
                        if isinstance(received_date, str):
                            dt = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%m/%d %H:%M')
                        else:
                            formatted_date = received_date.strftime('%m/%d %H:%M')
                        st.caption(f"🕐 {formatted_date}")
                    except:
                        st.caption(f"🕐 {received_date}")
            
            with col3:
                # 우선순위 및 첨부파일
                priority = mail.get('priority', 'normal')
                priority_icon = {
                    'high': '🔴',
                    'normal': '🟡', 
                    'low': '🟢'
                }.get(priority.lower(), '🟡')
                
                st.markdown(f"{priority_icon} {priority}")
                
                if mail.get('has_attachments', False):
                    attachment_count = mail.get('attachment_count', 0)
                    st.markdown(f"📎 {attachment_count}")
            
            # 메일 본문 미리보기
            body_preview = mail.get('body_preview', '')
            if body_preview:
                with st.expander("📄 메일 내용 보기", expanded=False):
                    st.text(body_preview)
            
            # 메일 상태 정보
            status_cols = st.columns(4)
            
            with status_cols[0]:
                is_read = mail.get('is_read', False)
                read_status = "✅ 읽음" if is_read else "🔴 안읽음"
                st.caption(read_status)
            
            with status_cols[1]:
                if mail.get('has_attachments', False):
                    st.caption("📎 첨부파일 있음")
                else:
                    st.caption("📄 첨부파일 없음")
            
            with status_cols[2]:
                # 리스트 표시 이유
                reason = mail.get('reason_for_list', '')
                if reason:
                    st.caption(f"ℹ️ {reason}")
            
            with status_cols[3]:
                # 메일 ID (디버깅용)
                mail_id = mail.get('id', '')
                if mail_id:
                    st.caption(f"ID: {mail_id[:8]}...")
            
            # 메일 액션 버튼들
            action_cols = st.columns(4)
            
            with action_cols[0]:
                if st.button(f"📧 상세보기", key=f"detail_{i}"):
                    st.session_state.selected_mail = mail
                    st.rerun()
            
            with action_cols[1]:
                if st.button(f"📝 답장", key=f"reply_{i}"):
                    st.info("답장 기능은 아직 구현되지 않았습니다.")
            
            with action_cols[2]:
                if st.button(f"📁 이동", key=f"move_{i}"):
                    st.info("이동 기능은 아직 구현되지 않았습니다.")
            
            with action_cols[3]:
                if st.button(f"🗑️ 삭제", key=f"delete_{i}"):
                    st.info("삭제 기능은 아직 구현되지 않았습니다.")

def display_mail_detail(mail: Dict[str, Any]):
    """
    선택된 메일의 상세 정보를 표시
    
    Args:
        mail: 메일 데이터
    """
    if not mail:
        return
    
    st.subheader("📧 메일 상세 정보")
    
    # 메일 헤더 정보
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**제목**: {mail.get('subject', '제목 없음')}")
        st.markdown(f"**발신자**: {mail.get('sender_name', mail.get('sender', '알 수 없음'))}")
        st.markdown(f"**수신 시간**: {mail.get('received_date', '알 수 없음')}")
    
    with col2:
        priority = mail.get('priority', 'normal')
        priority_icon = {
            'high': '🔴',
            'normal': '🟡',
            'low': '🟢'
        }.get(priority.lower(), '🟡')
        
        st.markdown(f"**우선순위**: {priority_icon} {priority}")
        
        if mail.get('has_attachments', False):
            attachment_count = mail.get('attachment_count', 0)
            st.markdown(f"**첨부파일**: 📎 {attachment_count}개")
        
        is_read = mail.get('is_read', False)
        read_status = "✅ 읽음" if is_read else "🔴 안읽음"
        st.markdown(f"**상태**: {read_status}")
    
    st.markdown("---")
    
    # 메일 본문
    st.subheader("📄 메일 내용")
    body = mail.get('body', '내용이 없습니다.')
    st.text_area("본문", value=body, height=300, disabled=True)
    
    # 메타데이터
    st.markdown("---")
    st.subheader("🔍 메타데이터")
    
    meta_cols = st.columns(2)
    
    with meta_cols[0]:
        st.markdown(f"**메일 ID**: {mail.get('id', '알 수 없음')}")
        st.markdown(f"**발신자 이메일**: {mail.get('sender', '알 수 없음')}")
        st.markdown(f"**수신자**: {mail.get('recipients', '알 수 없음')}")
    
    with meta_cols[1]:
        st.markdown(f"**라벨**: {', '.join(mail.get('labels', [])) or '없음'}")
        st.markdown(f"**카테고리**: {', '.join(mail.get('categories', [])) or '없음'}")
        st.markdown(f"**리스트 표시 이유**: {mail.get('reason_for_list', '알 수 없음')}")
    
    # 액션 버튼들
    st.markdown("---")
    st.subheader("⚡ 액션")
    
    action_cols = st.columns(4)
    
    with action_cols[0]:
        if st.button("📧 답장하기"):
            st.info("답장 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[1]:
        if st.button("📁 폴더로 이동"):
            st.info("이동 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[2]:
        if st.button("🏷️ 라벨 추가"):
            st.info("라벨 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[3]:
        if st.button("🗑️ 삭제"):
            st.info("삭제 기능은 아직 구현되지 않았습니다.")
    
    # 뒤로 가기
    if st.button("← 목록으로 돌아가기"):
        st.session_state.selected_mail = None
        st.rerun()

def display_mail_summary(mail_list: List[Dict[str, Any]]):
    """
    메일 목록 요약 정보 표시
    
    Args:
        mail_list: 메일 목록
    """
    if not mail_list:
        return
    
    st.subheader("📊 메일 요약")
    
    # 기본 통계
    total_count = len(mail_list)
    unread_count = sum(1 for mail in mail_list if not mail.get('is_read', False))
    read_count = total_count - unread_count
    attachment_count = sum(1 for mail in mail_list if mail.get('has_attachments', False))
    
    # 우선순위별 통계
    priority_counts = {}
    for mail in mail_list:
        priority = mail.get('priority', 'normal').lower()
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    
    # 통계 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 메일", total_count)
    
    with col2:
        st.metric("안읽은 메일", unread_count)
    
    with col3:
        st.metric("읽은 메일", read_count)
    
    with col4:
        st.metric("첨부파일 있음", attachment_count)
    
    # 우선순위별 분포
    if priority_counts:
        st.markdown("**우선순위별 분포**")
        for priority, count in priority_counts.items():
            priority_icon = {
                'high': '🔴',
                'normal': '🟡',
                'low': '🟢'
            }.get(priority, '🟡')
            
            st.caption(f"{priority_icon} {priority}: {count}개")
    
    # 리스트 표시 이유 통계
    reason_counts = {}
    for mail in mail_list:
        reason = mail.get('reason_for_list', '알 수 없음')
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    if reason_counts:
        st.markdown("**리스트 표시 이유**")
        for reason, count in reason_counts.items():
            st.caption(f"• {reason}: {count}개")

def create_mail_list_with_sidebar(mail_list: List[Dict[str, Any]], title: str = "메일 목록"):
    """
    메일 리스트를 버튼 형태로 표시하고 사이드바에 상세 내용을 표시
    
    Args:
        mail_list: 메일 목록
        title: 표시할 제목
    """
    if not mail_list:
        st.info("표시할 메일이 없습니다.")
        return
    
    # 세션 상태 초기화
    if 'selected_mail_id' not in st.session_state:
        st.session_state.selected_mail_id = None
    if 'selected_mail_data' not in st.session_state:
        st.session_state.selected_mail_data = None
    
    st.subheader(f"📧 {title} ({len(mail_list)}개)")
    
    # 메일 버튼 리스트
    for mail in mail_list:
        # 상태 아이콘
        read_icon = "✅" if mail.get('is_read', False) else "🔴"
        priority_icon = {
            'high': '🔴',
            'normal': '🟡', 
            'low': '🟢'
        }.get(mail.get('priority', 'normal').lower(), '🟡')
        
        # 첨부파일 아이콘
        attachment_icon = "📎" if mail.get('has_attachments', False) else ""
        
        # 발신자와 날짜
        sender = mail.get('sender', '알 수 없음')
        received_date = mail.get('received_date', '')
        if received_date:
            try:
                if isinstance(received_date, str):
                    dt = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%m/%d')
                else:
                    date_str = received_date.strftime('%m/%d')
            except:
                date_str = received_date[:10] if len(received_date) > 10 else received_date
        else:
            date_str = ""
        
        # 버튼 텍스트 구성
        button_text = f"{read_icon} {priority_icon} {attachment_icon} {mail.get('subject', '제목 없음')}"
        button_caption = f"👤 {sender} • 🕐 {date_str}"
        
        # 버튼 생성
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                button_text, 
                key=f"mail_btn_{mail.get('id', '')}",
                help=button_caption,
                use_container_width=True
            ):
                st.session_state.selected_mail_id = mail.get('id')
                st.session_state.selected_mail_data = mail
                st.rerun()
        
        with col2:
            st.caption(button_caption)
    
    # 사이드바에 선택된 메일 상세 정보 표시
    if st.session_state.selected_mail_data:
        with st.sidebar:
            st.markdown("---")
            st.header("📧 메일 상세 정보")
            
            mail_data = st.session_state.selected_mail_data
            
            # 기본 정보
            st.subheader(mail_data.get('subject', '제목 없음'))
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**발신자:**")
                st.write(mail_data.get('sender', '알 수 없음'))
            
            with col2:
                received_date = mail_data.get('received_date', '')
                if received_date:
                    try:
                        if isinstance(received_date, str):
                            dt = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%Y년 %m월 %d일 %H:%M')
                        else:
                            formatted_date = received_date.strftime('%Y년 %m월 %d일 %H:%M')
                        st.write("**수신일:**")
                        st.write(formatted_date)
                    except:
                        st.write("**수신일:**")
                        st.write(received_date)
            
            # 상태 정보
            st.write("**상태:**")
            read_status = "읽음" if mail_data.get('is_read', False) else "안읽음"
            priority = mail_data.get('priority', 'normal')
            st.write(f"📖 {read_status} | 🎯 {priority}")
            
            if mail_data.get('has_attachments', False):
                attachment_count = mail_data.get('attachment_count', 0)
                st.write(f"📎 첨부파일 {attachment_count}개")
            
            # 메일 내용
            body = mail_data.get('body', '')
            if body:
                with st.expander("📄 메일 내용", expanded=True):
                    st.text(body)
            else:
                st.info("메일 내용을 불러올 수 없습니다.")
            
            # 액션 버튼
            if st.button("🗑️ 선택 해제", use_container_width=True):
                st.session_state.selected_mail_id = None
                st.session_state.selected_mail_data = None
                st.rerun()

def create_mail_list_ui(mail_list: List[Dict[str, Any]], title: str = "메일 목록"):
    """
    메일 리스트 UI를 생성하고 관리 (기존 카드 형태)
    
    Args:
        mail_list: 메일 목록
        title: 표시할 제목
    """
    # 세션 상태 초기화
    if 'selected_mail' not in st.session_state:
        st.session_state.selected_mail = None
    
    # 선택된 메일이 있으면 상세 보기
    if st.session_state.selected_mail:
        display_mail_detail(st.session_state.selected_mail)
        return
    
    # 메일 요약 정보
    display_mail_summary(mail_list)
    
    # 메일 목록
    display_mail_list(mail_list, title) 