#!/usr/bin/env python3
"""
Insight 생성 기능 테스트
Agent가 캐시 데이터를 바탕으로 인사이트를 생성하는지 확인
"""

import os
import sys
from openai import AzureOpenAI
from agent.monthly_report_agent import MonthlyReportAgent


def test_insight_generation():
    """인사이트 생성 테스트"""
    print("\n" + "="*80)
    print("🧪 Insight 생성 기능 테스트")
    print("="*80)

    # Azure OpenAI 설정
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    if not azure_endpoint or not api_key:
        print("❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        print("   AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY를 설정하세요.")
        return False

    # Azure OpenAI 클라이언트 생성
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version="2024-05-01-preview"
    )

    # Agent 생성
    agent = MonthlyReportAgent(
        azure_client=client,
        user_id=1,
        deployment_name=deployment,
        db_path="tickets.db"
    )

    # 테스트 1: 캐시 상태 확인
    print("\n[1] 캐시 상태 확인")
    print("-" * 80)

    from tools.cache_tools import get_cache_summary
    summary = get_cache_summary(user_id=1)
    print(f"캐시된 이슈: {summary['unique_issues']}개")

    if summary['unique_issues'] == 0:
        print("⚠️  캐시에 데이터가 없습니다. 먼저 search_issues를 실행하여 데이터를 캐시하세요.")
        return False

    # 테스트 2: 인사이트 생성 프롬프트 실행
    print("\n[2] 인사이트 생성 프롬프트 실행")
    print("-" * 80)

    insight_prompts = [
        "캐시된 모든 이슈 데이터를 분석하여 주요 트렌드와 개선점을 2개 이상 도출하세요.",
        "현재까지 조회한 이슈들의 패턴을 분석하고 문제점을 찾아주세요.",
        "캐시 데이터 기반으로 프로젝트 상태에 대한 인사이트를 생성하세요."
    ]

    for i, prompt in enumerate(insight_prompts, 1):
        print(f"\n테스트 {i}: {prompt}")
        print("─" * 80)

        result = agent.generate_page(
            page_title=f"인사이트 테스트 {i}",
            user_prompt=prompt,
            max_iterations=5,
            temperature=0.7  # 창의적인 인사이트를 위해 temperature 증가
        )

        if result["success"]:
            print(f"\n✅ 인사이트 생성 성공!")
            print(f"\n생성된 인사이트:")
            print("─" * 80)
            print(result["content"])
            print("─" * 80)

            # 최소 2줄 이상인지 확인
            lines = [line.strip() for line in result["content"].split("\n") if line.strip()]
            if len(lines) >= 2:
                print(f"✅ 최소 요구사항 충족: {len(lines)}줄 생성")
            else:
                print(f"⚠️  짧은 응답: {len(lines)}줄만 생성됨")

            # Tool 사용 확인
            tool_usage = result["metadata"]["tool_usage"]
            print(f"\n사용된 Tool: {tool_usage}")

            if "get_cached_issues" in tool_usage:
                print("✅ get_cached_issues 사용됨")
            else:
                print("⚠️  get_cached_issues를 사용하지 않음")

            if "filter_issues" in tool_usage or "find_issue_by_field" in tool_usage:
                print("⚠️  불필요한 데이터 처리 Tool 사용됨 (인사이트 모드에서는 금지)")
            else:
                print("✅ 데이터 처리 Tool 사용 안함 (올바른 동작)")

        else:
            print(f"\n❌ 인사이트 생성 실패: {result['error']}")
            return False

        print("\n" + "="*80)

        # 첫 번째 테스트만 실행 (API 비용 절감)
        break

    print("\n✅ 인사이트 생성 기능 테스트 완료!")
    return True


def test_data_vs_insight_mode():
    """데이터 조회 모드 vs 인사이트 모드 비교 테스트"""
    print("\n" + "="*80)
    print("🧪 모드 비교 테스트: 데이터 조회 vs 인사이트 생성")
    print("="*80)

    # Azure OpenAI 설정
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    if not azure_endpoint or not api_key:
        print("❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        return False

    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version="2024-05-01-preview"
    )

    agent = MonthlyReportAgent(
        azure_client=client,
        user_id=1,
        deployment_name=deployment,
        db_path="tickets.db"
    )

    # 테스트 1: 데이터 조회 모드
    print("\n[1] 데이터 조회 모드 (단순 목록)")
    print("-" * 80)
    prompt1 = "캐시된 이슈 목록을 표로 보여주세요. key, summary, status 컬럼 포함."

    result1 = agent.generate_page(
        page_title="데이터 조회 테스트",
        user_prompt=prompt1,
        max_iterations=5
    )

    if result1["success"]:
        print(f"✅ 성공")
        print(f"사용된 Tool: {result1['metadata']['tool_usage']}")
        if "format_as_table" in result1['metadata']['tool_usage']:
            print("✅ format_as_table 사용됨 (올바른 동작)")
    else:
        print(f"❌ 실패: {result1['error']}")

    # 테스트 2: 인사이트 모드
    print("\n[2] 인사이트 모드 (분석 및 해석)")
    print("-" * 80)
    prompt2 = "캐시된 이슈들의 주요 트렌드를 분석하고 개선점을 도출하세요."

    result2 = agent.generate_page(
        page_title="인사이트 생성 테스트",
        user_prompt=prompt2,
        max_iterations=5,
        temperature=0.7
    )

    if result2["success"]:
        print(f"✅ 성공")
        print(f"사용된 Tool: {result2['metadata']['tool_usage']}")
        if "format_as_table" not in result2['metadata']['tool_usage']:
            print("✅ format_as_table 사용 안함 (올바른 동작)")
        else:
            print("⚠️  format_as_table 사용됨 (인사이트 모드에서는 금지)")

        # 내용 비교
        print(f"\n생성된 인사이트 길이: {len(result2['content'])}자")
    else:
        print(f"❌ 실패: {result2['error']}")

    print("\n" + "="*80)
    print("✅ 모드 비교 테스트 완료!")
    return True


if __name__ == "__main__":
    print("\n🚀 " + "="*78)
    print("🚀 Insight 생성 기능 통합 테스트")
    print("🚀 " + "="*78)

    # 캐시 상태 먼저 확인
    from tools.cache_tools import get_cache_summary
    summary = get_cache_summary(user_id=1)

    print(f"\n📊 현재 캐시 상태:")
    print(f"   - 캐시된 이슈: {summary['unique_issues']}개")
    print(f"   - JQL 쿼리 수: {summary['jql_queries']}회")
    print(f"   - 현재 월: {summary['month']}")

    if summary['unique_issues'] == 0:
        print("\n⚠️  캐시에 데이터가 없습니다!")
        print("   먼저 Streamlit 앱에서 프롬프트를 실행하여 Jira 데이터를 캐시하세요.")
        sys.exit(1)

    # 테스트 실행
    test1 = test_insight_generation()
    # test2 = test_data_vs_insight_mode()  # API 비용 때문에 주석 처리

    print("\n" + "="*80)
    print("✅ 모든 테스트 완료!")
    print("="*80 + "\n")
