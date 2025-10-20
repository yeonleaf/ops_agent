#!/usr/bin/env python3
"""
MCP 클라이언트를 통한 비동기 티켓 도구 호출
"""

import logging
import json
import requests
import time
from typing import Dict, Any, Optional
from fastmcp_direct_client import get_direct_client

logger = logging.getLogger(__name__)

class MCPAsyncClient:
    """MCP 기반 비동기 티켓 클라이언트 (FastMCP Direct Client 사용)"""

    def __init__(self):
        """FastMCP Direct Client를 사용한 초기화"""
        try:
            self.direct_client = get_direct_client()
            self.API_BASE_URL = "http://localhost:8001"
            logger.info("✅ MCP 비동기 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"❌ MCP 비동기 클라이언트 초기화 실패: {e}")
            self.direct_client = None

    def is_available(self) -> bool:
        """MCP 클라이언트 사용 가능 여부 확인"""
        return self.direct_client is not None

    def create_async_ticket_task(self, user_id: str = "default_user",
                                provider_name: str = "gmail",
                                user_query: Optional[str] = None) -> Dict[str, Any]:
        """
        FastMCP 서버의 비동기 티켓 생성 도구 호출

        Args:
            user_id: 사용자 ID
            provider_name: 이메일 제공자
            user_query: 사용자 쿼리

        Returns:
            작업 결과
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "MCP 클라이언트를 사용할 수 없습니다."
            }

        try:
            logger.info(f"🚀 비동기 티켓 생성 요청: user_id={user_id}")

            # FastMCP Direct Client를 통해 도구 호출
            result = self.direct_client.call_tool(
                "process_emails_with_ticket_logic_async",
                {
                    "provider_name": provider_name,
                    "user_id": user_id,
                    "user_query": user_query
                }
            )

            logger.info(f"📊 비동기 티켓 생성 결과: {result}")

            # FastMCP Direct Client가 결과를 data 필드에 감싸므로 추출
            if result.get("success") and "data" in result:
                return result["data"]  # 실제 도구 결과 반환
            else:
                # 도구 호출 자체가 실패한 경우
                return {
                    "success": False,
                    "error": result.get("error", "도구 호출 실패"),
                    "message": result.get("message", "알 수 없는 오류")
                }

        except Exception as e:
            logger.error(f"❌ 비동기 티켓 생성 실패: {e}")
            return {
                "success": False,
                "error": f"도구 호출 실패: {str(e)}"
            }

    def get_async_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        FastMCP 서버의 비동기 작업 상태 조회 도구 호출

        Args:
            task_id: 작업 ID

        Returns:
            작업 상태
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "MCP 클라이언트를 사용할 수 없습니다."
            }

        try:
            logger.info(f"📊 비동기 작업 상태 조회: task_id={task_id}")

            # FastMCP Direct Client를 통해 도구 호출
            result = self.direct_client.call_tool(
                "get_async_task_status",
                {
                    "task_id": task_id
                }
            )

            logger.info(f"📊 작업 상태 조회 결과: {result}")

            # FastMCP Direct Client가 결과를 data 필드에 감싸므로 추출
            if result.get("success") and "data" in result:
                return result["data"]  # 실제 도구 결과 반환
            else:
                # 도구 호출 자체가 실패한 경우
                return {
                    "success": False,
                    "error": result.get("error", "도구 호출 실패"),
                    "message": result.get("message", "알 수 없는 오류")
                }

        except Exception as e:
            logger.error(f"❌ 작업 상태 조회 실패: {e}")
            return {
                "success": False,
                "error": f"도구 호출 실패: {str(e)}"
            }

    def resume_paused_task(self, task_id: str) -> Dict[str, Any]:
        """
        일시 중단된 작업을 재개합니다.

        Args:
            task_id: 재개할 작업 ID

        Returns:
            재개 결과
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "MCP 클라이언트를 사용할 수 없습니다."
            }

        try:
            logger.info(f"🔄 일시 중단된 작업 재개: task_id={task_id}")

            # FastMCP Direct Client를 통해 도구 호출
            result = self.direct_client.call_tool(
                "resume_paused_task",
                {
                    "task_id": task_id
                }
            )

            logger.info(f"🔄 작업 재개 결과: {result}")

            # FastMCP Direct Client가 결과를 data 필드에 감싸므로 추출
            if result.get("success") and "data" in result:
                return result["data"]  # 실제 도구 결과 반환
            else:
                # 도구 호출 자체가 실패한 경우
                return {
                    "success": False,
                    "error": result.get("error", "도구 호출 실패"),
                    "message": result.get("message", "알 수 없는 오류")
                }

        except Exception as e:
            logger.error(f"❌ 작업 재개 실패: {e}")
            return {
                "success": False,
                "error": f"도구 호출 실패: {str(e)}"
            }

    def check_oauth_status(self, provider_name: str = "gmail") -> Dict[str, Any]:
        """
        OAuth 인증 상태를 확인합니다.

        Args:
            provider_name: 이메일 제공자

        Returns:
            인증 상태
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "MCP 클라이언트를 사용할 수 없습니다."
            }

        try:
            logger.info(f"🔐 OAuth 상태 확인: provider={provider_name}")

            # FastMCP Direct Client를 통해 도구 호출
            result = self.direct_client.call_tool(
                "check_oauth_status",
                {
                    "provider_name": provider_name
                }
            )

            logger.info(f"🔐 OAuth 상태 결과: {result}")

            # FastMCP Direct Client가 결과를 data 필드에 감싸므로 추출
            if result.get("success") and "data" in result:
                return result["data"]  # 실제 도구 결과 반환
            else:
                # 도구 호출 자체가 실패한 경우
                return {
                    "success": False,
                    "error": result.get("error", "도구 호출 실패"),
                    "message": result.get("message", "알 수 없는 오류")
                }

        except Exception as e:
            logger.error(f"❌ OAuth 상태 확인 실패: {e}")
            return {
                "success": False,
                "error": f"도구 호출 실패: {str(e)}"
            }

# 전역 클라이언트 인스턴스
_mcp_async_client = None

def get_mcp_async_client() -> MCPAsyncClient:
    """싱글톤 패턴으로 MCP 비동기 클라이언트 반환"""
    global _mcp_async_client
    if _mcp_async_client is None:
        _mcp_async_client = MCPAsyncClient()
    return _mcp_async_client