#!/usr/bin/env python3
"""
빠른 열거형 테스트 스크립트
"""

from email_models import EmailPriority, EmailStatus

def test_enums():
    """열거형 테스트"""
    print("🔍 열거형 테스트 시작")
    
    # 우선순위 테스트
    print(f"EmailPriority.HIGH: {EmailPriority.HIGH}")
    print(f"str(EmailPriority.HIGH): {str(EmailPriority.HIGH)}")
    print(f"EmailPriority.HIGH.value: {EmailPriority.HIGH.value}")
    
    # 상태 테스트
    print(f"EmailStatus.UNREAD: {EmailStatus.UNREAD}")
    print(f"str(EmailStatus.UNREAD): {str(EmailStatus.UNREAD)}")
    print(f"EmailStatus.UNREAD.value: {EmailStatus.UNREAD.value}")
    
    # 문자열 변환 테스트
    priority_str = str(EmailPriority.HIGH)
    status_str = str(EmailStatus.UNREAD)
    
    print(f"\n문자열 변환 결과:")
    print(f"priority_str: {priority_str} (타입: {type(priority_str)})")
    print(f"status_str: {status_str} (타입: {type(status_str)})")
    
    print("\n✅ 열거형 테스트 완료")

if __name__ == "__main__":
    test_enums() 