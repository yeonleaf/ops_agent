#!/usr/bin/env python3
"""
Jira CSV 데이터를 전문화된 청크로 처리하는 프로세서
하나의 티켓을 여러 개의 전문화된 청크로 분할
"""

import csv
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from jira_chunk_models import (
    JiraChunk, JiraChunkType, JiraTicketChunks, 
    JiraChunkPriority, JiraTextCleaner
)

# 텍스트 전처리 모듈 import
from text_preprocessor import preprocess_for_embedding

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JiraChunkProcessor:
    """Jira CSV 데이터를 전문화된 청크로 처리하는 프로세서"""
    
    def __init__(self, enable_text_cleaning: bool = False):
        """
        초기화 (커스텀 전처리 제거됨)
        
        Args:
            enable_text_cleaning: 텍스트 정제 기능 사용 여부 (기본값: False, 전처리 제거됨)
        """
        # 커스텀 전처리 제거: 항상 False로 설정
        self.enable_text_cleaning = False
        self.text_cleaner = None
        logger.info(f"Jira 청크 프로세서 초기화 완료 (커스텀 전처리 제거됨, 원문 그대로 사용)")
    
    def process_csv_file(self, csv_file_path: str) -> List[JiraTicketChunks]:
        """
        Jira CSV 파일을 처리하여 전문화된 청크들로 변환
        
        Args:
            csv_file_path: Jira CSV 파일 경로
            
        Returns:
            각 티켓별 청크 리스트
        """
        logger.info(f"Jira CSV 파일 처리 시작: {csv_file_path}")
        
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_file_path}")
        
        ticket_chunks_list = []
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
                # CSV 헤더 자동 감지
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                for row_idx, row in enumerate(reader, 1):
                    try:
                        # 각 행(티켓)을 전문화된 청크들로 변환
                        ticket_chunks = self._process_ticket_row(row, csv_file_path, row_idx)
                        if ticket_chunks and ticket_chunks.get_total_chunks() > 0:
                            ticket_chunks_list.append(ticket_chunks)
                            logger.info(f"티켓 {ticket_chunks.ticket_id} 처리 완료: {ticket_chunks.get_total_chunks()}개 청크")
                        
                    except Exception as e:
                        logger.error(f"행 {row_idx} 처리 오류: {e}")
                        continue
                
                logger.info(f"CSV 파일 처리 완료: {len(ticket_chunks_list)}개 티켓, 총 {sum(tc.get_total_chunks() for tc in ticket_chunks_list)}개 청크")
                return ticket_chunks_list
                
        except Exception as e:
            logger.error(f"CSV 파일 처리 실패: {e}")
            raise
    
    def _process_ticket_row(self, row: Dict[str, str], file_name: str, row_idx: int) -> Optional[JiraTicketChunks]:
        """
        하나의 티켓 행을 전문화된 청크들로 변환
        
        Args:
            row: CSV 행 데이터
            file_name: 원본 파일명
            row_idx: 행 번호
            
        Returns:
            티켓 청크 객체
        """
        try:
            # 티켓 ID 추출 (Key 필드)
            ticket_id = row.get('Key', '').strip()
            if not ticket_id:
                logger.warning(f"행 {row_idx}: 티켓 ID가 없습니다")
                return None
            
            # 티켓 데이터 정리
            ticket_data = self._clean_ticket_data(row)
            
            # 티켓 청크 컨테이너 생성
            ticket_chunks = JiraTicketChunks(
                ticket_id=ticket_id,
                ticket_data=ticket_data
            )
            
            # 1. 요약(Summary) 청크 생성
            summary_chunk = self._create_summary_chunk(ticket_data, file_name)
            if summary_chunk:
                ticket_chunks.add_chunk(summary_chunk)
            
            # 2. 설명(Description) 청크 생성
            description_chunk = self._create_description_chunk(ticket_data, file_name)
            if description_chunk:
                ticket_chunks.add_chunk(description_chunk)
            
            # 3. 댓글(Comment) 청크들 생성
            comment_chunks = self._create_comment_chunks(ticket_data, file_name)
            for comment_chunk in comment_chunks:
                ticket_chunks.add_chunk(comment_chunk)
            
            # 4. 메타데이터 청크 생성
            metadata_chunk = self._create_metadata_chunk(ticket_data, file_name)
            if metadata_chunk:
                ticket_chunks.add_chunk(metadata_chunk)
            
            return ticket_chunks
            
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 처리 오류: {e}")
            return None
    
    def _clean_ticket_data(self, row: Dict[str, str]) -> Dict[str, str]:
        """티켓 데이터 정리"""
        cleaned_data = {}
        
        # 기본 필드들 정리
        for key, value in row.items():
            if value is None:
                cleaned_data[key] = ""
            else:
                cleaned_data[key] = str(value).strip()
        
        return cleaned_data
    
    def _create_summary_chunk(self, ticket_data: Dict[str, str], file_name: str) -> Optional[JiraChunk]:
        """요약 청크 생성"""
        summary = ticket_data.get('Summary', '').strip()
        if not summary:
            return None
        
        # 텍스트 정제
        if self.text_cleaner:
            cleaned_content = self.text_cleaner.clean_summary_text(summary)
        else:
            cleaned_content = summary
        
        # 임베딩용 전처리 적용
        # 커스텀 전처리 제거: 원문 그대로 사용
        # cleaned_content = preprocess_for_embedding(cleaned_content)
        
        if not cleaned_content:
            return None
        
        # 우선순위 점수 계산
        priority_score = JiraChunkPriority.calculate_priority_score(
            JiraChunkType.SUMMARY, 
            ticket_data.get('Priority', 'Medium')
        )
        
        # 임시 청크 객체 생성 (문서 확장을 위해)
        temp_chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.SUMMARY,
            content=cleaned_content,
            field_name='Summary',
            field_value=summary,
            ticket_summary=summary,
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_field': 'Summary',
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_summary'
            }
        )
        
        # 문서 확장 적용
        expanded_content = temp_chunk.create_expanded_content()
        
        # 최종 청크 생성 (확장된 내용으로)
        chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.SUMMARY,
            content=expanded_content,  # 문서 확장된 내용 사용
            field_name='Summary',
            field_value=summary,
            ticket_summary=summary,
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_field': 'Summary',
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_summary',
                'document_expansion': True
            }
        )
        
        return chunk
    
    def _create_description_chunk(self, ticket_data: Dict[str, str], file_name: str) -> Optional[JiraChunk]:
        """설명 청크 생성"""
        description = ticket_data.get('Description', '').strip()
        if not description:
            return None
        
        # 텍스트 정제
        if self.text_cleaner:
            cleaned_content = self.text_cleaner.clean_description_text(description)
        else:
            cleaned_content = description
        
        # 임베딩용 전처리 적용
        # 커스텀 전처리 제거: 원문 그대로 사용
        # cleaned_content = preprocess_for_embedding(cleaned_content)
        
        if not cleaned_content:
            return None
        
        # 우선순위 점수 계산
        priority_score = JiraChunkPriority.calculate_priority_score(
            JiraChunkType.DESCRIPTION, 
            ticket_data.get('Priority', 'Medium')
        )
        
        # 임시 청크 객체 생성 (문서 확장을 위해)
        temp_chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.DESCRIPTION,
            content=cleaned_content,
            field_name='Description',
            field_value=description,
            ticket_summary=ticket_data.get('Summary', ''),
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_field': 'Description',
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_description'
            }
        )
        
        # 문서 확장 적용
        expanded_content = temp_chunk.create_expanded_content()
        
        # 최종 청크 생성 (확장된 내용으로)
        chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.DESCRIPTION,
            content=expanded_content,  # 문서 확장된 내용 사용
            field_name='Description',
            field_value=description,
            ticket_summary=ticket_data.get('Summary', ''),
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_field': 'Description',
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_description',
                'document_expansion': True
            }
        )
        
        return chunk
    
    def _create_comment_chunks(self, ticket_data: Dict[str, str], file_name: str) -> List[JiraChunk]:
        """댓글 청크들 생성"""
        comment_chunks = []
        
        # CSV에서 댓글 필드 찾기 (Comment, Comments, Comment_1, Comment_2 등)
        comment_fields = [key for key in ticket_data.keys() if 'comment' in key.lower()]
        
        for comment_field in comment_fields:
            comment_text = ticket_data.get(comment_field, '').strip()
            if not comment_text:
                continue
            
            # 텍스트 정제
            if self.text_cleaner:
                cleaned_content = self.text_cleaner.clean_comment_text(comment_text)
            else:
                cleaned_content = comment_text
            
            # 임베딩용 전처리 적용
            # 커스텀 전처리 제거: 원문 그대로 사용
        # cleaned_content = preprocess_for_embedding(cleaned_content)
            
            if not cleaned_content:
                continue
            
            # 댓글 작성자 추출 (필드명에서 또는 텍스트에서)
            comment_author = self._extract_comment_author(comment_field, comment_text)
            
            # 우선순위 점수 계산
            priority_score = JiraChunkPriority.calculate_priority_score(
                JiraChunkType.COMMENT, 
                ticket_data.get('Priority', 'Medium')
            )
            
            # 임시 청크 객체 생성 (문서 확장을 위해)
            temp_chunk = JiraChunk(
                ticket_id=ticket_data.get('Key', ''),
                chunk_type=JiraChunkType.COMMENT,
                content=cleaned_content,
                field_name=comment_field,
                field_value=comment_text,
                comment_author=comment_author,
                comment_date=ticket_data.get('Updated', ''),  # 댓글 날짜는 Updated 필드 사용
                comment_id=f"{ticket_data.get('Key', '')}_{comment_field}",
                ticket_summary=ticket_data.get('Summary', ''),
                ticket_status=ticket_data.get('Status', ''),
                ticket_priority=ticket_data.get('Priority', ''),
                ticket_type=ticket_data.get('Issue Type', ''),
                ticket_assignee=ticket_data.get('Assignee', ''),
                ticket_reporter=ticket_data.get('Reporter', ''),
                ticket_created=ticket_data.get('Created', ''),
                ticket_updated=ticket_data.get('Updated', ''),
                priority_score=priority_score,
                file_name=file_name,
                metadata={
                    'original_field': comment_field,
                    'text_cleaned': self.enable_text_cleaning,
                    'chunk_category': 'ticket_comment'
                }
            )
            
            # 문서 확장 적용
            expanded_content = temp_chunk.create_expanded_content()
            
            # 최종 청크 생성 (확장된 내용으로)
            chunk = JiraChunk(
                ticket_id=ticket_data.get('Key', ''),
                chunk_type=JiraChunkType.COMMENT,
                content=expanded_content,  # 문서 확장된 내용 사용
                field_name=comment_field,
                field_value=comment_text,
                comment_author=comment_author,
                comment_date=ticket_data.get('Updated', ''),  # 댓글 날짜는 Updated 필드 사용
                comment_id=f"{ticket_data.get('Key', '')}_{comment_field}",
                ticket_summary=ticket_data.get('Summary', ''),
                ticket_status=ticket_data.get('Status', ''),
                ticket_priority=ticket_data.get('Priority', ''),
                ticket_type=ticket_data.get('Issue Type', ''),
                ticket_assignee=ticket_data.get('Assignee', ''),
                ticket_reporter=ticket_data.get('Reporter', ''),
                ticket_created=ticket_data.get('Created', ''),
                ticket_updated=ticket_data.get('Updated', ''),
                priority_score=priority_score,
                file_name=file_name,
                metadata={
                    'original_field': comment_field,
                    'text_cleaned': self.enable_text_cleaning,
                    'chunk_category': 'ticket_comment',
                    'document_expansion': True
                }
            )
            
            comment_chunks.append(chunk)
        
        return comment_chunks
    
    def _create_metadata_chunk(self, ticket_data: Dict[str, str], file_name: str) -> Optional[JiraChunk]:
        """메타데이터 청크 생성"""
        # 메타데이터 필드들 수집
        metadata_fields = ['Issue Type', 'Priority', 'Status', 'Assignee', 'Reporter']
        metadata_content_parts = []
        
        for field in metadata_fields:
            value = ticket_data.get(field, '').strip()
            if value:
                metadata_content_parts.append(f"{field}: {value}")
        
        if not metadata_content_parts:
            return None
        
        metadata_content = " | ".join(metadata_content_parts)
        
        # 텍스트 정제
        if self.text_cleaner:
            cleaned_content = self.text_cleaner.clean_metadata_text(metadata_content)
        else:
            cleaned_content = metadata_content
        
        # 임베딩용 전처리 적용
        # 커스텀 전처리 제거: 원문 그대로 사용
        # cleaned_content = preprocess_for_embedding(cleaned_content)
        
        if not cleaned_content:
            return None
        
        # 우선순위 점수 계산
        priority_score = JiraChunkPriority.calculate_priority_score(
            JiraChunkType.METADATA, 
            ticket_data.get('Priority', 'Medium')
        )
        
        # 임시 청크 객체 생성 (문서 확장을 위해)
        temp_chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.METADATA,
            content=cleaned_content,
            field_name='Metadata',
            field_value=metadata_content,
            ticket_summary=ticket_data.get('Summary', ''),
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_fields': metadata_fields,
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_metadata'
            }
        )
        
        # 문서 확장 적용
        expanded_content = temp_chunk.create_expanded_content()
        
        # 최종 청크 생성 (확장된 내용으로)
        chunk = JiraChunk(
            ticket_id=ticket_data.get('Key', ''),
            chunk_type=JiraChunkType.METADATA,
            content=expanded_content,  # 문서 확장된 내용 사용
            field_name='Metadata',
            field_value=metadata_content,
            ticket_summary=ticket_data.get('Summary', ''),
            ticket_status=ticket_data.get('Status', ''),
            ticket_priority=ticket_data.get('Priority', ''),
            ticket_type=ticket_data.get('Issue Type', ''),
            ticket_assignee=ticket_data.get('Assignee', ''),
            ticket_reporter=ticket_data.get('Reporter', ''),
            ticket_created=ticket_data.get('Created', ''),
            ticket_updated=ticket_data.get('Updated', ''),
            priority_score=priority_score,
            file_name=file_name,
            metadata={
                'original_fields': metadata_fields,
                'text_cleaned': self.enable_text_cleaning,
                'chunk_category': 'ticket_metadata',
                'document_expansion': True
            }
        )
        
        return chunk
    
    def _extract_comment_author(self, comment_field: str, comment_text: str) -> Optional[str]:
        """댓글 작성자 추출"""
        # 필드명에서 작성자 추출 시도
        if '_' in comment_field:
            parts = comment_field.split('_')
            if len(parts) > 1:
                potential_author = parts[1]
                if potential_author and not potential_author.isdigit():
                    return potential_author
        
        # 텍스트에서 작성자 패턴 찾기
        import re
        patterns = [
            r'작성자:\s*([^\n\r]+)',
            r'Author:\s*([^\n\r]+)',
            r'By\s+([^\n\r]+)',
            r'-\s*([^\n\r]+)\s*$'  # 마지막 줄의 이름 패턴
        ]
        
        for pattern in patterns:
            match = re.search(pattern, comment_text, re.IGNORECASE)
            if match:
                author = match.group(1).strip()
                if author and len(author) < 50:  # 합리적인 이름 길이
                    return author
        
        return None
    
    def save_chunks_to_json(self, ticket_chunks_list: List[JiraTicketChunks], output_file: str):
        """청크들을 JSON 파일로 저장"""
        logger.info(f"청크들을 JSON 파일로 저장: {output_file}")
        
        output_data = {
            "created_at": datetime.now().isoformat(),
            "total_tickets": len(ticket_chunks_list),
            "total_chunks": sum(tc.get_total_chunks() for tc in ticket_chunks_list),
            "tickets": []
        }
        
        for ticket_chunks in ticket_chunks_list:
            ticket_data = {
                "ticket_id": ticket_chunks.ticket_id,
                "total_chunks": ticket_chunks.get_total_chunks(),
                "chunks": ticket_chunks.to_vector_db_list()
            }
            output_data["tickets"].append(ticket_data)
        
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
    
    # 프로세서 초기화
    processor = JiraChunkProcessor(enable_text_cleaning=True)
    
    try:
        # CSV 파일 처리
        ticket_chunks_list = processor.process_csv_file(csv_file)
        
        # 결과 출력
        print(f"\n=== Jira 청킹 결과 ===")
        print(f"총 티켓 수: {len(ticket_chunks_list)}")
        
        total_chunks = 0
        for ticket_chunks in ticket_chunks_list:
            chunks_count = ticket_chunks.get_total_chunks()
            total_chunks += chunks_count
            
            print(f"\n티켓 {ticket_chunks.ticket_id}:")
            print(f"  - 요약 청크: {len(ticket_chunks.get_summary_chunks())}개")
            print(f"  - 설명 청크: {len(ticket_chunks.get_description_chunks())}개")
            print(f"  - 댓글 청크: {len(ticket_chunks.get_comment_chunks())}개")
            print(f"  - 메타데이터 청크: {len(ticket_chunks.get_metadata_chunks())}개")
            print(f"  - 총 청크: {chunks_count}개")
        
        print(f"\n총 청크 수: {total_chunks}")
        
        # JSON 파일로 저장
        output_file = "/Users/a11479/Desktop/code/ops_agent/jira_chunks_output.json"
        processor.save_chunks_to_json(ticket_chunks_list, output_file)
        print(f"\n결과가 JSON 파일로 저장되었습니다: {output_file}")
        
    except Exception as e:
        print(f"처리 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
