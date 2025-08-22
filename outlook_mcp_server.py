#!/usr/bin/env python3
"""
Microsoft Graph API MCP Server
LLM이 자연어로 Outlook 메일을 조회할 수 있도록 하는 MCP 툴
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Microsoft Graph SDK
try:
    from msgraph import GraphServiceClient
    from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilder
    from azure.identity import ClientSecretCredential
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False

load_dotenv()

# MCP 서버 생성
server = Server("outlook-mcp")

class OutlookGraphClient:
    """Microsoft Graph API 클라이언트"""
    
    def __init__(self):
        """초기화"""
        self.client = None
        self.user_id = None
        self._setup_client()
    
    def _setup_client(self):
        """Graph API 클라이언트 설정"""
        if not GRAPH_AVAILABLE:
            raise ImportError("Microsoft Graph SDK가 설치되지 않았습니다. pip install msgraph-sdk 실행하세요.")
        
        # 환경변수에서 인증 정보 로드
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID") 
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        user_email = os.getenv("OUTLOOK_USER_EMAIL")
        
        if not all([tenant_id, client_id, client_secret, user_email]):
            raise ValueError("Azure/Outlook 인증 정보가 환경변수에 설정되지 않았습니다.")
        
        # 인증 설정
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Graph 클라이언트 생성
        scopes = ["https://graph.microsoft.com/.default"]
        self.client = GraphServiceClient(credential, scopes)
        self.user_id = user_email
    
    async def get_unread_emails(self, folder: str = "inbox", limit: int = 20) -> List[Dict[str, Any]]:
        """읽지 않은 메일 조회"""
        try:
            if not self.client:
                raise ValueError("Graph 클라이언트가 초기화되지 않았습니다.")
            
            # 읽지 않은 메일 필터링
            filter_query = "isRead eq false"
            
            # 메일 조회
            messages = await self.client.users.by_user_id(self.user_id).messages.get(
                request_configuration=lambda req_config: (
                    setattr(req_config.query_parameters, 'filter', filter_query),
                    setattr(req_config.query_parameters, 'top', limit),
                    setattr(req_config.query_parameters, 'orderby', 'receivedDateTime desc')
                )
            )
            
            # 결과 정리
            email_list = []
            if messages and messages.value:
                for message in messages.value:
                    email_info = {
                        "id": message.id,
                        "subject": message.subject or "제목 없음",
                        "sender": {
                            "name": message.sender.email_address.name if message.sender else "알 수 없음",
                            "email": message.sender.email_address.address if message.sender else ""
                        },
                        "received_time": message.received_date_time.isoformat() if message.received_date_time else "",
                        "body_preview": message.body_preview[:100] + "..." if message.body_preview and len(message.body_preview) > 100 else message.body_preview,
                        "importance": message.importance.value if message.importance else "normal",
                        "has_attachments": message.has_attachments or False,
                        "folder": folder
                    }
                    email_list.append(email_info)
            
            return email_list
            
        except Exception as e:
            raise Exception(f"메일 조회 실패: {str(e)}")
    
    async def get_recent_emails(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 메일 조회"""
        try:
            # 날짜 필터링
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            filter_query = f"receivedDateTime ge {since_date}"
            
            messages = await self.client.users.by_user_id(self.user_id).messages.get(
                request_configuration=lambda req_config: (
                    setattr(req_config.query_parameters, 'filter', filter_query),
                    setattr(req_config.query_parameters, 'top', limit),
                    setattr(req_config.query_parameters, 'orderby', 'receivedDateTime desc')
                )
            )
            
            email_list = []
            if messages and messages.value:
                for message in messages.value:
                    email_info = {
                        "id": message.id,
                        "subject": message.subject or "제목 없음", 
                        "sender": {
                            "name": message.sender.email_address.name if message.sender else "알 수 없음",
                            "email": message.sender.email_address.address if message.sender else ""
                        },
                        "received_time": message.received_date_time.isoformat() if message.received_date_time else "",
                        "is_read": message.is_read or False,
                        "body_preview": message.body_preview[:100] + "..." if message.body_preview and len(message.body_preview) > 100 else message.body_preview,
                        "importance": message.importance.value if message.importance else "normal"
                    }
                    email_list.append(email_info)
            
            return email_list
            
        except Exception as e:
            raise Exception(f"최근 메일 조회 실패: {str(e)}")
    
    async def search_emails(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """메일 검색"""
        try:
            messages = await self.client.users.by_user_id(self.user_id).messages.get(
                request_configuration=lambda req_config: (
                    setattr(req_config.query_parameters, 'search', f'"{query}"'),
                    setattr(req_config.query_parameters, 'top', limit),
                    setattr(req_config.query_parameters, 'orderby', 'receivedDateTime desc')
                )
            )
            
            email_list = []
            if messages and messages.value:
                for message in messages.value:
                    email_info = {
                        "id": message.id,
                        "subject": message.subject or "제목 없음",
                        "sender": {
                            "name": message.sender.email_address.name if message.sender else "알 수 없음", 
                            "email": message.sender.email_address.address if message.sender else ""
                        },
                        "received_time": message.received_date_time.isoformat() if message.received_date_time else "",
                        "is_read": message.is_read or False,
                        "body_preview": message.body_preview[:100] + "..." if message.body_preview and len(message.body_preview) > 100 else message.body_preview,
                        "relevance_score": 1.0  # Graph API에서 제공하는 경우 사용
                    }
                    email_list.append(email_info)
            
            return email_list
            
        except Exception as e:
            raise Exception(f"메일 검색 실패: {str(e)}")

# 전역 클라이언트 인스턴스
outlook_client = None

def get_outlook_client() -> OutlookGraphClient:
    """Outlook 클라이언트 싱글톤"""
    global outlook_client
    if outlook_client is None:
        outlook_client = OutlookGraphClient()
    return outlook_client

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """사용 가능한 툴 목록 반환"""
    return [
        types.Tool(
            name="get_unread_emails",
            description="읽지 않은 Outlook 메일을 조회합니다. '안 읽은 메일', '새 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "조회할 폴더 (기본값: inbox)",
                        "default": "inbox"
                    },
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
            name="get_recent_emails", 
            description="최근 며칠간의 메일을 조회합니다. '최근 메일', '이번 주 메일' 등의 요청에 사용하세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "조회할 기간 (일 단위, 기본값: 7일)",
                        "default": 7,
                        "minimum": 1,
                        "maximum": 30
                    },
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
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """툴 호출 처리"""
    try:
        client = get_outlook_client()
        
        if name == "get_unread_emails":
            folder = arguments.get("folder", "inbox")
            limit = arguments.get("limit", 20)
            
            emails = await client.get_unread_emails(folder=folder, limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text="📭 읽지 않은 메일이 없습니다!"
                )]
            
            # 결과 포맷팅
            result = f"📬 읽지 않은 메일 {len(emails)}개를 찾았습니다:\n\n"
            
            for i, email in enumerate(emails, 1):
                received_time = datetime.fromisoformat(email['received_time'].replace('Z', '+00:00'))
                time_str = received_time.strftime('%m/%d %H:%M')
                
                result += f"{i}. **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']} ({email['sender']['email']})\n"
                result += f"   🕐 수신시간: {time_str}\n"
                
                if email.get('importance') == 'high':
                    result += f"   🔴 중요도: 높음\n"
                
                if email.get('has_attachments'):
                    result += f"   📎 첨부파일 있음\n"
                
                if email.get('body_preview'):
                    result += f"   💬 미리보기: {email['body_preview']}\n"
                
                result += "\n"
            
            return [types.TextContent(type="text", text=result)]
        
        elif name == "get_recent_emails":
            days = arguments.get("days", 7)
            limit = arguments.get("limit", 50)
            
            emails = await client.get_recent_emails(days=days, limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text", 
                    text=f"📭 최근 {days}일간 메일이 없습니다."
                )]
            
            # 읽음/안읽음 통계
            unread_count = sum(1 for email in emails if not email.get('is_read', True))
            read_count = len(emails) - unread_count
            
            result = f"📊 최근 {days}일간 메일 {len(emails)}개 (읽지 않음: {unread_count}개, 읽음: {read_count}개)\n\n"
            
            for i, email in enumerate(emails[:10], 1):  # 상위 10개만 표시
                received_time = datetime.fromisoformat(email['received_time'].replace('Z', '+00:00'))
                time_str = received_time.strftime('%m/%d %H:%M')
                
                status = "🟡" if not email.get('is_read', True) else "✅"
                
                result += f"{i}. {status} **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']}\n"
                result += f"   🕐 수신시간: {time_str}\n\n"
            
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
            
            emails = await client.search_emails(query=query, limit=limit)
            
            if not emails:
                return [types.TextContent(
                    type="text",
                    text=f"🔍 '{query}' 검색 결과가 없습니다."
                )]
            
            result = f"🔍 '{query}' 검색 결과 {len(emails)}개:\n\n"
            
            for i, email in enumerate(emails, 1):
                received_time = datetime.fromisoformat(email['received_time'].replace('Z', '+00:00'))
                time_str = received_time.strftime('%m/%d %H:%M')
                
                status = "🟡" if not email.get('is_read', True) else "✅"
                
                result += f"{i}. {status} **{email['subject']}**\n"
                result += f"   📧 보낸이: {email['sender']['name']}\n"
                result += f"   🕐 수신시간: {time_str}\n"
                
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
        server_name="outlook-mcp",
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
    # 환경변수 확인
    required_vars = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "OUTLOOK_USER_EMAIL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ 필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        print("📝 .env 파일에 다음 변수들을 설정하세요:")
        for var in missing_vars:
            print(f"   {var}=your_value")
        exit(1)
    
    if not GRAPH_AVAILABLE:
        print("❌ Microsoft Graph SDK가 필요합니다.")
        print("📦 설치: pip install msgraph-sdk azure-identity")
        exit(1)
    
    print("🚀 Outlook MCP 서버를 시작합니다...")
    asyncio.run(main())