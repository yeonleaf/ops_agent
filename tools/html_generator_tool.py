#!/usr/bin/env python3
"""
HTML Generator Tool - Jira 이슈 데이터를 HTML로 변환
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HTMLGeneratorTool:
    """
    Jira 이슈 데이터를 깔끔한 HTML 보고서로 변환
    """

    def __init__(self):
        self.styles = self._get_default_styles()

    def _get_default_styles(self) -> str:
        """
        기본 CSS 스타일 (인쇄용 포함)
        """
        return """
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', Arial, sans-serif;
                background: #f5f5f5;
                padding: 20px;
                color: #333;
                line-height: 1.6;
            }

            .report-header {
                background: white;
                max-width: 1200px;
                margin: 0 auto 20px;
                padding: 30px 40px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-left: 5px solid #4CAF50;
            }

            .report-title {
                font-size: 28px;
                font-weight: bold;
                color: #1a1a1a;
                margin-bottom: 10px;
            }

            .report-period {
                font-size: 16px;
                color: #666;
            }

            .page {
                background: white;
                max-width: 1200px;
                margin: 0 auto 30px;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                page-break-after: always;
            }

            .page-title {
                font-size: 24px;
                font-weight: bold;
                color: #1a1a1a;
                margin-bottom: 10px;
                padding-bottom: 10px;
                border-bottom: 3px solid #4CAF50;
            }

            .page-meta {
                font-size: 14px;
                color: #666;
                margin-bottom: 20px;
                padding: 10px;
                background: #f9f9f9;
                border-radius: 4px;
            }

            .user-section {
                margin-bottom: 30px;
            }

            .user-header {
                font-size: 18px;
                font-weight: 600;
                color: #1976D2;
                margin-bottom: 15px;
                padding: 10px;
                background: #E3F2FD;
                border-radius: 4px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                font-size: 13px;
            }

            th {
                background: #4CAF50;
                color: white;
                padding: 12px 10px;
                text-align: left;
                font-weight: 600;
                font-size: 13px;
                border-right: 1px solid rgba(255,255,255,0.2);
            }

            th:last-child {
                border-right: none;
            }

            td {
                padding: 10px;
                border-bottom: 1px solid #e0e0e0;
                vertical-align: top;
            }

            tr:hover {
                background: #f9f9f9;
            }

            tr:last-child td {
                border-bottom: none;
            }

            .issue-key {
                color: #1976D2;
                font-weight: 600;
                text-decoration: none;
                font-family: 'Courier New', monospace;
            }

            .issue-key:hover {
                text-decoration: underline;
            }

            .status-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                white-space: nowrap;
            }

            .status-신규 { background: #E3F2FD; color: #1976D2; }
            .status-진행중 { background: #FFF3E0; color: #F57C00; }
            .status-완료 { background: #E8F5E9; color: #388E3C; }
            .status-Done { background: #E8F5E9; color: #388E3C; }
            .status-보류 { background: #F3E5F5; color: #7B1FA2; }
            .status-취소 { background: #FFEBEE; color: #C62828; }

            .summary {
                max-width: 400px;
                word-wrap: break-word;
                line-height: 1.4;
            }

            .labels {
                display: flex;
                flex-wrap: wrap;
                gap: 4px;
            }

            .label-tag {
                display: inline-block;
                padding: 2px 8px;
                background: #E0E0E0;
                color: #555;
                border-radius: 4px;
                font-size: 11px;
            }

            .empty-state {
                text-align: center;
                padding: 40px;
                color: #999;
                font-size: 14px;
            }

            /* 인쇄용 스타일 */
            @media print {
                body {
                    background: white;
                    padding: 0;
                }

                .report-header,
                .page {
                    box-shadow: none;
                    page-break-after: always;
                    margin-bottom: 0;
                }

                .page:last-child {
                    page-break-after: auto;
                }

                tr:hover {
                    background: transparent !important;
                }

                .issue-key {
                    color: #1976D2 !important;
                    text-decoration: none !important;
                }
            }

            /* 반응형 */
            @media (max-width: 768px) {
                body {
                    padding: 10px;
                }

                .report-header,
                .page {
                    padding: 20px;
                }

                .report-title {
                    font-size: 22px;
                }

                .page-title {
                    font-size: 20px;
                }

                table {
                    font-size: 12px;
                }

                th, td {
                    padding: 8px 6px;
                }

                .summary {
                    max-width: 200px;
                }
            }
        </style>
        """

    def generate_table(
        self,
        issues: List[Dict],
        columns: List[str],
        column_labels: Optional[Dict[str, str]] = None,
        group_by_user: bool = True
    ) -> str:
        """
        이슈 데이터를 표로 변환

        Args:
            issues: 이슈 목록
            columns: 표시할 컬럼 리스트
            column_labels: 컬럼 한글 라벨
            group_by_user: 유저별로 그룹화 여부
        """
        if column_labels is None:
            column_labels = {
                "key": "이슈 키",
                "summary": "제목",
                "status": "상태",
                "assignee": "담당자",
                "created": "생성일",
                "updated": "수정일",
                "priority": "우선순위",
                "reporter": "보고자",
                "labels": "라벨",
                "components": "컴포넌트",
                "issuetype": "유형",
                "fixVersions": "수정 버전"
            }

        if not issues:
            return '<div class="empty-state">📭 조회된 이슈가 없습니다.</div>'

        html = ''

        # 유저별로 그룹화
        if group_by_user and any('_query_user' in issue for issue in issues):
            # 유저별로 이슈 분류
            user_issues = {}
            for issue in issues:
                user = issue.get('_query_user', 'Unknown')
                if user not in user_issues:
                    user_issues[user] = []
                user_issues[user].append(issue)

            # 유저별로 테이블 생성
            for user, user_issue_list in user_issues.items():
                html += f'<div class="user-section">'
                html += f'<div class="user-header">👤 {user} ({len(user_issue_list)}개 이슈)</div>'
                html += self._generate_table_html(user_issue_list, columns, column_labels)
                html += '</div>'
        else:
            # 전체 이슈를 하나의 테이블로
            html += self._generate_table_html(issues, columns, column_labels)

        return html

    def _generate_table_html(
        self,
        issues: List[Dict],
        columns: List[str],
        column_labels: Dict[str, str]
    ) -> str:
        """
        실제 테이블 HTML 생성 (내부 헬퍼)
        """
        html = '<table>'

        # 헤더
        html += '<thead><tr>'
        for col in columns:
            label = column_labels.get(col, col)
            html += f'<th>{label}</th>'
        html += '</tr></thead>'

        # 바디
        html += '<tbody>'
        for issue in issues:
            html += '<tr>'
            for col in columns:
                value = issue.get(col, '')
                html += f'<td>{self._format_cell_value(col, value)}</td>'
            html += '</tr>'
        html += '</tbody>'

        html += '</table>'
        return html

    def _format_cell_value(self, column: str, value) -> str:
        """
        셀 값 포맷팅
        """
        if value is None or value == '':
            return '-'

        # 이슈 키: 스타일 적용
        if column == 'key':
            return f'<span class="issue-key">{value}</span>'

        # 상태: 배지
        elif column == 'status':
            # 상태명에서 특수문자 제거
            status_class = f'status-{value.replace(" ", "")}'
            return f'<span class="status-badge {status_class}">{value}</span>'

        # 제목: 긴 텍스트 처리
        elif column == 'summary':
            return f'<div class="summary" title="{value}">{value}</div>'

        # 날짜: 포맷팅
        elif column in ['created', 'updated']:
            try:
                # ISO 8601 형식 파싱
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M')
            except:
                return value

        # 라벨: 태그 형식
        elif column == 'labels' and isinstance(value, list):
            if not value:
                return '-'
            tags_html = '<div class="labels">'
            for label in value:
                tags_html += f'<span class="label-tag">{label}</span>'
            tags_html += '</div>'
            return tags_html

        # 리스트: 쉼표로 구분
        elif isinstance(value, list):
            if not value:
                return '-'
            return ', '.join(str(v) for v in value)

        # 기본
        return str(value)

    def generate_page(
        self,
        page_title: str,
        issues: List[Dict],
        output_format: Dict,
        report_period: Optional[str] = None
    ) -> str:
        """
        단일 페이지 HTML 생성

        Args:
            page_title: 페이지 제목
            issues: 이슈 목록
            output_format: {"type": "table", "columns": [...]}
            report_period: 보고 기간
        """
        # 메타 정보
        meta_parts = [f"이슈 수: {len(issues)}개"]
        if report_period:
            meta_parts.append(f"기간: {report_period}")

        # 유저별 통계
        if issues and any('_query_user' in issue for issue in issues):
            user_counts = {}
            for issue in issues:
                user = issue.get('_query_user', 'Unknown')
                user_counts[user] = user_counts.get(user, 0) + 1
            meta_parts.append(f"대상 유저: {', '.join(f'{u}({c})' for u, c in user_counts.items())}")

        meta_info = ' | '.join(meta_parts)

        # 콘텐츠 생성
        if output_format.get('type') == 'table':
            columns = output_format.get('columns', ['key', 'summary', 'status', 'assignee'])
            content = self.generate_table(issues, columns, group_by_user=True)
        else:
            content = f'<div class="empty-state">⚠️ 지원하지 않는 출력 형식: {output_format.get("type")}</div>'

        html = f"""
        <div class="page">
            <h2 class="page-title">{page_title}</h2>
            <div class="page-meta">{meta_info}</div>
            {content}
        </div>
        """

        return html

    def generate_full_report(
        self,
        pages_data: List[Dict],
        report_title: str = "월간 보고서",
        report_period: Optional[str] = None
    ) -> str:
        """
        전체 보고서 HTML 생성

        Args:
            pages_data: [{"page_title": "...", "issues": [...], "output_format": {...}}]
            report_title: 보고서 제목
            report_period: 보고 기간
        """
        logger.info(f"📄 HTML 보고서 생성 시작: {report_title}")

        # 헤더 생성
        header_html = f"""
        <div class="report-header">
            <h1 class="report-title">📊 {report_title}</h1>
            <div class="report-period">
                생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}
                {f' | 보고 기간: {report_period}' if report_period else ''}
            </div>
        </div>
        """

        # 페이지별 HTML 생성
        pages_html = []
        for i, page_data in enumerate(pages_data):
            logger.info(f"  페이지 {i+1}/{len(pages_data)}: {page_data['page_title']}")
            page_html = self.generate_page(
                page_title=page_data['page_title'],
                issues=page_data['issues'],
                output_format=page_data['output_format'],
                report_period=report_period
            )
            pages_html.append(page_html)

        # 전체 HTML 조합
        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    {self.styles}
</head>
<body>
    {header_html}
    {''.join(pages_html)}
</body>
</html>"""

        logger.info(f"✅ HTML 보고서 생성 완료 (크기: {len(full_html)} bytes)")
        return full_html


if __name__ == "__main__":
    # 간단한 테스트
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧪 HTMLGeneratorTool 테스트")
    print("=" * 60)

    tool = HTMLGeneratorTool()

    # 샘플 데이터
    sample_issues = [
        {
            "key": "BTVO-123",
            "summary": "[NCMS] 테스트 이슈 - 긴 제목 테스트를 위한 샘플 데이터입니다",
            "status": "신규",
            "assignee": "홍길동",
            "created": "2025-10-15T10:30:00",
            "_query_user": "user1"
        },
        {
            "key": "BTVO-124",
            "summary": "두 번째 이슈",
            "status": "완료",
            "assignee": "김철수",
            "created": "2025-10-16T14:20:00",
            "_query_user": "user1"
        },
        {
            "key": "PROJ-456",
            "summary": "다른 프로젝트 이슈",
            "status": "진행중",
            "assignee": "박영희",
            "created": "2025-10-17T09:00:00",
            "_query_user": "user2"
        }
    ]

    output_format = {
        "type": "table",
        "columns": ["key", "summary", "status", "assignee", "created"]
    }

    # HTML 생성
    html = tool.generate_full_report(
        pages_data=[{
            "page_title": "테스트 페이지",
            "issues": sample_issues,
            "output_format": output_format
        }],
        report_title="테스트 월간 보고서",
        report_period="2025-10"
    )

    # 파일로 저장
    output_file = "test_output.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ {output_file} 생성 완료!")
    print(f"   파일 크기: {len(html)} bytes")
    print(f"   브라우저로 확인하세요: file://{output_file}")
    print("=" * 60)
