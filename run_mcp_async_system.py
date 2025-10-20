#!/usr/bin/env python3
"""
MCP 기반 비동기 티켓 시스템 실행 스크립트
FastMCP 서버, 비동기 API 서버, Streamlit UI를 모두 실행
"""

import subprocess
import sys
import time
import threading
import os
from pathlib import Path

def run_fastmcp_server():
    """FastMCP 서버 실행"""
    print("🌟 FastMCP 서버 시작...")
    try:
        subprocess.run([
            sys.executable, "fastmcp_server.py"
        ], check=True)
    except KeyboardInterrupt:
        print("⛔ FastMCP 서버 종료")
    except Exception as e:
        print(f"❌ FastMCP 서버 실행 오류: {e}")

def run_async_api_server():
    """비동기 API 서버 실행"""
    print("🚀 비동기 API 서버 시작...")
    time.sleep(2)  # FastMCP 서버가 먼저 시작되도록 대기
    try:
        subprocess.run([
            sys.executable, "async_task_api.py"
        ], check=True)
    except KeyboardInterrupt:
        print("⛔ 비동기 API 서버 종료")
    except Exception as e:
        print(f"❌ 비동기 API 서버 실행 오류: {e}")

def run_streamlit_ui():
    """Streamlit UI 실행"""
    print("🎨 Streamlit UI 시작...")
    time.sleep(5)  # 서버들이 먼저 시작되도록 5초 대기
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "fastmcp_chatbot_app.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ], check=True)
    except KeyboardInterrupt:
        print("⛔ Streamlit UI 종료")
    except Exception as e:
        print(f"❌ Streamlit UI 실행 오류: {e}")

def check_dependencies():
    """필요한 의존성 확인"""
    required_files = [
        "fastmcp_server.py",
        "async_task_api.py",
        "async_task_models.py",
        "async_ticket_processor.py",
        "mcp_async_client.py",
        "async_ticket_mcp_ui.py",
        "fastmcp_chatbot_app.py",
        "unified_email_service.py"
    ]

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        print(f"❌ 필수 파일이 없습니다: {', '.join(missing_files)}")
        return False

    # 필요한 Python 패키지 확인
    try:
        import fastapi
        import uvicorn
        import streamlit
        import requests
        import sqlite3
        from fastmcp import FastMCP
        print("✅ 필수 의존성 확인 완료")
        return True
    except ImportError as e:
        print(f"❌ 필요한 패키지가 설치되지 않았습니다: {e}")
        print("다음 명령어로 설치하세요:")
        print("pip install fastapi uvicorn streamlit requests fastmcp")
        return False

def main():
    """메인 함수"""
    print("🚀 MCP 기반 비동기 티켓 시스템 시작")
    print("=" * 60)

    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)

    # logs 디렉토리 생성
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    print("📂 로그 디렉토리 생성 완료")
    print("🔧 시스템 구성 요소:")
    print("  - FastMCP 서버: MCP 도구 제공")
    print("  - 비동기 API 서버: http://localhost:8001")
    print("  - Streamlit UI: http://localhost:8501")
    print("=" * 60)

    try:
        # 세 프로세스를 병렬로 실행
        fastmcp_thread = threading.Thread(target=run_fastmcp_server, daemon=True)
        api_thread = threading.Thread(target=run_async_api_server, daemon=True)
        ui_thread = threading.Thread(target=run_streamlit_ui, daemon=True)

        # 순서대로 시작 (의존성 고려)
        fastmcp_thread.start()
        api_thread.start()
        ui_thread.start()

        print("✅ 모든 시스템이 시작되었습니다!")
        print("📱 브라우저에서 http://localhost:8501 에 접속하세요")
        print("🔧 MCP 도구:")
        print("  - create_async_ticket_task")
        print("  - get_async_task_status")
        print("🛑 종료하려면 Ctrl+C를 누르세요")

        # 메인 스레드에서 대기
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⛔ 시스템 종료 중...")
        print("👋 안녕히 가세요!")

if __name__ == "__main__":
    main()