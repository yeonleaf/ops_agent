#!/usr/bin/env python3
"""
이메일 스레드 탐지기
In-Reply-To, References, Message-ID 헤더를 활용하여 메일 스레드를 식별하고
중복 티켓 생성을 방지
"""

import os
import re
import hashlib
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import extract_msg


@dataclass
class EmailThreadInfo:
    """이메일 스레드 정보"""
    message_id: Optional[str]
    in_reply_to: Optional[str]
    references: List[str]
    subject_normalized: str
    thread_id: Optional[str]
    is_thread_root: bool
    file_path: str


class EmailThreadDetector:
    """이메일 스레드 탐지기"""
    
    def __init__(self):
        self.threads: Dict[str, List[EmailThreadInfo]] = {}
        self.message_id_to_thread: Dict[str, str] = {}
        self.subject_to_thread: Dict[str, str] = {}
        
    def normalize_subject(self, subject: str) -> str:
        """제목 정규화 (RE:, FW:, [번호] 등 제거)"""
        if not subject:
            return ""
        
        # RE:, FW:, 회신:, 전달: 등과 번호 제거
        patterns = [
            r'^(RE:\s*)*',
            r'^(FW:\s*)*',
            r'^(회신:\s*)*',
            r'^(전달:\s*)*',
            r'^\[\d+\]\s*',
            r'^\(\d+\)\s*',
            r'^\(#\d+\)\s*',
            r'^\(\d+\)\s*:',
            r'업데이트:?\s*',
            r'mentioned you in\s*',
        ]
        
        normalized = subject.strip()
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def is_reply_email(self, subject: str) -> bool:
        """제목으로 회신 메일인지 판단"""
        if not subject:
            return False
        
        reply_patterns = [
            r'^RE:\s*',
            r'^회신:\s*',
            r'업데이트:\s*',
            r'mentioned you in',
        ]
        
        for pattern in reply_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return True
        return False
    
    def extract_thread_info_from_msg(self, msg_path: str) -> Optional[EmailThreadInfo]:
        """MSG 파일에서 스레드 정보 추출"""
        try:
            msg = extract_msg.Message(msg_path)
            
            # 기본 정보
            subject = msg.subject or ""
            message_id = None
            in_reply_to = None
            references = []
            
            # 헤더에서 메시지 ID 관련 정보 추출
            try:
                # Message-ID 추출 (직접 속성 또는 헤더에서)
                if hasattr(msg, 'messageId') and msg.messageId:
                    message_id = msg.messageId.strip('<>')
                
                # email.message.Message 객체에서 헤더 정보 추출
                if hasattr(msg, 'header') and msg.header:
                    header_obj = msg.header
                    
                    # In-Reply-To 추출
                    in_reply_to_raw = header_obj.get('In-Reply-To')
                    if in_reply_to_raw:
                        # <> 제거하고 첫 번째 ID만 사용
                        in_reply_to_match = re.search(r'<([^>]+)>', in_reply_to_raw)
                        if in_reply_to_match:
                            in_reply_to = in_reply_to_match.group(1)
                    
                    # References 추출
                    references_raw = header_obj.get('References')
                    if references_raw:
                        # 모든 <message-id> 형태 추출
                        references = re.findall(r'<([^>]+)>', references_raw)
                    
                    # Message-ID가 없으면 헤더에서 추출
                    if not message_id:
                        message_id_raw = header_obj.get('Message-ID')
                        if message_id_raw:
                            message_id = message_id_raw.strip('<>')
                
                # 여전히 Message-ID가 없으면 생성
                if not message_id:
                    file_info = f"{os.path.basename(msg_path)}_{msg.date}"
                    message_id = hashlib.md5(file_info.encode()).hexdigest()
                    
            except Exception as e:
                print(f"헤더 추출 오류 ({msg_path}): {e}")
                # 파일명 기반 ID 생성
                file_info = f"{os.path.basename(msg_path)}_{msg.date}"
                message_id = hashlib.md5(file_info.encode()).hexdigest()
            
            # 제목 정규화
            normalized_subject = self.normalize_subject(subject)
            
            return EmailThreadInfo(
                message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                subject_normalized=normalized_subject,
                thread_id=None,  # 나중에 설정
                is_thread_root=False,  # 나중에 설정
                file_path=msg_path
            )
            
        except Exception as e:
            print(f"MSG 파일 읽기 오류 ({msg_path}): {e}")
            return None
    
    def build_thread_graph(self, email_infos: List[EmailThreadInfo]):
        """이메일 정보들로부터 스레드 그래프 구축"""
        # 1단계: Message-ID로 매핑
        id_to_email = {}
        for email in email_infos:
            if email.message_id:
                id_to_email[email.message_id] = email
        
        # 2단계: 스레드 관계 구축
        thread_groups = []
        processed = set()
        
        for email in email_infos:
            if email.message_id in processed:
                continue
            
            # 새 스레드 그룹 시작
            thread_group = [email]
            processed.add(email.message_id)
            
            # In-Reply-To나 References로 연결된 이메일들 찾기
            to_process = [email]
            
            while to_process:
                current = to_process.pop(0)
                
                # 이 메일이 회신하는 메일 찾기
                if current.in_reply_to and current.in_reply_to in id_to_email:
                    parent = id_to_email[current.in_reply_to]
                    if parent.message_id not in processed:
                        thread_group.append(parent)
                        processed.add(parent.message_id)
                        to_process.append(parent)
                
                # References에 있는 메일들 찾기
                for ref_id in current.references:
                    if ref_id in id_to_email:
                        ref_email = id_to_email[ref_id]
                        if ref_email.message_id not in processed:
                            thread_group.append(ref_email)
                            processed.add(ref_email.message_id)
                            to_process.append(ref_email)
                
                # 이 메일에 회신한 메일들 찾기
                for other in email_infos:
                    if (other.in_reply_to == current.message_id and 
                        other.message_id not in processed):
                        thread_group.append(other)
                        processed.add(other.message_id)
                        to_process.append(other)
            
            if len(thread_group) > 1:
                thread_groups.append(thread_group)
        
        # 3단계: 제목 기반 스레드 병합 (헤더 정보가 없는 경우 대비)
        subject_groups = defaultdict(list)
        for email in email_infos:
            if email.message_id not in processed and email.subject_normalized:
                # 정규화된 제목이 5글자 이상인 경우만 그룹화 (너무 짧은 제목 제외)
                if len(email.subject_normalized) >= 5:
                    subject_groups[email.subject_normalized].append(email)
        
        # 같은 제목의 메일들을 스레드로 처리
        for subject, emails in subject_groups.items():
            if len(emails) > 1:
                # 날짜순으로 정렬
                try:
                    sorted_emails = []
                    for email in emails:
                        try:
                            msg = extract_msg.Message(email.file_path)
                            date = msg.date if msg.date else "1900-01-01"
                            sorted_emails.append((date, email))
                        except:
                            sorted_emails.append(("1900-01-01", email))
                    
                    sorted_emails.sort(key=lambda x: x[0])
                    emails = [email for date, email in sorted_emails]
                except:
                    pass
                
                thread_groups.append(emails)
                for email in emails:
                    processed.add(email.message_id)
                
                print(f"📎 제목 기반 스레드 발견: '{subject}' ({len(emails)}개 메일)")
        
        return thread_groups
    
    def assign_thread_ids(self, thread_groups: List[List[EmailThreadInfo]]):
        """스레드 그룹에 ID 할당하고 루트 메일 결정"""
        for i, thread_group in enumerate(thread_groups):
            thread_id = f"thread_{i+1:03d}"
            
            # 날짜 기준으로 정렬하여 가장 오래된 메일을 루트로 설정
            try:
                # MSG에서 날짜 정보 추출하여 정렬
                sorted_emails = []
                for email in thread_group:
                    try:
                        msg = extract_msg.Message(email.file_path)
                        date = msg.date if msg.date else "1900-01-01"
                        sorted_emails.append((date, email))
                    except:
                        sorted_emails.append(("1900-01-01", email))
                
                sorted_emails.sort(key=lambda x: x[0])
                
                for j, (date, email) in enumerate(sorted_emails):
                    email.thread_id = thread_id
                    email.is_thread_root = (j == 0)  # 가장 오래된 메일이 루트
                    
            except Exception as e:
                print(f"날짜 정렬 오류: {e}")
                # 정렬 실패시 첫 번째를 루트로 설정
                for j, email in enumerate(thread_group):
                    email.thread_id = thread_id
                    email.is_thread_root = (j == 0)
    
    def get_original_emails_only(self, email_infos: List[EmailThreadInfo]) -> List[EmailThreadInfo]:
        """In-Reply-To가 없는 원본 메일들만 반환 (스레드의 시작점들)"""
        original_emails = []
        for email in email_infos:
            # In-Reply-To가 없는 메일만 선별 (원본 메일)
            if not email.in_reply_to:
                original_emails.append(email)
        
        return original_emails
    
    def analyze_email_threads(self, msg_files: List[str]) -> Tuple[List[EmailThreadInfo], List[EmailThreadInfo]]:
        """
        메일 파일들을 분석하여 스레드 정보를 반환
        
        Returns:
            (전체_메일_정보, 스레드_대표_메일들)
        """
        print(f"🧵 {len(msg_files)}개 메일 파일의 스레드 분석 시작...")
        
        # 1. 모든 메일에서 스레드 정보 추출
        email_infos = []
        threads_with_headers = 0
        for msg_file in msg_files:
            thread_info = self.extract_thread_info_from_msg(msg_file)
            if thread_info:
                email_infos.append(thread_info)
                if thread_info.in_reply_to or thread_info.references:
                    threads_with_headers += 1
                    print(f"🔗 스레드 관계 발견: {os.path.basename(thread_info.file_path)[:40]}...")
                    if thread_info.in_reply_to:
                        print(f"   In-Reply-To: {thread_info.in_reply_to[:40]}...")
                    if thread_info.references:
                        print(f"   References: {len(thread_info.references)}개")
        
        print(f"📧 {len(email_infos)}개 메일 정보 추출 완료")
        print(f"🔗 {threads_with_headers}개 메일에서 스레드 헤더 발견")
        
        # 2. 스레드 그래프 구축
        thread_groups = self.build_thread_graph(email_infos)
        print(f"🔗 {len(thread_groups)}개 스레드 그룹 발견")
        
        # 3. 스레드 ID 할당
        self.assign_thread_ids(thread_groups)
        
        # 4. In-Reply-To가 없는 원본 메일들만 선정
        original_emails = self.get_original_emails_only(email_infos)
        print(f"📋 {len(original_emails)}개 원본 메일 선정 (Reply 메일 제외: {len(email_infos) - len(original_emails)}개)")
        
        return email_infos, original_emails
    
    def print_thread_analysis(self, email_infos: List[EmailThreadInfo]):
        """스레드 분석 결과 출력"""
        threads = defaultdict(list)
        single_emails = []
        
        for email in email_infos:
            if email.thread_id:
                threads[email.thread_id].append(email)
            else:
                single_emails.append(email)
        
        print(f"\n🧵 스레드 분석 결과:")
        print(f"=" * 60)
        
        for thread_id, emails in threads.items():
            print(f"\n📎 {thread_id} ({len(emails)}개 메일):")
            for email in emails:
                root_mark = "🌟" if email.is_thread_root else "   "
                print(f"  {root_mark} {os.path.basename(email.file_path)[:50]}...")
                print(f"      제목: {email.subject_normalized[:60]}...")
        
        print(f"\n📧 단독 메일: {len(single_emails)}개")


# 테스트 함수
def test_thread_detection():
    """스레드 탐지 기능 테스트"""
    print("🧪 이메일 스레드 탐지 테스트")
    print("=" * 50)
    
    detector = EmailThreadDetector()
    
    # mail 폴더의 몇 개 파일로 테스트
    mail_dir = "mail"
    if not os.path.exists(mail_dir):
        print(f"❌ {mail_dir} 폴더를 찾을 수 없습니다.")
        return
    
    # 첫 50개 파일로 테스트 (더 많은 스레드 패턴을 찾기 위해)
    msg_files = [os.path.join(mail_dir, f) for f in os.listdir(mail_dir) 
                 if f.endswith('.msg')][:50]
    
    all_emails, original_emails = detector.analyze_email_threads(msg_files)
    
    print(f"\n🧵 원본 메일만 필터링 결과:")
    print("=" * 60)
    detector.print_thread_analysis(original_emails)
    
    print(f"\n📊 요약:")
    print(f"   전체 메일: {len(all_emails)}개")
    print(f"   원본 메일: {len(original_emails)}개")
    print(f"   Reply 제외: {len(all_emails) - len(original_emails)}개")


if __name__ == "__main__":
    test_thread_detection()