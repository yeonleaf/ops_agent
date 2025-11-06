#!/usr/bin/env python3
"""
Report Service - 동적 보고서 생성 서비스

사용자가 선택한 프롬프트들을 조합하여 보고서 생성
"""

from typing import List, Dict
from datetime import datetime
import json

from models.report_models import Report, PromptTemplate
from services.prompt_service import PromptService
from agent.monthly_report_agent import MonthlyReportAgent


class ReportService:
    """동적 보고서 생성 서비스"""

    def __init__(
        self,
        db_session,
        agent: MonthlyReportAgent,
        prompt_service: PromptService = None
    ):
        """
        Args:
            db_session: SQLAlchemy 세션
            agent: MonthlyReportAgent 인스턴스
            prompt_service: PromptService (없으면 자동 생성)
        """
        self.db = db_session
        self.agent = agent
        self.prompt_service = prompt_service or PromptService(db_session)

    def generate_report(
        self,
        user_id: int,
        title: str,
        prompt_ids: List[int],
        include_toc: bool = True,
        save: bool = False
    ) -> Dict:
        """
        보고서 생성

        Args:
            user_id: 사용자 ID
            title: 보고서 제목
            prompt_ids: 프롬프트 ID 리스트
            include_toc: 목차 포함 여부
            save: 히스토리 저장 여부

        Returns:
            {
                "report_id": int or None,
                "html": str,
                "metadata": {...}
            }

        Raises:
            ValueError: 프롬프트 접근 권한 없음
        """
        print(f"\n{'='*80}")
        print(f"📊 동적 보고서 생성 시작")
        print(f"{'='*80}")
        print(f"사용자 ID: {user_id}")
        print(f"제목: {title}")
        print(f"프롬프트 개수: {len(prompt_ids)}")
        print(f"{'='*80}\n")

        # 1. 프롬프트 조회 (권한 체크 포함)
        prompts = self.prompt_service.get_prompts_by_ids(prompt_ids, user_id)
        print(f"✅ 프롬프트 조회 완료: {len(prompts)}개")

        # 2. HTML 생성
        html = self._build_html(prompts, title, include_toc)
        print(f"✅ HTML 생성 완료")

        # 3. 히스토리 저장
        report_id = None
        if save:
            report = Report(
                user_id=user_id,
                title=title,
                html_content=html,
                prompt_ids=json.dumps(prompt_ids)
            )
            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)
            report_id = report.id
            print(f"✅ 보고서 저장 완료: ID={report_id}")

        # 4. 메타데이터
        metadata = {
            'prompt_count': len(prompts),
            'categories': list(set(p.category for p in prompts)),
            'generation_time': datetime.now().isoformat()
        }

        print(f"\n{'='*80}")
        print(f"✨ 보고서 생성 완료")
        print(f"{'='*80}\n")

        return {
            'report_id': report_id,
            'html': html,
            'metadata': metadata
        }

    def _build_html(
        self,
        prompts: List[PromptTemplate],
        title: str,
        include_toc: bool
    ) -> str:
        """
        프롬프트들로 HTML 구성

        Args:
            prompts: 프롬프트 리스트
            title: 보고서 제목
            include_toc: 목차 포함 여부

        Returns:
            완전한 HTML 문서
        """
        # HTML 시작
        html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="/static/report.css">
    <style>
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .report-header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #4CAF50;
        }}
        .report-header h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .report-date {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}
        .toc {{
            background-color: #f8f9fa;
            padding: 20px;
            margin-bottom: 30px;
            border-left: 4px solid #4CAF50;
        }}
        .toc h2 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .toc ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        .toc li {{
            margin: 8px 0;
        }}
        .toc a {{
            color: #3498db;
            text-decoration: none;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
        .report-section {{
            margin-bottom: 40px;
        }}
        .report-section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .component {{
            margin: 20px 0;
        }}
        .component h3 {{
            color: #34495e;
            margin-bottom: 15px;
        }}
        .component-description {{
            color: #7f8c8d;
            font-style: italic;
            margin-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>{title}</h1>
            <p class="report-date">{datetime.now().strftime('%Y-%m-%d')}</p>
        </div>
'''

        # 목차
        if include_toc:
            html += self._generate_toc(prompts)

        # 카테고리별 그룹핑
        grouped = self._group_by_category(prompts)

        # 각 카테고리 섹션
        for i, (category, category_prompts) in enumerate(grouped.items(), 1):
            html += f'\n<section id="section-{i}" class="report-section">\n'
            html += f'<h2>{i}. {category}</h2>\n'

            for prompt in category_prompts:
                html += self._generate_component(prompt)

            html += '</section>\n'

        # HTML 종료
        html += '''
    </div>
</body>
</html>
'''

        return html

    def _generate_toc(self, prompts: List[PromptTemplate]) -> str:
        """목차 생성"""
        grouped = self._group_by_category(prompts)

        toc_html = '\n<div class="toc">\n'
        toc_html += '<h2>목차</h2>\n'
        toc_html += '<ul>\n'

        for i, (category, _) in enumerate(grouped.items(), 1):
            toc_html += f'<li><a href="#section-{i}">{i}. {category}</a></li>\n'

        toc_html += '</ul>\n'
        toc_html += '</div>\n'

        return toc_html

    def _group_by_category(self, prompts: List[PromptTemplate]) -> Dict[str, List[PromptTemplate]]:
        """카테고리별 그룹핑"""
        grouped = {}
        for prompt in prompts:
            if prompt.category not in grouped:
                grouped[prompt.category] = []
            grouped[prompt.category].append(prompt)
        return grouped

    def _generate_component(self, prompt: PromptTemplate) -> str:
        """
        개별 컴포넌트 생성 (Agent 실행)

        Args:
            prompt: 프롬프트 템플릿

        Returns:
            컴포넌트 HTML
        """
        print(f"\n{'─'*80}")
        print(f"📦 컴포넌트 생성: {prompt.title}")
        print(f"{'─'*80}")

        try:
            # Agent로 프롬프트 실행
            result = self.agent.generate_page(
                page_title=prompt.title,
                user_prompt=prompt.prompt_content,
                context=None,
                max_iterations=10,
                temperature=0.3
            )

            if not result.get('success'):
                error_msg = result.get('error', '알 수 없는 오류')
                print(f"❌ 컴포넌트 생성 실패: {error_msg}")
                return self._generate_error_component(prompt.title, error_msg)

            content = result.get('content', '')

            # Markdown 테이블을 HTML로 변환 (간단한 변환)
            html_content = self._markdown_to_html(content)

            component_html = f'''
<div class="component" id="prompt-{prompt.id}">
    <h3>{prompt.title}</h3>
    {f'<p class="component-description">{prompt.description}</p>' if prompt.description else ''}
    {html_content}
</div>
'''

            print(f"✅ 컴포넌트 생성 완료 (소요: {result.get('elapsed_time', 0):.2f}초)")

            return component_html

        except Exception as e:
            print(f"❌ 컴포넌트 생성 오류: {str(e)}")
            return self._generate_error_component(prompt.title, str(e))

    def _markdown_to_html(self, markdown: str) -> str:
        """Markdown 테이블을 HTML로 변환"""
        # 이미 HTML이면 그대로 반환
        if '<table' in markdown.lower():
            return markdown

        # Markdown 테이블 파싱
        lines = markdown.strip().split('\n')
        table_lines = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            if '|' in stripped:
                in_table = True
                # 구분선 제거
                if not all(c in '-:|' for c in stripped.replace(' ', '')):
                    table_lines.append(stripped)
            elif in_table and not stripped:
                break

        if not table_lines:
            return f'<pre>{markdown}</pre>'

        # HTML 테이블 생성
        html = '<table>\n'

        # 헤더
        if table_lines:
            header = table_lines[0]
            cols = [col.strip() for col in header.split('|') if col.strip()]
            html += '<thead>\n<tr>\n'
            for col in cols:
                html += f'<th>{col}</th>\n'
            html += '</tr>\n</thead>\n'

        # 데이터
        if len(table_lines) > 1:
            html += '<tbody>\n'
            for row in table_lines[1:]:
                cols = [col.strip() for col in row.split('|') if col.strip()]
                html += '<tr>\n'
                for col in cols:
                    html += f'<td>{col}</td>\n'
                html += '</tr>\n'
            html += '</tbody>\n'

        html += '</table>\n'

        return html

    def _generate_error_component(self, title: str, error_msg: str) -> str:
        """에러 컴포넌트 생성"""
        return f'''
<div class="component component-error">
    <h3>{title}</h3>
    <div class="error-message">
        <strong>⚠️ 컴포넌트 생성 실패</strong>
        <p>{error_msg}</p>
    </div>
</div>
'''

    def get_user_reports(self, user_id: int) -> List[Dict]:
        """사용자의 보고서 목록"""
        reports = self.db.query(Report)\
            .filter_by(user_id=user_id)\
            .order_by(Report.created_at.desc())\
            .all()

        return [r.to_dict() for r in reports]

    def get_report_by_id(self, user_id: int, report_id: int) -> Dict:
        """보고서 조회 (HTML 포함)"""
        report = self.db.query(Report)\
            .filter_by(id=report_id, user_id=user_id)\
            .first()

        if not report:
            raise ValueError("보고서를 찾을 수 없거나 권한이 없습니다")

        return report.to_dict(include_html=True)

    def delete_report(self, user_id: int, report_id: int) -> None:
        """보고서 삭제"""
        report = self.db.query(Report)\
            .filter_by(id=report_id, user_id=user_id)\
            .first()

        if not report:
            raise ValueError("보고서를 찾을 수 없거나 권한이 없습니다")

        self.db.delete(report)
        self.db.commit()


if __name__ == "__main__":
    print("Report Service 모듈")
    print("실제 테스트는 Agent 인스턴스가 필요합니다.")
