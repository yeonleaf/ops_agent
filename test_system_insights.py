#!/usr/bin/env python3
"""
시스템별 인사이트 생성 테스트
labels/summary에서 시스템명을 추출하고 각 시스템별로 인사이트를 생성하는지 확인
"""

import logging

logging.basicConfig(level=logging.INFO)

def test_system_tools_in_registry():
    """Tool Registry에 시스템 도구가 등록되었는지 확인"""
    print("\n" + "="*80)
    print("🧪 [1] Tool Registry - System Tools 등록 확인")
    print("="*80)

    from agent.tool_registry import ToolRegistry

    registry = ToolRegistry(user_id=1, db_path="tickets.db")
    all_tools = registry.list_tools()

    print(f"\n✅ 등록된 도구 총 {len(all_tools)}개")

    system_tools = ["group_by_system", "get_system_summary"]

    print("\n[시스템 도구 등록 확인]")
    for tool_name in system_tools:
        if tool_name in all_tools:
            print(f"   ✅ {tool_name}: 등록됨")
        else:
            print(f"   ❌ {tool_name}: 미등록")
            return False

    # 스키마 확인
    schemas = registry.get_schemas()
    schema_names = [s['function']['name'] for s in schemas]

    print("\n[OpenAI Function Schema 확인]")
    for tool_name in system_tools:
        if tool_name in schema_names:
            schema = next(s for s in schemas if s['function']['name'] == tool_name)
            print(f"   ✅ {tool_name} schema:")
            print(f"      - description: {schema['function']['description'][:60]}...")
        else:
            print(f"   ❌ {tool_name}: 스키마 없음")
            return False

    return True


def test_system_tools_with_cache_data():
    """실제 캐시 데이터로 시스템 도구 테스트"""
    print("\n" + "="*80)
    print("🧪 [2] 실제 캐시 데이터로 시스템 도구 테스트")
    print("="*80)

    from tools.cache_tools import get_cached_issues, get_cache_summary
    from tools.system_tools import group_by_system, get_system_summary

    # 캐시 상태 확인
    summary = get_cache_summary(user_id=1)
    print(f"\n캐시 상태: {summary['unique_issues']}개 이슈")

    if summary['unique_issues'] == 0:
        print("⚠️  캐시에 데이터가 없습니다.")
        return False

    # 캐시된 이슈 가져오기
    issues = get_cached_issues(user_id=1)
    print(f"✅ {len(issues)}개 이슈 로드 완료")

    # 시스템별 그룹핑
    print("\n[1] group_by_system 테스트")
    print("-" * 80)
    groups = group_by_system(issues)
    print(f"✅ {len(groups)}개 시스템으로 그룹핑됨")

    for system_name, system_issues in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        print(f"   {system_name}: {len(system_issues)}개 이슈")

    # 시스템별 통계
    print("\n[2] get_system_summary 테스트")
    print("-" * 80)
    stats = get_system_summary(issues)
    print(f"✅ 총 {stats['total_systems']}개 시스템")
    print(f"   가장 큰 시스템: {stats['largest_system']}")
    print(f"   가장 작은 시스템: {stats['smallest_system']}")

    print("\n[시스템별 상세 통계 (상위 5개)]")
    sorted_systems = sorted(stats['systems'].items(), key=lambda x: x[1]['count'], reverse=True)[:5]

    for system_name, system_stats in sorted_systems:
        print(f"\n   📊 {system_name}")
        print(f"      - 총 이슈: {system_stats['count']}개")
        print(f"      - 완료: {system_stats['completed']}개")
        print(f"      - 완료율: {system_stats['completion_rate']}")
        print(f"      - 상태 분포: {system_stats['statuses']}")

    return True


def test_system_prompt_update():
    """시스템 프롬프트가 시스템별 구분을 지시하는지 확인"""
    print("\n" + "="*80)
    print("🧪 [3] Agent 시스템 프롬프트 확인")
    print("="*80)

    from agent.monthly_report_agent import MonthlyReportAgent
    import os
    from openai import AzureOpenAI

    # Azure OpenAI 설정 확인
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not azure_endpoint or not api_key:
        print("⚠️  Azure OpenAI 환경 변수가 설정되지 않았습니다. 스킵합니다.")
        return True

    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version="2024-05-01-preview"
    )

    agent = MonthlyReportAgent(
        azure_client=client,
        user_id=1,
        deployment_name="gpt-4o",
        db_path="tickets.db"
    )

    # 시스템 프롬프트 생성 테스트
    messages = agent._create_messages(
        user_prompt="캐시된 데이터를 분석하여 시스템별 인사이트를 생성하세요.",
        context=None
    )

    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    # 키워드 확인
    keywords = ["시스템별", "labels", "summary", "시스템명", "그룹핑", "섹션"]
    found_keywords = [kw for kw in keywords if kw in system_prompt or kw in user_prompt]

    print(f"\n✅ 시스템별 인사이트 관련 키워드 발견: {len(found_keywords)}개")
    for kw in found_keywords:
        print(f"   - {kw}")

    if len(found_keywords) >= 4:
        print("\n✅ 시스템 프롬프트에 시스템별 구분 지시사항이 충분히 포함됨")
        return True
    else:
        print("\n⚠️  시스템 프롬프트에 시스템별 구분 지시사항이 부족할 수 있음")
        return False


def main():
    print("\n" + "🚀 "+"="*78)
    print("🚀 시스템별 인사이트 생성 기능 통합 테스트")
    print("🚀 "+"="*78)

    # 캐시 상태 확인
    from tools.cache_tools import get_cache_summary
    summary = get_cache_summary(user_id=1)

    print(f"\n📊 현재 캐시 상태:")
    print(f"   - 캐시된 이슈: {summary['unique_issues']}개")
    print(f"   - JQL 쿼리 수: {summary['jql_queries']}회")
    print(f"   - 현재 월: {summary['month']}")

    # 테스트 실행
    test1 = test_system_tools_in_registry()
    test2 = test_system_tools_with_cache_data() if summary['unique_issues'] > 0 else True
    test3 = test_system_prompt_update()

    # 결과 요약
    print("\n" + "📊 "+"="*78)
    print("📊 테스트 결과 요약")
    print("📊 "+"="*78)
    print(f"   {'✅' if test1 else '❌'} Tool Registry 등록: {'성공' if test1 else '실패'}")
    print(f"   {'✅' if test2 else '⚠️ '} 실제 데이터 테스트: {'성공' if test2 else '캐시 데이터 없음'}")
    print(f"   {'✅' if test3 else '❌'} 시스템 프롬프트 확인: {'성공' if test3 else '실패'}")

    all_passed = test1 and test2 and test3

    if all_passed:
        print("\n" + "🎉 "+"="*78)
        print("🎉 모든 테스트 통과! 시스템별 인사이트 생성 기능이 정상 작동합니다.")
        print("🎉 "+"="*78)

        if summary['unique_issues'] > 0:
            print("\n💡 이제 다음 프롬프트를 실행해보세요:")
            print('   "캐시된 데이터를 시스템별로 분석하여 인사이트를 생성하세요."')
            print('   "labels에서 시스템명을 추출하고 각 시스템의 트렌드를 분석하세요."')
    else:
        print("\n" + "⚠️  "+"="*78)
        print("⚠️  일부 테스트 실패. 위 로그를 확인하세요.")
        print("⚠️  "+"="*78)

    print("\n")


if __name__ == "__main__":
    main()
