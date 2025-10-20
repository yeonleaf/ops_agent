#!/usr/bin/env python3
"""
MCP 비동기 클라이언트 테스트
"""

import sys
import os

def test_mcp_async_client():
    """MCP 비동기 클라이언트 테스트"""
    try:
        print("🧪 MCP 비동기 클라이언트 테스트 시작")
        print("=" * 50)

        # 클라이언트 import 테스트
        try:
            from mcp_async_client import get_mcp_async_client
            print("✅ mcp_async_client import 성공")
        except Exception as e:
            print(f"❌ mcp_async_client import 실패: {e}")
            return False

        # 클라이언트 초기화 테스트
        try:
            client = get_mcp_async_client()
            print("✅ MCP 비동기 클라이언트 초기화 성공")
        except Exception as e:
            print(f"❌ MCP 비동기 클라이언트 초기화 실패: {e}")
            return False

        # 사용 가능 여부 확인
        if client.is_available():
            print("✅ MCP 비동기 클라이언트 사용 가능")
        else:
            print("❌ MCP 비동기 클라이언트 사용 불가")
            return False

        # 비동기 API 서버 연결 테스트 (선택사항)
        try:
            import requests
            response = requests.get("http://localhost:8001/health", timeout=2)
            if response.status_code == 200:
                print("✅ 비동기 API 서버 연결 성공")
            else:
                print("⚠️ 비동기 API 서버 응답 오류")
        except requests.exceptions.ConnectionError:
            print("⚠️ 비동기 API 서버 연결 실패 (서버가 실행되지 않았을 수 있음)")
        except Exception as e:
            print(f"⚠️ API 서버 테스트 오류: {e}")

        print("=" * 50)
        print("✅ 모든 기본 테스트 통과!")
        print("📱 이제 fastmcp_chatbot_app.py에서 비동기 티켓 UI를 사용할 수 있습니다.")
        return True

    except Exception as e:
        print(f"❌ 테스트 중 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = test_mcp_async_client()
    sys.exit(0 if success else 1)