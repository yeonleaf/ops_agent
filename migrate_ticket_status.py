#!/usr/bin/env python3
"""
티켓 상태 마이그레이션 스크립트
new → pending으로 변경
"""

from database_models import DatabaseManager
import sqlite3
from datetime import datetime

def migrate_ticket_status():
    """티켓 상태를 new에서 pending으로 마이그레이션"""
    print("=== 티켓 상태 마이그레이션 시작 ===")
    
    # 1. 데이터베이스 관리자 초기화
    db_manager = DatabaseManager()
    
    # 2. 현재 상태 확인
    print("\n1. 마이그레이션 전 상태:")
    tickets = db_manager.get_all_tickets()
    
    status_counts_before = {}
    new_tickets = []
    
    for ticket in tickets:
        status = ticket.status
        status_counts_before[status] = status_counts_before.get(status, 0) + 1
        
        if status == "new":
            new_tickets.append(ticket)
            print(f"   ⚠️ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status} (변경 예정)")
        else:
            print(f"   ✅ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status}")
    
    print(f"\n📊 마이그레이션 전 상태별 개수:")
    for status, count in status_counts_before.items():
        print(f"   {status}: {count}개")
    
    if not new_tickets:
        print("\n✅ 변경할 티켓이 없습니다. 마이그레이션이 완료되었습니다.")
        return
    
    # 3. 마이그레이션 실행
    print(f"\n2. 마이그레이션 실행:")
    print(f"   변경할 티켓 수: {len(new_tickets)}개")
    
    try:
        with sqlite3.connect(db_manager.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
            updated_count = 0
            for ticket in new_tickets:
                try:
                    # 상태 업데이트
                    cursor.execute("""
                        UPDATE tickets 
                        SET status = ?, updated_at = ?
                        WHERE ticket_id = ?
                    """, ("pending", datetime.now().isoformat(), ticket.ticket_id))
                    
                    # 이벤트 기록
                    cursor.execute("""
                        INSERT INTO ticket_events (
                            ticket_id, event_type, old_value, new_value, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        ticket.ticket_id, 
                        "status_migration", 
                        "new", 
                        "pending", 
                        datetime.now().isoformat()
                    ))
                    
                    updated_count += 1
                    print(f"   ✅ 티켓 {ticket.ticket_id} 상태 변경: new → pending")
                    
                except Exception as e:
                    print(f"   ❌ 티켓 {ticket.ticket_id} 상태 변경 실패: {e}")
            
            # 커밋
            conn.commit()
            print(f"\n   🎯 총 {updated_count}개 티켓 상태 변경 완료")
            
    except Exception as e:
        print(f"   ❌ 마이그레이션 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 마이그레이션 후 상태 확인
    print(f"\n3. 마이그레이션 후 상태:")
    tickets_after = db_manager.get_all_tickets()
    
    status_counts_after = {}
    for ticket in tickets_after:
        status = ticket.status
        status_counts_after[status] = status_counts_after.get(status, 0) + 1
        
        if status == "new":
            print(f"   ❌ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status} (변경 실패)")
        else:
            print(f"   ✅ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status}")
    
    print(f"\n📊 마이그레이션 후 상태별 개수:")
    for status, count in status_counts_after.items():
        print(f"   {status}: {count}개")
    
    print("\n=== 마이그레이션 완료 ===")

if __name__ == "__main__":
    migrate_ticket_status()
