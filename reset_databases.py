#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
RDB(SQLite)와 VectorDB를 완전히 초기화합니다.
"""

import os
import shutil
import sqlite3
from pathlib import Path

def reset_sqlite_databases():
    """SQLite 데이터베이스들을 초기화합니다."""
    print("🗄️ SQLite 데이터베이스 초기화 시작...")
    
    # 초기화할 데이터베이스 파일들
    db_files = [
        'tickets.db',
        'jira_sync.db'
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            try:
                # 데이터베이스 백업 (선택사항)
                backup_file = f"{db_file}.backup"
                shutil.copy2(db_file, backup_file)
                print(f"  📋 {db_file} 백업 생성: {backup_file}")
                
                # 데이터베이스 삭제
                os.remove(db_file)
                print(f"  ✅ {db_file} 삭제 완료")
                
            except Exception as e:
                print(f"  ❌ {db_file} 초기화 실패: {str(e)}")
        else:
            print(f"  ℹ️ {db_file} 파일이 존재하지 않습니다.")
    
    print("✅ SQLite 데이터베이스 초기화 완료")

def reset_vector_database():
    """VectorDB를 초기화합니다."""
    print("🧠 VectorDB 초기화 시작...")
    
    vector_db_path = Path("vector_db")
    
    if vector_db_path.exists():
        try:
            # VectorDB 디렉토리 백업 (선택사항)
            backup_path = Path("vector_db.backup")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(vector_db_path, backup_path)
            print(f"  📋 VectorDB 백업 생성: {backup_path}")
            
            # VectorDB 디렉토리 삭제
            shutil.rmtree(vector_db_path)
            print(f"  ✅ VectorDB 디렉토리 삭제 완료")
            
        except Exception as e:
            print(f"  ❌ VectorDB 초기화 실패: {str(e)}")
    else:
        print("  ℹ️ VectorDB 디렉토리가 존재하지 않습니다.")
    
    print("✅ VectorDB 초기화 완료")

def create_fresh_databases():
    """새로운 데이터베이스들을 생성합니다."""
    print("🆕 새로운 데이터베이스 생성 시작...")
    
    try:
        # SQLite 티켓 데이터베이스 생성
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        # init_database는 __init__에서 자동으로 호출됨
        print("  ✅ tickets.db 테이블 생성 완료")
        
    except Exception as e:
        print(f"  ❌ tickets.db 테이블 생성 실패: {str(e)}")
    
    try:
        # VectorDB 초기화
        from vector_db_models import VectorDBManager
        vector_db = VectorDBManager()
        # _get_or_create_collection은 __init__에서 자동으로 호출됨
        print("  ✅ VectorDB 초기화 완료")
        
    except Exception as e:
        print(f"  ❌ VectorDB 초기화 실패: {str(e)}")
    
    print("✅ 새로운 데이터베이스 생성 완료")

def show_database_status():
    """데이터베이스 상태를 표시합니다."""
    print("\n📊 데이터베이스 상태:")
    
    # SQLite 파일들 확인
    db_files = ['tickets.db', 'jira_sync.db']
    for db_file in db_files:
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            print(f"  📁 {db_file}: {size:,} bytes")
        else:
            print(f"  📁 {db_file}: 존재하지 않음")
    
    # VectorDB 확인
    vector_db_path = Path("vector_db")
    if vector_db_path.exists():
        print(f"  🧠 VectorDB: 존재함")
        # VectorDB 크기 계산
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(vector_db_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
                file_count += 1
        print(f"    - 파일 수: {file_count:,}개")
        print(f"    - 총 크기: {total_size:,} bytes")
    else:
        print(f"  🧠 VectorDB: 존재하지 않음")

def main():
    """메인 함수"""
    print("🚀 데이터베이스 초기화 도구")
    print("=" * 50)
    
    # 현재 상태 표시
    show_database_status()
    
    print("\n⚠️  주의: 이 작업은 모든 데이터를 삭제합니다!")
    confirm = input("계속하시겠습니까? (yes/no): ").lower().strip()
    
    if confirm != 'yes':
        print("❌ 작업이 취소되었습니다.")
        return
    
    print("\n🔄 초기화 시작...")
    
    # 1. 기존 데이터베이스 삭제
    reset_sqlite_databases()
    reset_vector_database()
    
    # 2. 새로운 데이터베이스 생성
    create_fresh_databases()
    
    print("\n🎉 모든 데이터베이스가 성공적으로 초기화되었습니다!")
    
    # 최종 상태 표시
    show_database_status()

if __name__ == "__main__":
    main() 