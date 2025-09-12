#!/usr/bin/env python3
"""
ChromaDB 재설정 스크립트
기존 ChromaDB 인스턴스와의 충돌을 해결하기 위한 완전 재설정
"""

import os
import shutil
import sys
from pathlib import Path

def reset_chromadb():
    """ChromaDB 완전 재설정"""
    vector_db_path = "./vector_db"
    
    print("🔄 ChromaDB 완전 재설정을 시작합니다...")
    
    try:
        # 1. 실행 중인 Python 프로세스 정리
        print("🔄 실행 중인 Python 프로세스 정리 중...")
        try:
            import subprocess
            subprocess.run(["pkill", "-f", "python"], capture_output=True)
            print("✅ Python 프로세스 정리 완료")
        except:
            print("⚠️ 프로세스 정리 중 오류 (무시하고 계속)")
        
        # 2. 기존 vector_db 디렉토리 완전 삭제
        if os.path.exists(vector_db_path):
            shutil.rmtree(vector_db_path)
            print(f"✅ 기존 vector_db 디렉토리를 완전 삭제했습니다.")
        
        # 3. 백업 디렉토리도 삭제 (완전 정리)
        backup_path = "./vector_db_backup"
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            print(f"✅ 백업 디렉토리도 삭제했습니다.")
        
        # 4. 새로운 vector_db 디렉토리 생성
        os.makedirs(vector_db_path, mode=0o755, exist_ok=True)
        print(f"✅ 새로운 vector_db 디렉토리를 생성했습니다: {vector_db_path}")
        
        # 5. 권한 설정
        os.chmod(vector_db_path, 0o755)
        print(f"✅ vector_db 디렉토리 권한을 설정했습니다.")
        
        # 4. ChromaDB 테스트
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=vector_db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 테스트 컬렉션 생성
            test_collection = client.create_collection(
                name="test_collection",
                metadata={"description": "Test collection for ChromaDB reset"}
            )
            
            # 테스트 데이터 추가
            test_collection.add(
                documents=["This is a test document"],
                metadatas=[{"test": True}],
                ids=["test_id"]
            )
            
            # 테스트 데이터 조회
            result = test_collection.get(ids=["test_id"])
            if result['ids']:
                print("✅ ChromaDB 테스트 성공!")
            else:
                print("❌ ChromaDB 테스트 실패!")
                return False
            
            # 테스트 컬렉션 삭제
            client.delete_collection("test_collection")
            print("✅ 테스트 컬렉션 정리 완료!")
            
        except Exception as e:
            print(f"❌ ChromaDB 테스트 실패: {e}")
            return False
        
        print("🎉 ChromaDB 재설정이 완료되었습니다!")
        print("이제 UI에서 파일 업로드 및 임베딩을 다시 시도해보세요.")
        
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB 재설정 실패: {e}")
        return False

def restore_backup():
    """백업에서 복원"""
    backup_path = "./vector_db_backup"
    vector_db_path = "./vector_db"
    
    if not os.path.exists(backup_path):
        print("❌ 백업 파일이 없습니다.")
        return False
    
    try:
        if os.path.exists(vector_db_path):
            shutil.rmtree(vector_db_path)
        
        shutil.move(backup_path, vector_db_path)
        print("✅ 백업에서 복원했습니다.")
        return True
        
    except Exception as e:
        print(f"❌ 백업 복원 실패: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_backup()
    else:
        reset_chromadb()
