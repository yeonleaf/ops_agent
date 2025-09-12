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
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 환경 변수 로드
load_dotenv()

# Streamlit은 UI 피드백용으로만 제한적으로 사용
import streamlit as st

from email_provider import create_provider, get_available_providers, get_default_provider
from email_models import EmailMessage, EmailSearchResult, EmailPriority
from memory_based_ticket_processor import MemoryBasedTicketProcessorTool
from mem0_memory_adapter import create_mem0_memory, add_ticket_event, search_related_memories

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
    
    def __init__(self, provider_name: str = None, access_token: str = None):
        """초기화 - OAuth2 액세스 토큰 필수"""
        self.provider_name = provider_name or get_default_provider()
        self.access_token = access_token
        
        if not access_token:
            print("⚠️ OAuth2 인증이 필요합니다. 액세스 토큰을 제공하거나 OAuth 서버를 사용하세요.")
            print("💡 OAuth 서버 사용: http://localhost:8000/auth/login/gmail")
        
        self.provider = create_provider(self.provider_name, access_token=access_token)
        
        # OAuth2 액세스 토큰이 있으면 인증 시도
        if access_token:
            print(f"🔐 UnifiedEmailService에서 Gmail 인증 시도: {access_token[:20]}...")
            if not self.provider.authenticate():
                print("❌ Gmail 인증 실패")
            else:
                print("✅ Gmail 인증 성공")
        
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
        
        # 기본 쿼리 (최신 메일부터) - Gmail API에서는 빈 쿼리 사용
        # is:any는 Gmail API에서 유효하지 않으므로 빈 문자열 사용
        
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
            
            # 이미 인증된 Gmail API 클라이언트 사용
            gmail_client = self.provider
            
            if not gmail_client.is_authenticated:
                logging.error("Gmail API 인증 실패")
                return []
            
            # LLM의 limit 값을 Gmail API maxResults에 반영
            max_results = filters.get('limit', 100)  # 기본값 100, LLM limit 값 우선
            logging.info(f"Gmail API maxResults 설정: {max_results}")
            
            # Gmail API에서 필터링된 메일 가져오기
            search_result = gmail_client.search_emails(gmail_query, max_results=max_results)
            gmail_emails = search_result.messages
            
            if not gmail_emails:
                logging.info("조건에 맞는 메일이 없습니다.")
                return []
            
            logging.info(f"Gmail API에서 {len(gmail_emails)}개 메일 가져옴")
            
            # Gmail 데이터를 EmailMessage 형식으로 변환
            email_messages = []
            
            for gmail_data in gmail_emails:
                try:
                    # 메일 본문에서 HTML 태그 제거 (간단한 정리)
                    # EmailMessage 객체를 딕셔너리로 변환
                    email_dict = gmail_data.model_dump() if hasattr(gmail_data, 'model_dump') else gmail_data
                    body = email_dict.get('body', '')
                    if body:
                        # HTML 태그 제거 (간단한 방법)
                        import re
                        body = re.sub(r'<[^>]+>', '', body)
                        body = re.sub(r'\s+', ' ', body).strip()
                    
                    # Gmail API 데이터 상태 로깅
                    gmail_unread = email_dict.get('unread', False)
                    calculated_is_read = not gmail_unread
                    logging.info(f"메일 {email_dict.get('id', 'N/A')}: Gmail unread={gmail_unread}, 계산된 is_read={calculated_is_read}")
                    
                    # EmailMessage 생성
                    email_msg = EmailMessage(
                        id=email_dict.get('id', 'unknown'),  # Gmail의 실제 message_id
                        subject=email_dict.get('subject', '제목 없음'),
                        sender=email_dict.get('from', '발신자 없음'),
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
                    logging.error(f"메일 변환 오류 (ID: {email_dict.get('id', 'N/A')}): {str(e)}")
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
                    # EmailMessage 객체를 딕셔너리로 변환
                    email_dict = gmail_data.model_dump() if hasattr(gmail_data, 'model_dump') else gmail_data
                    body = email_dict.get('body', '')
                    if body:
                        # HTML 태그 제거 (간단한 방법)
                        import re
                        body = re.sub(r'<[^>]+>', '', body)
                        body = re.sub(r'\s+', ' ', body).strip()
                    
                    # Gmail API 데이터 상태 로깅
                    gmail_unread = email_dict.get('unread', False)
                    calculated_is_read = not gmail_unread
                    logging.info(f"메일 {email_dict.get('id', 'N/A')}: Gmail unread={gmail_unread}, 계산된 is_read={calculated_is_read}")
                    
                    # EmailMessage 생성
                    email_msg = EmailMessage(
                        id=email_dict.get('id', 'unknown'),  # Gmail의 실제 message_id
                        subject=email_dict.get('subject', '제목 없음'),
                        sender=email_dict.get('from', '발신자 없음'),
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

def clear_email_cache():
    """이메일 캐시를 초기화합니다."""
    if hasattr(process_emails_with_ticket_logic, '_cache'):
        process_emails_with_ticket_logic._cache.clear()

def process_single_email_with_llm(email, processor, context_info, previous_ticket_statuses):
    """단일 이메일을 LLM으로 처리하는 헬퍼 함수 (병렬 처리용)"""
    try:
        # 메일 내용을 LLM이 분석할 수 있는 형태로 구성
        email_content = f"제목: {email.subject}\n발신자: {email.sender}\n내용: {email.body}"
        
        # 발신자별 이전 상태 정보 추가
        email_context = context_info
        if previous_ticket_statuses and email.id in previous_ticket_statuses.get("sender_status_stats", {}):
            previous_status = previous_ticket_statuses["sender_status_stats"][email.id]
            email_context += f"\n[이 발신자의 이전 티켓 상태: {previous_status}]\n"
            if previous_status == "rejected":
                email_context += "⚠️ 이 발신자의 이전 메일이 거부되었습니다. 비슷한 내용이라면 티켓 생성에 주의하세요.\n"
            elif previous_status == "approved":
                email_context += "✅ 이 발신자의 이전 메일이 승인되었습니다. 비슷한 내용이라면 티켓 생성이 적절할 수 있습니다.\n"
        
        # 컨텍스트 정보를 포함한 이메일 내용
        enhanced_email_content = email_content + email_context
        
        # LLM을 사용하여 업무 관련성 판단
        llm_response = processor._run(
            email_content=enhanced_email_content,
            email_subject=email.subject,
            email_sender=email.sender,
            message_id=email.id
        )
        
        # LLM 응답을 JSON으로 파싱
        import json
        llm_data = json.loads(llm_response)
        
        if llm_data.get('success'):
            # reasoning 단계에서 티켓 생성 여부 판단
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
            
            # email 객체에 LLM 분석 결과 저장
            email._llm_analysis = {
                'is_work_related': is_work_related,
                'reason': reason,
                'confidence': confidence,
                'priority': priority,
                'suggested_labels': labels,
                'ticket_type': ticket_type
            }
            
            return email, is_work_related, None
            
        else:
            # LLM 실행 실패 - 기본적으로 업무 관련으로 처리
            email._llm_analysis = {
                'is_work_related': True,
                'reason': 'LLM 실행 실패로 인한 기본값',
                'confidence': 0.3,
                'priority': 'Medium',
                'suggested_labels': ['error-fallback'],
                'ticket_type': 'Task'
            }
            return email, True, "LLM 실행 실패"
            
    except json.JSONDecodeError as json_error:
        # 파싱 실패 시 기본적으로 포함
        email._llm_analysis = {
            'is_work_related': True,
            'reason': 'JSON 파싱 실패로 인한 기본값',
            'confidence': 0.3,
            'priority': 'Medium',
            'suggested_labels': ['parse-error'],
            'ticket_type': 'Task'
        }
        return email, True, f"JSON 파싱 실패: {str(json_error)}"
        
    except Exception as e:
        # 기타 오류 발생 시 기본적으로 포함
        email._llm_analysis = {
            'is_work_related': True,
            'reason': '처리 오류로 인한 기본값',
            'confidence': 0.3,
            'priority': 'Medium',
            'suggested_labels': ['process-error'],
            'ticket_type': 'Task'
        }
        return email, True, f"처리 오류: {str(e)}"
        logging.info("🗑️ 이메일 캐시 초기화 완료")

def get_previous_ticket_statuses(mem0_memory=None):
    """mem0에서 이전 티켓 상태 정보를 조회합니다."""
    try:
        if mem0_memory is None:
            # 전역에서 mem0_memory 가져오기 시도
            try:
                import sys
                if hasattr(sys.modules['__main__'], 'mem0_memory'):
                    mem0_memory = sys.modules['__main__'].mem0_memory
            except:
                pass
            
            # 여전히 None이면 새로 생성
            if mem0_memory is None:
                from mem0_memory_adapter import create_mem0_memory
                mem0_memory = create_mem0_memory("ticket_processor")
        
        # mem0에서 상태 변경 이벤트 조회
        status_events = mem0_memory.search(
            query="티켓 상태 변경",
            limit=50
        )
        
        # 상태별 통계 생성
        status_stats = {
            "approved": 0,
            "rejected": 0,
            "pending": 0,
            "total": 0
        }
        
        # 발신자별 상태 통계
        sender_status_stats = {}
        
        # mem0 결과 형식에 따라 처리
        if isinstance(status_events, list):
            events_list = status_events
        elif isinstance(status_events, dict) and 'results' in status_events:
            events_list = status_events['results']
        else:
            events_list = []
        
        for event in events_list:
            # DummyMemory와 실제 mem0 모두 지원
            if isinstance(event, dict):
                metadata = event.get('metadata', {})
                if metadata.get('event_type') == 'status_change':
                    new_value = metadata.get('new_value', '')
                    message_id = metadata.get('message_id', '')
                    
                    if new_value in status_stats:
                        status_stats[new_value] += 1
                        status_stats["total"] += 1
                        
                        # 발신자별 통계 (메일 ID로 발신자 추적)
                        if message_id:
                            sender_status_stats[message_id] = new_value
        
        logging.info(f"🔍 이전 티켓 상태 통계: {status_stats}")
        logging.info(f"🔍 발신자별 상태: {sender_status_stats}")
        
        return {
            "status_stats": status_stats,
            "sender_status_stats": sender_status_stats
        }
        
    except Exception as e:
        logging.error(f"❌ 이전 티켓 상태 조회 실패: {str(e)}")
        return {
            "status_stats": {"approved": 0, "rejected": 0, "pending": 0, "total": 0},
            "sender_status_stats": {}
        }

def process_emails_with_ticket_logic(provider_name: str, user_query: str = None, mem0_memory=None, access_token: str = None) -> Dict[str, Any]:
    """안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다."""
    try:
        import logging
        logging.info(f"🔍 process_emails_with_ticket_logic 시작: provider={provider_name}, query={user_query}")
        
        # mem0_memory가 None이면 전역에서 가져오기 시도
        if mem0_memory is None:
            try:
                import sys
                if hasattr(sys.modules['__main__'], 'mem0_memory'):
                    mem0_memory = sys.modules['__main__'].mem0_memory
            except:
                pass
        
        # Gmail API 중복 호출 방지를 위한 캐시 확인
        cache_key = f"unread_emails_{provider_name}"
        if hasattr(process_emails_with_ticket_logic, '_cache') and cache_key in process_emails_with_ticket_logic._cache:
            cached_data = process_emails_with_ticket_logic._cache[cache_key]
            if cached_data and len(cached_data) > 0:
                logging.info(f"📦 캐시된 이메일 데이터 사용: {len(cached_data)}개")
                unread_emails = cached_data
            else:
                unread_emails = None
        else:
            unread_emails = None
        
        # 캐시에 데이터가 없거나 비어있는 경우에만 Gmail API 호출
        if unread_emails is None:
            # 1단계: 안 읽은 메일 가져오기
            logging.info("🔍 1단계: 안 읽은 메일 가져오기 시작...")
            try:
                logging.info(f"🔍 UnifiedEmailService({provider_name}) 생성 시도...")
                service = UnifiedEmailService(provider_name, access_token=access_token)
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
                
                # 캐시에 저장
                if not hasattr(process_emails_with_ticket_logic, '_cache'):
                    process_emails_with_ticket_logic._cache = {}
                process_emails_with_ticket_logic._cache[cache_key] = unread_emails
                logging.info(f"💾 이메일 데이터 캐시에 저장: {len(unread_emails)}개")
                
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
        
        # 2단계: 최적화된 LLM 기반 업무용 메일 필터링
        logging.info("🔍 2단계: 최적화된 LLM 기반 업무용 메일 필터링 시작...")
        try:
            # Memory-Based Ticket Processor를 사용하여 LLM이 업무 관련성 판단
            from memory_based_ticket_processor import create_memory_based_ticket_processor
            
            processor = create_memory_based_ticket_processor()
            logging.info(f"🔍 Memory-Based Ticket Processor 생성 완료")
        except Exception as e:
            logging.error(f"❌ Memory-Based Ticket Processor 생성 실패: {e}")
            processor = None
        
        # mem0에서 이전 티켓 상태 정보 조회 (한 번만)
        previous_ticket_statuses = get_previous_ticket_statuses(mem0_memory)
        logging.info(f"🔍 이전 티켓 상태 정보 조회 완료")
        
        # 컨텍스트 정보 미리 구성 (한 번만)
        context_info = ""
        if previous_ticket_statuses:
            status_stats = previous_ticket_statuses.get("status_stats", {})
            sender_stats = previous_ticket_statuses.get("sender_status_stats", {})
            
            # 전체 상태 통계
            if status_stats.get("total", 0) > 0:
                context_info += f"\n\n[이전 티켓 상태 통계]\n"
                context_info += f"- 승인된 티켓: {status_stats.get('approved', 0)}개\n"
                context_info += f"- 거부된 티켓: {status_stats.get('rejected', 0)}개\n"
                context_info += f"- 대기 중인 티켓: {status_stats.get('pending', 0)}개\n"
                context_info += f"- 총 티켓: {status_stats.get('total', 0)}개\n"
            
            # 1단계: 빠른 키워드 기반 사전 필터링
            logging.info("🔍 2a. 빠른 키워드 기반 사전 필터링 시작...")
            work_related_emails = []
            non_work_emails = []
            
            # 업무 관련 키워드 패턴 (빠른 필터링용)
            work_keywords = [
                'bug', 'error', 'issue', 'problem', 'fix', 'urgent', 'important',
                'meeting', 'schedule', 'deadline', 'project', 'task', 'request',
                'approve', 'review', 'feedback', 'action', 'required', 'help',
                'support', 'service', 'system', 'server', 'database', 'api',
                '버그', '오류', '문제', '수정', '긴급', '중요', '회의', '일정',
                '마감', '프로젝트', '작업', '요청', '승인', '검토', '피드백',
                '액션', '필요', '도움', '지원', '서비스', '시스템', '서버', '데이터베이스'
            ]
            
            # 개인/마케팅 관련 키워드 패턴
            personal_keywords = [
                'newsletter', 'marketing', 'promotion', 'sale', 'discount',
                'personal', 'private', 'spam', 'unsubscribe', 'advertisement',
                '뉴스레터', '마케팅', '프로모션', '세일', '할인', '개인', '사적',
                '스팸', '구독취소', '광고', '지옥', '고백', 'MZ', '숏폼'
            ]
            
            for email in unread_emails:
                # 빠른 키워드 기반 사전 필터링
                full_text = f"{email.subject} {email.body}".lower()
                
                work_score = sum(1 for keyword in work_keywords if keyword.lower() in full_text)
                personal_score = sum(1 for keyword in personal_keywords if keyword.lower() in full_text)
                
                # 명확한 개인/마케팅 메일은 LLM 호출 없이 제외
                if personal_score > work_score and personal_score >= 2:
                    email._llm_analysis = {
                        'is_work_related': False,
                        'reason': f"키워드 사전 필터링: 개인/마케팅 키워드 {personal_score}개 발견",
                        'confidence': 0.8,
                        'priority': 'Low',
                        'suggested_labels': ['키워드-사전필터', '개인-관련'],
                        'ticket_type': 'Task'
                    }
                    non_work_emails.append(email)
                else:
                    # LLM 분석이 필요한 메일들
                    work_related_emails.append(email)
            
            logging.info(f"🔍 사전 필터링 완료: 업무용 {len(work_related_emails)}개, 개인용 {len(non_work_emails)}개")
            
            # 2단계: 병렬 LLM 기반 정밀 분석 (필요한 메일만)
            if work_related_emails:
                logging.info(f"🔍 2b. 병렬 LLM 기반 정밀 분석 시작: {len(work_related_emails)}개 메일")
                
                try:
                    # 병렬 처리로 성능 최적화
                    max_workers = min(3, len(work_related_emails))  # 최대 3개 스레드
                    final_work_emails = []
                    
                    start_time = time.time()
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # 모든 이메일에 대해 병렬 처리 작업 제출
                        future_to_email = {
                            executor.submit(process_single_email_with_llm, email, processor, context_info, previous_ticket_statuses): email 
                            for email in work_related_emails
                        }
                        
                        # 완료된 작업들 처리
                        completed_count = 0
                        for future in as_completed(future_to_email):
                            try:
                                email, is_work_related, error = future.result()
                                
                                if error:
                                    logging.warning(f"⚠️ {email.subject[:50]}... 처리 중 오류: {error}")
                                
                                if is_work_related:
                                    final_work_emails.append(email)
                                    logging.info(f"✅ LLM 업무 관련 판단: {email.subject[:50]}...")
                                else:
                                    non_work_emails.append(email)
                                    logging.info(f"❌ LLM 개인 관련 판단: {email.subject[:50]}...")
                                
                                completed_count += 1
                                if completed_count % 5 == 0:  # 5개마다 진행상황 로깅
                                    elapsed = time.time() - start_time
                                    logging.info(f"🔍 진행상황: {completed_count}/{len(work_related_emails)}개 완료 (경과시간: {elapsed:.1f}초)")
                                    
                            except Exception as e:
                                email = future_to_email[future]
                                logging.error(f"⚠️ {email.subject[:50]}... 병렬 처리 실패: {str(e)}")
                                # 실패한 경우 기본적으로 업무 관련으로 처리
                                email._llm_analysis = {
                                    'is_work_related': True,
                                    'reason': '병렬 처리 실패로 인한 기본값',
                                    'confidence': 0.3,
                                    'priority': 'Medium',
                                    'suggested_labels': ['parallel-error'],
                                    'ticket_type': 'Task'
                                }
                                final_work_emails.append(email)
                    
                    elapsed_time = time.time() - start_time
                    logging.info(f"🔍 병렬 LLM 분석 완료: 업무용 {len(final_work_emails)}개, 개인용 {len(non_work_emails)}개 (소요시간: {elapsed_time:.1f}초)")
                    
                    # 최종 결과 업데이트
                    work_related_emails = final_work_emails
                    
                except Exception as e:
                    logging.error(f"❌ LLM 기반 업무용 메일 필터링 실패: {str(e)}")
                    import traceback
                    logging.error(f"❌ 오류 상세: {traceback.format_exc()}")
                    # 필터링 실패 시 모든 메일을 업무 관련으로 간주
                    work_related_emails = unread_emails
                    non_work_emails = []
                    logging.warning("⚠️ LLM 필터링 실패로 모든 메일을 업무 관련으로 간주")
        
        # 3단계: mem0 기반 관련 기억 검색 및 LLM 기반 레이블 추천 (단순화됨)
        logging.info("🔍 3단계: mem0 기반 관련 기억 검색 및 LLM 기반 레이블 추천 시작...")
        try:
            # mem0 메모리 인스턴스 생성 (매개변수로 받은 것이 없으면 새로 생성)
            if mem0_memory is None:
                mem0_memory = create_mem0_memory("ai_system")
            
            # 각 업무 관련 메일에 대해 mem0 기반 관련 기억 검색 및 LLM 레이블 추천
            for email in work_related_emails:
                try:
                    # 메일 내용 구성
                    email_content = f"제목: {email.subject}\n발신자: {email.sender}\n내용: {email.body}"
                    
                    # mem0에서 관련 기억 검색 (기존의 복잡한 Vector DB + RDB 조회를 단 한 줄로 교체)
                    related_memories = search_related_memories(
                        memory=mem0_memory,
                        email_content=email_content,
                        limit=5
                    )
                    
                    logging.info(f"🔍 메일 '{email.subject}' 관련 기억 {len(related_memories)}개 발견")
                    
                    # 관련 기억에서 액션 정보 추출
                    similar_user_actions = []
                    action_summary = {}  # 액션 타입별 개수 집계
                    
                    for memory in related_memories:
                        metadata = memory.get('metadata', {})
                        action_type = metadata.get('action_type', 'unknown')
                        
                        if action_type in ['label_updated', 'user_correction', 'ai_decision']:
                            similar_user_actions.append({
                                'action_type': action_type,
                                'old_value': metadata.get('old_value', ''),
                                'new_value': metadata.get('new_value', ''),
                                'created_at': metadata.get('timestamp', ''),
                                'user_id': metadata.get('user_id', 'unknown')
                            })
                            
                            # 액션 타입별 개수 집계
                            action_key = f"{action_type}"
                            if action_type in ['label_updated', 'user_correction']:
                                old_val = metadata.get('old_value', '')
                                new_val = metadata.get('new_value', '')
                                if old_val and new_val:
                                    action_key += f":{old_val}→{new_val}"
                            
                            action_summary[action_key] = action_summary.get(action_key, 0) + 1
                    
                    # 액션 요약 로깅
                    if action_summary:
                        logging.info(f"🔍 메일 '{email.subject}' mem0 관련 기억 요약:")
                        for action_key, count in sorted(action_summary.items()):
                            if count > 1:
                                logging.info(f"   - {action_key}: {count}회")
                            else:
                                logging.info(f"   - {action_key}: 1회")
                    
                    logging.info(f"🔍 메일 '{email.subject}' mem0 관련 기억 총 {len(similar_user_actions)}개 수집")
                    
                    # LLM에게 user_action 정보와 함께 레이블 추천 요청
                    try:
                        # LLM 프롬프트에 user_action 정보 포함
                        if similar_user_actions:
                            # user_action이 있는 경우 - 강력한 새로운 프롬프트
                            
                            # 액션 타입별로 그룹화하여 표시
                            label_actions = []
                            status_actions = []
                            other_actions = []
                            
                            for action in similar_user_actions[:15]:  # 최대 15개
                                if action['action_type'] in ['label_added', 'label_deleted']:
                                    if action['action_type'] == 'label_added':
                                        label_actions.append(f"'{action['new_value']}' 추가")
                                    else:
                                        label_actions.append(f"'{action['old_value']}' 삭제")
                                elif action['action_type'] == 'status_change':
                                    status_actions.append(f"{action['old_value']} → {action['new_value']}")
                                else:
                                    other_actions.append(f"{action['action_type']}: {action['new_value'] or action['old_value'] or '값 없음'}")
                            
                            # 액션 요약 생성
                            action_summary = ""
                            if label_actions:
                                action_summary += "\n레이블 관련 행동:\n"
                                for i, action in enumerate(set(label_actions), 1):  # 중복 제거
                                    action_summary += f"  {i}. {action}\n"
                            
                            if status_actions:
                                action_summary += f"\n상태 변경 행동:\n"
                                for i, action in enumerate(set(status_actions), 1):  # 중복 제거
                                    action_summary += f"  {i}. {action}\n"
                            
                            if other_actions:
                                action_summary += f"\n기타 행동:\n"
                                for i, action in enumerate(set(other_actions), 1):  # 중복 제거
                                    action_summary += f"  {i}. {action}\n"
                            
                            llm_prompt = f"""당신은 mem0에서 검색된 '관련 기억'을 분석하여, 새로운 이메일에 가장 적합한 Jira 레이블을 추천하는 '전문 데이터 분석가'입니다.

당신에게는 '새로운 이메일 정보'와 'mem0 관련 기억' 두 가지가 제공됩니다.

'mem0 관련 기억'은 과거의 사용자 행동과 AI 결정을 요약한 맥락화된 정보입니다. 각 기억은 사용자가 직접 수행한 액션(레이블 수정, 티켓 생성 등)과 AI의 판단을 포함합니다.

당신의 임무는, 'mem0 관련 기억'을 면밀히 분석하여 '새로운 이메일'과 가장 관련성이 높은 핵심 패턴을 찾아내는 것입니다.

특히, 사용자가 직접 수행한 레이블 수정이나 티켓 생성 기록은 가장 중요한 단서입니다. 이 기록이 여러 번 나타난다면, 해당 레이블이 정답일 확률이 매우 높습니다.

분석이 끝나면, 가장 적합하다고 생각하는 레이블을 최대 3개까지 추천해주세요.

=== 새로운 이메일 정보 ===
제목: {email.subject}
발신자: {email.sender}
내용: {email.body}

=== mem0 관련 기억 ===
{action_summary}

답변은 반드시 아래의 JSON 형식만을 사용해야 하며, 다른 어떤 설명도 추가해서는 안 됩니다.

{{
  "recommended_labels": ["추천레이블_1", "추천레이블_2"],
  "reasoning": "mem0 관련 기억에서 과거 사용자가 유사한 '서버 점검' 이메일에 대해 'NCMS_운영지원' 레이블을 3번 추가했기 때문에, 이 레이블을 가장 강력하게 추천합니다."
}}"""
                        else:
                            # user_action이 없는 경우 - 강력한 새로운 프롬프트
                            llm_prompt = f"""당신은 이메일 내용을 분석하여 가장 적합한 Jira 레이블을 추천하는 '전문 데이터 분석가'입니다.

당신에게는 '새로운 이메일 정보'가 제공됩니다. 과거 사용자 행동 기록은 없지만, 이메일의 내용, 제목, 발신자를 종합적으로 분석하여 적절한 레이블을 추천해야 합니다.

당신의 임무는 이메일의 핵심 내용을 파악하고, 업무적 맥락에서 가장 적합한 레이블을 찾아내는 것입니다.

분석 기준:
- 이메일의 주요 주제나 내용과 관련된 레이블
- 발신자나 도메인과 관련된 레이블  
- 우선순위나 긴급도를 나타내는 레이블
- 업무 유형을 나타내는 레이블

분석이 끝나면, 가장 적합하다고 생각하는 레이블을 최대 3개까지 추천해주세요.

=== 새로운 이메일 정보 ===
제목: {email.subject}
발신자: {email.sender}
내용: {email.body}

답변은 반드시 아래의 JSON 형식만을 사용해야 하며, 다른 어떤 설명도 추가해서는 안 됩니다.

{{
  "recommended_labels": ["추천레이블_1", "추천레이블_2"],
  "reasoning": "이메일 내용에서 '서버 점검' 관련 내용이 확인되어 'NCMS_운영지원' 레이블을 추천합니다."
}}"""
                        
                        # LLM에게 레이블 추천 요청 (직접 Azure OpenAI 호출)
                        try:
                            from langchain_openai import AzureChatOpenAI
                            from langchain_core.prompts import ChatPromptTemplate
                            from langchain_core.output_parsers import StrOutputParser
                            import os
                            
                            # Azure OpenAI 설정
                            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
                            api_key = os.getenv("AZURE_OPENAI_API_KEY")
                            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
                            
                            if not all([azure_endpoint, deployment_name, api_key]):
                                raise ValueError("Azure OpenAI 환경 변수가 설정되지 않았습니다.")
                            
                            # LLM 인스턴스 생성
                            llm = AzureChatOpenAI(
                                azure_endpoint=azure_endpoint,
                                deployment_name=deployment_name,
                                openai_api_key=api_key,
                                openai_api_version=api_version,
                                temperature=0.3
                            )
                            
                            # 프롬프트 템플릿 생성
                            prompt_template = ChatPromptTemplate.from_messages([
                                ("system", "당신은 이메일 내용을 분석하여 적절한 Jira 레이블을 추천하는 전문가입니다."),
                                ("human", "{prompt}")
                            ])
                            
                            # 체인 생성
                            chain = prompt_template | llm | StrOutputParser()
                            
                            # LLM 호출
                            llm_response = chain.invoke({"prompt": llm_prompt})
                            
                        except Exception as llm_error:
                            logging.error(f"⚠️ 직접 LLM 호출 실패: {str(llm_error)}")
                            # 폴백: Memory-Based Ticket Processor 사용
                            from memory_based_ticket_processor import create_memory_based_ticket_processor
                            processor = create_memory_based_ticket_processor()
                            llm_response = processor._run(
                                email_content=llm_prompt,
                                email_subject=email.subject,
                                email_sender=email.sender,
                                message_id=email.id
                            )
                        
                        # LLM 응답 파싱
                        import json
                        import re
                        try:
                            # LLM 응답에서 JSON 부분 추출
                            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                llm_data = json.loads(json_str)
                                
                                # LLM 응답에서 레이블 추출 (새로운 JSON 형식에 맞게)
                                suggested_labels = llm_data.get('recommended_labels', [])
                                reasoning = llm_data.get('reasoning', 'LLM 추천')
                                
                                logging.info(f"🔍 LLM 레이블 추천: {suggested_labels}")
                                logging.info(f"🔍 추천 이유: {reasoning}")
                                
                                # email 객체에 LLM 추천 레이블 저장
                                email._llm_suggested_labels = suggested_labels
                                email._llm_reasoning = reasoning
                                
                            else:
                                # JSON 형식이 아닌 경우 기본 레이블
                                email._llm_suggested_labels = ['일반', '업무']
                                email._llm_reasoning = 'JSON 형식 아님'
                                logging.warning(f"⚠️ LLM 응답에서 JSON 형식을 찾을 수 없음: {llm_response[:200]}")
                                
                        except json.JSONDecodeError as e:
                            # JSON 파싱 실패 시 기본 레이블
                            email._llm_suggested_labels = ['일반', '업무']
                            email._llm_reasoning = 'JSON 파싱 실패'
                            logging.warning(f"⚠️ LLM 응답 JSON 파싱 실패: {str(e)}")
                            logging.warning(f"⚠️ 원본 응답: {llm_response[:200]}")
                            
                    except Exception as llm_error:
                        logging.error(f"⚠️ LLM 레이블 추천 실패: {str(llm_error)}")
                        # LLM 실패 시 기본 레이블
                        email._llm_suggested_labels = ['일반', '업무']
                        email._llm_reasoning = 'LLM 오류'
                    
                except Exception as e:
                    logging.error(f"⚠️ 메일 '{email.subject}' 유사 메일 검색 실패: {str(e)}")
                    # 오류 발생 시 기본 레이블 설정
                    email._llm_suggested_labels = ['일반', '업무']
                    email._llm_reasoning = '오류 발생'
                    continue
            
            logging.info(f"🔍 유사 메일 검색 및 LLM 기반 레이블 추천 완료")
            
        except Exception as e:
            logging.error(f"❌ 유사 메일 검색 및 LLM 기반 레이블 추천 실패: {str(e)}")
            import traceback
            logging.error(f"❌ 오류 상세: {traceback.format_exc()}")
            # 오류 발생 시 기본 레이블 설정
            for email in work_related_emails:
                email._llm_suggested_labels = ['일반', '업무']
                email._llm_reasoning = '시스템 오류'
        
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
                        
                        # LLM 분석 결과와 LLM 레이블 추천 결과 통합
                        llm_analysis = getattr(email, '_llm_analysis', {})
                        llm_suggested_labels = llm_analysis.get('suggested_labels', []) or []
                        suggested_priority = llm_analysis.get('priority', 'Medium')
                        suggested_ticket_type = llm_analysis.get('ticket_type', 'email')
                        
                        # 3단계에서 LLM이 user_action 기반으로 추천한 레이블
                        llm_action_based_labels = getattr(email, '_llm_suggested_labels', []) or []
                        llm_reasoning = getattr(email, '_llm_reasoning', '')
                        
                        # 두 LLM 레이블 소스를 통합 (user_action 기반 레이블 우선)
                        all_labels = []
                        
                        # 1. user_action 기반 LLM 추천 레이블 우선 추가
                        for label in llm_action_based_labels:
                            if label not in all_labels:
                                all_labels.append(label)
                                logging.info(f"🔍 user_action 기반 LLM 레이블 추가: {label}")
                        
                        # 2. 일반 LLM 추천 레이블 추가 (중복되지 않는 것만)
                        for label in llm_suggested_labels:
                            if label not in all_labels:
                                all_labels.append(label)
                                logging.info(f"🔍 일반 LLM 추천 레이블 추가: {label}")
                        
                        # 3. 레이블이 없으면 기본 레이블 추가
                        if not all_labels:
                            all_labels = ['일반', '업무']
                            logging.info(f"🔍 기본 레이블 추가: {all_labels}")
                        
                        logging.info(f"🔍 최종 통합 레이블: {all_labels}")
                        logging.info(f"🔍 user_action 기반 LLM 레이블: {llm_action_based_labels}")
                        logging.info(f"🔍 일반 LLM 추천 레이블: {llm_suggested_labels}")
                        logging.info(f"🔍 LLM 추천 이유: {llm_reasoning}")
                        
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
                            labels=all_labels,  # 통합된 레이블 사용
                            created_at=current_time,
                            updated_at=current_time
                        )
                        
                        logging.info(f"🔍 새로운 티켓 객체 생성: {new_ticket}")
                        logging.info(f"🔍 최종 통합 레이블: {all_labels}")
                        logging.info(f"🔍 LLM 제안 우선순위: {suggested_priority}")
                        logging.info(f"🔍 LLM 제안 티켓 타입: {suggested_ticket_type}")
                        
                        # insert_ticket 메서드로 티켓 생성
                        new_ticket_id = ticket_manager.insert_ticket(new_ticket)
                        if new_ticket_id:
                            new_tickets_created += 1
                            logging.info(f"🔍 새로운 티켓 생성 완료: ID={new_ticket_id}")
                            
                            # mem0에 티켓 생성 기억 저장
                            try:
                                memory_id = add_ticket_event(
                                    memory=mem0_memory,
                                    event_type="ticket_created",
                                    description=f"AI가 '{email.subject}' 이메일로부터 티켓 #{new_ticket_id}를 생성함 (레이블: {', '.join(all_labels)})",
                                    ticket_id=str(new_ticket_id),
                                    message_id=email.id
                                )
                                logging.info(f"🔍 mem0 티켓 생성 기억 저장 완료: {memory_id}")
                            except Exception as mem_error:
                                logging.warning(f"⚠️ mem0 기억 저장 실패: {mem_error}")
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
            
            # 업무용이 아니라고 판단된 메일들 수집 (confidence가 높은 것들만)
            non_work_emails_display = []
            for email in non_work_emails:
                if hasattr(email, '_llm_analysis') and email._llm_analysis:
                    analysis = email._llm_analysis
                    if not analysis.get('is_work_related', True) and analysis.get('confidence', 0) > 0.5:
                        non_work_emails_display.append({
                            'id': email.id,
                            'subject': email.subject,
                            'sender': email.sender,
                            'body': email.body[:200] + '...' if len(email.body) > 200 else email.body,
                            'received_date': str(email.received_date),
                            'confidence': analysis.get('confidence', 0),
                            'reason': analysis.get('reason', ''),
                            'priority': analysis.get('priority', 'Low'),
                            'suggested_labels': analysis.get('suggested_labels', []),
                            'ticket_type': analysis.get('ticket_type', 'Task')
                        })
            
            # confidence 순으로 정렬 (높은 것부터)
            non_work_emails_display.sort(key=lambda x: x['confidence'], reverse=True)
            
            # 결과 반환
            result = {
                'display_mode': 'tickets',
                'tickets': tickets,
                'non_work_emails': non_work_emails_display,
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