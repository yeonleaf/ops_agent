#!/usr/bin/env python3
"""
UnifiedChunk 간단한 테스트
"""

from models.unified_chunk import (
    UnifiedChunk,
    create_file_unified_chunk,
    file_chunk_to_unified
)
from vector_db_models import FileChunk
from datetime import datetime

print("=" * 60)
print("🧪 UnifiedChunk 간단한 테스트")
print("=" * 60)

# 테스트 1: create_file_unified_chunk
print("\n[Test 1] create_file_unified_chunk() 테스트")
try:
    chunk = create_file_unified_chunk(
        text_chunk="This is a test document",
        file_name="test.pdf",
        file_hash="abc123",
        file_type="pdf",
        file_size=1024,
        page_number=5
    )
    print(f"✅ 생성 성공!")
    print(f"   - chunk_id: {chunk.chunk_id}")
    print(f"   - data_source: {chunk.data_source}")
    print(f"   - file_name: {chunk.file_metadata['file_name']}")
    print(f"   - page_number: {chunk.file_metadata['page_number']}")
    print(f"   - jira_metadata: {chunk.jira_metadata}")
except Exception as e:
    print(f"❌ 실패: {e}")

# 테스트 2: file_chunk_to_unified
print("\n[Test 2] file_chunk_to_unified() 변환 테스트")
try:
    file_chunk = FileChunk(
        chunk_id="old-123",
        file_name="old_document.pdf",
        file_hash="old_hash",
        text_chunk="Old FileChunk content",
        architecture="dual_path_hybrid",
        processing_method="pdf_extraction",
        vision_analysis=False,
        section_title="Introduction",
        page_number=10,
        element_count=5,
        file_type="pdf",
        elements=[],
        created_at=datetime.now().isoformat(),
        file_size=2048,
        processing_duration=1.0
    )

    unified = file_chunk_to_unified(file_chunk)
    print(f"✅ 변환 성공!")
    print(f"   - chunk_id: {unified.chunk_id}")
    print(f"   - data_source: {unified.data_source}")
    print(f"   - file_name: {unified.file_metadata['file_name']}")
    print(f"   - page_number: {unified.file_metadata['page_number']}")
except Exception as e:
    print(f"❌ 실패: {e}")

# 테스트 3: to_dict / from_dict
print("\n[Test 3] to_dict() / from_dict() 테스트")
try:
    chunk = create_file_unified_chunk(
        text_chunk="Dict test",
        file_name="dict_test.pdf",
        file_hash="dict_hash",
        file_type="pdf",
        file_size=512
    )

    chunk_dict = chunk.to_dict()
    restored = UnifiedChunk.from_dict(chunk_dict)

    print(f"✅ 직렬화/역직렬화 성공!")
    print(f"   - 원본 chunk_id: {chunk.chunk_id}")
    print(f"   - 복원 chunk_id: {restored.chunk_id}")
    print(f"   - 일치 여부: {chunk.chunk_id == restored.chunk_id}")
except Exception as e:
    print(f"❌ 실패: {e}")

# 테스트 4: 메타데이터 요약
print("\n[Test 4] get_metadata_summary() 테스트")
try:
    chunk = create_file_unified_chunk(
        text_chunk="Summary test",
        file_name="summary_test.pdf",
        file_hash="summary_hash",
        file_type="pdf",
        file_size=256,
        page_number=42
    )

    summary = chunk.get_metadata_summary()
    print(f"✅ 요약 생성 성공!")
    print(f"   - {summary}")
except Exception as e:
    print(f"❌ 실패: {e}")

# 테스트 5: 검증 로직
print("\n[Test 5] 데이터 검증 테스트")
try:
    # data_source="file"인데 file_metadata=None (에러 발생 예상)
    now = datetime.now().isoformat()
    chunk = UnifiedChunk(
        chunk_id="test",
        data_source="file",
        text_chunk="Test",
        created_at=now,
        updated_at=now,
        file_metadata=None,
        jira_metadata=None
    )
    print(f"❌ 검증 실패: 에러가 발생해야 함")
except ValueError as e:
    print(f"✅ 검증 성공! 예상된 에러 발생: {e}")
except Exception as e:
    print(f"❌ 예상치 못한 에러: {e}")

print("\n" + "=" * 60)
print("✅ 모든 테스트 완료!")
print("=" * 60)
