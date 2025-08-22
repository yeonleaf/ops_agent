#!/usr/bin/env python3
"""
실제 LLM 응답 테스트
"""

import json
from dotenv import load_dotenv
from langchain_mail_agent import MailAgent

load_dotenv()

def test_actual_response():
    """실제 LLM 응답 확인"""
    print("=== Azure OpenAI 에이전트 초기화 ===")
    try:
        agent = MailAgent(llm_provider="azure", model_name="gpt-4")
        print("✅ 에이전트 초기화 성공")
    except Exception as e:
        print(f"❌ 에이전트 초기화 실패: {e}")
        return
    
    print("\n=== 실제 질문 테스트 ===")
    test_questions = [
        "오늘 내가 처리해야 할 티켓 리스트를 보여줘",
        "처리해야 할 작업이 뭐가 있어?",
        "새로운 메일에서 티켓을 만들어야 할 게 있나?"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n--- 질문 {i}: {question} ---")
        try:
            response = agent.query(question)
            print("응답 길이:", len(response))
            print("응답 미리보기 (처음 200자):")
            print(response[:200] + "..." if len(response) > 200 else response)
            
            # JSON 포함 확인
            if "{" in response and "}" in response:
                print("✅ JSON 포함된 것 같음")
                
                # JSON 추출 시도
                try:
                    from langchain_chatbot_app import extract_ticket_data_from_response
                    extracted = extract_ticket_data_from_response(response)
                    if extracted:
                        print("✅ JSON 추출 성공")
                        data = json.loads(extracted)
                        if "tasks" in data:
                            print(f"📝 티켓 개수: {len(data['tasks'])}")
                        if "summary" in data:
                            print(f"📊 요약 정보: {data['summary']}")
                    else:
                        print("❌ JSON 추출 실패")
                except Exception as e:
                    print(f"❌ JSON 추출 중 오류: {e}")
            else:
                print("❌ JSON이 포함되지 않은 것 같음")
                
        except Exception as e:
            print(f"❌ 질문 처리 오류: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_actual_response()