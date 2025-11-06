"""
월간보고 JQL 생성기 - 프롬프트 파서 모듈
Azure OpenAI를 사용하여 사용자 프롬프트를 JQL 쿼리로 변환
"""

from typing import List, Dict
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st

# LangChain Azure OpenAI import
from langchain_openai import AzureChatOpenAI

# 환경 변수 로드
load_dotenv()


def _has_period_condition_in_prompt(prompt: str) -> bool:
    """
    프롬프트에 기간 관련 조건이 명시되어 있는지 확인

    Args:
        prompt: 사용자가 입력한 프롬프트

    Returns:
        True: 기간 관련 조건이 명시되어 있음 (created 자동 추가 불필요)
        False: 기간 관련 조건이 없음 (created 자동 추가 필요)
    """
    # 기간 관련 키워드 패턴
    period_keywords = [
        r'fixVersion',
        r'fixVersions',
        r'version',
        r'버전',
        r'릴리즈',
        r'release',
        r'updated',
        r'resolved',
        r'resolutiondate',
        r'due',
        r'duedate',
        r'마감일',
        r'해결일',
        r'수정일',
        r'\d{2}\.\d{2}',  # 25.09 형식
        r'\d{4}-\d{2}',   # 2025-09 형식
    ]

    prompt_lower = prompt.lower()

    # 패턴 매칭
    for keyword in period_keywords:
        if re.search(keyword, prompt, re.IGNORECASE):
            return True

    return False


def generate_jql_from_prompts(
    target_users: List[str],
    report_period: str,
    pages: List[Dict]
) -> List[Dict]:
    """
    LLM을 사용해 프롬프트를 JQL로 변환

    Args:
        target_users: ["user1", "user2"]
        report_period: "2025-10"
        pages: [{"title": "...", "prompt": "..."}]

    Returns:
        [
            {
                "page_title": "...",
                "queries": [{"user": "...", "jql": "..."}],
                "output_format": {"type": "...", "columns": [...]}
            }
        ]
    """

    # Azure OpenAI 클라이언트 (기존 설정 재사용)
    try:
        client = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            temperature=0.3,
            max_tokens=2000
        )
    except Exception as e:
        st.error(f"❌ Azure OpenAI 클라이언트 생성 실패: {str(e)}")
        return []

    results = []

    # 보고 기간 파싱 (YYYY-MM 형식)
    try:
        year, month = report_period.split('-')
        # 해당 월의 마지막 날 계산
        if month == '12':
            next_year = int(year) + 1
            next_month = 1
        else:
            next_year = int(year)
            next_month = int(month) + 1

        from datetime import datetime, timedelta
        last_day = (datetime(next_year, next_month, 1) - timedelta(days=1)).day
        period_start = f"{year}-{month}-01"
        period_end = f"{year}-{month}-{last_day:02d}"
    except Exception as e:
        st.error(f"❌ 보고 기간 파싱 실패: {str(e)}")
        period_start = f"{report_period}-01"
        period_end = f"{report_period}-31"

    for page in pages:
        # 프롬프트에 기간 조건이 있는지 확인
        has_period_condition = _has_period_condition_in_prompt(page['prompt'])

        # LLM 프롬프트 구성 (기간 조건 유무에 따라 다르게)
        if has_period_condition:
            # 프롬프트에 기간 조건이 명시된 경우
            system_prompt = """당신은 Jira JQL 쿼리 생성 전문가입니다.

사용자가 월간보고 페이지에 대한 프롬프트를 제공하면,
각 유저별로 필요한 JQL 쿼리를 생성해주세요.

[JQL 작성 규칙]
1. 프로젝트 키는 대문자 (예: BTVO, PROJ)
2. 라벨은 작은따옴표: labels = 'NCMS'
3. 컴포넌트는 component 필드 사용
4. 상태는 status 필드 (예: status = 'Done')
5. 여러 조건은 AND로 연결
6. 괄호를 사용하여 복잡한 조건 그룹화
7. fixVersion은 작은따옴표로 감싸기: fixVersion = '25.09'
8. **중요**: 프롬프트에 기간 관련 조건(fixVersion, version, updated 등)이 명시되어 있으므로, created 날짜 조건을 추가하지 마세요

[출력 형식]
반드시 유효한 JSON만 반환하세요:
{
    "page_title": "페이지 제목",
    "queries": [
        {"user": "user1", "jql": "완전한 JQL 쿼리"},
        {"user": "user2", "jql": "완전한 JQL 쿼리"}
    ],
    "output_format": {
        "type": "table" or "chart",
        "columns": ["key", "created", "summary", "assignee"]
    }
}

주의사항:
- 각 유저에 대해 별도의 JQL 쿼리를 생성하세요
- JQL 쿼리는 Jira에서 직접 실행 가능해야 합니다
- 프롬프트에 명시된 조건을 정확히 따르세요
- 프롬프트에 기간 조건이 명시되어 있으므로 created 날짜를 추가하지 마세요
"""
        else:
            # 프롬프트에 기간 조건이 없는 경우
            system_prompt = """당신은 Jira JQL 쿼리 생성 전문가입니다.

사용자가 월간보고 페이지에 대한 프롬프트를 제공하면,
각 유저별로 필요한 JQL 쿼리를 생성해주세요.

[JQL 작성 규칙]
1. 프로젝트 키는 대문자 (예: BTVO, PROJ)
2. 라벨은 작은따옴표: labels = 'NCMS'
3. 컴포넌트는 component 필드 사용
4. 상태는 status 필드 (예: status = 'Done')
5. 여러 조건은 AND로 연결
6. 괄호를 사용하여 복잡한 조건 그룹화
7. **중요**: 프롬프트에 기간 관련 조건이 명시되지 않았으므로, created 날짜 조건은 나중에 자동으로 추가됩니다. 따라서 created 조건은 포함하지 마세요

[출력 형식]
반드시 유효한 JSON만 반환하세요:
{
    "page_title": "페이지 제목",
    "queries": [
        {"user": "user1", "jql": "완전한 JQL 쿼리"},
        {"user": "user2", "jql": "완전한 JQL 쿼리"}
    ],
    "output_format": {
        "type": "table" or "chart",
        "columns": ["key", "created", "summary", "assignee"]
    }
}

주의사항:
- 각 유저에 대해 별도의 JQL 쿼리를 생성하세요
- JQL 쿼리는 Jira에서 직접 실행 가능해야 합니다
- 프롬프트에 명시된 조건을 모두 포함하세요
- created 날짜 조건은 자동으로 추가되므로 포함하지 마세요
"""

        user_prompt = f"""[입력 정보]
대상 유저: {', '.join(target_users)}
보고 기간: {report_period} ({period_start} ~ {period_end})
페이지 제목: {page['title']}

[프롬프트]
{page['prompt']}

위 프롬프트를 분석하여 각 유저별 JQL 쿼리를 JSON 형식으로 생성해주세요."""

        try:
            # LLM 호출
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = client.invoke(messages)
            content = response.content

            # JSON 추출 (```json ``` 제거)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # 프롬프트에 기간 조건이 명시되지 않은 경우에만 created 조건 자동 추가
            if not has_period_condition:
                for query in result.get('queries', []):
                    jql = query.get('jql', '')
                    # created 조건이 없는 경우에만 추가
                    if 'created >=' not in jql and 'created <=' not in jql:
                        # 기간 조건 추가
                        if jql:
                            query['jql'] = f"{jql} AND created >= '{period_start}' AND created <= '{period_end}'"
                        else:
                            query['jql'] = f"created >= '{period_start}' AND created <= '{period_end}'"

            results.append(result)

        except json.JSONDecodeError as e:
            st.error(f"❌ 페이지 '{page['title']}' JSON 파싱 실패: {str(e)}")
            st.code(content, language="text")
            results.append({
                "page_title": page['title'],
                "error": f"JSON 파싱 실패: {str(e)}",
                "queries": [],
                "output_format": {}
            })
        except Exception as e:
            st.error(f"❌ 페이지 '{page['title']}' 처리 중 오류: {str(e)}")
            results.append({
                "page_title": page['title'],
                "error": str(e),
                "queries": [],
                "output_format": {}
            })

    return results


def display_jql_results(results: List[Dict]):
    """
    생성된 JQL 결과를 Streamlit UI에 표시
    """

    st.success("✅ JQL 생성 완료!")
    st.divider()

    for i, result in enumerate(results):
        st.subheader(f"📄 페이지 {i+1}: {result.get('page_title', 'Unknown')}")

        if "error" in result:
            st.error(f"❌ 오류 발생: {result['error']}")
            continue

        # 쿼리 표시
        queries = result.get('queries', [])
        if not queries:
            st.warning("⚠️ 생성된 쿼리가 없습니다.")
            continue

        for j, query in enumerate(queries):
            with st.expander(f"👤 {query.get('user', 'Unknown')}", expanded=True):
                jql = query.get('jql', '')
                st.code(jql, language="sql")

                # 복사 버튼 (Streamlit의 code 블록은 자동으로 복사 기능 제공)
                st.caption("💡 코드 블록 위에 마우스를 올려 복사 버튼을 클릭하세요")

        # 출력 형식 표시
        output_fmt = result.get('output_format', {})
        if output_fmt:
            col1, col2 = st.columns(2)
            with col1:
                output_type = output_fmt.get('type', 'unknown')
                st.info(f"📊 출력 형식: **{output_type}**")
            with col2:
                columns = output_fmt.get('columns', [])
                if columns:
                    st.info(f"📋 컬럼: {', '.join(columns)}")

        # 전체 JSON 표시
        with st.expander("🔍 전체 JSON 보기"):
            st.json(result)

        st.divider()

    # 전체 결과 다운로드
    try:
        json_data = json.dumps(results, indent=2, ensure_ascii=False)
        st.download_button(
            label="💾 전체 결과 JSON 다운로드",
            data=json_data,
            file_name=f"monthly_report_jql_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"❌ 다운로드 버튼 생성 실패: {str(e)}")
