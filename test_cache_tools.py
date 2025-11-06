#!/usr/bin/env python3
"""
Cache Tools 테스트 스크립트
get_cached_issues와 get_cache_summary가 Tool Registry에 정상적으로 등록되었는지 확인
"""

import logging
import sys
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_tool_registry():
    """Tool Registry에 캐시 도구가 등록되었는지 테스트"""
    print("\n" + "="*70)
    print("🧪 Tool Registry - Cache Tools 등록 확인")
    print("="*70)

    try:
        from agent.tool_registry import ToolRegistry

        # ToolRegistry 초기화 (user_id=1 사용)
        registry = ToolRegistry(user_id=1, db_path="tickets.db")

        # 등록된 모든 도구 목록
        all_tools = registry.list_tools()
        print(f"\n✅ 등록된 도구 총 {len(all_tools)}개")

        # 캐시 도구 확인
        cache_tools = ["get_cached_issues", "get_cache_summary"]

        print("\n[1] 캐시 도구 등록 확인:")
        for tool_name in cache_tools:
            if tool_name in all_tools:
                print(f"   ✅ {tool_name}: 등록됨")
            else:
                print(f"   ❌ {tool_name}: 미등록")
                return False

        # 스키마 확인
        print("\n[2] OpenAI Function Schema 확인:")
        schemas = registry.get_schemas()
        schema_names = [s['function']['name'] for s in schemas]

        for tool_name in cache_tools:
            if tool_name in schema_names:
                schema = next(s for s in schemas if s['function']['name'] == tool_name)
                print(f"   ✅ {tool_name} schema:")
                print(f"      - description: {schema['function']['description'][:60]}...")
                print(f"      - parameters: {len(schema['function']['parameters']['properties'])}개 속성")
            else:
                print(f"   ❌ {tool_name}: 스키마 없음")
                return False

        print("\n" + "="*70)
        print("✅ Tool Registry 테스트 성공!")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_tools_execution():
    """실제로 캐시 도구를 실행해보는 테스트"""
    print("\n" + "="*70)
    print("🧪 Cache Tools 실행 테스트")
    print("="*70)

    try:
        from tools.cache_tools import get_cached_issues, get_cache_summary

        # 캐시 요약 조회
        print("\n[1] get_cache_summary() 실행:")
        summary = get_cache_summary(user_id=1, db_path="tickets.db")
        print(f"   ✅ 캐시 요약:")
        for key, value in summary.items():
            print(f"      - {key}: {value}")

        # 캐시된 이슈 조회
        print("\n[2] get_cached_issues() 실행:")
        issues = get_cached_issues(user_id=1, db_path="tickets.db")
        print(f"   ✅ 캐시된 이슈: {len(issues)}개")

        if issues:
            print("\n[3] 첫 번째 이슈 샘플:")
            first_issue = issues[0]
            for key, value in list(first_issue.items())[:5]:  # 처음 5개 필드만
                print(f"      - {key}: {value}")

        print("\n" + "="*70)
        print("✅ Cache Tools 실행 테스트 성공!")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ 실행 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_callable():
    """ToolRegistry를 통해 도구를 호출할 수 있는지 테스트"""
    print("\n" + "="*70)
    print("🧪 Tool Callable 테스트 (Registry를 통한 호출)")
    print("="*70)

    try:
        from agent.tool_registry import ToolRegistry

        registry = ToolRegistry(user_id=1, db_path="tickets.db")

        # get_cache_summary 호출
        print("\n[1] get_cache_summary 호출:")
        tool_func = registry.get_tool("get_cache_summary")
        if tool_func is None:
            print("   ❌ 도구를 찾을 수 없음")
            return False

        result = tool_func()
        print(f"   ✅ 실행 성공:")
        print(f"      - total_cached_items: {result.get('total_cached_items', 0)}")
        print(f"      - unique_issues: {result.get('unique_issues', 0)}")
        print(f"      - month: {result.get('month', 'unknown')}")

        # get_cached_issues 호출
        print("\n[2] get_cached_issues 호출:")
        tool_func = registry.get_tool("get_cached_issues")
        if tool_func is None:
            print("   ❌ 도구를 찾을 수 없음")
            return False

        issues = tool_func()
        print(f"   ✅ 실행 성공: {len(issues)}개 이슈 반환")

        print("\n" + "="*70)
        print("✅ Tool Callable 테스트 성공!")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ Callable 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "🚀 "+"="*68)
    print("🚀 Cache-Based Insight Tools 통합 테스트")
    print("🚀 "+"="*68)

    # 테스트 실행
    test1 = test_tool_registry()
    test2 = test_cache_tools_execution()
    test3 = test_tool_callable()

    # 최종 결과
    print("\n" + "📊 "+"="*68)
    print("📊 테스트 결과 요약")
    print("📊 "+"="*68)
    print(f"   {'✅' if test1 else '❌'} Tool Registry 등록: {'성공' if test1 else '실패'}")
    print(f"   {'✅' if test2 else '❌'} Tools 직접 실행: {'성공' if test2 else '실패'}")
    print(f"   {'✅' if test3 else '❌'} Registry를 통한 호출: {'성공' if test3 else '실패'}")

    all_passed = test1 and test2 and test3

    if all_passed:
        print("\n" + "🎉 "+"="*68)
        print("🎉 모든 테스트 통과! Cache-Based Insight Tools가 정상 작동합니다.")
        print("🎉 "+"="*68 + "\n")
        sys.exit(0)
    else:
        print("\n" + "⚠️  "+"="*68)
        print("⚠️  일부 테스트 실패. 위 로그를 확인하세요.")
        print("⚠️  "+"="*68 + "\n")
        sys.exit(1)
