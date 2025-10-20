#!/usr/bin/env python3
"""
Import test for FastMCP functions
"""

print("🧪 Import 테스트 시작...")

try:
    print("1. fastmcp_server import 테스트...")
    from fastmcp_server import (
        process_emails_with_ticket_logic_async_raw,
        get_async_task_status_raw,
        list_active_tasks_raw
    )
    print("✅ fastmcp_server 비동기 함수들 import 성공!")

    print("2. 함수 직접 호출 테스트...")
    result = process_emails_with_ticket_logic_async_raw("gmail", "test_user", "test query")
    print(f"✅ 함수 호출 성공! 결과: {result}")

except Exception as e:
    print(f"❌ Import 또는 호출 실패: {e}")
    import traceback
    traceback.print_exc()