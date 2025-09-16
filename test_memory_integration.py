#!/usr/bin/env python3
"""
Memory 통합 테스트 스크립트
mem0와 IntegratedMailClassifier의 연동을 테스트
"""

from integrated_mail_classifier import IntegratedMailClassifier, TicketCreationStatus
from datetime import datetime

def test_memory_integration():
    """mem0 메모리 통합 테스트"""
    print("🧪 Memory 통합 테스트 시작")
    print("=" * 50)

    # 분류기 초기화
    classifier = IntegratedMailClassifier()

    # 테스트 메일 데이터
    test_emails = [
        {
            "id": "test-email-1",
            "subject": "서버 장애 긴급 복구 요청",
            "sender": "admin@company.com",
            "body": "현재 서버에 장애가 발생하여 긴급 복구가 필요합니다. 즉시 확인 부탁드립니다."
        },
        {
            "id": "test-email-2",
            "subject": "MZ세대 유행 밈 공유",
            "sender": "friend@personal.com",
            "body": "요즘 유행하는 밈들이에요~ ㅋㅋ 재미있게 보세요!"
        },
        {
            "id": "test-email-3",
            "subject": "프로젝트 회의 일정 조율",
            "sender": "pm@company.com",
            "body": "다음 주 프로젝트 회의 일정을 조율하고자 합니다. 가능한 시간을 알려주세요."
        }
    ]

    print(f"📧 테스트할 메일 개수: {len(test_emails)}")
    print()

    # 각 메일에 대해 분류 테스트
    for i, email in enumerate(test_emails, 1):
        print(f"📨 테스트 메일 {i}: {email['subject']}")
        print(f"   발신자: {email['sender']}")
        print(f"   내용: {email['body'][:50]}...")

        try:
            # 메모리 기반 분류 실행
            should_create, reason, metadata = classifier.should_create_ticket(email, "테스트 메일 분류")

            print(f"   🤖 LLM 사용 가능: {classifier.is_llm_available()}")
            print(f"   🧠 Memory 사용 가능: {classifier.is_memory_available()}")
            print(f"   📝 판단 결과: {should_create}")
            print(f"   💡 판단 이유: {reason}")

            # 메타데이터 출력
            if metadata:
                confidence = metadata.get('confidence', 0.0)
                print(f"   🎯 신뢰도: {confidence:.2f}")

                if 'lm_reasoning' in metadata:
                    print(f"   🧠 LLM 추론: {metadata['lm_reasoning']}")

        except Exception as e:
            print(f"   ❌ 분류 실패: {str(e)}")

        print("-" * 30)

    # 상태 정보 출력
    print("\n📊 분류기 상태 정보:")
    print(f"   LLM 상태: {classifier.get_llm_status()}")
    print(f"   LLM 사용 가능: {classifier.is_llm_available()}")
    print(f"   Memory 사용 가능: {classifier.is_memory_available()}")

    print("\n✅ Memory 통합 테스트 완료")

if __name__ == "__main__":
    test_memory_integration()