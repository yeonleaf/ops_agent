#!/usr/bin/env python3
"""
간단한 데이터베이스 초기화 스크립트
사용자 확인 없이 바로 초기화를 실행합니다.
"""

import os
import shutil
from pathlib import Path

def quick_reset():
    """데이터베이스를 빠르게 초기화합니다."""
    print("🚀 빠른 데이터베이스 초기화 시작...")
    
    # SQLite 데이터베이스 삭제
    db_files = ['tickets.db', 'jira_sync.db']
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"  ✅ {db_file} 삭제 완료")
    
    # VectorDB 디렉토리 삭제
    vector_db_path = Path("vector_db")
    if vector_db_path.exists():
        shutil.rmtree(vector_db_path)
        print("  ✅ VectorDB 삭제 완료")
    
    # 새로운 데이터베이스 생성
    try:
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        print("  ✅ tickets.db 생성 완료")
    except Exception as e:
        print(f"  ❌ tickets.db 생성 실패: {str(e)}")
    
    try:
        from vector_db_models import VectorDBManager
        vector_db = VectorDBManager()
        print("  ✅ VectorDB 생성 완료")
    except Exception as e:
        print(f"  ❌ VectorDB 생성 실패: {str(e)}")
    
    print("🎉 데이터베이스 초기화 완료!")

if __name__ == "__main__":
    quick_reset() 