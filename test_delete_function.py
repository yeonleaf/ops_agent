#!/usr/bin/env python3
"""delete_label_from_ticket 함수 직접 테스트"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_delete_function():
    """delete_label_from_ticket 함수를 직접 테스트합니다."""
    
    try:
        # enhanced_ticket_ui에서 함수 가져오기
        from enhanced_ticket_ui import delete_label_from_ticket
        
        print("🔍 delete_label_from_ticket 함수 테스트 시작")
        
        # 티켓 ID 1에서 'Batch' 레이블 삭제 테스트 (실제로 존재하는 레이블)
        ticket_id = 1
        label_to_delete = "Batch"
        
        print(f"🧪 테스트: 티켓 {ticket_id}에서 레이블 '{label_to_delete}' 삭제")
        
        # 함수 실행
        result = delete_label_from_ticket(ticket_id, label_to_delete)
        
        print(f"📊 결과: {result}")
        
        if result:
            print("✅ 레이블 삭제 성공!")
            
            # 삭제 후 상태 확인
            from sqlite_ticket_models import SQLiteTicketManager
            ticket_manager = SQLiteTicketManager()
            current_ticket = ticket_manager.get_ticket_by_id(ticket_id)
            
            if current_ticket:
                print(f"🔍 삭제 후 레이블: {current_ticket.labels}")
                if label_to_delete not in current_ticket.labels:
                    print(f"✅ 레이블 '{label_to_delete}' 삭제 확인됨!")
                else:
                    print(f"❌ 레이블 '{label_to_delete}' 여전히 존재!")
            else:
                print("❌ 티켓을 찾을 수 없음")
        else:
            print("❌ 레이블 삭제 실패!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    test_delete_function()
