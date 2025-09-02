#!/usr/bin/env python3
"""
레이블 업데이트 테스트 스크립트
"""

import json
from sqlite_ticket_models import SQLiteTicketManager
from vector_db_models import VectorDBManager

def test_label_update():
    """레이블 업데이트 테스트"""
    print("=== 레이블 업데이트 테스트 ===")
    
    # 1. SQLite 티켓 관리자 초기화
    sqlite_manager = SQLiteTicketManager()
    
    # 2. 현재 티켓 상태 확인
    print("\n1. 현재 티켓 상태:")
    tickets = sqlite_manager.get_all_tickets()
    for ticket in tickets[:3]:  # 상위 3개만
        print(f"   티켓 {ticket.ticket_id}: {ticket.title}")
        print(f"   레이블: {ticket.labels}")
        print(f"   메일 ID: {ticket.original_message_id}")
        print()
    
    # 3. 첫 번째 티켓에 "NCMS_운영지원" 레이블 추가
    if tickets:
        first_ticket = tickets[0]
        old_labels = first_ticket.labels.copy()
        new_labels = old_labels + ["NCMS_운영지원"]
        
        print(f"2. 티켓 {first_ticket.ticket_id} 레이블 업데이트:")
        print(f"   이전: {old_labels}")
        print(f"   새로운: {new_labels}")
        
        # 레이블 업데이트
        sqlite_manager.update_ticket_labels(
            first_ticket.ticket_id, 
            new_labels, 
            old_labels
        )
        
        # 4. 업데이트 후 확인
        print("\n3. 업데이트 후 확인:")
        updated_ticket = sqlite_manager.get_ticket_by_id(first_ticket.ticket_id)
        if updated_ticket:
            print(f"   업데이트된 레이블: {updated_ticket.labels}")
        
        # 5. VectorDB 동기화 확인
        print("\n4. VectorDB 동기화 확인:")
        try:
            vector_db = VectorDBManager()
            mail = vector_db.get_mail_by_id(first_ticket.original_message_id)
            if mail:
                print(f"   VectorDB 메일 ID: {mail.message_id}")
                print(f"   VectorDB key_points: {mail.key_points}")
            else:
                print(f"   ⚠️ VectorDB에서 메일을 찾을 수 없음: {first_ticket.original_message_id}")
        except Exception as e:
            print(f"   ❌ VectorDB 확인 중 오류: {e}")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_label_update()
