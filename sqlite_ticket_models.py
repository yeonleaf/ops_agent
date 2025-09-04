#!/usr/bin/env python3
"""
SQLite 전용 티켓 모델 및 관리자
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import sqlite3
import json
from datetime import datetime

@dataclass
class Ticket:
    """티켓 모델 - SQLite 테이블용"""
    ticket_id: Optional[int]  # PK - 티켓 기본 키
    original_message_id: str  # FK - mail.message_id와 연결
    status: str  # pending(초기상태), approved(승인된 상태), rejected(반려된 상태)
    title: str  # 티켓 제목
    description: str  # 티켓 상세 내용 (TEXT)
    priority: str  # 우선순위 (Highest, High, Medium, Low)
    ticket_type: str  # 티켓 타입 (Task, Bug, Feature 등)
    reporter: str  # 담당자/리포터
    reporter_email: str  # 담당자 이메일
    labels: List[str]  # 라벨 목록
    created_at: str  # 생성 시각
    updated_at: str  # 마지막 수정 시각

@dataclass
class TicketEvent:
    """티켓 이벤트 모델 - SQLite 테이블용"""
    event_id: Optional[int]  # PK - 이벤트 기본 키
    ticket_id: int  # FK - tickets.ticket_id와 연결
    event_type: str  # status_change, comment, priority_change 등
    old_value: str  # 변경 전 값
    new_value: str  # 변경 후 값
    created_at: str  # 이벤트 발생 시각

class SQLiteTicketManager:
    """SQLite 전용 티켓 관리자"""
    
    def __init__(self, db_path: str = "tickets.db"):
        self.db_path = db_path
        # 데이터베이스 파일이 있는 디렉토리 권한 확인 및 설정
        import os
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, mode=0o755, exist_ok=True)
            print(f"✅ SQLite RDB 디렉토리 생성 및 권한 설정: {db_dir}")
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            # WAL 모드로 설정하여 동시성 개선
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=1000")
            conn.execute("PRAGMA temp_store=memory")
            
            cursor = conn.cursor()
            
            # tickets 테이블 생성 (ERD 스키마 준수)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_message_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT DEFAULT 'Medium',
                    ticket_type TEXT DEFAULT 'Task',
                    reporter TEXT,
                    reporter_email TEXT,
                    labels TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # ticket_events 테이블 생성 (ERD 스키마 준수)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticket_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
                )
            """)
            
            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_message_id ON tickets(original_message_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id ON ticket_events(ticket_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_events_created_at ON ticket_events(created_at)")
            
            conn.commit()
    
    def insert_ticket(self, ticket: Ticket) -> int:
        """티켓 삽입"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO tickets (original_message_id, status, title, description,
                                       priority, ticket_type, reporter, reporter_email, labels,
                                       created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket.original_message_id, ticket.status, ticket.title, ticket.description,
                    ticket.priority, ticket.ticket_type, ticket.reporter, ticket.reporter_email,
                    json.dumps(ticket.labels), ticket.created_at, ticket.updated_at
                ))
                
                ticket_id = cursor.lastrowid
                conn.commit()
                
                # Vector DB에 메일 저장 시도
                try:
                    from vector_db_models import VectorDBManager, Mail
                    vector_db = VectorDBManager()
                    
                    # Mail 객체 생성 (기본 정보로)
                    mail = Mail(
                        message_id=ticket.original_message_id,
                        original_content=ticket.description or "",
                        refined_content=ticket.description or "",
                        sender=ticket.reporter,
                        status="acceptable",
                        subject=ticket.title,
                        received_datetime=ticket.created_at,
                        content_type="text",
                        has_attachment=False,
                        extraction_method="sqlite_ticket_manager",
                        content_summary=ticket.description[:200] + "..." if ticket.description and len(ticket.description) > 200 else (ticket.description or ""),
                        key_points=[],
                        created_at=ticket.created_at
                    )
                    
                    vector_save_success = vector_db.save_mail(mail)
                    if vector_save_success:
                        print(f"✅ 메일이 Vector DB에 저장되었습니다: {mail.message_id}")
                    else:
                        print(f"❌ 메일을 Vector DB에 저장하는데 실패했습니다: {mail.message_id}")
                        
                except Exception as e:
                    print(f"⚠️ Vector DB 저장 중 오류: {str(e)}")
                    print(f"⚠️ Vector DB 저장을 건너뛰고 티켓만 저장합니다.")
                
                return ticket_id
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(f"메일 ID {ticket.original_message_id}로 이미 티켓이 존재합니다. 중복 생성을 방지합니다.")
                else:
                    raise e
    
    def insert_ticket_event(self, event: TicketEvent) -> int:
        """티켓 이벤트 삽입"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event.ticket_id, event.event_type, event.old_value, event.new_value, event.created_at
            ))
            
            event_id = cursor.lastrowid
            conn.commit()
            return event_id
    
    def get_ticket_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """티켓 ID로 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticket_id, original_message_id, status, title, description,
                       priority, ticket_type, reporter, reporter_email, labels,
                       created_at, updated_at
                FROM tickets WHERE ticket_id = ?
            """, (ticket_id,))
            
            row = cursor.fetchone()
            if row:
                return Ticket(
                    ticket_id=row[0],
                    original_message_id=row[1],
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    priority=row[5],
                    ticket_type=row[6],
                    reporter=row[7],
                    reporter_email=row[8],
                    labels=json.loads(row[9]) if row[9] else [],
                    created_at=row[10],
                    updated_at=row[11]
                )
            return None
    
    def get_tickets_by_message_id(self, message_id: str) -> List[Ticket]:
        """메일 ID로 관련 티켓 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticket_id, original_message_id, status, title, description,
                       priority, ticket_type, reporter, reporter_email, labels,
                       created_at, updated_at
                FROM tickets WHERE original_message_id = ?
            """, (message_id,))
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(Ticket(
                    ticket_id=row[0],
                    original_message_id=row[1],
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    priority=row[5],
                    ticket_type=row[6],
                    reporter=row[7],
                    reporter_email=row[8],
                    labels=json.loads(row[9]) if row[9] else [],
                    created_at=row[10],
                    updated_at=row[11]
                ))
            return tickets
    
    def get_tickets_by_status(self, status: str) -> List[Ticket]:
        """특정 상태의 티켓만 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticket_id, original_message_id, status, title, description,
                       priority, ticket_type, reporter, reporter_email, labels,
                       created_at, updated_at
                FROM tickets WHERE status = ? ORDER BY created_at DESC
            """, (status,))
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(Ticket(
                    ticket_id=row[0],
                    original_message_id=row[1],
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    priority=row[5],
                    ticket_type=row[6],
                    reporter=row[7],
                    reporter_email=row[8],
                    labels=json.loads(row[9]) if row[9] else [],
                    created_at=row[10],
                    updated_at=row[11]
                ))
            return tickets
    
    def get_all_tickets(self) -> List[Ticket]:
        """모든 티켓 조회 (최근 순)"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticket_id, original_message_id, status, title, description,
                       priority, ticket_type, reporter, reporter_email, labels,
                       created_at, updated_at
                FROM tickets ORDER BY created_at DESC
            """)
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(Ticket(
                    ticket_id=row[0],
                    original_message_id=row[1],
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    priority=row[5],
                    ticket_type=row[6],
                    reporter=row[7],
                    reporter_email=row[8],
                    labels=json.loads(row[9]) if row[9] else [],
                    created_at=row[10],
                    updated_at=row[11]
                ))
            return tickets
    
    def update_ticket_status(self, ticket_id: int, new_status: str, old_status: str):
        """티켓 상태 업데이트 (RDB + VectorDB 동기화)"""
        current_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # 티켓 상태 업데이트
            cursor.execute("""
                UPDATE tickets 
                SET status = ?, updated_at = ?
                WHERE ticket_id = ?
            """, (new_status, current_time, ticket_id))
            
            # 이벤트 기록
            cursor.execute("""
                INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, "status_change", old_status, new_status, current_time))
            
            conn.commit()
        
        # VectorDB 상태 동기화
        try:
            from vector_db_models import VectorDBManager
            vector_db = VectorDBManager()
            
            # 해당 티켓의 메일 ID 찾기
            cursor.execute("SELECT original_message_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
            result = cursor.fetchone()
            if result:
                message_id = result[0]
                # VectorDB에서 해당 메일의 상태 업데이트
                vector_db.update_mail_status(message_id, new_status)
                print(f"✅ VectorDB 상태 동기화 완료: {message_id} -> {new_status}")
            else:
                print(f"⚠️ 티켓 {ticket_id}의 메일 ID를 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"❌ VectorDB 상태 동기화 실패: {str(e)}")
    
    def update_ticket_labels(self, ticket_id: int, new_labels: List[str], old_labels: List[str]) -> bool:
        """티켓 레이블 업데이트 (RDB만)"""
        try:
            current_time = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                # 티켓 레이블 업데이트 (JSON 형태로 저장)
                labels_json = json.dumps(new_labels)
                cursor.execute("""
                    UPDATE tickets 
                    SET labels = ?, updated_at = ?
                    WHERE ticket_id = ?
                """, (labels_json, current_time, ticket_id))
                
                # 이벤트 기록
                old_labels_str = ', '.join(old_labels) if old_labels else '없음'
                new_labels_str = ', '.join(new_labels) if new_labels else '없음'
                cursor.execute("""
                    INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (ticket_id, "labels_change", old_labels_str, new_labels_str, current_time))
                
                conn.commit()
                print(f"✅ RDB 레이블 업데이트 완료: ticket_id={ticket_id}, new_labels={new_labels}")
                return True
                
        except Exception as e:
            print(f"❌ RDB 레이블 업데이트 실패: {str(e)}")
            import traceback
            print(f"❌ 오류 상세: {traceback.format_exc()}")
            return False

    def update_ticket_priority(self, ticket_id: int, new_priority: str, old_priority: str):
        """티켓 우선순위 업데이트"""
        current_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # 티켓 우선순위 업데이트
            cursor.execute("""
                UPDATE tickets 
                SET priority = ?, updated_at = ?
                WHERE ticket_id = ?
            """, (new_priority, current_time, ticket_id))
            
            # 이벤트 기록
            cursor.execute("""
                INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, "priority_change", old_priority, new_priority, current_time))
            
            conn.commit()
    
    def update_ticket_description(self, ticket_id: int, new_description: str, old_description: str) -> bool:
        """티켓 description 업데이트"""
        try:
            current_time = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                # 티켓 description 업데이트
                cursor.execute("""
                    UPDATE tickets 
                    SET description = ?, updated_at = ?
                    WHERE ticket_id = ?
                """, (new_description, current_time, ticket_id))
                
                # 이벤트 기록
                cursor.execute("""
                    INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (ticket_id, "description_change", old_description or "", new_description or "", current_time))
                
                conn.commit()
                print(f"✅ RDB description 업데이트 완료: ticket_id={ticket_id}")
                return True
                
        except Exception as e:
            print(f"❌ RDB description 업데이트 실패: {str(e)}")
            import traceback
            print(f"❌ 오류 상세: {traceback.format_exc()}")
            return False
    
    
    def get_ticket_events(self, ticket_id: int) -> List[TicketEvent]:
        """티켓의 모든 이벤트 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT event_id, ticket_id, event_type, old_value, new_value, created_at
                FROM ticket_events 
                WHERE ticket_id = ?
                ORDER BY created_at DESC
            """, (ticket_id,))
            
            events = []
            for row in cursor.fetchall():
                events.append(TicketEvent(
                    event_id=row[0],
                    ticket_id=row[1],
                    event_type=row[2],
                    old_value=row[3],
                    new_value=row[4],
                    created_at=row[5]
                ))
            return events
    
    def get_tickets_by_status(self, status: str) -> List[Ticket]:
        """상태별 티켓 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ticket_id, original_message_id, status, title, description,
                       priority, ticket_type, reporter, reporter_email, labels,
                       created_at, updated_at
                FROM tickets 
                WHERE status = ?
                ORDER BY created_at DESC
            """, (status,))
            
            tickets = []
            for row in cursor.fetchall():
                tickets.append(Ticket(
                    ticket_id=row[0],
                    original_message_id=row[1],
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    priority=row[5],
                    ticket_type=row[6],
                    reporter=row[7],
                    reporter_email=row[8],
                    labels=json.loads(row[9]) if row[9] else [],
                    created_at=row[10],
                    updated_at=row[11]
                ))
            return tickets
    
    def delete_ticket(self, ticket_id: int) -> bool:
        """티켓 삭제 (관련 이벤트도 함께 삭제)"""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                # 관련 이벤트 먼저 삭제
                cursor.execute("DELETE FROM ticket_events WHERE ticket_id = ?", (ticket_id,))
                
                # 티켓 삭제
                cursor.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"티켓 삭제 오류: {e}")
            return False