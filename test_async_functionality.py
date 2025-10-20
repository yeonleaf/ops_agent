#!/usr/bin/env python3
"""
비동기 티켓 기능 테스트
"""

try:
    print("🧪 비동기 티켓 생성 기능 테스트 시작...")

    from mcp_async_client import get_mcp_async_client

    client = get_mcp_async_client()
    print(f"✅ 클라이언트 초기화 성공: {client}")
    print(f"✅ 사용 가능 여부: {client.is_available()}")

    # 테스트 작업 생성
    print("\n🚀 비동기 작업 생성 테스트...")
    result = client.create_async_ticket_task(
        user_id="test_user",
        provider_name="gmail",
        user_query="테스트 작업"
    )

    print(f"📊 작업 생성 결과: {result}")

    if result.get("success") and result.get("task_id"):
        task_id = result["task_id"]
        print(f"✅ 작업 시작됨! Task ID: {task_id}")

        # 상태 조회 테스트
        import time
        for i in range(3):
            print(f"\n📊 상태 조회 {i+1}/3...")
            status = client.get_async_task_status(task_id)
            print(f"상태: {status}")
            time.sleep(2)
    else:
        print(f"❌ 작업 시작 실패: {result.get('error', '알 수 없는 오류')}")

except Exception as e:
    print(f"❌ 테스트 중 오류: {e}")
    import traceback
    traceback.print_exc()