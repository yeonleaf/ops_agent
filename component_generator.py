#!/usr/bin/env python3
"""
Component Generator - 개별 보고서 컴포넌트 생성

MonthlyReportAgent를 활용하여 프롬프트 파일을 실행하고
결과를 HTML 컴포넌트로 래핑합니다.
"""

import os
from typing import Optional
from pathlib import Path
from agent.monthly_report_agent import MonthlyReportAgent


class ComponentGenerator:
    """
    프롬프트 파일을 읽어서 Agent로 실행하고
    결과를 HTML 컴포넌트로 변환
    """

    def __init__(self, agent: MonthlyReportAgent, prompts_dir: str = "prompts/"):
        """
        Args:
            agent: MonthlyReportAgent 인스턴스
            prompts_dir: 프롬프트 파일이 있는 디렉토리
        """
        self.agent = agent
        self.prompts_dir = Path(prompts_dir)

        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {prompts_dir}")

    def generate(self, prompt_file: str, component_name: str = None) -> str:
        """
        프롬프트 파일을 읽어서 Agent로 실행하고
        결과를 HTML 컴포넌트로 래핑하여 반환

        Args:
            prompt_file: 프롬프트 파일명 (예: "ncms_bmt.txt")
            component_name: 컴포넌트 이름 (예: "ncms_bmt")

        Returns:
            HTML string (div.component로 래핑된 컨텐츠)

        Raises:
            FileNotFoundError: 프롬프트 파일이 없는 경우
            Exception: Agent 실행 실패
        """
        print(f"\n{'='*80}")
        print(f"📦 컴포넌트 생성 시작: {prompt_file}")
        print(f"{'='*80}\n")

        # 1. 프롬프트 파일 읽기
        prompt_path = self.prompts_dir / prompt_file

        if not prompt_path.exists():
            error_msg = f"프롬프트 파일을 찾을 수 없습니다: {prompt_path}"
            print(f"❌ {error_msg}")
            return self._wrap_error(error_msg, component_name)

        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                user_prompt = f.read().strip()

            if not user_prompt:
                error_msg = f"프롬프트 파일이 비어있습니다: {prompt_file}"
                print(f"❌ {error_msg}")
                return self._wrap_error(error_msg, component_name)

            print(f"✅ 프롬프트 로드 완료 ({len(user_prompt)} 글자)")

        except Exception as e:
            error_msg = f"프롬프트 파일 읽기 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return self._wrap_error(error_msg, component_name)

        # 2. Agent 실행
        try:
            print(f"🤖 Agent 실행 중...\n")

            # Agent에게 페이지 생성 요청
            result = self.agent.generate_page(
                page_title=component_name or prompt_file.replace('.txt', ''),
                user_prompt=user_prompt,
                context=None,
                max_iterations=10,
                temperature=0.3
            )

            # 3. 결과 처리
            if not result.get("success"):
                error_msg = result.get("error", "알 수 없는 오류")
                print(f"❌ Agent 실행 실패: {error_msg}")
                return self._wrap_error(error_msg, component_name)

            content = result.get("content", "")

            if not content:
                error_msg = "Agent가 빈 결과를 반환했습니다"
                print(f"⚠️  {error_msg}")
                return self._wrap_error(error_msg, component_name)

            print(f"✅ Agent 실행 완료")
            print(f"   - 소요 시간: {result.get('elapsed_time', 0):.2f}초")
            print(f"   - Function Calls: {len(result.get('execution_history', []))}회")
            print(f"   - 컨텐츠 길이: {len(content)} 글자\n")

            # 4. HTML 컴포넌트로 래핑
            html_component = self._wrap_component(content, component_name)

            return html_component

        except Exception as e:
            error_msg = f"Agent 실행 중 오류 발생: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return self._wrap_error(error_msg, component_name)

    def _wrap_component(self, content: str, component_name: str = None) -> str:
        """
        컨텐츠를 HTML 컴포넌트로 래핑

        Args:
            content: Agent가 생성한 컨텐츠 (마크다운 또는 HTML)
            component_name: 컴포넌트 이름

        Returns:
            HTML 문자열
        """
        # Markdown 테이블을 HTML로 변환 (간단한 변환)
        html_content = self._markdown_table_to_html(content)

        component_id = f"component-{component_name}" if component_name else "component"

        return f'''
<div class="component" id="{component_id}">
    {html_content}
</div>
'''

    def _markdown_table_to_html(self, markdown: str) -> str:
        """
        Markdown 테이블을 HTML 테이블로 변환

        Args:
            markdown: Markdown 형식의 테이블

        Returns:
            HTML 테이블
        """
        # 이미 HTML 테이블이면 그대로 반환
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
                # 구분선(---|---|---) 제거
                if not all(c in '-:|' for c in stripped.replace(' ', '')):
                    table_lines.append(stripped)
            elif in_table and not stripped:
                # 테이블 끝
                break

        if not table_lines:
            # 테이블이 없으면 그냥 <pre> 태그로 감싸서 반환
            return f'<pre>{markdown}</pre>'

        # HTML 테이블 생성
        html = '<table class="report-table">\n'

        # 첫 줄은 헤더
        if table_lines:
            header = table_lines[0]
            cols = [col.strip() for col in header.split('|') if col.strip()]
            html += '  <thead>\n    <tr>\n'
            for col in cols:
                html += f'      <th>{col}</th>\n'
            html += '    </tr>\n  </thead>\n'

        # 나머지는 데이터
        if len(table_lines) > 1:
            html += '  <tbody>\n'
            for row in table_lines[1:]:
                cols = [col.strip() for col in row.split('|') if col.strip()]
                html += '    <tr>\n'
                for col in cols:
                    html += f'      <td>{col}</td>\n'
                html += '    </tr>\n'
            html += '  </tbody>\n'

        html += '</table>\n'

        return html

    def _wrap_error(self, error_message: str, component_name: str = None) -> str:
        """
        에러 메시지를 HTML 컴포넌트로 래핑

        Args:
            error_message: 에러 메시지
            component_name: 컴포넌트 이름

        Returns:
            HTML 문자열
        """
        component_id = f"component-{component_name}" if component_name else "component"

        return f'''
<div class="component component-error" id="{component_id}">
    <div class="error-message">
        <strong>⚠️ 컴포넌트 생성 실패</strong>
        <p>{error_message}</p>
    </div>
</div>
'''


if __name__ == "__main__":
    # 테스트 코드
    print("ComponentGenerator 테스트")
    print("실제 테스트는 Agent 인스턴스가 필요합니다.")
