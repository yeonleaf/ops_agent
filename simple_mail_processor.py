#!/usr/bin/env python3
"""
간단한 메일 처리기 - JSON 파일을 직접 읽어서 처리
MCP 없이 동작하는 버전
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any

class SimpleMailProcessor:
    """간단한 메일 처리기"""
    
    def __init__(self, json_file_path: str = "sample_mail_response.json"):
        self.json_file_path = json_file_path
        self._load_data()
    
    def _load_data(self):
        """JSON 파일에서 메일 데이터 로드"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                self._mail_data = json.load(f)
        except Exception as e:
            print(f"⚠️ JSON 파일 로드 실패: {e}")
            self._mail_data = {"value": []}
    
    def _clean_html_content(self, html_content: str) -> str:
        """HTML 태그 제거하여 텍스트만 추출"""
        if not html_content:
            return ""
        clean_text = re.sub('<.*?>', '', html_content)
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text.strip()
    
    def _format_email_info(self, mail_data: Dict[str, Any]) -> Dict[str, Any]:
        """메일 데이터를 표준 형식으로 변환"""
        sender_info = mail_data.get("from", mail_data.get("sender", {})).get("emailAddress", {})
        
        received_time = mail_data.get("receivedDateTime", "")
        if received_time:
            try:
                dt = datetime.fromisoformat(received_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                formatted_time = received_time
        else:
            formatted_time = "시간 정보 없음"
        
        body_preview = mail_data.get("bodyPreview", "")
        if len(body_preview) > 100:
            body_preview = body_preview[:100] + "..."
        
        return {
            "id": mail_data.get("id", ""),
            "subject": mail_data.get("subject", "제목 없음"),
            "sender": {
                "name": sender_info.get("name", "알 수 없음"),
                "email": sender_info.get("address", "")
            },
            "received_time": formatted_time,
            "is_read": mail_data.get("isRead", True),
            "importance": mail_data.get("importance", "normal"),
            "has_attachments": mail_data.get("hasAttachments", False),
            "body_preview": body_preview
        }
    
    def get_unread_emails(self, limit: int = 20) -> str:
        """안읽은 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return "📭 메일 데이터가 없습니다."
        
        unread_emails = []
        for mail_data in self._mail_data["value"]:
            if not mail_data.get("isRead", True):
                formatted_mail = self._format_email_info(mail_data)
                unread_emails.append(formatted_mail)
                if len(unread_emails) >= limit:
                    break
        
        if not unread_emails:
            return "📭 안읽은 메일이 없습니다!"
        
        result = f"📬 안읽은 메일 {len(unread_emails)}개를 찾았습니다:\n\n"
        
        for i, email in enumerate(unread_emails, 1):
            result += f"{i}. **{email['subject']}**\n"
            result += f"   📧 보낸이: {email['sender']['name']} ({email['sender']['email']})\n"
            result += f"   🕐 수신시간: {email['received_time']}\n"
            
            if email.get('importance') == 'high':
                result += f"   🔴 중요도: 높음\n"
            
            if email.get('has_attachments'):
                result += f"   📎 첨부파일 있음\n"
            
            if email.get('body_preview'):
                result += f"   💬 미리보기: {email['body_preview']}\n"
            
            result += "\n"
        
        return result
    
    def get_all_emails(self, limit: int = 50) -> str:
        """모든 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return "📭 메일 데이터가 없습니다."
        
        all_emails = []
        for mail_data in self._mail_data["value"][:limit]:
            formatted_mail = self._format_email_info(mail_data)
            all_emails.append(formatted_mail)
        
        if not all_emails:
            return "📭 조회할 메일이 없습니다."
        
        unread_count = sum(1 for email in all_emails if not email.get('is_read', True))
        read_count = len(all_emails) - unread_count
        
        result = f"📊 전체 메일 {len(all_emails)}개 (안읽음: {unread_count}개, 읽음: {read_count}개)\n\n"
        
        for i, email in enumerate(all_emails[:10], 1):
            status = "🟡" if not email.get('is_read', True) else "✅"
            result += f"{i}. {status} **{email['subject']}**\n"
            result += f"   📧 보낸이: {email['sender']['name']}\n"
            result += f"   🕐 수신시간: {email['received_time']}\n\n"
        
        if len(all_emails) > 10:
            result += f"... 외 {len(all_emails) - 10}개 메일\n"
        
        return result
    
    def search_emails(self, query: str, limit: int = 20) -> str:
        """메일 검색"""
        if not self._mail_data or "value" not in self._mail_data:
            return "📭 메일 데이터가 없습니다."
        
        if not query:
            return "❌ 검색 키워드를 입력해주세요."
        
        query_lower = query.lower()
        search_results = []
        
        for mail_data in self._mail_data["value"]:
            subject = mail_data.get("subject", "").lower()
            sender_name = mail_data.get("from", {}).get("emailAddress", {}).get("name", "").lower()
            sender_email = mail_data.get("from", {}).get("emailAddress", {}).get("address", "").lower()
            body_preview = mail_data.get("bodyPreview", "").lower()
            
            if (query_lower in subject or 
                query_lower in sender_name or 
                query_lower in sender_email or 
                query_lower in body_preview):
                
                formatted_mail = self._format_email_info(mail_data)
                search_results.append(formatted_mail)
                
                if len(search_results) >= limit:
                    break
        
        if not search_results:
            return f"🔍 '{query}' 검색 결과가 없습니다."
        
        result = f"🔍 '{query}' 검색 결과 {len(search_results)}개:\n\n"
        
        for i, email in enumerate(search_results, 1):
            status = "🟡" if not email.get('is_read', True) else "✅"
            result += f"{i}. {status} **{email['subject']}**\n"
            result += f"   📧 보낸이: {email['sender']['name']}\n"
            result += f"   🕐 수신시간: {email['received_time']}\n"
            
            if email.get('body_preview'):
                result += f"   💬 미리보기: {email['body_preview']}\n"
            
            result += "\n"
        
        return result
    
    def get_emails_by_sender(self, sender: str, limit: int = 20) -> str:
        """특정 발신자의 메일 조회"""
        if not self._mail_data or "value" not in self._mail_data:
            return "📭 메일 데이터가 없습니다."
        
        if not sender:
            return "❌ 발신자 정보를 입력해주세요."
        
        sender_lower = sender.lower()
        sender_emails = []
        
        for mail_data in self._mail_data["value"]:
            sender_info = mail_data.get("from", {}).get("emailAddress", {})
            sender_name = sender_info.get("name", "").lower()
            sender_email = sender_info.get("address", "").lower()
            
            if sender_lower in sender_name or sender_lower in sender_email:
                formatted_mail = self._format_email_info(mail_data)
                sender_emails.append(formatted_mail)
                
                if len(sender_emails) >= limit:
                    break
        
        if not sender_emails:
            return f"📭 '{sender}'에서 온 메일이 없습니다."
        
        result = f"📧 '{sender}'에서 온 메일 {len(sender_emails)}개:\n\n"
        
        for i, email in enumerate(sender_emails, 1):
            status = "🟡" if not email.get('is_read', True) else "✅"
            result += f"{i}. {status} **{email['subject']}**\n"
            result += f"   📧 보낸이: {email['sender']['name']} ({email['sender']['email']})\n"
            result += f"   🕐 수신시간: {email['received_time']}\n"
            
            if email.get('body_preview'):
                result += f"   💬 미리보기: {email['body_preview']}\n"
            
            result += "\n"
        
        return result

# 테스트 함수들
def test_simple_processor():
    """간단한 메일 처리기 테스트"""
    processor = SimpleMailProcessor()
    
    print("=== 안읽은 메일 테스트 ===")
    print(processor.get_unread_emails(limit=5))
    print()
    
    print("=== 전체 메일 테스트 ===") 
    print(processor.get_all_emails(limit=10))
    print()
    
    print("=== 메일 검색 테스트 ===")
    print(processor.search_emails("tasks", limit=5))
    print()
    
    print("=== 발신자별 메일 테스트 ===")
    print(processor.get_emails_by_sender("Microsoft", limit=5))
    print()

if __name__ == "__main__":
    test_simple_processor()