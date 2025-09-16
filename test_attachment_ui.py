#!/usr/bin/env python3
"""
첨부파일 UI 기능 테스트
"""

import streamlit as st
from enhanced_ticket_ui import display_mail_attachments, display_vectordb_attachments
from vector_db_models import VectorDBManager, AttachmentChunk
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="첨부파일 UI 테스트",
    page_icon="📎",
    layout="wide"
)

def main():
    st.title("📎 첨부파일 UI 테스트")
    
    st.subheader("1. VectorDB 첨부파일 조회 테스트")
    
    # VectorDB에서 첨부파일 조회 테스트
    try:
        vector_db = VectorDBManager()
        
        # 테스트용 첨부파일 청크 생성
        test_chunk = AttachmentChunk(
            chunk_id="test_chunk_1",
            ticket_id="test_ticket_1",
            file_id="test_file_1",
            original_filename="test_document.pdf",
            mime_type="application/pdf",
            chunk_index=0,
            content="This is a test document content.",
            file_size=1024,
            analysis_summary="테스트 문서입니다.",
            keywords=["테스트", "문서", "PDF"],
            file_category="문서",
            business_relevance="높음",
            created_at=datetime.now().isoformat()
        )
        
        # 첨부파일 표시 테스트
        st.write("**테스트 첨부파일 정보:**")
        display_vectordb_attachments([test_chunk])
        
    except Exception as e:
        st.error(f"VectorDB 테스트 중 오류: {str(e)}")
    
    st.subheader("2. Gmail API 첨부파일 조회 테스트")
    
    # Gmail API 테스트 (실제 메시지 ID가 필요한 경우)
    test_message_id = st.text_input("테스트할 Gmail 메시지 ID 입력:", value="")
    
    if st.button("Gmail 첨부파일 조회 테스트") and test_message_id:
        try:
            display_mail_attachments(test_message_id)
        except Exception as e:
            st.error(f"Gmail API 테스트 중 오류: {str(e)}")
    
    st.subheader("3. 기능 설명")
    st.markdown("""
    ### 구현된 기능:
    
    1. **VectorDB 첨부파일 표시**:
       - VectorDB에 저장된 첨부파일 정보를 조회하여 표시
       - 파일명, 타입, 크기, 카테고리, 업무 관련성, 키워드 등 표시
       - 텍스트 파일의 경우 내용 미리보기 제공
    
    2. **Gmail API 첨부파일 조회**:
       - Gmail API를 통해 실제 첨부파일 정보 조회
       - 첨부파일 다운로드 기능
       - 텍스트 파일 미리보기 기능
    
    3. **티켓 상세보기 통합**:
       - 티켓 상세보기에서 메일 원문 조회 시 첨부파일도 함께 표시
       - VectorDB 우선 조회, 실패 시 Gmail API 대체 조회
    """)

if __name__ == "__main__":
    main()
