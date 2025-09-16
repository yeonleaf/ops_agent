#!/usr/bin/env python3
"""
개선된 데이터베이스 초기화 스크립트 (DB 락 안전성 강화)
"""

import os
import shutil
import sqlite3
import tempfile
import time
import psutil
from pathlib import Path

def check_db_processes():
    """DB를 사용하는 프로세스 확인"""
    print("🔍 DB 사용 프로세스 확인")
    
    db_users = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'tickets.db' in cmdline or 'python' in proc.info['name'].lower():
                    if proc.info['pid'] != os.getpid():  # 현재 프로세스 제외
                        db_users.append(f"PID {proc.info['pid']}: {proc.info['name']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if db_users:
        print("⚠️ DB를 사용 중인 프로세스들:")
        for user in db_users:
            print(f"   - {user}")
        print("💡 안전한 초기화를 위해 다른 프로세스를 종료하는 것을 권장합니다.")
        
        response = input("계속 진행하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("❌ 사용자가 취소했습니다.")
            return False
    else:
        print("✅ DB를 사용하는 다른 프로세스가 없습니다.")
    
    return True

def safe_db_backup(db_file: Path):
    """안전한 DB 백업 (락 회피)"""
    users_backup = []
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"   시도 {attempt + 1}/{max_retries}: {db_file.name} 백업 중...")
            
            with sqlite3.connect(str(db_file), timeout=10.0) as conn:
                # WAL 모드 설정 (동시성 개선)
                conn.execute("PRAGMA journal_mode=WAL")
                
                cursor = conn.cursor()
                # users 테이블 존재 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if cursor.fetchone():
                    # users 테이블 데이터 백업
                    cursor.execute("SELECT * FROM users")
                    users_backup = cursor.fetchall()
                    print(f"   ✅ {len(users_backup)}개의 사용자 데이터를 백업했습니다.")
                else:
                    print("   ℹ️ users 테이블이 없습니다.")
            
            return users_backup
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(f"   ⚠️ DB 락 감지 (시도 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
                    continue
                else:
                    print("   ❌ 최대 재시도 횟수 초과")
                    raise
            else:
                raise
        except Exception as e:
            print(f"   ❌ 백업 실패: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                raise
    
    return users_backup

def safe_file_deletion(file_path: Path):
    """안전한 파일 삭제 (락 회피)"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"   ✅ {file_path.name} 삭제 완료")
                return True
        except PermissionError:
            print(f"   ⚠️ 파일 락 감지: {file_path.name} (시도 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                print(f"   ❌ {file_path.name} 삭제 실패 - 다른 프로세스에서 사용 중")
                return False
        except Exception as e:
            print(f"   ❌ {file_path.name} 삭제 실패: {e}")
            return False
    
    return False

def safe_reset_databases():
    """개선된 안전한 데이터베이스 초기화"""
    
    print("🚀 개선된 데이터베이스 초기화 시작")
    print("=" * 50)
    
    # 1. 프로세스 확인
    if not check_db_processes():
        return False
    
    print()
    
    # 2. Vector DB 초기화
    print("1️⃣ Vector DB 초기화")
    vector_db_path = Path("vector_db")
    
    if vector_db_path.exists():
        try:
            shutil.rmtree(vector_db_path)
            print("   ✅ 기존 Vector DB 삭제 완료")
        except Exception as e:
            print(f"   ❌ Vector DB 삭제 실패: {e}")
            return False
    
    # Vector DB 재생성
    try:
        vector_db_path.mkdir(exist_ok=True)
        print("   ✅ Vector DB 디렉토리 재생성 완료")
    except Exception as e:
        print(f"   ❌ Vector DB 재생성 실패: {e}")
        return False
    
    print()
    
    # 3. SQLite DB 안전한 초기화
    print("2️⃣ SQLite DB 안전한 초기화 (users 테이블 보존)")
    
    db_files = list(Path(".").glob("*.db"))
    all_users_backup = []
    
    # 백업 단계
    main_db_file = Path("tickets.db")
    if main_db_file.exists():
        all_users_backup = safe_db_backup(main_db_file)
        if all_users_backup is None:
            print("   ❌ 백업 실패로 인한 초기화 중단")
            return False
    
    # 삭제 단계
    deletion_success = True
    if db_files:
        for db_file in db_files:
            if not safe_file_deletion(db_file):
                deletion_success = False
        
        if not deletion_success:
            print("   ⚠️ 일부 DB 파일 삭제 실패, 계속 진행")
    else:
        print("   ℹ️ 삭제할 데이터베이스 파일이 없습니다.")
    
    print()
    
    # 4. 데이터베이스 재생성
    print("3️⃣ 데이터베이스 재생성")
    
    try:
        # SQLite 데이터베이스 재생성
        from database_models import DatabaseManager
        db_manager = DatabaseManager()
        print("   ✅ SQLite 데이터베이스 재생성 완료")
        
        # Vector DB 재생성
        from vector_db_models import VectorDBManager
        vector_db = VectorDBManager()
        print("   ✅ Vector DB 재생성 완료")
        
        # users 테이블 데이터 복원
        if all_users_backup:
            print("4️⃣ users 테이블 데이터 안전 복원")
            try:
                with sqlite3.connect("tickets.db", timeout=30.0) as conn:
                    # WAL 모드 재설정
                    conn.execute("PRAGMA journal_mode=WAL")
                    
                    cursor = conn.cursor()
                    for user_data in all_users_backup:
                        cursor.execute("""
                            INSERT OR REPLACE INTO users
                            (id, email, password_hash, google_refresh_token, jira_endpoint, jira_api_token, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, user_data)
                    conn.commit()
                    print(f"   ✅ {len(all_users_backup)}개의 사용자 데이터를 복원했습니다.")
            except Exception as e:
                print(f"   ❌ users 테이블 데이터 복원 실패: {e}")
                return False
        
    except Exception as e:
        print(f"   ❌ 데이터베이스 재생성 실패: {e}")
        return False
    
    print()
    print("🎉 안전한 데이터베이스 초기화 완료!")
    return True

if __name__ == "__main__":
    print("🔒 안전성 강화된 데이터베이스 초기화 스크립트")
    print()
    
    try:
        success = safe_reset_databases()
        if success:
            print("\n✅ 모든 작업이 성공적으로 완료되었습니다.")
        else:
            print("\n❌ 초기화 작업이 실패했습니다.")
            print("🔧 오류를 확인하고 다시 시도해주세요.")
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 작업을 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
