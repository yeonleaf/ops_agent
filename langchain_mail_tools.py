#!/usr/bin/env python3
"""
LangChain 툴로 구현한 메일 조회 시스템
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain.tools import tool
from simple_mail_processor import SimpleMailProcessor
from ticket_workflow_tools import TICKET_WORKFLOW_TOOLS

# 전역 메일 프로세서 인스턴스
mail_processor = SimpleMailProcessor()

@tool
def get_unread_emails(limit: int = 10) -> str:
    """
    안읽은 메일을 조회합니다.
    
    Args:
        limit: 조회할 메일 수 (기본값: 10, 최대: 50)
    
    Returns:
        안읽은 메일 목록 정보가 포함된 문자열
    """
    if limit > 50:
        limit = 50
    return mail_processor.get_unread_emails(limit=limit)

@tool
def get_all_emails(limit: int = 20) -> str:
    """
    전체 메일을 조회합니다.
    
    Args:
        limit: 조회할 메일 수 (기본값: 20, 최대: 100)
    
    Returns:
        전체 메일 목록 정보가 포함된 문자열
    """
    if limit > 100:
        limit = 100
    return mail_processor.get_all_emails(limit=limit)

@tool
def search_emails(query: str, limit: int = 15) -> str:
    """
    특정 키워드로 메일을 검색합니다.
    
    Args:
        query: 검색할 키워드나 문구
        limit: 조회할 메일 수 (기본값: 15, 최대: 50)
    
    Returns:
        검색된 메일 목록 정보가 포함된 문자열
    """
    if limit > 50:
        limit = 50
    return mail_processor.search_emails(query=query, limit=limit)

@tool
def get_emails_by_sender(sender: str, limit: int = 15) -> str:
    """
    특정 발신자의 메일을 조회합니다.
    
    Args:
        sender: 발신자 이름 또는 이메일 주소
        limit: 조회할 메일 수 (기본값: 15, 최대: 50)
    
    Returns:
        해당 발신자의 메일 목록 정보가 포함된 문자열
    """
    if limit > 50:
        limit = 50
    return mail_processor.get_emails_by_sender(sender=sender, limit=limit)

@tool
def get_mail_statistics() -> str:
    """
    메일 통계 정보를 조회합니다.
    
    Returns:
        전체 메일 수, 안읽은 메일 수 등의 통계 정보
    """
    try:
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
            
        total_emails = len(mail_data.get("value", []))
        unread_emails = sum(1 for email in mail_data.get("value", []) if not email.get("isRead", True))
        read_emails = total_emails - unread_emails
        
        # 발신자별 통계
        senders = {}
        for email in mail_data.get("value", []):
            sender_info = email.get("from", {}).get("emailAddress", {})
            sender_name = sender_info.get("name", "알 수 없음")
            senders[sender_name] = senders.get(sender_name, 0) + 1
        
        # 상위 5명 발신자
        top_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
        
        result = f"""📊 **메일 통계 정보**

📧 **전체 개요:**
- 총 메일 수: {total_emails}개
- 안읽은 메일: {unread_emails}개
- 읽은 메일: {read_emails}개
- 읽지 않은 비율: {(unread_emails/total_emails*100):.1f}%

👥 **주요 발신자 (상위 5명):**"""
        
        for i, (sender, count) in enumerate(top_senders, 1):
            result += f"\n{i}. {sender}: {count}개"
        
        return result
        
    except Exception as e:
        return f"❌ 통계 조회 중 오류 발생: {str(e)}"

# 기본 메일 조회 툴 목록
BASIC_MAIL_TOOLS = [
    get_unread_emails,
    get_all_emails, 
    search_emails,
    get_emails_by_sender,
    get_mail_statistics
]

# 모든 툴 통합 (기본 + 워크플로우)
AVAILABLE_TOOLS = BASIC_MAIL_TOOLS + TICKET_WORKFLOW_TOOLS

def get_tools_description() -> str:
    """사용 가능한 툴들의 설명을 반환"""
    return """
사용 가능한 메일 조회 툴들:

1. **get_unread_emails(limit=10)**: 안읽은 메일 조회
   - 사용 예: "안읽은 메일", "새 메일", "읽지 않은 메일"

2. **get_all_emails(limit=20)**: 전체 메일 조회  
   - 사용 예: "전체 메일", "모든 메일", "메일 전체"

3. **search_emails(query, limit=15)**: 키워드로 메일 검색
   - 사용 예: "회의 메일 찾아줘", "프로젝트 관련 메일"

4. **get_emails_by_sender(sender, limit=15)**: 특정 발신자 메일 조회
   - 사용 예: "Microsoft에서 온 메일", "홍길동이 보낸 메일"

5. **get_mail_statistics()**: 메일 통계 정보 조회
   - 사용 예: "메일 통계", "메일 현황", "메일 요약"
"""

# 테스트 함수
def test_tools():
    """툴들이 제대로 작동하는지 테스트"""
    print("=== LangChain 툴 테스트 ===\n")
    
    print("1. 안읽은 메일 테스트:")
    print(get_unread_emails.invoke({"limit": 3}))
    print("\n" + "="*50 + "\n")
    
    print("2. 전체 메일 테스트:")
    print(get_all_emails.invoke({"limit": 5}))
    print("\n" + "="*50 + "\n")
    
    print("3. 메일 검색 테스트:")
    print(search_emails.invoke({"query": "tasks", "limit": 3}))
    print("\n" + "="*50 + "\n")
    
    print("4. 발신자별 메일 테스트:")
    print(get_emails_by_sender.invoke({"sender": "Microsoft", "limit": 3}))
    print("\n" + "="*50 + "\n")
    
    print("5. 메일 통계 테스트:")
    print(get_mail_statistics.invoke({}))

if __name__ == "__main__":
    test_tools()