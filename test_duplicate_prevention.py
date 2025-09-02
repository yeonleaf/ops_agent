#!/usr/bin/env python3
"""
중복 생성 방지 로직 테스트
"""

from ticket_workflow_tools import check_ticket_exists, create_ticket_from_email
from database_models import DatabaseManager
import json

def test_duplicate_prevention():
    """중복 생성 방지 로직 테스트"""
    print("=== 중복 생성 방지 로직 테스트 ===")
    
    # 1. 데이터베이스 관리자 초기화
    db_manager = DatabaseManager()
    
    # 2. 현재 티켓 상태 확인
    print("\n1. 현재 티켓 상태:")
    tickets = db_manager.get_all_tickets()
    for ticket in tickets[:5]:  # 상위 5개만
        print(f"   티켓 {ticket.ticket_id}: {ticket.title}")
        print(f"   상태: {ticket.status}")
        print(f"   메일 ID: {ticket.original_message_id}")
        print(f"   레이블: {ticket.labels}")
        print()
    
    # 3. 특정 메일 ID로 중복 체크 테스트
    if tickets:
        test_message_id = tickets[0].original_message_id
        print(f"2. 메일 ID '{test_message_id}' 중복 체크:")
        
        # check_ticket_exists 함수 테스트
        result = check_ticket_exists.invoke({"message_id": test_message_id})
        print(f"   check_ticket_exists 결과: {result}")
        
        # JSON 파싱
        try:
            parsed = json.loads(result)
            if parsed.get("exists"):
                print(f"   ✅ 중복 확인: 티켓 {parsed.get('ticket_id')} 존재")
            else:
                print(f"   ❌ 중복 확인: 티켓 없음")
        except json.JSONDecodeError:
            print(f"   ❌ JSON 파싱 실패")
        
        # 4. 동일한 메일로 티켓 생성 시도 (중복 방지 테스트)
        print(f"\n3. 동일한 메일로 티켓 생성 시도 (중복 방지 테스트):")
        result = create_ticket_from_email.invoke({"message_id": test_message_id})
        print(f"   create_ticket_from_email 결과: {result}")
        
        if "이미 티켓이 존재합니다" in result:
            print("   ✅ 중복 방지 로직 정상 작동")
        else:
            print("   ❌ 중복 방지 로직 문제")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_duplicate_prevention()
