#!/usr/bin/env python3
"""
Mem0 통합 테스트 스크립트

mem0 라이브러리를 사용한 메모리 시스템이 제대로 작동하는지 테스트
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_mem0_adapter():
    """Mem0Memory 어댑터 기본 기능 테스트"""
    print("🧪 Mem0Memory 어댑터 테스트 시작")
    
    try:
        from mem0_memory_adapter import create_mem0_memory, add_ticket_event, search_related_memories
        
        # Mem0Memory 인스턴스 생성
        print("📝 Mem0Memory 인스턴스 생성...")
        mem0_memory = create_mem0_memory("test_user")
        
        # 테스트 이벤트 추가
        print("📝 테스트 이벤트 추가...")
        event_id1 = add_ticket_event(
            memory=mem0_memory,
            event_type="label_updated",
            description="사용자가 티켓 #123의 라벨을 '버그'에서 '개선사항'으로 수정함",
            ticket_id="123",
            old_value="버그",
            new_value="개선사항"
        )
        
        event_id2 = add_ticket_event(
            memory=mem0_memory,
            event_type="ticket_created",
            description="AI가 '서버 오류' 이메일로부터 티켓 #124를 생성함",
            ticket_id="124",
            message_id="msg_456"
        )
        
        # 메모리 검색 테스트
        print("🔍 메모리 검색 테스트...")
        search_results = search_related_memories(
            memory=mem0_memory,
            email_content="서버 접속 오류가 발생했습니다",
            limit=3
        )
        
        print(f"검색 결과: {len(search_results)}개")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. {result['memory']} (점수: {result['score']:.3f})")
        
        # 통계 조회
        print("📊 메모리 통계...")
        stats = mem0_memory.get_memory_stats()
        print(f"총 메모리 수: {stats['total_memories']}")
        print(f"액션 타입별: {stats['action_types']}")
        
        print("✅ Mem0Memory 어댑터 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ Mem0Memory 어댑터 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_memory_based_processor():
    """MemoryBasedTicketProcessorTool의 mem0 통합 테스트"""
    print("\n🧪 MemoryBasedTicketProcessorTool mem0 통합 테스트 시작")
    
    try:
        from memory_based_ticket_processor import create_memory_based_ticket_processor
        
        # 프로세서 인스턴스 생성
        print("📝 MemoryBasedTicketProcessorTool 인스턴스 생성...")
        processor = create_memory_based_ticket_processor()
        
        # 테스트 이메일 데이터
        test_email_data = {
            "email_content": "서버 접속 오류가 발생했습니다. NCMS 시스템에 로그인이 안 됩니다.",
            "email_subject": "NCMS 서버 접속 오류",
            "email_sender": "user@company.com",
            "message_id": "test_msg_001"
        }
        
        print("🔍 테스트 이메일 처리...")
        print(f"  제목: {test_email_data['email_subject']}")
        print(f"  발신자: {test_email_data['email_sender']}")
        print(f"  내용: {test_email_data['email_content'][:50]}...")
        
        # 프로세서 실행
        result_json = processor._run(
            email_content=test_email_data["email_content"],
            email_subject=test_email_data["email_subject"],
            email_sender=test_email_data["email_sender"],
            message_id=test_email_data["message_id"]
        )
        
        # 결과 파싱 및 출력
        import json
        result = json.loads(result_json)
        
        if result.get('success'):
            print("✅ 프로세서 실행 성공")
            
            # 워크플로우 단계별 결과 출력
            workflow_steps = result.get('workflow_steps', {})
            
            # 1단계: 검색 결과
            retrieval = workflow_steps.get('retrieval', {})
            print(f"  🔍 검색 단계: {retrieval.get('search_summary', {}).get('related_memories_count', 0)}개 관련 기억 발견")
            
            # 2단계: 추론 결과
            reasoning = workflow_steps.get('reasoning', {})
            decision = reasoning.get('ticket_creation_decision', {})
            print(f"  🧠 추론 단계: {decision.get('decision', 'unknown')} (신뢰도: {decision.get('confidence', 0.0)})")
            print(f"  📋 추천 레이블: {decision.get('labels', [])}")
            
            # 3단계: 실행 결과
            action = workflow_steps.get('action', {})
            print(f"  ⚡ 실행 단계: {action.get('action_taken', 'unknown')}")
            
        else:
            print(f"❌ 프로세서 실행 실패: {result.get('error', '알 수 없는 오류')}")
            return False
        
        print("✅ MemoryBasedTicketProcessorTool mem0 통합 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ MemoryBasedTicketProcessorTool 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_user_correction():
    """사용자 피드백 기록 테스트"""
    print("\n🧪 사용자 피드백 기록 테스트 시작")
    
    try:
        from memory_based_ticket_processor import record_user_correction
        
        # 사용자 피드백 기록
        print("📝 사용자 피드백 기록...")
        success = record_user_correction(
            ticket_id="123",
            old_label="버그",
            new_label="개선사항",
            user_id="test_user"
        )
        
        if success:
            print("✅ 사용자 피드백 기록 성공")
        else:
            print("❌ 사용자 피드백 기록 실패")
            return False
        
        # 기록된 피드백 검색 테스트
        print("🔍 기록된 피드백 검색 테스트...")
        from mem0_memory_adapter import create_mem0_memory, search_related_memories
        
        mem0_memory = create_mem0_memory("test_user")
        search_results = search_related_memories(
            memory=mem0_memory,
            email_content="버그 수정 요청",
            limit=3
        )
        
        print(f"검색 결과: {len(search_results)}개")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. {result['memory']} (점수: {result['score']:.3f})")
        
        print("✅ 사용자 피드백 기록 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ 사용자 피드백 기록 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Mem0 통합 테스트 시작")
    print("=" * 50)
    
    # 환경 변수 확인
    print("🔧 환경 변수 확인...")
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_NAME", 
        "AZURE_OPENAI_API_KEY"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ 누락된 환경 변수: {missing_vars}")
        print("   일부 테스트가 실패할 수 있습니다.")
    else:
        print("✅ 모든 필수 환경 변수가 설정되어 있습니다.")
    
    print()
    
    # 테스트 실행
    test_results = []
    
    # 1. Mem0Memory 어댑터 테스트
    test_results.append(("Mem0Memory 어댑터", test_mem0_adapter()))
    
    # 2. MemoryBasedTicketProcessorTool 테스트
    test_results.append(("MemoryBasedTicketProcessorTool", test_memory_based_processor()))
    
    # 3. 사용자 피드백 기록 테스트
    test_results.append(("사용자 피드백 기록", test_user_correction()))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 모든 테스트가 통과했습니다!")
        print("✅ mem0 통합이 성공적으로 완료되었습니다.")
    else:
        print("⚠️ 일부 테스트가 실패했습니다.")
        print("   환경 변수 설정이나 mem0 라이브러리 설치를 확인해주세요.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
