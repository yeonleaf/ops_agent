#!/usr/bin/env python3
"""
Jira 전문화된 청킹을 기존 RAG 시스템에 통합하는 인터페이스
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from jira_chunk_models import JiraChunk, JiraChunkType, JiraTicketChunks
from jira_chunk_processor import JiraChunkProcessor
# UnifiedChunk import
from models.unified_chunk import UnifiedChunk, create_file_unified_chunk

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JiraRAGIntegration:
    """Jira 전문화된 청킹을 기존 RAG 시스템에 통합"""
    
    def __init__(self, enable_text_cleaning: bool = True):
        """
        초기화
        
        Args:
            enable_text_cleaning: 텍스트 정제 기능 사용 여부
        """
        self.processor = JiraChunkProcessor(enable_text_cleaning=enable_text_cleaning)
        logger.info("Jira RAG 통합 인터페이스 초기화 완료")
    
    def process_jira_csv_to_chunks(self, csv_file_path: str) -> List[Dict[str, Any]]:
        """
        Jira CSV 파일을 전문화된 청크들로 처리하여 기존 RAG 시스템 형식으로 변환
        
        Args:
            csv_file_path: Jira CSV 파일 경로
            
        Returns:
            기존 RAG 시스템과 호환되는 청크 리스트
        """
        logger.info(f"Jira CSV 파일을 RAG 시스템 형식으로 처리: {csv_file_path}")
        
        # Jira 청크 프로세서로 처리
        ticket_chunks_list = self.processor.process_csv_file(csv_file_path)
        
        # 기존 RAG 시스템 형식으로 변환
        rag_chunks = []
        
        for ticket_chunks in ticket_chunks_list:
            for chunk in ticket_chunks.chunks:
                # 기존 RAG 시스템의 FileChunk 형식으로 변환
                rag_chunk = self._convert_to_rag_format(chunk, csv_file_path)
                rag_chunks.append(rag_chunk)
        
        logger.info(f"RAG 시스템 형식 변환 완료: {len(rag_chunks)}개 청크")
        return rag_chunks
    
    def _convert_to_rag_format(self, jira_chunk: JiraChunk, file_name: str) -> UnifiedChunk:
        """
        Jira 청크를 UnifiedChunk로 변환

        주의: 현재 버전에서는 Jira CSV를 "파일"로 처리합니다.
        향후 Jira 일배치 개발 시 data_source="jira"로 변경 예정입니다.

        Args:
            jira_chunk: Jira 청크 객체
            file_name: 원본 파일명

        Returns:
            UnifiedChunk 인스턴스 (data_source="file")
        """
        # 현재는 Jira CSV를 파일로 처리 (data_source="file")
        # 향후 Jira 일배치 개발 시:
        #   - data_source를 "jira"로 변경
        #   - file_metadata를 None으로 설정
        #   - jira_metadata에 실제 데이터 저장

        unified_chunk = create_file_unified_chunk(
            text_chunk=jira_chunk.content,
            file_name=os.path.basename(file_name),
            file_hash=f"jira_{jira_chunk.ticket_id}",  # Jira 티켓 ID 기반 해시
            file_type="csv",
            file_size=len(jira_chunk.content.encode('utf-8')),
            architecture="jira_specialized_chunking",
            processing_method="jira_field_based_processing",
            vision_analysis=False,  # Jira 데이터는 Vision 분석 불필요
            section_title=f"{jira_chunk.chunk_type.value.title()} - {jira_chunk.ticket_id}",
            page_number=1,  # Jira 데이터는 페이지 개념 없음
            element_count=1,  # 각 청크는 하나의 요소
            elements=[{
                "type": jira_chunk.chunk_type.value,
                "content": jira_chunk.content,
                "metadata": jira_chunk.metadata,
                # Jira 전용 정보를 elements에 저장 (향후 참조용)
                "jira_metadata": {
                    "ticket_id": jira_chunk.ticket_id,
                    "chunk_type": jira_chunk.chunk_type.value,
                    "field_name": jira_chunk.field_name,
                    "ticket_summary": jira_chunk.ticket_summary,
                    "ticket_status": jira_chunk.ticket_status,
                    "ticket_priority": jira_chunk.ticket_priority,
                    "ticket_type": jira_chunk.ticket_type,
                    "ticket_assignee": jira_chunk.ticket_assignee,
                    "ticket_reporter": jira_chunk.ticket_reporter,
                    "ticket_created": jira_chunk.ticket_created,
                    "ticket_updated": jira_chunk.ticket_updated,
                    "priority_score": jira_chunk.priority_score,
                    "comment_author": jira_chunk.comment_author,
                    "comment_date": jira_chunk.comment_date,
                    "comment_id": jira_chunk.comment_id
                }
            }],
            chunk_id=jira_chunk.chunk_id
        )

        return unified_chunk
    
    def get_chunks_by_type(self, chunks: List[Dict[str, Any]], chunk_type: JiraChunkType) -> List[Dict[str, Any]]:
        """
        청크 타입별로 필터링
        
        Args:
            chunks: 청크 리스트
            chunk_type: 필터링할 청크 타입
            
        Returns:
            필터링된 청크 리스트
        """
        return [
            chunk for chunk in chunks 
            if chunk.get('jira_metadata', {}).get('chunk_type') == chunk_type.value
        ]
    
    def get_summary_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """요약 청크들만 반환"""
        return self.get_chunks_by_type(chunks, JiraChunkType.SUMMARY)
    
    def get_description_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """설명 청크들만 반환"""
        return self.get_chunks_by_type(chunks, JiraChunkType.DESCRIPTION)
    
    def get_comment_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """댓글 청크들만 반환"""
        return self.get_chunks_by_type(chunks, JiraChunkType.COMMENT)
    
    def get_metadata_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """메타데이터 청크들만 반환"""
        return self.get_chunks_by_type(chunks, JiraChunkType.METADATA)
    
    def get_chunks_by_ticket_id(self, chunks: List[Dict[str, Any]], ticket_id: str) -> List[Dict[str, Any]]:
        """
        특정 티켓의 모든 청크 반환
        
        Args:
            chunks: 청크 리스트
            ticket_id: 티켓 ID
            
        Returns:
            해당 티켓의 모든 청크
        """
        return [
            chunk for chunk in chunks 
            if chunk.get('jira_metadata', {}).get('ticket_id') == ticket_id
        ]
    
    def get_chunks_by_priority(self, chunks: List[Dict[str, Any]], min_priority: int = 1, max_priority: int = 4) -> List[Dict[str, Any]]:
        """
        우선순위 범위로 청크 필터링
        
        Args:
            chunks: 청크 리스트
            min_priority: 최소 우선순위 (1: 높음, 4: 낮음)
            max_priority: 최대 우선순위
            
        Returns:
            우선순위 범위에 해당하는 청크들
        """
        return [
            chunk for chunk in chunks 
            if min_priority <= chunk.get('jira_metadata', {}).get('priority_score', 3) <= max_priority
        ]
    
    def create_search_context(self, chunks: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """
        검색 쿼리에 대한 컨텍스트 생성
        
        Args:
            chunks: 청크 리스트
            query: 검색 쿼리
            
        Returns:
            검색 컨텍스트 정보
        """
        context = {
            "query": query,
            "total_chunks": len(chunks),
            "chunk_type_distribution": {},
            "ticket_distribution": {},
            "priority_distribution": {},
            "search_recommendations": []
        }
        
        # 청크 타입별 분포
        for chunk_type in JiraChunkType:
            type_chunks = self.get_chunks_by_type(chunks, chunk_type)
            context["chunk_type_distribution"][chunk_type.value] = len(type_chunks)
        
        # 티켓별 분포
        ticket_ids = set()
        for chunk in chunks:
            ticket_id = chunk.get('jira_metadata', {}).get('ticket_id', '')
            if ticket_id:
                ticket_ids.add(ticket_id)
        context["ticket_distribution"]["unique_tickets"] = len(ticket_ids)
        
        # 우선순위별 분포
        for priority in range(1, 5):
            priority_chunks = self.get_chunks_by_priority(chunks, priority, priority)
            context["priority_distribution"][f"priority_{priority}"] = len(priority_chunks)
        
        # 검색 추천사항
        if "서버" in query or "접속" in query:
            context["search_recommendations"].append("summary 청크에서 관련 티켓을 찾아보세요")
        if "오류" in query or "에러" in query:
            context["search_recommendations"].append("description 청크에서 상세한 오류 정보를 확인하세요")
        if "댓글" in query or "코멘트" in query:
            context["search_recommendations"].append("comment 청크에서 관련 댓글을 검색하세요")
        
        return context
    
    def save_rag_chunks_to_json(self, chunks: List[Dict[str, Any]], output_file: str):
        """RAG 청크들을 JSON 파일로 저장"""
        logger.info(f"RAG 청크들을 JSON 파일로 저장: {output_file}")
        
        output_data = {
            "created_at": datetime.now().isoformat(),
            "total_chunks": len(chunks),
            "processing_method": "jira_specialized_chunking",
            "chunks": chunks
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON 파일 저장 완료: {output_file}")


def main():
    """테스트용 메인 함수"""
    # 샘플 CSV 파일로 테스트
    csv_file = "/Users/a11479/Desktop/code/ops_agent/sample_jira_tickets.csv"
    
    if not os.path.exists(csv_file):
        print(f"CSV 파일이 존재하지 않습니다: {csv_file}")
        return
    
    try:
        # Jira RAG 통합 인터페이스 초기화
        jira_rag = JiraRAGIntegration(enable_text_cleaning=True)
        
        # CSV 파일을 RAG 시스템 형식으로 처리
        print("=== Jira CSV를 RAG 시스템 형식으로 처리 ===")
        rag_chunks = jira_rag.process_jira_csv_to_chunks(csv_file)
        
        print(f"총 청크 수: {len(rag_chunks)}")
        
        # 청크 타입별 통계
        print("\n=== 청크 타입별 통계 ===")
        summary_chunks = jira_rag.get_summary_chunks(rag_chunks)
        description_chunks = jira_rag.get_description_chunks(rag_chunks)
        comment_chunks = jira_rag.get_comment_chunks(rag_chunks)
        metadata_chunks = jira_rag.get_metadata_chunks(rag_chunks)
        
        print(f"요약 청크: {len(summary_chunks)}개")
        print(f"설명 청크: {len(description_chunks)}개")
        print(f"댓글 청크: {len(comment_chunks)}개")
        print(f"메타데이터 청크: {len(metadata_chunks)}개")
        
        # 샘플 청크 출력
        print("\n=== 샘플 청크 (T-001) ===")
        t001_chunks = jira_rag.get_chunks_by_ticket_id(rag_chunks, "T-001")
        for chunk in t001_chunks:
            chunk_type = chunk['jira_metadata']['chunk_type']
            content = chunk['text_chunk'][:50] + "..." if len(chunk['text_chunk']) > 50 else chunk['text_chunk']
            print(f"  - {chunk_type}: {content}")
        
        # 검색 컨텍스트 생성
        print("\n=== 검색 컨텍스트 생성 ===")
        context = jira_rag.create_search_context(rag_chunks, "서버 접속 오류")
        print(f"총 청크 수: {context['total_chunks']}")
        print(f"고유 티켓 수: {context['ticket_distribution']['unique_tickets']}")
        print("청크 타입별 분포:")
        for chunk_type, count in context['chunk_type_distribution'].items():
            print(f"  - {chunk_type}: {count}개")
        print("검색 추천사항:")
        for recommendation in context['search_recommendations']:
            print(f"  - {recommendation}")
        
        # JSON 파일로 저장
        print("\n=== JSON 파일 저장 ===")
        output_file = "/Users/a11479/Desktop/code/ops_agent/jira_rag_chunks.json"
        jira_rag.save_rag_chunks_to_json(rag_chunks, output_file)
        print(f"RAG 청크들이 JSON 파일로 저장되었습니다: {output_file}")
        
    except Exception as e:
        print(f"처리 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
