#!/usr/bin/env python3
"""
LLM Agent Tools 종합 테스트

모든 원자적 Tool들의 단위 테스트를 포함합니다.
"""

import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime

# Import tools
from tools.text_tools import (
    extract_version,
    extract_pattern,
    extract_all_patterns,
    format_date,
    clean_whitespace,
    truncate_text,
)

from tools.data_tools import (
    find_issue_by_field,
    find_all_issues_by_field,
    group_by_field,
    filter_issues,
    sort_issues,
    extract_field_values,
    count_by_field,
)

from tools.format_tools import (
    format_as_table,
    format_as_list,
    format_as_json,
    format_as_csv,
    format_as_summary,
    format_key_value,
    wrap_text,
)


class TestTextTools(unittest.TestCase):
    """텍스트 처리 도구 테스트"""

    def test_extract_version(self):
        """버전 추출 테스트"""
        self.assertEqual(extract_version("Release v1.2.3"), "1.2.3")
        self.assertEqual(extract_version("버전 2.0 배포"), "2.0")
        self.assertEqual(extract_version("[NCMS] v10.5.2 배포"), "10.5.2")
        self.assertIsNone(extract_version("no version here"))
        self.assertIsNone(extract_version(""))
        self.assertIsNone(extract_version(None))

    def test_extract_pattern(self):
        """정규표현식 추출 테스트"""
        self.assertEqual(extract_pattern("BTVO-61032", r"[A-Z]+-\d+"), "BTVO-61032")
        self.assertEqual(extract_pattern("[NCMS] 작업 완료", r"\[([A-Z]+)\]", group=1), "NCMS")
        self.assertEqual(extract_pattern("priority: High", r"priority:\s*(\w+)", group=1), "High")
        self.assertIsNone(extract_pattern("no match here", r"\d{4}"))
        self.assertIsNone(extract_pattern("", r"\d+"))
        self.assertIsNone(extract_pattern("test", ""))

    def test_extract_all_patterns(self):
        """모든 패턴 추출 테스트"""
        result = extract_all_patterns("BTVO-123, PROJ-456", r"[A-Z]+-\d+")
        self.assertEqual(result, ["BTVO-123", "PROJ-456"])

        result = extract_all_patterns("v1.2, v2.0, v3.1", r"v(\d+\.\d+)")
        self.assertEqual(result, ["1.2", "2.0", "3.1"])

        self.assertEqual(extract_all_patterns("no match", r"\d{4}"), [])
        self.assertEqual(extract_all_patterns("", r"\d+"), [])

    def test_format_date(self):
        """날짜 포맷 변환 테스트"""
        self.assertEqual(format_date("2025-10-15T10:30:00"), "2025-10-15")
        self.assertEqual(
            format_date("2025-10-15T10:30:00", "%Y년 %m월 %d일"),
            "2025년 10월 15일"
        )
        self.assertEqual(format_date("2025-10-15", "%m/%d"), "10/15")
        self.assertIsNone(format_date("invalid date"))
        self.assertIsNone(format_date(""))
        self.assertIsNone(format_date(None))

    def test_clean_whitespace(self):
        """공백 정리 테스트"""
        self.assertEqual(clean_whitespace("  hello   world  "), "hello world")
        self.assertEqual(clean_whitespace("multiple\n\n\nlines"), "multiple lines")
        self.assertEqual(clean_whitespace("  "), "")
        self.assertEqual(clean_whitespace(""), "")
        self.assertEqual(clean_whitespace(None), "")

    def test_truncate_text(self):
        """텍스트 자르기 테스트"""
        self.assertEqual(truncate_text("This is a long text", 10), "This is...")
        self.assertEqual(truncate_text("Short", 10), "Short")
        # max_length=8이므로 suffix 포함해서 8글자: "Long te" (7) + "…" (1) = 8
        self.assertEqual(truncate_text("Long text here", 8, "…"), "Long te…")
        self.assertEqual(truncate_text("", 10), "")
        self.assertEqual(truncate_text(None, 10), "")


class TestDataTools(unittest.TestCase):
    """데이터 처리 도구 테스트"""

    def setUp(self):
        """테스트용 샘플 이슈 데이터"""
        self.issues = [
            {"key": "BTVO-123", "status": "신규", "assignee": "김철수", "priority": "High"},
            {"key": "BTVO-124", "status": "완료", "assignee": "김철수", "priority": "Low"},
            {"key": "PROJ-456", "status": "신규", "assignee": "박영희", "priority": "Medium"},
            {"key": "PROJ-457", "status": "진행중", "assignee": "박영희", "priority": "High"},
        ]

    def test_find_issue_by_field(self):
        """필드로 이슈 찾기 테스트"""
        result = find_issue_by_field(self.issues, "key", "BTVO-123")
        self.assertEqual(result["key"], "BTVO-123")

        result = find_issue_by_field(self.issues, "status", "완료")
        self.assertEqual(result["key"], "BTVO-124")

        result = find_issue_by_field(self.issues, "key", "BTVO", exact_match=False)
        self.assertEqual(result["key"], "BTVO-123")

        result = find_issue_by_field(self.issues, "key", "NOTFOUND")
        self.assertIsNone(result)

    def test_find_all_issues_by_field(self):
        """필드로 모든 이슈 찾기 테스트"""
        results = find_all_issues_by_field(self.issues, "status", "신규")
        self.assertEqual(len(results), 2)

        results = find_all_issues_by_field(self.issues, "assignee", "김철수")
        self.assertEqual(len(results), 2)

        results = find_all_issues_by_field(self.issues, "key", "BTVO", exact_match=False)
        self.assertEqual(len(results), 2)

        results = find_all_issues_by_field(self.issues, "status", "NOTFOUND")
        self.assertEqual(len(results), 0)

    def test_group_by_field(self):
        """필드로 그룹화 테스트"""
        groups = group_by_field(self.issues, "status")
        self.assertEqual(len(groups["신규"]), 2)
        self.assertEqual(len(groups["완료"]), 1)

        groups = group_by_field(self.issues, "assignee")
        self.assertEqual(len(groups["김철수"]), 2)
        self.assertEqual(len(groups["박영희"]), 2)

    def test_filter_issues(self):
        """이슈 필터링 테스트"""
        results = filter_issues(self.issues, status="신규")
        self.assertEqual(len(results), 2)

        results = filter_issues(self.issues, status="신규", priority="High")
        self.assertEqual(len(results), 1)

        results = filter_issues(
            self.issues,
            filter_func=lambda x: x.get("priority") == "High"
        )
        self.assertEqual(len(results), 2)

    def test_sort_issues(self):
        """이슈 정렬 테스트"""
        sorted_issues = sort_issues(self.issues, "priority")
        self.assertEqual(sorted_issues[0]["priority"], "High")

        sorted_issues = sort_issues(self.issues, "key", reverse=True)
        self.assertEqual(sorted_issues[0]["key"], "PROJ-457")

    def test_extract_field_values(self):
        """필드 값 추출 테스트"""
        values = extract_field_values(self.issues, "assignee")
        self.assertEqual(len(values), 4)

        values = extract_field_values(self.issues, "assignee", unique=True)
        self.assertEqual(len(values), 2)
        self.assertIn("김철수", values)
        self.assertIn("박영희", values)

    def test_count_by_field(self):
        """필드별 개수 집계 테스트"""
        counts = count_by_field(self.issues, "status")
        self.assertEqual(counts["신규"], 2)
        self.assertEqual(counts["완료"], 1)
        self.assertEqual(counts["진행중"], 1)

        counts = count_by_field(self.issues, "assignee")
        self.assertEqual(counts["김철수"], 2)
        self.assertEqual(counts["박영희"], 2)


class TestFormatTools(unittest.TestCase):
    """포맷팅 도구 테스트"""

    def setUp(self):
        """테스트용 샘플 데이터"""
        self.data = [
            {"key": "BTVO-123", "status": "신규", "assignee": "김철수", "summary": "작업1"},
            {"key": "PROJ-456", "status": "완료", "assignee": "박영희", "summary": "작업2"},
        ]

    def test_format_as_table(self):
        """테이블 포맷 테스트"""
        result = format_as_table(self.data)
        # 공백 개수와 상관없이 컬럼명이 있는지 확인
        self.assertIn("key", result)
        self.assertIn("status", result)
        self.assertIn("BTVO-123", result)
        self.assertIn("신규", result)
        self.assertIn("|", result)  # 테이블 구분자 확인

        result = format_as_table(self.data, columns=["key"])
        self.assertIn("key", result)
        self.assertNotIn("status", result)

    def test_format_as_list(self):
        """리스트 포맷 테스트"""
        result = format_as_list(self.data)
        self.assertIn("- BTVO-123:", result)
        self.assertIn("- PROJ-456:", result)

        result = format_as_list(
            self.data,
            template="[{key}] {status}",
            bullet="• "
        )
        self.assertIn("• [BTVO-123] 신규", result)

    def test_format_as_json(self):
        """JSON 포맷 테스트"""
        data = {"key": "BTVO-123", "status": "신규"}
        result = format_as_json(data)
        self.assertIn('"key"', result)
        self.assertIn('"BTVO-123"', result)
        self.assertIn('"status"', result)

    def test_format_as_csv(self):
        """CSV 포맷 테스트"""
        result = format_as_csv(self.data)
        self.assertIn("key,status,assignee", result)
        self.assertIn("BTVO-123,신규,김철수", result)

        result = format_as_csv(self.data, delimiter="|")
        self.assertIn("key|status|assignee", result)

        result = format_as_csv(self.data, include_header=False)
        self.assertNotIn("key,status", result)

    def test_format_as_summary(self):
        """요약 포맷 테스트"""
        result = format_as_summary(self.data, group_by="status")
        self.assertIn("총 2개 이슈", result)
        self.assertIn("status별 분포:", result)
        self.assertIn("신규:", result)
        self.assertIn("완료:", result)

    def test_format_key_value(self):
        """Key-Value 포맷 테스트"""
        data = {"key": "BTVO-123", "status": "신규", "priority": "High"}
        result = format_key_value(data)
        self.assertIn("key: BTVO-123", result)
        self.assertIn("status: 신규", result)

        result = format_key_value(data, indent=2, separator=" = ")
        self.assertIn("  key = BTVO-123", result)

    def test_wrap_text(self):
        """텍스트 줄바꿈 테스트"""
        text = "This is a very long text that needs to be wrapped properly"
        result = wrap_text(text, width=20)
        lines = result.split("\n")
        for line in lines:
            self.assertLessEqual(len(line), 20)


class TestEdgeCases(unittest.TestCase):
    """엣지 케이스 및 에러 처리 테스트"""

    def test_empty_inputs(self):
        """빈 입력 처리 테스트"""
        # Text tools
        self.assertIsNone(extract_version(""))
        self.assertIsNone(extract_pattern("", r"\d+"))
        self.assertEqual(extract_all_patterns("", r"\d+"), [])
        self.assertIsNone(format_date(""))
        self.assertEqual(clean_whitespace(""), "")
        self.assertEqual(truncate_text("", 10), "")

        # Data tools
        self.assertIsNone(find_issue_by_field([], "key", "test"))
        self.assertEqual(find_all_issues_by_field([], "key", "test"), [])
        self.assertEqual(group_by_field([], "key"), {})
        self.assertEqual(filter_issues([], status="test"), [])
        self.assertEqual(sort_issues([], "key"), [])
        self.assertEqual(extract_field_values([], "key"), [])
        self.assertEqual(count_by_field([], "key"), {})

        # Format tools
        self.assertIn("(데이터 없음)", format_as_table([]))
        self.assertEqual(format_as_list([]), "(데이터 없음)")
        self.assertEqual(format_as_csv([]), "(데이터 없음)")

    def test_invalid_types(self):
        """잘못된 타입 처리 테스트"""
        # Text tools
        self.assertIsNone(extract_version(123))
        self.assertIsNone(extract_pattern(None, r"\d+"))
        self.assertEqual(clean_whitespace(123), "")

        # Data tools
        self.assertIsNone(find_issue_by_field("not a list", "key", "test"))
        self.assertEqual(group_by_field("not a list", "key"), {})

    def test_none_values(self):
        """None 값 처리 테스트"""
        issues = [
            {"key": "BTVO-123", "status": None},
            {"key": "BTVO-124", "status": "완료"},
        ]

        groups = group_by_field(issues, "status")
        self.assertIn("(없음)", groups)

        counts = count_by_field(issues, "status")
        self.assertEqual(counts["(없음)"], 1)


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 70)
    print("🧪 LLM Agent Tools 종합 테스트")
    print("=" * 70)
    print()

    # 테스트 실행
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 모든 테스트 클래스 추가
    suite.addTests(loader.loadTestsFromTestCase(TestTextTools))
    suite.addTests(loader.loadTestsFromTestCase(TestDataTools))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatTools))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

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
