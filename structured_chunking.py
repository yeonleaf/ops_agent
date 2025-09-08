"""
구조적 데이터 청킹 모듈
Jira 티켓과 같은 구조화된 데이터를 의미 있는 청크로 분할하는 기능을 제공합니다.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

@dataclass
class StructuredChunk:
    """구조화된 청크 데이터 클래스"""
    content: str
    chunk_type: str  # 'header', 'comment'
    ticket_id: str
    field_name: str
    field_value: str
    metadata: Dict[str, Any]
    priority: int = 1  # 1: 높음, 2: 중간, 3: 낮음
    commenter: Optional[str] = None  # 댓글 작성자 (comment 타입일 때만)

class JiraStructuredChunker:
    """Jira 데이터의 구조적 청킹을 담당하는 클래스
    
    새로운 청킹 전략:
    1. '헤더(Header)' 청크: Summary + Description을 합쳐서 하나의 핵심 청크 생성
    2. '댓글(Comment)' 청크: 각 댓글을 개별적인 청크로 생성
    """
    
    def __init__(self):
        self.chunk_types = {
            'header': '헤더 (Summary + Description)',
            'comment': '댓글'
        }
    
    def chunk_jira_html(self, html_content: str, file_name: str) -> List[StructuredChunk]:
        """
        Jira HTML 파일을 구조적 청크로 분할
        
        Args:
            html_content: Jira HTML 내용
            file_name: 파일명
            
        Returns:
            구조화된 청크 리스트
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            chunks = []
            
            # 테이블에서 티켓 행들을 찾기
            ticket_rows = soup.find_all('tr', class_='issuerow')
            
            print(f"🔍 Jira HTML에서 {len(ticket_rows)}개의 티켓 행 발견")
            
            for row in ticket_rows:
                ticket_chunks = self._extract_ticket_chunks_from_html(row, file_name)
                chunks.extend(ticket_chunks)
            
            print(f"✅ 구조적 청킹 완료: {len(chunks)}개 청크 생성")
            return chunks
            
        except Exception as e:
            logger.error(f"Jira HTML 청킹 실패: {str(e)}")
            return []
    
    def _extract_ticket_chunks_from_html(self, row, file_name: str) -> List[StructuredChunk]:
        """HTML 행에서 새로운 청킹 전략에 따라 청크들을 추출"""
        chunks = []
        
        try:
            # 티켓 ID 추출
            ticket_id = row.get('data-issuekey', 'UNKNOWN')
            if not ticket_id or ticket_id == 'UNKNOWN':
                return chunks
            
            cells = row.find_all('td')
            if len(cells) < 3:  # 최소 필수 필드 수 확인
                return chunks
            
            # 1. 헤더 청크 생성 (Summary + Description)
            summary_text = ""
            description_text = ""
            
            # Summary 추출 (일반적으로 3번째 셀)
            if len(cells) > 2:
                summary_cell = cells[2]
                summary_text = summary_cell.get_text(strip=True)
            
            # Description은 HTML 테이블에서 직접 추출하기 어려우므로 
            # Summary만으로 헤더 청크 생성 (실제 Description은 API나 상세 페이지에서 가져와야 함)
            if summary_text:
                header_content = f"요약: {summary_text}"
                if description_text:
                    header_content += f"\n설명: {description_text}"
                
                chunk = StructuredChunk(
                    content=header_content,
                    chunk_type="header",
                    ticket_id=ticket_id,
                    field_name="header",
                    field_value=header_content,
                    metadata={
                        "file_name": file_name,
                        "ticket_id": ticket_id,
                        "field_type": "header",
                        "summary": summary_text,
                        "description": description_text
                    },
                    priority=1
                )
                chunks.append(chunk)
            
            # 2. 댓글 청크 생성 (HTML에서는 댓글 정보가 테이블에 직접 포함되지 않으므로 
            # 실제로는 API를 통해 별도로 가져와야 함)
            # 여기서는 예시로 빈 리스트를 반환
            # 실제 구현에서는 Jira API를 통해 댓글을 가져와야 함
            
            print(f"📝 티켓 {ticket_id}: {len(chunks)}개 청크 생성 (헤더: {len([c for c in chunks if c.chunk_type == 'header'])}, 댓글: {len([c for c in chunks if c.chunk_type == 'comment'])})")
            
        except Exception as e:
            logger.error(f"티켓 청킹 실패: {str(e)}")
        
        return chunks
    
    def chunk_csv_data(self, csv_data: List[Dict[str, Any]], file_name: str) -> List[StructuredChunk]:
        """
        CSV 데이터를 새로운 청킹 전략에 따라 구조적 청크로 분할
        
        Args:
            csv_data: CSV 데이터 리스트
            file_name: 파일명
            
        Returns:
            구조화된 청크 리스트
        """
        chunks = []
        
        try:
            for row in csv_data:
                ticket_id = row.get('Key', 'UNKNOWN')
                
                # 1. 헤더 청크 생성 (Summary + Description)
                summary = row.get('Summary', '')
                description = row.get('Description', '')
                
                if summary or description:
                    # Summary와 Description을 합쳐서 하나의 헤더 청크 생성
                    header_content = ""
                    if summary:
                        header_content += f"요약: {summary}"
                    if description:
                        if header_content:
                            header_content += f"\n설명: {description}"
                        else:
                            header_content = f"설명: {description}"
                    
                    chunk = StructuredChunk(
                        content=header_content,
                        chunk_type="header",
                        ticket_id=ticket_id,
                        field_name="header",
                        field_value=header_content,
                        metadata={
                            "file_name": file_name,
                            "ticket_id": ticket_id,
                            "field_type": "header",
                            "summary": summary,
                            "description": description
                        },
                        priority=1
                    )
                    chunks.append(chunk)
                
                # 2. 댓글 청크 생성 (각 댓글을 개별 청크로)
                comments = self._extract_comments_from_csv_row(row)
                for comment in comments:
                    chunk = StructuredChunk(
                        content=comment['content'],
                        chunk_type="comment",
                        ticket_id=ticket_id,
                        field_name="comment",
                        field_value=comment['content'],
                        metadata={
                            "file_name": file_name,
                            "ticket_id": ticket_id,
                            "field_type": "comment",
                            "comment_id": comment.get('id', ''),
                            "comment_date": comment.get('date', '')
                        },
                        priority=2,
                        commenter=comment.get('author', 'Unknown')
                    )
                    chunks.append(chunk)
            
            print(f"✅ CSV 구조적 청킹 완료: {len(chunks)}개 청크 생성")
            print(f"   - 헤더 청크: {len([c for c in chunks if c.chunk_type == 'header'])}개")
            print(f"   - 댓글 청크: {len([c for c in chunks if c.chunk_type == 'comment'])}개")
            
        except Exception as e:
            logger.error(f"CSV 청킹 실패: {str(e)}")
        
        return chunks
    
    def _extract_comments_from_csv_row(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        CSV 행에서 댓글 정보를 추출
        
        Args:
            row: CSV 행 데이터
            
        Returns:
            댓글 리스트
        """
        comments = []
        
        # Comments 필드가 있는지 확인
        comments_field = row.get('Comments', '')
        if not comments_field or comments_field.strip() == '':
            return comments
        
        # 댓글을 파싱 (여러 댓글이 있을 수 있음)
        # 실제 구현에서는 CSV의 Comments 필드 형식에 따라 파싱 로직을 조정해야 함
        try:
            # 간단한 댓글 분리 (실제로는 더 복잡한 파싱이 필요할 수 있음)
            comment_texts = comments_field.split('\n---\n')  # 댓글 구분자로 가정
            
            for i, comment_text in enumerate(comment_texts):
                if comment_text.strip():
                    comments.append({
                        'id': f"comment_{i+1}",
                        'content': comment_text.strip(),
                        'author': 'Unknown',  # CSV에서 작성자 정보 추출이 어려움
                        'date': ''  # CSV에서 날짜 정보 추출이 어려움
                    })
        except Exception as e:
            logger.warning(f"댓글 파싱 실패: {str(e)}")
        
        return comments

def test_structured_chunking():
    """구조적 청킹 테스트 함수"""
    print("🧪 새로운 구조적 청킹 전략 테스트 시작")
    
    # CSV 데이터 테스트 (댓글 포함)
    csv_data = [
        {
            "Key": "T-001",
            "Summary": "서버 접속 불가 문제",
            "Description": "메인 서버에 접속이 되지 않습니다. HTTP 500 오류가 발생하고 있습니다.",
            "Comments": "김개발: 로그를 확인해보니 데이터베이스 연결 문제로 보입니다.\n---\n이사용: 네트워크 설정도 확인해주세요.",
            "Issue Type": "Bug",
            "Priority": "High",
            "Status": "Open",
            "Assignee": "김개발",
            "Reporter": "이사용",
            "Created": "2024-01-15",
            "Updated": "2024-01-15"
        },
        {
            "Key": "T-002",
            "Summary": "UI 개선 요청",
            "Description": "사용자 인터페이스가 직관적이지 않아 개선이 필요합니다.",
            "Comments": "홍길동: 특히 로그인 화면의 버튼 배치를 개선하면 좋겠습니다.",
            "Issue Type": "Improvement",
            "Priority": "Medium",
            "Status": "Open",
            "Assignee": "박디자인",
            "Reporter": "홍길동",
            "Created": "2024-01-16",
            "Updated": "2024-01-16"
        }
    ]
    
    chunker = JiraStructuredChunker()
    csv_chunks = chunker.chunk_csv_data(csv_data, "test.csv")
    
    print(f"\n📊 CSV 청킹 결과: {len(csv_chunks)}개")
    
    # 청크 타입별로 그룹화
    header_chunks = [c for c in csv_chunks if c.chunk_type == 'header']
    comment_chunks = [c for c in csv_chunks if c.chunk_type == 'comment']
    
    print(f"   - 헤더 청크: {len(header_chunks)}개")
    print(f"   - 댓글 청크: {len(comment_chunks)}개")
    
    # 헤더 청크 출력
    print(f"\n📋 헤더 청크들:")
    for i, chunk in enumerate(header_chunks, 1):
        print(f"\n--- 헤더 청크 {i} ---")
        print(f"티켓 ID: {chunk.ticket_id}")
        print(f"우선순위: {chunk.priority}")
        print(f"내용: {chunk.content}")
        print(f"댓글 작성자: {chunk.commenter or 'N/A'}")
    
    # 댓글 청크 출력
    print(f"\n💬 댓글 청크들:")
    for i, chunk in enumerate(comment_chunks, 1):
        print(f"\n--- 댓글 청크 {i} ---")
        print(f"티켓 ID: {chunk.ticket_id}")
        print(f"댓글 작성자: {chunk.commenter}")
        print(f"우선순위: {chunk.priority}")
        print(f"내용: {chunk.content}")

if __name__ == "__main__":
    test_structured_chunking()
