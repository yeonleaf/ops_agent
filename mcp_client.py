#!/usr/bin/env python3
"""
MCP 클라이언트 - JSON 메일 MCP 서버와 통신
"""

import json
import asyncio
import subprocess
import sys
import tempfile
import os
from typing import Dict, Any, List, Optional

class MCPClient:
    """MCP 클라이언트"""
    
    def __init__(self, server_script: str = "json_mail_mcp_server.py"):
        self.server_script = server_script
        self.server_process = None
        
    async def start_server(self):
        """MCP 서버 시작"""
        try:
            self.server_process = await asyncio.create_subprocess_exec(
                sys.executable, self.server_script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            return True
        except Exception as e:
            print(f"서버 시작 실패: {e}")
            return False
    
    async def stop_server(self):
        """MCP 서버 종료"""
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            self.server_process = None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """MCP 툴 호출"""
        try:
            # 서버가 실행 중이 아니면 직접 호출 방식 사용
            return await self._call_tool_direct(tool_name, arguments)
        except Exception as e:
            return f"툴 호출 오류: {str(e)}"
    
    async def _call_tool_direct(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """직접 MCP 서버 호출 (subprocess 방식)"""
        try:
            # JSON-RPC 요청 생성
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # 초기화 요청 먼저 보내기
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mail-chatbot",
                        "version": "1.0.0"
                    }
                }
            }
            
            # 툴 목록 요청
            list_tools_request = {
                "jsonrpc": "2.0", 
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            # 툴 호출 요청
            call_tool_request = {
                "jsonrpc": "2.0",
                "id": 2, 
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # 요청들을 순서대로 전송
            requests = [
                json.dumps(init_request),
                json.dumps(list_tools_request),
                json.dumps(call_tool_request)
            ]
            
            input_data = "\n".join(requests)
            
            # MCP 서버 실행
            result = await asyncio.create_subprocess_exec(
                sys.executable, self.server_script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate(input=input_data.encode())
            
            if result.returncode == 0:
                # 응답 파싱
                output_lines = stdout.decode().strip().split('\n')
                
                # 마지막 응답 (툴 호출 결과) 찾기
                for line in reversed(output_lines):
                    if line.strip():
                        try:
                            response = json.loads(line)
                            if response.get("id") == 2 and "result" in response:
                                content = response["result"].get("content", [])
                                if isinstance(content, list) and len(content) > 0:
                                    return content[0].get("text", "응답 내용이 없습니다.")
                                return str(content)
                        except json.JSONDecodeError:
                            continue
                
                return "유효한 응답을 받지 못했습니다."
            else:
                error_output = stderr.decode()
                return f"서버 오류: {error_output}"
                
        except Exception as e:
            return f"MCP 통신 오류: {str(e)}"

# 간단한 동기 래퍼
class SimpleMCPClient:
    """간단한 동기 MCP 클라이언트"""
    
    def __init__(self, server_script: str = "json_mail_mcp_server.py"):
        self.server_script = server_script
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """툴 호출 (동기 방식)"""
        try:
            # JSON-RPC 요청들 생성
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize", 
                "params": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mail-chatbot",
                        "version": "1.0.0"
                    }
                }
            }
            
            call_tool_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # 요청 순서대로 전송
            input_data = json.dumps(init_request) + "\n" + json.dumps(call_tool_request)
            
            # subprocess로 MCP 서버 실행
            result = subprocess.run([
                sys.executable, self.server_script
            ],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
            )
            
            if result.returncode == 0:
                # 응답 라인들 파싱
                lines = result.stdout.strip().split('\n')
                
                # 툴 호출 응답 찾기 (id=1인 응답)
                for line in lines:
                    if line.strip():
                        try:
                            response = json.loads(line)
                            if response.get("id") == 1 and "result" in response:
                                content = response["result"].get("content", [])
                                if isinstance(content, list) and len(content) > 0:
                                    return content[0].get("text", "응답 내용이 없습니다.")
                                return str(content)
                        except json.JSONDecodeError:
                            continue
                
                return "유효한 응답을 받지 못했습니다."
            else:
                return f"서버 오류: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return "서버 응답 시간 초과"
        except Exception as e:
            return f"MCP 통신 오류: {str(e)}"

# 테스트용 함수들
def test_unread_emails():
    """안읽은 메일 테스트"""
    client = SimpleMCPClient()
    result = client.call_tool("get_unread_emails", {"limit": 5})
    print("=== 안읽은 메일 테스트 ===")
    print(result)
    print()

def test_all_emails():
    """전체 메일 테스트"""
    client = SimpleMCPClient()
    result = client.call_tool("get_all_emails", {"limit": 10})
    print("=== 전체 메일 테스트 ===")
    print(result)
    print()

def test_search_emails():
    """메일 검색 테스트"""
    client = SimpleMCPClient()
    result = client.call_tool("search_emails", {"query": "tasks", "limit": 5})
    print("=== 메일 검색 테스트 ===")
    print(result)
    print()

if __name__ == "__main__":
    # 테스트 실행
    test_unread_emails()
    test_all_emails() 
    test_search_emails()