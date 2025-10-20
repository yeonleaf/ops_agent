#!/usr/bin/env python3
"""
비동기 티켓 처리를 위한 백그라운드 작업 함수
"""

import asyncio
import logging
import threading
import traceback
from typing import Dict, Any
from datetime import datetime

from async_task_models import AsyncTaskManager
from unified_email_service import process_emails_with_ticket_logic

# 로깅 설정
logger = logging.getLogger(__name__)

class AsyncTicketProcessor:
    """비동기 티켓 처리기"""

    def __init__(self):
        self.task_manager = AsyncTaskManager()

    def process_emails_with_ticket_logic_async(self, task_id: str, provider_name: str, user_query: str = None,
                                               mem0_memory=None, access_token: str = None):
        """비동기로 티켓 생성 로직 실행"""

        def _background_worker():
            """백그라운드 워커 함수"""
            try:
                logger.info(f"🚀 비동기 티켓 생성 시작: task_id={task_id}")

                # 작업 전체 상태를 IN_PROGRESS로 변경
                self.task_manager.update_task_status(task_id, "IN_PROGRESS")

                # 단계 1: 이메일 수집
                logger.info("📧 단계 1: 이메일 수집 시작")
                self.task_manager.update_step_status(task_id, "이메일 수집", "IN_PROGRESS", "Gmail API를 통해 이메일을 수집하고 있습니다...")

                try:
                    # 원본 함수 호출 전 단계별 상태 추적을 위한 래퍼
                    result = self._process_with_progress_tracking(
                        task_id, provider_name, user_query, mem0_memory, access_token
                    )

                    if result and result.get('new_tickets_created', 0) > 0:
                        # 성공적으로 완료
                        logger.info(f"✅ 티켓 생성 완료: {result.get('new_tickets_created')}개 생성")

                        # 최종 결과 저장
                        final_result = {
                            "success": True,
                            "tickets_created": result.get('new_tickets_created', 0),
                            "existing_tickets": result.get('existing_tickets_found', 0),
                            "message": f"{result.get('new_tickets_created', 0)}개의 새로운 티켓이 생성되었습니다.",
                            "completed_at": datetime.utcnow().isoformat()
                        }

                        self.task_manager.update_task_status(task_id, "COMPLETED", final_result)

                        # 마지막 단계 완료 처리
                        self.task_manager.update_step_status(
                            task_id, "Jira 티켓 발행", "COMPLETED",
                            f"총 {result.get('new_tickets_created', 0)}개의 티켓이 성공적으로 생성되었습니다."
                        )

                    elif result and result.get('display_mode') == 'no_emails':
                        # 처리할 이메일이 없는 경우
                        logger.info("📭 처리할 이메일이 없습니다")

                        final_result = {
                            "success": True,
                            "tickets_created": 0,
                            "existing_tickets": 0,
                            "message": "처리할 새로운 이메일이 없습니다.",
                            "completed_at": datetime.utcnow().isoformat()
                        }

                        self.task_manager.update_task_status(task_id, "COMPLETED", final_result)

                        # 모든 단계를 완료로 표시
                        self.task_manager.update_step_status(task_id, "이메일 수집", "COMPLETED", "처리할 새로운 이메일이 없습니다.")
                        self.task_manager.update_step_status(task_id, "메일 분류", "COMPLETED", "분류할 이메일이 없습니다.")
                        self.task_manager.update_step_status(task_id, "Jira 티켓 발행", "COMPLETED", "생성할 티켓이 없습니다.")

                    else:
                        # 기타 오류 또는 실패
                        error_msg = result.get('message', '알 수 없는 오류가 발생했습니다.') if result else '처리 결과를 받지 못했습니다.'
                        logger.error(f"❌ 티켓 생성 실패: {error_msg}")

                        final_result = {
                            "success": False,
                            "tickets_created": 0,
                            "existing_tickets": 0,
                            "message": error_msg,
                            "error": error_msg,
                            "failed_at": datetime.utcnow().isoformat()
                        }

                        self.task_manager.update_task_status(task_id, "FAILED", final_result)

                        # 현재 진행 중인 단계를 실패로 표시
                        task = self.task_manager.get_task(task_id)
                        if task:
                            for step in task.steps:
                                if step['status'] == 'IN_PROGRESS':
                                    self.task_manager.update_step_status(task_id, step['step_name'], "FAILED", error_msg)
                                elif step['status'] == 'PENDING':
                                    self.task_manager.update_step_status(task_id, step['step_name'], "FAILED", "이전 단계 실패로 인해 건너뜀")

                except Exception as processing_error:
                    logger.error(f"❌ 티켓 처리 중 오류: {str(processing_error)}")
                    logger.error(f"❌ 상세 오류: {traceback.format_exc()}")

                    # 실패 결과 저장
                    final_result = {
                        "success": False,
                        "tickets_created": 0,
                        "existing_tickets": 0,
                        "message": f"티켓 처리 중 오류가 발생했습니다: {str(processing_error)}",
                        "error": str(processing_error),
                        "failed_at": datetime.utcnow().isoformat()
                    }

                    self.task_manager.update_task_status(task_id, "FAILED", final_result)

                    # 현재 진행 중인 단계를 실패로 표시
                    task = self.task_manager.get_task(task_id)
                    if task:
                        for step in task.steps:
                            if step['status'] == 'IN_PROGRESS':
                                self.task_manager.update_step_status(task_id, step['step_name'], "FAILED", str(processing_error))
                            elif step['status'] == 'PENDING':
                                self.task_manager.update_step_status(task_id, step['step_name'], "FAILED", "이전 단계 실패로 인해 건너뜀")

            except Exception as e:
                logger.error(f"❌ 백그라운드 워커 실행 중 오류: {str(e)}")
                logger.error(f"❌ 상세 오류: {traceback.format_exc()}")

                # 치명적 오류 결과 저장
                final_result = {
                    "success": False,
                    "tickets_created": 0,
                    "existing_tickets": 0,
                    "message": f"시스템 오류가 발생했습니다: {str(e)}",
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                }

                try:
                    self.task_manager.update_task_status(task_id, "FAILED", final_result)
                except Exception as update_error:
                    logger.error(f"❌ 상태 업데이트 실패: {update_error}")

        # 백그라운드 스레드에서 실행
        logger.info(f"🧵 백그라운드 스레드 시작: task_id={task_id}")
        thread = threading.Thread(target=_background_worker, daemon=True)
        thread.start()
        logger.info(f"✅ 백그라운드 스레드 시작 완료: task_id={task_id}")

    def _process_with_progress_tracking(self, task_id: str, provider_name: str, user_query: str = None,
                                        mem0_memory=None, access_token: str = None) -> Dict[str, Any]:
        """진행상황을 추적하면서 원본 함수 실행"""

        try:
            # 이메일 수집 단계 완료
            self.task_manager.update_step_status(task_id, "이메일 수집", "COMPLETED", "이메일 수집이 완료되었습니다.")

            # 메일 분류 단계 시작
            logger.info("🔍 단계 2: 메일 분류 시작")
            self.task_manager.update_step_status(task_id, "메일 분류", "IN_PROGRESS", "LLM을 이용하여 업무 관련 메일을 분류하고 있습니다...")

            # 원본 함수 호출
            result = process_emails_with_ticket_logic(provider_name, user_query, mem0_memory, access_token)

            # 메일 분류 단계 완료
            tickets_found = result.get('new_tickets_created', 0) + result.get('existing_tickets_found', 0)
            self.task_manager.update_step_status(
                task_id, "메일 분류", "COMPLETED",
                f"메일 분류가 완료되었습니다. 총 {tickets_found}개의 업무 관련 메일을 발견했습니다."
            )

            # Jira 티켓 발행 단계 시작
            if result.get('new_tickets_created', 0) > 0:
                logger.info("🎫 단계 3: Jira 티켓 발행 시작")
                self.task_manager.update_step_status(
                    task_id, "Jira 티켓 발행", "IN_PROGRESS",
                    f"{result.get('new_tickets_created', 0)}개의 새로운 티켓을 생성하고 있습니다..."
                )
            else:
                logger.info("🎫 단계 3: 생성할 티켓이 없어 Jira 티켓 발행 단계를 건너뜁니다")
                self.task_manager.update_step_status(
                    task_id, "Jira 티켓 발행", "COMPLETED",
                    "새로 생성할 티켓이 없어 이 단계를 건너뜁니다."
                )

            return result

        except Exception as e:
            logger.error(f"❌ 진행상황 추적 중 오류: {str(e)}")
            raise e

# 전역 프로세서 인스턴스
_processor = None

def get_async_processor() -> AsyncTicketProcessor:
    """싱글톤 패턴으로 프로세서 인스턴스 반환"""
    global _processor
    if _processor is None:
        _processor = AsyncTicketProcessor()
    return _processor

def start_async_ticket_creation(task_id: str, provider_name: str = "gmail", user_query: str = None,
                               mem0_memory=None, access_token: str = None):
    """비동기 티켓 생성 시작 (외부 API용)"""
    processor = get_async_processor()
    processor.process_emails_with_ticket_logic_async(
        task_id, provider_name, user_query, mem0_memory, access_token
    )