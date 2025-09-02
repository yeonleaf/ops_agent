#!/usr/bin/env python3
"""
티켓 워크플로우 LangChain 툴들
메일 → 티켓 생성 → 임베딩 → 조회의 전체 프로세스
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain.tools import tool
from simple_mail_processor import SimpleMailProcessor
from database_models import DatabaseManager, MailParser, Mail, Ticket
from vector_db_models import VectorDBManager

# 전역 인스턴스들
mail_processor = SimpleMailProcessor()
db_manager = DatabaseManager()
mail_parser = MailParser()
vector_manager = VectorDBManager()

@tool
def get_todays_unread_emails() -> str:
    """
    오늘 처리해야 할 안읽은 메일 목록을 조회합니다.
    
    Returns:
        오늘의 안읽은 메일 목록 (JSON 형태의 문자열)
    """
    try:
        # JSON 파일에서 안읽은 메일 조회
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
        
        unread_emails = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        for mail_item in mail_data.get("value", []):
            if not mail_item.get("isRead", True):  # 안읽은 메일만
                # 오늘 날짜 필터 (실제로는 받은 날짜 확인, 여기서는 모든 안읽은 메일)
                email_info = {
                    "id": mail_item.get("id", ""),
                    "subject": mail_item.get("subject", "제목 없음"),
                    "sender_name": mail_item.get("from", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "sender_email": mail_item.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "received_time": mail_item.get("receivedDateTime", ""),
                    "body_preview": mail_item.get("bodyPreview", "")[:100],
                    "has_attachments": mail_item.get("hasAttachments", False),
                    "importance": mail_item.get("importance", "normal")
                }
                unread_emails.append(email_info)
        
        result = {
            "count": len(unread_emails),
            "emails": unread_emails[:10],  # 최대 10개만
            "message": f"오늘 처리해야 할 안읽은 메일 {len(unread_emails)}개를 찾았습니다."
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 메일 조회 중 오류 발생: {str(e)}"

@tool
def check_ticket_exists(message_id: str) -> str:
    """
    특정 메일 ID에 대한 티켓이 이미 존재하는지 확인합니다.
    
    Args:
        message_id: 확인할 메일 ID
    
    Returns:
        티켓 존재 여부와 정보
    """
    try:
        existing_tickets = db_manager.get_tickets_by_message_id(message_id)
        
        if existing_tickets:
            ticket = existing_tickets[0]  # 첫 번째 티켓
            result = {
                "exists": True,
                "ticket_id": ticket.ticket_id,
                "status": ticket.status,
                "title": ticket.title,
                "priority": ticket.priority,
                "created_at": ticket.created_at,
                "updated_at": ticket.updated_at
            }
        else:
            result = {
                "exists": False,
                "message": "해당 메일에 대한 티켓이 존재하지 않습니다."
            }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 티켓 확인 중 오류 발생: {str(e)}"

@tool
def create_ticket_from_email(message_id: str) -> str:
    """
    특정 메일로부터 티켓을 생성하고 RDB에 저장합니다.
    
    Args:
        message_id: 티켓을 생성할 메일 ID
    
    Returns:
        생성된 티켓 정보
    """
    try:
        # 메일 데이터 찾기
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
        
        target_mail = None
        for mail_item in mail_data.get("value", []):
            if mail_item.get("id") == message_id:
                target_mail = mail_item
                break
        
        if not target_mail:
            return f"❌ 메일 ID '{message_id}'를 찾을 수 없습니다."
        
        # 이미 티켓이 있는지 확인
        existing_tickets = db_manager.get_tickets_by_message_id(message_id)
        if existing_tickets:
            ticket = existing_tickets[0]
            return f"✅ 이미 티켓이 존재합니다 (ID: {ticket.ticket_id}, 제목: {ticket.title})"
        
        # 메일 파싱
        mail = mail_parser.parse_mail_to_json(target_mail)
        
        # 티켓 생성
        ticket = mail_parser.create_ticket_from_mail(mail)
        
        # 저장
        result = mail_parser.save_mail_and_ticket(mail, ticket)
        
        ticket_info = {
            "ticket_id": result['ticket_id'],
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "reporter": ticket.reporter,
            "created_at": ticket.created_at,
            "message": "티켓이 성공적으로 생성되었습니다."
        }
        
        return json.dumps(ticket_info, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 티켓 생성 중 오류 발생: {str(e)}"

@tool
def add_mail_to_vector_db(message_id: str) -> str:
    """
    메일을 벡터 데이터베이스에 임베딩하여 저장합니다.
    
    Args:
        message_id: 임베딩할 메일 ID
    
    Returns:
        임베딩 저장 결과
    """
    try:
        # 메일 데이터 찾기
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
        
        target_mail = None
        for mail_item in mail_data.get("value", []):
            if mail_item.get("id") == message_id:
                target_mail = mail_item
                break
        
        if not target_mail:
            return f"❌ 메일 ID '{message_id}'를 찾을 수 없습니다."
        
        # 이미 벡터 DB에 있는지 확인
        try:
            existing = vector_manager.get_mail_by_id(message_id)
            if existing:
                return f"✅ 이미 벡터 DB에 저장되어 있습니다 (ID: {message_id})"
        except:
            pass  # 없으면 계속 진행
        
        # 메일 객체 생성
        sender_info = target_mail.get("from", {}).get("emailAddress", {})
        
        # HTML 내용 정리
        body_content = target_mail.get("body", {}).get("content", "")
        if target_mail.get("body", {}).get("contentType") == "html":
            clean_content = re.sub('<.*?>', '', body_content)
            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        else:
            clean_content = body_content
        
        # 핵심 포인트 추출 (간단한 방식)
        key_points = []
        content_lower = clean_content.lower()
        if "meeting" in content_lower or "회의" in content_lower:
            key_points.append("회의 관련")
        if "urgent" in content_lower or "급한" in content_lower or "긴급" in content_lower:
            key_points.append("긴급")
        if "task" in content_lower or "작업" in content_lower:
            key_points.append("작업 요청")
        
        mail = Mail(
            message_id=message_id,
            original_content=body_content,
            refined_content=clean_content[:500],  # 처음 500자
            sender=sender_info.get("name", "알 수 없음"),
            status="acceptable",  # 기본값
            subject=target_mail.get("subject", "제목 없음"),
            received_datetime=target_mail.get("receivedDateTime", ""),
            content_type=target_mail.get("body", {}).get("contentType", "text"),
            has_attachment=target_mail.get("hasAttachments", False),
            extraction_method="automatic",
            content_summary=clean_content[:200] + "..." if len(clean_content) > 200 else clean_content,
            key_points=key_points,
            created_at=datetime.now().isoformat()
        )
        
        # 벡터 DB에 저장
        vector_manager.add_mail(mail)
        
        result = {
            "message_id": message_id,
            "subject": mail.subject,
            "sender": mail.sender,
            "key_points": key_points,
            "message": "메일이 벡터 DB에 성공적으로 저장되었습니다."
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 벡터 DB 저장 중 오류 발생: {str(e)}"

@tool
def get_existing_tickets_by_status(status: str = "new") -> str:
    """
    특정 상태의 기존 티켓들을 조회합니다.
    
    Args:
        status: 조회할 티켓 상태 (new, in_progress, resolved, closed)
    
    Returns:
        해당 상태의 티켓 목록
    """
    try:
        all_tickets = db_manager.get_all_tickets()
        filtered_tickets = [t for t in all_tickets if t.status == status]
        
        ticket_list = []
        for ticket in filtered_tickets[:10]:  # 최대 10개
            ticket_info = {
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "status": ticket.status,
                "priority": ticket.priority,
                "reporter": ticket.reporter,
                "created_at": ticket.created_at,
                "updated_at": ticket.updated_at,
                "description": ticket.description[:100] + "..." if len(ticket.description) > 100 else ticket.description
            }
            ticket_list.append(ticket_info)
        
        result = {
            "status": status,
            "count": len(ticket_list),
            "tickets": ticket_list,
            "message": f"상태가 '{status}'인 티켓 {len(ticket_list)}개를 찾았습니다."
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 티켓 조회 중 오류 발생: {str(e)}"

@tool
def process_todays_tasks() -> str:
    """
    오늘 처리해야 할 모든 작업을 처리합니다.
    1. 안읽은 메일 조회
    2. 티켓이 없는 메일은 티켓 생성 + 벡터 DB 저장
    3. 기존 티켓과 새 티켓을 모두 포함한 리스트 반환
    
    Returns:
        오늘 처리해야 할 전체 티켓 리스트
    """
    try:
        # 1. 안읽은 메일 조회
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
        
        unread_emails = [mail for mail in mail_data.get("value", []) if not mail.get("isRead", True)]
        
        processed_results = []
        new_tickets_created = 0
        existing_tickets_found = 0
        
        # 2. 각 안읽은 메일에 대해 처리
        for mail_item in unread_emails[:5]:  # 처리량 제한 (최대 5개)
            message_id = mail_item.get("id", "")
            subject = mail_item.get("subject", "제목 없음")
            
            # 기존 티켓 확인
            existing_tickets = db_manager.get_tickets_by_message_id(message_id)
            
            if existing_tickets:
                # 기존 티켓이 있는 경우
                ticket = existing_tickets[0]
                existing_tickets_found += 1
                processed_results.append({
                    "type": "existing_ticket",
                    "ticket_id": ticket.ticket_id,
                    "message_id": message_id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "created_at": ticket.created_at,
                    "action": "조회됨"
                })
            else:
                # 새 티켓 생성 필요
                try:
                    # 메일 파싱
                    mail = mail_parser.parse_mail_to_json(mail_item)
                    
                    # 티켓 생성
                    ticket = mail_parser.create_ticket_from_mail(mail)
                    
                    # RDB에 저장
                    result = mail_parser.save_mail_and_ticket(mail, ticket)
                    
                    # 벡터 DB에도 저장 시도
                    try:
                        # 메일 객체 생성하여 벡터 DB에 저장
                        sender_info = mail_item.get("from", {}).get("emailAddress", {})
                        body_content = mail_item.get("body", {}).get("content", "")
                        
                        if mail_item.get("body", {}).get("contentType") == "html":
                            clean_content = re.sub('<.*?>', '', body_content)
                            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                        else:
                            clean_content = body_content
                        
                        # 핵심 포인트 추출
                        key_points = []
                        content_lower = clean_content.lower()
                        if "meeting" in content_lower or "회의" in content_lower:
                            key_points.append("회의 관련")
                        if "urgent" in content_lower or "급한" in content_lower:
                            key_points.append("긴급")
                        if "task" in content_lower or "작업" in content_lower:
                            key_points.append("작업 요청")
                        
                        vector_mail = Mail(
                            message_id=message_id,
                            original_content=body_content,
                            refined_content=clean_content[:500],
                            sender=sender_info.get("name", "알 수 없음"),
                            status="acceptable",
                            subject=subject,
                            received_datetime=mail_item.get("receivedDateTime", ""),
                            content_type=mail_item.get("body", {}).get("contentType", "text"),
                            has_attachment=mail_item.get("hasAttachments", False),
                            extraction_method="automatic",
                            content_summary=clean_content[:200] + "..." if len(clean_content) > 200 else clean_content,
                            key_points=key_points,
                            created_at=datetime.now().isoformat()
                        )
                        
                        vector_manager.add_mail(vector_mail)
                        vector_saved = True
                    except:
                        vector_saved = False
                    
                    new_tickets_created += 1
                    processed_results.append({
                        "type": "new_ticket",
                        "ticket_id": result['ticket_id'],
                        "message_id": message_id,
                        "title": ticket.title,
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "created_at": ticket.created_at,
                        "action": "생성됨",
                        "vector_saved": vector_saved
                    })
                    
                except Exception as e:
                    processed_results.append({
                        "type": "error",
                        "message_id": message_id,
                        "subject": subject,
                        "error": str(e),
                        "action": "실패"
                    })
        
        # 3. 기존의 처리 중인 티켓들도 추가
        existing_active_tickets = db_manager.get_all_tickets()
        # pending, approved, rejected 상태의 모든 티켓 포함 (new 상태 제거)
        today_tickets = [t for t in existing_active_tickets if t.status in ["pending", "approved", "rejected"]]
        
        # 기존 티켓들을 더 많이 포함하고, 레이블 정보도 추가
        for ticket in today_tickets[:15]:  # 최대 15개로 증가
            # 이미 처리한 티켓이 아닌 경우만 추가
            if not any(r.get("ticket_id") == ticket.ticket_id for r in processed_results):
                processed_results.append({
                    "type": "existing_active_ticket",
                    "ticket_id": ticket.ticket_id,
                    "message_id": ticket.original_message_id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "labels": ticket.labels,  # 레이블 정보 추가
                    "created_at": ticket.created_at,
                    "action": "기존 활성"
                })
        
        # 결과 정리
        final_result = {
            "summary": {
                "total_unread_emails": len(unread_emails),
                "new_tickets_created": new_tickets_created,
                "existing_tickets_found": existing_tickets_found,
                "total_tasks": len(processed_results)
            },
            "tasks": processed_results,
            "message": f"오늘 처리해야 할 작업 {len(processed_results)}개가 준비되었습니다."
        }
        
        return json.dumps(final_result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"❌ 작업 처리 중 오류 발생: {str(e)}"

# 사용 가능한 모든 툴 목록
TICKET_WORKFLOW_TOOLS = [
    get_todays_unread_emails,
    check_ticket_exists,
    create_ticket_from_email,
    add_mail_to_vector_db,
    get_existing_tickets_by_status,
    process_todays_tasks
]

def get_workflow_tools_description() -> str:
    """워크플로우 툴들의 설명을 반환"""
    return """
티켓 워크플로우 툴들:

1. **get_todays_unread_emails()**: 오늘의 안읽은 메일 목록 조회
2. **check_ticket_exists(message_id)**: 특정 메일의 티켓 존재 여부 확인
3. **create_ticket_from_email(message_id)**: 메일로부터 티켓 생성
4. **add_mail_to_vector_db(message_id)**: 메일을 벡터 DB에 임베딩 저장
5. **get_existing_tickets_by_status(status)**: 특정 상태의 기존 티켓 조회
6. **process_todays_tasks()**: 오늘 처리해야 할 모든 작업 통합 처리

주요 워크플로우:
- "오늘 처리할 작업 보여줘" → process_todays_tasks() 호출
- 안읽은 메일 → 티켓 없으면 생성 → 벡터 DB 저장 → 리스트 반환
"""

if __name__ == "__main__":
    # 테스트
    print("=== 티켓 워크플로우 툴 테스트 ===")
    
    # 1. 안읽은 메일 조회 테스트
    print("\n1. 안읽은 메일 조회:")
    current_result = ""
    for chunk in get_todays_unread_emails.stream({}):
        current_result += chunk
    print(current_result[:200] + "..." if len(current_result) > 200 else current_result)
    
    # 2. 전체 워크플로우 테스트
    print("\n2. 전체 워크플로우 테스트:")
    current_result = ""
    for chunk in process_todays_tasks.stream({}):
        current_result += chunk
    print(current_result[:300] + "..." if len(current_result) > 300 else current_result)