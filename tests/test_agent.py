#!/usr/bin/env python3
"""
Agent 모듈 테스트
"""

import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch
import json

from agent.tool_registry import ToolRegistry
from agent.execution_engine import ExecutionEngine

# MonthlyReportAgent는 openai 모듈이 필요하므로 조건부 import
try:
    from agent.monthly_report_agent import MonthlyReportAgent
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    MonthlyReportAgent = None


class TestToolRegistry(unittest.TestCase):
    """Tool Registry 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.user_id = 1
        self.registry = ToolRegistry(user_id=self.user_id)

    def test_initialization(self):
        """초기화 테스트"""
        self.assertIsInstance(self.registry.tools, dict)
        self.assertIsInstance(self.registry.tool_schemas, list)
        self.assertEqual(self.registry.user_id, self.user_id)

    def test_tool_registration(self):
        """Tool 등록 테스트"""
        tools = self.registry.list_tools()
        self.assertIn("search_issues", tools)
        self.assertIn("extract_version", tools)
        self.assertIn("group_by_field", tools)
        self.assertIn("format_as_table", tools)

    def test_get_tool(self):
        """Tool 가져오기 테스트"""
        tool = self.registry.get_tool("extract_version")
        self.assertIsNotNone(tool)
        self.assertTrue(callable(tool))

        # 존재하지 않는 Tool
        tool = self.registry.get_tool("nonexistent_tool")
        self.assertIsNone(tool)

    def test_get_schemas(self):
        """Schema 가져오기 테스트"""
        schemas = self.registry.get_schemas()
        self.assertIsInstance(schemas, list)
        self.assertGreater(len(schemas), 0)

        # 첫 번째 schema 검증
        schema = schemas[0]
        self.assertEqual(schema["type"], "function")
        self.assertIn("function", schema)
        self.assertIn("name", schema["function"])
        self.assertIn("description", schema["function"])
        self.assertIn("parameters", schema["function"])

    def test_text_tools(self):
        """Text Tool 실행 테스트"""
        # extract_version
        extract_version = self.registry.get_tool("extract_version")
        result = extract_version("Release v1.2.3")
        self.assertEqual(result, "1.2.3")

        # format_date
        format_date = self.registry.get_tool("format_date")
        result = format_date("2025-10-15T10:30:00", "%Y-%m-%d")
        self.assertEqual(result, "2025-10-15")


class TestExecutionEngine(unittest.TestCase):
    """Execution Engine 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.user_id = 1
        self.registry = ToolRegistry(user_id=self.user_id)
        self.engine = ExecutionEngine(self.registry)

    def test_initialization(self):
        """초기화 테스트"""
        self.assertIsInstance(self.engine.context, dict)
        self.assertEqual(len(self.engine.context), 0)

    def test_execute_function_call_success(self):
        """Function Call 실행 성공 테스트"""
        result = self.engine.execute_function_call(
            function_name="extract_version",
            function_arguments='{"text": "Release v2.0.1"}',
            call_id="call_1"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "2.0.1")
        self.assertIsNone(result["error"])

    def test_execute_function_call_with_invalid_tool(self):
        """존재하지 않는 Tool 호출 테스트"""
        result = self.engine.execute_function_call(
            function_name="invalid_tool",
            function_arguments='{}',
            call_id="call_2"
        )

        self.assertFalse(result["success"])
        self.assertIsNone(result["result"])
        self.assertIn("Unknown tool", result["error"])

    def test_execute_function_call_with_invalid_json(self):
        """잘못된 JSON 인자 테스트"""
        result = self.engine.execute_function_call(
            function_name="extract_version",
            function_arguments='invalid json',
            call_id="call_3"
        )

        self.assertFalse(result["success"])
        self.assertIn("JSON 파싱 실패", result["error"])

    def test_context_storage_and_retrieval(self):
        """Context 저장 및 조회 테스트"""
        test_data = [{"key": "BTVO-123", "status": "완료"}]

        self.engine.store_result("test_issues", test_data)
        retrieved = self.engine.get_context_value("test_issues")

        self.assertEqual(retrieved, test_data)

    def test_context_reference_resolution(self):
        """Context 참조 해결 테스트"""
        # Context에 데이터 저장
        test_issues = [
            {"key": "BTVO-123", "status": "완료"},
            {"key": "BTVO-124", "status": "신규"}
        ]
        self.engine.store_result("my_issues", test_issues)

        # Context 참조를 사용한 함수 호출
        result = self.engine.execute_function_call(
            function_name="find_issue_by_field",
            function_arguments='{"issues": "$my_issues", "field_name": "status", "field_value": "완료"}',
            call_id="call_4"
        )

        self.assertTrue(result["success"])
        self.assertIsNotNone(result["result"])
        self.assertEqual(result["result"]["key"], "BTVO-123")

    def test_clear_context(self):
        """Context 초기화 테스트"""
        self.engine.store_result("test", "value")
        self.assertEqual(len(self.engine.context), 1)

        self.engine.clear_context()
        self.assertEqual(len(self.engine.context), 0)
        self.assertEqual(len(self.engine.execution_history), 0)

    def test_execution_history(self):
        """실행 이력 테스트"""
        self.engine.execute_function_call(
            function_name="extract_version",
            function_arguments='{"text": "v1.0"}',
            call_id="call_5"
        )

        history = self.engine.get_execution_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["function"], "extract_version")
        self.assertTrue(history[0]["success"])

    def test_format_result_for_llm(self):
        """LLM용 결과 포맷팅 테스트"""
        # None
        result = self.engine.format_result_for_llm(None)
        self.assertIn("no_result", result)

        # List
        result = self.engine.format_result_for_llm([1, 2, 3])
        parsed = json.loads(result)
        self.assertEqual(parsed["type"], "list")
        self.assertEqual(parsed["count"], 3)

        # String
        result = self.engine.format_result_for_llm("test string")
        self.assertIn("test string", result)


@unittest.skipIf(not HAS_OPENAI, "openai 모듈이 설치되지 않음")
class TestMonthlyReportAgentMocked(unittest.TestCase):
    """Monthly Report Agent 테스트 (LLM 호출 Mocking)"""

    @patch('agent.monthly_report_agent.AzureOpenAI')
    def test_initialization(self, mock_azure_openai):
        """초기화 테스트"""
        mock_client = Mock()
        agent = MonthlyReportAgent(
            azure_client=mock_client,
            user_id=1,
            deployment_name="gpt-4",
            db_path="test.db"
        )

        self.assertIsNotNone(agent.registry)
        self.assertIsNotNone(agent.engine)
        self.assertEqual(agent.user_id, 1)
        self.assertEqual(agent.deployment, "gpt-4")

    @patch('agent.monthly_report_agent.AzureOpenAI')
    def test_reset(self, mock_azure_openai):
        """Agent 리셋 테스트"""
        mock_client = Mock()
        agent = MonthlyReportAgent(
            azure_client=mock_client,
            user_id=1,
            deployment_name="gpt-4"
        )

        # Context에 데이터 추가
        agent.engine.store_result("test", "value")
        self.assertEqual(len(agent.engine.context), 1)

        # Reset
        agent.reset()
        self.assertEqual(len(agent.engine.context), 0)


class TestDataToolsIntegration(unittest.TestCase):
    """Data Tools 통합 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.user_id = 1
        self.registry = ToolRegistry(user_id=self.user_id)
        self.engine = ExecutionEngine(self.registry)

        # 테스트용 이슈 데이터
        self.test_issues = [
            {"key": "BTVO-123", "status": "완료", "assignee": "김철수"},
            {"key": "BTVO-124", "status": "신규", "assignee": "박영희"},
            {"key": "BTVO-125", "status": "완료", "assignee": "김철수"}
        ]

    def test_data_processing_pipeline(self):
        """데이터 처리 파이프라인 테스트"""
        # 1. Context에 이슈 저장
        self.engine.store_result("all_issues", self.test_issues)

        # 2. filter_issues 실행
        result = self.engine.execute_function_call(
            function_name="filter_issues",
            function_arguments='{"issues": "$all_issues", "field_conditions": {"status": "완료"}}',
            call_id="call_1"
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]), 2)

        # 3. 결과 저장
        self.engine.store_result("completed_issues", result["result"])

        # 4. count_by_field 실행
        result = self.engine.execute_function_call(
            function_name="count_by_field",
            function_arguments='{"issues": "$completed_issues", "field_name": "assignee"}',
            call_id="call_2"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["김철수"], 2)

    def test_group_by_and_format(self):
        """그룹화 및 포맷팅 테스트"""
        # 1. Context에 이슈 저장
        self.engine.store_result("issues", self.test_issues)

        # 2. group_by_field 실행
        result = self.engine.execute_function_call(
            function_name="group_by_field",
            function_arguments='{"issues": "$issues", "field_name": "status"}',
            call_id="call_1"
        )

        self.assertTrue(result["success"])
        self.assertIn("완료", result["result"])
        self.assertIn("신규", result["result"])

        # 3. format_as_table 실행 (완료 그룹)
        self.engine.store_result("completed_group", result["result"]["완료"])

        result = self.engine.execute_function_call(
            function_name="format_as_table",
            function_arguments='{"data": "$completed_group", "columns": ["key", "assignee"]}',
            call_id="call_2"
        )

        self.assertTrue(result["success"])
        self.assertIn("BTVO-123", result["result"])
        self.assertIn("김철수", result["result"])


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 70)
    print("🧪 Agent 모듈 테스트")
    print("=" * 70)
    print()

    # 테스트 실행
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 모든 테스트 클래스 추가
    suite.addTests(loader.loadTestsFromTestCase(TestToolRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutionEngine))
    if HAS_OPENAI:
        suite.addTests(loader.loadTestsFromTestCase(TestMonthlyReportAgentMocked))
    suite.addTests(loader.loadTestsFromTestCase(TestDataToolsIntegration))

    # 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 결과 요약
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 모든 테스트 통과!")
        print(f"   총 {result.testsRun}개 테스트 실행")
    else:
        print("❌ 일부 테스트 실패")
        print(f"   실행: {result.testsRun}")
        print(f"   실패: {len(result.failures)}")
        print(f"   에러: {len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
