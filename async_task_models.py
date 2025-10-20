#!/usr/bin/env python3
"""
비동기 작업 관리를 위한 Task 모델 및 관리자
"""

import uuid
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StepStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class TaskStep:
    """작업 단계"""
    step_name: str
    status: str = "PENDING"
    log: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

@dataclass
class Task:
    """비동기 작업 모델"""
    task_id: str
    user_id: str
    overall_status: str = "PENDING"
    steps: List[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow().isoformat()
        if self.steps is None:
            # 기본 티켓 생성 단계들
            self.steps = [
                {"step_name": "이메일 수집", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
                {"step_name": "메일 분류", "status": "PENDING", "log": None, "started_at": None, "completed_at": None},
                {"step_name": "Jira 티켓 발행", "status": "PENDING", "log": None, "started_at": None, "completed_at": None}
            ]

class AsyncTaskManager:
    """비동기 작업 관리자"""

    def __init__(self, db_path: str = "tickets.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """데이터베이스 초기화 및 tasks 테이블 생성"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            # WAL 모드로 설정하여 동시성 개선
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=1000")
            conn.execute("PRAGMA temp_store=memory")

            cursor = conn.cursor()

            # tasks 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    overall_status TEXT NOT NULL DEFAULT 'PENDING',
                    steps TEXT NOT NULL,
                    final_result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(overall_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")

            conn.commit()
            print("✅ 비동기 작업 테이블 및 인덱스 생성 완료")

    def create_task(self, user_id: str, steps: List[Dict[str, Any]] = None) -> str:
        """새 작업 생성"""
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            user_id=user_id,
            steps=steps
        )

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO tasks (task_id, user_id, overall_status, steps, final_result, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.user_id,
                task.overall_status,
                json.dumps(task.steps),
                json.dumps(task.final_result) if task.final_result else None,
                task.created_at,
                task.updated_at
            ))

            conn.commit()
            print(f"✅ 비동기 작업 생성 완료: {task_id}")
            return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """작업 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT task_id, user_id, overall_status, steps, final_result, created_at, updated_at
                FROM tasks WHERE task_id = ?
            """, (task_id,))

            row = cursor.fetchone()
            if row:
                return Task(
                    task_id=row[0],
                    user_id=row[1],
                    overall_status=row[2],
                    steps=json.loads(row[3]) if row[3] else [],
                    final_result=json.loads(row[4]) if row[4] else None,
                    created_at=row[5],
                    updated_at=row[6]
                )
            return None

    def update_task_status(self, task_id: str, status: str, final_result: Dict[str, Any] = None):
        """작업의 전체 상태 업데이트"""
        current_time = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE tasks
                SET overall_status = ?, final_result = ?, updated_at = ?
                WHERE task_id = ?
            """, (
                status,
                json.dumps(final_result) if final_result else None,
                current_time,
                task_id
            ))

            conn.commit()
            print(f"✅ 작업 상태 업데이트: {task_id} -> {status}")

    def update_step_status(self, task_id: str, step_name: str, status: str, log: str = None):
        """특정 단계의 상태 업데이트"""
        current_time = datetime.utcnow().isoformat()

        # 현재 작업 조회
        task = self.get_task(task_id)
        if not task:
            print(f"❌ 작업을 찾을 수 없습니다: {task_id}")
            return

        # 해당 단계 찾아서 업데이트
        updated_steps = task.steps.copy()
        step_found = False

        for step in updated_steps:
            if step["step_name"] == step_name:
                step["status"] = status
                if log:
                    step["log"] = log

                # 시작/완료 시간 설정
                if status == "IN_PROGRESS" and not step.get("started_at"):
                    step["started_at"] = current_time
                elif status in ["COMPLETED", "FAILED"]:
                    step["completed_at"] = current_time

                step_found = True
                break

        if not step_found:
            print(f"❌ 단계를 찾을 수 없습니다: {step_name}")
            return

        # 데이터베이스 업데이트
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE tasks
                SET steps = ?, updated_at = ?
                WHERE task_id = ?
            """, (
                json.dumps(updated_steps),
                current_time,
                task_id
            ))

            conn.commit()
            print(f"✅ 단계 상태 업데이트: {task_id} -> {step_name}: {status}")

    def get_user_tasks(self, user_id: str, status: str = None) -> List[Task]:
        """사용자의 작업 목록 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            if status:
                cursor.execute("""
                    SELECT task_id, user_id, overall_status, steps, final_result, created_at, updated_at
                    FROM tasks WHERE user_id = ? AND overall_status = ?
                    ORDER BY created_at DESC
                """, (user_id, status))
            else:
                cursor.execute("""
                    SELECT task_id, user_id, overall_status, steps, final_result, created_at, updated_at
                    FROM tasks WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,))

            tasks = []
            for row in cursor.fetchall():
                tasks.append(Task(
                    task_id=row[0],
                    user_id=row[1],
                    overall_status=row[2],
                    steps=json.loads(row[3]) if row[3] else [],
                    final_result=json.loads(row[4]) if row[4] else None,
                    created_at=row[5],
                    updated_at=row[6]
                ))

            return tasks

    def delete_task(self, task_id: str) -> bool:
        """작업 삭제"""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()

                print(f"✅ 작업 삭제 완료: {task_id}")
                return True
        except Exception as e:
            print(f"❌ 작업 삭제 실패: {e}")
            return False