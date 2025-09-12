#!/usr/bin/env python3
"""
데이터베이스 모델 및 스키마 정의
Vector DB Collection과 RDB 연동 구조
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import uuid

@dataclass
class Mail:
    """메일 데이터 모델 (Vector DB Collection용)"""
    message_id: str
    original_content: str
    refined_content: str
    sender: str
    status: str
    has_attachment: bool
    subject: str
    received_datetime: str
    content_type: str
    extraction_method: str
    content_summary: str
    key_points: List[str]
    created_at: str

@dataclass
class Ticket:
    """티켓 데이터 모델 (RDB용)"""
    ticket_id: Optional[int]
    original_message_id: str
    status: str
    title: str
    description: str
    priority: str
    ticket_type: str
    reporter: str
    reporter_email: str
    labels: List[str]
    created_at: str
    updated_at: str

@dataclass
class TicketEvent:
    """티켓 이벤트 데이터 모델 (RDB용)"""
    event_id: Optional[int]
    ticket_id: int
    event_type: str
    old_value: str
    new_value: str
    created_at: str

@dataclass
class User:
    """사용자 데이터 모델 (RDB용)"""
    id: Optional[int]
    email: str
    password_hash: str
    google_refresh_token: Optional[str] = None
    jira_endpoint: Optional[str] = None
    jira_api_token: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class UserAction:
    """사용자 액션 데이터 모델 (RDB용) - 장기 기억용"""
    action_id: Optional[int]
    ticket_id: Optional[int]  # 관련 티켓 ID (없을 수 있음)
    message_id: Optional[str]  # 관련 메일 ID (없을 수 있음)
    action_type: str  # 'ai_decision', 'user_correction', 'ticket_created', 'label_updated' 등
    action_description: str  # 액션에 대한 상세 설명
    old_value: str  # 이전 값
    new_value: str  # 새로운 값
    context: str  # 액션 발생 컨텍스트 (메일 내용, 티켓 정보 등)
    created_at: str  # 생성 시각
    user_id: Optional[str]  # 사용자 ID (AI인 경우 'ai_system')

class DatabaseManager:
    """데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "tickets.db"):
        self.db_path = db_path
        # 데이터베이스 파일이 있는 디렉토리 권한 확인 및 설정
        import os
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, mode=0o755, exist_ok=True)
            print(f"✅ RDB 디렉토리 생성 및 권한 설정: {db_dir}")
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
            
            # tickets 테이블 생성
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
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (original_message_id) REFERENCES mail(message_id)
                )
            """)
            
            # ticket_events 테이블 생성
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
            
            # users 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    google_refresh_token TEXT NULL,
                    jira_endpoint VARCHAR(255) NULL,
                    jira_api_token TEXT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # user_actions 테이블 생성 (장기 기억용)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    message_id TEXT,
                    action_type TEXT NOT NULL,
                    action_description TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    context TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    user_id TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
                )
            """)
            
            # 인덱스 생성
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_message_id 
                ON tickets(original_message_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id 
                ON ticket_events(ticket_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_actions_ticket_id 
                ON user_actions(ticket_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_actions_message_id 
                ON user_actions(message_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_actions_action_type 
                ON user_actions(action_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email 
                ON users(email)
            """)
            
            conn.commit()
    
    def insert_ticket(self, ticket: Ticket) -> int:
        """티켓 삽입"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO tickets (
                    original_message_id, status, title, description, priority,
                    ticket_type, reporter, reporter_email, labels, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket.original_message_id, ticket.status, ticket.title, ticket.description,
                ticket.priority, ticket.ticket_type, ticket.reporter, ticket.reporter_email,
                json.dumps(ticket.labels), ticket.created_at, ticket.updated_at
            ))
            
            ticket_id = cursor.lastrowid
            conn.commit()
            return ticket_id
    
    def insert_ticket_event(self, event: TicketEvent) -> int:
        """티켓 이벤트 삽입"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO ticket_events (
                    ticket_id, event_type, old_value, new_value, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                event.ticket_id, event.event_type, event.old_value, event.new_value, event.created_at
            ))
            
            event_id = cursor.lastrowid
            conn.commit()
            return event_id
    
    def insert_user_action(self, action: UserAction) -> int:
        """사용자 액션 삽입 (장기 기억용)"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO user_actions (
                    ticket_id, message_id, action_type, action_description, 
                    old_value, new_value, context, created_at, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.ticket_id, action.message_id, action.action_type, action.action_description,
                action.old_value, action.new_value, action.context, action.created_at, action.user_id
            ))
            
            action_id = cursor.lastrowid
            conn.commit()
            return action_id
    
    def get_user_actions_by_ticket_id(self, ticket_id: int) -> List[UserAction]:
        """티켓 ID로 관련 사용자 액션 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT action_id, ticket_id, message_id, action_type, action_description,
                       old_value, new_value, context, created_at, user_id
                FROM user_actions WHERE ticket_id = ? ORDER BY created_at DESC
            """, (ticket_id,))
            
            actions = []
            for row in cursor.fetchall():
                actions.append(UserAction(
                    action_id=row[0],
                    ticket_id=row[1],
                    message_id=row[2],
                    action_type=row[3],
                    action_description=row[4],
                    old_value=row[5],
                    new_value=row[6],
                    context=row[7],
                    created_at=row[8],
                    user_id=row[9]
                ))
            return actions
    
    def get_user_actions_by_message_id(self, message_id: str) -> List[UserAction]:
        """메일 ID로 관련 사용자 액션 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT action_id, ticket_id, message_id, action_type, action_description,
                       old_value, new_value, context, created_at, user_id
                FROM user_actions WHERE message_id = ? ORDER BY created_at DESC
            """, (message_id,))
            
            actions = []
            for row in cursor.fetchall():
                actions.append(UserAction(
                    action_id=row[0],
                    ticket_id=row[1],
                    message_id=row[2],
                    action_type=row[3],
                    action_description=row[4],
                    old_value=row[5],
                    new_value=row[6],
                    context=row[7],
                    created_at=row[8],
                    user_id=row[9]
                ))
            return actions
    
    def get_all_user_actions(self, limit: int = 100) -> List[UserAction]:
        """모든 사용자 액션 조회 (최근 순)"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT action_id, ticket_id, message_id, action_type, action_description,
                       old_value, new_value, context, created_at, user_id
                FROM user_actions ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            
            actions = []
            for row in cursor.fetchall():
                actions.append(UserAction(
                    action_id=row[0],
                    ticket_id=row[1],
                    message_id=row[2],
                    action_type=row[3],
                    action_description=row[4],
                    old_value=row[5],
                    new_value=row[6],
                    context=row[7],
                    created_at=row[8],
                    user_id=row[9]
                ))
            return actions
    
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
    
    def update_ticket_status(self, ticket_id: int, new_status: str, old_status: str):
        """티켓 상태 업데이트 및 이벤트 기록"""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                
                # 트랜잭션 시작
                cursor.execute("BEGIN IMMEDIATE")
                
                # 티켓 상태 업데이트
                cursor.execute("""
                    UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?
                """, (new_status, datetime.now().isoformat(), ticket_id))
                
                # 이벤트 기록 (동일한 연결에서 처리)
                cursor.execute("""
                    INSERT INTO ticket_events (
                        ticket_id, event_type, old_value, new_value, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    ticket_id, "status_change", old_status, new_status, datetime.now().isoformat()
                ))
                
                # 커밋
                conn.commit()
                
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                # 잠시 대기 후 재시도
                import time
                time.sleep(0.1)
                self._retry_update_ticket_status(ticket_id, new_status, old_status)
            else:
                raise e
    
    def _retry_update_ticket_status(self, ticket_id: int, new_status: str, old_status: str, max_retries: int = 3):
        """데이터베이스 락 해결을 위한 재시도 메커니즘"""
        import time
        
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")  # WAL 모드로 동시성 개선
                    cursor = conn.cursor()
                    
                    # 티켓 상태 업데이트
                    cursor.execute("""
                        UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?
                    """, (new_status, datetime.now().isoformat(), ticket_id))
                    
                    # 이벤트 기록
                    cursor.execute("""
                        INSERT INTO ticket_events (
                            ticket_id, event_type, old_value, new_value, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        ticket_id, "status_change", old_status, new_status, datetime.now().isoformat()
                    ))
                    
                    conn.commit()
                    return  # 성공시 리턴
                    
            except sqlite3.OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(0.2 * (attempt + 1))  # 점진적 대기
                    continue
                else:
                    raise e
    
    def get_all_tickets(self) -> List[Ticket]:
        """모든 티켓 조회"""
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
    
    # === 사용자 관련 메서드들 ===
    
    def insert_user(self, user: User) -> int:
        """사용자 삽입"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (
                    email, password_hash, google_refresh_token, 
                    jira_endpoint, jira_api_token, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user.email, user.password_hash, user.google_refresh_token,
                user.jira_endpoint, user.jira_api_token, 
                user.created_at or datetime.now().isoformat()
            ))
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, email, password_hash, google_refresh_token,
                       jira_endpoint, jira_api_token, created_at
                FROM users WHERE email = ?
            """, (email,))
            
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    google_refresh_token=row[3],
                    jira_endpoint=row[4],
                    jira_api_token=row[5],
                    created_at=row[6]
                )
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, email, password_hash, google_refresh_token,
                       jira_endpoint, jira_api_token, created_at
                FROM users WHERE id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    google_refresh_token=row[3],
                    jira_endpoint=row[4],
                    jira_api_token=row[5],
                    created_at=row[6]
                )
            return None
    
    def update_user_google_token(self, user_id: int, google_refresh_token: str):
        """사용자의 Google Refresh Token 업데이트"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET google_refresh_token = ? WHERE id = ?
            """, (google_refresh_token, user_id))
            
            conn.commit()
    
    def update_user_jira_info(self, user_id: int, jira_endpoint: str, jira_api_token: str):
        """사용자의 Jira 정보 업데이트"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET jira_endpoint = ?, jira_api_token = ? WHERE id = ?
            """, (jira_endpoint, jira_api_token, user_id))
            
            conn.commit()
    
    def user_exists(self, email: str) -> bool:
        """이메일로 사용자 존재 여부 확인"""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,))
            count = cursor.fetchone()[0]
            return count > 0

class MailParser:
    """메일 파싱 및 구조화 클래스"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def parse_mail_to_json(self, mail_data: Dict[str, Any]) -> Mail:
        """메일 데이터를 Mail 모델로 파싱"""
        
        # 메일 기본 정보 추출
        message_id = mail_data.get('id', str(uuid.uuid4()))
        subject = mail_data.get('subject', '(제목 없음)')
        sender = mail_data.get('from', {}).get('emailAddress', {})
        received_datetime = mail_data.get('receivedDateTime', '')
        has_attachment = mail_data.get('hasAttachments', False)
        
        # 본문 정보
        body_data = mail_data.get('body', {})
        original_content = body_data.get('content', '')
        content_type = body_data.get('contentType', 'text')
        
        # 향상된 내용 추출
        from enhanced_content_extractor import EnhancedContentExtractor
        extractor = EnhancedContentExtractor()
        content_result = extractor.extract_clean_content(original_content, content_type)
        
        # Mail 모델 생성
        mail = Mail(
            message_id=message_id,
            original_content=original_content,
            refined_content=content_result.get('cleaned_text', ''),
            sender=f"{sender.get('name', '알 수 없음')} <{sender.get('address', '')}>",
            status='acceptable',  # 기본값, 나중에 변경 가능
            has_attachment=has_attachment,
            subject=subject,
            received_datetime=received_datetime,
            content_type=content_type,
            extraction_method=content_result.get('extraction_method', ''),
            content_summary=content_result.get('summary', ''),
            key_points=content_result.get('key_points', []),
            created_at=datetime.now().isoformat()
        )
        
        return mail
    
    def create_ticket_from_mail(self, mail: Mail) -> Ticket:
        """메일을 바탕으로 티켓 생성"""
        
        # 우선순위 결정
        priority = self._determine_priority(mail.subject, mail.refined_content)
        
        # 티켓 타입 결정
        ticket_type = self._determine_ticket_type(mail.subject, mail.refined_content)
        
        # 라벨 생성
        labels = self._generate_labels(mail)
        
        # 티켓 모델 생성
        ticket = Ticket(
            ticket_id=None,
            original_message_id=mail.message_id,
            status='new',
            title=mail.subject,
            description=mail.refined_content,
            priority=priority,
            ticket_type=ticket_type,
            reporter=mail.sender.split('<')[0].strip(),
            reporter_email=mail.sender.split('<')[1].rstrip('>') if '<' in mail.sender else '',
            labels=labels,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        return ticket
    
    def _determine_priority(self, subject: str, content: str) -> str:
        """우선순위 결정"""
        urgent_keywords = ['urgent', '긴급', 'asap', 'immediate', 'critical', 'deadline']
        high_keywords = ['important', '중요', 'high', 'priority', 'due']
        
        text_lower = f"{subject} {content}".lower()
        
        for keyword in urgent_keywords:
            if keyword in text_lower:
                return 'Highest'
        
        for keyword in high_keywords:
            if keyword in text_lower:
                return 'High'
        
        return 'Medium'
    
    def _determine_ticket_type(self, subject: str, content: str) -> str:
        """티켓 타입 결정"""
        bug_keywords = ['bug', 'error', 'issue', 'problem', 'fail', 'broken', '오류', '문제']
        feature_keywords = ['feature', 'request', 'enhancement', 'improvement', '새기능', '요청']
        task_keywords = ['task', 'todo', 'work', 'assignment', '업무', '작업']
        
        text_lower = f"{subject} {content}".lower()
        
        for keyword in bug_keywords:
            if keyword in text_lower:
                return 'Bug'
        
        for keyword in feature_keywords:
            if keyword in text_lower:
                return 'Feature Request'
        
        for keyword in task_keywords:
            if keyword in text_lower:
                return 'Task'
        
        return 'Task'
    
    def _generate_labels(self, mail: Mail) -> List[str]:
        """라벨 생성"""
        labels = ['email-generated', 'auto-classified']
        
        # 도메인별 라벨
        if 'microsoft' in mail.subject.lower() or 'office' in mail.subject.lower():
            labels.append('microsoft-office')
        
        if 'planner' in mail.subject.lower() or 'task' in mail.subject.lower():
            labels.append('task-management')
        
        if mail.has_attachment:
            labels.append('has-attachments')
        
        # 상태별 라벨
        if mail.status == 'acceptable':
            labels.append('approved')
        
        return labels
    
    def save_mail_and_ticket(self, mail: Mail, ticket: Ticket) -> Dict[str, Any]:
        """메일과 티켓을 데이터베이스에 저장"""
        
        # 중복 티켓 생성 방지: 메일 ID로 이미 티켓이 존재하는지 확인
        existing_tickets = self.db_manager.get_tickets_by_message_id(mail.message_id)
        if existing_tickets:
            print(f"⚠️ 메일 ID {mail.message_id}로 이미 티켓이 생성되어 있습니다. 중복 생성을 건너뜁니다.")
            existing_ticket = existing_tickets[0]  # 첫 번째 티켓 사용
            return {
                'mail': asdict(mail),
                'ticket': asdict(existing_ticket),
                'ticket_id': existing_ticket.ticket_id,
                'duplicate_prevented': True
            }
        
        # Vector DB에 메일 저장
        print(f"🔍 Vector DB에 메일 저장 시도: {mail.message_id}")
        try:
            from vector_db_models import VectorDBManager
            print(f"✅ VectorDBManager 모듈 로드 성공")
            vector_db = VectorDBManager()
            print(f"✅ VectorDBManager 인스턴스 생성 성공")
            vector_save_success = vector_db.save_mail(mail)
            if vector_save_success:
                print(f"✅ 메일이 Vector DB에 저장되었습니다: {mail.message_id}")
            else:
                print(f"❌ 메일을 Vector DB에 저장하는데 실패했습니다: {mail.message_id}")
        except ImportError as e:
            print(f"❌ Vector DB 모듈을 불러올 수 없음: {str(e)}")
            print(f"⚠️ Vector DB 저장을 건너뛰고 티켓만 저장합니다.")
        except Exception as e:
            print(f"⚠️ Vector DB 저장 중 오류: {str(e)}")
            print(f"⚠️ Vector DB 저장을 건너뛰고 티켓만 저장합니다.")
        
        # 티켓 저장 (중복 체크 포함)
        try:
            ticket_id = self.db_manager.insert_ticket(ticket)
            ticket.ticket_id = ticket_id
            
            # 생성 이벤트 기록
            event = TicketEvent(
                event_id=None,
                ticket_id=ticket_id,
                event_type="ticket_created",
                old_value="",
                new_value="new",
                created_at=datetime.now().isoformat()
            )
            
            self.db_manager.insert_ticket_event(event)
            
            return {
                'mail': asdict(mail),
                'ticket': asdict(ticket),
                'ticket_id': ticket_id,
                'duplicate_prevented': False
            }
            
        except sqlite3.IntegrityError as e:
            # UNIQUE 제약조건 위반 시 (중복 메일 ID)
            if "UNIQUE constraint failed" in str(e):
                print(f"⚠️ 메일 ID {mail.message_id}로 이미 티켓이 존재합니다. 기존 티켓을 반환합니다.")
                existing_tickets = self.db_manager.get_tickets_by_message_id(mail.message_id)
                if existing_tickets:
                    existing_ticket = existing_tickets[0]
                    return {
                        'mail': asdict(mail),
                        'ticket': asdict(existing_ticket),
                        'ticket_id': existing_ticket.ticket_id,
                        'duplicate_prevented': True
                    }
            raise e 