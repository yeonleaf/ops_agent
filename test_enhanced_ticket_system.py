#!/usr/bin/env python3
"""
향상된 티켓 시스템 테스트
새로 추가된 non_work_emails 기능과 정정 버튼 기능을 테스트합니다.
"""

import streamlit as st
import json
from datetime import datetime

def test_enhanced_ticket_data_structure():
    """향상된 티켓 데이터 구조를 테스트합니다."""
    st.header("🧪 향상된 티켓 시스템 테스트")
    
    # 테스트용 데이터 생성
    test_data = {
        'display_mode': 'tickets',
        'tickets': [
            {
                'ticket_id': 'T20250825123456',
                'title': '서버 장애 보고',
                'status': 'new',
                'type': 'incident',
                'priority': 'High',
                'reporter': '김철수',
                'description': '프로덕션 서버에서 500 에러가 발생하고 있습니다.',
                'sender': 'kim@company.com',
                'created_at': datetime.now().isoformat(),
                'action': '메일 수신'
            },
            {
                'ticket_id': 'T20250825123457',
                'title': '새 기능 요청',
                'status': 'in_progress',
                'type': 'feature',
                'priority': 'Medium',
                'reporter': '이영희',
                'description': '사용자 대시보드에 차트 기능을 추가해주세요.',
                'sender': 'lee@company.com',
                'created_at': datetime.now().isoformat(),
                'action': '메일 수신'
            }
        ],
        'non_work_emails': [
            {
                'id': 'email_001',
                'subject': '주말 휴무 안내',
                'sender': 'HR 담당자',
                'body': '주말 휴무 기간 동안 고객 문의는 월요일 오전 9시부터 접수해주세요. 긴급한 경우에는 당직자에게 연락해주시기 바랍니다.',
                'received_date': datetime.now().isoformat(),
                'is_read': True,
                'priority': 'Normal',
                'classification_reason': '휴무 관련 공지사항으로 업무 액션 불필요'
            },
            {
                'id': 'email_002',
                'subject': '오프라인 교육 일정',
                'sender': '교육 담당자',
                'body': '오프라인 교육 일정이 변경되었습니다. 9월 15일에서 9월 20일로 연기되었으니 참고해주세요.',
                'received_date': datetime.now().isoformat(),
                'is_read': False,
                'priority': 'Normal',
                'classification_reason': '교육 관련 정보 공유로 즉시 액션 불필요'
            },
            {
                'id': 'email_003',
                'subject': '개인 안부 인사',
                'sender': '동료',
                'body': '오랜만입니다. 잘 지내시나요? 요즘 날씨가 많이 더운데 건강에 유의하세요.',
                'received_date': datetime.now().isoformat(),
                'is_read': True,
                'priority': 'Normal',
                'classification_reason': '개인적인 안부 인사로 업무와 무관'
            },
            {
                'id': 'email_004',
                'subject': '회사 동호회 모임 안내',
                'sender': '동호회장',
                'body': '이번 주 토요일 오후 2시에 회사 근처 카페에서 동호회 모임이 있습니다. 참석 가능하신 분들은 회신 부탁드립니다.',
                'received_date': datetime.now().isoformat(),
                'is_read': False,
                'priority': 'Normal',
                'classification_reason': '동호회 활동 관련으로 업무와 직접적 연관 없음'
            },
            {
                'id': 'email_005',
                'subject': '뉴스레터 구독 안내',
                'sender': '마케팅팀',
                'body': '업계 최신 동향과 회사 소식을 받아보실 수 있는 뉴스레터 구독을 안내드립니다. 구독을 원하시는 분들은 링크를 클릭해주세요.',
                'received_date': datetime.now().isoformat(),
                'is_read': True,
                'priority': 'Normal',
                'classification_reason': '마케팅 뉴스레터로 즉시 액션 불필요'
            }
        ],
        'new_tickets_created': 2,
        'existing_tickets_found': 0,
        'summary': {'total_tasks': 2}
    }
    
    # 데이터 구조 표시
    st.subheader("📊 테스트 데이터 구조")
    st.json(test_data)
    
    # 통계 정보 확인
    st.subheader("📈 데이터 통계")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("새로 생성된 티켓", test_data.get('new_tickets_created', 0))
    with col2:
        st.metric("기존 티켓", test_data.get('existing_tickets_found', 0))
    with col3:
        st.metric("총 티켓", len(test_data.get('tickets', [])))
    with col4:
        st.metric("업무용 아님", len(test_data.get('non_work_emails', [])))
    
    # 티켓 목록 표시
    st.subheader("🎫 티켓 목록")
    for i, ticket in enumerate(test_data['tickets']):
        with st.expander(f"티켓 {i+1}: {ticket['title']}", expanded=False):
            st.write(f"**ID:** {ticket['ticket_id']}")
            st.write(f"**상태:** {ticket['status']}")
            st.write(f"**우선순위:** {ticket['priority']}")
            st.write(f"**발신자:** {ticket['sender']}")
            st.write(f"**설명:** {ticket['description']}")
    
    # 업무용이 아닌 메일 목록 표시
    st.subheader("📧 업무용으로 분류되지 않은 메일")
    st.info("AI가 업무용이 아니라고 판단한 메일들입니다. 티켓으로 변환이 필요한 메일이 있다면 '정정' 버튼을 클릭하세요.")
    
    for i, email in enumerate(test_data['non_work_emails']):
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{email['subject']}**")
                st.markdown(f"📧 {email['sender']}")
                st.markdown(f"💡 {email['classification_reason']}")
            
            with col2:
                body_preview = email['body'][:50] + "..." if len(email['body']) > 50 else email['body']
                st.markdown(f"<small>{body_preview}</small>", unsafe_allow_html=True)
                
                read_status = "✅ 읽음" if email['is_read'] else "📬 안읽음"
                st.markdown(f"<small>{read_status}</small>", unsafe_allow_html=True)
            
            with col3:
                # 정정 버튼 (실제로는 백엔드 함수를 호출)
                if st.button("정정", key=f"test_correct_{i}", use_container_width=True, type="primary"):
                    st.success(f"✅ '{email['subject']}' 메일이 티켓으로 변환되었습니다!")
                    st.info("실제 환경에서는 이 메일이 non_work_emails에서 제거되고 tickets에 추가됩니다.")
            
            st.markdown("---")
    
    # 기능 설명
    st.markdown("---")
    st.subheader("🚀 새로 추가된 기능")
    st.markdown("""
    ### 1. 이중 분류 시스템
    - **tickets**: AI가 '업무용'으로 판단하여 티켓으로 생성한 메일들
    - **non_work_emails**: AI가 '업무용이 아님'으로 판단한 메일들
    
    ### 2. 정정(Correct) 기능
    - 사용자가 AI의 분류 결과를 직접 수정 가능
    - '업무용이 아님'으로 분류된 메일을 '업무용'으로 재분류
    - 버튼 클릭 한 번으로 즉시 티켓 생성 프로세스 실행
    
    ### 3. 실시간 업데이트
    - 정정 버튼 클릭 후 화면 자동 새로고침
    - 새로 생성된 티켓이 상단 티켓 목록에 즉시 표시
    - 정정된 메일은 non_work_emails에서 제거
    """)

def test_backend_functions():
    """백엔드 함수들을 테스트합니다."""
    st.header("🔧 백엔드 함수 테스트")
    
    # create_ticket_from_single_email 함수 테스트
    st.subheader("테스트: create_ticket_from_single_email")
    
    test_email = {
        'id': 'test_email_001',
        'subject': '테스트 메일 - 티켓 변환',
        'sender': 'test@company.com',
        'body': '이것은 테스트를 위한 메일입니다. 티켓으로 변환되어야 합니다.',
        'received_date': datetime.now().isoformat(),
        'is_read': False,
        'priority': 'Normal'
    }
    
    st.write("**테스트 메일 데이터:**")
    st.json(test_email)
    
    if st.button("백엔드 함수 호출 테스트", type="primary"):
        try:
            # 실제 백엔드 함수 호출 (환경에 따라 실패할 수 있음)
            from unified_email_service import create_ticket_from_single_email
            st.success("✅ 백엔드 함수 임포트 성공!")
            st.info("실제 티켓 생성을 위해서는 Gmail API 인증과 Azure OpenAI 설정이 필요합니다.")
        except ImportError as e:
            st.error(f"❌ 백엔드 함수 임포트 실패: {str(e)}")
        except Exception as e:
            st.error(f"❌ 기타 오류: {str(e)}")

if __name__ == "__main__":
    st.set_page_config(
        page_title="향상된 티켓 시스템 테스트",
        page_icon="🧪",
        layout="wide"
    )
    
    # 테스트 실행
    test_enhanced_ticket_data_structure()
    st.markdown("---")
    test_backend_functions() 