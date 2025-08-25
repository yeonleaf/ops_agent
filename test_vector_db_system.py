#!/usr/bin/env python3
"""
벡터DB 저장 시스템 테스트 스크립트

SystemInfoVectorDBManager의 기능을 테스트합니다.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

def test_vector_db_system():
    """벡터DB 시스템 테스트"""
    print("🚀 SystemInfoVectorDBManager 테스트 시작")
    print("=" * 60)
    
    try:
        # SystemInfoVectorDBManager import
        from vector_db_models import SystemInfoVectorDBManager
        
        # 벡터DB 매니저 초기화
        db_manager = SystemInfoVectorDBManager()
        print("✅ SystemInfoVectorDBManager 초기화 성공")
        print(f"📁 컬렉션명: {db_manager.collection_name}")
        
        # 테스트용 가짜 청크 데이터 생성
        test_chunks = [
            {
                "text_chunk_to_embed": "이것은 테스트용 PPTX 파일의 첫 번째 슬라이드입니다.",
                "metadata": {
                    "architecture": "dual_path_hybrid",
                    "processing_method": "dual_path_hybrid",
                    "vision_analysis": True,
                    "section_title": "테스트 슬라이드 1",
                    "page_number": 1,
                    "element_count": 3,
                    "file_type": "pptx",
                    "elements": [
                        {"element_type": "text", "content": "제목 텍스트"},
                        {"element_type": "image", "content": "테스트 이미지"},
                        {"element_type": "table", "content": "테스트 테이블"}
                    ]
                }
            },
            {
                "text_chunk_to_embed": "이것은 테스트용 PPTX 파일의 두 번째 슬라이드입니다.",
                "metadata": {
                    "architecture": "dual_path_hybrid",
                    "processing_method": "dual_path_hybrid",
                    "vision_analysis": False,
                    "section_title": "테스트 슬라이드 2",
                    "page_number": 2,
                    "element_count": 2,
                    "file_type": "pptx",
                    "elements": [
                        {"element_type": "text", "content": "내용 텍스트"},
                        {"element_type": "list", "content": "테스트 리스트"}
                    ]
                }
            }
        ]
        
        # 테스트용 가짜 파일 내용
        test_file_content = b"This is a test file content for testing vector DB storage."
        test_file_name = "test_sample.pptx"
        test_processing_duration = 1.5
        
        print(f"\n📝 테스트 데이터 준비:")
        print(f"   - 파일명: {test_file_name}")
        print(f"   - 청크 수: {len(test_chunks)}")
        print(f"   - 파일 크기: {len(test_file_content)} bytes")
        print(f"   - 처리 시간: {test_processing_duration}초")
        
        # 1. 첫 번째 저장 테스트
        print(f"\n🔍 1차 저장 테스트 시작...")
        start_time = time.time()
        
        result1 = db_manager.save_file_chunks(
            chunks=test_chunks,
            file_content=test_file_content,
            file_name=test_file_name,
            processing_duration=test_processing_duration
        )
        
        save_time = time.time() - start_time
        print(f"⏱️ 저장 소요 시간: {save_time:.3f}초")
        
        if result1["success"]:
            print(f"✅ 1차 저장 성공!")
            print(f"   - 메시지: {result1['message']}")
            print(f"   - 파일 해시: {result1.get('file_hash', '')[:16]}...")
            print(f"   - 저장된 청크 수: {result1.get('chunks_saved', 0)}")
            print(f"   - 중복 여부: {result1.get('duplicate', False)}")
        else:
            print(f"❌ 1차 저장 실패: {result1.get('error', '알 수 없는 오류')}")
            return
        
        # 2. 중복 파일 테스트 (동일한 내용으로 재저장)
        print(f"\n🔍 2차 저장 테스트 (중복 방지 확인)...")
        start_time = time.time()
        
        result2 = db_manager.save_file_chunks(
            chunks=test_chunks,
            file_content=test_file_content,  # 동일한 내용
            file_name=test_file_name,
            processing_duration=test_processing_duration
        )
        
        save_time = time.time() - start_time
        print(f"⏱️ 저장 소요 시간: {save_time:.3f}초")
        
        if result2["success"]:
            print(f"✅ 2차 저장 성공!")
            print(f"   - 메시지: {result2['message']}")
            print(f"   - 중복 여부: {result2.get('duplicate', False)}")
            
            if result2.get("duplicate", False):
                print("🎯 중복 방지 기능 정상 작동!")
            else:
                print("⚠️  중복 방지 기능이 제대로 작동하지 않음")
        else:
            print(f"❌ 2차 저장 실패: {result2.get('error', '알 수 없는 오류')}")
        
        # 3. 컬렉션 통계 확인
        print(f"\n📊 컬렉션 통계 확인...")
        stats = db_manager.get_collection_stats()
        
        if "error" not in stats:
            print(f"✅ 통계 조회 성공!")
            print(f"   - 총 청크 수: {stats['total_chunks']}")
            print(f"   - 총 파일 수: {stats['total_files']}")
            print(f"   - 파일 타입별: {stats['file_types']}")
        else:
            print(f"❌ 통계 조회 실패: {stats['error']}")
        
        # 4. 파일별 청크 조회 테스트
        print(f"\n🔍 파일별 청크 조회 테스트...")
        file_chunks = db_manager.get_file_chunks(test_file_name)
        
        if file_chunks:
            print(f"✅ 파일 청크 조회 성공!")
            print(f"   - 조회된 청크 수: {len(file_chunks)}")
            for i, chunk in enumerate(file_chunks, 1):
                print(f"   - 청크 {i}: {chunk['metadata'].get('section_title', '제목 없음')}")
        else:
            print(f"❌ 파일 청크 조회 실패")
        
        # 5. 유사 청크 검색 테스트
        print(f"\n🔍 유사 청크 검색 테스트...")
        search_results = db_manager.search_similar_chunks(
            query="테스트 슬라이드",
            n_results=3
        )
        
        if search_results:
            print(f"✅ 검색 성공!")
            print(f"   - 검색 결과 수: {len(search_results)}")
            for i, result in enumerate(search_results, 1):
                similarity = result.get('similarity_score', 0)
                title = result['metadata'].get('section_title', '제목 없음')
                print(f"   - 결과 {i}: {title} (유사도: {similarity:.3f})")
        else:
            print(f"❌ 검색 실패")
        
        # 6. 다른 파일명으로 저장 테스트 (해시는 동일하지만 파일명이 다른 경우)
        print(f"\n🔍 다른 파일명 저장 테스트...")
        result3 = db_manager.save_file_chunks(
            chunks=test_chunks,
            file_content=test_file_content,  # 동일한 내용 (동일한 해시)
            file_name="different_name.pptx",  # 다른 파일명
            processing_duration=test_processing_duration
        )
        
        if result3["success"]:
            print(f"✅ 다른 파일명 저장 결과:")
            print(f"   - 메시지: {result3['message']}")
            print(f"   - 중복 여부: {result3.get('duplicate', False)}")
            
            if result3.get("duplicate", False):
                print("🎯 해시 기반 중복 방지 정상 작동!")
            else:
                print("⚠️  해시 기반 중복 방지가 제대로 작동하지 않음")
        else:
            print(f"❌ 다른 파일명 저장 실패: {result3.get('error', '알 수 없는 오류')}")
        
        print(f"\n🎉 모든 테스트 완료!")
        
        # 최종 통계
        final_stats = db_manager.get_collection_stats()
        if "error" not in final_stats:
            print(f"\n📊 최종 컬렉션 상태:")
            print(f"   - 총 청크 수: {final_stats['total_chunks']}")
            print(f"   - 총 파일 수: {final_stats['total_files']}")
            print(f"   - 파일 타입별: {final_stats['file_types']}")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def cleanup_test_data():
    """테스트 데이터 정리"""
    print(f"\n🧹 테스트 데이터 정리...")
    
    try:
        from vector_db_models import SystemInfoVectorDBManager
        
        db_manager = SystemInfoVectorDBManager()
        
        # 컬렉션 초기화
        db_manager.reset_collection()
        print("✅ 테스트 데이터 정리 완료")
        
    except Exception as e:
        print(f"❌ 데이터 정리 실패: {e}")

if __name__ == "__main__":
    print("🚀 벡터DB 저장 시스템 테스트")
    print("=" * 60)
    
    # 테스트 실행
    test_vector_db_system()
    
    # 사용자 선택으로 테스트 데이터 정리
    print(f"\n" + "=" * 60)
    choice = input("테스트 데이터를 정리하시겠습니까? (y/n): ").lower().strip()
    
    if choice in ['y', 'yes', '예']:
        cleanup_test_data()
    else:
        print("테스트 데이터를 유지합니다.")
    
    print("🎉 테스트 완료!") 