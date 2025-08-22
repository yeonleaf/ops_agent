#!/usr/bin/env python3
"""
LangChain 에이전트와 규칙 기반 도구를 결합한 AI 메일 조회 챗봇 (최종 최적화 버전)
"""

import streamlit as st
import json
import os
import sys
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# LangChain 관련 import
from langchain_core.tools import BaseTool
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 환경 변수 로딩 (가장 먼저 실행)
load_dotenv()

# 로컬 모듈 import
from enhanced_ticket_ui import display_ticket_list_with_sidebar, clear_ticket_selection
from mail_list_ui import create_mail_list_ui, create_mail_list_with_sidebar
from unified_email_service import (
    get_email_provider_status, 
    get_available_providers, 
    get_default_provider, 
    EmailMessage, 
    process_emails_with_ticket_logic, 
    get_raw_emails
)

# --- 1. 로그 및 파서 함수 (기존과 동일, 안정성 강화) ---

# logging 설정
import logging
import os

# 기존 로거 핸들러 제거 (중복 방지)
for handler in logging.getLogger().handlers[:]:
    logging.getLogger().removeHandler(handler)

# 현재 시간으로 로그 파일명 생성
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"debug_logs_{timestamp}.txt"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        logging.FileHandler(log_filename, mode='w', encoding='utf-8')  # 파일 출력 (새 파일)
    ]
)

print(f"✅ 로깅 시스템 초기화 완료 - 로그 파일: {log_filename}")
print(f"📁 현재 디렉토리: {os.getcwd()}")
print(f"🔍 로그 파일 경로: {os.path.abspath(log_filename)}")

def determine_ui_mode(query: str, response_data: Dict[str, Any]) -> str:
    """쿼리와 응답 데이터를 기반으로 UI 모드를 결정합니다."""
    query_lower = query.lower()
    display_mode = response_data.get('display_mode', '')
    
    # 버튼 리스트가 필요한 키워드들
    button_list_keywords = [
        "목록", "리스트", "조회", "보여줘", "확인", "찾아줘",
        "티켓", "메일", "전체", "생성되어 있는", "이미"
    ]
    
    # 텍스트만 필요한 키워드들  
    text_only_keywords = [
        "요약", "통계", "개수", "몇 개", "상태", "정보"
    ]
    
    # 1. 명시적으로 텍스트만 요청하는 경우
    text_score = sum(1 for kw in text_only_keywords if kw in query_lower)
    if text_score > 0:
        return "text_only"
    
    # 2. 메일이나 티켓 리스트를 요청하는 경우
    button_score = sum(1 for kw in button_list_keywords if kw in query_lower)
    
    # 3. display_mode가 mail_list이고 버튼 관련 키워드가 있으면 버튼 리스트
    if display_mode == 'mail_list' and button_score >= 2:
        return "button_list"
    
    # 4. 티켓 관련 요청이면 기본적으로 버튼 리스트
    if display_mode == 'tickets' or "티켓" in query_lower:
        return "button_list"
    
    # 5. 기본값은 텍스트
    return "text_only"

def parse_query_to_parameters(query: str) -> Dict[str, Any]:
    """LLM을 사용하여 사용자 쿼리를 분석하여 실행 파라미터 딕셔너리를 생성합니다."""
    logging.info(f"LLM 쿼리 파싱 시작: '{query}'")
    
    # session_state 상태 확인
    logging.info(f"session_state.llm 존재 여부: {'llm' in st.session_state}")
    if 'llm' in st.session_state:
        logging.info(f"session_state.llm 값: {st.session_state.llm}")
    
    try:
        # LLM이 사용 가능한 경우 LLM 기반 파싱 사용
        if 'llm' in st.session_state and st.session_state.llm:
            logging.info("LLM 기반 파싱 시도 중...")
            result = _parse_query_with_llm(query)
            logging.info(f"LLM 파싱 성공: {result}")
            return result
        else:
            logging.warning("LLM이 사용 불가능하여 규칙 기반 파싱으로 대체")
            result = _parse_query_with_rules(query)
            logging.info(f"규칙 기반 파싱 결과: {result}")
            return result
    except Exception as e:
        logging.error(f"LLM 쿼리 파싱 실패, 규칙 기반으로 대체: {str(e)}")
        result = _parse_query_with_rules(query)
        logging.info(f"Fallback 규칙 기반 파싱 결과: {result}")
        return result

def _parse_query_with_llm(query: str) -> Dict[str, Any]:
    """LLM을 사용하여 자연어 쿼리를 Gmail API 파라미터로 변환합니다."""
    try:
        llm = st.session_state.llm
        
        # LLM에게 전달할 시스템 프롬프트
        system_prompt = """당신은 Gmail API 쿼리 생성 전문가입니다.
사용자의 자연어 요청을 Gmail API 파라미터로 변환해주세요.

지원하는 필터:
- is_read: true/false (읽은 메일/안 읽은 메일)
- sender: 발신자 이메일 또는 도메인
- subject: 제목에 포함된 키워드
- has_attachments: true/false (첨부파일 유무)
- limit: 가져올 메일 개수
- date_after: 특정 날짜 이후 (YYYY-MM-DD)
- date_before: 특정 날짜 이전 (YYYY-MM-DD)

지원하는 액션:
- view: 메일 조회
- classify: 메일 분류 및 티켓 생성
- process_tickets: 티켓 처리

응답은 반드시 다음 JSON 형식으로만 해주세요:
{
    "action": "view",
    "filters": {
        "is_read": false,
        "limit": 10
    }
}"""

        # 사용자 쿼리
        user_message = f"다음 요청을 Gmail API 파라미터로 변환해주세요: {query}"
        
        # LLM 호출
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        response_content = response.content
        
        logging.info(f"LLM 응답: {response_content}")
        
        # JSON 파싱 시도
        try:
            # JSON 블록 추출 (```json ... ``` 형태일 수 있음)
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                if json_end != -1:
                    response_content = response_content[json_start:json_end].strip()
            
            # JSON 파싱
            params = json.loads(response_content)
            
            # 필수 필드 검증
            if 'action' not in params:
                params['action'] = 'view'
            if 'filters' not in params:
                params['filters'] = {}
                
            logging.info(f"LLM 파싱 결과: {params}")
            return params
            
        except json.JSONDecodeError as e:
            logging.error(f"LLM 응답 JSON 파싱 실패: {str(e)}")
            logging.error(f"응답 내용: {response_content}")
            raise e
            
    except Exception as e:
        logging.error(f"LLM 쿼리 파싱 오류: {str(e)}")
        raise e

def _parse_query_with_rules(query: str) -> Dict[str, Any]:
    """규칙 기반 쿼리 파싱 (LLM 실패 시 대체용)"""
    logging.info(f"규칙 기반 쿼리 파싱 시작: '{query}'")
    query_lower = query.lower()
    params = {'action': 'view', 'filters': {}}

    view_keywords = ["보여줘", "찾아줘", "조회", "목록", "리스트", "보기", "확인"]
    process_keywords = ["처리", "분류", "업무", "티켓", "작업", "정리해줘"]
    
    view_score = sum(1 for kw in view_keywords if kw in query_lower)
    process_score = sum(1 for kw in process_keywords if kw in query_lower)
    
    if '개' in query_lower and re.search(r'\d+', query):
        view_score += 2

    # "티켓" 키워드가 있으면 먼저 분류 후 티켓 처리
    if "티켓" in query_lower:
        params['action'] = 'classify'
    elif process_score > view_score:
        params['action'] = 'process_tickets'

    # 안 읽은 메일 관련 키워드 (공백 유무 상관없이)
    unread_keywords = ["안읽은", "안 읽은", "새로운", "새 메일", "읽지 않은", "읽지않은"]
    read_keywords = ["읽은", "읽은 메일", "읽음"]
    
    # 디버깅: 키워드 매칭 확인
    matched_unread = [kw for kw in unread_keywords if kw in query_lower]
    matched_read = [kw for kw in read_keywords if kw in query_lower]
    
    logging.info(f"쿼리: '{query}' -> 소문자: '{query_lower}'")
    logging.info(f"안 읽은 키워드 매칭 시도: {unread_keywords}")
    logging.info(f"읽은 키워드 매칭 시도: {read_keywords}")
    logging.info(f"매칭된 안 읽은 키워드: {matched_unread}")
    logging.info(f"매칭된 읽은 키워드: {matched_read}")
    
    if matched_unread:
        params['filters']['is_read'] = False
        logging.info(f"✅ 안 읽은 메일로 설정: is_read=False")
    elif matched_read:
        params['filters']['is_read'] = True
        logging.info(f"✅ 읽은 메일로 설정: is_read=True")
    else:
        logging.info("⚠️ 읽음 상태 관련 키워드가 없음 - 기본값 사용")
    
    if match := re.search(r'(\d+)개', query):
        params['filters']['limit'] = int(match.group(1))

    logging.info(f"규칙 기반 파싱 결과: {params}")
    return params

def handle_mail_query(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    파라미터 딕셔너리를 기반으로 메일 쿼리를 처리하는 통합 함수
    """
    action = params.get('action', 'view')
    filters = params.get('filters', {})
    provider = st.session_state.get('email_provider', get_default_provider())
    
    logging.info(f"메일 쿼리 핸들러 실행: action='{action}', filters={filters}")

    try:
        if action == 'view_mails':
            # 단순 메일 조회는 get_raw_emails 함수를 호출합니다.
            logging.info(f"view_mails 액션: get_raw_emails 호출 - provider={provider}, filters={filters}")
            emails = get_raw_emails(provider, filters)
            if emails:
                # EmailMessage 객체를 JSON 직렬화 가능한 딕셔너리로 변환
                mail_list = []
                for email in emails:
                    email_dict = email.model_dump()
                    mail_list.append({
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    })
                return {'display_mode': 'mail_list', 'mail_list': mail_list}
            else:
                return {'display_mode': 'no_emails', 'message': '조건에 맞는 메일이 없습니다.'}
        
        elif action == 'view_tickets':
            # 기존 티켓 조회 (이미 생성된 티켓 목록)
            logging.info(f"view_tickets 액션: 기존 티켓 조회")
            try:
                from sqlite_ticket_models import SQLiteTicketManager
                ticket_manager = SQLiteTicketManager()
                # pending 상태인 티켓만 조회
                existing_tickets = ticket_manager.get_tickets_by_status('pending')
                
                if existing_tickets:
                    # Ticket 객체를 딕셔너리로 변환
                    ticket_list = []
                    for ticket in existing_tickets:
                        ticket_dict = {
                            'ticket_id': ticket.ticket_id,
                            'title': ticket.title,
                            'status': ticket.status,
                            'priority': ticket.priority,
                            'ticket_type': ticket.ticket_type,
                            'reporter': ticket.reporter,
                            'created_at': ticket.created_at,
                            'updated_at': ticket.updated_at
                        }
                        ticket_list.append(ticket_dict)
                    
                    logging.info(f"기존 티켓 {len(ticket_list)}개 조회 완료")
                    return {'display_mode': 'tickets', 'tickets': ticket_list, 'message': f'기존 티켓 {len(ticket_list)}개를 조회했습니다.'}
                else:
                    logging.info("기존 티켓이 없습니다.")
                    return {'display_mode': 'no_tickets', 'message': '생성된 티켓이 없습니다.', 'tickets': []}
                    
            except Exception as e:
                logging.error(f"기존 티켓 조회 오류: {str(e)}")
                return {'display_mode': 'error', 'message': f'기존 티켓 조회 중 오류가 발생했습니다: {str(e)}', 'tickets': []}
        
        elif action == 'view':
            # 기존 view 액션과의 호환성을 위한 fallback
            logging.info(f"view 액션 (fallback): get_raw_emails 호출")
            emails = get_raw_emails(provider, filters)
            if emails:
                mail_list = []
                for email in emails:
                    email_dict = email.model_dump()
                    mail_list.append({
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    })
                return {'display_mode': 'mail_list', 'mail_list': mail_list}
            else:
                return {'display_mode': 'no_emails', 'message': '조건에 맞는 메일이 없습니다.'}
        
        elif action == 'classify':
            # 메일 분류는 get_raw_emails로 메일을 가져온 후 분류 로직 적용
            emails = get_raw_emails(provider, filters)
            if emails:
                # EmailMessage 객체를 JSON 직렬화 가능한 딕셔너리로 변환
                mail_list = []
                work_related_emails = []
                
                for email in emails:
                    email_dict = email.model_dump()
                    mail_data = {
                        'id': email_dict.get('id'),
                        'subject': email_dict.get('subject'),
                        'sender': email_dict.get('sender'),
                        'body': email_dict.get('body'),
                        'received_date': email_dict.get('received_date').isoformat() if email_dict.get('received_date') else None,
                        'is_read': email_dict.get('is_read', False),
                        'priority': email_dict.get('priority'),
                        'has_attachments': email_dict.get('has_attachments', False)
                    }
                    mail_list.append(mail_data)
                    
                    # 업무 관련 메일인지 확인 (간단한 키워드 기반 필터링)
                    subject_lower = email_dict.get('subject', '').lower()
                    body_lower = email_dict.get('body', '').lower()
                    
                    work_keywords = ['업무', '회사', '프로젝트', '회의', '보고서', '개발', '코딩', '버그', '이슈', '배포', '테스트', '코드', '시스템', '서버', '데이터베이스', 'api', '웹', '앱', '소프트웨어', '프로그램', '기술', '인프라', '클라우드', '보안', '백업', '모니터링', '로그', '성능', '최적화', '업그레이드', '마이그레이션', '통합', '연동', '동기화', '백업', '복구', '장애', '오류', '에러', '문제', '해결', '지원', '문의', '요청', '제안', '검토', '승인', '결재', '계약', '협력', '파트너', '고객', '사용자', '관리자', '운영', '유지보수', '개선', '개발', '설계', '구현', '테스트', '배포', '운영', '모니터링', '백업', '복구', '보안', '인증', '권한', '접근', '로그', '감사', '준수', '정책', '절차', '가이드', '매뉴얼', '문서', '코드', '소스', '버전', '커밋', '브랜치', '머지', '풀리퀘스트', '코드리뷰', '테스트', 'qa', '품질', '성능', '보안', '접근성', '사용성', '호환성', '확장성', '안정성', '신뢰성', '가용성', '복구성', '백업', '동기화', '백업', '복구', '장애', '오류', '에러', '문제', '해결', '지원', '문의', '요청', '제안', '검토', '승인', '결재', '계약', '협력', '파트너', '고객', '사용자', '관리자', '운영', '유지보수', '개선', '개발', '설계', '구현', '테스트', '배포', '운영', '모니터링', '백업', '복구', '보안', '인증', '권한', '접근', '로그', '감사', '준수', '정책', '절차', '가이드', '매뉴얼', '문서', '코드', '소스', '버전', '커밋', '브랜치', '머지', '풀리퀘스트', '코드리뷰', '테스트', 'qa', '품질', '성능', '보안', '접근성', '사용성', '호환성', '확장성', '안정성', '신뢰성', '가용성', '복구성']
                    
                    # 업무 관련 키워드가 있거나, 특정 도메인이 아닌 경우 업무 관련으로 간주
                    is_work_related = any(keyword in subject_lower or keyword in body_lower for keyword in work_keywords)
                    
                    # 개인/스팸 메일 도메인 제외
                    personal_domains = ['@gmail.com', '@naver.com', '@daum.net', '@hotmail.com', '@outlook.com', '@yahoo.com']
                    sender_domain = email_dict.get('sender', '').lower()
                    is_personal = any(domain in sender_domain for domain in personal_domains)
                    
                    if is_work_related and not is_personal:
                        work_related_emails.append(mail_data)
                
                # 업무 관련 메일이 있으면 티켓 처리 진행
                if work_related_emails:
                    # 티켓 처리 로직 실행 (이미 import됨)
                    try:
                        logging.info(f"티켓 처리 시작: 업무 관련 메일 {len(work_related_emails)}개")
                        
                        ticket_result = process_emails_with_ticket_logic(provider, user_query=str(params))
                        logging.info(f"티켓 처리 결과: {ticket_result}")
                        
                        # 티켓 결과 검증
                        if not ticket_result.get('tickets'):
                            logging.warning(f"경고: 티켓 결과에 tickets 배열이 없음: {ticket_result}")
                        
                        # 티켓 결과에 분류 정보 추가
                        ticket_result['classification_info'] = f'업무 관련 메일 {len(work_related_emails)}개를 티켓으로 처리했습니다.'
                        ticket_result['work_related_count'] = len(work_related_emails)
                        ticket_result['total_emails'] = len(mail_list)
                        
                        logging.info(f"최종 반환 결과: {ticket_result}")
                        return ticket_result
                    except Exception as e:
                        logging.error(f"티켓 처리 중 오류: {e}")
                        import traceback
                        logging.error(f"오류 상세: {traceback.format_exc()}")
                        return {
                            'display_mode': 'classified_mail_list',
                            'mail_list': work_related_emails,
                            'classification_info': f'업무 관련 메일 {len(work_related_emails)}개를 찾았지만 티켓 처리 중 오류가 발생했습니다.',
                            'error': str(e)
                        }
                else:
                    # 업무 관련 메일이 없는 경우
                    return {
                        'display_mode': 'classified_mail_list',
                        'mail_list': mail_list,
                        'classification_info': '업무 관련 메일이 없습니다. 모든 메일을 단순 조회로 표시합니다.',
                        'work_related_count': 0,
                        'total_emails': len(mail_list)
                    }
            else:
                return {'display_mode': 'no_emails', 'message': '분류할 메일이 없습니다.'}
        
        elif action == 'process_tickets':
            # 티켓 처리는 process_emails_with_ticket_logic 함수를 호출합니다.
            logging.info(f"process_tickets 액션 시작: provider={provider}, params={params}")
            
            try:
                response_data = process_emails_with_ticket_logic(provider, user_query=str(params))
                logging.info(f"process_emails_with_ticket_logic 결과: {response_data}")
                
                # 티켓 결과 검증
                if response_data.get('display_mode') == 'tickets':
                    tickets_count = len(response_data.get('tickets', []))
                    logging.info(f"process_tickets - 티켓 개수: {tickets_count}")
                    if tickets_count == 0:
                        logging.warning(f"process_tickets - 경고: 티켓이 0개입니다. 전체 결과: {response_data}")
                
                return response_data
            except Exception as e:
                logging.error(f"process_tickets 액션 오류: {e}")
                import traceback
                logging.error(f"오류 상세: {traceback.format_exc()}")
                raise
            
    except Exception as e:
        logging.error(f"handle_mail_query 오류: {e}")
        st.error(f"메일 처리 중 오류가 발생했습니다: {str(e)}")
        return {'display_mode': 'error', 'message': f'처리 중 오류가 발생했습니다.'}

# --- 2. 새로운 LangChain 도구 정의 ---

class ViewEmailsTool(BaseTool):
    """단순 이메일 조회 및 필터링을 위한 LangChain 도구"""
    name: str = "view_emails_tool"
    description: str = """단순 이메일 조회 및 필터링을 위한 도구입니다. 
    
    사용해야 하는 경우:
    - "안 읽은 메일 3개 보여줘"
    - "읽은 메일 목록"
    - "특정 발신자 메일 조회"
    - "최근 메일 5개"
    - "메일 리스트"
    - "이메일 확인"
    
    이 도구는 메일을 조회하고 표시하는 것만 담당하며, 티켓 생성이나 분류는 수행하지 않습니다."""
    
    def _run(self, query: str) -> str:
        """메일 조회만 수행하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(f"ViewEmailsTool 실행: {query}")
            params = parse_query_to_parameters(query)
            logging.info(f"파싱된 파라미터: {params}")
            
            # view 액션만 처리
            if params.get('action') != 'view':
                return json.dumps({"error": "이 도구는 메일 조회만 가능합니다."}, ensure_ascii=False)
            
            result_data = handle_mail_query(params)
            logging.info(f"핸들러 실행 결과: {result_data}")
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(f"세션에 직접 저장 완료: {st.session_state.get('latest_response') is not None}")
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(f"반환할 JSON: {json_result}")
            return json_result
        except Exception as e:
            error_msg = f"ViewEmailsTool 실행 오류: {e}"
            logging.error(error_msg)
            return json.dumps({"error": error_msg}, ensure_ascii=False)

class ClassifyEmailsTool(BaseTool):
    """이메일 조회 및 내부 분류기 실행을 위한 LangChain 도구"""
    name: str = "classify_emails_tool"
    description: str = """이메일을 조회하고 내부 분류기를 실행하여 업무 관련성을 판단하는 도구입니다.
    
    사용해야 하는 경우:
    - "업무 메일 분류해줘"
    - "중요한 메일 찾아줘"
    - "메일을 분류해서 보여줘"
    - "업무 관련 메일만"
    - "메일 우선순위 정해줘"
    
    이 도구는 메일을 조회하고 분류하지만, 티켓 생성은 수행하지 않습니다."""
    
    def _run(self, query: str) -> str:
        """메일 조회 및 분류를 수행하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(f"ClassifyEmailsTool 실행 시작: {query}")
            params = parse_query_to_parameters(query)
            logging.info(f"파싱된 파라미터: {params}")
            
            # classify 액션으로 변경
            params['action'] = 'classify'
            logging.info(f"액션 강제 설정: {params['action']}")
            
            logging.info("handle_mail_query 호출 시작")
            result_data = handle_mail_query(params)
            logging.info(f"핸들러 실행 결과: {result_data}")
            
            # 티켓 결과 검증
            if result_data.get('display_mode') == 'tickets':
                tickets_count = len(result_data.get('tickets', []))
                logging.info(f"티켓 개수 확인: {tickets_count}")
                if tickets_count == 0:
                    logging.warning(f"경고: 티켓이 0개입니다. 전체 결과: {result_data}")
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            logging.info(f"UI 모드 결정: {ui_mode}")
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(f"세션에 직접 저장 완료: {st.session_state.get('latest_response') is not None}")
                logging.info(f"세션에 저장된 데이터: {st.session_state.get('latest_response')}")
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(f"ClassifyEmailsTool 최종 반환: {json_result}")
            return json_result
        except Exception as e:
            error_msg = f"ClassifyEmailsTool 실행 오류: {e}"
            logging.error(error_msg)
            import traceback
            logging.error(f"오류 상세: {traceback.format_exc()}")
            return json.dumps({"error": error_msg}, ensure_ascii=False)

class ProcessTicketsTool(BaseTool):
    """이메일 조회, 티켓 생성/조회 등 전체 티켓 워크플로우를 처리하는 LangChain 도구"""
    name: str = "process_tickets_tool"
    description: str = """이메일을 조회하고 티켓 생성/조회 등 전체 티켓 워크플로우를 처리하는 도구입니다.
    
    사용해야 하는 경우:
    - "티켓 생성해줘"
    - "업무 메일을 티켓으로 만들어줘"
    - "기존 티켓 목록 조회"
    - "오늘 처리할 티켓"
    - "티켓 워크플로우 실행"
    - "메일을 티켓으로 변환"
    
    이 도구는 메일 조회부터 티켓 생성까지 전체 프로세스를 담당합니다."""
    
    def _determine_action_with_llm(self, query: str) -> str:
        """LLM을 사용하여 사용자 요청의 의도를 파악하고 적절한 액션을 결정합니다."""
        try:
            # LLM이 사용 가능한 경우 LLM 기반 판단
            if 'llm' in st.session_state and st.session_state.llm:
                return self._determine_action_with_llm_internal(query)
            else:
                logging.warning("LLM이 사용 불가능하여 기본 규칙 기반 판단으로 대체")
                return self._determine_action_with_rules(query)
        except Exception as e:
            logging.error(f"LLM 액션 결정 실패, 규칙 기반으로 대체: {str(e)}")
            return self._determine_action_with_rules(query)
    
    def _determine_action_with_llm_internal(self, query: str) -> str:
        """LLM을 사용하여 액션을 결정합니다."""
        try:
            llm = st.session_state.llm
            
            system_prompt = """당신은 사용자 요청을 분석하여 적절한 액션을 결정하는 전문가입니다.

지원하는 액션:
1. view_mails: 단순 메일 조회 (필터링, 검색, 목록 등)
2. view_tickets: 기존 티켓 조회 (이미 생성된 티켓 목록)
3. process_tickets: 새로운 티켓 생성 및 업무 처리

판단 기준:
- "메일 보여줘", "이메일 조회", "안 읽은 메일" → view_mails
- "기존 티켓 목록", "생성된 티켓 보여줘", "이미 있는 티켓" → view_tickets  
- "새로운 티켓 생성", "업무 메일을 티켓으로", "메일을 티켓으로 변환" → process_tickets
- "오늘 받은 메일 중 중요한 것만" → view_mails (메일 필터링)
- "업무 관련 메일을 티켓으로 변환" → process_tickets

JSON 형식으로만 응답:
{
    "action": "view_mails|view_tickets|process_tickets",
    "reasoning": "선택 이유",
    "query_type": "mail_query|ticket_query|ticket_creation"
}"""

            user_message = f"다음 요청을 분석하여 적절한 액션을 결정해주세요: {query}"
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
            
            response = llm.invoke(messages)
            response_content = response.content
            
            logging.info(f"LLM 액션 결정 응답: {response_content}")
            
            # JSON 파싱
            try:
                if "```json" in response_content:
                    json_start = response_content.find("```json") + 7
                    json_end = response_content.find("```", json_start)
                    if json_end != -1:
                        response_content = response_content[json_start:json_end].strip()
                
                result = json.loads(response_content)
                action = result.get('action', 'view_mails')
                reasoning = result.get('reasoning', '')
                
                logging.info(f"LLM 액션 결정 결과: {action}, 이유: {reasoning}")
                return action
                
            except json.JSONDecodeError as e:
                logging.error(f"LLM 응답 JSON 파싱 실패: {str(e)}")
                raise e
                
        except Exception as e:
            logging.error(f"LLM 액션 결정 오류: {str(e)}")
            raise e
    
    def _determine_action_with_rules(self, query: str) -> str:
        """규칙 기반으로 액션을 결정합니다 (LLM 실패 시 대체용)"""
        query_lower = query.lower()
        
        # 기존 티켓 조회 키워드
        ticket_view_keywords = ["이미 생성된", "기존", "생성된", "있는", "티켓 목록", "티켓 리스트"]
        if any(keyword in query_lower for keyword in ticket_view_keywords):
            return 'view_tickets'
        
        # 새로운 티켓 생성 키워드
        ticket_creation_keywords = ["새로운", "생성", "만들어줘", "변환", "업무 메일을 티켓으로"]
        if any(keyword in query_lower for keyword in ticket_creation_keywords):
            return 'process_tickets'
        
        # 기본값: 메일 조회
        return 'view_mails'
    
    def _run(self, query: str) -> str:
        """전체 티켓 워크플로우를 처리하고 결과를 JSON 문자열로 반환합니다."""
        try:
            logging.info(f"ProcessTicketsTool 실행: {query}")
            params = parse_query_to_parameters(query)
            logging.info(f"파싱된 파라미터: {params}")
            
            # LLM을 사용하여 액션 결정
            params['action'] = self._determine_action_with_llm(query)
            logging.info(f"ProcessTicketsTool에서 LLM 기반 액션 결정: {params['action']}")
            result_data = handle_mail_query(params)
            logging.info(f"핸들러 실행 결과: {result_data}")
            
            # 티켓 결과 검증
            if result_data.get('display_mode') == 'tickets':
                tickets_count = len(result_data.get('tickets', []))
                logging.info(f"ProcessTicketsTool - 티켓 개수 확인: {tickets_count}")
                if tickets_count == 0:
                    logging.warning(f"ProcessTicketsTool - 경고: 티켓이 0개입니다. 전체 결과: {result_data}")
            
            # UI 모드 결정 및 세션에 저장
            ui_mode = determine_ui_mode(query, result_data)
            result_data['ui_mode'] = ui_mode
            
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state.latest_response = result_data
                logging.info(f"세션에 직접 저장 완료: {st.session_state.get('latest_response') is not None}")
            
            json_result = json.dumps(result_data, ensure_ascii=False, indent=2)
            logging.info(f"반환할 JSON: {json_result}")
            return json_result
        except Exception as e:
            error_msg = f"ProcessTicketsTool 실행 오류: {e}"
            logging.error(error_msg)
            return json.dumps({"error": error_msg}, ensure_ascii=False)

# --- 3. Streamlit 앱 메인 로직 ---

def init_session_state():
    """세션 상태 변수들을 초기화합니다."""
    defaults = {
        'main_agent': None,
        'messages': [],
        'latest_response': None,
        'email_provider': get_default_provider(),
        'email_connected': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def create_main_agent():
    """LLM과 도구를 사용하여 메인 에이전트를 생성합니다."""
    try:
        # --- 1. 환경 변수 로드 및 검증 (가장 중요!) ---
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        # 필수 변수들이 모두 로드되었는지 확인
        if not all([api_key, api_version, azure_endpoint, deployment_name]):
            missing_vars = [var for var, val in locals().items() if not val]
            st.error(f"필수 환경변수가 누락되었습니다: {', '.join(missing_vars)}. .env 파일을 확인해주세요.")
            return None
            
        # .env 파일에 불필요한 공백이나 '/'가 들어가는 것을 방지
        clean_endpoint = azure_endpoint.strip().rstrip('/')

        # --- 2. Streamlit UI에 현재 설정값 출력 (디버깅용) ---
        st.info("🔧 현재 적용된 Azure OpenAI 설정:")
        st.text(f"   - ENDPOINT: {clean_endpoint}")
        st.text(f"   - DEPLOYMENT_NAME: {deployment_name}")
        st.text(f"   - API_VERSION: {api_version}")
        
        # --- 3. AzureChatOpenAI 초기화 (표준 방식) ---
        # 라이브러리가 clean_endpoint를 기반으로 전체 URL을 만들도록 위임합니다.
        llm = AzureChatOpenAI(
            azure_endpoint=clean_endpoint,
            deployment_name=deployment_name,
            api_key=api_key,
            api_version=api_version,
            temperature=0
        )
        st.success("✅ AzureChatOpenAI 초기화 성공")
        
        # LLM을 session_state에 저장 (쿼리 파싱에서 사용)
        st.session_state.llm = llm
        logging.info("LLM이 session_state에 저장되었습니다.")

        tools = [
            ViewEmailsTool(),
            ClassifyEmailsTool(),
            ProcessTicketsTool()
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 사용자의 요청을 분석하여 가장 적절한 전문 도구를 선택하는 유능한 AI 어시스턴트입니다.

🚨 **도구 선택 규칙:**
사용자의 요청에 따라 다음 세 가지 도구 중 하나를 선택해야 합니다:

1. **view_emails_tool**: 단순 메일 조회 및 필터링
   - "안 읽은 메일 보여줘", "메일 목록", "특정 발신자 메일" 등

2. **classify_emails_tool**: 메일 분류 및 업무 관련성 판단
   - "업무 메일 분류", "중요한 메일 찾기", "메일 우선순위" 등

3. **process_tickets_tool**: 전체 티켓 워크플로우
   - "티켓 생성", "기존 티켓 조회", "업무 메일을 티켓으로 변환" 등

📋 **도구 사용이 필수인 경우들:**
- 메일/이메일 관련 모든 요청
- 티켓 관련 모든 요청
- 업무 처리 관련 모든 요청

✅ **도구 사용 후 응답 예시:**
"[선택된 도구명] 도구를 사용하여 요청하신 정보를 처리했습니다. 결과는 화면에 표시됩니다."

❌ **금지된 응답:**
- 직접적인 메일/티켓 정보 제공
- 도구 사용 없이 결과 설명

🔍 **일반 대화만 직접 답변:**
- 날씨, 수학 계산, 일반적인 대화 등 이메일/업무와 무관한 요청만 직접 답변하세요."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_functions_agent(llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    except Exception as e:
        st.error(f"에이전트 생성 실패: {e}")
        logging.error(f"에이전트 생성 실패: {e}")
        import traceback
        logging.error(f"오류 상세: {traceback.format_exc()}")
        return None
        
def handle_query(query: str):
    """사용자 쿼리를 받아 에이전트를 실행하고 상태를 업데이트합니다."""
    clear_ticket_selection()
    st.session_state.latest_response = None
    st.session_state.messages.append(HumanMessage(content=query))

    if not st.session_state.main_agent:
        st.error("에이전트가 초기화되지 않았습니다. 설정을 확인해주세요.")
        return

    with st.spinner("🤖 AI가 요청을 분석하고 처리하는 중..."):
        try:
            chat_history = st.session_state.messages[:-1] # 현재 입력을 제외한 히스토리
            response = st.session_state.main_agent.invoke({
                "input": query,
                "chat_history": chat_history
            })
            
            # 도구 결과를 안정적으로 추출 (핵심 개선)
            tool_output_str = None
            logging.info(f"전체 응답 구조: {list(response.keys())}")
            logging.info(f"응답 내용: {response}")
            
            # 1. intermediate_steps에서 도구 결과 추출 시도
            if "intermediate_steps" in response and response["intermediate_steps"]:
                logging.info(f"intermediate_steps 발견: {len(response['intermediate_steps'])}개")
                for i, step in enumerate(response["intermediate_steps"]):
                    logging.info(f"Step {i}: {step}")
                    if len(step) >= 2:
                        tool_output_str = step[1]
                        logging.info(f"도구 출력 추출: {tool_output_str}")
                        break
            
            # 2. output에서 도구 결과 추출 시도 (LangChain 버전에 따라 다를 수 있음)
            elif "output" in response:
                output = response["output"]
                logging.info(f"output 내용: {output}")
                
                # output이 문자열이고 JSON이 포함되어 있는지 확인
                if isinstance(output, str) and "{" in output and "}" in output:
                    # JSON 부분 추출 시도
                    try:
                        start = output.find("{")
                        end = output.rfind("}") + 1
                        if start != -1 and end != -1:
                            json_str = output[start:end]
                            logging.info(f"JSON 추출 시도: {json_str}")
                            # 유효한 JSON인지 확인
                            json.loads(json_str)
                            tool_output_str = json_str
                            logging.info(f"output에서 JSON 추출 성공")
                    except:
                        logging.info("output에서 JSON 추출 실패")
            
            if not tool_output_str:
                logging.info("도구 결과를 찾을 수 없습니다.")

            if tool_output_str:
                logging.info(f"도구 실행 결과: {tool_output_str}")
                try:
                    response_data = json.loads(tool_output_str)
                    
                    # UI 모드 결정 및 저장
                    ui_mode = determine_ui_mode(query, response_data)
                    response_data['ui_mode'] = ui_mode
                    st.session_state.latest_response = response_data
                    
                    logging.info(f"UI 모드 결정: {ui_mode}, display_mode: {response_data.get('display_mode')}")
                    logging.info(f"latest_response 설정 완료: {st.session_state.get('latest_response') is not None}")
                    
                    # 화면에 표시될 최종 AI 답변 생성
                    final_message = response.get("output", "결과를 확인해주세요.")
                    st.session_state.messages.append(AIMessage(content=final_message))
                except json.JSONDecodeError as e:
                    logging.error(f"JSON 파싱 오류: {e}, tool_output_str: {tool_output_str}")
                    st.error(f"응답 데이터 파싱 오류: {e}")
                except Exception as e:
                    logging.error(f"응답 처리 오류: {e}")
                    st.error(f"응답 처리 중 오류 발생: {e}")
            else:
                logging.info(f"도구가 사용되지 않음. LLM 직접 응답: {response.get('output')}")
                # 도구를 사용하지 않은 일반 답변
                st.session_state.messages.append(AIMessage(content=response.get("output")))

        except Exception as e:
            error_msg = f"처리 중 오류 발생: {e}"
            st.error(error_msg)
            logging.error(error_msg)
            st.session_state.messages.append(AIMessage(content=error_msg))
    
    st.rerun()

def main():
    """메인 애플리케이션 함수"""
    # 환경변수 확인 및 설정 (.env 파일에서 자동 로드됨)
    required_env_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", 
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        st.error(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        st.info("프로젝트 루트의 .env 파일을 확인해주세요.")
        return
    
    init_session_state()

    st.title("🤖 AI 메일 어시스턴트")
    
    with st.sidebar:
        st.header("🔗 연결 설정")
        provider = st.session_state.email_provider
        if st.session_state.email_connected:
            st.success(f"✅ {provider.upper()} 연결됨")
        else:
            st.error(f"❌ {provider.upper()} 미연결")
            if st.button("이메일 연결"):
                status = get_email_provider_status(provider)
                st.session_state.email_connected = status.get('is_connected', False)
                st.rerun()
        
        st.markdown("---")
        st.header("🚀 빠른 액션")
        quick_actions = [
            ("안읽은 메일 3개 보여줘", "view"),
            ("오늘 처리할 티켓 목록", "process_tickets")
        ]
        for label, _ in quick_actions:
            if st.button(label, use_container_width=True, disabled=not st.session_state.email_connected):
                handle_query(label)

        if st.button("🗑️ 대화 초기화", use_container_width=True):
            init_session_state() # 모든 상태 초기화
            st.rerun()

    # 에이전트 초기화 (한 번만 실행)
    if st.session_state.main_agent is None:
        st.session_state.main_agent = create_main_agent()

    # --- 메인 페이지 ---
    
    # 1. 채팅 기록 표시
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(message.content)

    # 2. 최신 응답 데이터가 있으면 UI 컴포넌트 렌더링
    st.markdown("---")
    st.subheader("🔍 디버깅 정보")
    
    # 세션 상태 확인
    st.write("**세션 상태:**")
    st.write(f"- latest_response 존재: {st.session_state.get('latest_response') is not None}")
    st.write(f"- messages 개수: {len(st.session_state.get('messages', []))}")
    
    if response_data := st.session_state.get('latest_response'):
        display_mode = response_data.get('display_mode')
        ui_mode = response_data.get('ui_mode', 'text_only')
        
        st.success(f"✅ 응답 데이터 발견: display_mode={display_mode}, ui_mode={ui_mode}")
        st.json(response_data)
        
        if display_mode == 'tickets':
            if ui_mode == 'button_list':
                display_ticket_list_with_sidebar(response_data, "요청하신 티켓 목록")
            else:
                # 텍스트 형태로 간단히 표시
                tickets = response_data.get('tickets', [])
                if tickets:
                    st.subheader("📋 티켓 요약")
                    for i, ticket in enumerate(tickets, 1):
                        st.write(f"{i}. {ticket.get('title', '제목 없음')} - {ticket.get('status', '상태 불명')}")
                else:
                    st.info("표시할 티켓이 없습니다.")
                    
        elif display_mode == 'mail_list':
            if ui_mode == 'button_list':
                create_mail_list_with_sidebar(response_data.get('mail_list', []), "요청하신 메일 목록")
            else:
                create_mail_list_ui(response_data.get('mail_list', []), "요청하신 메일 목록")
                
        elif display_mode in ['no_emails', 'error']:
            st.info(response_data.get('message', '알 수 없는 응답입니다.'))
    else:
        st.info("🔍 디버깅: latest_response가 없습니다.")

    # 3. 사용자 입력 처리
    if prompt := st.chat_input("메일에 대해 무엇이든 물어보세요..."):
        if st.session_state.email_connected:
            handle_query(prompt)
        else:
            st.warning("먼저 사이드바에서 이메일 연결을 해주세요.")

if __name__ == "__main__":
    main()