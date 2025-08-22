#!/usr/bin/env python3
"""
process_todays_tasks 도구 문제 진단
"""

import json
from ticket_workflow_tools import process_todays_tasks, get_todays_unread_emails
from database_models import DatabaseManager

def test_basic_functions():
    """기본 기능 테스트"""
    print("=== 기본 기능 테스트 ===")
    
    # 1. JSON 파일 읽기 테스트
    try:
        with open("sample_mail_response.json", 'r', encoding='utf-8') as f:
            mail_data = json.load(f)
        print(f"✅ JSON 파일 읽기 성공: {len(mail_data.get('value', []))}개 메일")
        
        # 안읽은 메일 수 확인
        unread_count = len([m for m in mail_data.get("value", []) if not m.get("isRead", True)])
        print(f"📧 안읽은 메일: {unread_count}개")
        
    except Exception as e:
        print(f"❌ JSON 파일 읽기 실패: {e}")
        return
    
    # 2. 데이터베이스 연결 테스트
    try:
        db_manager = DatabaseManager()
        all_tickets = db_manager.get_all_tickets()
        print(f"✅ DB 연결 성공: {len(all_tickets)}개 티켓")
        
        # 티켓 상태별 개수
        status_counts = {}
        for ticket in all_tickets:
            status = ticket.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("📊 티켓 상태별 개수:")
        for status, count in status_counts.items():
            print(f"  - {status}: {count}개")
            
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return
    
    # 3. 개별 도구 테스트
    print("\n=== 개별 도구 테스트 ===")
    
    try:
        print("1. get_todays_unread_emails:")
        result = get_todays_unread_emails.invoke({})
        print(f"   결과 길이: {len(result)}")
        print(f"   결과 미리보기: {result[:100]}...")
        
    except Exception as e:
        print(f"   ❌ 오류: {e}")
    
    try:
        print("\n2. process_todays_tasks:")
        result = process_todays_tasks.invoke({})
        print(f"   결과 길이: {len(result)}")
        print(f"   결과 미리보기: {result[:200]}...")
        
        # JSON 파싱 테스트
        try:
            parsed = json.loads(result)
            print(f"   ✅ JSON 파싱 성공")
            print(f"   📊 요약: {parsed.get('summary', {})}")
            print(f"   📝 작업 수: {len(parsed.get('tasks', []))}")
            
            if parsed.get('tasks'):
                print("   🎫 첫 번째 작업:")
                first_task = parsed['tasks'][0]
                for key, value in first_task.items():
                    print(f"     {key}: {value}")
            else:
                print("   ❌ 작업 목록이 비어있음")
                
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON 파싱 실패: {e}")
            print(f"   원본 결과: {result}")
        
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    test_basic_functions() 