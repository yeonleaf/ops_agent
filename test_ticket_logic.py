#!/usr/bin/env python3
"""
티켓 생성 로직 테스트 스크립트
"""

import streamlit as st
from integrated_mail_classifier import IntegratedMailClassifier, TicketCreationStatus

def test_ticket_logic():
    """티켓 생성 로직 테스트"""
    st.title("🧪 티켓 생성 로직 테스트")
    
    # 분류기 초기화
    classifier = IntegratedMailClassifier(use_lm=False)
    
    # 테스트 쿼리들
    test_queries = [
        "안 읽은 메일 10개만 찾아줘",
        "티켓으로 변환할 메일을 보여줘",
        "일감으로 변환해줘",
        "프로젝트 관련 티켓 생성",
        "업무 관련 메일만 보여줘",
        "긴급하고 중요한 메일만 보여줘"
    ]
    
    # 테스트 메일 데이터
    test_email = {
        'id': 'test_email_001',
        'subject': '테스트 메일 제목',
        'body': '이것은 테스트 메일의 본문입니다.',
        'sender': 'test@example.com'
    }
    
    st.subheader("📝 테스트 쿼리별 티켓 생성 여부")
    
    for query in test_queries:
        st.markdown("---")
        st.write(f"**쿼리**: {query}")
        
        # 티켓 생성 여부 판단
        status, reason, details = classifier.should_create_ticket(test_email, query)
        
        # 결과 표시
        if status == TicketCreationStatus.SHOULD_CREATE:
            st.success(f"✅ 티켓 생성: {reason}")
        elif status == TicketCreationStatus.ALREADY_EXISTS:
            st.warning(f"⚠️ 기존 티켓: {reason}")
        else:
            st.info(f"ℹ️ 티켓 생성 불필요: {reason}")
        
        # 상세 정보
        if details:
            st.json(details)
    
    st.markdown("---")
    st.subheader("🔍 티켓 키워드 목록")
    st.write("다음 키워드가 포함된 쿼리만 티켓을 생성합니다:")
    
    ticket_keywords = [
        "티켓", "일감", "일", "작업", "할일", "task", "ticket", "work", "job",
        "프로젝트", "project", "이슈", "issue", "버그", "bug", "요청", "request",
        "승인", "approve", "검토", "review", "피드백", "feedback"
    ]
    
    # 키워드를 그리드 형태로 표시
    cols = st.columns(4)
    for i, keyword in enumerate(ticket_keywords):
        with cols[i % 4]:
            st.code(keyword)

if __name__ == "__main__":
    test_ticket_logic() 