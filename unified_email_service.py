#!/usr/bin/env python3
"""
통합 이메일 서비스 (리팩토링 버전)
- app.py의 파라미터 기반 요청을 처리하도록 수정
- 백엔드 로직과 Streamlit UI 코드(st.*) 분리
- 로직 단순화 및 역할 명확화
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Streamlit은 UI 피드백용으로만 제한적으로 사용
import streamlit as st

from email_provider import create_provider, get_available_providers, get_default_provider
from email_models import EmailMessage, EmailSearchResult, EmailPriority
from memory_based_ticket_processor import MemoryBasedTicketProcessorTool

# TicketCreationStatus enum 정의 (memory_based_ticket_processor에서 가져옴)
class TicketCreationStatus(str):
    """티켓 생성 상태"""
    SHOULD_CREATE = "should_create"      # 티켓 생성해야 함
    ALREADY_EXISTS = "already_exists"    # 이미 티켓이 존재함
    NO_TICKET_NEEDED = "no_ticket_needed"  # 티켓 생성 불필요
from gmail_api_client import get_gmail_client
from vector_db_models import VectorDBManager

# Memory-Based Ticket Processor Tool import
from memory_based_ticket_processor import create_memory_based_ticket_processor

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_emails_sync(provider_name: str, use_classifier: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """
    동기적으로 이메일을 가져오는 함수
    
    Args:
        provider_name: 이메일 제공자 이름 (gmail, outlook 등)
        use_classifier: 분류기 사용 여부
        max_results: 최대 결과 수
        
    Returns:
        Dict: 이메일 데이터와 메타데이터
    """
    try:
        service = UnifiedEmailService(provider_name)
        # 모든 메일 가져오기 (읽은 메일 + 안 읽은 메일)
        emails = service.get_all_emails(max_results)
        
        if not emails:
            return {
                'tickets': [],
                'summary': {
                    'reason': '가져올 메일이 없습니다.',
                    'total_emails': 0,
                    'applied_filters': {}
                }
            }
        
        # 이메일을 티켓 형태로 변환
        tickets = []
        for email in emails:
            # EmailMessage 객체를 딕셔너리로 변환하여 JSON 직렬화 가능하게 만듦
            email_dict = email.model_dump()
            ticket = {
                'ticket_id': email_dict.get('id'),
                'title': email_dict.get('subject'),
                'sender': email_dict.get('sender'),
                'content': email_dict.get('body') or '메일 내용을 불러올 수 없습니다.',
                'description': email_dict.get('body') or '메일 내용이 없습니다.',
                'status': 'pending' if not email_dict.get('is_read') else 'closed',
                'priority': email_dict.get('priority', 'Medium'),
                'type': 'email',
                'reporter': email_dict.get('sender'),
                'created_at': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                'action': '메일 수신',
                'is_read': email_dict.get('is_read', False)
            }
            tickets.append(ticket)
        
        return {
            'tickets': tickets,
            'summary': {
                'reason': f'요청하신 조건에 맞는 {len(tickets)}개의 메일을 조회했습니다.',
                'total_emails': len(tickets),
                'applied_filters': {}
            }
        }
        
    except Exception as e:
        logging.error(f"fetch_emails_sync 오류: {str(e)}")
        return {
            'tickets': [],
            'summary': {
                'reason': f'메일 조회 중 오류가 발생했습니다: {str(e)}',
                'total_emails': 0,
                'applied_filters': {}
            }
        }

def _apply_filters_to_emails(emails: List[EmailMessage], filters: Dict[str, Any]) -> List[EmailMessage]:
    """메일 목록에 필터 딕셔너리를 적용합니다."""
    logging.info(f"필터 적용 시작: {len(emails)}개 메일, 필터: {filters}")
    
    if not filters:
        logging.info("필터가 없어 모든 메일 반환")
        return emails

    filtered_emails = emails.copy()
    
    if filters.get('is_read') is not None:
        is_read_filter = filters['is_read']
        logging.info(f"is_read 필터 적용: {is_read_filter}")
        
        # 필터링 전 상태
        before_count = len(filtered_emails)
        before_read = sum(1 for e in filtered_emails if e.is_read == is_read_filter)
        before_opposite = sum(1 for e in filtered_emails if e.is_read != is_read_filter)
        logging.info(f"필터링 전 - 조건에 맞는 메일: {before_read}개, 맞지 않는 메일: {before_opposite}개")
        
        # 필터링 적용
        filtered_emails = [e for e in filtered_emails if e.is_read == is_read_filter]
        
        # 필터링 후 상태
        after_count = len(filtered_emails)
        logging.info(f"is_read 필터 적용 후: {before_count}개 → {after_count}개")
        
        # 필터링된 메일 샘플 로깅
        if filtered_emails:
            sample_emails = filtered_emails[:3]  # 처음 3개만
            for i, email in enumerate(sample_emails):
                logging.info(f"  샘플 {i+1}: ID={email.id}, is_read={email.is_read}")
    
    if 'sender' in filters:
        sender = filters['sender'].lower()
        logging.info(f"sender 필터 적용: {sender}")
        before_count = len(filtered_emails)
        filtered_emails = [e for e in filtered_emails if sender in (e.sender or '').lower()]
        after_count = len(filtered_emails)
        logging.info(f"sender 필터 적용 후: {before_count}개 → {after_count}개")
    
    # ... 기타 필요한 필터 로직 추가 ...
    
    logging.info(f"최종 필터링 결과: {len(filtered_emails)}개 메일")
    return filtered_emails

class UnifiedEmailService:
    """통합 이메일 서비스 로직을 담당하는 클래스"""
    
    def __init__(self, provider_name: str = None):
        self.provider_name = provider_name or get_default_provider()
        self.provider = create_provider(self.provider_name)
        # 분류기는 필요할 때만 초기화하여 리소스 절약
        self.classifier = None

    def _build_gmail_query(self, filters: Dict[str, Any]) -> str:
        """필터 딕셔너리를 Gmail API의 q 파라미터로 변환합니다."""
        query_parts = []
        
        # 읽음 상태 필터
        if filters.get('is_read') is not None:
            if filters['is_read']:
                query_parts.append("is:read")  # 읽은 메일
            else:
                query_parts.append("is:unread")  # 안 읽은 메일
        
        # 발신자 필터
        if 'sender' in filters:
            sender = filters['sender']
            if '@' in sender:
                query_parts.append(f"from:{sender}")
            else:
                query_parts.append(f"from:{sender}")
        
        # 제목 필터
        if 'subject' in filters:
            query_parts.append(f"subject:{filters['subject']}")
        
        # 첨부파일 필터
        if filters.get('has_attachments') is not None:
            if filters['has_attachments']:
                query_parts.append("has:attachment")
            else:
                query_parts.append("-has:attachment")
        
        # 날짜 필터
        if 'date_after' in filters:
            query_parts.append(f"after:{filters['date_after']}")
        if 'date_before' in filters:
            query_parts.append(f"before:{filters['date_before']}")
        
        # 기본 쿼리 (최신 메일부터)
        if not query_parts:
            query_parts.append("is:any")
        
        # 쿼리 조합
        final_query = " ".join(query_parts)
        logging.info(f"Gmail 쿼리 구성: {final_query}")
        
        return final_query

    def _init_classifier(self):
        """필요 시점에 Memory-Based 학습 분류기를 초기화합니다."""
        if not self.classifier:
            try:
                self.classifier = MemoryBasedTicketProcessorTool()
                logging.info("Memory-Based 학습 분류기 초기화 완료")
            except Exception as e:
                logging.warning(f"Memory-Based 학습 분류기 초기화 실패: {e}")
                raise e

    def fetch_emails(self, filters: Optional[Dict[str, Any]] = None) -> List[EmailMessage]:
        """Gmail API의 q 파라미터를 사용하여 서버 레벨에서 필터링된 이메일을 가져옵니다."""
        try:
            # Gmail API 쿼리 구성
            gmail_query = self._build_gmail_query(filters or {})
            logging.info(f"Gmail API 쿼리 구성: {gmail_query}")
            
            # Gmail API 클라이언트 가져오기
            gmail_client = get_gmail_client()
            
            if not gmail_client.authenticate():
                logging.error("Gmail API 인증 실패")
                return []
            
            # LLM의 limit 값을 Gmail API maxResults에 반영
            max_results = filters.get('limit', 100)  # 기본값 100, LLM limit 값 우선
            logging.info(f"Gmail API maxResults 설정: {max_results}")
            
            # Gmail API에서 필터링된 메일 가져오기
            gmail_emails = gmail_client.get_emails_with_query(gmail_query, max_results=max_results)
            
            if not gmail_emails:
                logging.info("조건에 맞는 메일이 없습니다.")
                return []
            
            logging.info(f"Gmail API에서 {len(gmail_emails)}개 메일 가져옴")
            
            # Gmail 데이터를 EmailMessage 형식으로 변환
            email_messages = []
            
            for gmail_data in gmail_emails:
                try:
                    # 메일 본문에서 HTML 태그 제거 (간단한 정리)
                    body = gmail_data.get('body', '')
                    if body:
                        # HTML 태그 제거 (간단한 방법)
                        import re
                        body = re.sub(r'<[^>]+>', '', body)
                        body = re.sub(r'\s+', ' ', body).strip()
                    
                    # Gmail API 데이터 상태 로깅
                    gmail_unread = gmail_data.get('unread', False)
                    calculated_is_read = not gmail_unread
                    logging.info(f"메일 {gmail_data['id']}: Gmail unread={gmail_unread}, 계산된 is_read={calculated_is_read}")
                    
                    # EmailMessage 생성
                    email_msg = EmailMessage(
                        id=gmail_data['id'],  # Gmail의 실제 message_id
                        subject=gmail_data.get('subject', '제목 없음'),
                        sender=gmail_data.get('from', '발신자 없음'),
                        body=body,
                        received_date=datetime.now(),  # 실제 날짜 파싱 필요
                        is_read=calculated_is_read,
                        priority=EmailPriority.NORMAL,
                        has_attachments=False  # 첨부파일 확인 로직 필요
                    )
                    
                    email_messages.append(email_msg)
                    
                    # VectorDB 저장 제거 - 티켓 생성 프로세스에서만 저장
                    logging.info(f"메일 {gmail_data['id']} VectorDB 저장 건너뜀 (티켓 생성 시에만 저장)")
                    
                except Exception as e:
                    logging.error(f"메일 변환 오류 (ID: {gmail_data.get('id', 'N/A')}): {str(e)}")
                    continue
            
            # Gmail API에서 이미 maxResults로 제한했으므로 추가 제한 불필요
            logging.info(f"최종 반환 메일 수: {len(email_messages)}개")
            return email_messages
            
        except Exception as e:
            logging.error(f"fetch_emails 오류: {str(e)}")
            return []

    def get_all_emails(self, max_results: int = 50) -> List[EmailMessage]:
        """실제 Gmail API를 사용하여 모든 메일을 가져옵니다"""
        try:
            # Gmail API 클라이언트 가져오기
            gmail_client = get_gmail_client()
            
            if not gmail_client.authenticate():
                logging.error("Gmail API 인증 실패")
                return []
            
            # 실제 Gmail에서 모든 메일 가져오기 (읽은 메일 + 안 읽은 메일)
            gmail_emails = gmail_client.get_all_emails(max_results)
            
            if not gmail_emails:
                logging.info("가져올 메일이 없습니다.")
                return []
            
            # Gmail 데이터를 EmailMessage 형식으로 변환
            email_messages = []
            
            for gmail_data in gmail_emails:
                try:
                    # 메일 본문에서 HTML 태그 제거 (간단한 정리)
                    body = gmail_data.get('body', '')
                    if body:
                        # HTML 태그 제거 (간단한 방법)
                        import re
                        body = re.sub(r'<[^>]+>', '', body)
                        body = re.sub(r'\s+', ' ', body).strip()
                    
                    # Gmail API 데이터 상태 로깅
                    gmail_unread = gmail_data.get('unread', False)
                    calculated_is_read = not gmail_unread
                    logging.info(f"메일 {gmail_data['id']}: Gmail unread={gmail_unread}, 계산된 is_read={calculated_is_read}")
                    
                    # EmailMessage 생성
                    email_msg = EmailMessage(
                        id=gmail_data['id'],  # Gmail의 실제 message_id
                        subject=gmail_data.get('subject', '제목 없음'),
                        sender=gmail_data.get('from', '발신자 없음'),
                        body=body,
                        received_date=datetime.now(),  # 실제 날짜 파싱 필요
                        is_read=calculated_is_read,
                        priority=EmailPriority.NORMAL,
                        has_attachments=False  # 첨부파일 확인 로직 필요
                    )
                    
                    email_messages.append(email_msg)
                    
                    # VectorDB 저장 제거 - 티켓 생성 프로세스에서만 저장
                    logging.info(f"메일 {gmail_data['id']} VectorDB 저장 건너뜀 (티켓 생성 시에만 저장)")
                    
                except Exception as e:
                    logging.error(f"메일 변환 오류: {str(e)}")
                    continue
            
            logging.info(f"Gmail에서 {len(email_messages)}개 메일을 가져왔습니다.")
            return email_messages
            
        except Exception as e:
            logging.error(f"get_all_emails 오류: {str(e)}")
            return []

    def process_tickets(self, emails: List[EmailMessage], user_query: str) -> Dict[str, Any]:
        """가져온 이메일 목록으로 티켓 처리 로직을 실행합니다."""
        import logging
        logging.info(f"process_tickets 시작: {len(emails)}개 메일, query={user_query}")
        
        self._init_classifier()
        if not self.classifier:
            logging.error("티켓 처리를 위한 분류기를 사용할 수 없습니다.")
            raise RuntimeError("티켓 처리를 위한 분류기를 사용할 수 없습니다.")

        logging.info("분류기 초기화 완료")

        tickets = []
        new_tickets = 0
        existing_tickets = 0

        for i, email in enumerate(emails):
            logging.info(f"메일 {i+1}/{len(emails)} 처리: {email.subject}")
            
            # EmailMessage 객체를 딕셔너리로 변환하여 JSON 직렬화 가능하게 만듦
            email_dict = email.model_dump()
            logging.info(f"메일 {i+1} 딕셔너리 변환 완료: {email_dict.get('subject')}")
            
            ticket_status, reason, details = self.classifier.should_create_ticket(email_dict, user_query)
            logging.info(f"메일 {i+1} 티켓 상태: {ticket_status}, 이유: {reason}")

            if ticket_status == TicketCreationStatus.SHOULD_CREATE:
                logging.info(f"메일 {i+1} 티켓 생성 시작")
                ticket = self.classifier.create_ticket_from_email(email_dict, user_query)
                if ticket:
                    # SQLite에 티켓 저장
                    try:
                        from sqlite_ticket_models import SQLiteTicketManager, Ticket
                        ticket_manager = SQLiteTicketManager()
                        
                        # Ticket 객체 생성
                        db_ticket = Ticket(
                            ticket_id=None,  # SQLite에서 자동 생성
                            original_message_id=ticket.get('original_message_id', ''),
                            status=ticket.get('status', 'pending'),
                            title=ticket.get('title', ''),
                            description=ticket.get('description', ''),
                            priority=ticket.get('priority', 'Medium'),
                            ticket_type=ticket.get('type', 'Task'),
                            reporter=ticket.get('reporter', ''),
                            reporter_email='',
                            labels=ticket.get('labels', []),  # 생성된 레이블 사용
                            created_at=ticket.get('created_at', ''),
                            updated_at=ticket.get('created_at', '')
                        )
                        
                        # SQLite에 저장
                        ticket_id = ticket_manager.insert_ticket(db_ticket)
                        ticket['ticket_id'] = ticket_id
                        logging.info(f"메일 {i+1} SQLite 저장 성공: ticket_id={ticket_id}")
                        
                    except Exception as e:
                        logging.error(f"메일 {i+1} SQLite 저장 실패: {str(e)}")
                    
                    tickets.append(ticket)
                    new_tickets += 1
                    logging.info(f"메일 {i+1} 티켓 생성 성공: {ticket}")
                else:
                    logging.warning(f"메일 {i+1} 티켓 생성 실패")
            elif ticket_status == TicketCreationStatus.ALREADY_EXISTS:
                logging.info(f"메일 {i+1} 기존 티켓 발견")
                # 간단한 기존 티켓 정보 생성
                tickets.append({'ticket_id': details.get('ticket_id', 'N/A'), 'title': email.subject, 'status': 'existing'})
                existing_tickets += 1
            else:
                logging.info(f"메일 {i+1} 티켓 생성 불필요: {reason}")
        
        logging.info(f"티켓 처리 완료: 총 {len(tickets)}개, 새로 생성: {new_tickets}개, 기존: {existing_tickets}개")
        
        result = {
            'display_mode': 'tickets',
            'tickets': tickets,
            'new_tickets_created': new_tickets,
            'existing_tickets_found': existing_tickets,
            'summary': { 'total_tasks': len(tickets) }
        }
        
        logging.info(f"최종 결과: {result}")
        return result

# --- app.py에서 호출할 공용 함수들 ---

def get_raw_emails(provider_name: str, filters: Dict[str, Any]) -> List[EmailMessage]:
    """필터링된 순수 이메일 목록을 가져옵니다."""
    service = UnifiedEmailService(provider_name)
    return service.fetch_emails(filters)

def process_emails_with_ticket_logic(provider_name: str, user_query: str = None) -> Dict[str, Any]:
    """메일을 가져와 티켓 처리까지 완료합니다."""
    try:
        import logging
        logging.info(f"process_emails_with_ticket_logic 시작: provider={provider_name}, query={user_query}")
        
        service = UnifiedEmailService(provider_name)
        logging.info(f"UnifiedEmailService 생성 완료: {service}")
        
        # 1. 모든 메일을 가져옵니다.
        logging.info("get_all_emails 호출 시작...")
        emails_to_process = service.get_all_emails(max_results=50)
        logging.info(f"get_all_emails 결과: {len(emails_to_process)}개 메일")
        
        if not emails_to_process:
            logging.warning("처리할 메일이 없습니다.")
            return {
                'display_mode': 'no_emails', 
                'message': '처리할 새 메일이 없습니다.',
                'tickets': [],
                'non_work_emails': []
            }
        
        # 2. 가져온 메일을 티켓 로직으로 처리합니다.
        logging.info(f"process_tickets 호출 시작: {len(emails_to_process)}개 메일")
        # user_query가 파라미터 딕셔너리인 경우 기본 티켓 생성 쿼리로 변경
        actual_query = "오늘 처리할 티켓 목록" if isinstance(user_query, str) and user_query.startswith('{') else (user_query or '오늘 처리할 티켓 목록')
        logging.info(f"실제 사용할 쿼리: {actual_query}")
        
        # 메일 분류 및 티켓 생성
        tickets = []
        non_work_emails = []
        new_tickets = 0
        existing_tickets = 0
        
        service._init_classifier()
        if not service.classifier:
            logging.error("티켓 처리를 위한 분류기를 사용할 수 없습니다.")
            raise RuntimeError("티켓 처리를 위한 분류기를 사용할 수 없습니다.")
        
        for i, email in enumerate(emails_to_process):
            logging.info(f"메일 {i+1}/{len(emails_to_process)} 처리: {email.subject}")
            
            # EmailMessage 객체를 딕셔너리로 변환하여 JSON 직렬화 가능하게 만듦
            email_dict = email.model_dump()
            logging.info(f"메일 {i+1} 딕셔너리 변환 완료: {email_dict.get('subject')}")
            
            # EmailMessage를 Mail 객체로 변환하여 Vector DB에 저장
            try:
                from vector_db_models import Mail
                from datetime import datetime
                
                mail = Mail(
                    message_id=email_dict.get('id', f'email_{i}_{datetime.now().timestamp()}'),
                    original_content=email_dict.get('body', ''),
                    refined_content=email_dict.get('body', '')[:500] + '...' if len(email_dict.get('body', '')) > 500 else email_dict.get('body', ''),
                    sender=email_dict.get('sender', ''),
                    status='acceptable',
                    subject=email_dict.get('subject', ''),
                    received_datetime=email_dict.get('received_date', datetime.now().isoformat()),
                    content_type='text',
                    has_attachment=email_dict.get('has_attachments', False),
                    extraction_method='email_provider',
                    content_summary=email_dict.get('body', '')[:200] + '...' if len(email_dict.get('body', '')) > 200 else email_dict.get('body', ''),
                    key_points=[],
                    created_at=datetime.now().isoformat()
                )
                
                # Vector DB에 메일 저장
                from vector_db_models import VectorDBManager
                vector_db = VectorDBManager()
                vector_save_success = vector_db.save_mail(mail)
                if vector_save_success:
                    logging.info(f"✅ 메일 {i+1} Vector DB 저장 성공: {mail.message_id}")
                else:
                    logging.warning(f"⚠️ 메일 {i+1} Vector DB 저장 실패: {mail.message_id}")
                    
            except Exception as e:
                logging.error(f"메일 {i+1} Vector DB 저장 중 오류: {str(e)}")
            
            # Memory-Based 학습 시스템으로 메일 처리
            logging.info(f"메일 {i+1} Memory-Based 학습 시스템으로 처리 시작")
            
            try:
                # MemoryBasedTicketProcessorTool 실행
                result_json = service.classifier._run(
                    email_content=email_dict.get('body', ''),
                    email_subject=email_dict.get('subject', ''),
                    email_sender=email_dict.get('sender', ''),
                    message_id=email_dict.get('id', '')
                )
                
                # 결과 파싱
                import json
                result = json.loads(result_json)
                
                if result.get('success'):
                    decision = result.get('decision', {})
                    ticket_creation_decision = decision.get('ticket_creation_decision', {})
                    
                    decision_type = ticket_creation_decision.get('decision', 'create_ticket')
                    reason = ticket_creation_decision.get('reason', 'AI 판단')
                    
                    if decision_type == 'create_ticket':
                        ticket_status = TicketCreationStatus.SHOULD_CREATE
                        # 티켓 데이터 생성
                        ticket = {
                            'title': email_dict.get('subject', '제목 없음'),
                            'description': email_dict.get('body', '내용 없음'),
                            'status': 'pending',
                            'priority': ticket_creation_decision.get('priority', 'Medium'),
                            'type': ticket_creation_decision.get('ticket_type', 'Task'),
                            'reporter': email_dict.get('sender', '알 수 없음'),
                            'labels': ticket_creation_decision.get('labels', ['일반', '업무']),
                            'created_at': datetime.now().isoformat(),
                            'message_id': email_dict.get('id', ''),
                            'memory_based_decision': True,
                            'ai_reasoning': reason
                        }
                    else:
                        ticket_status = TicketCreationStatus.NO_TICKET_NEEDED
                        ticket = None
                else:
                    logging.error(f"Memory-Based 시스템 실행 실패: {result.get('error')}")
                    ticket_status = TicketCreationStatus.NO_TICKET_NEEDED
                    ticket = None
                    
            except Exception as e:
                logging.error(f"Memory-Based 시스템 실행 중 오류: {str(e)}")
                # 폴백: 기본 분류 로직 사용
                ticket_status = TicketCreationStatus.SHOULD_CREATE
                ticket = {
                    'title': email_dict.get('subject', '제목 없음'),
                    'description': email_dict.get('body', '내용 없음'),
                    'status': 'pending',
                    'priority': 'Medium',
                    'type': 'Task',
                    'reporter': email_dict.get('sender', '알 수 없음'),
                    'labels': ['일반', '업무'],
                    'created_at': datetime.now().isoformat(),
                    'message_id': email_dict.get('id', ''),
                    'memory_based_decision': False,
                    'fallback_reason': 'Memory-Based 시스템 오류'
                }
            
            logging.info(f"메일 {i+1} 처리 결과: {ticket_status}, 이유: {reason}")

            if ticket_status == TicketCreationStatus.SHOULD_CREATE:
                logging.info(f"메일 {i+1} 티켓 생성 시작")
                if ticket:
                    # SQLite에 티켓 저장
                    try:
                        from sqlite_ticket_models import SQLiteTicketManager, Ticket
                        ticket_manager = SQLiteTicketManager()
                        
                        # Ticket 객체 생성
                        db_ticket = Ticket(
                            ticket_id=None,  # SQLite에서 자동 생성
                            original_message_id=mail.message_id,  # Vector DB에 저장된 메일 ID 사용
                            status=ticket.get('status', 'pending'),
                            title=ticket.get('title', ''),
                            description='',  # 티켓 설명은 빈 문자열로 초기화
                            priority=ticket.get('priority', 'Medium'),
                            ticket_type=ticket.get('type', 'Task'),
                            reporter=ticket.get('reporter', ''),
                            reporter_email='',
                            labels=ticket.get('labels', []),  # 생성된 레이블 사용
                            created_at=ticket.get('created_at', ''),
                            updated_at=ticket.get('created_at', '')
                        )
                        
                        # SQLite에 저장
                        ticket_id = ticket_manager.insert_ticket(db_ticket)
                        ticket['ticket_id'] = ticket_id
                        logging.info(f"메일 {i+1} SQLite 저장 성공: ticket_id={ticket_id}")
                        
                    except Exception as e:
                        logging.error(f"메일 {i+1} SQLite 저장 실패: {str(e)}")
                    
                    # 티켓에 message_id 추가 (description은 빈 문자열로 초기화)
                    ticket['message_id'] = mail.message_id
                    ticket['description'] = ''
                    tickets.append(ticket)
                    new_tickets += 1
                    logging.info(f"메일 {i+1} 티켓 생성 성공: {ticket}")
                else:
                    logging.warning(f"메일 {i+1} 티켓 생성 실패")
            elif ticket_status == TicketCreationStatus.ALREADY_EXISTS:
                logging.info(f"메일 {i+1} 기존 티켓 발견")
                # 간단한 기존 티켓 정보 생성
                tickets.append({
                    'ticket_id': details.get('ticket_id', 'N/A'), 
                    'message_id': mail.message_id,
                    'title': email.subject, 
                    'status': 'existing',
                    'description': ''  # 기존 티켓도 description은 빈 문자열
                })
                existing_tickets += 1
            else:
                logging.info(f"메일 {i+1} 티켓 생성 불필요: {reason}")
                # 업무용이 아닌 메일을 non_work_emails에 추가
                non_work_email = {
                    'id': email_dict.get('id'),
                    'subject': email_dict.get('subject', '제목 없음'),
                    'sender': email_dict.get('sender', '발신자 없음'),
                    'body': email_dict.get('body', '내용 없음'),
                    'received_date': email_dict.get('received_date'),
                    'is_read': email_dict.get('is_read', False),
                    'priority': email_dict.get('priority', 'Normal'),
                    'classification_reason': reason
                }
                non_work_emails.append(non_work_email)
        
        logging.info(f"티켓 처리 완료: 총 {len(tickets)}개, 새로 생성: {new_tickets}개, 기존: {existing_tickets}개, 업무용 아님: {len(non_work_emails)}개")
        
        result = {
            'display_mode': 'tickets',
            'tickets': tickets,
            'non_work_emails': non_work_emails,
            'new_tickets_created': new_tickets,
            'existing_tickets_found': existing_tickets,
            'summary': { 'total_tasks': len(tickets) }
        }
        
        logging.info(f"최종 결과: {result}")
        return result
        
    except Exception as e:
        import logging
        logging.error(f"process_emails_with_ticket_logic 오류: {str(e)}")
        import traceback
        logging.error(f"오류 상세: {traceback.format_exc()}")
        return {
            'display_mode': 'error',
            'message': f'메일 처리 중 오류가 발생했습니다: {str(e)}',
            'error': str(e),
            'tickets': [],
            'non_work_emails': []
        }

def create_ticket_from_single_email(email_data: dict) -> Dict[str, Any]:
    """
    단일 이메일을 티켓으로 변환하는 함수
    
    Args:
        email_data: 이메일 데이터 딕셔너리
        
    Returns:
        생성된 티켓 정보
    """
    try:
        import logging
        logging.info(f"create_ticket_from_single_email 시작: {email_data.get('subject', '제목 없음')}")
        
        # 기본 제공자로 UnifiedEmailService 생성
        service = UnifiedEmailService()
        service._init_classifier()
        
        if not service.classifier:
            logging.error("티켓 생성을 위한 분류기를 사용할 수 없습니다.")
            raise RuntimeError("티켓 생성을 위한 분류기를 사용할 수 없습니다.")
        
        # Memory-Based 학습 시스템으로 티켓 생성
        try:
            result_json = service.classifier._run(
                email_content=email_data.get('body', ''),
                email_subject=email_data.get('subject', ''),
                email_sender=email_data.get('sender', ''),
                message_id=email_data.get('id', '')
            )
            
            # 결과 파싱
            import json
            result = json.loads(result_json)
            
            if result.get('success'):
                decision = result.get('decision', {})
                ticket_creation_decision = decision.get('ticket_creation_decision', {})
                
                if ticket_creation_decision.get('decision') == 'create_ticket':
                    # 티켓 데이터 생성
                    ticket = {
                        'title': email_data.get('subject', '제목 없음'),
                        'description': email_data.get('body', '내용 없음'),
                        'status': 'pending',
                        'priority': ticket_creation_decision.get('priority', 'Medium'),
                        'type': ticket_creation_decision.get('ticket_type', 'Task'),
                        'reporter': email_data.get('sender', '알 수 없음'),
                        'labels': ticket_creation_decision.get('labels', ['일반', '업무']),
                        'created_at': datetime.now().isoformat(),
                        'message_id': email_data.get('id', ''),
                        'memory_based_decision': True,
                        'ai_reasoning': ticket_creation_decision.get('reason', 'AI 판단')
                    }
                else:
                    logging.error("AI가 티켓 생성이 불필요하다고 판단했습니다.")
                    raise RuntimeError("AI 판단: 티켓 생성 불필요")
            else:
                logging.error(f"Memory-Based 시스템 실행 실패: {result.get('error')}")
                raise RuntimeError(f"Memory-Based 시스템 오류: {result.get('error')}")
                
        except Exception as e:
            logging.error(f"Memory-Based 시스템 실행 중 오류: {str(e)}")
            # 폴백: 기본 티켓 생성
            ticket = {
                'title': email_data.get('subject', '제목 없음'),
                'description': email_data.get('body', '내용 없음'),
                'status': 'pending',
                'priority': 'Medium',
                'type': 'Task',
                'reporter': email_data.get('sender', '알 수 없음'),
                'labels': ['일반', '업무'],
                'created_at': datetime.now().isoformat(),
                'message_id': email_data.get('id', ''),
                'memory_based_decision': False,
                'fallback_reason': 'Memory-Based 시스템 오류'
            }
        
        if not ticket:
            logging.error("티켓 생성에 실패했습니다.")
            raise RuntimeError("티켓 생성에 실패했습니다.")
        
        # SQLite에 티켓 저장
        try:
            from sqlite_ticket_models import SQLiteTicketManager, Ticket
            ticket_manager = SQLiteTicketManager()
            
            # Ticket 객체 생성
            db_ticket = Ticket(
                ticket_id=None,  # SQLite에서 자동 생성
                original_message_id=ticket.get('original_message_id', ''),
                status=ticket.get('status', 'pending'),
                title=ticket.get('title', ''),
                description=ticket.get('description', ''),
                priority=ticket.get('priority', 'Medium'),
                ticket_type=ticket.get('type', 'Task'),
                reporter=ticket.get('reporter', ''),
                reporter_email='',
                labels=ticket.get('labels', []),  # 생성된 레이블 사용
                created_at=ticket.get('created_at', ''),
                updated_at=ticket.get('created_at', '')
            )
            
            # SQLite에 저장
            ticket_id = ticket_manager.insert_ticket(db_ticket)
            ticket['ticket_id'] = ticket_id
            logging.info(f"SQLite 저장 성공: ticket_id={ticket_id}")
            
        except Exception as e:
            logging.error(f"SQLite 저장 실패: {str(e)}")
            # SQLite 저장 실패해도 티켓은 반환
        
        logging.info(f"티켓 생성 완료: {ticket}")
        return ticket
        
    except Exception as e:
        import logging
        logging.error(f"create_ticket_from_single_email 오류: {str(e)}")
        import traceback
        logging.error(f"오류 상세: {traceback.format_exc()}")
        raise e

def get_email_provider_status(provider_name: str = None) -> Dict[str, Any]:
    """이메일 제공자 상태를 확인합니다."""
    provider = create_provider(provider_name or get_default_provider())
    status = provider.get_provider_status()
    return status.model_dump()

def get_mail_content_by_id(message_id: str) -> Optional[Dict[str, Any]]:
    """VectorDB에서 message_id로 메일 상세 내용을 조회합니다."""
    try:
        vector_db = VectorDBManager()
        mail_data = vector_db.get_mail_by_id(message_id)
        
        if not mail_data:
            logging.warning(f"메일을 찾을 수 없습니다: {message_id}")
            return None
        
        return {
            'message_id': mail_data.message_id,
            'subject': mail_data.subject,
            'sender': mail_data.sender,
            'body': mail_data.original_content,
            'refined_content': mail_data.refined_content,
            'content_summary': mail_data.content_summary,
            'key_points': mail_data.key_points,
            'received_datetime': mail_data.received_datetime,
            'has_attachment': mail_data.has_attachment,
            'status': mail_data.status
        }
        
    except Exception as e:
        logging.error(f"메일 내용 조회 오류: {str(e)}")
        return None