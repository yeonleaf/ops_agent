#!/usr/bin/env python3
"""
데이터베이스 초기화 및 재생성 스크립트
"""

import os
import shutil
from pathlib import Path

def reset_databases():
    """Vector DB와 RDB를 초기화하고 재생성"""
    
    print("🗑️ 데이터베이스 초기화 시작")
    print("=" * 50)
    
    # 1. Vector DB 초기화
    print("1️⃣ Vector DB 초기화")
    vector_db_path = Path("vector_db")
    
    if vector_db_path.exists():
        try:
            shutil.rmtree(vector_db_path)
            print("   ✅ 기존 Vector DB 삭제 완료")
        except Exception as e:
            print(f"   ❌ Vector DB 삭제 실패: {e}")
    
    # Vector DB 재생성
    try:
        vector_db_path.mkdir(exist_ok=True)
        print("   ✅ Vector DB 디렉토리 재생성 완료")
    except Exception as e:
        print(f"   ❌ Vector DB 재생성 실패: {e}")
    
    print()
    
    # 2. RDB (SQLite) 초기화
    print("2️⃣ RDB (SQLite) 초기화")
    
    # 데이터베이스 파일들 찾기
    db_files = list(Path(".").glob("*.db"))
    
    if db_files:
        for db_file in db_files:
            try:
                db_file.unlink()
                print(f"   ✅ {db_file.name} 삭제 완료")
            except Exception as e:
                print(f"   ❌ {db_file.name} 삭제 실패: {e}")
    else:
        print("   ℹ️ 삭제할 데이터베이스 파일이 없습니다.")
    
    print()
    
    # 3. 데이터베이스 재생성 테스트
    print("3️⃣ 데이터베이스 재생성 테스트")
    
    try:
        # SQLite 데이터베이스 재생성
        from sqlite_ticket_models import SQLiteTicketManager
        ticket_manager = SQLiteTicketManager()
        print("   ✅ SQLite 티켓 데이터베이스 재생성 완료")
        
        # Vector DB 재생성
        from vector_db_models import VectorDBManager
        vector_db = VectorDBManager()
        print("   ✅ Vector DB 재생성 완료")
        
    except Exception as e:
        print(f"   ❌ 데이터베이스 재생성 실패: {e}")
        return False
    
    print()
    print("🎉 데이터베이스 초기화 및 재생성 완료!")
    return True

def verify_clean_state():
    """깨끗한 상태 확인"""
    
    print("🔍 깨끗한 상태 확인")
    print("=" * 50)
    
    # Vector DB 확인
    vector_db_path = Path("vector_db")
    if vector_db_path.exists():
        vector_files = list(vector_db_path.iterdir())
        print(f"   📁 Vector DB: {len(vector_files)}개 파일")
        if vector_files:
            for file in vector_files:
                print(f"      - {file.name}")
        else:
            print("      ✅ Vector DB가 비어있습니다.")
    else:
        print("   ❌ Vector DB 디렉토리가 없습니다.")
    
    # RDB 확인
    db_files = list(Path(".").glob("*.db"))
    if db_files:
        print(f"   🗄️ RDB 파일: {len(db_files)}개")
        for db_file in db_files:
            print(f"      - {db_file.name}")
    else:
        print("   ✅ RDB 파일이 없습니다.")
    
    print()
    print("🎯 초기화 완료! 이제 새로운 데이터로 시작할 수 있습니다.")

if __name__ == "__main__":
    print("🚀 데이터베이스 초기화 스크립트 실행")
    print()
    
    success = reset_databases()
    
    if success:
        print()
        verify_clean_state()
    else:
        print("❌ 데이터베이스 초기화에 실패했습니다.")
        print("🔧 오류를 확인하고 수정해주세요.")
