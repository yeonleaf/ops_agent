#!/usr/bin/env python3
"""레이블 추가/삭제 기능과 user_action 기록 테스트"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_label_functions():
    """레이블 추가/삭제 기능을 테스트합니다."""
    
    try:
        # enhanced_ticket_ui에서 함수 가져오기
        from enhanced_ticket_ui import add_label_to_ticket, delete_label_from_ticket
        
        print("🔍 레이블 기능 테스트 시작")
        
        # 테스트할 티켓 ID
        test_ticket_id = 1
        
        print(f"\n🧪 테스트 1: 티켓 {test_ticket_id}에 새 레이블 추가")
        print("=" * 50)
        
        # 새 레이블 추가 테스트
        new_label = "테스트레이블"
        add_result = add_label_to_ticket(test_ticket_id, new_label)
        
        print(f"📊 레이블 추가 결과: {add_result}")
        
        if add_result:
            print("✅ 레이블 추가 성공!")
        else:
            print("❌ 레이블 추가 실패!")
        
        print(f"\n🧪 테스트 2: 티켓 {test_ticket_id}에서 레이블 삭제")
        print("=" * 50)
        
        # 레이블 삭제 테스트
        delete_result = delete_label_from_ticket(test_ticket_id, new_label)
        
        print(f"📊 레이블 삭제 결과: {delete_result}")
        
        if delete_result:
            print("✅ 레이블 삭제 성공!")
        else:
            print("❌ 레이블 삭제 실패!")
        
        print(f"\n🧪 테스트 3: user_action 테이블 확인")
        print("=" * 50)
        
        # user_action 테이블 확인
        try:
            from database_models import DatabaseManager
            db_manager = DatabaseManager()
            
            # 최근 user_action 조회
            cursor = db_manager.conn.cursor()
            cursor.execute("""
                SELECT action_type, action_description, old_value, new_value, created_at
                FROM user_actions 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            
            actions = cursor.fetchall()
            if actions:
                print("📋 최근 user_action 기록:")
                for action in actions:
                    action_type, description, old_val, new_val, created_at = action
                    print(f"  • {action_type}: {description}")
                    print(f"    이전값: {old_val}, 새값: {new_val}")
                    print(f"    시간: {created_at}")
                    print()
            else:
                print("📋 user_action 기록이 없습니다.")
                
        except Exception as e:
            print(f"❌ user_action 조회 실패: {str(e)}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    test_label_functions()
