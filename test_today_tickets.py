#!/usr/bin/env python3
"""
오늘 처리할 티켓 조회 테스트
"""

from ticket_workflow_tools import process_todays_tasks

def test_today_tickets():
    """오늘 처리할 티켓 조회 테스트"""
    print("=== 오늘 처리할 티켓 조회 테스트 ===")
    
    try:
        print("🔍 process_todays_tasks() 실행 중...")
        
        # 스트리밍으로 결과 수집
        current_result = ""
        for chunk in process_todays_tasks.stream({}):
            current_result += chunk
        
        print(f"\n📊 결과 길이: {len(current_result)}")
        print("📝 결과 내용:")
        print(current_result)
        
        # JSON 파싱 시도
        import json
        try:
            parsed = json.loads(current_result)
            print(f"\n✅ JSON 파싱 성공")
            print(f"📊 요약: {parsed.get('summary', {})}")
            print(f"📝 작업 수: {len(parsed.get('tasks', []))}")
            
            if parsed.get('tasks'):
                print("\n🎫 작업 목록:")
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
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_today_tickets()
