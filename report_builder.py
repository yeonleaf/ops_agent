#!/usr/bin/env python3
"""
Report Builder - 통합 보고서 생성

ComponentGenerator를 사용하여 구조에 따라 전체 보고서를 빌드합니다.
"""

from typing import Dict, List, Any
from component_generator import ComponentGenerator


class ReportBuilder:
    """
    보고서 구조를 순회하며 통합 HTML 보고서 생성
    """

    def __init__(self, component_generator: ComponentGenerator):
        """
        Args:
            component_generator: ComponentGenerator 인스턴스
        """
        self.generator = component_generator

    def build(self, structure: Dict[str, Any]) -> str:
        """
        구조에 따라 통합 보고서 생성

        Args:
            structure: 보고서 구조 딕셔너리 (report_structure.get_report_structure() 결과)

        Returns:
            완전한 HTML 문서 (<!DOCTYPE html>부터 </html>까지)
        """
        print(f"\n{'='*80}")
        print(f"📊 통합 보고서 빌드 시작")
        print(f"{'='*80}\n")

        title = structure.get("title", "월간보고")
        date = structure.get("date", "")
        sections = structure.get("sections", [])

        # HTML 문서 시작
        html = self._header(title, date)

        # 목차 생성
        html += self._toc(sections)

        # 섹션별 컨텐츠 생성
        for section in sections:
            html += self._build_section(section)

        # HTML 문서 종료
        html += self._footer()

        print(f"\n{'='*80}")
        print(f"✨ 통합 보고서 빌드 완료")
        print(f"{'='*80}\n")

        return html

    def _build_section(self, section: Dict[str, Any]) -> str:
        """
        섹션 HTML 생성

        Args:
            section: 섹션 딕셔너리

        Returns:
            섹션 HTML
        """
        section_id = section.get("id", "")
        title = section.get("title", "")

        print(f"\n{'─'*80}")
        print(f"📁 섹션: {title}")
        print(f"{'─'*80}")

        html = f'\n<section class="report-section" id="{section_id}">\n'
        html += f'  <h2>{title}</h2>\n'

        # 직접 컴포넌트가 있는 경우
        if "components" in section:
            for component in section["components"]:
                html += self._build_component(component)

        # 하위 섹션이 있는 경우
        if "subsections" in section:
            for subsection in section["subsections"]:
                html += self._build_subsection(subsection)

        html += '</section>\n'

        return html

    def _build_subsection(self, subsection: Dict[str, Any]) -> str:
        """
        하위 섹션 HTML 생성

        Args:
            subsection: 하위 섹션 딕셔너리

        Returns:
            하위 섹션 HTML
        """
        subsection_id = subsection.get("id", "")
        title = subsection.get("title", "")

        print(f"\n  📂 하위 섹션: {title}")

        html = f'\n  <div class="report-subsection" id="{subsection_id}">\n'
        html += f'    <h3>{title}</h3>\n'

        # 컴포넌트 생성
        if "components" in subsection:
            for component in subsection["components"]:
                html += self._build_component(component, indent=4)

        html += '  </div>\n'

        return html

    def _build_component(self, component: Dict[str, Any], indent: int = 2) -> str:
        """
        개별 컴포넌트 생성

        Args:
            component: 컴포넌트 딕셔너리
            indent: 들여쓰기 레벨

        Returns:
            컴포넌트 HTML
        """
        name = component.get("name", "")
        prompt_file = component.get("prompt_file", "")
        description = component.get("description", "")

        print(f"    📦 컴포넌트: {name} ({prompt_file})")

        # ComponentGenerator로 컴포넌트 생성
        try:
            component_html = self.generator.generate(prompt_file, name)

            # 들여쓰기 적용
            indented = self._indent_html(component_html, indent)

            return indented

        except Exception as e:
            print(f"    ❌ 컴포넌트 생성 실패: {str(e)}")
            error_html = f'''
<div class="component component-error">
    <div class="error-message">
        <strong>⚠️ 컴포넌트 생성 실패: {name}</strong>
        <p>{str(e)}</p>
    </div>
</div>
'''
            return self._indent_html(error_html, indent)

    def _header(self, title: str, date: str) -> str:
        """
        HTML 문서 헤더 생성

        Args:
            title: 보고서 제목
            date: 보고서 날짜

        Returns:
            HTML 헤더
        """
        return f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="/static/report.css">
    <style>
        /* Embedded styles for standalone HTML */
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
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
        .report-header .date {{
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
        .report-subsection {{
            margin-left: 20px;
            margin-bottom: 30px;
        }}
        .report-subsection h3 {{
            color: #34495e;
            border-left: 4px solid #4CAF50;
            padding-left: 15px;
            margin-bottom: 15px;
        }}
        .component {{
            margin: 20px 0;
        }}
        .component-error {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
        }}
        .error-message {{
            color: #856404;
        }}
        .report-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .report-table th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        .report-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        .report-table tr:hover {{
            background-color: #f5f5f5;
        }}
        .report-table tr:last-child td {{
            border-bottom: none;
        }}
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .report-container {{
                box-shadow: none;
                padding: 20px;
            }}
            .report-section {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>{title}</h1>
            <div class="date">보고 기간: {date}</div>
        </div>
'''

    def _toc(self, sections: List[Dict[str, Any]]) -> str:
        """
        목차 생성

        Args:
            sections: 섹션 리스트

        Returns:
            목차 HTML
        """
        html = '\n        <div class="toc">\n'
        html += '            <h2>목차</h2>\n'
        html += '            <ul>\n'

        for section in sections:
            section_id = section.get("id", "")
            title = section.get("title", "")
            html += f'                <li><a href="#{section_id}">{title}</a></li>\n'

            # 하위 섹션 목차
            if "subsections" in section:
                html += '                <ul>\n'
                for subsection in section["subsections"]:
                    subsection_id = subsection.get("id", "")
                    subsection_title = subsection.get("title", "")
                    html += f'                    <li><a href="#{subsection_id}">{subsection_title}</a></li>\n'
                html += '                </ul>\n'

        html += '            </ul>\n'
        html += '        </div>\n'

        return html

    def _footer(self) -> str:
        """
        HTML 문서 푸터 생성

        Returns:
            HTML 푸터
        """
        return '''
    </div>
</body>
</html>
'''

    def _indent_html(self, html: str, spaces: int) -> str:
        """
        HTML 문자열에 들여쓰기 적용

        Args:
            html: HTML 문자열
            spaces: 공백 개수

        Returns:
            들여쓰기가 적용된 HTML
        """
        indent = ' ' * spaces
        lines = html.split('\n')
        indented_lines = [indent + line if line.strip() else line for line in lines]
        return '\n'.join(indented_lines)


if __name__ == "__main__":
    # 테스트 코드
    print("ReportBuilder 테스트")
    print("실제 테스트는 ComponentGenerator 인스턴스가 필요합니다.")
