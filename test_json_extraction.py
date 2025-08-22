#!/usr/bin/env python3
"""
JSON 추출 로직 테스트
"""

import json
from langchain_chatbot_app import extract_ticket_data_from_response, is_ticket_response, is_valid_ticket_data

def test_json_extraction():
    # 실제 응답 예시 (유저가 보고한 형태)
    sample_response = """오늘 처리해야 할 티켓 리스트입니다!

총 5개의 티켓이 준비되어 있습니다.

[티켓 #1] You have upcoming tasks due
상태: closed
우선순위: High
생성일: 2025-08-17
[티켓 #3] Test Email
상태: new
우선순위: Medium
생성일: 2025-08-17
[티켓 #4] You have late tasks
상태: new
우선순위: High
생성일: 2025-08-18
[티켓 #2] (제목 없음)
상태: new
우선순위: Medium
생성일: 2025-08-17
[티켓 #5] You have late tasks
상태: new
우선순위: High
생성일: 2025-08-18"""
    
    # JSON 포함된 응답 예시
    json_response = """오늘 처리해야 할 티켓 리스트입니다!

{
  "summary": {
    "total_unread_emails": 10,
    "new_tickets_created": 2,
    "existing_tickets_found": 3,
    "total_tasks": 5
  },
  "tasks": [
    {
      "type": "existing_ticket",
      "ticket_id": 1,
      "title": "You have upcoming tasks due",
      "status": "closed",
      "priority": "High",
      "created_at": "2025-08-17T16:42:04.266353",
      "action": "조회됨"
    },
    {
      "type": "existing_ticket",
      "ticket_id": 3,
      "title": "Test Email",
      "status": "new",
      "priority": "Medium",
      "created_at": "2025-08-17T21:31:26.213080",
      "action": "조회됨"
    }
  ],
  "message": "오늘 처리해야 할 작업 5개가 준비되었습니다."
}

총 5개의 티켓이 준비되어 있습니다!"""
    
    print("=== 테스트 1: 일반 텍스트 응답 ===")
    print("티켓 응답인가?", is_ticket_response(sample_response))
    extracted = extract_ticket_data_from_response(sample_response)
    print("추출된 JSON:", extracted)
    
    print("\n=== 테스트 2: JSON 포함된 응답 ===")
    print("티켓 응답인가?", is_ticket_response(json_response))
    extracted = extract_ticket_data_from_response(json_response)
    print("추출된 JSON:", extracted is not None)
    
    if extracted:
        try:
            data = json.loads(extracted)
            print("유효한 티켓 데이터인가?", is_valid_ticket_data(data))
            print("tasks 개수:", len(data.get("tasks", [])))
        except json.JSONDecodeError as e:
            print("JSON 파싱 에러:", e)
    
    print("\n=== 테스트 3: 유효성 검사 ===")
    valid_data = {
        "summary": {"total_tasks": 2},
        "tasks": [
            {"ticket_id": 1, "title": "Test", "status": "new"},
            {"ticket_id": 2, "title": "Test2", "status": "pending"}
        ]
    }
    print("유효한 데이터인가?", is_valid_ticket_data(valid_data))
    
    invalid_data = {"other": "data"}
    print("잘못된 데이터인가?", is_valid_ticket_data(invalid_data))

if __name__ == "__main__":
    test_json_extraction()