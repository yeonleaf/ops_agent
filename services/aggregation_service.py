#!/usr/bin/env python3
"""
Aggregation Service - 캐시된 Jira 이슈 집계/분석 서비스

PromptExecution에 캐시된 Jira 이슈들을 기반으로 통계 및 인사이트 생성
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import Counter
import json

from models.report_models import PromptExecution, PromptTemplate


class AggregationService:
    """캐시 기반 집계/분석 서비스"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def aggregate_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        prompt_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        날짜 범위 내 캐시된 이슈 집계

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            prompt_ids: 특정 프롬프트들만 집계 (None이면 전체)

        Returns:
            {
                "total_issues": int,
                "by_status": {...},
                "by_priority": {...},
                "by_assignee": {...},
                "by_label": {...},
                "executions_count": int
            }
        """
        # 날짜 범위 내 실행 결과 조회
        query = self.db.query(PromptExecution)\
            .filter(PromptExecution.executed_at >= start_date)\
            .filter(PromptExecution.executed_at <= end_date)

        if prompt_ids:
            query = query.filter(PromptExecution.prompt_id.in_(prompt_ids))

        executions = query.all()

        # 모든 이슈 수집
        all_issues = []
        for execution in executions:
            all_issues.extend(execution.get_jira_issues())

        # 중복 제거 (key 기준)
        unique_issues = {}
        for issue in all_issues:
            if 'key' in issue:
                unique_issues[issue['key']] = issue

        issues_list = list(unique_issues.values())

        # 집계
        return {
            "total_issues": len(issues_list),
            "by_status": self._count_by_field(issues_list, 'status'),
            "by_priority": self._count_by_field(issues_list, 'priority'),
            "by_assignee": self._count_by_field(issues_list, 'assignee'),
            "by_label": self._count_by_labels(issues_list),
            "by_type": self._count_by_field(issues_list, 'issuetype'),
            "executions_count": len(executions),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }

    def aggregate_by_prompt(self, prompt_id: int) -> Dict[str, Any]:
        """
        특정 프롬프트의 모든 실행 결과 집계

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            집계 결과
        """
        executions = self.db.query(PromptExecution)\
            .filter_by(prompt_id=prompt_id)\
            .order_by(PromptExecution.executed_at.desc())\
            .all()

        if not executions:
            return {
                "total_executions": 0,
                "total_issues": 0,
                "error": "실행 이력이 없습니다"
            }

        # 모든 이슈 수집
        all_issues = []
        for execution in executions:
            all_issues.extend(execution.get_jira_issues())

        # 중복 제거
        unique_issues = {}
        for issue in all_issues:
            if 'key' in issue:
                unique_issues[issue['key']] = issue

        issues_list = list(unique_issues.values())

        # 프롬프트 정보
        prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()

        return {
            "prompt_id": prompt_id,
            "prompt_title": prompt.title if prompt else "Unknown",
            "total_executions": len(executions),
            "total_issues": len(issues_list),
            "latest_execution": executions[0].executed_at.isoformat() if executions else None,
            "by_status": self._count_by_field(issues_list, 'status'),
            "by_priority": self._count_by_field(issues_list, 'priority'),
            "by_assignee": self._count_by_field(issues_list, 'assignee'),
            "by_label": self._count_by_labels(issues_list)
        }

    def get_completion_rate(
        self,
        start_date: datetime,
        end_date: datetime,
        prompt_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        이슈 완료율 계산

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            prompt_ids: 특정 프롬프트들만 (None이면 전체)

        Returns:
            {
                "total": int,
                "completed": int,
                "completion_rate": float,  # 0.0 ~ 1.0
                "by_status": {...}
            }
        """
        aggregate = self.aggregate_by_date_range(start_date, end_date, prompt_ids)

        total = aggregate['total_issues']
        by_status = aggregate['by_status']

        # 완료로 간주할 상태들
        completed_statuses = ['Done', 'Closed', 'Resolved', 'Completed']
        completed = sum(
            count for status, count in by_status.items()
            if status in completed_statuses
        )

        completion_rate = completed / total if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "in_progress": total - completed,
            "completion_rate": completion_rate,
            "by_status": by_status
        }

    def get_workload_distribution(
        self,
        start_date: datetime,
        end_date: datetime,
        prompt_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        담당자별 작업량 분포

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            prompt_ids: 특정 프롬프트들만

        Returns:
            {
                "by_assignee": {
                    "user1": {"total": 10, "done": 5, "in_progress": 5},
                    ...
                },
                "statistics": {...}
            }
        """
        aggregate = self.aggregate_by_date_range(start_date, end_date, prompt_ids)

        # 담당자별 상세 분석이 필요하면 raw issues 다시 조회
        query = self.db.query(PromptExecution)\
            .filter(PromptExecution.executed_at >= start_date)\
            .filter(PromptExecution.executed_at <= end_date)

        if prompt_ids:
            query = query.filter(PromptExecution.prompt_id.in_(prompt_ids))

        executions = query.all()

        all_issues = []
        for execution in executions:
            all_issues.extend(execution.get_jira_issues())

        # 중복 제거
        unique_issues = {}
        for issue in all_issues:
            if 'key' in issue:
                unique_issues[issue['key']] = issue

        issues_list = list(unique_issues.values())

        # 담당자별 분석
        workload = {}
        for issue in issues_list:
            assignee = issue.get('assignee', 'Unassigned')
            status = issue.get('status', 'Unknown')

            if assignee not in workload:
                workload[assignee] = {
                    "total": 0,
                    "done": 0,
                    "in_progress": 0,
                    "todo": 0
                }

            workload[assignee]["total"] += 1

            # 상태 분류
            if status in ['Done', 'Closed', 'Resolved', 'Completed']:
                workload[assignee]["done"] += 1
            elif status in ['In Progress', 'In Review', 'Testing']:
                workload[assignee]["in_progress"] += 1
            else:
                workload[assignee]["todo"] += 1

        # 통계
        total_assignees = len(workload)
        total_issues = sum(w["total"] for w in workload.values())
        avg_per_person = total_issues / total_assignees if total_assignees > 0 else 0

        return {
            "by_assignee": workload,
            "statistics": {
                "total_assignees": total_assignees,
                "total_issues": total_issues,
                "average_per_person": avg_per_person,
                "max_workload": max((w["total"] for w in workload.values()), default=0),
                "min_workload": min((w["total"] for w in workload.values()), default=0)
            }
        }

    def get_trend_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        interval_days: int = 7,
        prompt_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        시간대별 트렌드 분석

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            interval_days: 간격 (일)
            prompt_ids: 특정 프롬프트들만

        Returns:
            {
                "intervals": [
                    {"start": "...", "end": "...", "issues": int, "completed": int},
                    ...
                ],
                "trend": "increasing" | "decreasing" | "stable"
            }
        """
        intervals = []
        current = start_date

        while current < end_date:
            interval_end = min(current + timedelta(days=interval_days), end_date)

            agg = self.aggregate_by_date_range(current, interval_end, prompt_ids)

            intervals.append({
                "start": current.isoformat(),
                "end": interval_end.isoformat(),
                "total_issues": agg['total_issues'],
                "executions": agg['executions_count']
            })

            current = interval_end

        # 트렌드 판단 (간단한 로직)
        if len(intervals) >= 2:
            first_half = sum(i['total_issues'] for i in intervals[:len(intervals)//2])
            second_half = sum(i['total_issues'] for i in intervals[len(intervals)//2:])

            if second_half > first_half * 1.1:
                trend = "increasing"
            elif second_half < first_half * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "intervals": intervals,
            "trend": trend
        }

    def _count_by_field(self, issues: List[Dict], field: str) -> Dict[str, int]:
        """특정 필드별 이슈 개수 집계"""
        values = [issue.get(field, 'Unknown') for issue in issues]
        return dict(Counter(values))

    def _count_by_labels(self, issues: List[Dict]) -> Dict[str, int]:
        """라벨별 이슈 개수 집계"""
        all_labels = []
        for issue in issues:
            labels = issue.get('labels', [])
            if isinstance(labels, list):
                all_labels.extend(labels)
            elif isinstance(labels, str):
                all_labels.append(labels)

        return dict(Counter(all_labels))


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager
    from datetime import timedelta

    print("=== Aggregation Service 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_aggregation.db')
    db.create_tables()
    session = db.get_session()

    try:
        service = AggregationService(session)

        # 최근 30일 집계 테스트
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        result = service.aggregate_by_date_range(start_date, end_date)
        print(f"최근 30일 집계 결과:")
        print(f"  총 이슈: {result['total_issues']}개")
        print(f"  실행 횟수: {result['executions_count']}회")
        print(f"  상태별: {result['by_status']}")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
