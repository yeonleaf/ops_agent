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
    """안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다."""
    try:
        import logging
        logging.info(f"🔍 process_emails_with_ticket_logic 시작: provider={provider_name}, query={user_query}")
        
        # 1단계: 안 읽은 메일 가져오기
        logging.info("🔍 1단계: 안 읽은 메일 가져오기 시작...")
        try:
            logging.info(f"🔍 UnifiedEmailService({provider_name}) 생성 시도...")
            service = UnifiedEmailService(provider_name)
            logging.info(f"🔍 서비스 생성 완료: {service}")
            
            # 안 읽은 메일 필터 설정
            unread_filters = {
                'is_read': False,  # 안 읽은 메일만
                'limit': 50
            }
            logging.info(f"🔍 안 읽은 메일 필터: {unread_filters}")
            
            logging.info("🔍 fetch_emails(unread_filters) 호출 시도...")
            unread_emails = service.fetch_emails(unread_filters)
            logging.info(f"🔍 안 읽은 메일 {len(unread_emails)}개 발견")
            
            # 첫 번째 메일 정보 로깅
            if unread_emails:
                first_email = unread_emails[0]
                logging.info(f"🔍 첫 번째 메일: id={first_email.id}, subject={first_email.subject}, sender={first_email.sender}")
            else:
                logging.warning("⚠️ 안 읽은 메일이 없습니다")
                return {
                    'display_mode': 'no_emails',
                    'message': '안 읽은 메일이 없습니다.',
                    'tickets': [],
                    'new_tickets_created': 0,
                    'existing_tickets_found': 0
                }
        except Exception as e:
            logging.error(f"❌ 안 읽은 메일 가져오기 실패: {str(e)}")
            import traceback
            logging.error(f"❌ 오류 상세: {traceback.format_exc()}")
            return {
                'display_mode': 'error',
                'message': f'메일 가져오기 실패: {str(e)}',
                'tickets': [],
                'new_tickets_created': 0,
                'existing_tickets_found': 0
            }
        
        # 2단계: LLM 기반 업무용 메일 필터링
        logging.info("🔍 2단계: LLM 기반 업무용 메일 필터링 시작...")
        try:
            # Memory-Based Ticket Processor를 사용하여 LLM이 업무 관련성 판단
            from memory_based_ticket_processor import create_memory_based_ticket_processor
            
            processor = create_memory_based_ticket_processor()
            logging.info(f"🔍 Memory-Based Ticket Processor 생성 완료: {processor}")
            
            work_related_emails = []
            for i, email in enumerate(unread_emails):
                try:
                    logging.info(f"🔍 메일 {i+1}/{len(unread_emails)}: '{email.subject}' 처리 중...")
                    
                    # 메일 내용을 LLM이 분석할 수 있는 형태로 구성
                    email_content = f"제목: {email.subject}\n발신자: {email.sender}\n내용: {email.body}"
                    
                    # LLM을 사용하여 업무 관련성 판단 (판단 근거와 함께)
                    try:
                        # LLM에게 업무 관련성 판단 요청
                        llm_response = processor._run(
                            email_content=email_content,
                            email_subject=email.subject,
                            email_sender=email.sender,
                            message_id=email.id
                        )
                        
                        logging.info(f"🔍 LLM 응답: {llm_response}")
                        
                        # LLM 응답을 JSON으로 파싱
                        try:
                            import json
                            llm_data = json.loads(llm_response)
                            
                            if llm_data.get('success'):
                                # reasoning 단계에서 티켓 생성 여부 판단 (fallback 포함)
                                reasoning_data = llm_data.get('workflow_steps', {}).get('reasoning', {})
                                decision_data = reasoning_data.get('ticket_creation_decision', {})
                                
                                # fallback: workflow_steps가 없으면 최상위 decision 사용
                                if not decision_data:
                                    decision_data = llm_data.get('decision', {}).get('ticket_creation_decision', {})
                                
                                decision = decision_data.get('decision', 'create_ticket')
                                reason = decision_data.get('reason', 'AI 판단 완료')
                                confidence = decision_data.get('confidence', 0.5)
                                priority = decision_data.get('priority', 'Medium')
                                labels = decision_data.get('labels', [])
                                ticket_type = decision_data.get('ticket_type', 'Task')
                                
                                # decision이 'create_ticket'이면 업무 관련으로 판단
                                is_work_related = (decision == 'create_ticket')
                                
                                logging.info(f"🔍 메일 '{email.subject}' LLM 판단 결과: {is_work_related}")
                                logging.info(f"🔍 판단 근거: {reason}")
                                logging.info(f"🔍 신뢰도: {confidence}")
                                logging.info(f"🔍 우선순위: {priority}")
                                logging.info(f"🔍 제안 레이블: {labels}")
                                logging.info(f"🔍 티켓 타입: {ticket_type}")
                                
                                # email 객체에 LLM 분석 결과 저장
                                email._llm_analysis = {
                                    'is_work_related': is_work_related,
                                    'reason': reason,
                                    'confidence': confidence,
                                    'priority': priority,
                                    'suggested_labels': labels,
                                    'ticket_type': ticket_type
                                }
                                
                                if is_work_related:
                                    work_related_emails.append(email)
                                    logging.info(f"✅ LLM이 업무 관련으로 판단: {email.subject}")
                                    logging.info(f"🔍 판단 근거: {reason}")
                                else:
                                    logging.info(f"❌ LLM이 업무 관련이 아니라고 판단: {email.subject}")
                                    logging.info(f"🔍 판단 근거: {reason}")
                                    
                            else:
                                # LLM 실행 실패
                                logging.error(f"⚠️ LLM 실행 실패: {llm_data.get('error', '알 수 없는 오류')}")
                                # 실패 시 기본적으로 포함
                                work_related_emails.append(email)
                                email._llm_analysis = {
                                    'is_work_related': True,
                                    'reason': 'LLM 실행 실패로 인한 기본값',
                                    'confidence': 0.3,
                                    'priority': 'Medium',
                                    'suggested_labels': ['error-fallback'],
                                    'ticket_type': 'Task'
                                }
                                
                        except json.JSONDecodeError as json_error:
                            logging.error(f"⚠️ LLM 응답 JSON 파싱 실패: {str(json_error)}")
                            logging.error(f"⚠️ 원본 응답: {llm_response}")
                            # 파싱 실패 시 기본적으로 포함
                            work_related_emails.append(email)
                            email._llm_analysis = {
                                'is_work_related': True,
                                'reason': 'JSON 파싱 실패로 인한 기본값',
                                'confidence': 0.3,
                                'priority': 'Medium',
                                'suggested_labels': ['parse-error'],
                                'ticket_type': 'Task'
                            }
                            
                    except Exception as llm_error:
                        logging.error(f"⚠️ LLM 판단 실패: {str(llm_error)}")
                        # LLM 실패 시 기본적으로 포함
                        work_related_emails.append(email)
                        logging.warning(f"⚠️ LLM 실패로 인해 메일을 업무 관련으로 간주: {email.subject}")
                        
                except Exception as e:
                    logging.error(f"⚠️ 메일 '{email.subject}' 처리 실패: {str(e)}")
                    # 오류 발생 시 기본적으로 포함
                    work_related_emails.append(email)
                    logging.warning(f"⚠️ 오류로 인해 메일을 업무 관련으로 간주: {email.subject}")
            
            logging.info(f"🔍 LLM 기반 업무 관련 메일 {len(work_related_emails)}개 필터링 완료")
            
        except Exception as e:
            logging.error(f"❌ LLM 기반 업무용 메일 필터링 실패: {str(e)}")
            import traceback
            logging.error(f"❌ 오류 상세: {traceback.format_exc()}")
            # 필터링 실패 시 모든 메일을 업무 관련으로 간주
            work_related_emails = unread_emails
            logging.warning("⚠️ LLM 필터링 실패로 모든 메일을 업무 관련으로 간주")
        
        # 3단계: 유사 메일 검색 및 레이블 생성
        logging.info("🔍 3단계: 유사 메일 검색 및 레이블 생성 시작...")
        try:
            from vector_db_models import VectorDBManager
            from database_models import DatabaseManager
            
            vector_db = VectorDBManager()
            db_manager = DatabaseManager()
            
            # 각 업무 관련 메일에 대해 유사 메일 검색
            for email in work_related_emails:
                try:
                    # 메일 내용을 Vector DB에 저장 (아직 저장되지 않은 경우)
                    email_content = f"제목: {email.subject}\n발신자: {email.sender}\n내용: {email.body}"
                    
                    # 유사 메일 검색 - n_results 파라미터 사용
                    similar_mails = vector_db.search_similar_mails(email_content, n_results=5)
                    logging.info(f"🔍 메일 '{email.subject}' 유사 메일 {len(similar_mails)}개 발견")
                    
                    # user_action 테이블에서 유사한 패턴의 레이블 조회
                    similar_labels = []
                    if similar_mails:
                        for similar_mail in similar_mails:
                            # 유사 메일과 관련된 user_action에서 레이블 정보 추출
                            mail_id = similar_mail.message_id if hasattr(similar_mail, 'message_id') else None
                            if mail_id:
                                # 해당 메일과 관련된 티켓의 user_action 조회
                                user_actions = db_manager.get_user_actions_by_message_id(mail_id)
                                for action in user_actions:
                                    if action.action_type == 'label_added':
                                        similar_labels.append(action.new_value)
                                        logging.info(f"🔍 유사 메일에서 레이블 발견: {action.new_value}")
                    
                    # 중복 제거
                    similar_labels = list(set(similar_labels))
                    logging.info(f"🔍 메일 '{email.subject}' 유사 레이블: {similar_labels}")
                    
                    # email 객체에 레이블 정보를 딕셔너리로 저장 (EmailMessage 객체 수정 불가)
                    if not hasattr(email, '_suggested_labels'):
                        email._suggested_labels = similar_labels
                    else:
                        email._suggested_labels = similar_labels
                    
                except Exception as e:
                    logging.error(f"⚠️ 메일 '{email.subject}' 유사 메일 검색 실패: {str(e)}")
                    # 오류 발생 시 빈 레이블 설정
                    if not hasattr(email, '_suggested_labels'):
                        email._suggested_labels = []
                    else:
                        email._suggested_labels = []
                    continue
            
            logging.info(f"🔍 유사 메일 검색 및 레이블 생성 완료")
            
        except Exception as e:
            logging.error(f"❌ 유사 메일 검색 및 레이블 생성 실패: {str(e)}")
            import traceback
            logging.error(f"❌ 오류 상세: {traceback.format_exc()}")
            # 오류 발생 시 기본 레이블 설정
            for email in work_related_emails:
                if not hasattr(email, '_suggested_labels'):
                    email._suggested_labels = []
                else:
                    email._suggested_labels = []
        
        # 4단계: 새로운 티켓 생성 (업무 관련 메일만)
        logging.info("🔍 4단계: 새로운 티켓 생성 시작...")
        logging.info(f"🔍 처리할 업무 관련 메일 수: {len(work_related_emails)}")
        new_tickets_created = 0
        
        try:
            from sqlite_ticket_models import SQLiteTicketManager
            from datetime import datetime, timedelta
            
            ticket_manager = SQLiteTicketManager()
            
            # 이미 티켓이 생성된 메일 ID 목록 조회
            existing_message_ids = set()
            existing_tickets = ticket_manager.get_all_tickets()
            for ticket in existing_tickets:
                if ticket.original_message_id:
                    existing_message_ids.add(ticket.original_message_id)
            
            logging.info(f"🔍 기존 티켓의 메일 ID {len(existing_message_ids)}개 발견")
            
            # 새로운 티켓 생성
            for email in work_related_emails:
                if email.id not in existing_message_ids:
                    try:
                        # 티켓 생성 - insert_ticket 메서드 사용
                        from sqlite_ticket_models import Ticket
                        
                        # LLM이 제안한 레이블과 우선순위 사용
                        llm_analysis = getattr(email, '_llm_analysis', {})
                        suggested_labels = llm_analysis.get('suggested_labels', []) or []
                        suggested_priority = llm_analysis.get('priority', 'Medium')
                        suggested_ticket_type = llm_analysis.get('ticket_type', 'email')
                        
                        # Ticket 객체 생성 (모든 필수 인자 포함)
                        current_time = datetime.now().isoformat()
                        new_ticket = Ticket(
                            ticket_id=None,  # 자동 생성
                            original_message_id=email.id,
                            status='pending',
                            title=email.subject or '제목 없음',
                            description=email.body or '내용 없음',
                            priority=suggested_priority,  # LLM이 제안한 우선순위 사용
                            ticket_type=suggested_ticket_type,  # LLM이 제안한 티켓 타입 사용
                            reporter=email.sender or '발신자 없음',
                            reporter_email=email.sender or '발신자 없음',
                            labels=suggested_labels,  # LLM이 제안한 레이블 사용
                            created_at=current_time,
                            updated_at=current_time
                        )
                        
                        logging.info(f"🔍 새로운 티켓 객체 생성: {new_ticket}")
                        logging.info(f"🔍 LLM 제안 레이블: {suggested_labels}")
                        logging.info(f"🔍 LLM 제안 우선순위: {suggested_priority}")
                        logging.info(f"🔍 LLM 제안 티켓 타입: {suggested_ticket_type}")
                        
                        # insert_ticket 메서드로 티켓 생성
                        new_ticket_id = ticket_manager.insert_ticket(new_ticket)
                        if new_ticket_id:
                            new_tickets_created += 1
                            logging.info(f"🔍 새로운 티켓 생성 완료: ID={new_ticket_id}")
                        else:
                            logging.warning(f"⚠️ 티켓 생성 실패: {email.id}")
                    except Exception as e:
                        logging.error(f"❌ 티켓 생성 중 오류: {str(e)}")
                        continue
            
            logging.info(f"🔍 새로운 티켓 {new_tickets_created}개 생성 완료")
            
        except Exception as e:
            logging.error(f"❌ 새로운 티켓 생성 실패: {str(e)}")
        
        # 5단계: 기존 티켓과 새로운 티켓 합치기
        logging.info("🔍 5단계: 기존 티켓과 새로운 티켓 합치기 시작...")
        
        try:
            # 오늘 날짜 계산
            today = datetime.now().date()
            
            # 오늘 생성된 모든 티켓 조회 (새로 생성된 것 포함)
            all_tickets = ticket_manager.get_all_tickets()
            today_tickets = []
            
            for ticket in all_tickets:
                try:
                    ticket_date = datetime.fromisoformat(ticket.created_at.replace('Z', '+00:00')).date()
                    if ticket_date == today:
                        today_tickets.append(ticket)
                except:
                    # 날짜 파싱 실패 시 포함
                    today_tickets.append(ticket)
            
            logging.info(f"🔍 오늘 생성된 총 티켓 {len(today_tickets)}개 발견")
            
            # 티켓 데이터를 UI 표시용으로 변환
            tickets = []
            for ticket in today_tickets:
                ticket_data = {
                    'id': ticket.ticket_id,  # UI에서 사용하는 키
                    'ticket_id': ticket.ticket_id,
                    'title': ticket.title,
                    'description': ticket.description or '',
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'type': ticket.ticket_type,
                    'reporter': ticket.reporter,
                    'labels': ticket.labels or [],  # RDB에서 직접 가져온 최신 레이블
                    'created_at': ticket.created_at,
                    'updated_at': ticket.updated_at,
                    'original_message_id': ticket.original_message_id
                }
                tickets.append(ticket_data)
            
            # 결과 반환
            result = {
                'display_mode': 'tickets',
                'tickets': tickets,
                'new_tickets_created': new_tickets_created,
                'existing_tickets_found': len(tickets) - new_tickets_created,
                'summary': { 'total_tasks': len(tickets) },
                'message': f'업무 관련 메일 {len(work_related_emails)}개 중 새로운 티켓 {new_tickets_created}개 생성, 총 {len(tickets)}개 티켓 제공'
            }
            
            logging.info(f"🔍 티켓 생성 및 통합 완료: 새로운 {new_tickets_created}개, 기존 {len(tickets) - new_tickets_created}개, 총 {len(tickets)}개")
            return result
            
        except Exception as e:
            logging.error(f"RDB 티켓 조회 실패: {str(e)}")
            # RDB 조회 실패 시 빈 결과 반환
            logging.info("RDB 조회 실패로 빈 결과 반환")
            return {
                'display_mode': 'no_emails',
                'message': '티켓 조회 중 오류가 발생했습니다.',
                'tickets': [],
                'non_work_emails': [],
                'new_tickets_created': 0,
                'existing_tickets_found': 0,
                'summary': { 'total_tasks': 0 }
            }
        
    except Exception as e:
        import logging
        logging.error(f"process_emails_with_ticket_logic 오류: {str(e)}")
        import traceback
        logging.error(f"오류 상세: {traceback.format_exc()}")
        return {
            'display_mode': 'error',
            'message': f'티켓 처리 중 오류가 발생했습니다: {str(e)}',
            'error': str(e),
            'tickets': [],
            'non_work_emails': []
        }

def test_work_related_filtering() -> Dict[str, Any]:
    """테스트용 업무 관련 메일 필터링 - 간단한 버전"""
    try:
        logging.info("🧪 테스트용 업무 관련 메일 필터링 시작...")
        
        # 테스트용 메일 데이터
        test_emails = [
            {"subject": "서버 접속 불가 및 기능 제안", "body": "NCMS 서버에 접속이 안 됩니다."},
            {"subject": "PRD NCMSAPI-BATCH 서버 다운 문의", "body": "배치 서버가 다운되었습니다."},
            {"subject": "광고 메일입니다", "body": "할인 상품을 확인해보세요."},
            {"subject": "개인 메시지", "body": "안녕하세요, 개인적인 내용입니다."},
            {"subject": "API 오류 확인 요청", "body": "EUXP API에서 오류가 발생했습니다."}
        ]
        
        # 업무 관련 키워드
        work_related_keywords = [
            '서버', '오류', '문의', '공지', 'API', '배치', 'NCMS', 'EUXP',
            '접속', '다운', '이상', '확인', '요청', '건', '개발', '테스트',
            'PRD', 'STG', 'PrePRD', '서버', '시스템', '기능', '제안'
        ]
        
        logging.info(f"🧪 테스트용 메일 {len(test_emails)}개")
        logging.info(f"🧪 업무 관련 키워드: {work_related_keywords}")
        
        # 필터링 테스트
        work_related_count = 0
        for i, email in enumerate(test_emails):
            email_text = f"{email['subject']} {email['body']}".lower()
            matched_keywords = [kw for kw in work_related_keywords if kw.lower() in email_text]
            is_work_related = len(matched_keywords) > 0
            
            logging.info(f"🧪 메일 {i+1}: '{email['subject']}' -> 업무 관련: {is_work_related} (키워드: {matched_keywords})")
            
            if is_work_related:
                work_related_count += 1
        
        logging.info(f"🧪 필터링 결과: 총 {len(test_emails)}개 중 업무 관련 {work_related_count}개")
        
        return {
            'success': True,
            'total_emails': len(test_emails),
            'work_related_count': work_related_count,
            'message': f'필터링 테스트 완료: 총 {len(test_emails)}개 중 업무 관련 {work_related_count}개'
        }
        
    except Exception as e:
        logging.error(f"🧪 테스트용 업무 관련 메일 필터링 오류: {str(e)}")
        import traceback
        logging.error(f"🧪 오류 상세: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

def test_email_fetch_logic(provider_name: str) -> Dict[str, Any]:
    """테스트용 메일 조회 로직 - 간단한 버전"""
    try:
        logging.info(f"🧪 테스트용 메일 조회 로직 시작: provider={provider_name}")
        
        # UnifiedEmailService 생성
        service = UnifiedEmailService(provider_name)
        logging.info(f"🧪 서비스 생성 완료: {service}")
        
        # 안 읽은 메일 필터
        unread_filters = {
            'is_read': False,
            'limit': 10
        }
        logging.info(f"🧪 안 읽은 메일 필터: {unread_filters}")
        
        # 메일 조회
        unread_emails = service.fetch_emails(unread_filters)
        logging.info(f"🧪 안 읽은 메일 {len(unread_emails)}개 발견")
        
        # 첫 번째 메일 정보
        if unread_emails:
            first_email = unread_emails[0]
            logging.info(f"🧪 첫 번째 메일: id={first_email.id}, subject={first_email.subject}, sender={first_email.sender}")
            
            return {
                'success': True,
                'email_count': len(unread_emails),
                'first_email': {
                    'id': first_email.id,
                    'subject': first_email.subject,
                    'sender': first_email.sender
                },
                'message': f'안 읽은 메일 {len(unread_emails)}개 조회 성공'
            }
        else:
            return {
                'success': True,
                'email_count': 0,
                'message': '안 읽은 메일이 없습니다'
            }
            
    except Exception as e:
        logging.error(f"🧪 테스트용 메일 조회 로직 오류: {str(e)}")
        import traceback
        logging.error(f"🧪 오류 상세: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

def test_ticket_creation_logic(provider_name: str) -> Dict[str, Any]:
    """테스트용 티켓 생성 로직 - 간단한 버전"""
    try:
        logging.info(f"🧪 테스트용 티켓 생성 로직 시작: provider={provider_name}")
        
        # 간단한 테스트 티켓 생성
        from sqlite_ticket_models import SQLiteTicketManager
        from datetime import datetime
        
        ticket_manager = SQLiteTicketManager()
        
        # 테스트 티켓 데이터
        test_ticket_data = {
            'title': f'테스트 티켓 - {datetime.now().strftime("%H:%M:%S")}',
            'description': '테스트용 티켓입니다.',
            'status': 'pending',
            'priority': 'Medium',
            'ticket_type': 'test',
            'reporter': '테스트 사용자',
            'original_message_id': f'test_{datetime.now().timestamp()}',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        logging.info(f"🧪 테스트 티켓 데이터: {test_ticket_data}")
        
        # 티켓 생성 - insert_ticket 메서드 사용
        from sqlite_ticket_models import Ticket
        
        # Ticket 객체 생성
        test_ticket = Ticket(
            ticket_id=None,  # 자동 생성
            original_message_id=test_ticket_data['original_message_id'],
            status=test_ticket_data['status'],
            title=test_ticket_data['title'],
            description=test_ticket_data['description'],
            priority=test_ticket_data['priority'],
            ticket_type=test_ticket_data['ticket_type'],
            reporter=test_ticket_data['reporter'],
            reporter_email='test@example.com',
            labels=[],
            created_at=test_ticket_data['created_at'],
            updated_at=test_ticket_data['updated_at']
        )
        
        logging.info(f"🧪 Ticket 객체 생성: {test_ticket}")
        
        # insert_ticket 메서드로 티켓 생성
        new_ticket_id = ticket_manager.insert_ticket(test_ticket)
        if new_ticket_id:
            logging.info(f"🧪 테스트 티켓 생성 성공: ID={new_ticket_id}")
            return {
                'success': True,
                'ticket_id': new_ticket_id,
                'message': '테스트 티켓 생성 성공'
            }
        else:
            logging.error("🧪 테스트 티켓 생성 실패")
            return {
                'success': False,
                'message': '테스트 티켓 생성 실패'
            }
            
    except Exception as e:
        logging.error(f"🧪 테스트 티켓 생성 로직 오류: {str(e)}")
        import traceback
        logging.error(f"🧪 오류 상세: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
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