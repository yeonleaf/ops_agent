#!/usr/bin/env python3
"""
UnifiedChunk 모델 - 파일과 Jira 데이터를 통합 관리하는 청크 모델

현재 단계에서는 파일 데이터만 처리하며, Jira 일배치는 향후 확장 예정입니다.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


@dataclass
class UnifiedChunk:
    """
    통합 청크 모델 - 파일과 Jira 데이터를 통합 관리

    현재 버전:
        - data_source는 항상 "file"
        - file_metadata에 모든 파일 관련 정보 저장
        - jira_metadata는 항상 None (향후 Jira 일배치 개발 시 사용)

    향후 Jira 일배치 추가 시:
        - data_source = "jira"
        - jira_metadata에 티켓 정보 저장
        - file_metadata = None

    Attributes:
        chunk_id: 고유 청크 ID
        data_source: 데이터 소스 ("file" 또는 "jira")
        text_chunk: 임베딩할 텍스트 내용
        created_at: 생성 시각 (ISO 8601 형식)
        updated_at: 수정 시각 (ISO 8601 형식)
        file_metadata: 파일 전용 메타데이터 (현재 사용 중)
        jira_metadata: Jira 전용 메타데이터 (향후 사용 예정)
    """

    # ===== 공통 필수 필드 =====
    chunk_id: str
    data_source: str  # "file" 또는 "jira"
    text_chunk: str
    created_at: str
    updated_at: str

    # ===== 소스별 메타데이터 =====
    file_metadata: Optional[Dict[str, Any]] = None
    jira_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """
        데이터 일관성 검증

        Raises:
            ValueError: 유효하지 않은 data_source 또는 메타데이터 구조
        """
        # data_source 검증
        if self.data_source not in ["file", "jira"]:
            raise ValueError(f"Invalid data_source: {self.data_source}. Must be 'file' or 'jira'")

        # 메타데이터 일관성 검증
        if self.data_source == "file" and self.file_metadata is None:
            raise ValueError("file_metadata is required when data_source='file'")

        if self.data_source == "jira" and self.jira_metadata is None:
            raise ValueError("jira_metadata is required when data_source='jira'")

    def to_dict(self) -> Dict[str, Any]:
        """
        딕셔너리로 변환

        Returns:
            딕셔너리 형식의 청크 데이터
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedChunk':
        """
        딕셔너리에서 UnifiedChunk 생성

        Args:
            data: 청크 데이터 딕셔너리

        Returns:
            UnifiedChunk 인스턴스
        """
        return cls(**data)

    def get_metadata_summary(self) -> str:
        """
        메타데이터 요약 정보 반환

        Returns:
            메타데이터 요약 문자열
        """
        if self.data_source == "file" and self.file_metadata:
            file_name = self.file_metadata.get("file_name", "Unknown")
            file_type = self.file_metadata.get("file_type", "Unknown")
            page_num = self.file_metadata.get("page_number", "N/A")
            return f"File: {file_name} (Type: {file_type}, Page: {page_num})"

        elif self.data_source == "jira" and self.jira_metadata:
            ticket_id = self.jira_metadata.get("ticket_id", "Unknown")
            chunk_type = self.jira_metadata.get("chunk_type", "Unknown")
            return f"Jira: {ticket_id} (Type: {chunk_type})"

        return f"UnifiedChunk ({self.data_source})"


def file_chunk_to_unified(file_chunk: Any) -> UnifiedChunk:
    """
    기존 FileChunk를 UnifiedChunk로 변환

    Args:
        file_chunk: FileChunk 객체 (또는 FileChunk 호환 객체)

    Returns:
        UnifiedChunk 인스턴스
        - data_source = "file"
        - file_metadata = 모든 파일 관련 정보
        - jira_metadata = None (향후 Jira 일배치 개발 시 사용)

    Example:
        >>> from vector_db_models import FileChunk
        >>> file_chunk = FileChunk(
        ...     chunk_id="abc123",
        ...     file_name="document.pdf",
        ...     file_hash="hash123",
        ...     text_chunk="Sample text",
        ...     architecture="dual_path_hybrid",
        ...     processing_method="pdf_text_extraction",
        ...     vision_analysis=False,
        ...     section_title="Introduction",
        ...     page_number=1,
        ...     element_count=5,
        ...     file_type="pdf",
        ...     elements=[],
        ...     created_at="2025-10-23T12:00:00",
        ...     file_size=1024,
        ...     processing_duration=0.5
        ... )
        >>> unified_chunk = file_chunk_to_unified(file_chunk)
        >>> assert unified_chunk.data_source == "file"
        >>> assert unified_chunk.file_metadata["file_name"] == "document.pdf"
        >>> assert unified_chunk.jira_metadata is None
    """
    # 현재 시각
    now = datetime.now().isoformat()

    # FileChunk의 모든 파일 관련 정보를 file_metadata로 이동
    file_metadata = {
        "file_name": getattr(file_chunk, "file_name", ""),
        "file_hash": getattr(file_chunk, "file_hash", ""),
        "file_type": getattr(file_chunk, "file_type", ""),
        "file_size": getattr(file_chunk, "file_size", 0),
        "architecture": getattr(file_chunk, "architecture", ""),
        "processing_method": getattr(file_chunk, "processing_method", ""),
        "vision_analysis": getattr(file_chunk, "vision_analysis", False),
        "processing_duration": getattr(file_chunk, "processing_duration", 0.0),
        "section_title": getattr(file_chunk, "section_title", ""),
        "page_number": getattr(file_chunk, "page_number", 1),
        "element_count": getattr(file_chunk, "element_count", 0),
        "elements": getattr(file_chunk, "elements", [])
    }

    # UnifiedChunk 생성
    unified_chunk = UnifiedChunk(
        chunk_id=getattr(file_chunk, "chunk_id", str(uuid.uuid4())),
        data_source="file",  # 현재는 항상 "file"
        text_chunk=getattr(file_chunk, "text_chunk", ""),
        created_at=getattr(file_chunk, "created_at", now),
        updated_at=now,
        file_metadata=file_metadata,
        jira_metadata=None  # 향후 Jira 일배치 개발 시 사용
    )

    return unified_chunk


def create_file_unified_chunk(
    text_chunk: str,
    file_name: str,
    file_hash: str,
    file_type: str,
    file_size: int,
    architecture: str = "unknown",
    processing_method: str = "unknown",
    vision_analysis: bool = False,
    processing_duration: float = 0.0,
    section_title: str = "",
    page_number: int = 1,
    element_count: int = 0,
    elements: Optional[List[Dict[str, Any]]] = None,
    chunk_id: Optional[str] = None
) -> UnifiedChunk:
    """
    파일 데이터로부터 UnifiedChunk를 직접 생성하는 헬퍼 함수

    Args:
        text_chunk: 임베딩할 텍스트
        file_name: 파일명
        file_hash: 파일 해시
        file_type: 파일 타입 (pdf, docx, pptx, xlsx, etc.)
        file_size: 파일 크기 (bytes)
        architecture: 처리 아키텍처
        processing_method: 처리 방법
        vision_analysis: Vision 분석 사용 여부
        processing_duration: 처리 시간 (초)
        section_title: 섹션 제목
        page_number: 페이지 번호
        element_count: 요소 개수
        elements: 요소 상세 정보
        chunk_id: 청크 ID (None이면 자동 생성)

    Returns:
        UnifiedChunk 인스턴스
    """
    now = datetime.now().isoformat()

    file_metadata = {
        "file_name": file_name,
        "file_hash": file_hash,
        "file_type": file_type,
        "file_size": file_size,
        "architecture": architecture,
        "processing_method": processing_method,
        "vision_analysis": vision_analysis,
        "processing_duration": processing_duration,
        "section_title": section_title,
        "page_number": page_number,
        "element_count": element_count,
        "elements": elements or []
    }

    return UnifiedChunk(
        chunk_id=chunk_id or str(uuid.uuid4()),
        data_source="file",
        text_chunk=text_chunk,
        created_at=now,
        updated_at=now,
        file_metadata=file_metadata,
        jira_metadata=None
    )


def create_jira_unified_chunk(
    text_chunk: str,
    ticket_id: str,
    chunk_type: str,
    field_name: str,
    field_value: str,
    priority: int = 3,
    ticket_summary: str = "",
    ticket_status: str = "",
    ticket_priority: str = "",
    ticket_type: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    chunk_id: Optional[str] = None
) -> UnifiedChunk:
    """
    Jira 데이터로부터 UnifiedChunk를 생성하는 헬퍼 함수 (향후 사용)

    주의: 현재 버전에서는 사용하지 않음. Jira 일배치 개발 시 활성화 예정.

    Args:
        text_chunk: 임베딩할 텍스트
        ticket_id: Jira 티켓 ID
        chunk_type: 청크 타입 (header, comment, etc.)
        field_name: 필드명
        field_value: 필드값
        priority: 우선순위 (1: 높음, 2: 중간, 3: 낮음)
        ticket_summary: 티켓 요약
        ticket_status: 티켓 상태
        ticket_priority: 티켓 우선순위
        ticket_type: 티켓 타입
        metadata: 추가 메타데이터
        chunk_id: 청크 ID (None이면 자동 생성)

    Returns:
        UnifiedChunk 인스턴스
    """
    now = datetime.now().isoformat()

    jira_metadata = {
        "ticket_id": ticket_id,
        "chunk_type": chunk_type,
        "field_name": field_name,
        "field_value": field_value,
        "priority": priority,
        "ticket_summary": ticket_summary,
        "ticket_status": ticket_status,
        "ticket_priority": ticket_priority,
        "ticket_type": ticket_type,
        **(metadata or {})
    }

    return UnifiedChunk(
        chunk_id=chunk_id or str(uuid.uuid4()),
        data_source="jira",
        text_chunk=text_chunk,
        created_at=now,
        updated_at=now,
        file_metadata=None,
        jira_metadata=jira_metadata
    )
