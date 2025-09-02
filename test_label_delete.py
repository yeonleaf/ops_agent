#!/usr/bin/env python3
"""레이블 삭제 기능 테스트 스크립트"""

import sqlite3
import json
from datetime import datetime

def test_label_delete():
    """레이블 삭제 기능을 테스트합니다."""
    
    # SQLite 연결
    db_path = "tickets.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 현재 티켓과 레이블 상태 확인
            print("🔍 현재 티켓 상태:")
            cursor.execute("SELECT ticket_id, title, labels FROM tickets LIMIT 5")
            tickets = cursor.fetchall()
            
            for ticket in tickets:
                ticket_id, title, labels_json = ticket
                labels = json.loads(labels_json) if labels_json else []
                print(f"  티켓 ID: {ticket_id}, 제목: {title}, 레이블: {labels}")
            
            if not tickets:
                print("  티켓이 없습니다.")
                return
            
            # 첫 번째 티켓의 레이블 삭제 테스트
            test_ticket_id = tickets[0][0]
            test_labels = json.loads(tickets[0][2]) if tickets[0][2] else []
            
            if not test_labels:
                print(f"  티켓 {test_ticket_id}에 레이블이 없습니다.")
                return
            
            # 첫 번째 레이블 삭제
            label_to_delete = test_labels[0]
            new_labels = test_labels[1:]  # 첫 번째 레이블 제거
            
            print(f"\n🧪 레이블 삭제 테스트:")
            print(f"  티켓 ID: {test_ticket_id}")
            print(f"  삭제할 레이블: {label_to_delete}")
            print(f"  삭제 후 레이블: {new_labels}")
            
            # 레이블 업데이트
            labels_json = json.dumps(new_labels)
            current_time = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE tickets 
                SET labels = ?, updated_at = ?
                WHERE ticket_id = ?
            """, (labels_json, current_time, test_ticket_id))
            
            # 이벤트 기록
            cursor.execute("""
                INSERT INTO ticket_events (ticket_id, event_type, old_value, new_value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (test_ticket_id, "labels_change", label_to_delete, ', '.join(new_labels), current_time))
            
            conn.commit()
            print(f"  ✅ 레이블 삭제 완료!")
            
            # 업데이트 후 상태 확인
            cursor.execute("SELECT labels FROM tickets WHERE ticket_id = ?", (test_ticket_id,))
            result = cursor.fetchone()
            if result:
                updated_labels = json.loads(result[0]) if result[0] else []
                print(f"  🔍 업데이트 후 레이블: {updated_labels}")
                
                if label_to_delete not in updated_labels:
                    print(f"  ✅ 레이블 '{label_to_delete}' 삭제 성공!")
                else:
                    print(f"  ❌ 레이블 '{label_to_delete}' 삭제 실패!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    test_label_delete()
