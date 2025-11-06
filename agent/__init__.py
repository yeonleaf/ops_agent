#!/usr/bin/env python3
"""
LLM Function Calling 기반 월간보고 자동 생성 Agent

이 모듈은 자연어 프롬프트를 받아 LLM이 자동으로 Tool 조합 실행 계획을 수립하고,
필요한 Tool들을 순차적으로 호출하여 최종 HTML 페이지를 생성합니다.
"""

from agent.tool_registry import ToolRegistry
from agent.execution_engine import ExecutionEngine

__all__ = [
    "ToolRegistry",
    "ExecutionEngine",
]

# MonthlyReportAgent는 openai 모듈이 필요하므로 조건부 import
try:
    from agent.monthly_report_agent import MonthlyReportAgent
    __all__.append("MonthlyReportAgent")
except ImportError:
    pass

__version__ = "1.0.0"
