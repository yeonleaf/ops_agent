#!/usr/bin/env python3
"""
Mock test of async functionality without external dependencies
"""

import sys
import os
import uuid
import time
import threading
from enum import Enum
from typing import Dict, Any
from datetime import datetime

# Mock the imports
sys.modules['fastmcp'] = type(sys)('fastmcp')
sys.modules['fastmcp'].FastMCP = lambda name: None
sys.modules['fastmcp'].tool = lambda: lambda f: f

# Mock streamlit and other problematic imports
sys.modules['streamlit'] = type(sys)('streamlit')

# Import task management functions
from fastmcp_server import (
    TaskStatus,
    create_task,
    update_task_status,
    update_step_status,
    get_task_status,
    process_emails_with_ticket_logic_async_raw,
    get_async_task_status_raw
)

print("🧪 비동기 기능 Mock 테스트 시작...")

try:
    # 테스트 작업 생성
    print("1. 비동기 작업 생성 테스트...")
    result = process_emails_with_ticket_logic_async_raw(
        provider_name="gmail",
        user_id="test_user",
        user_query="테스트 작업"
    )

    print(f"✅ 작업 생성 결과: {result}")

    if result.get("success") and result.get("task_id"):
        task_id = result["task_id"]
        print(f"✅ Task ID: {task_id}")

        # 상태 조회 테스트
        print("\n2. 상태 조회 테스트...")
        for i in range(5):
            print(f"📊 상태 조회 {i+1}/5...")
            status = get_async_task_status_raw(task_id)
            print(f"상태: {status.get('task', {}).get('overall_status', 'Unknown')}")

            # 단계별 상태 출력
            if 'task' in status and 'steps' in status['task']:
                for step in status['task']['steps']:
                    print(f"  - {step['step_name']}: {step['status']} - {step['message']}")

            time.sleep(1)

            # 완료되면 중단
            if status.get('task', {}).get('overall_status') in ['COMPLETED', 'FAILED']:
                break

        print("\n✅ 테스트 완료!")
    else:
        print(f"❌ 작업 생성 실패: {result.get('error')}")

except Exception as e:
    print(f"❌ 테스트 중 오류: {e}")
    import traceback
    traceback.print_exc()