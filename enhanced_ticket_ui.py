#!/usr/bin/env python3
"""
Enhanced Ticket UI - Streamlit 기반 티켓 관리 시스템
st.rerun() 대신 session state를 활용한 상태 관리로 개선
"""

import streamlit as st
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
from vector_db_models import VectorDBManager

# 로깅 설정 추가
from module.logging_config import setup_logging
import logging

# 로깅 초기화
setup_logging(level="INFO", log_file="logs/enhanced_ticket_ui.log", console_output=True)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="Enhanced Ticket Management",
    page_icon="🎫",
    layout="wide"
)

# 기본 변수 초기화
tickets = []
selected_ticket = None
ui_mode = 'card'

def display_mail_attachments(message_id: str):
    """메일의 첨부파일을 표시합니다."""
    try:
        from gmail_api_client import GmailAPIClient
        
        # Gmail API 클라이언트 초기화
        gmail_client = GmailAPIClient()
        
        # 첨부파일 목록 조회
        attachments = gmail_client.get_message_attachments(message_id)
        
        if not attachments:
            st.info("첨부파일이 없습니다.")
            return
        
        st.success(f"📎 첨부파일 {len(attachments)}개 발견")
        
        for i, attachment in enumerate(attachments):
            attachment_id = attachment.get('id', '')
            filename = attachment.get('filename', '알 수 없는 파일')
            mime_type = attachment.get('mime_type', 'application/octet-stream')
            size = attachment.get('size', 0)
            
            # 파일 크기 포맷팅
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} bytes"
            
            # 첨부파일 정보 표시
            with st.expander(f"📄 {filename}", expanded=False):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**파일명:** {filename}")
                    st.write(f"**타입:** {mime_type}")
                    st.write(f"**크기:** {size_str}")
                
                with col2:
                    if st.button("📥 다운로드", key=f"download_{message_id}_{i}"):
                        # 첨부파일 다운로드
                        file_content = gmail_client.download_attachment(message_id, attachment_id)
                        if file_content:
                            st.download_button(
                                label="💾 저장",
                                data=file_content,
                                file_name=filename,
                                mime=mime_type,
                                key=f"save_{message_id}_{i}"
                            )
                        else:
                            st.error("첨부파일 다운로드에 실패했습니다.")
                
                with col3:
                    if st.button("👁️ 미리보기", key=f"preview_{message_id}_{i}"):
                        # 텍스트 파일 미리보기
                        if mime_type.startswith('text/'):
                            file_content = gmail_client.download_attachment(message_id, attachment_id)
                            if file_content:
                                try:
                                    text_content = file_content.decode('utf-8')
                                    st.text_area("파일 내용", text_content, height=200, key=f"preview_content_{message_id}_{i}")
                                except:
                                    st.warning("텍스트로 변환할 수 없습니다.")
                        else:
                            st.info("미리보기는 텍스트 파일만 지원됩니다.")
                
                st.divider()
                
    except Exception as e:
        st.error(f"첨부파일 조회 중 오류가 발생했습니다: {str(e)}")
        st.info("💡 Gmail API 설정을 확인해주세요.")

def display_vectordb_attachments(attachment_chunks):
    """VectorDB에서 가져온 첨부파일 정보를 표시합니다."""
    try:
        if not attachment_chunks:
            st.info("첨부파일이 없습니다.")
            return
        
        st.success(f"📎 첨부파일 {len(attachment_chunks)}개 발견")
        
        for i, chunk in enumerate(attachment_chunks):
            filename = chunk.original_filename or '알 수 없는 파일'
            mime_type = chunk.mime_type or 'application/octet-stream'
            size = chunk.file_size or 0
            analysis_summary = chunk.analysis_summary or ""
            keywords = chunk.keywords or []
            file_category = chunk.file_category or ""
            business_relevance = chunk.business_relevance or ""
            
            # 파일 크기 포맷팅
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} bytes"
            
            # 첨부파일 정보 표시
            with st.expander(f"📄 {filename}", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**파일명:** {filename}")
                    st.write(f"**타입:** {mime_type}")
                    st.write(f"**크기:** {size_str}")
                    
                    if file_category:
                        st.write(f"**카테고리:** {file_category}")
                    
                    if business_relevance:
                        st.write(f"**업무 관련성:** {business_relevance}")
                    
                    if keywords:
                        st.write(f"**키워드:** {', '.join(keywords)}")
                
                with col2:
                    if analysis_summary:
                        st.write("**분석 요약:**")
                        st.write(analysis_summary)
                
                # 파일 내용 표시 (텍스트인 경우)
                if chunk.content and mime_type.startswith('text/'):
                    st.write("**파일 내용:**")
                    st.text_area("", chunk.content, height=200, disabled=True, key=f"vectordb_content_{i}")
                
                st.divider()
                
    except Exception as e:
        st.error(f"VectorDB 첨부파일 표시 중 오류가 발생했습니다: {str(e)}")

def load_tickets():
    """데이터베이스에서 티켓을 로드합니다."""
    try:
        logger.info("📋 티켓 목록 로드 시작")
        conn = sqlite3.connect('tickets.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, description, status, priority, assignee, created_at, 
                   original_message_id, message_id, ticket_id
            FROM tickets 
            ORDER BY created_at DESC
        """)
        
        tickets = []
        for row in cursor.fetchall():
            ticket = {
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'status': row[3],
                'priority': row[4],
                'assignee': row[5],
                'created_at': row[6],
                'original_message_id': row[7],
                'message_id': row[8],
                'ticket_id': row[9]
            }
            tickets.append(ticket)
        
        conn.close()
        return tickets
    except Exception as e:
        st.error(f"티켓 로드 중 오류: {str(e)}")
        return []

def update_ticket_status(ticket_id: int, new_status: str):
    """티켓 상태를 업데이트합니다."""
    try:
        conn = sqlite3.connect('tickets.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tickets 
            SET status = ? 
            WHERE id = ?
        """, (new_status, ticket_id))
        
        conn.commit()
        conn.close()
        
        # 상태 업데이트 완료
        return True
    except Exception as e:
        st.error(f"상태 업데이트 중 오류: {str(e)}")
        return False

def delete_label_from_ticket(ticket_id: int, label: str):
    """티켓에서 레이블을 삭제합니다."""
    try:
        print(f"🔍 delete_label_from_ticket 호출: ticket_id={ticket_id}, label={label}")
        
        from sqlite_ticket_models import SQLiteTicketManager
        from datetime import datetime
        
        ticket_manager = SQLiteTicketManager()
        current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
        
        print(f"🔍 현재 티켓 조회 결과: {current_ticket}")
        if current_ticket:
            print(f"🔍 현재 레이블: {current_ticket.labels}")
        
        if current_ticket and current_ticket.labels:
            # 레이블에서 해당 항목 제거
            old_labels = current_ticket.labels.copy()
            print(f"🔍 기존 레이블 복사: {old_labels}")
            
            if label in old_labels:
                old_labels.remove(label)
                print(f"🔍 레이블 제거 후: {old_labels}")
                
                # RDB 업데이트
                result = ticket_manager.update_ticket_labels(ticket_id, old_labels, current_ticket.labels)
                print(f"🔍 RDB 업데이트 결과: {result}")
                print(f"✅ RDB 레이블 삭제 완료: {label}")
                
                # user_action 테이블에 레이블 삭제 기록
                try:
                    from database_models import DatabaseManager, UserAction
                    
                    db_manager = DatabaseManager()
                    user_action = UserAction(
                        action_id=None,
                        ticket_id=ticket_id,
                        message_id=current_ticket.original_message_id,
                        action_type='label_deleted',
                        action_description=f'레이블 "{label}" 삭제',
                        old_value=label,
                        new_value='',
                        context=f'티켓 ID: {ticket_id}, 제목: {current_ticket.title}',
                        created_at=datetime.now().isoformat(),
                        user_id='user'
                    )
                    db_manager.insert_user_action(user_action)
                    print(f"✅ 레이블 삭제 user_action 기록 완료: {label}")
                except Exception as e:
                    print(f"⚠️ user_action 기록 실패: {e}")
                    import traceback
                    print(f"⚠️ user_action 오류 상세: {traceback.format_exc()}")
                
                return True
            else:
                print(f"⚠️ 레이블 '{label}'을 찾을 수 없음")
                return False
        else:
            print(f"⚠️ 티켓을 찾을 수 없거나 레이블이 없음: {ticket_id}")
            return False
            
    except Exception as e:
        print(f"❌ 레이블 삭제 중 오류: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")
        return False

def add_label_to_ticket(ticket_id: int, new_label: str):
    """티켓에 새 레이블을 추가합니다."""
    try:
        print(f"🔍 add_label_to_ticket 호출: ticket_id={ticket_id}, new_label={new_label}")
        
        from sqlite_ticket_models import SQLiteTicketManager
        from datetime import datetime
        
        ticket_manager = SQLiteTicketManager()
        current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
        
        print(f"🔍 현재 티켓 조회 결과: {current_ticket}")
        if current_ticket:
            print(f"🔍 현재 레이블: {current_ticket.labels}")
        
        if current_ticket:
            # 레이블에 새 항목 추가
            old_labels = current_ticket.labels.copy() if current_ticket.labels else []
            new_labels = old_labels + [new_label.strip()]
            print(f"🔍 기존 레이블: {old_labels}")
            print(f"🔍 새 레이블 목록: {new_labels}")
            
            # RDB 업데이트
            result = ticket_manager.update_ticket_labels(ticket_id, new_labels, old_labels)
            print(f"🔍 RDB 업데이트 결과: {result}")
            print(f"✅ RDB 레이블 추가 완료: {new_label.strip()}")
            
            # user_action 테이블에 레이블 추가 기록
            try:
                from database_models import DatabaseManager, UserAction
                
                db_manager = DatabaseManager()
                user_action = UserAction(
                    action_id=None,
                    ticket_id=ticket_id,
                    message_id=current_ticket.original_message_id,
                    action_type='label_added',
                    action_description=f'레이블 "{new_label.strip()}" 추가',
                    old_value='',
                    new_value=new_label.strip(),
                    context=f'티켓 ID: {ticket_id}, 제목: {current_ticket.title}',
                    created_at=datetime.now().isoformat(),
                    user_id='user'
                )
                db_manager.insert_user_action(user_action)
                print(f"✅ 레이블 추가 user_action 기록 완료: {new_label.strip()}")
            except Exception as e:
                print(f"⚠️ user_action 기록 실패: {e}")
                import traceback
                print(f"⚠️ user_action 오류 상세: {traceback.format_exc()}")
            
            return True
        else:
            print(f"⚠️ 티켓을 찾을 수 없음: {ticket_id}")
            return False
            
    except Exception as e:
        print(f"❌ 레이블 추가 중 오류: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")
        return False

def clear_ticket_selection():
    """선택된 티켓을 초기화합니다."""
    global selected_ticket
    selected_ticket = None

def display_ticket_list(tickets: List[Dict[str, Any]]):
    """티켓 목록을 표시합니다."""
    if not tickets:
        st.info("등록된 티켓이 없습니다.")
        return
    
    # UI 모드 선택
    col1, col2 = st.columns([3, 1])
    with col2:
        ui_mode = st.selectbox(
            "보기 모드",
            ['card', 'table'],
            index=0,
            key="ui_mode_selector"
        )
    
    if ui_mode == 'card':
        st.subheader("📋 티켓 목록 (카드 형태)")
        
        for i, ticket in enumerate(tickets):
            with st.container():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    title = ticket.get('title', '제목 없음')
                    description = ticket.get('description', '')
                    status = ticket.get('status', '상태 없음')
                    priority = ticket.get('priority', '우선순위 없음')
                    created_at = ticket.get('created_at', '날짜 없음')
                    
                    # 상태별 색상 설정
                    status_colors = {
                        'new': '🔵',
                        'pending': '🟡', 
                        'in_progress': '🟠',
                        'resolved': '🟢',
                        'closed': '⚫'
                    }
                    status_icon = status_colors.get(status, '❓')
                    
                    # 우선순위별 색상 설정
                    priority_colors = {
                        'low': '🟢',
                        'medium': '🟡',
                        'high': '🟠', 
                        'urgent': '🔴'
                    }
                    priority_icon = priority_colors.get(priority, '❓')
                    
                    st.write(f"**{title}** {status_icon} {priority_icon}")
                    
                    if isinstance(created_at, str):
                        try:
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            formatted_date = str(created_at)
                    else:
                        formatted_date = str(created_at)
                    
                    st.write(f"📅 {formatted_date}")
                    if description and len(description) > 100:
                        st.write(f"📝 {description[:100]}...")
                    elif description:
                        st.write(f"📝 {description}")
                
                with col2:
                    # 티켓 선택 버튼
                    if st.button(f"상세보기", key=f"view_{ticket.get('id', i)}"):
                        global selected_ticket
                        selected_ticket = ticket
                        st.rerun()
                
                st.divider()
    
    elif ui_mode == 'table':
        st.subheader("📋 티켓 목록 (테이블 형태)")
        
        # 테이블 데이터 준비
        table_data = []
        for ticket in tickets:
            created_at = ticket.get('created_at', '날짜 없음')
            if isinstance(created_at, str):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = created_at
            else:
                formatted_date = str(created_at)
            
            table_data.append({
                "ID": ticket.get('id', 'N/A'),
                "제목": ticket.get('title', '제목 없음'),
                "상태": ticket.get('status', '상태 없음'),
                "생성일": formatted_date,
                "설명": ticket.get('description', '설명 없음')[:50] + "..." if ticket.get('description') and len(ticket.get('description', '')) > 50 else ticket.get('description', '설명 없음')
            })
        
        st.dataframe(table_data, use_container_width=True)

# 호환성을 위한 함수들 (langchain_chatbot_app.py에서 사용)
def display_ticket_list_with_sidebar(tickets: List[Dict[str, Any]], ui_mode: str = 'button_list'):
    """티켓 목록을 사이드바와 함께 표시합니다."""
    
    if not tickets:
        st.info("표시할 티켓이 없습니다.")
        return
    
    if ui_mode == 'button_list':
        st.subheader("📋 티켓 목록")
        
        # 티켓을 상태별로 그룹화
        status_groups = {}
        for ticket in tickets:
            status = ticket.get('status', 'unknown')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(ticket)
        
        # 각 상태별로 티켓 표시
        for status, status_tickets in status_groups.items():
            with st.expander(f"📊 {status.upper()} ({len(status_tickets)}개)", expanded=True):
                for i, ticket in enumerate(status_tickets):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # 티켓 기본 정보
                        title = ticket.get('title', '제목 없음')
                        description = ticket.get('description', '설명 없음')
                        created_at = ticket.get('created_at', '날짜 없음')
                        
                        # 날짜 포맷팅
                        if isinstance(created_at, str):
                            try:
                                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                            except:
                                formatted_date = created_at
                        else:
                            formatted_date = str(created_at)
                        
                        st.write(f"**{title}**")
                        st.write(f"📅 {formatted_date}")
                        if description and len(description) > 100:
                            st.write(f"📝 {description[:100]}...")
                        elif description:
                            st.write(f"📝 {description}")
                    
                    with col2:
                        # 티켓 선택 버튼
                        if st.button(f"상세보기", key=f"view_{ticket.get('id', i)}"):
                            global selected_ticket
                            selected_ticket = ticket
                            st.rerun()
                    
                    st.divider()
    
    elif ui_mode == 'table':
        display_ticket_list(tickets)

def display_ticket_detail(ticket: Dict[str, Any]):
    """선택된 티켓의 상세 정보를 표시합니다."""
    if not ticket:
        st.warning("표시할 티켓이 선택되지 않았습니다.")
        return
    

    
    st.subheader("🎫 티켓 상세 정보")
    
    # 기본 정보 섹션
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**ID:** {ticket.get('id', 'N/A')}")
        st.write(f"**제목:** {ticket.get('title', '제목 없음')}")
        
        # 상태 변경 기능
        current_status = ticket.get('status', '상태 없음')
        status_options = ['new', 'pending', 'in_progress', 'resolved', 'closed']
        current_index = status_options.index(current_status) if current_status in status_options else 0

        new_status = st.selectbox(
            "**상태:**",
            status_options,
            index=current_index,
            key=f"status_{ticket.get('id')}"
        )

        # 상태가 변경되었는지 확인하고 업데이트
        if new_status != current_status:
            if update_ticket_status(ticket.get('id'), new_status):
                ticket['status'] = new_status
                st.success(f"상태가 '{new_status}'로 변경되었습니다!")
                st.rerun()
    
    with col2:
        created_at = ticket.get('created_at', '날짜 없음')
        if isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = created_at
        else:
            formatted_date = str(created_at)
        
        st.write(f"**생성일:** {formatted_date}")
        st.write(f"**우선순위:** {ticket.get('priority', '우선순위 없음')}")
        st.write(f"**담당자:** {ticket.get('assignee', '담당자 없음')}")
    
    # 설명 섹션
    st.subheader("📝 설명")
    
    # 설명 편집 기능
    col1, col2 = st.columns([3, 1])
    
    with col1:
        current_description = ticket.get('description', '')
        if current_description:
            edited_description = st.text_area(
                "설명 편집:",
                value=current_description,
                height=150,
                key=f"description_edit_{ticket.get('id')}"
            )
        else:
            edited_description = st.text_area(
                "설명 편집:",
                placeholder="설명을 입력하세요...",
                height=150,
                key=f"description_edit_{ticket.get('id')}"
            )
    
    with col2:
        st.write("")  # 공간 확보
        st.write("")  # 공간 확보
        if st.button("💾 저장", key=f"save_description_{ticket.get('id')}"):
            if edited_description != current_description:
                # description 업데이트 (SQLite 직접 업데이트)
                try:
                    import sqlite3
                    conn = sqlite3.connect('tickets.db')
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE tickets 
                        SET description = ?, updated_at = ?
                        WHERE id = ?
                    """, (edited_description, datetime.now().isoformat(), ticket.get('id')))
                    
                    conn.commit()
                    conn.close()
                    
                    st.success("✅ 설명이 업데이트되었습니다!")
                    logger.info(f"✅ 티켓 {ticket.get('id')} description 업데이트 완료")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 설명 업데이트 실패: {str(e)}")
                    logger.error(f"❌ 티켓 {ticket.get('id')} description 업데이트 실패: {str(e)}")
            else:
                st.info("ℹ️ 변경사항이 없습니다.")
    
    # 레이블 관리 섹션 - langchain_chatbot_app.py에서 직접 구현하므로 여기서는 제거
    # (기존 레이블 관리 기능은 langchain_chatbot_app.py의 "레이블 관리 (직접 구현)" 섹션에서 처리)
    
    # 메일 원문 보기 섹션
    st.subheader("📧 메일 원문")
    
    # Vector DB에서 메일 내용 조회
    try:
        vector_db = VectorDBManager()
        message_id = ticket.get('original_message_id') or ticket.get('message_id')
        
        st.write(f"🔍 **디버그 정보:**")
        st.write(f"   - 조회할 메일 ID: `{message_id}`")
        st.write(f"   - 티켓에서 가져온 original_message_id: `{ticket.get('original_message_id')}`")
        st.write(f"   - 티켓에서 가져온 message_id: `{ticket.get('message_id')}`")
        
        if message_id:
            st.write(f"   - VectorDB에서 메일 조회 시도...")
            mail = vector_db.get_mail_by_id(message_id)
            
            if mail:
                st.success(f"   ✅ VectorDB에서 메일 발견!")
                st.write(f"   - original_content 길이: {len(mail.original_content)}")
                st.write(f"   - extraction_method: {mail.extraction_method}")
            else:
                st.warning(f"   ⚠️ VectorDB에서 메일을 찾을 수 없습니다 (ID: {message_id})")
                st.info("🔄 Gmail API에서 직접 조회를 시도합니다...")
                
                try:
                    from unified_email_service import get_mail_content_by_id
                    from gmail_api_client import get_gmail_client
                    
                    # Gmail API에서 직접 조회
                    gmail_client = get_gmail_client()
                    if gmail_client and gmail_client.service:
                        st.write("   - Gmail API 클라이언트 연결 확인됨")
                        mail_detail = gmail_client.get_email_details(message_id)
                        if mail_detail:
                            st.success("✅ Gmail API에서 메일을 가져왔습니다!")
                            st.write(f"   - Gmail API에서 가져온 본문 길이: {len(mail_detail.get('body', ''))}")
                            
                            # 임시 메일 객체 생성
                            from vector_db_models import Mail
                            from datetime import datetime
                            
                            mail = Mail(
                                message_id=message_id,
                                original_content=mail_detail.get('body', ''),
                                refined_content=mail_detail.get('body', ''),
                                sender=mail_detail.get('from', ''),
                                status='retrieved_from_api',
                                subject=mail_detail.get('subject', ''),
                                received_datetime=mail_detail.get('received_date', datetime.now().isoformat()),
                                content_type='html',
                                has_attachment=mail_detail.get('has_attachments', False),
                                extraction_method='gmail_api_fallback',
                                content_summary='Gmail API에서 직접 조회',
                                key_points=[],
                                created_at=datetime.now().isoformat()
                            )
                        else:
                            st.error("❌ Gmail API에서도 메일을 찾을 수 없습니다.")
                    else:
                        st.error("❌ Gmail API 연결이 필요합니다.")
                        
                except Exception as api_error:
                    st.error(f"❌ Gmail API 조회 실패: {api_error}")
                    import traceback
                    st.code(traceback.format_exc())
            
            if mail:
                # 메일 정보 표시
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**발신자:** {mail.sender}")
                    st.write(f"**제목:** {mail.subject}")
                
                with col2:
                    st.write(f"**수신일:** {mail.received_datetime}")
                    st.write(f"**상태:** {mail.status}")
                
                # 메일 내용 표시
                st.subheader("📄 메일 내용")
                
                # 정제된 내용만 표시
                if mail.refined_content:
                    st.text_area("정제된 내용", mail.refined_content, height=300, disabled=True)
                else:
                    st.info("정제된 내용이 없습니다.")
                
                # 요약 및 핵심 포인트
                if mail.content_summary:
                    st.subheader("📋 요약")
                    st.write(mail.content_summary)
                
                # 첨부파일 표시 섹션
                if mail.has_attachment:
                    st.subheader("📎 첨부파일")
                    
                    # VectorDB에서 첨부파일 정보 조회
                    try:
                        attachment_chunks = vector_db.get_attachment_chunks_by_message_id(message_id)
                        if attachment_chunks:
                            display_vectordb_attachments(attachment_chunks)
                        else:
                            # VectorDB에 첨부파일 정보가 없으면 Gmail API로 조회
                            display_mail_attachments(message_id)
                    except Exception as e:
                        st.warning(f"VectorDB 첨부파일 조회 실패: {str(e)}")
                        # Gmail API로 대체 조회
                        display_mail_attachments(message_id)
                
                if mail.key_points:
                    st.subheader("🎯 핵심 포인트")
                    for point in mail.key_points:
                        st.write(f"• {point}")
            else:
                st.warning("메일을 찾을 수 없습니다.")
        else:
            st.warning("❌ 메일 ID가 없습니다.")
            st.write(f"   - ticket 전체 정보: {ticket}")
    except Exception as e:
        st.error(f"❌ 메일 로드 중 오류: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.write(f"   - 오류 발생 시점 ticket 정보: {ticket}")
        st.write(f"   - 메일 ID: {ticket.get('original_message_id') or ticket.get('message_id')}")
    
    # AI 추천 섹션
    st.subheader("🤖 AI 추천")
    
    # 고유한 키 생성 (타임스탬프 추가)
    ticket_id = ticket.get('id') or ticket.get('ticket_id') or 'unknown'
    timestamp = int(datetime.now().timestamp() * 1000)  # 밀리초 단위 타임스탬프
    ai_button_key = f"ai_recommend_{ticket_id}_{timestamp}_button"
    
    if st.button("AI 추천 생성", type="primary", key=ai_button_key):
        try:
            with st.spinner("🤖 AI 추천을 생성하고 있습니다..."):
                # AI 추천 생성
                from ticket_ai_recommender import get_ticket_ai_recommendation
                
                # 메일 내용 가져오기
                mail_content = ""
                message_id = ticket.get('original_message_id') or ticket.get('message_id')
                if message_id:
                    try:
                        vector_db = VectorDBManager()
                        mail = vector_db.get_mail_by_id(message_id)
                        if mail:
                            mail_content = mail.original_content or mail.refined_content or ""
                    except Exception as e:
                        st.warning(f"메일 내용 조회 실패: {str(e)}")
                
                # 티켓 히스토리 (간단한 형태)
                ticket_history = f"티켓 ID: {ticket.get('ticket_id')}, 상태: {ticket.get('status')}, 우선순위: {ticket.get('priority')}, 제목: {ticket.get('title')}"
                
                # AI 추천 생성
                recommendation_result = get_ticket_ai_recommendation(
                    ticket_description=ticket.get('description', ''),
                    mail_content=mail_content,
                    ticket_history=ticket_history
                )
                
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
            st.error(f"AI 추천 생성 중 오류가 발생했습니다: {str(e)}")
            st.info("💡 Azure OpenAI 설정을 확인해주세요.")
    
    # 뒤로가기 버튼
    if st.button("← 목록으로 돌아가기", key=f"back_{ticket.get('id')}"):
        clear_ticket_selection()
        st.rerun()


def display_ticket_list_with_sidebar(tickets: List[Dict[str, Any]], ui_mode: str = 'card'):
    """사이드바가 있는 티켓 목록 표시"""
    st.subheader("📋 티켓 목록")
    
    if not tickets:
        st.info("등록된 티켓이 없습니다.")
        return
    
    # UI 모드에 따른 표시
    if ui_mode == 'button_list':
        # 버튼 리스트 형태
        for i, ticket in enumerate(tickets):
            with st.container():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    title = ticket.get('title', '제목 없음')
                    status = ticket.get('status', '상태 없음')
                    priority = ticket.get('priority', '우선순위 없음')
                    created_at = ticket.get('created_at', '날짜 없음')
                    
                    st.write(f"**{title}**")
                    st.write(f"상태: {status} | 우선순위: {priority}")
                    st.write(f"생성일: {created_at}")
                
                with col2:
                    if st.button(f"상세보기", key=f"sidebar_detail_{i}_{ticket.get('id', 'unknown')}"):
                        global selected_ticket
                        selected_ticket = ticket
                        st.rerun()
    else:
        # 기본 카드 형태
        for i, ticket in enumerate(tickets):
            with st.container():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    title = ticket.get('title', '제목 없음')
                    status = ticket.get('status', '상태 없음')
                    priority = ticket.get('priority', '우선순위 없음')
                    created_at = ticket.get('created_at', '날짜 없음')
                    
                    st.write(f"**{title}**")
                    st.write(f"상태: {status} | 우선순위: {priority}")
                    st.write(f"생성일: {created_at}")
                
                with col2:
                    if st.button(f"상세보기", key=f"sidebar_detail_{i}_{ticket.get('id', 'unknown')}"):
                        global selected_ticket
                        selected_ticket = ticket
                        st.rerun()

def create_ticket_form():
    """새 티켓 생성을 위한 폼을 표시합니다."""
    st.subheader("➕ 새 티켓 생성")
    
    with st.form("create_ticket"):
        title = st.text_input("제목 *", placeholder="티켓 제목을 입력하세요")
        description = st.text_area("설명", placeholder="티켓에 대한 상세 설명을 입력하세요")
        status = st.selectbox("상태", ["open", "in_progress", "resolved", "closed"])
        priority = st.selectbox("우선순위", ["low", "medium", "high", "urgent"])
        assignee = st.text_input("담당자", placeholder="담당자 이름을 입력하세요")
        
        submitted = st.form_submit_button("티켓 생성")
        
        if submitted:
            if title:
                # 여기에 티켓 생성 로직 추가
                st.success("티켓이 생성되었습니다!")
                st.rerun()
                return {
                    'title': title,
                    'description': description,
                    'status': status,
                    'priority': priority,
                    'assignee': assignee
                }
            else:
                st.error("제목은 필수 입력 항목입니다.")
    
    return None

# 메인 앱
def main():
    st.title("🎫 Enhanced Ticket Management System")

    global selected_ticket

    # 티켓 목록 또는 상세 보기
    if selected_ticket:
        display_ticket_detail(selected_ticket)
    else:
        # 티켓 목록 로드 및 표시
        tickets = load_tickets()
        display_ticket_list(tickets)

if __name__ == "__main__":
    main()
