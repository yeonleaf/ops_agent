#!/usr/bin/env python3
"""
향상된 티켓 UI 모듈
티켓 목록 표시, 선택, 데이터 추출 등의 기능을 제공합니다.
"""

import streamlit as st
import json
import re
from typing import Dict, List, Any, Optional, Union

def is_ticket_response(response: str) -> bool:
    """
    응답이 티켓 데이터인지 확인합니다.
    
    Args:
        response (str): AI 에이전트의 응답 문자열
        
    Returns:
        bool: 티켓 응답이면 True, 아니면 False
    """
    # JSON 형태의 응답인지 확인
    try:
        data = json.loads(response)
        # 티켓 관련 키가 있는지 확인 (tasks 배열 포함)
        ticket_keys = ['new_tickets_created', 'existing_tickets_found', 'tickets', 'tasks']
        return any(key in data for key in ticket_keys)
    except (json.JSONDecodeError, TypeError):
        # JSON이 아니면 티켓 관련 키워드가 있는지 확인
        ticket_keywords = ['티켓', 'ticket', 'new_tickets', 'existing_tickets', 'tasks']
        return any(keyword.lower() in response.lower() for keyword in ticket_keywords)

def extract_ticket_data_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    AI 응답에서 티켓 데이터를 추출합니다.
    
    Args:
        response (str): AI 에이전트의 응답 문자열
        
    Returns:
        Optional[Dict[str, Any]]: 추출된 티켓 데이터 또는 None
    """
    # 응답에서 JSON 부분만 추출 시도
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    
    if json_start != -1 and json_end > json_start:
        json_str = response[json_start:json_end]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # 개행 문자나 제어 문자 문제일 수 있으므로 정리
            cleaned_json = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            try:
                data = json.loads(cleaned_json)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 전체 응답으로 재시도
                try:
                    data = json.loads(response)
                except json.JSONDecodeError:
                    return None
    else:
        # JSON이 없으면 전체 응답으로 시도
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return None
    
    # tasks 배열이 있는 경우 (현재 응답 형식)
    if 'tasks' in data and isinstance(data['tasks'], list):
        # tasks를 tickets 형식으로 변환
        tickets = []
        for task in data['tasks']:
            if task.get('type') == 'existing_ticket':
                ticket = {
                    'ticket_id': task.get('ticket_id'),
                    'title': task.get('title', '제목 없음'),
                    'status': task.get('status', 'pending'),
                    'type': 'existing_ticket',
                    'priority': task.get('priority', 'Medium'),
                    'reporter': '시스템',
                    'created_at': task.get('created_at', ''),
                    'description': task.get('description', '메일 내용이 없습니다.'),
                    'message_id': task.get('message_id', ''),
                    'action': task.get('action', ''),
                    'content': task.get('content', '메일 내용을 불러올 수 없습니다.')
                }
                tickets.append(ticket)
        
        if tickets:
            return {
                'tickets': tickets,
                'new_tickets_created': 0,
                'existing_tickets_found': len(tickets),
                'summary': data.get('summary', {})
            }
    
    # 기존 형식 지원
    if 'tickets' in data:
        return data
    elif 'new_tickets_created' in data or 'existing_tickets_found' in data:
        return data
    else:
        return None

def extract_ticket_data_with_regex(response: str) -> Optional[Dict[str, Any]]:
    """
    정규식을 사용하여 응답에서 티켓 데이터를 추출합니다.
    
    Args:
        response (str): AI 에이전트의 응답 문자열
        
    Returns:
        Optional[Dict[str, Any]]: 추출된 티켓 데이터 또는 None
    """
    # 티켓 ID 패턴 (예: T-123, TICKET-456 등)
    ticket_id_pattern = r'[Tt][Ii][Cc][Kk][Ee][Tt]?[-_]?\d+'
    ticket_ids = re.findall(ticket_id_pattern, response)
    
    if ticket_ids:
        # 간단한 티켓 데이터 구조 생성
        tickets = []
        for i, ticket_id in enumerate(ticket_ids):
            tickets.append({
                "ticket_id": ticket_id,
                "title": f"추출된 티켓 {i+1}",
                "status": "new",
                "type": "extracted"
            })
        
        return {
            "tickets": tickets,
            "new_tickets_created": len(tickets),
            "existing_tickets_found": 0
        }
    
    return None

def is_valid_ticket_data(data: Dict[str, Any]) -> bool:
    """
    티켓 데이터가 유효한지 확인합니다.
    
    Args:
        data (Dict[str, Any]): 검증할 티켓 데이터
        
    Returns:
        bool: 유효하면 True, 아니면 False
    """
    if not isinstance(data, dict):
        return False
    
    # 필수 키 확인 (tickets는 필수, non_work_emails는 선택)
    if 'tickets' not in data:
        return False
    
    # tickets가 리스트인지 확인
    if not isinstance(data['tickets'], list):
        return False
    
    # non_work_emails가 있다면 리스트인지 확인
    if 'non_work_emails' in data and not isinstance(data['non_work_emails'], list):
        return False
    
    # 각 티켓이 최소한의 정보를 가지고 있는지 확인
    for ticket in data['tickets']:
        if not isinstance(ticket, dict):
            return False
        if 'ticket_id' not in ticket:
            return False
    
    return True

def clear_ticket_selection():
    """티켓 선택 상태를 초기화합니다."""
    if 'selected_ticket_id' in st.session_state:
        st.session_state.selected_ticket_id = None
    if 'selected_ticket_data' in st.session_state:
        st.session_state.selected_ticket_data = None

def display_ticket_list_with_sidebar(ticket_data: Dict[str, Any], title: str = "티켓 목록"):
    """
    사이드바와 함께 티켓 목록을 표시합니다.
    
    Args:
        ticket_data (Dict[str, Any]): 표시할 티켓 데이터 (tickets와 non_work_emails 포함)
        title (str): 섹션 제목
    """
    if not is_valid_ticket_data(ticket_data):
        st.error("유효하지 않은 티켓 데이터입니다.")
        return
    
    st.subheader(f"🎫 {title}")
    
    # 통계 정보 표시
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("새로 생성된 티켓", ticket_data.get('new_tickets_created', 0))
    with col2:
        st.metric("기존 티켓", ticket_data.get('existing_tickets_found', 0))
    with col3:
        st.metric("총 티켓", len(ticket_data.get('tickets', [])))
    with col4:
        non_work_count = len(ticket_data.get('non_work_emails', []))
        st.metric("업무용 아님", non_work_count)
    
    # 티켓 목록을 두 컬럼으로 분할
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 1. 티켓 목록 섹션
        st.markdown("### 📋 티켓 목록")
        
        if ticket_data.get('tickets'):
            # 티켓 목록을 카드 형식의 버튼으로 표시
            for i, ticket in enumerate(ticket_data['tickets']):
                # 메일 제목 또는 기본 제목 생성
                title = ticket.get('title', f'티켓 {i+1}')
                if not title or title.strip() == '':
                    title = f'제목 없는 티켓 {i+1}'
                
                # 상태와 우선순위
                status = ticket.get('status', 'new')
                priority = ticket.get('priority', 'Medium')
                sender = ticket.get('sender', 'Unknown')
                created_at = ticket.get('created_at', 'N/A')
                
                # 상태 아이콘
                status_icon = {
                    'new': '🆕',
                    'in_progress': '🔄',
                    'resolved': '✅',
                    'closed': '🔒'
                }.get(status, '❓')
                
                # 우선순위 아이콘
                priority_icon = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(priority, '⚪')
                
                # 카드 스타일의 컨테이너
                with st.container():
                    # 카드 헤더 (클릭 가능한 버튼)
                    col1, col2, col3 = st.columns([1, 3, 1])
                    
                    with col1:
                        st.markdown(f"**{status_icon} {priority_icon}**")
                    
                    with col2:
                        # 제목을 클릭 가능한 버튼으로 표시
                        if st.button(f"**{title}**", key=f"ticket_title_{i}", use_container_width=True):
                            st.session_state.selected_ticket_id = ticket.get('ticket_id')
                            st.session_state.selected_ticket_data = ticket
                            st.rerun()
                    
                    with col3:
                        # 날짜 표시
                        if created_at != 'N/A':
                            try:
                                # ISO 형식 날짜를 파싱하여 간단하게 표시
                                from datetime import datetime
                                if isinstance(created_at, str):
                                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    date_str = dt.strftime('%m/%d')
                                else:
                                    date_str = str(created_at)[:10]
                            except:
                                date_str = str(created_at)[:10]
                            st.markdown(f"<small>{date_str}</small>", unsafe_allow_html=True)
                    
                    # 발신자 정보 (작은 텍스트)
                    st.markdown(f"<small>📧 {sender}</small>", unsafe_allow_html=True)
                    
                    # 구분선
                    st.markdown("---")
        else:
            st.info("생성된 티켓이 없습니다.")
        
        # 2. 업무용으로 분류되지 않은 메일 섹션
        if ticket_data.get('non_work_emails'):
            st.markdown("---")
            
            # 간단한 요약 정보 (토글 밖에 표시)
            non_work_count = len(ticket_data['non_work_emails'])
            st.markdown(f"### 📧 업무용으로 분류되지 않은 메일 ({non_work_count}개)")
            
            # 토글 형태로 non-work 메일 표시
            with st.expander("📋 메일 목록 보기", expanded=False):
                st.info("AI가 업무용이 아니라고 판단한 메일들입니다. 티켓으로 변환이 필요한 메일이 있다면 '정정' 버튼을 클릭하세요.")
                
                for i, email in enumerate(ticket_data['non_work_emails']):
                    with st.container():
                        # 메일 카드 스타일
                        st.markdown("""
                        <style>
                        .email-card {
                            background-color: #f8f9fa;
                            border: 1px solid #dee2e6;
                            border-radius: 8px;
                            padding: 12px;
                            margin: 8px 0;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        
                        # 메일 정보를 컬럼으로 배치
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            # 메일 제목 (강조)
                            subject = email.get('subject', '제목 없음')
                            if not subject or subject.strip() == '':
                                subject = f'제목 없는 메일 {i+1}'
                            st.markdown(f"**📧 {subject}**")
                            
                            # 발신자 정보
                            sender = email.get('sender', '발신자 없음')
                            st.markdown(f"👤 **발신자:** {sender}")
                            
                            # 분류 이유 (중요 정보)
                            reason = email.get('classification_reason', '분류 이유 없음')
                            st.markdown(f"💡 **분류 이유:** {reason}")
                        
                        with col2:
                            # 메일 내용 미리보기
                            body = email.get('body', '내용 없음')
                            if body and len(body) > 80:
                                preview = body[:80] + "..."
                            else:
                                preview = body
                            st.markdown(f"**📝 내용 미리보기:**")
                            st.markdown(f"<small>{preview}</small>", unsafe_allow_html=True)
                            
                            # 읽음 상태
                            is_read = email.get('is_read', False)
                            read_status = "✅ 읽음" if is_read else "📬 안읽음"
                            st.markdown(f"**상태:** {read_status}")
                        
                        with col3:
                            # 정정 버튼
                            if st.button("정정", key=f"correct_email_{i}", use_container_width=True, type="primary"):
                                # 티켓 생성 프로세스 시작
                                with st.spinner("티켓 생성 중..."):
                                    try:
                                        # 백엔드 함수 호출
                                        from unified_email_service import create_ticket_from_single_email
                                        ticket = create_ticket_from_single_email(email)
                                        
                                        if ticket:
                                            st.success("✅ 티켓이 성공적으로 생성되었습니다!")
                                            # 화면 새로고침
                                            st.rerun()
                                        else:
                                            st.error("❌ 티켓 생성에 실패했습니다.")
                                            
                                    except Exception as e:
                                        st.error(f"❌ 티켓 생성 중 오류가 발생했습니다: {str(e)}")
                        
                        # 구분선
                        st.markdown("---")
            
            # 토글 밖에 간단한 요약 정보 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 메일", non_work_count)
            with col2:
                read_count = sum(1 for email in ticket_data['non_work_emails'] if email.get('is_read', False))
                st.metric("읽은 메일", read_count)
            with col3:
                unread_count = sum(1 for email in ticket_data['non_work_emails'] if not email.get('is_read', False))
                st.metric("안 읽은 메일", unread_count)
        else:
            st.markdown("---")
            st.info("📧 업무용으로 분류되지 않은 메일이 없습니다.")
    
    with col2:
        st.markdown("### 🔍 선택된 티켓 상세정보")
        
        if st.session_state.get('selected_ticket_data'):
            selected = st.session_state.selected_ticket_data
            
            # 카드 스타일의 상세정보
            with st.container():
                st.markdown("""
                <style>
                .ticket-detail-card {
                    background-color: #f0f2f6;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    border-left: 4px solid #1f77b4;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # 티켓 헤더 정보
                st.markdown("#### 📌 기본 정보")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**제목:** {selected.get('title', 'N/A')}")
                    st.markdown(f"**티켓 ID:** {selected.get('ticket_id', 'N/A')}")
                with col2:
                    st.markdown(f"**타입:** {selected.get('type', 'N/A')}")
                    st.markdown(f"**발신자:** {selected.get('sender', 'N/A')}")
                
                # 상태 및 우선순위 (시각적으로 강조)
                st.markdown("#### 🏷️ 상태 및 우선순위")
                status = selected.get('status', 'pending')
                priority = selected.get('priority', 'Medium')
                
                status_icon = {
                    'new': '🆕',
                    'in_progress': '🔄',
                    'resolved': '✅',
                    'closed': '🔒'
                }.get(status, '❓')
                
                priority_icon = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(priority, '⚪')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**상태:** {status_icon} {status}")
                with col2:
                    st.markdown(f"**우선순위:** {priority_icon} {priority}")
                
                # 날짜 정보
                st.markdown("#### 📅 날짜 정보")
                if selected.get('created_at'):
                    try:
                        from datetime import datetime
                        if isinstance(selected['created_at'], str):
                            dt = datetime.fromisoformat(selected['created_at'].replace('Z', '+00:00'))
                            created_date = dt.strftime('%Y년 %m월 %d일 %H:%M')
                        else:
                            created_date = str(selected['created_at'])[:10]
                    except:
                        created_date = str(selected['created_at'])[:10]
                    st.markdown(f"**생성일:** {created_date}")
                
                # 담당자 정보
                st.markdown("#### 👤 담당자 정보")
                st.markdown(f"**담당자:** {selected.get('reporter', 'N/A')}")
                
                # 메일 내용 정보 (접을 수 있는 형태)
                if selected.get('content') and selected['content'] != '메일 내용을 불러올 수 없습니다.':
                    with st.expander("📧 메일 내용 보기", expanded=False):
                        st.markdown(selected['content'])
                elif selected.get('description') and selected['description'] != '메일 내용이 없습니다.':
                    with st.expander("📝 메일 설명 보기", expanded=False):
                        st.markdown(selected['description'])
                else:
                    st.markdown("#### 📝 메일 내용")
                    st.info("메일 내용을 불러올 수 없습니다. 메일 ID를 통해 직접 확인해주세요.")
                
                # 액션 정보
                if selected.get('action'):
                    st.markdown("#### ⚡ 액션")
                    st.markdown(f"**최근 액션:** {selected['action']}")
                
                # 구분선
                st.markdown("---")
                
                # 상태 변경 기능
                st.markdown("#### 🔄 상태 관리")
                new_status = st.selectbox(
                    "상태 변경",
                    options=['pending', 'approved', 'rejected'],
                    index=['pending', 'approved', 'rejected'].index(selected.get('status', 'pending'))
                )
                
                if new_status != selected.get('status'):
                    if st.button("상태 업데이트", use_container_width=True):
                        try:
                            # SQLite DB 업데이트 (VectorDB도 함께 동기화됨)
                            from sqlite_ticket_models import SQLiteTicketManager
                            ticket_manager = SQLiteTicketManager()
                            
                            # ticket_id가 문자열인 경우 정수로 변환
                            ticket_id = selected.get('ticket_id', '')
                            if isinstance(ticket_id, str) and ticket_id.startswith('T'):
                                # T20250822123456 형식에서 숫자 부분 추출
                                ticket_id = int(ticket_id[1:]) if ticket_id[1:].isdigit() else 0
                            
                            if ticket_id:
                                old_status = selected.get('status', 'pending')
                                ticket_manager.update_ticket_status(ticket_id, new_status, old_status)
                                st.success(f"✅ 상태가 {new_status}로 업데이트되었습니다! (RDB + VectorDB 동기화 완료)")
                                selected['status'] = new_status
                            else:
                                st.error("❌ 티켓 ID를 찾을 수 없습니다.")
                                
                        except Exception as e:
                            st.error(f"❌ 상태 업데이트 실패: {str(e)}")
                        st.rerun()
            
            # 선택 해제 버튼
            if st.button("선택 해제", use_container_width=True, type="secondary"):
                clear_ticket_selection()
                st.rerun()
        else:
            st.info("👈 왼쪽에서 티켓 버튼을 클릭하여 상세정보를 확인하세요.")
            st.markdown("---")
            st.markdown("**💡 팁:**")
            st.markdown("- 🆕 새로 생성된 티켓")
            st.markdown("- 🔄 진행 중인 티켓")
            st.markdown("- ✅ 해결된 티켓")
            st.markdown("- 🔒 종료된 티켓")
            st.markdown("- 🔴 높은 우선순위")
            st.markdown("- 🟡 중간 우선순위")
            st.markdown("- 🟢 낮은 우선순위")
            st.markdown("- 📧 업무용이 아닌 메일은 '정정' 버튼으로 티켓 변환 가능")

def demo_ticket_ui():
    """티켓 UI 데모를 실행합니다."""
    st.title("🎫 향상된 티켓 UI 데모")
    
    # 샘플 티켓 데이터
    sample_data = {
        "new_tickets_created": 2,
        "existing_tickets_found": 1,
        "tickets": [
            {
                "ticket_id": "T-001",
                "title": "서버 장애 보고",
                "status": "new",
                "type": "incident",
                "priority": "high",
                "reporter": "김철수",
                "description": "프로덕션 서버에서 500 에러가 발생하고 있습니다."
            },
            {
                "ticket_id": "T-002",
                "title": "새 기능 요청",
                "status": "in_progress",
                "type": "feature",
                "priority": "medium",
                "reporter": "이영희",
                "description": "사용자 대시보드에 차트 기능을 추가해주세요."
            },
            {
                "ticket_id": "T-003",
                "title": "문서 업데이트",
                "status": "resolved",
                "type": "documentation",
                "priority": "low",
                "reporter": "박민수",
                "description": "API 문서를 최신 버전으로 업데이트했습니다."
            }
        ],
        "non_work_emails": [
            {
                "subject": "주말 휴무 안내",
                "sender": "HR 담당자",
                "body": "주말 휴무 기간 동안 고객 문의는 월요일 오전 9시부터 접수해주세요.",
                "is_read": True,
                "classification_reason": "휴무 관련 메일"
            },
            {
                "subject": "오프라인 교육 일정",
                "sender": "교육 담당자",
                "body": "오프라인 교육 일정이 변경되었습니다. 확인해주세요.",
                "is_read": False,
                "classification_reason": "교육 관련 메일"
            }
        ]
    }
    
    # 티켓 UI 표시
    display_ticket_list_with_sidebar(sample_data, "샘플 티켓 데이터")
    
    # 기능 설명
    st.markdown("---")
    st.markdown("### 🚀 주요 기능")
    st.markdown("- **티켓 목록 표시**: 생성된 티켓과 기존 티켓을 구분하여 표시")
    st.markdown("- **티켓 선택**: 클릭으로 티켓을 선택하고 상세 정보 확인")
    st.markdown("- **상태 관리**: 선택된 티켓의 상태를 변경")
    st.markdown("- **반응형 레이아웃**: 사이드바와 메인 컨텐츠로 효율적인 공간 활용")

if __name__ == "__main__":
    demo_ticket_ui() 