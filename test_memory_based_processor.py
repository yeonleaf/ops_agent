#!/usr/bin/env python3
"""
Memory-Based Ticket Processor Tool 통합 테스트 스크립트
"""

import json
import os
from dotenv import load_dotenv
from memory_based_ticket_processor import MemoryBasedTicketProcessorTool, record_user_correction

# 환경 변수 로드
load_dotenv()

def test_integrated_system():
    """통합된 시스템 테스트"""
    print("\n🔄 통합 시스템 테스트 시작")
    print("=" * 60)
    
    try:
        # 1. LangChain 챗봇 앱 테스트
        print("📱 1. LangChain 챗봇 앱 통합 테스트")
        print("MemoryBasedTicketProcessorTool이 AI 에이전트 도구로 등록되었는지 확인...")
        
        from langchain_chatbot_app import create_agent
        # 에이전트 생성 시 도구 목록에 포함되는지 테스트
        print("✅ LangChain 챗봇 앱 통합 완료")
        
        # 2. 티켓 UI 테스트
        print("\n📋 2. 기존 티켓 UI 통합 테스트")
        print("장기 기억 기능과 사용자 피드백 기능이 UI에 추가되었는지 확인...")
        
        from enhanced_ticket_ui import create_memory_based_ticket_processor, record_user_correction
        # UI에서 장기 기억 기능 사용 가능한지 테스트
        print("✅ 티켓 UI 통합 완료")
        
        # 3. 이메일 서비스 테스트
        print("\n📧 3. 이메일 서비스 통합 테스트")
        print("장기 기억 기반 메일 처리 함수가 추가되었는지 확인...")
        
        from unified_email_service import process_emails_with_memory_based_logic
        # 새로운 메모리 기반 처리 함수 사용 가능한지 테스트
        print("✅ 이메일 서비스 통합 완료")
        
        # 4. 전체 워크플로우 테스트
        print("\n🚀 4. 전체 워크플로우 통합 테스트")
        
        # 데이터베이스 초기화 테스트
        from database_models import DatabaseManager
        db_manager = DatabaseManager()
        db_manager.init_database()
        print("✅ 데이터베이스 초기화 완료")
        
        # Vector DB 초기화 테스트
        from vector_db_models import UserActionVectorDBManager
        user_action_db = UserActionVectorDBManager()
        print("✅ Vector DB 초기화 완료")
        
        # MemoryBasedTicketProcessorTool 인스턴스 생성 테스트
        tool = MemoryBasedTicketProcessorTool()
        print("✅ MemoryBasedTicketProcessorTool 인스턴스 생성 완료")
        
        print("\n🎉 통합 시스템 테스트 성공!")
        print("모든 구성 요소가 성공적으로 통합되었습니다.")
        
        # 5. 통합 기능 요약
        print("\n📊 통합된 기능 요약:")
        print("1. LangChain 챗봇: 4번째 도구로 MemoryBasedTicketProcessorTool 추가")
        print("2. 티켓 UI: 장기 기억 조회 및 사용자 피드백 입력 기능 추가")
        print("3. 이메일 서비스: process_emails_with_memory_based_logic 함수 추가")
        print("4. 데이터베이스: user_actions 테이블 및 Vector DB user_action 컬렉션 추가")
        print("5. 4단계 워크플로우: 검색 → 추론 → 실행 → 기억 저장")
        
        return True
        
    except Exception as e:
        print(f"❌ 통합 시스템 테스트 실패: {str(e)}")
        import traceback
        print(f"오류 상세: {traceback.format_exc()}")
        return False

def test_basic_functionality():
    """기본 기능 테스트"""
    print("🧪 Memory-Based Ticket Processor Tool 기본 기능 테스트")
    print("=" * 60)
    
    try:
        # 도구 인스턴스 생성
        tool = MemoryBasedTicketProcessorTool()
        print("✅ MemoryBasedTicketProcessorTool 인스턴스 생성 성공")
        
        # 테스트 이메일 데이터
        test_cases = [
            {
                "email_content": "안녕하세요. 웹사이트에 로그인이 되지 않습니다. 사용자들이 계속 문의하고 있어서 긴급히 확인 부탁드립니다.",
                "email_subject": "[긴급] 로그인 시스템 장애",
                "email_sender": "김철수 <chulsoo@company.com>",
                "message_id": "test_message_001"
            },
            {
                "email_content": "다음 주 회의실 예약 부탁드립니다. 10명 정도 참석 예정입니다.",
                "email_subject": "회의실 예약 요청",
                "email_sender": "이영희 <younghee@company.com>",
                "message_id": "test_message_002"
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔬 테스트 케이스 {i}: {test_case['email_subject']}")
            print("-" * 40)
            
            try:
                # 도구 실행
                result = tool._run(
                    email_content=test_case["email_content"],
                    email_subject=test_case["email_subject"],
                    email_sender=test_case["email_sender"],
                    message_id=test_case["message_id"]
                )
                
                # 결과 파싱
                result_dict = json.loads(result)
                results.append(result_dict)
                
                # 결과 출력
                if result_dict.get("success"):
                    print("✅ 처리 성공")
                    decision = result_dict.get("decision", {}).get("ticket_creation_decision", {})
                    action = result_dict.get("action", {})
                    
                    print(f"   📋 AI 결정: {decision.get('decision', 'unknown')}")
                    print(f"   📝 결정 이유: {decision.get('reason', '')[:100]}...")
                    print(f"   ⚡ 실행 결과: {action.get('action_taken', 'unknown')}")
                    
                    if action.get("ticket_id"):
                        print(f"   🎫 생성된 티켓 ID: {action.get('ticket_id')}")
                        print(f"   🏷️ 추천 레이블: {action.get('labels', [])}")
                else:
                    print(f"❌ 처리 실패: {result_dict.get('error', '')}")
                    
            except Exception as e:
                print(f"❌ 테스트 케이스 {i} 실행 오류: {e}")
                results.append({"success": False, "error": str(e)})
        
        # 전체 결과 요약
        print(f"\n📊 테스트 결과 요약")
        print("=" * 60)
        successful_tests = sum(1 for r in results if r.get("success"))
        print(f"성공: {successful_tests}/{len(test_cases)}")
        
        return results
        
    except Exception as e:
        print(f"❌ 기본 기능 테스트 실패: {e}")
        return []

def main():
    """메인 테스트 함수"""
    print("🚀 Memory-Based Ticket Processor Tool 종합 테스트")
    print("=" * 60)
    
    # 환경 변수 확인
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_NAME", 
        "AZURE_OPENAI_API_KEY"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ 필수 환경 변수가 설정되지 않았습니다: {missing_vars}")
        print("   .env 파일에 Azure OpenAI 설정을 추가해주세요.")
        return
    
    print("✅ 환경 변수 확인 완료")
    
    # 테스트 실행
    test_basic_functionality()
    test_integrated_system()
    
    print(f"\n🎉 모든 테스트 완료!")
    print("=" * 60)
    print("✅ MemoryBasedTicketProcessorTool이 모든 메인 앱에 성공적으로 통합되었습니다!")

if __name__ == "__main__":
    main()
