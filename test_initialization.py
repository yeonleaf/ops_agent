#!/usr/bin/env python3
"""
데이터베이스 초기화 상태 테스트
"""

from database_models import DatabaseManager
from vector_db_models import VectorDBManager

def test_initialization():
    """데이터베이스 초기화 상태 테스트"""
    print("=== 데이터베이스 초기화 상태 테스트 ===")
    
    # 1. RDB 초기화 테스트
    print("\n1. RDB (SQLite) 초기화 테스트:")
    try:
        db_manager = DatabaseManager()
        tickets = db_manager.get_all_tickets()
        print(f"   ✅ RDB 연결 성공")
        print(f"   📊 티켓 수: {len(tickets)}개")
        
        if len(tickets) == 0:
            print("   🎯 RDB 완전 초기화 완료")
        else:
            print(f"   ⚠️ RDB에 {len(tickets)}개 티켓이 남아있음")
            
    except Exception as e:
        print(f"   ❌ RDB 연결 실패: {e}")
    
    # 2. VectorDB 초기화 테스트
    print("\n2. VectorDB (ChromaDB) 초기화 테스트:")
    try:
        vector_db = VectorDBManager()
        mails = vector_db.get_all_mails()
        print(f"   ✅ VectorDB 연결 성공")
        print(f"   📊 메일 수: {len(mails)}개")
        
        if len(mails) == 0:
            print("   🎯 VectorDB 완전 초기화 완료")
        else:
            print(f"   ⚠️ VectorDB에 {len(mails)}개 메일이 남아있음")
            
    except Exception as e:
        print(f"   ❌ VectorDB 연결 실패: {e}")
    
    # 3. 파일 시스템 확인
    print("\n3. 파일 시스템 확인:")
    import os
    
    # RDB 파일 확인
    if os.path.exists("tickets.db"):
        print("   ❌ tickets.db 파일이 여전히 존재")
    else:
        print("   ✅ tickets.db 파일 삭제 완료")
    
    # VectorDB 폴더 확인
    if os.path.exists("vector_db"):
        print("   ❌ vector_db 폴더가 여전히 존재")
    else:
        print("   ✅ vector_db 폴더 삭제 완료")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_initialization()
