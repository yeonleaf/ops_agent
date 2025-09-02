#!/usr/bin/env python3
"""티켓 4에 레이블 추가 테스트"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_add_label_to_ticket4():
    """티켓 4에 레이블을 추가합니다."""
    
    try:
        # enhanced_ticket_ui에서 함수 가져오기
        from enhanced_ticket_ui import add_label_to_ticket
        
        print("🔍 티켓 4에 레이블 추가 테스트")
        print("=" * 50)
        
        # 티켓 4에 새 레이블 추가
        ticket_id = 4
        new_label = "서버장애"
        
        print(f"🧪 테스트: 티켓 {ticket_id}에 레이블 '{new_label}' 추가")
        
        # 레이블 추가 실행
        result = add_label_to_ticket(ticket_id, new_label)
        
        print(f"📊 레이블 추가 결과: {result}")
        
        if result:
            print("✅ 레이블 추가 성공!")
            
            # 추가 후 상태 확인
            from sqlite_ticket_models import SQLiteTicketManager
            ticket_manager = SQLiteTicketManager()
            current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
            
            if current_ticket:
                print(f"🔍 추가 후 레이블: {current_ticket.labels}")
                if new_label in current_ticket.labels:
                    print(f"✅ 레이블 '{new_label}' 추가 확인됨!")
                else:
                    print(f"❌ 레이블 '{new_label}' 추가 실패!")
            else:
                print("❌ 티켓을 찾을 수 없음")
        else:
            print("❌ 레이블 추가 실패!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    test_add_label_to_ticket4()
