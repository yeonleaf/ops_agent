#!/usr/bin/env python3
"""
Group Report Service - 그룹 보고서 생성 서비스

그룹 멤버들이 작성한 프롬프트를 카테고리별, 시스템별로 계층화하여 보고서 생성
"""

from typing import List, Dict, Optional
from datetime import datetime
import json
from collections import defaultdict

from models.report_models import Report, PromptTemplate, UserGroup
from services.prompt_service import PromptService
from services.group_service import GroupService
from agent.monthly_report_agent import MonthlyReportAgent


class GroupReportService:
    """그룹 보고서 생성 서비스"""

    def __init__(
        self,
        db_session,
        agent: MonthlyReportAgent,
        prompt_service: PromptService = None,
        group_service: GroupService = None
    ):
        """
        Args:
            db_session: SQLAlchemy 세션
            agent: MonthlyReportAgent 인스턴스
            prompt_service: PromptService (없으면 자동 생성)
            group_service: GroupService (없으면 자동 생성)
        """
        self.db = db_session
        self.agent = agent
        self.prompt_service = prompt_service or PromptService(db_session)
        self.group_service = group_service or GroupService(db_session)

    def generate_group_report(
        self,
        user_id: int,
        group_id: int,
        title: str,
        prompt_ids: List[int],
        include_toc: bool = True,
        save: bool = True
    ) -> Dict:
        """
        그룹 보고서 생성

        Args:
            user_id: 요청 사용자 ID (그룹 멤버여야 함)
            group_id: 그룹 ID
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
            PermissionError: 그룹 멤버가 아님
            ValueError: 프롬프트 접근 권한 없음
        """
        print(f"\n{'='*80}")
        print(f"📊 그룹 보고서 생성 시작")
        print(f"{'='*80}")
        print(f"그룹 ID: {group_id}")
        print(f"요청자 ID: {user_id}")
        print(f"제목: {title}")
        print(f"프롬프트 개수: {len(prompt_ids)}")
        print(f"{'='*80}\n")

        # 1. 그룹 멤버 권한 체크
        if not self.group_service.is_group_member(group_id, user_id):
            raise PermissionError("이 그룹의 멤버가 아닙니다")

        # 2. 그룹 정보 조회
        group = self.db.query(UserGroup).filter_by(id=group_id).first()
        if not group:
            raise ValueError(f"그룹을 찾을 수 없습니다 (ID: {group_id})")

        # 3. 프롬프트 조회 (group_id로 필터링된 것만)
        prompts = self._get_group_prompts_by_ids(group_id, prompt_ids)
        print(f"✅ 그룹 프롬프트 조회 완료: {len(prompts)}개")

        # 4. HTML 생성 (계층적 넘버링)
        html = self._build_hierarchical_html(prompts, title, group.name, include_toc)
        print(f"✅ 계층적 HTML 생성 완료")

        # 5. 히스토리 저장
        report_id = None
        if save:
            report = Report(
                user_id=user_id,
                group_id=group_id,
                report_type='group',
                title=title,
                html_content=html,
                prompt_ids=json.dumps(prompt_ids)
            )
            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)
            report_id = report.id
            print(f"✅ 그룹 보고서 저장 완료: ID={report_id}")

        # 6. 메타데이터
        metadata = {
            'group_id': group_id,
            'group_name': group.name,
            'prompt_count': len(prompts),
            'categories': list(set(p.category for p in prompts)),
            'systems': list(set(p.system for p in prompts if p.system)),
            'generation_time': datetime.now().isoformat()
        }

        print(f"\n{'='*80}")
        print(f"✨ 그룹 보고서 생성 완료")
        print(f"{'='*80}\n")

        return {
            'report_id': report_id,
            'html': html,
            'metadata': metadata
        }

    def _get_group_prompts_by_ids(self, group_id: int, prompt_ids: List[int]) -> List[PromptTemplate]:
        """
        그룹의 프롬프트들을 ID로 조회

        Args:
            group_id: 그룹 ID
            prompt_ids: 프롬프트 ID 리스트

        Returns:
            프롬프트 리스트 (카테고리 > order_index > system 순 정렬)

        Raises:
            ValueError: 일부 프롬프트가 해당 그룹에 속하지 않음
        """
        prompts = self.db.query(PromptTemplate)\
            .filter(
                PromptTemplate.id.in_(prompt_ids),
                PromptTemplate.group_id == group_id
            )\
            .order_by(
                PromptTemplate.category,
                PromptTemplate.order_index,
                PromptTemplate.system
            )\
            .all()

        # 권한 체크
        if len(prompts) != len(prompt_ids):
            found_ids = set(p.id for p in prompts)
            missing_ids = set(prompt_ids) - found_ids
            raise ValueError(f"일부 프롬프트가 해당 그룹에 속하지 않습니다: {missing_ids}")

        return prompts

    def _build_hierarchical_html(
        self,
        prompts: List[PromptTemplate],
        title: str,
        group_name: str,
        include_toc: bool
    ) -> str:
        """
        계층적 HTML 구성 (카테고리 > 시스템)

        Args:
            prompts: 프롬프트 리스트
            title: 보고서 제목
            group_name: 그룹 이름
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
        .report-subtitle {{
            color: #7f8c8d;
            font-size: 1.2em;
            margin-bottom: 5px;
        }}
        .report-date {{
            color: #95a5a6;
            font-size: 1em;
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
        .toc li.subsection {{
            margin-left: 20px;
            font-size: 0.95em;
        }}
        .toc a {{
            color: #3498db;
            text-decoration: none;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
        .report-section {{
            margin-bottom: 50px;
        }}
        .report-section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        .report-subsection {{
            margin-bottom: 35px;
            padding-left: 20px;
        }}
        .report-subsection h3 {{
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-bottom: 20px;
        }}
        .component {{
            margin: 20px 0;
            padding: 15px;
            background-color: #fafafa;
            border-radius: 5px;
        }}
        .component h4 {{
            color: #2c3e50;
            margin-top: 0;
            margin-bottom: 10px;
        }}
        .component-description {{
            color: #7f8c8d;
            font-style: italic;
            margin-bottom: 15px;
            font-size: 0.95em;
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
        .component-error {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }}
        .error-message {{
            color: #856404;
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
            <p class="report-subtitle">{group_name}</p>
            <p class="report-date">{datetime.now().strftime('%Y년 %m월 %d일')}</p>
        </div>
'''

        # 목차
        if include_toc:
            html += self._generate_hierarchical_toc(prompts)

        # 카테고리별 > 시스템별 그룹핑
        grouped = self._group_by_category_and_system(prompts)

        # 각 카테고리 섹션
        for i, (category, systems_dict) in enumerate(grouped.items(), 1):
            html += f'\n<section id="section-{i}" class="report-section">\n'
            html += f'<h2>{i}. {category}</h2>\n'

            # 시스템별 하위 섹션
            for j, (system, system_prompts) in enumerate(systems_dict.items(), 1):
                subsection_id = f"section-{i}-{j}"
                system_label = system if system else "기타"

                html += f'\n<div id="{subsection_id}" class="report-subsection">\n'
                html += f'<h3>{i}.{j} {system_label}</h3>\n'

                # 각 프롬프트 컴포넌트
                for prompt in system_prompts:
                    html += self._generate_component(prompt)

                html += '</div>\n'

            html += '</section>\n'

        # HTML 종료
        html += '''
    </div>
</body>
</html>
'''

        return html

    def _generate_hierarchical_toc(self, prompts: List[PromptTemplate]) -> str:
        """계층적 목차 생성 (카테고리 > 시스템)"""
        grouped = self._group_by_category_and_system(prompts)

        toc_html = '\n<div class="toc">\n'
        toc_html += '<h2>📋 목차</h2>\n'
        toc_html += '<ul>\n'

        for i, (category, systems_dict) in enumerate(grouped.items(), 1):
            toc_html += f'<li><a href="#section-{i}"><strong>{i}. {category}</strong></a></li>\n'

            # 하위 시스템
            for j, (system, _) in enumerate(systems_dict.items(), 1):
                system_label = system if system else "기타"
                toc_html += f'<li class="subsection"><a href="#section-{i}-{j}">{i}.{j} {system_label}</a></li>\n'

        toc_html += '</ul>\n'
        toc_html += '</div>\n'

        return toc_html

    def _group_by_category_and_system(
        self,
        prompts: List[PromptTemplate]
    ) -> Dict[str, Dict[Optional[str], List[PromptTemplate]]]:
        """
        카테고리별 > 시스템별 2단계 그룹핑

        Returns:
            {
                "운영지원": {
                    "NCMS": [prompt1, prompt2],
                    "EUXP": [prompt3]
                },
                "BMT": {
                    "EDMP": [prompt4]
                }
            }
        """
        grouped = defaultdict(lambda: defaultdict(list))

        for prompt in prompts:
            category = prompt.category or '기타'
            system = prompt.system  # None일 수 있음
            grouped[category][system].append(prompt)

        # defaultdict를 일반 dict로 변환
        return {cat: dict(systems) for cat, systems in grouped.items()}

    def _generate_component(self, prompt: PromptTemplate) -> str:
        """
        개별 컴포넌트 생성 (Agent 실행)

        Args:
            prompt: 프롬프트 템플릿

        Returns:
            컴포넌트 HTML
        """
        print(f"\n{'─'*80}")
        print(f"📦 컴포넌트 생성: {prompt.title} (System: {prompt.system or 'N/A'})")
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

            # Markdown 테이블을 HTML로 변환
            html_content = self._markdown_to_html(content)

            component_html = f'''
<div class="component" id="prompt-{prompt.id}">
    <h4>{prompt.title}</h4>
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
            return f'<div class="content">{markdown}</div>'

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
    <h4>{title}</h4>
    <div class="error-message">
        <strong>⚠️ 컴포넌트 생성 실패</strong>
        <p>{error_msg}</p>
    </div>
</div>
'''

    def get_group_reports(self, group_id: int, user_id: int) -> List[Dict]:
        """
        그룹의 보고서 목록 (멤버만 조회 가능)

        Args:
            group_id: 그룹 ID
            user_id: 요청 사용자 ID

        Returns:
            보고서 목록

        Raises:
            PermissionError: 그룹 멤버가 아님
        """
        # 권한 체크
        if not self.group_service.is_group_member(group_id, user_id):
            raise PermissionError("이 그룹의 멤버가 아닙니다")

        reports = self.db.query(Report)\
            .filter_by(group_id=group_id, report_type='group')\
            .order_by(Report.created_at.desc())\
            .all()

        return [r.to_dict() for r in reports]

    def get_group_report_by_id(self, group_id: int, report_id: int, user_id: int) -> Dict:
        """
        그룹 보고서 조회 (HTML 포함)

        Args:
            group_id: 그룹 ID
            report_id: 보고서 ID
            user_id: 요청 사용자 ID

        Returns:
            보고서 정보 (HTML 포함)

        Raises:
            PermissionError: 그룹 멤버가 아님
            ValueError: 보고서 없음
        """
        # 권한 체크
        if not self.group_service.is_group_member(group_id, user_id):
            raise PermissionError("이 그룹의 멤버가 아닙니다")

        report = self.db.query(Report)\
            .filter_by(id=report_id, group_id=group_id, report_type='group')\
            .first()

        if not report:
            raise ValueError("보고서를 찾을 수 없습니다")

        return report.to_dict(include_html=True)


if __name__ == "__main__":
    print("Group Report Service 모듈")
    print("실제 테스트는 Agent 및 DB 인스턴스가 필요합니다.")
