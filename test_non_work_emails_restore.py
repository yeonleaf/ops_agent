#!/usr/bin/env python3
"""
업무용이 아닌 메일 UI 복원 테스트
정정 버튼과 Mem0 기록 기능이 제대로 작동하는지 테스트합니다.
"""

import streamlit as st
from datetime import datetime
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_data():
    """테스트용 non_work_emails 데이터 생성"""
    return [
        {
            'id': 'test_email_001',
            'subject': '주말 특가 세일 이벤트 안내',
            'sender': 'marketing@onlineshop.com',
            'body': '주말 특가 이벤트가 시작되었습니다! 최대 70% 할인된 가격으로 다양한 상품을 만나보세요. 이 기회를 놓치지 마세요!',
            'received_date': '2025-09-18T09:30:00',
            'confidence': 0.95,
            'reason': '광고/마케팅 메일로 판단됨',
            'priority': 'Low',
            'suggested_labels': ['광고', '세일', '마케팅'],
            'ticket_type': 'Task'
        },
        {
            'id': 'test_email_002',
            'subject': '카페 모임 시간 변경',
            'sender': 'friend@personal.com',
            'body': '안녕하세요! 이번 주 카페 모임 시간을 3시에서 4시로 변경하려고 합니다. 괜찮으시다면 답변 부탁드려요.',
            'received_date': '2025-09-18T10:15:00',
            'confidence': 0.89,
            'reason': '개인적인 약속 관련 메일',
            'priority': 'Low',
            'suggested_labels': ['개인', '약속', '모임'],
            'ticket_type': 'Task'
        },
        {
            'id': 'test_email_003',
            'subject': '시스템 점검 안내',
            'sender': 'system@company.com',
            'body': '시스템 정기 점검으로 인해 내일 오후 2시부터 4시까지 서비스 이용이 제한됩니다.',
            'received_date': '2025-09-18T11:00:00',
            'confidence': 0.82,
            'reason': '시스템 안내 메일로 분류됨',
            'priority': 'Medium',
            'suggested_labels': ['시스템', '점검', '안내'],
            'ticket_type': 'Task'
        },
        {
            'id': 'test_email_004',
            'subject': '뉴스레터 구독 확인',
            'sender': 'newsletter@techblog.com',
            'body': '테크 블로그 뉴스레터 구독을 확인해주세요. 매주 최신 기술 동향을 전해드립니다.',
            'received_date': '2025-09-18T11:30:00',
            'confidence': 0.78,
            'reason': '뉴스레터 관련 메일',
            'priority': 'Low',
            'suggested_labels': ['뉴스레터', '구독', '기술'],
            'ticket_type': 'Task'
        },
        {
            'id': 'test_email_005',
            'subject': '서버 오류 보고',
            'sender': 'monitoring@company.com',
            'body': '웹 서버에서 503 에러가 발생하고 있습니다. 즉시 확인이 필요합니다.',
            'received_date': '2025-09-18T12:00:00',
            'confidence': 0.75,
            'reason': '모니터링 알림이지만 자동화된 메일로 판단',
            'priority': 'High',
            'suggested_labels': ['서버', '오류', '긴급'],
            'ticket_type': 'Bug'
        }
    ]

def test_ui():
    """UI 테스트 함수"""
    st.title("🧪 업무용이 아닌 메일 UI 복원 테스트")

    st.markdown("""
    ## 테스트 목적
    - AI가 업무 관련이 아니라고 판단한 메일들을 confidence score 순으로 표시
    - 정정 버튼 클릭 시 티켓 생성 및 Mem0 기록 기능 테스트
    - Human-in-the-loop 학습 시스템 동작 확인
    """)

    # 테스트 데이터 생성
    test_emails = create_test_data()

    st.markdown("---")
    st.subheader("📊 테스트 데이터 정보")
    st.info(f"총 {len(test_emails)}개의 테스트 메일을 생성했습니다.")

    # 간단한 통계
    col1, col2, col3 = st.columns(3)
    with col1:
        avg_confidence = sum(email['confidence'] for email in test_emails) / len(test_emails)
        st.metric("평균 신뢰도", f"{avg_confidence:.2%}")

    with col2:
        high_conf_count = sum(1 for email in test_emails if email['confidence'] > 0.8)
        st.metric("고신뢰도 메일", f"{high_conf_count}개")

    with col3:
        priority_high = sum(1 for email in test_emails if email['priority'] == 'High')
        st.metric("높은 우선순위", f"{priority_high}개")

    st.markdown("---")

    # 실제 UI 컴포넌트 테스트
    try:
        from non_work_emails_ui import display_non_work_emails
        st.subheader("🎯 실제 UI 컴포넌트 테스트")
        display_non_work_emails(test_emails)

        st.success("✅ UI 컴포넌트가 성공적으로 로드되었습니다!")

    except ImportError as e:
        st.error(f"❌ UI 모듈 임포트 실패: {e}")
        st.code("pip install streamlit")

    except Exception as e:
        st.error(f"❌ UI 렌더링 오류: {e}")
        st.exception(e)

    st.markdown("---")

    # 기능 설명
    st.subheader("🚀 복원된 기능들")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### ✨ 주요 기능
        - **신뢰도 순 정렬**: confidence score가 높은 순으로 표시
        - **상위 10개 제한**: 너무 많은 메일 방지
        - **직관적인 레이아웃**: 3열 구조로 정보 정리
        - **정정 버튼**: 한 번의 클릭으로 티켓 변환
        """)

    with col2:
        st.markdown("""
        ### 🧠 학습 시스템
        - **Mem0 기록**: 사용자 정정 이벤트 자동 저장
        - **컨텍스트 보존**: 메일 ID, 티켓 ID 연결
        - **학습 데이터**: 향후 AI 분류 개선에 활용
        - **실시간 업데이트**: 정정 후 자동 새로고침
        """)

    st.markdown("---")

    # 기술적 구현 세부사항
    with st.expander("🔧 기술적 구현 세부사항"):
        st.markdown("""
        ### 파일 구조
        - `non_work_emails_ui.py`: 새로 생성된 UI 모듈
        - `langchain_chatbot_app.py`: 메인 앱에 통합
        - `fastmcp_chatbot_app.py`: FastMCP 앱에 통합

        ### 주요 함수들
        - `display_non_work_emails()`: 메일 목록 표시
        - `handle_email_correction()`: 정정 버튼 처리
        - `record_user_correction_to_mem0()`: Mem0 기록
        - `create_ticket_from_single_email()`: 티켓 생성 (기존)

        ### 데이터 플로우
        ```
        사용자 클릭 → 티켓 생성 → Mem0 기록 → 세션 업데이트 → 자동 새로고침
        ```
        """)

    # 테스트 로그
    if st.button("🧪 백엔드 연결 테스트"):
        st.subheader("🔍 백엔드 연결 테스트")

        # 1. unified_email_service 테스트
        try:
            from unified_email_service import create_ticket_from_single_email
            st.success("✅ unified_email_service.create_ticket_from_single_email 임포트 성공")
        except ImportError:
            st.error("❌ unified_email_service 모듈 임포트 실패")

        # 2. mem0_memory_adapter 테스트
        try:
            from mem0_memory_adapter import create_mem0_memory, add_ticket_event
            st.success("✅ mem0_memory_adapter 임포트 성공")
        except ImportError:
            st.error("❌ mem0_memory_adapter 모듈 임포트 실패")

        # 3. 환경 변수 확인
        import os
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")

        if azure_endpoint and azure_key:
            st.success("✅ Azure OpenAI 환경 변수 설정됨")
        else:
            st.warning("⚠️ Azure OpenAI 환경 변수 미설정")

if __name__ == "__main__":
    st.set_page_config(
        page_title="업무용이 아닌 메일 UI 복원 테스트",
        page_icon="🧪",
        layout="wide"
    )

    test_ui()