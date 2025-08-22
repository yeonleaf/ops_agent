#!/usr/bin/env python3
"""
JSON 파일 기반 메일 조회 MCP 서버
sample_mail_response.json 파일의 데이터를 정제해서 제공하는 MCP 툴
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# MCP 서버 생성
server = Server("json-mail-mcp")

class JsonMailProcessor:
    """JSON 파일 기반 메일 처리기"""
    
    def __init__(self, json_file_path: str = "sample_mail_response.json"):
        """초기화"""
        self.json_file_path = json_file_path
        self._mail_data = None
        self._load_data()
    
    def _load_data(self):
        """JSON 파일에서 메일 데이터 로드"""
        try:
            if os.path.exists(self.json_file_path):
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    self._mail_data = json.load(f)
            else:
                self._mail_data = {"value": []}
        except Exception as e:
            print(f"⚠️ JSON 파일 로드 실패: {e}")
            self._mail_data = {"value": []}
    
    def _clean_html_content(self, html_content: str) -> str:
        """HTML 태그 제거하여 텍스트만 추출"""
        if not html_content:
            return ""
        # HTML 태그 제거
        clean_text = re.sub('<.*?>', '', html_content)
        # 연속된 공백 정리
        clean_text = re.sub(r'\s+', ' ', clean_text)
        # 앞뒤 공백 제거
        return clean_text.strip()
    
    def _format_email_info(self, mail_data: Dict[str, Any]) -> Dict[str, Any]:
        """메일 데이터를 표준 형식으로 변환"""
        # 발신자 정보 추출
        sender_info = mail_data.get("from", mail_data.get("sender", {})).get("emailAddress", {})
        
        # 수신시간 포맷팅
        received_time = mail_data.get("receivedDateTime", "")
        if received_time:
            try:
                dt = datetime.fromisoformat(received_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                formatted_time = received_time
        else:
            formatted_time = "시간 정보 없음"
        
        # 본문 내용 정리
        body_content = ""
        if mail_data.get("body", {}).get("content"):
            if mail_data["body"].get("contentType") == "html":
                body_content = self._clean_html_content(mail_data["body"]["content"])
            else:
                body_content = mail_data["body"]["content"]
        
        # bodyPreview 정리
        body_preview = mail_data.get("bodyPreview", "")
        if len(body_preview) > 100:
            body_preview = body_preview[:100] + "..."
        
        return {
            "id": mail_data.get("id", ""),
            "subject": mail_data.get("subject", "제목 없음"),
            "sender": {
                "name": sender_info.get("name", "알 수 없음"),
                "email": sender_info.get("address", "")
            },
            "received_time": formatted_time,
            "is_read": mail_data.get("isRead", True),
            "importance": mail_data.get("importance", "normal"),
            "has_attachments": mail_data.get("hasAttachments", False),
            "body_preview": body_preview,
            "body_content": body_content[:200] + "..." if len(body_content) > 200 else body_content,
            "conversation_id": mail_data.get("conversationId", ""),
            "categories": mail_data.get("categories", [])
        }
    
    async def get_unread_emails(self, limit: int = 20) -> List[Dict[str, Any]]:
        """안읽은 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return []
        
        unread_emails = []
        for mail_data in self._mail_data["value"]:
            if not mail_data.get("isRead", True):  # isRead가 False인 것만
                formatted_mail = self._format_email_info(mail_data)
                unread_emails.append(formatted_mail)
                
                if len(unread_emails) >= limit:
                    break
        
        return unread_emails
    
    async def get_all_emails(self, limit: int = 50) -> List[Dict[str, Any]]:
        """모든 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return []
        
        all_emails = []
        for mail_data in self._mail_data["value"][:limit]:
            formatted_mail = self._format_email_info(mail_data)
            all_emails.append(formatted_mail)
        
        return all_emails
    
    async def search_emails(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """메일 검색 (제목, 발신자, 내용에서 검색)"""
        if not self._mail_data or "value" not in self._mail_data:
            return []
        
        query_lower = query.lower()
        search_results = []
        
        for mail_data in self._mail_data["value"]:
            # 검색 대상 텍스트들
            subject = mail_data.get("subject", "").lower()
            sender_name = mail_data.get("from", {}).get("emailAddress", {}).get("name", "").lower()
            sender_email = mail_data.get("from", {}).get("emailAddress", {}).get("address", "").lower()
            body_preview = mail_data.get("bodyPreview", "").lower()
            
            # 검색 조건 확인
            if (query_lower in subject or 
                query_lower in sender_name or 
                query_lower in sender_email or 
                query_lower in body_preview):
                
                formatted_mail = self._format_email_info(mail_data)
                search_results.append(formatted_mail)
                
                if len(search_results) >= limit:
                    break
        
        return search_results
    
    async def get_emails_by_sender(self, sender: str, limit: int = 20) -> List[Dict[str, Any]]:
        """특정 발신자의 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return []
        
        sender_lower = sender.lower()
        sender_emails = []
        
        for mail_data in self._mail_data["value"]:
            sender_info = mail_data.get("from", {}).get("emailAddress", {})
            sender_name = sender_info.get("name", "").lower()
            sender_email = sender_info.get("address", "").lower()
            
            if sender_lower in sender_name or sender_lower in sender_email:
                formatted_mail = self._format_email_info(mail_data)
                sender_emails.append(formatted_mail)
                
                if len(sender_emails) >= limit:
                    break
        
        return sender_emails

# 전역 메일 프로세서 인스턴스
mail_processor = None

def get_mail_processor() -> JsonMailProcessor:
    """메일 프로세서 싱글톤"""
    global mail_processor
    if mail_processor is None:
        mail_processor = JsonMailProcessor()
    return mail_processor

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """사용 가능한 툴 목록 반환"""
    return [
        types.Tool(
            name="get_unread_emails",
            description="안읽은 메일을 조회합니다. '안읽은 메일 보여줘', '새 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "조회할 메일 수 (기본값: 20)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_all_emails",
            description="모든 메일을 조회합니다. '전체 메일', '모든 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "조회할 메일 수 (기본값: 50)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="search_emails",
            description="특정 키워드로 메일을 검색합니다. '회의 관련 메일', '프로젝트 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 키워드나 문구"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "조회할 메일 수 (기본값: 20)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_emails_by_sender",
            description="특정 발신자의 메일을 조회합니다. 'XX에서 온 메일', 'XX가 보낸 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sender": {
                        "type": "string",
                        "description": "발신자 이름 또는 이메일 주소"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "조회할 메일 수 (기본값: 20)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["sender"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """툴 호출 처리"""
    try:
        processor = get_mail_processor()
        
        if name == "get_unread_emails":
            limit = arguments.get("limit", 20)
            emails = await processor.get_unread_emails(limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text="📭 안읽은 메일이 없습니다!"
                )]
            
            # 결과 포맷팅
            result = f"📬 안읽은 메일 {len(emails)}개를 찾았습니다:\n\n"
            
            for i, email in enumerate(emails, 1):
                result += f"{i}. **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']} ({email['sender']['email']})\n"
                result += f"   🕐 수신시간: {email['received_time']}\n"
                
                if email.get('importance') == 'high':
                    result += f"   🔴 중요도: 높음\n"
                
                if email.get('has_attachments'):
                    result += f"   📎 첨부파일 있음\n"
                
                if email.get('body_preview'):
                    result += f"   💬 미리보기: {email['body_preview']}\n"
                
                result += "\n"
            
            return [types.TextContent(type="text", text=result)]
        
        elif name == "get_all_emails":
            limit = arguments.get("limit", 50)
            emails = await processor.get_all_emails(limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text="📭 조회할 메일이 없습니다."
                )]
            
            # 읽음/안읽음 통계
            unread_count = sum(1 for email in emails if not email.get('is_read', True))
            read_count = len(emails) - unread_count
            
            result = f"📊 전체 메일 {len(emails)}개 (안읽음: {unread_count}개, 읽음: {read_count}개)\n\n"
            
            for i, email in enumerate(emails[:10], 1):  # 상위 10개만 표시
                status = "🟡" if not email.get('is_read', True) else "✅"
                
                result += f"{i}. {status} **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']}\n"
                result += f"   🕐 수신시간: {email['received_time']}\n\n"
            
            if len(emails) > 10:
                result += f"... 외 {len(emails) - 10}개 메일\n"
            
            return [types.TextContent(type="text", text=result)]
        
        elif name == "search_emails":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 20)
            
            if not query:
                return [types.TextContent(
                    type="text",
                    text="❌ 검색 키워드를 입력해주세요."
                )]
            
            emails = await processor.search_emails(query=query, limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text=f"🔍 '{query}' 검색 결과가 없습니다."
                )]
            
            result = f"🔍 '{query}' 검색 결과 {len(emails)}개:\n\n"
            
            for i, email in enumerate(emails, 1):
                status = "🟡" if not email.get('is_read', True) else "✅"
                
                result += f"{i}. {status} **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']}\n"
                result += f"   🕐 수신시간: {email['received_time']}\n"
                
                if email.get('body_preview'):
                    result += f"   💬 미리보기: {email['body_preview']}\n"
                
                result += "\n"
            
            return [types.TextContent(type="text", text=result)]
        
        elif name == "get_emails_by_sender":
            sender = arguments.get("sender", "")
            limit = arguments.get("limit", 20)
            
            if not sender:
                return [types.TextContent(
                    type="text",
                    text="❌ 발신자 정보를 입력해주세요."
                )]
            
            emails = await processor.get_emails_by_sender(sender=sender, limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text=f"📭 '{sender}'에서 온 메일이 없습니다."
                )]
            
            result = f"📧 '{sender}'에서 온 메일 {len(emails)}개:\n\n"
            
            for i, email in enumerate(emails, 1):
                status = "🟡" if not email.get('is_read', True) else "✅"
                
                result += f"{i}. {status} **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']} ({email['sender']['email']})\n"
                result += f"   🕐 수신시간: {email['received_time']}\n"
                
                if email.get('body_preview'):
                    result += f"   💬 미리보기: {email['body_preview']}\n"
                
                result += "\n"
            
            return [types.TextContent(type="text", text=result)]
        
        else:
            return [types.TextContent(
                type="text",
                text=f"❌ 알 수 없는 툴: {name}"
            )]
            
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ 오류 발생: {str(e)}"
        )]

async def main():
    """MCP 서버 실행"""
    # 서버 옵션 설정
    options = InitializationOptions(
        server_name="json-mail-mcp",
        server_version="1.0.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={}
        )
    )
    
    # stdin/stdout을 통한 MCP 서버 실행
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            options
        )

if __name__ == "__main__":
    print("🚀 JSON Mail MCP 서버를 시작합니다...")
    asyncio.run(main())