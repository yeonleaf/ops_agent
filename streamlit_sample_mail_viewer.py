#!/usr/bin/env python3
"""
샘플 메일 데이터를 사용한 티켓 생성 Streamlit 앱
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
from database_models import DatabaseManager, MailParser, Mail
from enhanced_content_extractor import EnhancedContentExtractor

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

# 페이지 설정
st.set_page_config(
    page_title="📧 Sample Mail Ticket Creator",
    page_icon="📧",
    layout="wide"
)

@st.cache_data
def load_sample_mail_data():
    """샘플 메일 데이터 파일 로드"""
    try:
        with open('sample_mail_response.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ sample_mail_response.json 파일을 찾을 수 없습니다.")
        return {"value": []}

def main():
    st.title("📧 샘플 메일 데이터로 티켓 생성하기")
    
    # 데이터베이스 초기화
    db_manager = DatabaseManager()
    mail_parser = MailParser()
    
    # 사이드바
    st.sidebar.header("📋 메뉴")
    menu = st.sidebar.radio(
        "작업 선택",
        ["샘플 메일 보기", "티켓 생성", "생성된 티켓 조회"]
    )
    
    if menu == "샘플 메일 보기":
        st.header("📬 샘플 메일 데이터")
        
        sample_data = load_sample_mail_data()
        
        for idx, mail_data in enumerate(sample_data["value"]):
            with st.expander(f"📧 메일 {idx + 1}: {mail_data['subject']}"):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    sender_info = mail_data.get("from", mail_data.get("sender", {})).get("emailAddress", {})
                    st.write("**발신자:**", sender_info.get("name", "알 수 없음"))
                    st.write("**이메일:**", sender_info.get("address", ""))
                    st.write("**수신시간:**", mail_data.get("receivedDateTime", ""))
                    st.write("**첨부파일:**", "있음" if mail_data.get("hasAttachments", False) else "없음")
                    st.write("**중요도:**", mail_data.get("importance", "normal"))
                
                with col2:
                    st.write("**내용:**")
                    content = mail_data["body"]["content"]
                    if mail_data["body"]["contentType"] == "html":
                        # HTML 태그 제거하여 표시
                        import re
                        clean_content = re.sub('<.*?>', '', content)
                        st.text_area("", clean_content, height=150, key=f"content_{idx}")
                    else:
                        st.text_area("", content, height=150, key=f"content_{idx}")
    
    elif menu == "티켓 생성":
        st.header("🎫 샘플 메일에서 티켓 생성")
        
        sample_data = load_sample_mail_data()
        
        # 메일 선택
        mail_options = [f"메일 {i+1}: {mail['subject']}" for i, mail in enumerate(sample_data["value"])]
        selected_mail_idx = st.selectbox("티켓으로 만들 메일 선택:", range(len(mail_options)), format_func=lambda x: mail_options[x])
        
        selected_mail = sample_data["value"][selected_mail_idx]
        
        st.subheader("선택된 메일 정보")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**제목:**", selected_mail["subject"])
            sender_info = selected_mail.get("from", selected_mail.get("sender", {})).get("emailAddress", {})
            st.write("**발신자:**", sender_info.get("name", "알 수 없음"))
            st.write("**이메일:**", sender_info.get("address", ""))
        
        with col2:
            st.write("**수신시간:**", selected_mail.get("receivedDateTime", ""))
            st.write("**첨부파일:**", "있음" if selected_mail.get("hasAttachments", False) else "없음")
            st.write("**중요도:**", selected_mail.get("importance", "normal"))
        
        # 메일 내용 표시
        st.write("**메일 내용:**")
        content = selected_mail["body"]["content"]
        if selected_mail["body"]["contentType"] == "html":
            import re
            clean_content = re.sub('<.*?>', '', content)
            st.text_area("", clean_content, height=150)
        else:
            st.text_area("", content, height=150)
        
        # 티켓 생성 버튼
        if st.button("🎫 티켓 생성", type="primary"):
            try:
                # 메일 파싱
                mail = mail_parser.parse_mail_to_json(selected_mail)
                
                # 티켓 생성
                ticket = mail_parser.create_ticket_from_mail(mail)
                
                # 메일과 티켓 저장
                result = mail_parser.save_mail_and_ticket(mail, ticket)
                ticket_id = result['ticket_id']
                
                st.success(f"✅ 티켓이 성공적으로 생성되었습니다! (ID: {ticket_id})")
                
                # 생성된 티켓 정보 표시
                st.subheader("생성된 티켓 정보")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**티켓 ID:**", ticket_id)
                    st.write("**상태:**", ticket.status)
                    st.write("**우선순위:**", ticket.priority)
                    st.write("**타입:**", ticket.ticket_type)
                
                with col2:
                    st.write("**담당자:**", ticket.reporter)
                    st.write("**이메일:**", ticket.reporter_email)
                    st.write("**생성시간:**", ticket.created_at)
                    st.write("**라벨:**", ", ".join(ticket.labels))
                
            except Exception as e:
                st.error(f"❌ 티켓 생성 중 오류가 발생했습니다: {str(e)}")
    
    elif menu == "생성된 티켓 조회":
        st.header("📋 생성된 티켓 목록")
        
        # 모든 티켓 조회
        tickets = db_manager.get_all_tickets()
        
        if not tickets:
            st.info("생성된 티켓이 없습니다. '티켓 생성' 메뉴에서 티켓을 생성해보세요.")
        else:
            # 티켓 데이터프레임 생성
            ticket_data = []
            for ticket in tickets:
                ticket_data.append({
                    "ID": ticket.ticket_id,
                    "제목": ticket.title,
                    "상태": ticket.status,
                    "우선순위": ticket.priority,
                    "타입": ticket.ticket_type,
                    "담당자": ticket.reporter,
                    "생성일": ticket.created_at[:10]  # 날짜만 표시
                })
            
            df = pd.DataFrame(ticket_data)
            st.dataframe(df, use_container_width=True)
            
            # 개별 티켓 상세 정보
            st.subheader("티켓 상세 정보")
            selected_ticket_id = st.selectbox("상세 보기할 티켓 선택:", [t.ticket_id for t in tickets])
            
            selected_ticket = next(t for t in tickets if t.ticket_id == selected_ticket_id)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**ID:**", selected_ticket.ticket_id)
                st.write("**제목:**", selected_ticket.title)
                st.write("**상태:**", selected_ticket.status)
                st.write("**우선순위:**", selected_ticket.priority)
                st.write("**타입:**", selected_ticket.ticket_type)
            
            with col2:
                st.write("**담당자:**", selected_ticket.reporter)
                st.write("**이메일:**", selected_ticket.reporter_email)
                st.write("**생성일:**", selected_ticket.created_at)
                st.write("**수정일:**", selected_ticket.updated_at)
                st.write("**라벨:**", ", ".join(selected_ticket.labels))
            
            st.write("**설명:**")
            st.text_area("", selected_ticket.description, height=200, disabled=True)
            
            # 티켓 상태 업데이트
            st.subheader("티켓 상태 변경")
            new_status = st.selectbox(
                "새 상태 선택:",
                ["new", "in_progress", "resolved", "closed"],
                index=["new", "in_progress", "resolved", "closed"].index(selected_ticket.status)
            )
            
                            if st.button("상태 업데이트") and new_status != selected_ticket.status:
                    try:
                        db_manager.update_ticket_status(selected_ticket.ticket_id, new_status, selected_ticket.status)
                        st.success(f"✅ 티켓 상태가 '{new_status}'로 업데이트되었습니다!")
                        st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
                    except Exception as e:
                        st.error(f"❌ 상태 업데이트 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()