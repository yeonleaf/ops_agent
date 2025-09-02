#!/usr/bin/env python3
"""Streamlit 환경에서 레이블 추가 테스트"""

import streamlit as st
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_label_add_ui():
    """Streamlit UI에서 레이블 추가를 테스트합니다."""
    
    st.title("🔍 레이블 추가 테스트")
    
    # 테스트할 티켓 ID 선택
    ticket_id = st.selectbox(
        "테스트할 티켓 ID 선택",
        [1, 2, 3, 4],
        index=3  # 기본값: 티켓 4
    )
    
    st.write(f"**선택된 티켓 ID:** {ticket_id}")
    
    # 현재 티켓 정보 표시
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
        
        if current_ticket:
            st.write(f"**제목:** {current_ticket.title}")
            st.write(f"**현재 레이블:** {current_ticket.labels}")
            st.write(f"**업데이트 시간:** {current_ticket.updated_at}")
        else:
            st.error("티켓을 찾을 수 없습니다.")
            return
            
    except Exception as e:
        st.error(f"티켓 조회 실패: {str(e)}")
        return
    
    # 레이블 추가 테스트
    st.subheader("➕ 새 레이블 추가")
    
    new_label = st.text_input("새 레이블", placeholder="새로운 레이블을 입력하세요", key="test_new_label")
    
    if st.button("레이블 추가 테스트", type="primary"):
        if new_label and new_label.strip():
            try:
                from enhanced_ticket_ui import add_label_to_ticket
                
                st.info("레이블 추가 중...")
                
                # 레이블 추가 실행
                success = add_label_to_ticket(ticket_id, new_label.strip())
                
                if success:
                    st.success(f"✅ 레이블 '{new_label.strip()}' 추가 완료!")
                    
                    # 추가 후 상태 확인
                    updated_ticket = ticket_manager.get_ticket_by_id(ticket_id)
                    if updated_ticket:
                        st.write(f"**업데이트된 레이블:** {updated_ticket.labels}")
                        st.write(f"**새로운 업데이트 시간:** {updated_ticket.updated_at}")
                        
                        if new_label.strip() in updated_ticket.labels:
                            st.success("🎉 레이블 추가가 성공적으로 반영되었습니다!")
                        else:
                            st.error("❌ 레이블이 제대로 추가되지 않았습니다.")
                    else:
                        st.error("❌ 업데이트된 티켓을 찾을 수 없습니다.")
                        
                else:
                    st.error("❌ 레이블 추가 실패")
                    
            except Exception as e:
                st.error(f"❌ 오류 발생: {str(e)}")
                import traceback
                st.error(f"오류 상세: {traceback.format_exc()}")
        else:
            st.warning("레이블을 입력해주세요.")
    
    # 현재 모든 티켓의 레이블 상태 표시
    st.subheader("📋 모든 티켓 레이블 상태")
    
    try:
        all_tickets = ticket_manager.get_all_tickets()
        
        for ticket in all_tickets:
            with st.expander(f"티켓 {ticket.ticket_id}: {ticket.title}"):
                st.write(f"**레이블:** {ticket.labels}")
                st.write(f"**업데이트:** {ticket.updated_at}")
                
    except Exception as e:
        st.error(f"전체 티켓 조회 실패: {str(e)}")

if __name__ == "__main__":
    test_label_add_ui()
