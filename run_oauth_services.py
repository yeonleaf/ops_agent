#!/usr/bin/env python3
"""
OAuth 서비스 실행 스크립트
OAuth 서버와 MCP 서버를 동시에 실행
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

def run_oauth_server():
    """OAuth 서버 실행"""
    print("🔄 OAuth 서버 시작 중...")
    try:
        subprocess.run([
            sys.executable, "oauth_auth_server.py"
        ], check=True)
    except KeyboardInterrupt:
        print("🛑 OAuth 서버 중지됨")
    except Exception as e:
        print(f"❌ OAuth 서버 실행 실패: {e}")

def run_mcp_server():
    """MCP 서버 실행"""
    print("🔄 MCP 서버 시작 중...")
    try:
        subprocess.run([
            sys.executable, "secure_mcp_server.py"
        ], check=True)
    except KeyboardInterrupt:
        print("🛑 MCP 서버 중지됨")
    except Exception as e:
        print(f"❌ MCP 서버 실행 실패: {e}")

def run_streamlit_app():
    """Streamlit 앱 실행"""
    print("🔄 Streamlit 앱 시작 중...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "oauth_client_integration.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ], check=True)
    except KeyboardInterrupt:
        print("🛑 Streamlit 앱 중지됨")
    except Exception as e:
        print(f"❌ Streamlit 앱 실행 실패: {e}")

def check_dependencies():
    """의존성 확인"""
    required_packages = [
        "fastapi", "uvicorn", "requests", "streamlit", 
        "python-multipart", "python-jose", "passlib"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 누락된 패키지: {', '.join(missing_packages)}")
        print("다음 명령어로 설치하세요:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    """메인 실행 함수"""
    print("🚀 OAuth 이메일 서비스 시작")
    print("=" * 50)
    
    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)
    
    # 환경 설정 확인
    if not os.path.exists(".env"):
        print("⚠️ .env 파일이 없습니다.")
        print("oauth_config.env 파일을 .env로 복사하세요:")
        print("cp oauth_config.env .env")
        print("그리고 OAuth 설정을 입력하세요.")
        sys.exit(1)
    
    print("✅ 의존성 확인 완료")
    print("✅ 환경 설정 확인 완료")
    
    # 서비스 실행
    try:
        # OAuth 서버를 별도 스레드에서 실행
        oauth_thread = threading.Thread(target=run_oauth_server, daemon=True)
        oauth_thread.start()
        
        # 잠시 대기
        time.sleep(2)
        
        # MCP 서버를 별도 스레드에서 실행
        mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
        mcp_thread.start()
        
        # 잠시 대기
        time.sleep(2)
        
        # Streamlit 앱 실행 (메인 스레드)
        run_streamlit_app()
        
    except KeyboardInterrupt:
        print("\n🛑 모든 서비스 중지됨")
    except Exception as e:
        print(f"❌ 서비스 실행 실패: {e}")

if __name__ == "__main__":
    main()
