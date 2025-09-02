#!/usr/bin/env python3
"""
수정된 상태 체계 테스트
"""

from ticket_workflow_tools import process_todays_tasks
from database_models import DatabaseManager
import json

def test_status_system():
    """수정된 상태 체계 테스트"""
    print("=== 수정된 상태 체계 테스트 ===")
    
    # 1. 데이터베이스 관리자 초기화
    db_manager = DatabaseManager()
    
    # 2. 현재 티켓 상태 확인
    print("\n1. 현재 티켓 상태:")
    tickets = db_manager.get_all_tickets()
    
    status_counts = {}
    for ticket in tickets:
        status = ticket.status
        status_counts[status] = status_counts.get(status, 0) + 1
        
        if status == "new":  # new 상태가 있으면 경고
            print(f"   ⚠️ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status} (수정 필요)")
        else:
            print(f"   ✅ 티켓 {ticket.ticket_id}: {ticket.title} - 상태: {status}")
    
    print(f"\n📊 상태별 개수:")
    for status, count in status_counts.items():
        print(f"   {status}: {count}개")
    
    # 3. process_todays_tasks 실행 테스트
    print(f"\n2. process_todays_tasks 실행 테스트:")
    try:
        current_result = ""
        for chunk in process_todays_tasks.stream({}):
            current_result += chunk
        
        print(f"   📊 결과 길이: {len(current_result)}")
        
        # JSON 파싱
        try:
            parsed = json.loads(current_result)
            print(f"   ✅ JSON 파싱 성공")
            print(f"   📊 요약: {parsed.get('summary', {})}")
            print(f"   📝 작업 수: {len(parsed.get('tasks', []))}")
            
            if parsed.get('tasks'):
                print(f"\n🎫 작업 목록:")
                for i, task in enumerate(parsed['tasks'][:5], 1):  # 상위 5개만
                    print(f"  {i}. {task.get('type', 'N/A')}")
                    print(f"     제목: {task.get('title', 'N/A')}")
                    print(f"     상태: {task.get('status', 'N/A')}")
                    if 'labels' in task:
                        print(f"     레이블: {task.get('labels', [])}")
                    print()
            else:
                print("   ❌ 작업 목록이 비어있음")
                
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON 파싱 실패: {e}")
            print(f"   원본 결과: {current_result}")
        
    except Exception as e:
        print(f"   ❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_status_system()
