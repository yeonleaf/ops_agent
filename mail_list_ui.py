#!/usr/bin/env python3
"""
Mail List UI - Streamlit 기반 메일 관리 시스템
st.rerun() 대신 session state를 활용한 상태 관리로 개선
"""

import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

# 페이지 설정
st.set_page_config(
    page_title="Mail Management System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'mails' not in st.session_state:
    st.session_state.mails = []
if 'selected_mail' not in st.session_state:
    st.session_state.selected_mail = None
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'list'

def load_sample_mails():
    """샘플 메일 데이터를 로드합니다."""
    sample_mails = [
        {
            'id': 'msg_001',
            'subject': '서버 장애 보고',
            'sender': 'admin@company.com',
            'sender_name': '시스템 관리자',
            'received_date': '2024-01-15 14:30:00',
            'body': '프로덕션 서버에서 장애가 발생했습니다. 긴급 조치가 필요합니다.',
            'priority': 'high',
            'has_attachments': True,
            'attachment_count': 2,
            'is_read': False,
            'labels': ['urgent', 'server'],
            'categories': ['technical'],
            'reason_for_list': '높은 우선순위'
        },
        {
            'id': 'msg_002',
            'subject': '월간 보고서',
            'sender': 'reports@company.com',
            'sender_name': '보고서 시스템',
            'received_date': '2024-01-15 10:00:00',
            'body': '1월 월간 시스템 운영 보고서가 준비되었습니다.',
            'priority': 'normal',
            'has_attachments': True,
            'attachment_count': 1,
            'is_read': True,
            'labels': ['report', 'monthly'],
            'categories': ['business'],
            'reason_for_list': '정기 보고서'
        },
        {
            'id': 'msg_003',
            'subject': '사용자 문의',
            'sender': 'user@company.com',
            'sender_name': '김철수',
            'received_date': '2024-01-15 09:15:00',
            'body': '로그인 시스템에 문제가 있습니다. 확인 부탁드립니다.',
            'priority': 'medium',
            'has_attachments': False,
            'attachment_count': 0,
            'is_read': False,
            'labels': ['user-query', 'login'],
            'categories': ['support'],
            'reason_for_list': '사용자 문의'
        }
    ]
    return sample_mails

def display_mail_list(mails: List[Dict[str, Any]]):
    """
    메일 목록을 표시
    
    Args:
        mails: 메일 데이터 리스트
    """
    if not mails:
        st.info("표시할 메일이 없습니다.")
        return
    
    # 뷰 모드 선택
    col1, col2 = st.columns([3, 1])
    with col2:
        view_mode = st.selectbox(
            "보기 모드",
            ['list', 'grid'],
            index=0 if st.session_state.view_mode == 'list' else 1,
            key="view_mode_selector"
        )
        st.session_state.view_mode = view_mode
    
    if view_mode == 'list':
        st.subheader("📧 메일 목록")
        
        for i, mail in enumerate(mails):
            with st.container():
                # 메일 헤더
                header_cols = st.columns([3, 1, 1, 1])
                
                with header_cols[0]:
                    subject = mail.get('subject', '제목 없음')
                    sender = mail.get('sender_name', mail.get('sender', '알 수 없음'))
                    st.markdown(f"**{subject}**")
                    st.caption(f"📧 {sender}")
                
                with header_cols[1]:
                    priority = mail.get('priority', 'normal')
                    priority_icon = {
                        'high': '🔴',
                        'normal': '🟡',
                        'low': '🟢'
                    }.get(priority.lower(), '🟡')
                    st.markdown(f"{priority_icon} {priority}")
                
                with header_cols[2]:
                    received_date = mail.get('received_date', '')
                    if received_date:
                        try:
                            dt = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%m-%d %H:%M')
                        except:
                            formatted_date = received_date[:10]
                    else:
                        formatted_date = '날짜 없음'
                    st.caption(f"📅 {formatted_date}")
                
                with header_cols[3]:
                    # 메일 ID (디버깅용)
                    mail_id = mail.get('id', '')
                    if mail_id:
                        st.caption(f"ID: {mail_id[:8]}...")
                
                # 메일 액션 버튼들
                action_cols = st.columns(4)
                
                with action_cols[0]:
                    if st.button(f"📧 상세보기", key=f"detail_{i}"):
                        st.session_state.selected_mail = mail
                        st.session_state.refresh_trigger += 1
                
                with action_cols[1]:
                    if st.button(f"📝 답장", key=f"reply_{i}"):
                        st.info("답장 기능은 아직 구현되지 않았습니다.")
                
                with action_cols[2]:
                    if st.button(f"📁 이동", key=f"move_{i}"):
                        st.info("이동 기능은 아직 구현되지 않았습니다.")
                
                with action_cols[3]:
                    if st.button(f"🗑️ 삭제", key=f"delete_{i}"):
                        st.info("삭제 기능은 아직 구현되지 않았습니다.")
                
                st.divider()
    
    elif view_mode == 'grid':
        st.subheader("📧 메일 그리드")
        
        # 그리드 레이아웃 (3열)
        cols = st.columns(3)
        for i, mail in enumerate(mails):
            col_idx = i % 3
            with cols[col_idx]:
                with st.container():
                    st.markdown("---")
                    
                    # 메일 카드
                    subject = mail.get('subject', '제목 없음')
                    sender = mail.get('sender_name', mail.get('sender', '알 수 없음'))
                    priority = mail.get('priority', 'normal')
                    
                    priority_icon = {
                        'high': '🔴',
                        'normal': '🟡',
                        'low': '🟢'
                    }.get(priority.lower(), '🟡')
                    
                    st.markdown(f"**{subject}**")
                    st.caption(f"📧 {sender}")
                    st.caption(f"{priority_icon} {priority}")
                    
                    # 액션 버튼
                    if st.button(f"상세보기", key=f"grid_detail_{i}"):
                        st.session_state.selected_mail = mail
                        st.session_state.refresh_trigger += 1

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
        if st.button("📧 답장하기", key="reply_detail"):
            st.info("답장 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[1]:
        if st.button("📁 폴더 이동", key="move_detail"):
            st.info("이동 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[2]:
        if st.button("🏷️ 라벨 편집", key="label_detail"):
            st.info("라벨 편집 기능은 아직 구현되지 않았습니다.")
    
    with action_cols[3]:
        if st.button("🗑️ 삭제", key="delete_detail"):
            st.info("삭제 기능은 아직 구현되지 않았습니다.")
    
    # 뒤로가기 버튼
    st.markdown("---")
    if st.button("← 목록으로 돌아가기", key="back_to_list"):
        st.session_state.selected_mail = None
        st.session_state.refresh_trigger += 1

def clear_mail_selection():
    """선택된 메일을 초기화합니다."""
    st.session_state.selected_mail = None

# 기존 함수들 (호환성을 위해 유지)
def display_mail_list_with_sidebar(mail_list: List[Dict[str, Any]], title: str = "메일 목록"):
    """
    메일을 리스트 형태로 표시하고 사이드바에 상세 내용을 표시
    
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
                    st.session_state.refresh_trigger += 1
            
            with action_cols[1]:
                if st.button(f"📝 답장", key=f"reply_{i}"):
                    st.info("답장 기능은 아직 구현되지 않았습니다.")
            
            with action_cols[2]:
                if st.button(f"📁 이동", key=f"move_{i}"):
                    st.info("이동 기능은 아직 구현되지 않았습니다.")
            
            with action_cols[3]:
                if st.button(f"🗑️ 삭제", key=f"delete_{i}"):
                    st.info("삭제 기능은 아직 구현되지 않았습니다.")

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
                st.session_state.refresh_trigger += 1
        
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
                st.session_state.refresh_trigger += 1

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
    display_mail_list_with_sidebar(mail_list, title)

def main():
    """메인 앱"""
    st.title("📧 Mail Management System")
    
    # 사이드바
    with st.sidebar:
        st.header("🔧 설정")
        
        # 새로고침 버튼
        if st.button("🔄 데이터 새로고침"):
            st.session_state.refresh_trigger += 1
        
        st.divider()
        
        # 필터 옵션
        st.subheader("🔍 필터")
        
        priority_filter = st.multiselect(
            "우선순위",
            ['high', 'normal', 'low'],
            default=['high', 'normal', 'low']
        )
        
        read_filter = st.selectbox(
            "읽음 상태",
            ['전체', '읽음', '안읽음']
        )
        
        st.divider()
        
        # 통계
        st.subheader("📊 통계")
        if st.session_state.mails:
            total_mails = len(st.session_state.mails)
            unread_mails = len([m for m in st.session_state.mails if not m.get('is_read', False)])
            high_priority = len([m for m in st.session_state.mails if m.get('priority', 'normal') == 'high'])
            
            st.metric("전체 메일", total_mails)
            st.metric("안읽음", unread_mails)
            st.metric("높은 우선순위", high_priority)
    
    # 메인 컨텐츠
    if st.session_state.selected_mail:
        display_mail_detail(st.session_state.selected_mail)
    else:
        # 메일 목록 표시
        mails = load_sample_mails()
        st.session_state.mails = mails
        display_mail_list(mails)

if __name__ == "__main__":
    main() 