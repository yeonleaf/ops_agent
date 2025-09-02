#!/usr/bin/env python3
"""process_emails_with_ticket_logic 함수 직접 테스트"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_process_emails():
    """process_emails_with_ticket_logic 함수를 테스트합니다."""
    
    try:
        # unified_email_service에서 함수 가져오기
        from unified_email_service import process_emails_with_ticket_logic
        
        print("🔍 process_emails_with_ticket_logic 함수 테스트")
        print("=" * 50)
        
        # "오늘 처리할 티켓 목록" 쿼리로 테스트
        user_query = "오늘 처리할 티켓 목록"
        
        print(f"🧪 테스트: user_query='{user_query}'")
        
        # 함수 실행
        result = process_emails_with_ticket_logic("gmail", user_query)
        
        print(f"📊 결과 타입: {type(result)}")
        print(f"📊 display_mode: {result.get('display_mode')}")
        print(f"📊 티켓 수: {len(result.get('tickets', []))}")
        print(f"📊 메시지: {result.get('message')}")
        
        # 티켓 상세 정보 출력
        tickets = result.get('tickets', [])
        if tickets:
            print(f"\n📋 티켓 상세 정보 ({len(tickets)}개):")
            for i, ticket in enumerate(tickets):
                print(f"\n  {i+1}. 티켓 ID: {ticket.get('ticket_id')}")
                print(f"     제목: {ticket.get('title')}")
                print(f"     레이블: {ticket.get('labels')}")
                print(f"     상태: {ticket.get('status')}")
                print(f"     우선순위: {ticket.get('priority')}")
                print(f"     생성일: {ticket.get('created_at')}")
                print(f"     업데이트: {ticket.get('updated_at')}")
        else:
            print("\n📋 티켓이 없습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        print(f"❌ 오류 상세: {traceback.format_exc()}")

if __name__ == "__main__":
    test_process_emails()
