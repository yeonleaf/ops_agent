#!/usr/bin/env python3
"""
Vector DB 저장 테스트
"""

from models.unified_chunk import create_file_unified_chunk
from vector_db_models import VectorDBManager

print("=" * 60)
print("🧪 Vector DB 저장 테스트")
print("=" * 60)

# VectorDBManager 초기화
print("\n[1] VectorDBManager 초기화")
try:
    vector_db = VectorDBManager()
    print("✅ 초기화 성공!")
except Exception as e:
    print(f"❌ 초기화 실패: {e}")
    exit(1)

# UnifiedChunk 생성
print("\n[2] UnifiedChunk 생성")
try:
    chunk = create_file_unified_chunk(
        text_chunk="이것은 테스트 문서입니다. ChromaDB에 저장할 샘플 텍스트입니다.",
        file_name="test_document.pdf",
        file_hash="test_hash_123",
        file_type="pdf",
        file_size=1024,
        architecture="dual_path_hybrid",
        processing_method="pdf_text_extraction",
        vision_analysis=False,
        section_title="테스트 섹션",
        page_number=1,
        element_count=1,
        elements=[{
            "element_type": "text",
            "content": "샘플 텍스트"
        }]
    )
    print("✅ UnifiedChunk 생성 성공!")
    print(f"   - chunk_id: {chunk.chunk_id}")
    print(f"   - data_source: {chunk.data_source}")
    print(f"   - file_name: {chunk.file_metadata['file_name']}")
except Exception as e:
    print(f"❌ 생성 실패: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Vector DB 저장
print("\n[3] Vector DB에 저장")
try:
    vector_db.add_unified_chunk(chunk)
    print("✅ 저장 성공!")
except Exception as e:
    print(f"❌ 저장 실패: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 검색 테스트
print("\n[4] 검색 테스트")
try:
    from chromadb_singleton import get_chromadb_client
    client = get_chromadb_client()
    collection = client.get_collection("file_chunks")

    results = collection.query(
        query_texts=["테스트 문서"],
        n_results=1,
        include=["metadatas", "documents"]
    )

    if results['ids']:
        print("✅ 검색 성공!")
        print(f"   - 검색된 chunk_id: {results['ids'][0][0]}")
        print(f"   - data_source: {results['metadatas'][0][0].get('data_source', 'N/A')}")
        print(f"   - file_name: {results['metadatas'][0][0].get('file_name', 'N/A')}")

        # None 값 확인
        metadata = results['metadatas'][0][0]
        none_values = [k for k, v in metadata.items() if v is None]
        if none_values:
            print(f"   ⚠️ None 값 발견: {none_values}")
        else:
            print(f"   ✅ None 값 없음 (ChromaDB 호환)")
    else:
        print("❌ 검색 결과 없음")
except Exception as e:
    print(f"❌ 검색 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ Vector DB 저장 테스트 완료!")
print("=" * 60)
