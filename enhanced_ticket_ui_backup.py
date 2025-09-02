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

# 페이지 설정
st.set_page_config(
    page_title="Enhanced Ticket Management",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 디버깅을 위한 테스트 섹션
st.sidebar.subheader("🔍 디버깅 테스트")

# add_label_to_ticket 함수를 전역 스코프에 먼저 정의
def add_label_to_ticket(ticket_id: int, new_label: str):
    """티켓에 새 레이블을 추가합니다."""
    print(f"🔍 add_label_to_ticket 함수 정의됨 - 전역 스코프에서 접근 가능")
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

# add_label_to_ticket 함수를 전역 스코프에 명시적으로 등록
def test_add_label_function():
    """테스트용 레이블 추가 함수"""
    st.sidebar.write("🔍 add_label_to_ticket 함수 테스트 시작...")
    
    # 1. globals() 확인
    st.sidebar.write(f"🔍 globals()에 있는 함수들: {[k for k in globals().keys() if callable(globals()[k]) and 'label' in k.lower()]}")
    
    # 2. locals() 확인
    st.sidebar.write(f"🔍 locals()에 있는 함수들: {[k for k in locals().keys() if callable(locals()[k]) and 'label' in k.lower()]}")
    
    # 3. 함수 객체 직접 확인
    try:
        if 'add_label_to_ticket' in globals():
            st.sidebar.write("✅ add_label_to_ticket 함수가 globals()에 있습니다.")
            func = globals()['add_label_to_ticket']
            st.sidebar.write(f"🔍 함수 타입: {type(func)}")
            st.sidebar.write(f"🔍 함수 이름: {func.__name__}")
            
            # 함수를 직접 호출해보기
            from sqlite_ticket_models import SQLiteTicketManager
            ticket_manager = SQLiteTicketManager()
            
            # 티켓 4에 테스트 레이블 추가
            test_result = func(4, "테스트레이블")
            st.sidebar.write(f"🔍 함수 실행 결과: {test_result}")
            
        elif 'add_label_to_ticket' in locals():
            st.sidebar.write("✅ add_label_to_ticket 함수가 locals()에 있습니다.")
            func = locals()['add_label_to_ticket']
            test_result = func(4, "테스트레이블")
            st.sidebar.write(f"🔍 함수 실행 결과: {test_result}")
            
        else:
            st.sidebar.write("❌ add_label_to_ticket 함수를 찾을 수 없습니다.")
            
            # 4. 함수를 직접 정의해보기
            st.sidebar.write("🔍 함수를 직접 정의해보겠습니다...")
            def temp_add_label(ticket_id: int, new_label: str):
                st.sidebar.write(f"🔍 임시 함수 호출: ticket_id={ticket_id}, new_label={new_label}")
                return True
            
            test_result = temp_add_label(4, "테스트레이블")
            st.sidebar.write(f"🔍 임시 함수 실행 결과: {test_result}")
            
    except Exception as e:
        st.sidebar.error(f"❌ 오류 발생: {str(e)}")
        import traceback
        st.sidebar.error(f"오류 상세: {traceback.format_exc()}")

if st.sidebar.button("레이블 추가 함수 테스트"):
    test_add_label_function()
    """티켓에 새 레이블을 추가합니다."""
    print(f"🔍 add_label_to_ticket 함수 정의됨 - 전역 스코프에서 접근 가능")
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

# 세션 상태 초기화
if 'tickets' not in st.session_state:
    st.session_state.tickets = []
if 'selected_ticket' not in st.session_state:
    st.session_state.selected_ticket = None
if 'ui_mode' not in st.session_state:
    st.session_state.ui_mode = 'card'
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0
if 'ai_recommendations' not in st.session_state:
    st.session_state.ai_recommendations = []

def load_tickets():
    """데이터베이스에서 티켓을 로드합니다."""
    try:
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
        
        # 세션 상태 업데이트로 새로고침 대신 처리
        st.session_state.refresh_trigger += 1
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

# 중복된 add_label_to_ticket 함수 정의 제거됨 - 전역 스코프에 이미 정의되어 있음

def clear_ticket_selection():
    """선택된 티켓을 초기화합니다."""
    st.session_state.selected_ticket = None

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
            index=0 if st.session_state.ui_mode == 'card' else 1,
            key="ui_mode_selector"
        )
        st.session_state.ui_mode = ui_mode
    
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
                    # 티켓 선택 버튼 - session state로 상태 관리
                    if st.button(f"상세보기", key=f"view_{ticket.get('id', i)}"):
                        st.session_state.selected_ticket = ticket
                        st.session_state.refresh_trigger += 1
                
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
                            st.session_state.selected_ticket = ticket
                            st.session_state.refresh_trigger += 1
                    
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
        
        # 상태 변경 기능 - session state로 상태 관리
        current_status = ticket.get('status', '상태 없음')
        status_key = f"status_{ticket.get('id')}"
        
        if status_key not in st.session_state:
            st.session_state[status_key] = current_status
        
        new_status = st.selectbox(
            "**상태:**", 
            ['new', 'pending', 'in_progress', 'resolved', 'closed'],
            index=['new', 'pending', 'in_progress', 'resolved', 'closed'].index(st.session_state[status_key]) if st.session_state[status_key] in ['new', 'pending', 'in_progress', 'resolved', 'closed'] else 0,
            key=status_key
        )
        
        # 상태가 변경되었는지 확인하고 업데이트
        if new_status != st.session_state[status_key]:
            if update_ticket_status(ticket.get('id'), new_status):
                st.session_state[status_key] = new_status
                ticket['status'] = new_status
                st.success(f"상태가 '{new_status}'로 변경되었습니다!")
    
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
    description = ticket.get('description', '설명이 없습니다.')
    st.write(description)
    
    # 레이블 관리 섹션
    st.subheader("🏷️ 레이블 관리")
    
    # RDB에서 현재 레이블 가져오기
    current_labels = []
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        ticket_id = ticket.get('id') or ticket.get('ticket_id')
        
        if ticket_id:
            current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
            if current_ticket and current_ticket.labels:
                current_labels = current_labels = current_ticket.labels
    except Exception as e:
        st.warning(f"레이블 로드 실패: {str(e)}")
    
    # 기존 레이블 표시 및 삭제
    if current_labels:
        st.write("**현재 레이블:**")
        for idx, label in enumerate(current_labels):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"🏷️ {label}")
            with col2:
                # 고유한 키 생성
                current_ticket_id = ticket.get('id') or ticket.get('ticket_id')
                safe_label = label.replace(' ', '_').replace('-', '_').replace('_', '')
                button_key = f"delete_{safe_label}_{current_ticket_id}_{idx}"
                
                if st.button(f"삭제", key=button_key):
                    # ticket_id가 유효한지 확인
                    if not current_ticket_id:
                        st.error("유효하지 않은 티켓 ID입니다")
                        return
                    
                    # 정수로 변환
                    try:
                        actual_ticket_id = int(current_ticket_id)
                    except (ValueError, TypeError):
                        st.error(f"유효하지 않은 티켓 ID: {current_ticket_id}")
                        return
                    
                    # 삭제 실행
                    success = delete_label_from_ticket(actual_ticket_id, label)
                    if success:
                        st.success(f"레이블 '{label}' 삭제 완료!")
                        # 사용자에게 새로고침 안내
                        st.info("변경사항을 확인하려면 상세보기를 다시 클릭하세요.")
                    else:
                        st.error("레이블 삭제 실패")
    else:
        st.info("설정된 레이블이 없습니다")
    
    # 새 레이블 추가
    with st.expander("➕ 새 레이블 추가", expanded=False):
        # 고유한 키 생성 (타임스탬프 추가)
        current_ticket_id = ticket.get('id') or ticket.get('ticket_id')
        timestamp = int(datetime.now().timestamp() * 1000)  # 밀리초 단위 타임스탬프
        text_input_key = f"new_label_{current_ticket_id}_{timestamp}_input"
        add_button_key = f"add_label_{current_ticket_id}_{timestamp}_button"
        
        new_label = st.text_input("새 레이블", placeholder="새로운 레이블을 입력하세요", key=text_input_key)
        if st.button("레이블 추가", key=add_button_key):
            st.write(f"🔍 버튼 클릭됨! 입력된 레이블: '{new_label}'")
            
            if new_label and new_label.strip():
                st.write(f"🔍 레이블 유효성 검사 통과: '{new_label.strip()}'")
                
                # ticket_id가 유효한지 확인
                if not current_ticket_id:
                    st.error("유효하지 않은 티켓 ID입니다")
                    st.write(f"🔍 current_ticket_id: {current_ticket_id}")
                    return
                
                st.write(f"🔍 current_ticket_id: {current_ticket_id}")
                
                # 정수로 변환
                try:
                    actual_ticket_id = int(current_ticket_id)
                    st.write(f"🔍 변환된 ticket_id: {actual_ticket_id}")
                except (ValueError, TypeError):
                    st.error(f"유효하지 않은 티켓 ID: {current_ticket_id}")
                    return
                
                # 추가 실행
                st.write(f"🔍 add_label_to_ticket 함수 호출 시작...")
                success = add_label_to_ticket(actual_ticket_id, new_label.strip())
                st.write(f"🔍 add_label_to_ticket 함수 실행 결과: {success}")
                
                if success:
                    st.success(f"레이블 '{new_label.strip()}' 추가 완료!")
                    # 사용자에게 새로고침 안내
                    st.info("변경사항을 확인하려면 상세보기를 다시 클릭하세요.")
                else:
                    st.error("레이블 추가 실패")
            else:
                st.warning("레이블을 입력해주세요")
                st.write(f"🔍 입력된 레이블이 유효하지 않음: '{new_label}'")
    
    # 메일 원문 보기 섹션
    st.subheader("📧 메일 원문")
    
    # Vector DB에서 메일 내용 조회
    try:
        vector_db = VectorDBManager()
        message_id = ticket.get('original_message_id') or ticket.get('message_id')
        
        if message_id:
            mail = vector_db.get_mail_by_id(message_id)
            
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
                
                # 탭으로 원본/정제된 내용 구분
                tab1, tab2 = st.tabs(["📝 정제된 내용", "📄 원본 내용"])
                
                with tab1:
                    if mail.refined_content:
                        st.text_area("정제된 내용", mail.refined_content, height=300, disabled=True)
                    else:
                        st.info("정제된 내용이 없습니다.")
                
                with tab2:
                    if mail.original_content:
                        st.text_area("원본 내용", mail.original_content, height=300, disabled=True)
                    else:
                        st.info("원본 내용이 없습니다.")
                
                # 요약 및 핵심 포인트
                if mail.content_summary:
                    st.subheader("📋 요약")
                    st.write(mail.content_summary)
                
                if mail.key_points:
                    st.subheader("🎯 핵심 포인트")
                    for point in mail.key_points:
                        st.write(f"• {point}")
            else:
                st.warning("메일을 찾을 수 없습니다.")
        else:
            st.warning("메일 ID가 없습니다.")
    except Exception as e:
        st.error(f"메일 로드 중 오류: {str(e)}")
    
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
                from vector_db_models import AIRecommendationEngine
                
                # 메일 내용 가져오기
                mail_content = ""
                if st.session_state.selected_ticket:
                    message_id = st.session_state.selected_ticket.get('original_message_id') or st.session_state.selected_ticket.get('message_id')
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
                
                # AI 추천 엔진 실행
                ai_engine = AIRecommendationEngine()
                recommendation = ai_engine.generate_solution_recommendation(mail_content, ticket_history)
                
                # AI 추천 결과를 session state에 저장
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.ai_recommendations.append({
                    'timestamp': timestamp,
                    'recommendation': recommendation,
                    'ticket_id': ticket.get('id')
                })
                
                st.success("✅ AI 추천이 생성되었습니다!")
                st.markdown("---")
                st.subheader("🤖 AI 추천 해결방법")
                st.markdown(recommendation)
                
        except Exception as e:
            st.error(f"AI 추천 생성 중 오류가 발생했습니다: {str(e)}")
            st.info("💡 Azure OpenAI 설정을 확인해주세요.")
    
    # AI 추천 히스토리 표시
    st.markdown("---")
    display_ai_recommendations(ticket.get('id'))
    
    # 뒤로가기 버튼
    if st.button("← 목록으로 돌아가기", key=f"back_{ticket.get('id')}"):
        clear_ticket_selection()
        st.session_state.refresh_trigger += 1

def display_ai_recommendations(ticket_id: int):
    """AI 추천 히스토리를 표시합니다."""
    if 'ai_recommendations' in st.session_state and st.session_state.ai_recommendations:
        # 현재 티켓의 AI 추천만 필터링
        ticket_recommendations = [rec for rec in st.session_state.ai_recommendations if rec.get('ticket_id') == ticket_id]
        
        if ticket_recommendations:
            st.subheader("🤖 AI 추천 히스토리")
            
            for rec in reversed(ticket_recommendations):
                with st.expander(f"📅 {rec['timestamp']}", expanded=False):
                    st.write(rec['recommendation'])
                    st.divider()

# 호환성을 위한 함수들
def add_ai_recommendation_to_history(recommendation: str):
    """AI 추천을 히스토리에 추가합니다."""
    if 'ai_recommendations' not in st.session_state:
        st.session_state.ai_recommendations = []
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    st.session_state.ai_recommendations.append({
        'timestamp': timestamp,
        'recommendation': recommendation
    })

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
                st.session_state.refresh_trigger += 1
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
    
    # 사이드바
    with st.sidebar:
        st.header("🔧 설정")
        
        # 새로고침 버튼
        if st.button("🔄 데이터 새로고침"):
            st.session_state.refresh_trigger += 1
        
        st.divider()
        
        # 새 티켓 생성
        if st.button("➕ 새 티켓 생성"):
            st.session_state.show_create_form = True
    
    # 메인 컨텐츠
    if st.session_state.get('show_create_form', False):
        create_ticket_form()
        if st.button("← 목록으로 돌아가기"):
            st.session_state.show_create_form = False
            st.session_state.refresh_trigger += 1
    else:
        # 티켓 목록 또는 상세 보기
        if st.session_state.selected_ticket:
            display_ticket_detail(st.session_state.selected_ticket)
        else:
            # refresh_trigger가 변경되면 티켓 목록 다시 로드
            tickets = load_tickets()
            st.session_state.tickets = tickets
            display_ticket_list(tickets)

if __name__ == "__main__":
    main()
