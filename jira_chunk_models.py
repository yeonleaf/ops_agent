#!/usr/bin/env python3
"""
Jira 티켓 데이터 전문화된 청킹을 위한 모델
하나의 티켓을 여러 개의 전문화된 청크로 분할
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class JiraChunkType(Enum):
    """Jira 청크 타입"""
    SUMMARY = "summary"           # 요약 청크
    DESCRIPTION = "description"   # 설명 청크
    COMMENT = "comment"          # 댓글 청크
    METADATA = "metadata"        # 메타데이터 청크 (상태, 우선순위 등)


@dataclass
class JiraChunk:
    """Jira 전문화된 청크 모델"""
    # 기본 식별자
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticket_id: str = ""  # 원본 티켓 ID (예: T-001)
    
    # 청크 타입 및 내용
    chunk_type: JiraChunkType = JiraChunkType.SUMMARY
    content: str = ""  # 임베딩할 텍스트 내용
    
    # 필드별 메타데이터
    field_name: str = ""  # 원본 필드명 (summary, description, comment 등)
    field_value: str = ""  # 원본 필드값
    
    # 댓글 관련 메타데이터 (comment 타입일 때만)
    comment_author: Optional[str] = None
    comment_date: Optional[str] = None
    comment_id: Optional[str] = None
    
    # 티켓 메타데이터 (모든 청크에 공통)
    ticket_summary: str = ""  # 티켓 요약 (참조용)
    ticket_status: str = ""
    ticket_priority: str = ""
    ticket_type: str = ""
    ticket_assignee: Optional[str] = None
    ticket_reporter: str = ""
    ticket_created: str = ""
    ticket_updated: str = ""
    
    # 청크 우선순위 (검색 시 가중치용)
    priority_score: int = 1  # 1: 높음, 2: 중간, 3: 낮음
    
    # 처리 메타데이터
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    file_name: str = ""  # 원본 파일명
    processing_method: str = "jira_specialized_chunking"
    
    # 추가 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_vector_db_dict(self) -> Dict[str, Any]:
        """Vector DB 저장용 딕셔너리로 변환"""
        return {
            "chunk_id": self.chunk_id,
            "ticket_id": self.ticket_id,
            "chunk_type": self.chunk_type.value,
            "content": self.content,
            "field_name": self.field_name,
            "field_value": self.field_value,
            "comment_author": self.comment_author,
            "comment_date": self.comment_date,
            "comment_id": self.comment_id,
            "ticket_summary": self.ticket_summary,
            "ticket_status": self.ticket_status,
            "ticket_priority": self.ticket_priority,
            "ticket_type": self.ticket_type,
            "ticket_assignee": self.ticket_assignee,
            "ticket_reporter": self.ticket_reporter,
            "ticket_created": self.ticket_created,
            "ticket_updated": self.ticket_updated,
            "priority_score": self.priority_score,
            "created_at": self.created_at,
            "file_name": self.file_name,
            "processing_method": self.processing_method,
            "metadata": self.metadata
        }


@dataclass
class JiraTicketChunks:
    """하나의 Jira 티켓에서 생성된 모든 청크들"""
    ticket_id: str
    ticket_data: Dict[str, Any]  # 원본 티켓 데이터
    chunks: List[JiraChunk] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_chunk(self, chunk: JiraChunk):
        """청크 추가"""
        self.chunks.append(chunk)
    
    def get_chunks_by_type(self, chunk_type: JiraChunkType) -> List[JiraChunk]:
        """타입별 청크 조회"""
        return [chunk for chunk in self.chunks if chunk.chunk_type == chunk_type]
    
    def get_summary_chunks(self) -> List[JiraChunk]:
        """요약 청크들 조회"""
        return self.get_chunks_by_type(JiraChunkType.SUMMARY)
    
    def get_description_chunks(self) -> List[JiraChunk]:
        """설명 청크들 조회"""
        return self.get_chunks_by_type(JiraChunkType.DESCRIPTION)
    
    def get_comment_chunks(self) -> List[JiraChunk]:
        """댓글 청크들 조회"""
        return self.get_chunks_by_type(JiraChunkType.COMMENT)
    
    def get_metadata_chunks(self) -> List[JiraChunk]:
        """메타데이터 청크들 조회"""
        return self.get_chunks_by_type(JiraChunkType.METADATA)
    
    def get_total_chunks(self) -> int:
        """총 청크 수"""
        return len(self.chunks)
    
    def to_vector_db_list(self) -> List[Dict[str, Any]]:
        """Vector DB 저장용 리스트로 변환"""
        return [chunk.to_vector_db_dict() for chunk in self.chunks]


class JiraChunkPriority:
    """Jira 청크 우선순위 관리"""
    
    # 청크 타입별 우선순위 점수
    CHUNK_TYPE_PRIORITY = {
        JiraChunkType.SUMMARY: 1,      # 가장 높음
        JiraChunkType.DESCRIPTION: 2,  # 높음
        JiraChunkType.COMMENT: 3,      # 중간
        JiraChunkType.METADATA: 4      # 낮음
    }
    
    # 티켓 우선순위별 가중치
    TICKET_PRIORITY_WEIGHT = {
        "Critical": 1.0,
        "High": 0.8,
        "Medium": 0.6,
        "Low": 0.4
    }
    
    @classmethod
    def calculate_priority_score(cls, chunk_type: JiraChunkType, ticket_priority: str = "Medium") -> int:
        """청크 우선순위 점수 계산"""
        base_score = cls.CHUNK_TYPE_PRIORITY.get(chunk_type, 3)
        weight = cls.TICKET_PRIORITY_WEIGHT.get(ticket_priority, 0.6)
        
        # 가중치를 적용한 최종 점수 (1-4 범위)
        final_score = int(base_score * weight)
        return max(1, min(4, final_score))


class JiraTextCleaner:
    """Jira 텍스트 정제기"""
    
    @staticmethod
    def clean_summary_text(text: str) -> str:
        """요약 텍스트 정제"""
        if not text or not text.strip():
            return ""
        
        # 불필요한 접두사 제거
        prefixes_to_remove = [
            "요약:", "Summary:", "[NCMS]", "[NCMSAPI]", "제목:", "Title:"
        ]
        
        cleaned_text = text.strip()
        for prefix in prefixes_to_remove:
            if cleaned_text.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        return cleaned_text
    
    @staticmethod
    def clean_description_text(text: str) -> str:
        """설명 텍스트 정제"""
        if not text or not text.strip():
            return ""
        
        # HTML 태그 제거 (간단한 방법)
        import re
        cleaned_text = re.sub(r'<[^>]+>', '', text)
        
        # 불필요한 접두사 제거
        prefixes_to_remove = [
            "설명:", "Description:", "내용:", "Content:"
        ]
        
        cleaned_text = cleaned_text.strip()
        for prefix in prefixes_to_remove:
            if cleaned_text.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        # 연속된 공백 정리
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text
    
    @staticmethod
    def clean_comment_text(text: str) -> str:
        """댓글 텍스트 정제"""
        if not text or not text.strip():
            return ""
        
        # HTML 태그 제거
        import re
        cleaned_text = re.sub(r'<[^>]+>', '', text)
        
        # 불필요한 접두사 제거
        prefixes_to_remove = [
            "댓글:", "Comment:", "코멘트:", "Comment by", "작성자:"
        ]
        
        cleaned_text = cleaned_text.strip()
        for prefix in prefixes_to_remove:
            if cleaned_text.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        # 연속된 공백 정리
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text
    
    @staticmethod
    def clean_metadata_text(text: str) -> str:
        """메타데이터 텍스트 정제"""
        if not text or not text.strip():
            return ""
        
        # 불필요한 접두사 제거
        prefixes_to_remove = [
            "상태:", "Status:", "우선순위:", "Priority:", "타입:", "Type:",
            "담당자:", "Assignee:", "보고자:", "Reporter:"
        ]
        
        cleaned_text = text.strip()
        for prefix in prefixes_to_remove:
            if cleaned_text.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        return cleaned_text
