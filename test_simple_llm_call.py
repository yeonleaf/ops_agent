#!/usr/bin/env python3
"""
simple_llm_call 함수 테스트 스크립트
"""

import os
import sys
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 현재 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simple_llm_call():
    """simple_llm_call 함수 테스트"""
    try:
        # fastmcp_server에서 simple_llm_call 함수 import
        from fastmcp_server import simple_llm_call

        print("🧪 simple_llm_call 함수 테스트 시작")
        print("=" * 50)

        # 테스트 프롬프트
        test_prompt = "안녕하세요! 간단한 인사말을 응답해주세요."

        print(f"📝 테스트 프롬프트: {test_prompt}")
        print("-" * 50)

        # 함수 호출
        response = simple_llm_call(test_prompt)

        print(f"🤖 LLM 응답:")
        print(response)
        print("-" * 50)

        # 응답 검증
        if response.startswith("오류:"):
            print("❌ 테스트 실패: 오류가 발생했습니다.")
            return False
        else:
            print("✅ 테스트 성공: LLM이 정상적으로 응답했습니다.")
            return True

    except ImportError as e:
        print(f"❌ import 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        return False

def test_environment_variables():
    """환경 변수 확인 테스트"""
    print("🔧 환경 변수 확인")
    print("=" * 50)

    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_DEPLOYMENT_NAME',
        'AZURE_OPENAI_API_VERSION'
    ]

    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 키는 일부만 표시
            if 'KEY' in var:
                display_value = f"{value[:10]}...{value[-10:]}" if len(value) > 20 else value
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: 설정되지 않음")
            all_set = False

    print("-" * 50)
    return all_set

if __name__ == "__main__":
    print("🚀 simple_llm_call 함수 테스트 시작")
    print()

    # 환경 변수 확인
    env_ok = test_environment_variables()
    print()

    if not env_ok:
        print("❌ 환경 변수가 올바르게 설정되지 않았습니다.")
        sys.exit(1)

    # 함수 테스트
    success = test_simple_llm_call()
    print()

    if success:
        print("🎉 모든 테스트가 성공했습니다!")
        sys.exit(0)
    else:
        print("❌ 테스트가 실패했습니다.")
        sys.exit(1)