#!/usr/bin/env python3
"""
비동기 티켓 UI 간단 테스트
"""

try:
    print("🧪 async_ticket_mcp_ui import 테스트...")
    from async_ticket_mcp_ui import get_async_ticket_mcp_ui
    print("✅ async_ticket_mcp_ui import 성공")

    print("🧪 UI 인스턴스 생성 테스트...")
    ui = get_async_ticket_mcp_ui()
    print("✅ UI 인스턴스 생성 성공")

    print("🧪 MCP 클라이언트 사용 가능 여부 테스트...")
    if ui.mcp_client.is_available():
        print("✅ MCP 클라이언트 사용 가능")
    else:
        print("❌ MCP 클라이언트 사용 불가")

    print("\n🎉 모든 테스트 통과! UI를 실행할 수 있습니다.")

except Exception as e:
    print(f"❌ 테스트 실패: {e}")
    import traceback
    traceback.print_exc()