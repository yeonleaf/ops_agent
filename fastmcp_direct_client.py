#!/usr/bin/env python3
"""
FastMCP 직접 클라이언트
HTTP 대신 직접 함수 호출을 사용하여 FastMCP 도구들을 사용
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FastMCPDirectClient:
    """FastMCP 도구들을 직접 호출하는 클라이언트"""
    
    def __init__(self):
        self.tools_available = True
        self._import_tools()
    
    def _import_tools(self):
        """원본 함수들을 직접 import"""
        try:
            # 원본 unified_email_service에서 함수들을 직접 import
            from unified_email_service import (
                get_raw_emails as original_get_raw_emails,
                process_emails_with_ticket_logic as original_process_emails,
                get_email_provider_status as original_get_provider_status,
                get_mail_content_by_id as original_get_mail_content,
                create_ticket_from_single_email as original_create_ticket,
                fetch_emails_sync as original_fetch_emails
            )
            
            # 이메일 에이전트는 별도로 구현
            from fastmcp_email_agent import email_agent_logic
            
            # 도구들을 딕셔너리에 저장
            self.tools = {
                'get_raw_emails': original_get_raw_emails,
                'process_emails_with_ticket_logic': original_process_emails,
                'get_email_provider_status': original_get_provider_status,
                'get_mail_content_by_id': original_get_mail_content,
                'create_ticket_from_single_email': original_create_ticket,
                'fetch_emails_sync': original_fetch_emails,
                'email_agent': email_agent_logic
            }
            
            logging.info("✅ 원본 함수들 import 성공")
            
        except Exception as e:
            logging.error(f"❌ 원본 함수들 import 실패: {str(e)}")
            self.tools_available = False
            self.tools = {}
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """도구 직접 호출"""
        try:
            if not self.tools_available:
                return {
                    "success": False,
                    "message": "FastMCP 도구들을 사용할 수 없습니다.",
                    "error": "Tools not available"
                }
            
            if tool_name not in self.tools:
                return {
                    "success": False,
                    "message": f"도구 '{tool_name}'을 찾을 수 없습니다.",
                    "error": f"Tool '{tool_name}' not found"
                }
            
            # 도구 실행
            tool_function = self.tools[tool_name]
            result = tool_function(**arguments)
            
            return {
                "success": True,
                "message": f"도구 '{tool_name}' 실행 완료",
                "data": result,
                "tool_name": tool_name
            }
            
        except Exception as e:
            logging.error(f"❌ 도구 '{tool_name}' 실행 실패: {str(e)}")
            return {
                "success": False,
                "message": f"도구 '{tool_name}' 실행 중 오류가 발생했습니다: {str(e)}",
                "error": str(e),
                "tool_name": tool_name
            }
    
    def call_agent(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """에이전트 직접 호출"""
        try:
            if not self.tools_available:
                return {
                    "success": False,
                    "message": "FastMCP 에이전트를 사용할 수 없습니다.",
                    "error": "Agent not available"
                }
            
            if 'email_agent' not in self.tools:
                return {
                    "success": False,
                    "message": "이메일 에이전트를 찾을 수 없습니다.",
                    "error": "Email agent not found"
                }
            
            # 에이전트 실행
            agent_function = self.tools['email_agent']
            result = agent_function(user_query, context)
            
            return {
                "success": True,
                "message": "에이전트 실행 완료",
                "data": result,
                "agent_name": "email_agent"
            }
            
        except Exception as e:
            logging.error(f"❌ 에이전트 실행 실패: {str(e)}")
            return {
                "success": False,
                "message": f"에이전트 실행 중 오류가 발생했습니다: {str(e)}",
                "error": str(e),
                "agent_name": "email_agent"
            }
    
    def get_available_tools(self) -> List[str]:
        """사용 가능한 도구 목록 반환"""
        if not self.tools_available:
            return []
        return list(self.tools.keys())
    
    def get_server_status(self) -> Dict[str, Any]:
        """서버 상태 확인"""
        try:
            import psutil
            import platform
            
            # 시스템 정보 수집
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage': psutil.disk_usage('/').percent
            }
            
            # 도구 상태
            tools_status = {
                'tools_available': self.tools_available,
                'tools_count': len(self.tools) if self.tools_available else 0,
                'available_tools': self.get_available_tools()
            }
            
            return {
                'status': 'healthy' if self.tools_available else 'error',
                'system_info': system_info,
                'tools_status': tools_status,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# 전역 클라이언트 인스턴스
_direct_client = None

def get_direct_client() -> FastMCPDirectClient:
    """전역 클라이언트 인스턴스 반환"""
    global _direct_client
    if _direct_client is None:
        _direct_client = FastMCPDirectClient()
    return _direct_client

# 편의 함수들
def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """도구 호출 편의 함수"""
    client = get_direct_client()
    return client.call_tool(tool_name, arguments)

def call_agent(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """에이전트 호출 편의 함수"""
    client = get_direct_client()
    return client.call_agent(user_query, context)

def get_server_status() -> Dict[str, Any]:
    """서버 상태 확인 편의 함수"""
    client = get_direct_client()
    return client.get_server_status()

if __name__ == "__main__":
    # 테스트
    client = FastMCPDirectClient()
    
    print("🧪 FastMCP 직접 클라이언트 테스트")
    print("=" * 50)
    
    # 서버 상태 확인
    status = client.get_server_status()
    print(f"📊 서버 상태: {status.get('status')}")
    print(f"🛠️ 사용 가능한 도구: {len(client.get_available_tools())}개")
    
    # 간단한 도구 테스트
    if client.tools_available:
        print("\n🔧 도구 테스트:")
        
        # get_available_providers 테스트
        result = client.call_tool('get_email_provider_status', {'provider_name': None})
        print(f"  - get_email_provider_status: {'✅' if result.get('success') else '❌'}")
        
        # 에이전트 테스트
        print("\n🤖 에이전트 테스트:")
        agent_result = client.call_agent("서버 상태를 확인해주세요")
        print(f"  - email_agent: {'✅' if agent_result.get('success') else '❌'}")
        if agent_result.get('success'):
            print(f"    응답: {agent_result.get('data', {}).get('message', '')[:100]}...")
    
    print("\n✅ 테스트 완료")
