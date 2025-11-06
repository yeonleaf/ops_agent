#!/usr/bin/env python3
"""
UnifiedChunk 모델 테스트

테스트 실행:
    python -m pytest tests/test_unified_chunk.py -v
"""

import pytest
import sys
import os
from datetime import datetime
import uuid

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.unified_chunk import (
    UnifiedChunk,
    file_chunk_to_unified,
    create_file_unified_chunk,
    create_jira_unified_chunk
)
from vector_db_models import FileChunk


class TestUnifiedChunkModel:
    """UnifiedChunk 모델 기본 테스트"""

    def test_unified_chunk_creation_file(self):
        """파일 데이터로 UnifiedChunk 생성 테스트"""
        now = datetime.now().isoformat()

        file_metadata = {
            "file_name": "test.pdf",
            "file_hash": "abc123",
            "file_type": "pdf",
            "file_size": 1024,
            "architecture": "dual_path_hybrid",
            "processing_method": "pdf_text_extraction",
            "vision_analysis": False,
            "processing_duration": 0.5,
            "section_title": "Introduction",
            "page_number": 1,
            "element_count": 5,
            "elements": []
        }

        chunk = UnifiedChunk(
            chunk_id="test-123",
            data_source="file",
            text_chunk="This is a test document.",
            created_at=now,
            updated_at=now,
            file_metadata=file_metadata,
            jira_metadata=None
        )

        assert chunk.chunk_id == "test-123"
        assert chunk.data_source == "file"
        assert chunk.text_chunk == "This is a test document."
        assert chunk.file_metadata["file_name"] == "test.pdf"
        assert chunk.jira_metadata is None

    def test_unified_chunk_validation_file(self):
        """파일 데이터 검증 테스트 - file_metadata 필수"""
        now = datetime.now().isoformat()

        with pytest.raises(ValueError, match="file_metadata is required"):
            UnifiedChunk(
                chunk_id="test-123",
                data_source="file",
                text_chunk="Test",
                created_at=now,
                updated_at=now,
                file_metadata=None,  # 필수인데 None
                jira_metadata=None
            )

    def test_unified_chunk_validation_jira(self):
        """Jira 데이터 검증 테스트 - jira_metadata 필수"""
        now = datetime.now().isoformat()

        with pytest.raises(ValueError, match="jira_metadata is required"):
            UnifiedChunk(
                chunk_id="test-123",
                data_source="jira",
                text_chunk="Test",
                created_at=now,
                updated_at=now,
                file_metadata=None,
                jira_metadata=None  # 필수인데 None
            )

    def test_unified_chunk_invalid_data_source(self):
        """잘못된 data_source 검증 테스트"""
        now = datetime.now().isoformat()

        with pytest.raises(ValueError, match="Invalid data_source"):
            UnifiedChunk(
                chunk_id="test-123",
                data_source="invalid",  # 잘못된 값
                text_chunk="Test",
                created_at=now,
                updated_at=now,
                file_metadata={"file_name": "test.pdf"},
                jira_metadata=None
            )

    def test_unified_chunk_to_dict(self):
        """to_dict() 메서드 테스트"""
        chunk = create_file_unified_chunk(
            text_chunk="Test content",
            file_name="test.pdf",
            file_hash="abc123",
            file_type="pdf",
            file_size=1024
        )

        chunk_dict = chunk.to_dict()

        assert isinstance(chunk_dict, dict)
        assert chunk_dict["data_source"] == "file"
        assert chunk_dict["file_metadata"]["file_name"] == "test.pdf"

    def test_unified_chunk_from_dict(self):
        """from_dict() 메서드 테스트"""
        chunk_data = {
            "chunk_id": "test-123",
            "data_source": "file",
            "text_chunk": "Test content",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "file_metadata": {
                "file_name": "test.pdf",
                "file_hash": "abc123",
                "file_type": "pdf",
                "file_size": 1024,
                "architecture": "test",
                "processing_method": "test",
                "vision_analysis": False,
                "processing_duration": 0.0,
                "section_title": "Test",
                "page_number": 1,
                "element_count": 0,
                "elements": []
            },
            "jira_metadata": None
        }

        chunk = UnifiedChunk.from_dict(chunk_data)

        assert chunk.chunk_id == "test-123"
        assert chunk.data_source == "file"
        assert chunk.file_metadata["file_name"] == "test.pdf"

    def test_get_metadata_summary_file(self):
        """get_metadata_summary() 테스트 - 파일 데이터"""
        chunk = create_file_unified_chunk(
            text_chunk="Test",
            file_name="test.pdf",
            file_hash="abc123",
            file_type="pdf",
            file_size=1024,
            page_number=5
        )

        summary = chunk.get_metadata_summary()

        assert "test.pdf" in summary
        assert "pdf" in summary
        assert "5" in summary


class TestFileChunkConversion:
    """FileChunk → UnifiedChunk 변환 테스트"""

    def test_file_chunk_to_unified_conversion(self):
        """file_chunk_to_unified() 함수 테스트"""
        # FileChunk 생성
        file_chunk = FileChunk(
            chunk_id="test-456",
            file_name="document.pdf",
            file_hash="hash456",
            text_chunk="Sample text for testing",
            architecture="dual_path_hybrid",
            processing_method="pdf_text_extraction",
            vision_analysis=False,
            section_title="Chapter 1",
            page_number=2,
            element_count=10,
            file_type="pdf",
            elements=[{"type": "text", "content": "Sample"}],
            created_at=datetime.now().isoformat(),
            file_size=2048,
            processing_duration=1.5
        )

        # UnifiedChunk로 변환
        unified_chunk = file_chunk_to_unified(file_chunk)

        # 검증
        assert unified_chunk.chunk_id == "test-456"
        assert unified_chunk.data_source == "file"
        assert unified_chunk.text_chunk == "Sample text for testing"
        assert unified_chunk.file_metadata["file_name"] == "document.pdf"
        assert unified_chunk.file_metadata["file_hash"] == "hash456"
        assert unified_chunk.file_metadata["file_type"] == "pdf"
        assert unified_chunk.file_metadata["page_number"] == 2
        assert unified_chunk.file_metadata["element_count"] == 10
        assert unified_chunk.jira_metadata is None

    def test_create_file_unified_chunk_helper(self):
        """create_file_unified_chunk() 헬퍼 함수 테스트"""
        chunk = create_file_unified_chunk(
            text_chunk="Test content",
            file_name="test.docx",
            file_hash="hash789",
            file_type="docx",
            file_size=512,
            architecture="simple_conversion",
            processing_method="docx_extraction",
            vision_analysis=False,
            section_title="Section 1",
            page_number=3,
            element_count=7,
            elements=[{"type": "paragraph", "content": "Test"}]
        )

        # 검증
        assert chunk.data_source == "file"
        assert chunk.text_chunk == "Test content"
        assert chunk.file_metadata["file_name"] == "test.docx"
        assert chunk.file_metadata["file_type"] == "docx"
        assert chunk.file_metadata["architecture"] == "simple_conversion"
        assert chunk.file_metadata["page_number"] == 3
        assert chunk.jira_metadata is None

    def test_create_file_unified_chunk_default_values(self):
        """create_file_unified_chunk() 기본값 테스트"""
        chunk = create_file_unified_chunk(
            text_chunk="Test",
            file_name="test.txt",
            file_hash="hash000",
            file_type="txt",
            file_size=100
        )

        # 기본값 검증
        assert chunk.file_metadata["architecture"] == "unknown"
        assert chunk.file_metadata["processing_method"] == "unknown"
        assert chunk.file_metadata["vision_analysis"] is False
        assert chunk.file_metadata["page_number"] == 1
        assert chunk.file_metadata["element_count"] == 0
        assert chunk.file_metadata["elements"] == []


class TestJiraChunkCreation:
    """Jira UnifiedChunk 생성 테스트 (향후 사용)"""

    def test_create_jira_unified_chunk(self):
        """create_jira_unified_chunk() 헬퍼 함수 테스트"""
        chunk = create_jira_unified_chunk(
            text_chunk="Jira ticket summary",
            ticket_id="PROJ-123",
            chunk_type="summary",
            field_name="Summary",
            field_value="Implement feature X",
            priority=1,
            ticket_summary="Implement feature X",
            ticket_status="In Progress",
            ticket_priority="High",
            ticket_type="Task"
        )

        # 검증
        assert chunk.data_source == "jira"
        assert chunk.text_chunk == "Jira ticket summary"
        assert chunk.jira_metadata["ticket_id"] == "PROJ-123"
        assert chunk.jira_metadata["chunk_type"] == "summary"
        assert chunk.jira_metadata["priority"] == 1
        assert chunk.file_metadata is None

    def test_jira_chunk_metadata_structure(self):
        """Jira 메타데이터 구조 테스트"""
        chunk = create_jira_unified_chunk(
            text_chunk="Test",
            ticket_id="PROJ-456",
            chunk_type="comment",
            field_name="Comment",
            field_value="This is a comment"
        )

        # Jira 메타데이터 필드 확인
        assert "ticket_id" in chunk.jira_metadata
        assert "chunk_type" in chunk.jira_metadata
        assert "field_name" in chunk.jira_metadata
        assert "field_value" in chunk.jira_metadata
        assert "priority" in chunk.jira_metadata


class TestIntegration:
    """통합 테스트"""

    def test_full_workflow_file_chunk_to_unified(self):
        """FileChunk → UnifiedChunk 전체 워크플로우 테스트"""
        # 1. FileChunk 생성
        file_chunk = FileChunk(
            chunk_id=str(uuid.uuid4()),
            file_name="workflow_test.pdf",
            file_hash="workflow_hash",
            text_chunk="This is a workflow test",
            architecture="dual_path_hybrid",
            processing_method="test",
            vision_analysis=False,
            section_title="Test Section",
            page_number=1,
            element_count=1,
            file_type="pdf",
            elements=[],
            created_at=datetime.now().isoformat(),
            file_size=100,
            processing_duration=0.1
        )

        # 2. UnifiedChunk로 변환
        unified_chunk = file_chunk_to_unified(file_chunk)

        # 3. 딕셔너리로 변환
        chunk_dict = unified_chunk.to_dict()

        # 4. 다시 UnifiedChunk로 복원
        restored_chunk = UnifiedChunk.from_dict(chunk_dict)

        # 5. 검증
        assert restored_chunk.chunk_id == unified_chunk.chunk_id
        assert restored_chunk.data_source == "file"
        assert restored_chunk.text_chunk == "This is a workflow test"
        assert restored_chunk.file_metadata["file_name"] == "workflow_test.pdf"

    def test_metadata_summary_output(self):
        """메타데이터 요약 출력 테스트"""
        # 파일 청크
        file_chunk = create_file_unified_chunk(
            text_chunk="Test",
            file_name="summary_test.pdf",
            file_hash="summary_hash",
            file_type="pdf",
            file_size=100,
            page_number=10
        )

        file_summary = file_chunk.get_metadata_summary()
        assert "summary_test.pdf" in file_summary
        assert "pdf" in file_summary
        assert "10" in file_summary

        # Jira 청크
        jira_chunk = create_jira_unified_chunk(
            text_chunk="Test",
            ticket_id="PROJ-789",
            chunk_type="description",
            field_name="Description",
            field_value="Test description"
        )

        jira_summary = jira_chunk.get_metadata_summary()
        assert "PROJ-789" in jira_summary
        assert "description" in jira_summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
