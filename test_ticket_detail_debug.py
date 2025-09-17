#!/usr/bin/env python3
"""
티켓 상세보기 디버깅 테스트
상세보기 버튼 클릭 시 로그가 제대로 출력되는지 확인
"""

import streamlit as st
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    st.title("🔍 티켓 상세보기 디버깅 테스트")

    # 세션 상태 확인
    if 'test_selected' not in st.session_state:
        st.session_state.test_selected = None

    st.write("## 현재 세션 상태:")
    st.write(f"- test_selected: {st.session_state.test_selected}")
    st.write(f"- selected_ticket: {getattr(st.session_state, 'selected_ticket', '없음')}")

    # 테스트 버튼
    if st.button("테스트 버튼 1"):
        print("🔥 테스트 버튼 1 클릭됨!")
        st.session_state.test_selected = "버튼1"
        st.success("버튼 1이 클릭되었습니다!")
        print(f"✅ 세션 상태 업데이트: {st.session_state.test_selected}")
        st.rerun()

    if st.button("테스트 버튼 2"):
        print("🔥 테스트 버튼 2 클릭됨!")
        st.session_state.test_selected = "버튼2"
        st.success("버튼 2가 클릭되었습니다!")
        print(f"✅ 세션 상태 업데이트: {st.session_state.test_selected}")
        st.rerun()

    if st.button("초기화"):
        print("🔄 초기화 버튼 클릭됨!")
        st.session_state.test_selected = None
        st.success("상태가 초기화되었습니다!")
        print("✅ 세션 상태 초기화됨")
        st.rerun()

    # 선택된 상태에 따라 다른 내용 표시
    if st.session_state.test_selected:
        st.write(f"## 선택된 항목: {st.session_state.test_selected}")
        print(f"📄 상세 내용 표시 중: {st.session_state.test_selected}")

        if st.session_state.test_selected == "버튼1":
            st.info("버튼 1의 상세 정보입니다.")
        elif st.session_state.test_selected == "버튼2":
            st.info("버튼 2의 상세 정보입니다.")
    else:
        st.write("## 아무것도 선택되지 않음")
        print("📋 기본 목록 표시 중")

    # 실제 티켓 UI 테스트
    st.write("---")
    st.write("## 실제 티켓 UI 테스트")

    if st.button("티켓 UI 불러오기"):
        try:
            print("🎫 티켓 UI 모듈 import 시도...")
            from enhanced_ticket_ui_v2 import main as ticket_main
            print("✅ 티켓 UI 모듈 import 성공")

            # 티켓 DB에서 데이터 로드 테스트
            try:
                from sqlite_ticket_models import SQLiteTicketManager
                ticket_manager = SQLiteTicketManager()
                tickets = ticket_manager.get_all_tickets()
                st.write(f"📊 DB에서 로드된 티켓 수: {len(tickets)}")
                print(f"📊 DB에서 로드된 티켓 수: {len(tickets)}")

                if tickets:
                    first_ticket = tickets[0]
                    st.write(f"첫 번째 티켓: #{first_ticket.ticket_id} - {first_ticket.title}")
                    print(f"첫 번째 티켓: #{first_ticket.ticket_id} - {first_ticket.title}")

                    # 세션 상태에 직접 설정해보기
                    if st.button("첫 번째 티켓 선택"):
                        print(f"🎯 첫 번째 티켓 선택: #{first_ticket.ticket_id}")
                        st.session_state.selected_ticket = first_ticket
                        print(f"✅ selected_ticket 설정 완료")
                        st.rerun()
                else:
                    st.warning("DB에 티켓이 없습니다.")

            except Exception as db_error:
                st.error(f"DB 연결 오류: {db_error}")
                print(f"❌ DB 연결 오류: {db_error}")

        except Exception as import_error:
            st.error(f"모듈 import 오류: {import_error}")
            print(f"❌ 모듈 import 오류: {import_error}")

if __name__ == "__main__":
    main()