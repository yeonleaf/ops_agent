#!/usr/bin/env python3
"""
Execution Service - 프롬프트 실행 및 캐싱 서비스

프롬프트를 MonthlyReportAgent로 실행하고, 결과를 PromptExecution에 캐시합니다.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from models.report_models import PromptExecution, PromptTemplate
from agent.monthly_report_agent import MonthlyReportAgent


class ExecutionService:
    """프롬프트 실행 및 캐싱 서비스"""

    def __init__(self, db_session, agent: MonthlyReportAgent):
        """
        Args:
            db_session: SQLAlchemy 세션
            agent: MonthlyReportAgent 인스턴스
        """
        self.db = db_session
        self.agent = agent

    def execute_prompt(
        self,
        prompt_id: int,
        context: Optional[Dict] = None,
        save_to_cache: bool = True
    ) -> Dict[str, Any]:
        """
        프롬프트를 실행하고 결과를 캐시에 저장

        Args:
            prompt_id: 프롬프트 ID
            context: 실행 컨텍스트 (기간, 대상 유저 등)
            save_to_cache: 캐시 저장 여부

        Returns:
            {
                "success": bool,
                "execution_id": str,  # PromptExecution.id
                "html_output": str,   # HTML fragment
                "jira_issues": [...]  # 조회된 Jira 이슈 목록
                "metadata": {...},
                "error": str
            }
        """
        print(f"\n{'='*80}")
        print(f"📦 프롬프트 실행 시작 (ID: {prompt_id})")
        print(f"{'='*80}\n")

        # 1. 프롬프트 조회
        prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()
        if not prompt:
            return {
                "success": False,
                "error": f"프롬프트 ID {prompt_id}를 찾을 수 없습니다"
            }

        print(f"프롬프트: {prompt.title}")
        print(f"카테고리: {prompt.category}")

        # 2. Agent로 프롬프트 실행
        try:
            result = self.agent.generate_page(
                page_title=prompt.title,
                user_prompt=prompt.prompt_content,
                context=context,
                max_iterations=10,
                temperature=0.3
            )

            if not result.get('success'):
                return {
                    "success": False,
                    "error": result.get('error', '알 수 없는 오류')
                }

            html_output = result.get('content', '')
            execution_history = result.get('execution_history', [])

            # 3. Jira 이슈 추출
            jira_issues = self._extract_jira_issues(execution_history)

            # 4. 메타데이터 생성
            metadata = {
                "prompt_title": prompt.title,
                "prompt_category": prompt.category,
                "execution_time": result.get('elapsed_time', 0),
                "tool_calls": len(execution_history),
                "context": context or {},
                "agent_metadata": result.get('metadata', {})
            }

            # 5. 캐시에 저장
            execution_id = None
            if save_to_cache:
                execution_id = self._save_to_cache(
                    prompt_id=prompt_id,
                    html_output=html_output,
                    jira_issues=jira_issues,
                    metadata=metadata
                )
                print(f"\n✅ 실행 결과 캐시 저장 완료 (execution_id: {execution_id})")

            print(f"\n{'='*80}")
            print(f"✨ 프롬프트 실행 완료")
            print(f"{'='*80}\n")

            return {
                "success": True,
                "execution_id": execution_id,
                "html_output": html_output,
                "jira_issues": jira_issues,
                "metadata": metadata
            }

        except Exception as e:
            print(f"\n❌ 실행 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def execute_multiple_prompts(
        self,
        prompt_ids: list,
        context: Optional[Dict] = None,
        save_to_cache: bool = True
    ) -> Dict[str, Any]:
        """
        여러 프롬프트를 순차 실행

        Args:
            prompt_ids: 프롬프트 ID 리스트
            context: 실행 컨텍스트
            save_to_cache: 캐시 저장 여부

        Returns:
            {
                "success": bool,
                "results": {prompt_id: result_dict},
                "summary": {...}
            }
        """
        print(f"\n{'='*80}")
        print(f"🚀 다중 프롬프트 실행 시작 ({len(prompt_ids)}개)")
        print(f"{'='*80}\n")

        results = {}
        success_count = 0
        fail_count = 0

        for prompt_id in prompt_ids:
            result = self.execute_prompt(prompt_id, context, save_to_cache)
            results[prompt_id] = result

            if result.get('success'):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"✨ 다중 실행 완료: 성공 {success_count}개, 실패 {fail_count}개")
        print(f"{'='*80}\n")

        return {
            "success": fail_count == 0,
            "results": results,
            "summary": {
                "total": len(prompt_ids),
                "success": success_count,
                "failed": fail_count
            }
        }

    def _extract_jira_issues(self, execution_history: list) -> list:
        """
        실행 이력에서 Jira 이슈 추출

        Args:
            execution_history: Agent의 execution_history

        Returns:
            Jira 이슈 리스트
        """
        jira_issues = []

        for record in execution_history:
            func_name = record.get("function", "")
            result = record.get("result", {})

            # search_issues 함수의 결과에서 이슈 추출
            if func_name == "search_issues":
                if isinstance(result, list):
                    jira_issues.extend(result)
                elif isinstance(result, dict) and 'issues' in result:
                    jira_issues.extend(result['issues'])

            # get_cached_issues 함수의 결과에서 이슈 추출
            elif func_name == "get_cached_issues":
                if isinstance(result, list):
                    jira_issues.extend(result)

        # 중복 제거 (issue key 기준)
        unique_issues = {}
        for issue in jira_issues:
            if isinstance(issue, dict) and 'key' in issue:
                unique_issues[issue['key']] = issue

        return list(unique_issues.values())

    def _save_to_cache(
        self,
        prompt_id: int,
        html_output: str,
        jira_issues: list,
        metadata: dict
    ) -> str:
        """
        실행 결과를 캐시에 저장

        Args:
            prompt_id: 프롬프트 ID
            html_output: HTML fragment
            jira_issues: Jira 이슈 목록
            metadata: 메타데이터

        Returns:
            execution_id (UUID)
        """
        execution = PromptExecution(
            prompt_id=prompt_id,
            html_output=html_output
        )

        # Jira 이슈 저장
        execution.set_jira_issues(jira_issues)

        # 메타데이터 저장
        execution.set_metadata(metadata)

        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        return execution.id

    def get_latest_execution(self, prompt_id: int) -> Optional[Dict]:
        """
        프롬프트의 최신 실행 결과 조회

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            실행 결과 딕셔너리 또는 None
        """
        execution = self.db.query(PromptExecution)\
            .filter_by(prompt_id=prompt_id)\
            .order_by(PromptExecution.executed_at.desc())\
            .first()

        if not execution:
            return None

        return execution.to_dict(include_content=True)

    def get_all_executions(self, prompt_id: int) -> list:
        """
        프롬프트의 모든 실행 이력 조회

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            실행 이력 리스트
        """
        executions = self.db.query(PromptExecution)\
            .filter_by(prompt_id=prompt_id)\
            .order_by(PromptExecution.executed_at.desc())\
            .all()

        return [e.to_dict() for e in executions]

    def delete_execution(self, execution_id: str) -> bool:
        """
        실행 결과 삭제

        Args:
            execution_id: 실행 ID (UUID)

        Returns:
            성공 여부
        """
        execution = self.db.query(PromptExecution)\
            .filter_by(id=execution_id)\
            .first()

        if not execution:
            return False

        self.db.delete(execution)
        self.db.commit()

        return True


if __name__ == "__main__":
    print("Execution Service 모듈")
    print("실제 테스트는 Agent 인스턴스가 필요합니다.")
