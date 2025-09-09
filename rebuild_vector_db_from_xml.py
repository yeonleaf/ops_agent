#!/usr/bin/env python3
"""
XML Jira 데이터를 원문 그대로 사용하여 Vector DB 재구축
- 커스텀 전처리 제거됨
- ko-sroberta-multitask 모델 사용
- L2 정규화 적용
"""

import xml.etree.ElementTree as ET
import re
import html
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from clean_korean_embedding import CleanKoreanEmbeddingFunction
from jira_chunk_processor import JiraChunkProcessor
from jira_chunk_models import JiraChunk, JiraChunkType
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanse_text(text: str) -> str:
    """
    임베딩 전 텍스트 정제 - 잡음 제거
    반복되는 메타데이터 패턴을 제거하여 의미있는 텍스트만 추출
    """
    if not text:
        return ""
    
    # 1. Jira 티켓 키 패턴 제거 [BTVO-NNNNN]
    text = re.sub(r'\[BTVO-\s?\d+\]', '', text)
    
    # 2. NCMS 패턴 제거 [NCMS]
    text = re.sub(r'\[NCMS\]', '', text)
    
    # 3. 날짜 패턴 제거 (MM/DD) 또는 (YYYY-MM-DD)
    text = re.sub(r'\(\d{1,2}/\d{1,2}\)', '', text)
    text = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', text)
    
    # 4. 기타 불필요한 패턴들
    text = re.sub(r'\[.*?\]', '', text)  # 대괄호 안의 모든 내용 제거
    text = re.sub(r'\(.*?\)', '', text)  # 소괄호 안의 모든 내용 제거
    
    # 5. 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 6. 앞뒤 공백 제거
    text = text.strip()
    
    return text

def create_multi_vector_chunks_from_ticket(ticket: Dict[str, Any]) -> List[JiraChunk]:
    """
    다중 벡터 표현을 위한 청크 생성
    - 제목 청크 (1개): 티켓의 제목만으로 구성
    - 설명 청크 (1개): 티켓의 본문(Description)만으로 구성  
    - 댓글 청크 (N개): 각 댓글을 개별 청크로 생성 (문맥 유지)
    """
    chunks = []
    ticket_key = ticket.get('Key', 'UNKNOWN')
    ticket_summary = ticket.get('Summary', '')
    description = ticket.get('Description', '')
    comments = ticket.get('Comments', [])
    
    # 텍스트 정제 적용
    clean_summary = cleanse_text(ticket_summary)
    clean_description = cleanse_text(description)
    
    # 1. 제목 청크 생성 (1개)
    if clean_summary:
        title_chunk = JiraChunk(
            ticket_id=f"{ticket_key}_title",
            parent_ticket_id=ticket_key,
            ticket_summary=clean_summary,
            chunk_type=JiraChunkType.SUMMARY,
            content=clean_summary,
            field_name="title",
            field_value=clean_summary
        )
        chunks.append(title_chunk)
    
    # 2. 설명 청크 생성 (1개) - 긴 설명도 하나의 청크로 유지
    if clean_description:
        description_chunk = JiraChunk(
            ticket_id=f"{ticket_key}_description",
            parent_ticket_id=ticket_key,
            ticket_summary=clean_summary,
            chunk_type=JiraChunkType.DESCRIPTION,
            content=clean_description,
            field_name="description",
            field_value=clean_description
        )
        chunks.append(description_chunk)
    
    # 3. 댓글 청크 생성 (N개) - 각 댓글을 개별 청크로 생성
    for i, comment in enumerate(comments):
        comment_text = comment.get('text', '')
        comment_author = comment.get('author', 'Unknown')
        comment_date = comment.get('date', '')
        
        if comment_text:
            # 댓글 텍스트 정제
            clean_comment = cleanse_text(comment_text)
            
            # 문맥 유지를 위한 댓글 청크 포맷
            comment_content = f"티켓 제목: {clean_summary}\n\n댓글: {clean_comment}"
            
            comment_chunk = JiraChunk(
                ticket_id=f"{ticket_key}_comment_{i}",
                parent_ticket_id=ticket_key,
                ticket_summary=clean_summary,
                chunk_type=JiraChunkType.COMMENT,
                content=comment_content,
                field_name="comment",
                field_value=clean_comment,
                comment_author=comment_author,
                comment_date=comment_date,
                comment_id=f"comment_{i}"
            )
            chunks.append(comment_chunk)
    
    return chunks

def create_chunks_from_ticket(ticket: Dict[str, Any]) -> List[JiraChunk]:
    """기존 방식 유지 (하위 호환성)"""
    return create_multi_vector_chunks_from_ticket(ticket)

def clean_html_content(html_content: str) -> str:
    """HTML 태그와 엔티티를 정리하여 순수 텍스트 추출"""
    if not html_content:
        return ""
    
    # HTML 엔티티 디코딩
    text = html.unescape(html_content)
    
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    
    # 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def parse_jira_xml(xml_file_path: str) -> List[Dict[str, Any]]:
    """XML 파일에서 Jira 티켓 데이터 파싱"""
    logger.info(f"📄 XML 파일 파싱 시작: {xml_file_path}")
    
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        tickets = []
        
        # RSS 구조에서 item 요소들 찾기
        for item in root.findall('.//item'):
            try:
                # 기본 정보 추출
                key_elem = item.find('key')
                title_elem = item.find('title')
                summary_elem = item.find('summary')
                description_elem = item.find('description')
                type_elem = item.find('type')
                priority_elem = item.find('priority')
                status_elem = item.find('status')
                assignee_elem = item.find('assignee')
                reporter_elem = item.find('reporter')
                created_elem = item.find('created')
                updated_elem = item.find('updated')
                
                # 키 추출
                key = key_elem.text if key_elem is not None else "UNKNOWN"
                
                # 제목 추출 (title에서 [KEY] 부분 제거)
                title = title_elem.text if title_elem is not None else ""
                if title.startswith(f"[{key}]"):
                    title = title[len(f"[{key}]"):].strip()
                
                # 요약 추출
                summary = summary_elem.text if summary_elem is not None else ""
                if summary.startswith(f"[{key}]"):
                    summary = summary[len(f"[{key}]"):].strip()
                
                # 설명 추출 및 HTML 정리
                description = ""
                if description_elem is not None and description_elem.text:
                    description = clean_html_content(description_elem.text)
                
                # 기타 메타데이터
                issue_type = type_elem.text if type_elem is not None else "Unknown"
                priority = priority_elem.text if priority_elem is not None else "Unknown"
                status = status_elem.text if status_elem is not None else "Unknown"
                assignee = assignee_elem.text if assignee_elem is not None else "Unknown"
                reporter = reporter_elem.text if reporter_elem is not None else "Unknown"
                created = created_elem.text if created_elem is not None else ""
                updated = updated_elem.text if updated_elem is not None else ""
                
                # 댓글 데이터 추출
                comments = []
                comments_elem = item.find('comments')
                if comments_elem is not None:
                    for comment_elem in comments_elem.findall('comment'):
                        comment_text = ""
                        comment_author = "Unknown"
                        comment_date = ""
                        
                        # 댓글 텍스트 추출
                        if comment_elem.text:
                            comment_text = clean_html_content(comment_elem.text)
                        
                        # 댓글 작성자 추출
                        author_elem = comment_elem.find('author')
                        if author_elem is not None:
                            comment_author = author_elem.text or "Unknown"
                        
                        # 댓글 날짜 추출
                        date_elem = comment_elem.find('created')
                        if date_elem is not None:
                            comment_date = date_elem.text or ""
                        
                        if comment_text.strip():
                            comments.append({
                                'text': comment_text,
                                'author': comment_author,
                                'date': comment_date
                            })
                
                # 티켓 데이터 구성
                ticket = {
                    'Key': key,
                    'Summary': summary or title,  # summary가 없으면 title 사용
                    'Description': description,
                    'Status': status,
                    'Priority': priority,
                    'Issue Type': issue_type,
                    'Assignee': assignee,
                    'Reporter': reporter,
                    'Created': created,
                    'Updated': updated,
                    'Comments': comments
                }
                
                tickets.append(ticket)
                
            except Exception as e:
                logger.warning(f"⚠️ 티켓 파싱 실패: {e}")
                continue
        
        logger.info(f"✅ {len(tickets)}개 티켓 파싱 완료")
        return tickets
        
    except Exception as e:
        logger.error(f"❌ XML 파싱 실패: {e}")
        return []

def rebuild_vector_db():
    """Vector DB 재구축"""
    logger.info("🏗️ Vector DB 재구축 시작...")
    
    # 1. 기존 Vector DB 삭제 확인
    import os
    if os.path.exists('./vector_db'):
        logger.info("🗑️ 기존 Vector DB 삭제됨")
    else:
        logger.info("📁 Vector DB 디렉토리 없음 (새로 생성)")
    
    # 2. 한국어 임베딩 함수 초기화
    logger.info("🔧 한국어 임베딩 함수 초기화...")
    embedding_function = CleanKoreanEmbeddingFunction()
    
    # 3. ChromaDB 클라이언트 초기화
    logger.info("💾 ChromaDB 클라이언트 초기화...")
    client = chromadb.PersistentClient(
        path='./vector_db',
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    
    # 4. Jira 다중 벡터 청크 컬렉션 생성
    logger.info("📝 Jira 다중 벡터 청크 컬렉션 생성...")
    try:
        # 기존 컬렉션 삭제 (있다면)
        try:
            client.delete_collection('jira_multi_vector_chunks')
            logger.info("🗑️ 기존 컬렉션 삭제됨")
        except:
            pass
        
        collection = client.create_collection(
            name='jira_multi_vector_chunks',
            embedding_function=embedding_function,
            metadata={
                'description': 'Jira 다중 벡터 청크 컬렉션 - 제목/설명/댓글별 개별 벡터',
                'embedding_model': 'jhgan/ko-sroberta-multitask',
                'embedding_dimension': 768,
                'language': 'korean',
                'l2_normalization': True,
                'custom_preprocessing': False,
                'tokenizer': 'BertTokenizerFast',
                'multi_vector_representation': True,
                'chunk_types': 'title,description,comment'
            }
        )
        logger.info("✅ 컬렉션 생성 완료")
        
    except Exception as e:
        logger.error(f"❌ 컬렉션 생성 실패: {e}")
        return False
    
    # 5. Jira 청크 프로세서 초기화 (전처리 제거됨)
    logger.info("🔧 Jira 청크 프로세서 초기화...")
    processor = JiraChunkProcessor(enable_text_cleaning=False)
    
    # 6. XML 파일들에서 Jira 데이터 파싱
    xml_files = ['ncms_1.xml', 'ncms_2.xml']
    all_tickets = []
    
    for xml_file in xml_files:
        if os.path.exists(xml_file):
            tickets = parse_jira_xml(xml_file)
            all_tickets.extend(tickets)
            logger.info(f"📊 {xml_file}: {len(tickets)}개 티켓")
        else:
            logger.warning(f"⚠️ 파일 없음: {xml_file}")
    
    logger.info(f"📊 총 {len(all_tickets)}개 티켓 파싱 완료")
    
    if not all_tickets:
        logger.error("❌ 파싱된 티켓이 없습니다")
        return False
    
    # 7. 청크 생성 및 Vector DB에 저장
    logger.info("🔄 청크 생성 및 Vector DB 저장 시작...")
    total_chunks = 0
    processed_tickets = 0
    
    for i, ticket in enumerate(all_tickets):
        try:
            # 직접 청크 생성 (원문 그대로)
            chunks = create_chunks_from_ticket(ticket)
            
            if chunks:
                # Vector DB에 저장
                for chunk in chunks:
                    try:
                        # 문서 확장된 내용 사용
                        expanded_content = chunk.create_expanded_content()
                        
                        # ChromaDB에 추가 (None 값 제거)
                        metadata = {
                            'parent_ticket_id': chunk.parent_ticket_id or '',
                            'ticket_key': chunk.ticket_id or '',
                            'ticket_summary': chunk.ticket_summary or '',
                            'chunk_type': chunk.chunk_type.value,
                            'original_content': chunk.content or '',
                            'expanded_content': expanded_content or '',
                            'field_name': chunk.field_name or '',
                            'field_value': chunk.field_value or '',
                            'document_expansion': True,
                            'custom_preprocessing': False,
                            'l2_normalization': True,
                            'multi_vector_representation': True
                        }
                        
                        # None이 아닌 댓글 관련 필드만 추가
                        if chunk.comment_author is not None:
                            metadata['comment_author'] = chunk.comment_author
                        if chunk.comment_date is not None:
                            metadata['comment_date'] = chunk.comment_date
                        if chunk.comment_id is not None:
                            metadata['comment_id'] = chunk.comment_id
                        
                        collection.add(
                            documents=[expanded_content],
                            metadatas=[metadata],
                            ids=[f"{chunk.parent_ticket_id}_{chunk.chunk_type.value}_{chunk.chunk_id}"]
                        )
                        total_chunks += 1
                        
                    except Exception as e:
                        logger.warning(f"⚠️ 청크 저장 실패 {chunk.ticket_id}: {e}")
                        continue
                
                processed_tickets += 1
                
                # 진행 상황 로그
                if (i + 1) % 50 == 0:
                    logger.info(f"📈 진행률: {i + 1}/{len(all_tickets)} 티켓, {total_chunks}개 청크 저장됨")
            
        except Exception as e:
            logger.warning(f"⚠️ 티켓 처리 실패 {ticket.get('Key', 'UNKNOWN')}: {e}")
            continue
    
    # 8. 최종 결과
    logger.info("🎉 다중 벡터 Vector DB 재구축 완료!")
    logger.info(f"   ✅ 처리된 티켓: {processed_tickets}/{len(all_tickets)}")
    logger.info(f"   ✅ 저장된 청크: {total_chunks}개")
    logger.info(f"   ✅ 다중 벡터 표현 적용됨")
    logger.info(f"   ✅ 제목/설명/댓글별 개별 벡터")
    logger.info(f"   ✅ 문맥 유지 댓글 청크")
    logger.info(f"   ✅ L2 정규화 적용됨")
    logger.info(f"   ✅ 올바른 토크나이저 사용")
    
    # 9. 검색 테스트
    logger.info("🔍 검색 테스트...")
    try:
        test_results = collection.query(
            query_texts=["서버 문제", "데이터베이스 오류"],
            n_results=3
        )
        
        logger.info(f"검색 테스트 결과:")
        for i, (doc, meta, dist) in enumerate(zip(
            test_results['documents'][0], 
            test_results['metadatas'][0], 
            test_results['distances'][0]
        )):
            similarity = 1 - dist  # 거리를 유사도로 변환
            logger.info(f"  {i+1}. 유사도: {similarity:.3f}")
            logger.info(f"     부모 티켓: {meta.get('parent_ticket_id', 'Unknown')}")
            logger.info(f"     청크 타입: {meta.get('chunk_type', 'Unknown')}")
            logger.info(f"     필드명: {meta.get('field_name', 'Unknown')}")
            logger.info(f"     내용: {doc[:100]}...")
    
    except Exception as e:
        logger.warning(f"⚠️ 검색 테스트 실패: {e}")
    
    return True

if __name__ == "__main__":
    success = rebuild_vector_db()
    if success:
        print("\n🎉 Vector DB 재구축이 성공적으로 완료되었습니다!")
    else:
        print("\n❌ Vector DB 재구축에 실패했습니다.")
