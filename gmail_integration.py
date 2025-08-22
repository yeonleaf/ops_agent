#!/usr/bin/env python3
"""
Gmail 연동을 위한 모듈
실제 Gmail에서 메일을 가져와서 티켓 데이터로 변환
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import streamlit as st

# 실제 Gmail API 클라이언트
from gmail_api_client import get_gmail_client

class GmailTicketFetcher:
    """Gmail에서 티켓 관련 메일을 가져오는 클래스"""
    
    def __init__(self):
        self.server_name = "gmail"
        self.is_connected = False
    
    async def connect(self):
        """Gmail MCP 서버에 연결"""
        try:
            # 실제 구현에서는 mcp-agent 사용
            # async with gen_client(self.server_name) as client:
            #     self.client = client
            #     self.is_connected = True
            
            # 임시로 연결 성공 상태만 표시
            self.is_connected = True
            return True
        except Exception as e:
            st.error(f"Gmail 연결 실패: {str(e)}")
            return False
    
    async def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        """안읽은 메일 가져오기"""
        try:
            # 실제 Gmail API 클라이언트 사용
            gmail_client = get_gmail_client()
            emails = gmail_client.get_unread_emails(max_results=50)
            
            if emails:
                self.is_connected = True
                return emails
            else:
                st.warning("Gmail에서 안읽은 메일을 찾을 수 없습니다.")
                return []
            
        except Exception as e:
            st.error(f"메일 가져오기 실패: {str(e)}")
            # 에러 발생 시 샘플 데이터 반환 (개발용)
            return self.get_sample_emails()
    
    async def fetch_ticket_emails(self) -> List[Dict[str, Any]]:
        """티켓 관련 메일만 가져오기"""
        emails = await self.fetch_unread_emails()
        return [email for email in emails if self.is_ticket_email(email)]
    
    def is_ticket_email(self, email: Dict[str, Any]) -> bool:
        """티켓 관련 메일인지 판단"""
        subject = email.get("subject", "").lower()
        keywords = [
            "ticket", "issue", "bug", "request", "support", 
            "urgent", "error", "problem", "help", "assistance",
            "티켓", "이슈", "버그", "요청", "지원", "긴급", "오류", "문제"
        ]
        return any(keyword in subject for keyword in keywords)
    
    def get_sample_emails(self) -> List[Dict[str, Any]]:
        """임시 샘플 메일 데이터 (실제 구현 전까지 사용)"""
        return [
            {
                "id": "msg_001",
                "subject": "서버 장애 보고 - 긴급",
                "from": "system@company.com",
                "to": "admin@company.com",
                "date": "2025-01-20T10:30:00Z",
                "body": "프로덕션 서버에서 지속적으로 500 에러가 발생하고 있습니다. 긴급 조치가 필요합니다.",
                "labels": ["urgent", "system"],
                "unread": True
            },
            {
                "id": "msg_002", 
                "subject": "새 기능 요청 - 사용자 대시보드",
                "from": "product@company.com",
                "to": "dev@company.com",
                "date": "2025-01-19T14:20:00Z",
                "body": "사용자 대시보드에 차트 기능을 추가해주세요. 매출 추이와 사용자 활동 분석이 필요합니다.",
                "labels": ["feature", "enhancement"],
                "unread": True
            },
            {
                "id": "msg_003",
                "subject": "고객 문의 응답 지연 - 2일",
                "from": "support@company.com", 
                "to": "team@company.com",
                "date": "2025-01-18T09:15:00Z",
                "body": "고객 문의가 예정된 시간을 2일 초과했습니다. 즉시 처리해주세요.",
                "labels": ["support", "urgent"],
                "unread": True
            }
        ]
    
    def convert_to_ticket_format(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gmail 메일을 티켓 형식으로 변환"""
        tickets = []
        
        for email in emails:
            # 메일 날짜 파싱
            try:
                date_obj = datetime.fromisoformat(email["date"].replace("Z", "+00:00"))
                created_at = date_obj.strftime("%Y-%m-%dT%H:%M:%S")
            except:
                created_at = email["date"]
            
            # 우선순위 결정
            priority = "High" if "urgent" in email.get("labels", []) else "Medium"
            
            # 상태 결정
            status = "new"  # 새로 받은 메일은 모두 new 상태
            
            ticket = {
                "ticket_id": email["id"],
                "title": email["subject"],
                "status": status,
                "type": "email_ticket",
                "priority": priority,
                "reporter": email["from"],
                "created_at": created_at,
                "description": email["body"],
                "message_id": email["id"],
                "action": "새 메일",
                "content": email["body"],
                "labels": email.get("labels", [])
            }
            tickets.append(ticket)
        
        return {
            "tickets": tickets,
            "new_tickets_created": len(tickets),
            "existing_tickets_found": 0,
            "summary": {
                "total_unread_emails": len(emails),
                "ticket_emails": len(tickets)
            }
        }

# 비동기 함수를 동기적으로 실행하는 헬퍼 함수
def run_async(coro):
    """비동기 함수를 동기적으로 실행"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

def fetch_gmail_tickets_sync() -> Dict[str, Any]:
    """동기적으로 Gmail 티켓 가져오기 (Streamlit에서 사용)"""
    fetcher = GmailTicketFetcher()
    emails = run_async(fetcher.fetch_ticket_emails())
    return fetcher.convert_to_ticket_format(emails)

async def fetch_gmail_tickets_async() -> Dict[str, Any]:
    """비동기적으로 Gmail 티켓 가져오기"""
    fetcher = GmailTicketFetcher()
    emails = await fetcher.fetch_ticket_emails()
    return fetcher.convert_to_ticket_format(emails)

# 테스트용 함수
def test_gmail_integration():
    """Gmail 연동 테스트"""
    print("🔍 Gmail 연동 테스트 시작")
    
    fetcher = GmailTicketFetcher()
    emails = run_async(fetcher.fetch_unread_emails())
    
    print(f"📧 총 메일 수: {len(emails)}")
    
    ticket_emails = [email for email in emails if fetcher.is_ticket_email(email)]
    print(f"🎫 티켓 관련 메일 수: {len(ticket_emails)}")
    
    if ticket_emails:
        ticket_data = fetcher.convert_to_ticket_format(ticket_emails)
        print(f"✅ 티켓 변환 성공: {len(ticket_data['tickets'])}개")
        
        for ticket in ticket_data['tickets']:
            print(f"  - {ticket['title']} ({ticket['priority']})")
    
    return ticket_data if ticket_emails else None

if __name__ == "__main__":
    test_gmail_integration() 