#!/usr/bin/env python3
"""
티켓 UI 테스트 파일
"""

import streamlit as st
from enhanced_ticket_ui import (
    is_ticket_response, 
    extract_ticket_data_from_response, 
    display_ticket_list_with_sidebar
)

# 페이지 설정
st.set_page_config(
    page_title="🎫 티켓 UI 테스트",
    page_icon="🎫",
    layout="wide"
)

st.title("🎫 향상된 티켓 UI 테스트")
st.markdown("**새로운 기능:** 메일 제목만 보이는 간단한 버튼 + 클릭 시 상세정보 표시")

# 테스트용 JSON 데이터
test_response = '''{
  "summary": {
    "total_unread_emails": 10,
    "new_tickets_created": 0,
    "existing_tickets_found": 5,
    "total_tasks": 5
  },
  "tasks": [
    {
      "type": "existing_ticket",
      "ticket_id": 1,
      "message_id": "AAMkADY1YmE3N2FhLWEwMzQtNDNkMC04Mzg3LTczMTdiMjk2NzRhMABGAAAAAADfsy0XtCMZS5XonZkyBLu6BwDUwywT0x3WRJXfefGC8Xz-AAAAAAEMAADUwywT0x3WRJXfefGC8Xz-AAAvREoQAAA=",
      "title": "You have upcoming tasks due",
      "status": "closed",
      "priority": "High",
      "created_at": "2025-08-17T16:42:04.266353",
      "action": "조회됨",
      "content": "안녕하세요, 오늘 처리해야 할 작업들이 있습니다: 1. 서버 모니터링 점검 2. 데이터베이스 백업 3. 보안 업데이트 모든 작업을 완료해주세요. 감사합니다."
    },
    {
      "type": "existing_ticket",
      "ticket_id": 3,
      "message_id": "AAMkADY1YmE3N2FhLWEwMzQtNDNkMC04Mzg3LTczMTdiMjk2NzRhMABGAAAAAADfsy0XtCMZS5XonZkyBLu6BwDUwywT0x3WRJXfefGC8Xz-AAAAAAEMAADUwywT0x3WRJXfefGC8Xz-AAAvREoPAAA=",
      "title": "Test Email",
      "status": "new",
      "priority": "Medium",
      "created_at": "2025-08-17T21:31:26.213080",
      "action": "조회됨",
      "content": "이것은 테스트 메일입니다. 새로운 기능 테스트를 위해 발송되었습니다. - 기능: 사용자 인증 - 상태: 테스트 중 - 담당자: 개발팀 테스트 결과를 확인해주세요."
    },
    {
      "type": "existing_ticket",
      "ticket_id": 4,
      "message_id": "AAMkADY1YmE3N2FhLWEwMzQtNDNkMC04Mzg3LTczMTdiMjk2NzRhMABGAAAAAADfsy0XtCMZS5XonZkyBLu6BwDUwywT0x3WRJXfefGC8Xz-AAAAAAEMAADUwywT0x3WRJXfefGC8Xz-AAAsxV9FAAA=",
      "title": "You have late tasks",
      "status": "new",
      "priority": "High",
      "created_at": "2025-08-18T16:27:38.757287",
      "action": "조회됨",
      "content": "긴급: 지연된 작업 알림 다음 작업들이 예정된 시간을 초과했습니다: 🚨 고객 문의 응답 (2일 지연) 🚨 시스템 점검 보고서 (1일 지연) 🚨 월간 통계 작성 (3일 지연) 즉시 처리해주시기 바랍니다."
    },
    {
      "type": "existing_ticket",
      "ticket_id": 2,
      "message_id": "AAMkADY1YmE3N2FhLWEwMzQtNDNkMC04Mzg3LTczMTdiMjk2NzRhMABGAAAAAADfsy0XtCMZS5XonZkyBLu6BwDUwywT0x3WRJXfefGC8Xz-AAAAAAEMAADUwywT0x3WRJXfefGC8Xz-AAAss2kTAAA=",
      "title": "",
      "status": "new",
      "priority": "Medium",
      "created_at": "2025-08-17T16:42:55.884472",
      "action": "조회됨",
      "content": "제목 없는 메일입니다. 내용: 시스템 자동 생성된 알림 - 유형: 시스템 모니터링 - 중요도: 보통 - 생성 시간: 2025-08-17 16:42"
    },
    {
      "type": "existing_ticket",
      "ticket_id": 5,
      "message_id": "AAMkADY1YmE3N2FhLWEwMzQtNDNkMC04Mzg3LTczMTdiMjk2NzRhMABGAAAAAADfsy0XtCMZS5XonZkyBLu6BwDUwywT0x3WRJXfefGC8Xz-AAAAAAEMAADUwywT0x3WRJXfefGC8Xz-AAAss2kSAAA=",
      "title": "You have late tasks",
      "status": "new",
      "priority": "High",
      "created_at": "2025-08-18T16:27:38.768136",
      "action": "조회됨",
      "content": "지연 작업 추가 알림 추가로 지연된 작업이 발견되었습니다: ⚠️ 코드 리뷰 (1일 지연) ⚠️ 테스트 케이스 작성 (2일 지연) ⚠️ 문서 업데이트 (1일 지연) 팀 리더에게 보고하고 우선순위를 조정해주세요."
    }
  ],
  "message": "오늘 처리해야 할 작업 5개가 준비되었습니다."
}'''

# 테스트 결과 표시
st.subheader("🔍 테스트 결과")

# 1. 티켓 응답인지 확인
is_ticket = is_ticket_response(test_response)
st.write(f"**티켓 응답인가?** {'✅ 예' if is_ticket else '❌ 아니오'}")

# 2. 티켓 데이터 추출
ticket_data = extract_ticket_data_from_response(test_response)
if ticket_data:
    st.write(f"**데이터 추출 성공:** ✅")
    st.write(f"**추출된 티켓 수:** {len(ticket_data.get('tickets', []))}")
else:
    st.write("**데이터 추출 실패:** ❌")

# 3. 원본 JSON 표시
with st.expander("📄 원본 JSON 데이터"):
    st.json(test_response)

# 4. 추출된 데이터 표시
if ticket_data:
    with st.expander("🔧 추출된 티켓 데이터"):
        st.json(ticket_data)

# 5. 티켓 UI 표시
if ticket_data:
    st.markdown("---")
    st.subheader("🎨 실제 티켓 UI")
    display_ticket_list_with_sidebar(ticket_data, "테스트 티켓 목록")
else:
    st.error("티켓 데이터를 추출할 수 없어 UI를 표시할 수 없습니다.") 