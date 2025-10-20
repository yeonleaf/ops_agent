#!/usr/bin/env python3
"""
비동기 티켓 시스템 실행 스크립트
API 서버와 Streamlit UI를 함께 실행
"""

import subprocess
import sys
import time
import threading
import os
from pathlib import Path

def run_api_server():
    """API 서버 실행"""
    print("🌟 API 서버 시작...")
    try:
        subprocess.run([
            sys.executable, "async_task_api.py"
        ], check=True)
    except KeyboardInterrupt:
        print("⛔ API 서버 종료")
    except Exception as e:
        print(f"❌ API 서버 실행 오류: {e}")

def run_streamlit_ui():
    """Streamlit UI 실행"""
    print("🎨 Streamlit UI 시작...")
    time.sleep(3)  # API 서버가 먼저 시작되도록 3초 대기
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "async_ticket_ui.py",
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
        "async_task_api.py",
        "async_ticket_ui.py",
        "async_task_models.py",
        "async_ticket_processor.py",
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
        print("✅ 필수 의존성 확인 완료")
        return True
    except ImportError as e:
        print(f"❌ 필요한 패키지가 설치되지 않았습니다: {e}")
        print("다음 명령어로 설치하세요:")
        print("pip install fastapi uvicorn streamlit requests")
        return False

def main():
    """메인 함수"""
    print("🚀 비동기 티켓 시스템 시작")
    print("=" * 50)

    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)

    # logs 디렉토리 생성
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    print("📂 로그 디렉토리 생성 완료")
    print("🔧 시스템 구성 요소:")
    print("  - API 서버: http://localhost:8001")
    print("  - Streamlit UI: http://localhost:8501")
    print("=" * 50)

    try:
        # 두 프로세스를 병렬로 실행
        api_thread = threading.Thread(target=run_api_server, daemon=True)
        ui_thread = threading.Thread(target=run_streamlit_ui, daemon=True)

        api_thread.start()
        ui_thread.start()

        print("✅ 시스템이 시작되었습니다!")
        print("📱 브라우저에서 http://localhost:8501 에 접속하세요")
        print("🛑 종료하려면 Ctrl+C를 누르세요")

        # 메인 스레드에서 대기
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⛔ 시스템 종료 중...")
        print("👋 안녕히 가세요!")

if __name__ == "__main__":
    main()