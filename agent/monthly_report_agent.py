#!/usr/bin/env python3
"""
Monthly Report Agent - LLM 기반 월간보고 자동 생성 Agent
"""

from typing import Dict, List, Optional, Any
from openai import AzureOpenAI
import json
import time

from agent.tool_registry import ToolRegistry
from agent.execution_engine import ExecutionEngine


class MonthlyReportAgent:
    """
    자연어 프롬프트를 받아 LLM이 자동으로 Tool 조합 실행 계획을 수립하고,
    필요한 Tool들을 순차적으로 호출하여 최종 결과를 생성합니다.
    """

    def __init__(
        self,
        azure_client: AzureOpenAI,
        user_id: int,
        deployment_name: str,
        db_path: str = "tickets.db"
    ):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
            user_id: Jira API 호출에 사용할 사용자 ID
            deployment_name: Azure OpenAI 배포 이름
            db_path: 데이터베이스 경로
        """
        self.llm = azure_client
        self.deployment = deployment_name
        self.user_id = user_id
        self.db_path = db_path

        # Tool Registry와 Execution Engine 초기화
        self.registry = ToolRegistry(user_id=user_id, db_path=db_path)
        self.engine = ExecutionEngine(self.registry)

    def generate_page(
        self,
        page_title: str,
        user_prompt: str,
        context: Optional[Dict] = None,
        max_iterations: int = 15,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        사용자 프롬프트로 페이지 생성

        Args:
            page_title: 페이지 제목
            user_prompt: 사용자 요청 (자연어)
            context: 추가 컨텍스트 (기간, 대상 유저 등)
            max_iterations: 최대 반복 횟수
            temperature: LLM temperature

        Returns:
            {
                "success": bool,
                "page_title": str,
                "content": str,  # 생성된 마크다운/테이블
                "metadata": dict,  # 통계 정보
                "error": str  # 에러 메시지 (실패 시)
            }
        """
        print(f"\n{'='*80}")
        print(f"📄 Agent 페이지 생성 시작")
        print(f"{'='*80}")
        print(f"제목: {page_title}")
        print(f"프롬프트: {user_prompt}")
        if context:
            print(f"컨텍스트: {json.dumps(context, ensure_ascii=False)}")
        print(f"{'='*80}\n")

        start_time = time.time()

        try:
            # 1. Context 초기화
            self.engine.clear_context()

            # 2. LLM 메시지 구성
            messages = self._create_messages(user_prompt, context)
            conversation_history = messages.copy()

            # 3. Function Calling 반복 실행
            iteration = 0
            final_content = None

            while iteration < max_iterations:
                iteration += 1
                print(f"\n{'─'*80}")
                print(f"🔄 Iteration {iteration}/{max_iterations}")
                print(f"{'─'*80}")

                # LLM 호출
                response = self.llm.chat.completions.create(
                    model=self.deployment,
                    messages=conversation_history,
                    tools=self.registry.get_schemas(),
                    tool_choice="auto",
                    temperature=temperature
                )

                message = response.choices[0].message

                # Assistant 메시지 추가
                conversation_history.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls if message.tool_calls else None
                })

                # Function Call 없으면 종료
                if not message.tool_calls:
                    print("\n✅ 작업 완료 (더 이상 Function Call 없음)")
                    final_content = message.content
                    break

                # Function Calls 실행
                print(f"\n📞 Function Calls: {len(message.tool_calls)}개")

                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments

                    # Tool 실행
                    exec_result = self.engine.execute_function_call(
                        function_name=function_name,
                        function_arguments=function_args,
                        call_id=tool_call.id
                    )

                    # 결과 저장 (다음 Tool에서 참조 가능하도록)
                    if exec_result["success"]:
                        result_key = f"result_{iteration}_{function_name}"
                        self.engine.store_result(result_key, exec_result["result"])

                    # Tool 결과를 대화에 추가
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self.engine.format_result_for_llm(
                            exec_result["result"] if exec_result["success"] else {"error": exec_result["error"]}
                        )
                    }
                    conversation_history.append(tool_message)

            # 4. 최대 반복 횟수 도달 시
            if iteration >= max_iterations:
                print(f"\n⚠️  최대 반복 횟수 도달 ({max_iterations})")
                final_content = "작업을 완료하지 못했습니다. 더 단순한 요청으로 시도해주세요."

            # 5. 최종 결과 정리
            elapsed_time = time.time() - start_time

            # Execution history에서 통계 추출
            metadata = self._extract_metadata()

            self.engine.print_summary()

            print(f"\n{'='*80}")
            print(f"✨ 페이지 생성 완료")
            print(f"{'='*80}")
            print(f"⏱️  소요 시간: {elapsed_time:.2f}초")
            print(f"🔧 Tool 호출: {len(self.engine.get_execution_history())}회")
            print(f"{'='*80}\n")

            return {
                "success": True,
                "page_title": page_title,
                "content": final_content or "",
                "metadata": metadata,
                "execution_history": self.engine.get_execution_history(),
                "elapsed_time": elapsed_time,
                "error": None
            }

        except Exception as e:
            print(f"\n❌ Agent 실행 실패: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "page_title": page_title,
                "content": "",
                "metadata": {},
                "error": str(e)
            }

    def _create_messages(self, user_prompt: str, context: Optional[Dict]) -> List[Dict]:
        """
        LLM에게 보낼 메시지 구성

        Args:
            user_prompt: 사용자 프롬프트
            context: 추가 컨텍스트

        Returns:
            메시지 리스트
        """
        system_prompt = """당신은 Jira 데이터를 처리하고 인사이트를 생성하는 전문 AI Agent입니다.

**역할:**
사용자의 요청을 분석하고, 제공된 Tool들을 조합하여 작업을 수행합니다.

**중요 규칙:**
1. 한 번에 하나 또는 여러 개의 Tool을 호출할 수 있습니다 (병렬 가능)
2. 이전 Tool의 결과를 다음 Tool에서 활용하려면 '$result_N_함수명' 형식으로 참조하세요
3. 복잡한 요청은 단계별로 나눠서 처리하세요

**두 가지 작업 모드:**

📊 **모드 1: 데이터 조회 및 표시** (단순 조회, 목록, 표 생성)
- search_issues로 데이터 수집 후 format_as_table/format_as_list로 출력
- 예: "BMT 이슈 목록", "완료된 작업 표로 보여줘"

💡 **모드 2: 인사이트 생성** (분석, 트렌드, insight, 경향, 개선점)
- **반드시 get_cached_issues()를 먼저 호출**하여 캐시된 모든 데이터 수집
- Tool로 필터링하지 말고, **당신이 직접 데이터를 분석**하여 인사이트 도출
- **시스템별로 구분하여 인사이트 생성** (중요!)
- 데이터가 부족해도 가능한 분석을 수행하고 한계를 명시

**시스템 구분 방법:**
1. labels 필드에서 시스템명 추출 (예: "NCMS_BMT", "NCMS_Admin", "BTV_Mobile" 등)
2. labels가 없으면 summary 필드에서 시스템명 패턴 찾기 (예: "[NCMS]", "BTV:", 대괄호/콜론 패턴)
3. 각 시스템별로 이슈를 그룹핑하여 별도 분석

**인사이트 생성 시 필수 포함 사항:**
1. **시스템별 섹션 구분** (헤더로 시스템명 명시)
2. 각 시스템별 주요 트렌드 또는 패턴
3. 각 시스템별 문제점 또는 개선 기회
4. 시스템별 정량적 통계 (이슈 개수, 완료율 등)
5. 시스템 간 비교 분석 (선택)

**Tool 사용 예시:**

예시 1: 단순 조회 (모드 1)
1. search_issues(jql="labels='NCMS_BMT' AND created>='2025-10-01'")
2. format_as_table(data="$result_1_search_issues", columns=["key", "summary", "status"])

예시 2: 시스템별 인사이트 생성 (모드 2)
1. get_cached_issues() ← 캐시된 모든 데이터 가져오기
2. [Tool 호출 없이 당신이 직접 데이터 분석]
3. labels 또는 summary에서 시스템명 추출 (NCMS_BMT, NCMS_Admin, BTV 등)
4. 시스템별로 그룹핑하여 각각 분석
5. 시스템별 헤더로 구분하여 인사이트 출력

   출력 형식 예시:
   ```
   ## NCMS_BMT 시스템 인사이트
   - 총 45건의 이슈 중 완료 30건 (66.7%)
   - 주요 트렌드: 성능 개선 관련 이슈 증가 (10건)
   - 개선 필요: 버그 수정 평균 소요 시간 3일 → 1.5일로 단축 필요

   ## BTV 시스템 인사이트
   - 총 28건의 이슈 중 완료 20건 (71.4%)
   - 주요 트렌드: UI/UX 개선 작업 집중 (15건)
   - 개선 필요: 담당자 분산 필요 (1명에게 60% 집중)
   ```

예시 3: 캐시 기반 시스템 간 비교 분석 (모드 2)
1. get_cache_summary() ← 캐시 상태 확인
2. get_cached_issues() ← 전체 데이터 수집
3. [시스템별 그룹핑 및 비교 분석]
4. 시스템별 인사이트 + 시스템 간 비교 인사이트 출력

**⚠️ 중요 - 인사이트 모드에서 금지 사항:**
- filter_issues, find_issue_by_field 같은 데이터 처리 Tool 사용 금지
- format_as_table, format_as_list로 단순 목록 출력 금지
- "해당 데이터가 없습니다" 같은 답변 금지 (최소 2줄은 생성)

**Context 참조 방법:**
- 이전 실행 결과를 참조하려면: "$result_{iteration}_{function_name}"
- 예: "$result_1_get_cached_issues"
"""

        # 컨텍스트 정보 추가
        context_str = ""
        if context:
            context_str = f"\n\n**제공된 컨텍스트:**\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"

        user_message = f"""**요청사항:**
{user_prompt}
{context_str}

위 요청을 처리하기 위해 필요한 Tool들을 순차적으로 호출하세요.

**작업 흐름 판단:**

🔍 **요청에 "insight", "분석", "트렌드", "경향", "개선", "패턴" 등이 포함된 경우:**
1. get_cached_issues() 호출하여 모든 캐시 데이터 수집
2. Tool 호출 종료 후, 당신이 직접 데이터를 분석
3. **labels 또는 summary 필드에서 시스템명을 추출하고 시스템별로 그룹핑**
   - labels 예시: "NCMS_BMT", "NCMS_Admin", "BTV_Mobile"
   - summary 예시: "[NCMS]", "BTV:", "[Admin]"
4. **각 시스템별로 섹션을 나눠서 인사이트 생성** (헤더로 시스템명 명시)
5. 각 시스템마다 최소 1-2개의 의미 있는 인사이트 포함
6. 시스템별 트렌드, 문제점, 개선 방향, 정량적 통계 포함
7. format_as_table 같은 formatting tool 사용 금지

📋 **단순 데이터 조회/표시 요청인 경우:**
1. search_issues로 데이터 수집
2. 필요시 filter_*, group_by_* 등으로 데이터 처리
3. format_as_table 또는 format_as_list로 최종 출력

⚠️ **중요:** 인사이트 생성 요청인데도 데이터가 부족하면, 가능한 범위에서 분석하고 한계를 명시하세요. "데이터가 없습니다"로 끝내지 마세요.
"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

    def _extract_metadata(self) -> Dict[str, Any]:
        """
        실행 이력에서 메타데이터 추출

        Returns:
            메타데이터 딕셔너리
        """
        metadata = {
            "total_function_calls": len(self.engine.get_execution_history()),
            "successful_calls": 0,
            "failed_calls": 0,
            "tool_usage": {},
            "total_issues_fetched": 0
        }

        for record in self.engine.get_execution_history():
            func_name = record["function"]

            # 성공/실패 카운트
            if record["success"]:
                metadata["successful_calls"] += 1
            else:
                metadata["failed_calls"] += 1

            # Tool 사용 빈도
            metadata["tool_usage"][func_name] = metadata["tool_usage"].get(func_name, 0) + 1

            # 이슈 개수 추출 (search_issues 결과)
            if func_name == "search_issues" and record.get("result_summary"):
                summary = record["result_summary"]
                if "List[" in summary:
                    try:
                        count = int(summary.split("[")[1].split(" ")[0])
                        metadata["total_issues_fetched"] += count
                    except:
                        pass

        return metadata

    def reset(self):
        """Agent 상태 초기화"""
        self.engine.clear_context()
        print("🔄 Agent reset")
