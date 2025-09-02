#!/usr/bin/env python3
"""현재 티켓들의 레이블 상태 확인"""

import sqlite3
import json

def check_current_labels():
    """현재 티켓들의 레이블 상태를 확인합니다."""
    
    try:
        # SQLite 연결
        with sqlite3.connect("tickets.db") as conn:
            cursor = conn.cursor()
            
            print("🔍 현재 티켓 레이블 상태")
            print("=" * 50)
            
            # 모든 티켓의 레이블 조회
            cursor.execute("""
                SELECT ticket_id, title, labels, updated_at
                FROM tickets 
                ORDER BY ticket_id
            """)
            
            tickets = cursor.fetchall()
            
            if tickets:
                print(f"📋 총 {len(tickets)}개의 티켓:")
                for ticket in tickets:
                    ticket_id, title, labels_json, updated_at = ticket
                    labels = json.loads(labels_json) if labels_json else []
                    
                    print(f"\n  🎫 티켓 ID: {ticket_id}")
                    print(f"     제목: {title}")
                    print(f"     레이블: {labels}")
                    print(f"     업데이트: {updated_at}")
            else:
                print("📋 티켓이 없습니다.")
                
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    check_current_labels()
