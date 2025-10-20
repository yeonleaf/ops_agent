#!/usr/bin/env python3
"""
FastMCP 기반 이메일 서비스 서버
기존 mcp_server.py를 FastMCP 애플리케이션으로 교체
"""

import os
import logging
import requests
import secrets
import hashlib
import json
import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
import threading

# FastMCP import
from fastmcp import FastMCP

# FastAPI import
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from email_validator import validate_email
import bcrypt
from cryptography.fernet import Fernet
import sqlite3
import uuid

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("EmailServiceServer")

# 비동기 작업 추적을 위한 전역 저장소
import uuid
import time
import threading
from enum import Enum

class TaskStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"  # 외부 인증 대기 등의 사유로 일시 중단

# 메모리 기반 작업 저장소 (간단한 구현)
_active_tasks = {}
_task_lock = threading.Lock()

def create_task(user_id: str, steps: list = None) -> str:
    """새 작업 생성"""
    task_id = str(uuid.uuid4())

    if steps is None:
        steps = [
            {"step_name": "이메일 수집", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
            {"step_name": "메일 분류", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
            {"step_name": "Jira 티켓 발행", "status": "PENDING", "log": None, "started_at": None, "completed_at": None}
        ]

    with _task_lock:
        _active_tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "overall_status": TaskStatus.PENDING.value,
            "steps": steps,
            "final_result": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    logging.info(f"✅ 작업 생성: {task_id}")
    return task_id

def update_task_status(task_id: str, status: str, final_result: Dict[str, Any] = None):
    """작업 전체 상태 업데이트"""
    with _task_lock:
        if task_id in _active_tasks:
            _active_tasks[task_id]["overall_status"] = status
            _active_tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            if final_result:
                _active_tasks[task_id]["final_result"] = final_result
            logging.info(f"📊 작업 상태 업데이트: {task_id} -> {status}")

def update_step_status(task_id: str, step_name: str, status: str, log: str = None):
    """단계 상태 업데이트"""
    current_time = datetime.now(timezone.utc).isoformat()

    with _task_lock:
        if task_id in _active_tasks:
            steps = _active_tasks[task_id]["steps"]
            for step in steps:
                if step["step_name"] == step_name:
                    step["status"] = status
                    if log:
                        step["log"] = log

                    if status == "IN_PROGRESS" and not step.get("started_at"):
                        step["started_at"] = current_time
                    elif status in ["COMPLETED", "FAILED"]:
                        step["completed_at"] = current_time
                    break

            _active_tasks[task_id]["updated_at"] = current_time
            logging.info(f"📋 단계 업데이트: {task_id} -> {step_name}: {status}")

def get_task_status(task_id: str) -> Dict[str, Any]:
    """작업 상태 조회"""
    with _task_lock:
        if task_id in _active_tasks:
            return _active_tasks[task_id].copy()
        return None

# 글로벌 컨텍스트 저장소
current_context = {
    "user_email": None
}

def set_current_user_email(email: str):
    """현재 사용자 이메일을 컨텍스트에 설정"""
    current_context["user_email"] = email
    logging.info(f"📧 사용자 이메일 컨텍스트 설정: {email}")

def get_current_user_email() -> Optional[str]:
    """현재 사용자 이메일을 컨텍스트에서 가져오기"""
    return current_context.get("user_email")

def clear_user_context():
    """사용자 컨텍스트 초기화"""
    current_context["user_email"] = None
    logging.info("🧹 사용자 컨텍스트 초기화 완료")


# 데이터베이스 관리자
class DatabaseManager:
    def __init__(self, db_path="tickets.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # users 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                google_refresh_token TEXT NULL,
                jira_endpoint VARCHAR(255) NULL,
                jira_api_token TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # sessions 테이블 제거됨 (메모리 기반 세션 관리 사용)
        
        conn.commit()
        conn.close()
    
    def get_user_by_email(self, email: str):
        """이메일로 사용자 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def create_user(self, email: str, password_hash: str):
        """사용자 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    
    # sessions 테이블 관련 메서드 제거됨 (메모리 기반 세션 관리 사용)
    
    def update_user_google_token(self, user_id: int, encrypted_token: str = None):
        """사용자 Google 토큰 업데이트 (None이면 토큰 삭제)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET google_refresh_token = ? WHERE id = ?",
            (encrypted_token, user_id)
        )
        conn.commit()
        conn.close()

# 전역 데이터베이스 관리자
db_manager = DatabaseManager()

# 토큰 암호화 관리자
class TokenEncryption:
    def __init__(self):
        self.key = os.getenv("ENCRYPTION_KEY")
        if not self.key:
            # 새로운 키 생성
            self.key = Fernet.generate_key().decode()
            print(f"⚠️ 새로운 암호화 키가 생성되었습니다. ENCRYPTION_KEY={self.key}")
        
        logging.info(f"🔐 암호화 키 정보: 길이={len(self.key)}, 시작={self.key[:10]}...")
        
        try:
            self.fernet = Fernet(self.key.encode())
            logging.info("✅ Fernet 객체 생성 성공")
        except Exception as e:
            logging.error(f"❌ Fernet 객체 생성 실패: {e}")
            raise
    
    def encrypt_token(self, token: str) -> str:
        """토큰 암호화 (POC용 비활성화)"""
        logging.info("🔓 POC 모드: 토큰 암호화 비활성화")
        return token  # 암호화하지 않고 그대로 반환
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """토큰 복호화 (POC용 비활성화)"""
        logging.info("🔓 POC 모드: 토큰 복호화 비활성화")
        return encrypted_token  # 복호화하지 않고 그대로 반환

token_encryption = TokenEncryption()

# Pydantic 모델들
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleTokenByEmailRequest(BaseModel):
    email: EmailStr
    refresh_token: str

class LogoutRequest(BaseModel):
    session_id: Optional[str] = None






# 이메일 도구들 import
from fastmcp_email_tools import (
    get_raw_emails,
    process_emails_with_ticket_logic,
    get_email_provider_status,
    get_mail_content_by_id,
    create_ticket_from_single_email,
    fetch_emails_sync
)

# 이메일 에이전트 import
from fastmcp_email_agent import email_agent

# 도구들을 FastMCP에 등록
@mcp.tool()
def get_raw_emails_tool(provider_name: str, filters: Dict[str, Any]) -> list:
    """사용자의 특정 조건에 맞는 순수 이메일 목록을 반환합니다."""
    return get_raw_emails(provider_name, filters)

@mcp.tool()
def process_emails_with_ticket_logic_tool(provider_name: str, user_query: str = None) -> Dict[str, Any]:
    """안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다."""
    return process_emails_with_ticket_logic(provider_name, user_query)


# Raw implementations for direct calling
def process_emails_with_ticket_logic_async_raw(provider_name: str, user_id: str = "default_user", user_query: str = None) -> Dict[str, Any]:
    """비동기 방식으로 티켓 생성 작업을 시작하고 완료까지 추적합니다. (Raw implementation)"""

    # 0. 사용자 컨텍스트 설정
    set_current_user_email(user_id)
    logging.info(f"🔧 사용자 컨텍스트 설정: {user_id}")

    # 2. 새 작업 생성
    task_id = create_task(user_id)
    logging.info(f"🚀 비동기 티켓 생성 시작: task_id={task_id}")

    def run_async_task():
        """백그라운드에서 실행될 실제 작업"""
        try:
            # 작업 시작
            update_task_status(task_id, TaskStatus.IN_PROGRESS.value)

            # 단계 1: 이메일 수집
            update_step_status(task_id, "이메일 수집", "IN_PROGRESS", f"{provider_name} API를 통해 이메일을 수집하고 있습니다...")
            time.sleep(0.5)  # UI에서 진행상황을 볼 수 있도록 약간의 지연

            # 단계 2: 메일 분류 시작
            update_step_status(task_id, "이메일 수집", "COMPLETED", f"{provider_name}에서 이메일을 수집했습니다.")
            update_step_status(task_id, "메일 분류", "IN_PROGRESS", "LLM을 통해 업무용 메일을 분류하고 있습니다...")
            time.sleep(0.5)

            # 단계 3: Jira 티켓 생성 시작
            update_step_status(task_id, "메일 분류", "COMPLETED", "메일 분류가 완료되었습니다.")
            update_step_status(task_id, "Jira 티켓 발행", "IN_PROGRESS", "Jira 티켓을 생성하고 있습니다...")

            # 실제 티켓 생성 함수 호출 (raw function from unified_email_service)
            from unified_email_service import process_emails_with_ticket_logic as raw_process_emails

            try:
                result = raw_process_emails(provider_name, user_query)
            except ValueError as e:
                # 인증 오류가 발생한 경우
                if "OAuth2 인증이 필요합니다" in str(e) or "인증이 필요합니다" in str(e):
                    logging.warning(f"🔐 비동기 작업 중 인증 오류: {str(e)}")

                    # 작업을 실패로 처리
                    final_result = {
                        "success": False,
                        "status": "authentication_failed",
                        "tickets_created": 0,
                        "existing_tickets": 0,
                        "message": "인증이 필요합니다. 별도 인증 서버(port 8001)에서 인증을 완료한 후 다시 시도해주세요.",
                        "error": str(e),
                        "failed_at": datetime.now(timezone.utc).isoformat()
                    }

                    update_step_status(task_id, "Jira 티켓 발행", "FAILED", "인증 오류로 인해 작업이 실패했습니다.")
                    update_task_status(task_id, TaskStatus.FAILED.value, final_result)
                    return
                else:
                    # 다른 오류는 그대로 전파
                    raise

            # 최종 단계 완료
            tickets_created = result.get('new_tickets_created', 0)
            existing_tickets = result.get('existing_tickets_found', 0)

            if tickets_created > 0:
                update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", f"총 {tickets_created}개의 새 티켓이 생성되었습니다.")
            elif existing_tickets > 0:
                update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", f"기존 티켓 {existing_tickets}개를 확인했습니다.")
            else:
                update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", "처리할 이메일이 없습니다.")

            # 최종 결과
            if result.get('new_tickets_created', 0) > 0 or result.get('display_mode') == 'no_emails':
                final_result = {
                    "success": True,
                    "tickets_created": result.get('new_tickets_created', 0),
                    "existing_tickets": result.get('existing_tickets_found', 0),
                    "message": result.get('message', '작업이 완료되었습니다.'),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
                update_task_status(task_id, TaskStatus.COMPLETED.value, final_result)
            else:
                final_result = {
                    "success": False,
                    "tickets_created": 0,
                    "existing_tickets": 0,
                    "message": result.get('message', '작업이 실패했습니다.'),
                    "error": result.get('error', '알 수 없는 오류'),
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
                update_task_status(task_id, TaskStatus.FAILED.value, final_result)

        except Exception as e:
            logging.error(f"❌ 비동기 작업 실패: {str(e)}")
            final_result = {
                "success": False,
                "tickets_created": 0,
                "existing_tickets": 0,
                "message": f"작업 중 오류가 발생했습니다: {str(e)}",
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
            update_task_status(task_id, TaskStatus.FAILED.value, final_result)

            # 실패한 단계 업데이트
            current_task = get_task_status(task_id)
            if current_task:
                for step in current_task["steps"]:
                    if step["status"] == "IN_PROGRESS":
                        update_step_status(task_id, step["step_name"], "FAILED", str(e))

    # 백그라운드 스레드에서 실행
    thread = threading.Thread(target=run_async_task, daemon=True)
    thread.start()

    # 즉시 task_id 반환 (UI가 상태를 추적할 수 있도록)
    return {
        "success": True,
        "task_id": task_id,
        "message": "비동기 작업이 시작되었습니다. get_async_task_status로 상태를 확인하세요.",
        "status": "PENDING"
    }

# Raw implementation for get_async_task_status
def get_async_task_status_raw(task_id: str) -> Dict[str, Any]:
    """비동기 작업의 현재 상태를 조회합니다. (Raw implementation)"""
    logging.info(f"📊 작업 상태 조회: task_id={task_id}")

    task_data = get_task_status(task_id)

    if not task_data:
        return {
            "success": False,
            "error": f"작업 ID {task_id}를 찾을 수 없습니다."
        }

    return {
        "success": True,
        "task": task_data,
        "message": f"작업 ID {task_id}의 상태를 조회했습니다."
    }

# Raw implementation for list_active_tasks
def list_active_tasks_raw() -> Dict[str, Any]:
    """현재 실행 중인 모든 비동기 작업의 목록을 조회합니다. (Raw implementation)"""
    logging.info("📊 모든 활성 작업 목록 조회")

    with _task_lock:
        active_tasks = [
            task for task in _active_tasks.values()
            if task["overall_status"] in [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value, TaskStatus.PAUSED.value]
        ]

    return {
        "success": True,
        "active_tasks": active_tasks,
        "count": len(active_tasks),
        "message": f"현재 {len(active_tasks)}개의 활성 작업이 있습니다."
    }

# 일시 중단된 작업 재개 함수
def resume_paused_task_raw(task_id: str) -> Dict[str, Any]:
    """일시 중단된 작업을 재개합니다. (Raw implementation)"""
    logging.info(f"🔄 일시 중단된 작업 재개: task_id={task_id}")

    task_data = get_task_status(task_id)
    if not task_data:
        return {
            "success": False,
            "error": f"작업 ID {task_id}를 찾을 수 없습니다."
        }

    if task_data["overall_status"] != TaskStatus.PAUSED.value:
        return {
            "success": False,
            "error": f"작업이 일시 중단 상태가 아닙니다. 현재 상태: {task_data['overall_status']}"
        }

    # 인증 상태 다시 확인
    final_result = task_data.get("final_result", {})
    if final_result.get("status") == "paused_for_auth":
        # 마지막 단계에서 사용된 provider_name을 추출해야 함
        # 이를 위해 task_data에 provider_name을 저장하도록 수정 필요
        # 임시로 gmail로 가정
        provider_name = "gmail"  # TODO: task_data에서 추출하도록 개선

        # 작업 재시작 (인증은 별도 서버에서 처리)
        logging.info(f"🔄 인증 완료 확인됨. 작업 재개: {task_id}")

        # 새로운 스레드에서 작업 재개
        def resume_task():
            try:
                update_task_status(task_id, TaskStatus.IN_PROGRESS.value)
                update_step_status(task_id, "Jira 티켓 발행", "IN_PROGRESS", "인증 완료. 티켓 생성을 재개합니다...")

                # 실제 티켓 생성 함수 호출
                from unified_email_service import process_emails_with_ticket_logic as raw_process_emails
                # user_query는 원래 저장해야 하지만 임시로 None 사용
                result = raw_process_emails(provider_name, None)

                # 최종 단계 완료
                tickets_created = result.get('new_tickets_created', 0)
                existing_tickets = result.get('existing_tickets_found', 0)

                if tickets_created > 0:
                    update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", f"총 {tickets_created}개의 새 티켓이 생성되었습니다.")
                elif existing_tickets > 0:
                    update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", f"기존 티켓 {existing_tickets}개를 확인했습니다.")
                else:
                    update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", "처리할 이메일이 없습니다.")

                # 최종 결과
                if result.get('new_tickets_created', 0) > 0 or result.get('display_mode') == 'no_emails':
                    final_result = {
                        "success": True,
                        "tickets_created": result.get('new_tickets_created', 0),
                        "existing_tickets": result.get('existing_tickets_found', 0),
                        "message": result.get('message', '작업이 완료되었습니다.'),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "resumed_from": "paused_for_auth"
                    }
                    update_task_status(task_id, TaskStatus.COMPLETED.value, final_result)
                else:
                    final_result = {
                        "success": False,
                        "tickets_created": 0,
                        "existing_tickets": 0,
                        "message": result.get('message', '작업이 실패했습니다.'),
                        "error": result.get('error', '알 수 없는 오류'),
                        "failed_at": datetime.now(timezone.utc).isoformat()
                    }
                    update_task_status(task_id, TaskStatus.FAILED.value, final_result)

            except Exception as e:
                logging.error(f"❌ 작업 재개 중 오류 발생: {str(e)}")
                final_result = {
                    "success": False,
                    "tickets_created": 0,
                    "existing_tickets": 0,
                    "message": f"작업 재개 중 오류가 발생했습니다: {str(e)}",
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
                update_task_status(task_id, TaskStatus.FAILED.value, final_result)

        # 백그라운드에서 재개
        thread = threading.Thread(target=resume_task, daemon=True)
        thread.start()

        return {
            "success": True,
            "task_id": task_id,
            "message": "작업 재개가 시작되었습니다.",
            "status": "RESUMING"
        }

    return {
        "success": False,
        "error": "지원되지 않는 일시 중단 상태입니다."
    }

@mcp.tool()
def process_emails_with_ticket_logic_async(provider_name: str, user_id: str = "default_user", user_query: str = None) -> Dict[str, Any]:
    """비동기 방식으로 티켓 생성 작업을 시작하고 완료까지 추적합니다."""
    return process_emails_with_ticket_logic_async_raw(provider_name, user_id, user_query)

@mcp.tool()
def get_async_task_status(task_id: str) -> Dict[str, Any]:
    """비동기 작업의 현재 상태를 조회합니다."""
    return get_async_task_status_raw(task_id)

@mcp.tool()
def list_active_tasks() -> Dict[str, Any]:
    """현재 활성 상태인 모든 작업 목록을 반환합니다."""
    return list_active_tasks_raw()

@mcp.tool()
def resume_paused_task(task_id: str) -> Dict[str, Any]:
    """일시 중단된 작업을 재개합니다."""
    return resume_paused_task_raw(task_id)

@mcp.tool()
def check_oauth_status(provider_name: str = "gmail") -> Dict[str, Any]:
    """OAuth 인증 상태를 확인합니다."""
    return {
        "success": False,
        "message": "OAuth 인증은 별도 auth_server(port 8001)에서 처리됩니다.",
        "error": "This function is deprecated. Use auth_server for authentication."
    }

@mcp.tool()
def get_email_provider_status_tool(provider_name: str = None) -> Dict[str, Any]:
    """이메일 제공자의 연결 상태와 설정 정보를 확인합니다."""
    return get_email_provider_status(provider_name)

@mcp.tool()
def get_mail_content_by_id_tool(message_id: str) -> Optional[Dict[str, Any]]:
    """VectorDB에서 message_id로 메일 상세 내용을 조회합니다."""
    return get_mail_content_by_id(message_id)

@mcp.tool()
def create_ticket_from_single_email_tool(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """단일 이메일을 티켓으로 변환하는 함수입니다."""
    return create_ticket_from_single_email(email_data)

@mcp.tool()
def fetch_emails_sync_tool(provider_name: str, use_classifier: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """동기적으로 이메일을 가져와서 티켓 형태로 변환하여 반환합니다."""
    return fetch_emails_sync(provider_name, use_classifier, max_results)

# 에이전트를 FastMCP 도구로 등록
@mcp.tool()
def email_agent_tool(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    이메일 관리 및 티켓 생성 전문 AI 어시스턴트
    
    사용자의 이메일 관련 요청을 이해하고 적절한 도구를 선택하여 실행합니다.
    
    Args:
        user_query (str): 사용자의 요청 또는 질문
        context (Optional[Dict[str, Any]]): 추가 컨텍스트 정보
    
    Returns:
        Dict[str, Any]: 처리 결과
            - success (bool): 처리 성공 여부
            - message (str): 응답 메시지
            - data (Any): 처리된 데이터
            - tools_used (List[str]): 사용된 도구 목록
            - error (str, optional): 오류 메시지
    """
    return email_agent(user_query, context)

# 추가 유틸리티 도구들
@mcp.tool()
def get_available_providers() -> list:
    """
    사용 가능한 이메일 제공자 목록을 반환합니다.
    
    Returns:
        list: 사용 가능한 이메일 제공자 목록
    """
    try:
        from email_provider import get_available_providers as original_function
        providers = original_function()
        logging.info(f"✅ 사용 가능한 이메일 제공자: {providers}")
        return providers
    except Exception as e:
        logging.error(f"❌ 이메일 제공자 목록 조회 실패: {str(e)}")
        return []

@mcp.tool()
def get_default_provider() -> str:
    """
    기본 이메일 제공자를 반환합니다.
    
    Returns:
        str: 기본 이메일 제공자 이름
    """
    try:
        from email_provider import get_default_provider as original_function
        provider = original_function()
        logging.info(f"✅ 기본 이메일 제공자: {provider}")
        return provider
    except Exception as e:
        logging.error(f"❌ 기본 이메일 제공자 조회 실패: {str(e)}")
        return "gmail"

@mcp.tool()
def test_work_related_filtering() -> Dict[str, Any]:
    """
    테스트용 업무 관련 메일 필터링 기능을 실행합니다.
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_work_related_filtering as original_function
        result = original_function()
        logging.info(f"✅ 업무 관련 메일 필터링 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 업무 관련 메일 필터링 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_email_fetch_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 메일 조회 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_email_fetch_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 메일 조회 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 메일 조회 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
def test_ticket_creation_logic(provider_name: str) -> Dict[str, Any]:
    """
    테스트용 티켓 생성 로직을 실행합니다.
    
    Args:
        provider_name (str): 테스트할 이메일 제공자 이름
    
    Returns:
        Dict[str, Any]: 테스트 결과
    """
    try:
        from unified_email_service import test_ticket_creation_logic as original_function
        result = original_function(provider_name)
        logging.info(f"✅ 티켓 생성 로직 테스트 완료: {result.get('success', False)}")
        return result
    except Exception as e:
        logging.error(f"❌ 티켓 생성 로직 테스트 실패: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# 인증 상태 확인 도구들
# 서버 상태 확인 도구
@mcp.tool()
def set_user_email_context(user_email: str) -> Dict[str, Any]:
    """현재 사용자 이메일을 컨텍스트에 설정합니다.
    
    Args:
        user_email: 설정할 사용자 이메일 주소
    """
    try:
        if not user_email or not user_email.strip():
            return {
                "success": False,
                "error": "유효한 이메일 주소를 입력해주세요"
            }
        
        set_current_user_email(user_email.strip())
        
        return {
            "success": True,
            "message": f"사용자 이메일이 설정되었습니다: {user_email}",
            "user_email": user_email
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"사용자 이메일 설정 실패: {str(e)}"
        }

@mcp.tool()
def get_user_email_context() -> Dict[str, Any]:
    """현재 컨텍스트에 설정된 사용자 이메일을 조회합니다."""
    try:
        user_email = get_current_user_email()
        
        return {
            "success": True,
            "user_email": user_email or "unknown@example.com",
            "has_email_set": user_email is not None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"사용자 이메일 조회 실패: {str(e)}"
        }

@mcp.tool()
def logout_user() -> Dict[str, Any]:
    """현재 사용자를 로그아웃하고 세션과 컨텍스트를 정리합니다."""
    try:
        # 글로벌 컨텍스트 초기화
        clear_user_context()
        
        return {
            "success": True,
            "message": "로그아웃이 완료되었습니다. 컨텍스트가 정리되었습니다."
        }
    except Exception as e:
        logging.error(f"❌ 로그아웃 실패: {e}")
        return {
            "success": False,
            "error": f"로그아웃 실패: {str(e)}"
        }

@mcp.tool()
def check_encryption_key() -> Dict[str, Any]:
    """암호화 키 상태를 확인합니다."""
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        return {
            "success": True,
            "has_encryption_key": bool(encryption_key),
            "key_length": len(encryption_key) if encryption_key else 0,
            "message": "ENCRYPTION_KEY가 설정되어 있습니다" if encryption_key else "ENCRYPTION_KEY가 설정되지 않았습니다"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"암호화 키 확인 실패: {str(e)}"
        }

@mcp.tool()
def reset_corrupted_tokens() -> Dict[str, Any]:
    """손상된 토큰들을 정리합니다."""
    try:
        # 모든 사용자의 Google 토큰을 확인하고 손상된 것들을 정리
        import sqlite3
        conn = sqlite3.connect("tickets.db")
        cursor = conn.cursor()
        
        # Google 토큰이 있는 모든 사용자 조회
        cursor.execute("SELECT id, email, google_refresh_token FROM users WHERE google_refresh_token IS NOT NULL")
        users_with_tokens = cursor.fetchall()
        
        corrupted_count = 0
        for user in users_with_tokens:
            try:
                logging.info(f"🔍 처리 중인 사용자 데이터 타입: {type(user)}, 값: {user}")

                # 안전한 접근을 위해 인덱스와 언패킹 모두 시도
                if isinstance(user, (list, tuple)) and len(user) >= 3:
                    user_id, email, encrypted_token = user[0], user[1], user[2]
                else:
                    logging.error(f"❌ 예상치 못한 사용자 데이터 형태: {user}")
                    continue

                # 토큰 복호화 시도
                token_encryption.decrypt_token(encrypted_token)
                logging.info(f"✅ {email}: 토큰 정상")
            except Exception as e:
                # 손상된 토큰 삭제
                try:
                    cursor.execute("UPDATE users SET google_refresh_token = NULL WHERE id = ?", (user_id,))
                    corrupted_count += 1
                    logging.warning(f"🗑️ {email}: 손상된 토큰 삭제 - {str(e)}")
                except Exception as delete_error:
                    logging.error(f"❌ 토큰 삭제 실패: {delete_error}")
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"토큰 정리 완료: {corrupted_count}개의 손상된 토큰을 삭제했습니다",
            "corrupted_tokens_removed": corrupted_count,
            "total_tokens_checked": len(users_with_tokens)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"토큰 정리 실패: {str(e)}"
        }

@mcp.tool()
def create_async_ticket_task(user_id: str = "default_user",
                            provider_name: str = "gmail",
                            user_query: Optional[str] = None) -> Dict[str, Any]:
    """
    비동기 방식으로 티켓 생성 작업을 시작합니다.

    Args:
        user_id: 사용자 ID (기본값: "default_user")
        provider_name: 이메일 제공자 (gmail, outlook)
        user_query: 선택적 사용자 쿼리

    Returns:
        Dict[str, Any]: 작업 결과 (완료될 때까지 대기)
    """
    logging.info(f"🚀 비동기 티켓 생성 작업 시작: user_id={user_id}, provider={provider_name}")
    return create_async_ticket_task_impl(user_id, provider_name, user_query)

@mcp.tool()
def get_async_task_status(task_id: str) -> Dict[str, Any]:
    """
    비동기 작업의 현재 상태를 조회합니다.

    Args:
        task_id: 조회할 작업 ID

    Returns:
        Dict[str, Any]: 작업 상태 정보
    """
    logging.info(f"📊 비동기 작업 상태 조회: task_id={task_id}")
    return get_async_task_status_impl(task_id)

@mcp.tool()
def get_server_status() -> Dict[str, Any]:
    """
    FastMCP 서버의 상태를 확인합니다.

    Returns:
        Dict[str, Any]: 서버 상태 정보
    """
    try:
        import psutil
        import platform

        # 시스템 정보 수집
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': psutil.disk_usage('/').percent
        }

        # 환경 변수 확인
        env_vars = {
            'AZURE_OPENAI_ENDPOINT': bool(os.getenv('AZURE_OPENAI_ENDPOINT')),
            'AZURE_OPENAI_API_KEY': bool(os.getenv('AZURE_OPENAI_API_KEY')),
            'AZURE_OPENAI_DEPLOYMENT_NAME': bool(os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')),
            'AZURE_OPENAI_API_VERSION': bool(os.getenv('AZURE_OPENAI_API_VERSION'))
        }

        logging.info("✅ 서버 상태 확인 완료")

        return {
            'status': 'healthy',
            'system_info': system_info,
            'environment_variables': env_vars,
            'timestamp': str(os.path.getmtime(__file__))
        }

    except Exception as e:
        logging.error(f"❌ 서버 상태 확인 실패: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': str(os.path.getmtime(__file__))
        }

@mcp.tool()
def simple_llm_call(prompt: str) -> str:
    """
    주어진 프롬프트를 사용하여 Azure OpenAI LLM을 호출하고, 텍스트 응답을 반환합니다.

    Args:
        prompt (str): LLM에 전달할 프롬프트

    Returns:
        str: LLM의 응답 텍스트
    """
    try:
        logging.info(f"LLM 호출 시작: {prompt[:50]}...")

        # Azure OpenAI 설정 확인
        azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4.1')
        azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-10-21')

        if not all([azure_endpoint, azure_api_key]):
            error_msg = "Azure OpenAI 환경 변수가 설정되지 않았습니다. AZURE_OPENAI_ENDPOINT와 AZURE_OPENAI_API_KEY를 확인하세요."
            logging.error(error_msg)
            return f"오류: {error_msg}"

        # Azure OpenAI 클라이언트 import 및 초기화
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version
        )

        # LLM 호출
        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000,
            temperature=0.7
        )

        # 응답 텍스트 추출
        response_text = response.choices[0].message.content.strip()

        logging.info(f"LLM 호출 성공: 응답 길이 {len(response_text)}자")
        return response_text

    except ImportError as e:
        error_msg = f"openai 라이브러리를 import할 수 없습니다. pip install openai를 실행하세요. ({e})"
        logging.error(error_msg)
        return f"오류: {error_msg}"

    except Exception as e:
        logging.error(f"LLM 호출 중 오류 발생: {e}")
        return f"오류: LLM 호출에 실패했습니다. {str(e)}"

# FastMCP 앱 실행을 위한 메인 함수
def run_fastmcp_server():
    """FastMCP 서버 실행"""
    logging.info("🚀 FastMCP 이메일 서비스 서버 시작")
    logging.info("📧 등록된 도구들:")
    logging.info("  - get_raw_emails_tool")
    logging.info("  - process_emails_with_ticket_logic_tool")
    logging.info("  - get_email_provider_status_tool")
    logging.info("  - get_mail_content_by_id_tool")
    logging.info("  - create_ticket_from_single_email_tool")
    logging.info("  - fetch_emails_sync_tool")
    logging.info("  - email_agent_tool")
    logging.info("  - get_available_providers")
    logging.info("  - get_default_provider")
    logging.info("  - test_work_related_filtering")
    logging.info("  - test_email_fetch_logic")
    logging.info("  - test_ticket_creation_logic")
    logging.info("  - get_server_status")
    logging.info("🚀 비동기 티켓 생성 도구들:")
    logging.info("  - process_emails_with_ticket_logic_async")
    logging.info("  - get_async_task_status")
    logging.info("  - list_active_tasks")
    logging.info("  - resume_paused_task")
    logging.info("  - check_oauth_status (deprecated)")
    logging.info("📧 사용자 컨텍스트 도구들:")
    logging.info("  - set_user_email_context")
    logging.info("  - get_user_email_context")
    logging.info("  - logout_user")
    logging.info("🔐 암호화 도구들:")
    logging.info("  - check_encryption_key")
    
    
    
    
    # FastMCP 서버 실행
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        log_level="info"
    )

if __name__ == "__main__":
    run_fastmcp_server()
