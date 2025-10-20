#!/usr/bin/env python3
"""
MCP Tool that calls the async FastAPI server
기존 MCP 구조를 유지하면서 async API를 호출하는 도구
"""

import requests
import json
import time
from typing import Dict, Any, Optional

def create_async_ticket_task_mcp_tool(user_id: str = "default_user",
                                      provider_name: str = "gmail",
                                      user_query: Optional[str] = None) -> Dict[str, Any]:
    """
    MCP Tool: 비동기 티켓 생성 작업을 시작하고 완료될 때까지 기다림

    Args:
        user_id: 사용자 ID
        provider_name: 이메일 제공자 (gmail, outlook)
        user_query: 사용자 쿼리

    Returns:
        작업 완료 결과
    """
    API_BASE_URL = "http://localhost:8001"

    try:
        # 1. 작업 생성
        payload = {
            "user_id": user_id,
            "provider_name": provider_name,
            "user_query": user_query
        }

        response = requests.post(f"{API_BASE_URL}/tasks/create-tickets", json=payload)
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"작업 생성 실패: {response.text}"
            }

        task_data = response.json()
        task_id = task_data["task_id"]

        print(f"✅ 비동기 작업 시작: {task_id}")

        # 2. 작업 완료까지 폴링
        max_wait_time = 300  # 5분 최대 대기
        poll_interval = 5    # 5초마다 확인
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            # 상태 확인
            status_response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/status")
            if status_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"상태 조회 실패: {status_response.text}"
                }

            status_data = status_response.json()
            overall_status = status_data["overall_status"]

            print(f"📊 작업 상태: {overall_status}")

            # 완료 또는 실패 시 결과 반환
            if overall_status == "COMPLETED":
                final_result = status_data.get("final_result", {})
                return {
                    "success": True,
                    "task_id": task_id,
                    "tickets_created": final_result.get("tickets_created", 0),
                    "existing_tickets": final_result.get("existing_tickets", 0),
                    "message": final_result.get("message", "작업이 완료되었습니다.")
                }

            elif overall_status == "FAILED":
                final_result = status_data.get("final_result", {})
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": final_result.get("message", "작업이 실패했습니다."),
                    "details": final_result.get("error", "")
                }

            # 진행 중인 경우 계속 대기
            time.sleep(poll_interval)
            elapsed_time += poll_interval

        # 타임아웃
        return {
            "success": False,
            "task_id": task_id,
            "error": f"작업이 {max_wait_time}초 내에 완료되지 않았습니다.",
            "timeout": True
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "FastAPI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"예상치 못한 오류: {str(e)}"
        }

def get_async_task_status_mcp_tool(task_id: str) -> Dict[str, Any]:
    """
    MCP Tool: 특정 작업의 상태를 조회

    Args:
        task_id: 조회할 작업 ID

    Returns:
        작업 상태 정보
    """
    API_BASE_URL = "http://localhost:8001"

    try:
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/status")
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json()
            }
        elif response.status_code == 404:
            return {
                "success": False,
                "error": "작업을 찾을 수 없습니다."
            }
        else:
            return {
                "success": False,
                "error": f"상태 조회 실패: {response.text}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"오류 발생: {str(e)}"
        }

# MCP 서버에 등록할 도구들
MCP_TOOLS = {
    "create_async_ticket_task": {
        "name": "create_async_ticket_task",
        "description": "비동기 방식으로 티켓 생성 작업을 시작하고 완료까지 대기합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "default_user"},
                "provider_name": {"type": "string", "enum": ["gmail", "outlook"], "default": "gmail"},
                "user_query": {"type": "string", "description": "선택적 사용자 쿼리"}
            }
        },
        "handler": create_async_ticket_task_mcp_tool
    },
    "get_async_task_status": {
        "name": "get_async_task_status",
        "description": "비동기 작업의 현재 상태를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "조회할 작업 ID"}
            },
            "required": ["task_id"]
        },
        "handler": get_async_task_status_mcp_tool
    }
}