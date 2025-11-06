#!/usr/bin/env python3
"""
Execution Engine - LLM의 Function Calling 결과를 순차적으로 실행
"""

from typing import Dict, Any, List, Optional
import json
import traceback


class ExecutionEngine:
    """
    LLM의 Function Calling 결과를 순차적으로 실행하고 context를 관리
    """

    def __init__(self, tool_registry):
        """
        Args:
            tool_registry: ToolRegistry 인스턴스
        """
        self.registry = tool_registry
        self.context: Dict[str, Any] = {}  # 실행 컨텍스트 (이전 결과 저장)
        self.execution_history: List[Dict] = []  # 실행 이력

    def execute_function_call(
        self,
        function_name: str,
        function_arguments: str,
        call_id: str = None
    ) -> Dict[str, Any]:
        """
        단일 Function Call 실행

        Args:
            function_name: 함수 이름
            function_arguments: JSON 문자열 형태의 인자
            call_id: Function Call ID (로깅용)

        Returns:
            {
                "success": True/False,
                "result": 실행 결과,
                "error": 에러 메시지 (실패 시)
            }
        """
        print(f"\n{'='*60}")
        print(f"🔧 Tool: {function_name}")
        print(f"{'='*60}")

        try:
            # 1. 인자 파싱
            arguments = json.loads(function_arguments)
            print(f"📥 Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)[:200]}...")

            # 2. Context 참조 해결
            resolved_args = self._resolve_arguments(arguments)

            # 3. Tool 가져오기
            tool_func = self.registry.get_tool(function_name)
            if not tool_func:
                error_msg = f"Unknown tool: {function_name}"
                print(f"❌ {error_msg}")
                return {
                    "success": False,
                    "result": None,
                    "error": error_msg
                }

            # 4. 실행
            result = tool_func(**resolved_args)

            # 5. 결과 요약
            result_summary = self._summarize_result(result)
            print(f"✅ Success: {result_summary}")

            # 6. 실행 이력 저장
            self.execution_history.append({
                "call_id": call_id,
                "function": function_name,
                "arguments": arguments,
                "success": True,
                "result_summary": result_summary
            })

            return {
                "success": True,
                "result": result,
                "error": None
            }

        except json.JSONDecodeError as e:
            error_msg = f"JSON 파싱 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "result": None,
                "error": error_msg
            }

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"📋 Traceback:\n{traceback.format_exc()}")

            self.execution_history.append({
                "call_id": call_id,
                "function": function_name,
                "arguments": arguments if 'arguments' in locals() else {},
                "success": False,
                "error": error_msg
            })

            return {
                "success": False,
                "result": None,
                "error": error_msg
            }

    def _resolve_arguments(self, arguments: Dict) -> Dict:
        """
        인자에서 context 참조 처리

        예:
            {"issues": "$result_1"} → {"issues": self.context["result_1"]}
            {"data": "$bmt_issues"} → {"data": self.context["bmt_issues"]}

        Args:
            arguments: 원본 인자 딕셔너리

        Returns:
            Context 참조가 해결된 인자 딕셔너리
        """
        resolved = {}

        for key, value in arguments.items():
            if isinstance(value, str) and value.startswith("$"):
                # Context 참조
                context_key = value[1:]  # $ 제거
                if context_key in self.context:
                    resolved[key] = self.context[context_key]
                    print(f"🔗 Resolved ${context_key}: {self._summarize_result(self.context[context_key])}")
                else:
                    print(f"⚠️  Context key not found: ${context_key}")
                    resolved[key] = None
            elif isinstance(value, dict):
                # 딕셔너리 내부도 재귀적으로 처리
                resolved[key] = self._resolve_arguments(value)
            elif isinstance(value, list):
                # 리스트 내부도 처리
                resolved[key] = [
                    self._resolve_arguments(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value

        return resolved

    def store_result(self, key: str, value: Any):
        """
        실행 결과를 context에 저장

        Args:
            key: Context 키 (예: "result_1", "bmt_issues")
            value: 저장할 값
        """
        self.context[key] = value
        print(f"💾 Stored in context: {key} = {self._summarize_result(value)}")

    def get_context(self) -> Dict:
        """
        현재 context 반환

        Returns:
            Context 딕셔너리
        """
        return self.context

    def get_context_value(self, key: str) -> Optional[Any]:
        """
        특정 context 값 반환

        Args:
            key: Context 키

        Returns:
            Context 값, 없으면 None
        """
        return self.context.get(key)

    def clear_context(self):
        """Context 초기화"""
        self.context.clear()
        self.execution_history.clear()
        print("🗑️  Context cleared")

    def get_execution_history(self) -> List[Dict]:
        """
        실행 이력 반환

        Returns:
            실행 이력 리스트
        """
        return self.execution_history

    def _summarize_result(self, result: Any) -> str:
        """
        실행 결과를 요약 문자열로 변환 (로깅용)

        Args:
            result: 실행 결과

        Returns:
            요약 문자열
        """
        if result is None:
            return "None"
        elif isinstance(result, list):
            return f"List[{len(result)} items]"
        elif isinstance(result, dict):
            return f"Dict[{len(result)} keys]"
        elif isinstance(result, str):
            if len(result) > 100:
                return f"String[{len(result)} chars]: {result[:100]}..."
            return f"String: {result}"
        else:
            return f"{type(result).__name__}: {str(result)[:100]}"

    def format_result_for_llm(self, result: Any, max_length: int = 50000) -> str:
        """
        실행 결과를 LLM에게 전달할 수 있는 형식으로 변환

        Args:
            result: 실행 결과
            max_length: 최대 문자열 길이 (기본: 50000, 인사이트 생성을 위해 증가)

        Returns:
            JSON 문자열
        """
        try:
            # None 처리
            if result is None:
                return json.dumps({"status": "no_result"}, ensure_ascii=False)

            # 리스트인 경우 - 통계 정보와 함께 더 많은 데이터 전달
            if isinstance(result, list):
                # 전체 데이터 통계 생성
                summary = {
                    "type": "list",
                    "count": len(result)
                }

                # 50개 이하면 전체 전달, 아니면 샘플링
                if len(result) <= 50:
                    summary["items"] = result
                else:
                    # 앞 30개 + 뒤 20개 (전체 분포 파악 가능하도록)
                    summary["items"] = result[:30] + result[-20:]
                    summary["truncated"] = True
                    summary["sampling"] = "처음 30개 + 마지막 20개 샘플"

                # 딕셔너리 리스트인 경우 필드별 통계 추가
                if result and isinstance(result[0], dict):
                    # 주요 필드 분석
                    field_stats = {}
                    sample_fields = result[0].keys()

                    for field in list(sample_fields)[:10]:  # 최대 10개 필드만
                        try:
                            values = [item.get(field) for item in result if field in item and item.get(field)]
                            if values:
                                # 고유 값 개수
                                unique_count = len(set(str(v) for v in values))
                                field_stats[field] = {
                                    "total": len(values),
                                    "unique": unique_count
                                }

                                # 상위 빈도 값 (문자열/숫자만)
                                if isinstance(values[0], (str, int, float)):
                                    from collections import Counter
                                    top_values = Counter(values).most_common(5)
                                    field_stats[field]["top_values"] = [
                                        {"value": v, "count": c} for v, c in top_values
                                    ]
                        except:
                            pass

                    summary["field_statistics"] = field_stats

                result_str = json.dumps(summary, ensure_ascii=False, default=str)
            else:
                result_str = json.dumps(result, ensure_ascii=False, default=str)

            # 길이 제한
            if len(result_str) > max_length:
                result_str = result_str[:max_length] + "... [truncated]"

            return result_str

        except Exception as e:
            return json.dumps({
                "error": "Failed to format result",
                "message": str(e)
            }, ensure_ascii=False)

    def print_summary(self):
        """실행 이력 요약 출력"""
        print(f"\n{'='*60}")
        print(f"📊 Execution Summary")
        print(f"{'='*60}")
        print(f"Total function calls: {len(self.execution_history)}")

        success_count = sum(1 for h in self.execution_history if h['success'])
        fail_count = len(self.execution_history) - success_count

        print(f"✅ Success: {success_count}")
        print(f"❌ Failed: {fail_count}")

        print(f"\n📦 Context variables:")
        for key, value in self.context.items():
            print(f"  - {key}: {self._summarize_result(value)}")

        print(f"{'='*60}\n")
