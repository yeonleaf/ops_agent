#!/usr/bin/env python3
"""
디버그 테스트 스크립트
'str' object 에러를 찾기 위한 단계별 테스트
"""

import sys
import traceback

def test_step_1():
    """1단계: 기본 모듈 임포트 테스트"""
    print("🔍 1단계: 기본 모듈 임포트 테스트")
    try:
        import email_models
        print("✅ email_models 임포트 성공")
        return True
    except Exception as e:
        print(f"❌ email_models 임포트 실패: {e}")
        traceback.print_exc()
        return False

def test_step_2():
    """2단계: 모델 클래스 생성 테스트"""
    print("\n🔍 2단계: 모델 클래스 생성 테스트")
    try:
        from email_models import EmailMessage, EmailPriority, EmailStatus
        from datetime import datetime
        
        # 기본 이메일 메시지 생성
        email = EmailMessage(
            id="test123",
            sender="test@example.com",
            subject="테스트 메일",
            body="테스트 내용",
            received_date=datetime.now()
        )
        print("✅ EmailMessage 생성 성공")
        print(f"   - ID: {email.id}")
        print(f"   - 발신자: {email.sender}")
        print(f"   - 제목: {email.subject}")
        return True
    except Exception as e:
        print(f"❌ EmailMessage 생성 실패: {e}")
        traceback.print_exc()
        return False

def test_step_3():
    """3단계: 제공자 팩토리 테스트"""
    print("\n🔍 3단계: 제공자 팩토리 테스트")
    try:
        from email_provider import get_available_providers, get_default_provider
        
        available = get_available_providers()
        default = get_default_provider()
        
        print(f"✅ 사용 가능한 제공자: {available}")
        print(f"✅ 기본 제공자: {default}")
        return True
    except Exception as e:
        print(f"❌ 제공자 팩토리 테스트 실패: {e}")
        traceback.print_exc()
        return False

def test_step_4():
    """4단계: 통합 서비스 테스트"""
    print("\n🔍 4단계: 통합 서비스 테스트")
    try:
        from unified_email_service import UnifiedEmailService
        
        service = UnifiedEmailService()
        print(f"✅ 통합 서비스 생성 성공: {service.provider_name}")
        return True
    except Exception as e:
        print(f"❌ 통합 서비스 테스트 실패: {e}")
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 디버그 테스트 시작")
    print("=" * 50)
    
    steps = [
        test_step_1,
        test_step_2,
        test_step_3,
        test_step_4
    ]
    
    results = []
    for step in steps:
        try:
            result = step()
            results.append(result)
        except Exception as e:
            print(f"❌ 단계 실행 중 예외 발생: {e}")
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    
    for i, result in enumerate(results, 1):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {i}단계: {status}")
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n🎯 전체 결과: {success_count}/{total_count} 성공")
    
    if success_count == total_count:
        print("🎉 모든 테스트가 성공했습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 위의 오류 메시지를 확인해주세요.")

if __name__ == "__main__":
    main() 