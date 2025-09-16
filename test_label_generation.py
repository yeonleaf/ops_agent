#!/usr/bin/env python3
"""
LLM 기반 레이블 생성 로직 테스트
"""

import sys
import logging
from memory_based_ticket_processor import create_memory_based_ticket_processor
from mem0_memory_adapter import create_mem0_memory, add_ticket_event

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_llm_label_generation():
    """LLM 기반 레이블 생성 테스트"""
    print("🧪 LLM 기반 레이블 생성 테스트 시작")
    
    try:
        # Memory-Based Ticket Processor 생성
        processor = create_memory_based_ticket_processor()
        print("✅ Memory-Based Ticket Processor 생성 완료")
        
        # 테스트 이메일 데이터
        test_emails = [
            {
                "subject": "서버 접속 불가 긴급 수정 요청",
                "sender": "developer@company.com",
                "body": "NCMS API 서버에 접속이 안 됩니다. 긴급히 확인 부탁드립니다."
            },
            {
                "subject": "새로운 기능 개발 요청",
                "sender": "product@company.com", 
                "body": "사용자 인증 시스템에 MFA 기능을 추가해주세요."
            },
            {
                "subject": "DB 성능 개선 요청",
                "sender": "dba@company.com",
                "body": "Oracle 데이터베이스 쿼리 성능이 느려서 개선이 필요합니다."
            }
        ]
        
        # 각 이메일에 대해 LLM 레이블 분석
        for i, email in enumerate(test_emails, 1):
            print(f"\n🔍 테스트 이메일 {i}: '{email['subject']}'")
            
            try:
                # LLM을 사용하여 레이블 생성
                email_content = f"제목: {email['subject']}\n발신자: {email['sender']}\n내용: {email['body']}"
                
                llm_response = processor._run(
                    email_content=email_content,
                    email_subject=email['subject'],
                    email_sender=email['sender'],
                    message_id=f"test_msg_{i}"
                )
                
                # 응답 파싱
                import json
                llm_data = json.loads(llm_response)
                
                if llm_data.get('success'):
                    reasoning_data = llm_data.get('workflow_steps', {}).get('reasoning', {})
                    decision_data = reasoning_data.get('ticket_creation_decision', {})
                    
                    # fallback: workflow_steps가 없으면 최상위 decision 사용
                    if not decision_data:
                        decision_data = llm_data.get('decision', {}).get('ticket_creation_decision', {})
                    
                    decision = decision_data.get('decision', 'create_ticket')
                    reason = decision_data.get('reason', 'AI 판단 완료')
                    confidence = decision_data.get('confidence', 0.5)
                    priority = decision_data.get('priority', 'Medium')
                    labels = decision_data.get('labels', [])
                    ticket_type = decision_data.get('ticket_type', 'Task')
                    
                    print(f"  ✅ LLM 분석 완료:")
                    print(f"     결정: {decision}")
                    print(f"     이유: {reason}")
                    print(f"     신뢰도: {confidence}")
                    print(f"     우선순위: {priority}")
                    print(f"     레이블: {labels}")
                    print(f"     티켓 타입: {ticket_type}")
                    
                else:
                    print(f"  ❌ LLM 분석 실패: {llm_data.get('error', 'Unknown error')}")
                    
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON 파싱 실패: {e}")
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
        
        print("\n✅ LLM 기반 레이블 생성 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_llm_label_generation()
    sys.exit(0 if success else 1)
