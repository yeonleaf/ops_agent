#!/usr/bin/env python3
"""
업무용이 아닌 메일 표시 및 정정 기능 UI 모듈
AI가 업무 관련이 아니라고 판단한 메일들을 confidence score 순으로 표시하고
정정 버튼을 통해 티켓으로 변환할 수 있는 기능을 제공합니다.
"""

import streamlit as st
import json
from typing import List, Dict, Any
from datetime import datetime

def display_non_work_emails(non_work_emails: List[Dict[str, Any]]) -> None:
    """
    업무용이 아닌 메일들을 표시하고 정정 기능을 제공합니다.

    Args:
        non_work_emails: AI가 업무용이 아니라고 판단한 메일 목록
    """
    # 이미 티켓이 생성된 메일은 목록에서 제외
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        existing_tickets = ticket_manager.get_all_tickets()
        existing_message_ids = set()
        for t in existing_tickets:
            try:
                if getattr(t, 'original_message_id', None):
                    existing_message_ids.add(t.original_message_id)
                if getattr(t, 'message_id', None):
                    existing_message_ids.add(t.message_id)
            except Exception:
                pass
        non_work_emails = [e for e in non_work_emails if e.get('id') not in existing_message_ids]
    except Exception:
        # 조회 실패 시 필터링 없이 진행
        pass

    if not non_work_emails:
        st.info("📧 현재 업무용이 아니라고 분류된 메일이 없습니다.")
        return

    # confidence score 순으로 정렬 (높은 순)
    sorted_emails = sorted(non_work_emails, key=lambda x: x.get('confidence', 0), reverse=True)

    # 상위 10개만 표시
    display_emails = sorted_emails[:10]

    st.subheader("📧 업무용으로 분류되지 않은 메일")
    st.info(f"AI가 업무용이 아니라고 판단한 메일들입니다 (상위 {len(display_emails)}개). 티켓으로 변환이 필요한 메일이 있다면 '정정' 버튼을 클릭하세요.")

    for i, email in enumerate(display_emails):
        with st.container():
            # 3열 레이아웃: 메일 정보 | 미리보기 | 정정 버튼
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                # 메일 제목과 기본 정보
                st.markdown(f"**{email.get('subject', 'No Subject')}**")
                st.markdown(f"📧 {email.get('sender', 'Unknown')}")

                # AI 분류 이유
                reason = email.get('reason', '분류 이유 없음')
                confidence = email.get('confidence', 0)
                st.markdown(f"💡 **AI 판단**: {reason}")
                st.markdown(f"🎯 **신뢰도**: {confidence:.2%}")

            with col2:
                # 메일 내용 미리보기
                body = email.get('body', '')
                body_preview = body[:100] + "..." if len(body) > 100 else body
                st.markdown(f"<small><em>{body_preview}</em></small>", unsafe_allow_html=True)

                # 날짜와 추가 정보
                received_date = email.get('received_date', '')
                if received_date:
                    try:
                        date_obj = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                        date_str = date_obj.strftime("%m/%d %H:%M")
                    except:
                        date_str = received_date
                    st.markdown(f"<small>📅 {date_str}</small>", unsafe_allow_html=True)

                # 우선순위와 제안된 레이블
                priority = email.get('priority', 'Low')
                suggested_labels = email.get('suggested_labels', [])
                if suggested_labels:
                    labels_str = ', '.join(suggested_labels[:2])  # 최대 2개만
                    st.markdown(f"<small>🏷️ {labels_str}</small>", unsafe_allow_html=True)

            with col3:
                # 정정 버튼
                email_id = email.get('id', f'email_{i}')
                button_key = f"correct_{email_id}_{i}"

                if st.button("정정", key=button_key, use_container_width=True, type="primary"):
                    # 정정 버튼 클릭 시 처리
                    handle_email_correction(email, i)

            # 구분선
            st.markdown("---")

def handle_email_correction(email: Dict[str, Any], index: int) -> None:
    """
    정정 버튼 클릭 시 메일을 티켓으로 변환하고 mem0에 기록합니다.

    Args:
        email: 정정할 메일 데이터
        index: 메일 인덱스
    """
    with st.spinner(f"티켓 생성 중... ({email.get('subject', 'No Subject')})"):
        try:
            # create_ticket_from_single_email 함수 호출
            from unified_email_service import create_ticket_from_single_email

            # 이메일 데이터를 티켓 생성 함수에 전달할 형태로 변환
            email_data = {
                'id': email.get('id'),
                'subject': email.get('subject'),
                'sender': email.get('sender'),
                'body': email.get('body'),
                'received_date': email.get('received_date'),
                'priority': email.get('priority', 'Medium'),
                'suggested_labels': email.get('suggested_labels', []),
                'ticket_type': email.get('ticket_type', 'Task')
            }

            # 세션 상태에서 OAuth 토큰 가져오기
            access_token = st.session_state.get('gmail_access_token', '')

            # 티켓 생성 실행 (OAuth 토큰 포함, 정정 플래그 설정)
            result = create_ticket_from_single_email(
                email_data, 
                access_token=access_token,
                force_create=True,
                correction_reason="사용자 요청으로 정정 생성"
            )

            if result.get('success'):
                ticket_id = result.get('ticket_id')
                st.success(f"✅ 티켓이 성공적으로 생성되었습니다!")
                st.info(f"🎫 티켓 ID: {ticket_id}")

                # Mem0에 사용자 정정 이벤트 기록
                record_user_correction_to_mem0(email, ticket_id)

                # 세션 상태 업데이트를 위한 플래그 설정
                st.session_state.email_corrected = True
                st.session_state.last_corrected_email = email.get('id')

                # 자동 새로고침 (3초 후)
                st.markdown("""
                <script>
                setTimeout(function() {
                    window.location.reload();
                }, 3000);
                </script>
                """, unsafe_allow_html=True)

                st.info("🔄 3초 후 자동으로 새로고침됩니다...")

            else:
                error_msg = result.get('error', '알 수 없는 오류')
                st.error(f"❌ 티켓 생성 실패: {error_msg}")

        except ImportError:
            st.error("❌ 티켓 생성 함수를 찾을 수 없습니다. 백엔드 설정을 확인해주세요.")
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

def record_user_correction_to_mem0(email: Dict[str, Any], ticket_id: str) -> None:
    """
    사용자 정정 이벤트를 Mem0에 기록합니다.

    Args:
        email: 정정된 메일 데이터
        ticket_id: 생성된 티켓 ID
    """
    try:
        from mem0_memory_adapter import create_mem0_memory, add_ticket_event

        # Mem0 메모리 인스턴스 생성
        mem0_memory = create_mem0_memory(llm_client=None, user_id="ticket_ui")

        # 사용자 정정 이벤트 기록
        event_description = f"User Correction: AI가 '업무용이 아님'으로 분류한 메일 '{email.get('subject')}' (발신자: {email.get('sender')})를 사용자가 '업무용'으로 정정하여 티켓 {ticket_id} 생성함."

        memory_id = add_ticket_event(
            memory=mem0_memory,
            event_type="user_correction",
            description=event_description,
            ticket_id=ticket_id,
            message_id=email.get('id'),
            old_value="non_work_related",
            new_value="work_related"
        )

        st.success(f"🧠 Mem0에 학습 데이터가 기록되었습니다 (Memory ID: {memory_id})")

    except Exception as e:
        st.warning(f"⚠️ Mem0 기록 실패 (티켓은 정상 생성됨): {str(e)}")

def display_correction_stats() -> None:
    """정정 통계 정보를 표시합니다."""
    if hasattr(st.session_state, 'email_corrected') and st.session_state.email_corrected:
        st.info("✅ 최근에 메일 정정이 수행되었습니다. 새로고침하여 최신 상태를 확인하세요.")

# 사용 예시 함수
def test_non_work_emails_ui():
    """테스트용 함수"""
    # 테스트 데이터
    test_emails = [
        {
            'id': 'test_001',
            'subject': '쇼핑몰 할인 이벤트 안내',
            'sender': 'promotion@shop.com',
            'body': '특별 할인 이벤트가 시작되었습니다. 지금 바로 확인해보세요!',
            'received_date': '2025-09-18T10:30:00',
            'confidence': 0.95,
            'reason': '광고성 메일로 판단됨',
            'priority': 'Low',
            'suggested_labels': ['광고', '쇼핑'],
            'ticket_type': 'Task'
        },
        {
            'id': 'test_002',
            'subject': '점심 약속 변경',
            'sender': 'friend@personal.com',
            'body': '오늘 점심 약속을 2시로 변경할 수 있을까요?',
            'received_date': '2025-09-18T11:00:00',
            'confidence': 0.88,
            'reason': '개인적인 약속 관련 메일',
            'priority': 'Low',
            'suggested_labels': ['개인', '약속'],
            'ticket_type': 'Task'
        }
    ]

    display_non_work_emails(test_emails)

if __name__ == "__main__":
    st.set_page_config(
        page_title="업무용이 아닌 메일 UI 테스트",
        page_icon="📧",
        layout="wide"
    )

    st.title("📧 업무용이 아닌 메일 UI 테스트")
    test_non_work_emails_ui()