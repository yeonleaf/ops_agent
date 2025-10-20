#!/usr/bin/env python3
"""
Final test of the async functionality
"""

print("🧪 최종 비동기 기능 테스트...")

try:
    from mcp_async_client import get_mcp_async_client
    import time

    print("1. 클라이언트 초기화...")
    client = get_mcp_async_client()
    print(f"✅ 사용 가능: {client.is_available()}")

    if client.is_available():
        print("\n2. 비동기 작업 생성...")
        result = client.create_async_ticket_task(
            user_id="final_test_user",
            provider_name="gmail",
            user_query="최종 테스트"
        )

        print(f"📊 생성 결과: {result}")

        # 성공적으로 생성되었는지 확인
        if result.get("success"):
            # data 필드에서 실제 결과 추출
            data = result.get("data", {})
            if data.get("success") and data.get("task_id"):
                task_id = data["task_id"]
                print(f"✅ 작업 생성 성공! Task ID: {task_id}")

                print("\n3. 실시간 상태 추적...")
                for i in range(10):
                    print(f"\n📊 상태 조회 {i+1}/10...")
                    status_result = client.get_async_task_status(task_id)

                    if status_result.get("success") and "data" in status_result:
                        task_data = status_result["data"]["task"]
                        overall_status = task_data.get("overall_status", "Unknown")
                        print(f"전체 상태: {overall_status}")

                        # 각 단계 상태 출력
                        for step in task_data.get("steps", []):
                            status_emoji = {"PENDING": "⏳", "IN_PROGRESS": "🔄", "COMPLETED": "✅", "FAILED": "❌"}.get(step["status"], "❓")
                            print(f"  {status_emoji} {step['step_name']}: {step['message']}")

                        if overall_status in ["COMPLETED", "FAILED"]:
                            print(f"\n🎯 최종 상태: {overall_status}")
                            if overall_status == "COMPLETED":
                                print("🎉 비동기 티켓 생성이 성공적으로 완료되었습니다!")
                            else:
                                print("❌ 작업이 실패했습니다.")
                            break
                    else:
                        print(f"❌ 상태 조회 실패: {status_result}")

                    time.sleep(2)

                print("\n✅ 최종 테스트 완료!")
            else:
                print(f"❌ 작업 생성 실패: {data}")
        else:
            print(f"❌ 클라이언트 오류: {result.get('error')}")
    else:
        print("❌ 클라이언트 사용 불가")

except Exception as e:
    print(f"❌ 테스트 중 오류: {e}")
    import traceback
    traceback.print_exc()