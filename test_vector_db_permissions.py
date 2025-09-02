#!/usr/bin/env python3
"""
VectorDB 권한 설정 테스트
"""

from vector_db_models import VectorDBManager
from database_models import Mail
from datetime import datetime

def test_vector_db_permissions():
    """VectorDB 권한 설정 테스트"""
    print("=== VectorDB 권한 설정 테스트 ===")
    
    try:
        # 1. VectorDB 매니저 초기화
        print("\n1. VectorDB 매니저 초기화:")
        vector_db = VectorDBManager()
        print("   ✅ VectorDB 매니저 생성 성공")
        
        # 2. 테스트 메일 생성
        print("\n2. 테스트 메일 생성:")
        test_mail = Mail(
            message_id="test_message_001",
            original_content="테스트 메일 내용입니다.",
            refined_content="테스트 메일 내용입니다.",
            sender="test@example.com",
            status="acceptable",
            subject="테스트 메일",
            received_datetime="2025-09-01T21:30:00",
            content_type="text",
            has_attachment=False,
            extraction_method="test",
            content_summary="테스트 메일 요약",
            key_points=["테스트", "권한", "확인"],
            created_at=datetime.now().isoformat()
        )
        print("   ✅ 테스트 메일 생성 성공")
        
        # 3. 메일 저장 테스트
        print("\n3. 메일 저장 테스트:")
        success = vector_db.save_mail(test_mail)
        if success:
            print("   ✅ 메일 저장 성공")
        else:
            print("   ❌ 메일 저장 실패")
        
        # 4. 저장된 메일 조회 테스트
        print("\n4. 저장된 메일 조회 테스트:")
        retrieved_mail = vector_db.get_mail_by_id("test_message_001")
        if retrieved_mail:
            print("   ✅ 메일 조회 성공")
            print(f"   📧 제목: {retrieved_mail.subject}")
            print(f"   👤 발신자: {retrieved_mail.sender}")
            print(f"   🏷️ 키포인트: {retrieved_mail.key_points}")
        else:
            print("   ❌ 메일 조회 실패")
        
        # 5. 권한 확인
        print("\n5. 파일 권한 확인:")
        import os
        vector_db_path = "./vector_db"
        if os.path.exists(vector_db_path):
            print(f"   📁 VectorDB 폴더: {vector_db_path}")
            print(f"   📊 폴더 권한: {oct(os.stat(vector_db_path).st_mode)[-3:]}")
            
            chroma_file = os.path.join(vector_db_path, "chroma.sqlite3")
            if os.path.exists(chroma_file):
                print(f"   💾 ChromaDB 파일: {chroma_file}")
                print(f"   📊 파일 권한: {oct(os.stat(chroma_file).st_mode)[-3:]}")
                print(f"   📏 파일 크기: {os.path.getsize(chroma_file)} bytes")
            else:
                print("   ⚠️ ChromaDB 파일이 아직 생성되지 않음")
        else:
            print("   ❌ VectorDB 폴더가 존재하지 않음")
        
    except Exception as e:
        print(f"   ❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_vector_db_permissions()
