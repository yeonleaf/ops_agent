#!/usr/bin/env python3
"""
Template Parser - 보고서 템플릿 placeholder 처리

Markdown 템플릿에서 {{prompt:id}} 형식의 placeholder를 찾아서
해당 프롬프트의 실행 결과(HTML fragment)로 치환합니다.
"""

import re
from typing import Dict, List, Optional
from models.report_models import PromptExecution, PromptTemplate


class TemplatePlaceholderParser:
    """템플릿 placeholder 파서"""

    def __init__(self, db_session):
        """
        Args:
            db_session: SQLAlchemy 세션
        """
        self.db = db_session

    def parse_template(
        self,
        template_content: str,
        execution_cache: Optional[Dict[int, str]] = None
    ) -> Dict:
        """
        템플릿을 파싱하여 placeholder를 실행 결과로 치환

        Args:
            template_content: 템플릿 내용 (Markdown + {{prompt:id}})
            execution_cache: {prompt_id: html_fragment} 딕셔너리 (선택사항)

        Returns:
            {
                "html": str,  # 최종 HTML
                "placeholders": [{"prompt_id": int, "found": bool}],
                "missing_executions": [int]  # 실행 결과가 없는 prompt_id 목록
            }
        """
        # Placeholder 패턴: {{prompt:123}} or {{prompt:prompt_id}}
        placeholder_pattern = r'\{\{prompt:(\d+)\}\}'

        # 모든 placeholder 찾기
        placeholders = re.findall(placeholder_pattern, template_content)
        placeholder_info = []
        missing_executions = []

        result_html = template_content

        for prompt_id_str in placeholders:
            prompt_id = int(prompt_id_str)

            # execution_cache에서 찾기 (우선순위 1)
            if execution_cache and prompt_id in execution_cache:
                html_fragment = execution_cache[prompt_id]
                placeholder_info.append({"prompt_id": prompt_id, "found": True, "source": "cache"})
            else:
                # DB에서 최신 실행 결과 찾기 (우선순위 2)
                html_fragment = self._get_latest_html_output(prompt_id)
                if html_fragment:
                    placeholder_info.append({"prompt_id": prompt_id, "found": True, "source": "db"})
                else:
                    # 실행 결과 없음
                    placeholder_info.append({"prompt_id": prompt_id, "found": False})
                    missing_executions.append(prompt_id)
                    html_fragment = self._generate_missing_placeholder_html(prompt_id)

            # Placeholder 치환
            result_html = result_html.replace(f"{{{{prompt:{prompt_id}}}}}", html_fragment)

        return {
            "html": result_html,
            "placeholders": placeholder_info,
            "missing_executions": missing_executions
        }

    def _get_latest_html_output(self, prompt_id: int) -> Optional[str]:
        """
        해당 프롬프트의 최신 실행 결과 HTML을 가져옴

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            HTML fragment 또는 None
        """
        execution = self.db.query(PromptExecution)\
            .filter_by(prompt_id=prompt_id)\
            .order_by(PromptExecution.executed_at.desc())\
            .first()

        if execution and execution.html_output:
            return execution.html_output

        return None

    def _generate_missing_placeholder_html(self, prompt_id: int) -> str:
        """
        실행 결과가 없는 프롬프트에 대한 placeholder HTML 생성

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            경고 메시지 HTML
        """
        # 프롬프트 정보 가져오기
        prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()

        if not prompt:
            return f'''
<div class="missing-prompt-warning">
    <strong>⚠️ 프롬프트를 찾을 수 없습니다</strong>
    <p>프롬프트 ID: {prompt_id}</p>
</div>
'''

        return f'''
<div class="missing-execution-warning">
    <strong>⚠️ 실행 결과 없음</strong>
    <p>프롬프트: <em>{prompt.title}</em> (ID: {prompt_id})</p>
    <p>이 프롬프트를 먼저 실행해주세요.</p>
</div>
'''

    def extract_prompt_ids(self, template_content: str) -> List[int]:
        """
        템플릿에서 사용된 모든 프롬프트 ID 추출

        Args:
            template_content: 템플릿 내용

        Returns:
            프롬프트 ID 리스트
        """
        placeholder_pattern = r'\{\{prompt:(\d+)\}\}'
        matches = re.findall(placeholder_pattern, template_content)
        return [int(m) for m in matches]

    def validate_template(self, template_content: str, user_id: int) -> Dict:
        """
        템플릿 유효성 검사

        Args:
            template_content: 템플릿 내용
            user_id: 사용자 ID

        Returns:
            {
                "valid": bool,
                "errors": [str],
                "warnings": [str],
                "prompt_ids": [int]
            }
        """
        errors = []
        warnings = []

        # 프롬프트 ID 추출
        prompt_ids = self.extract_prompt_ids(template_content)

        if not prompt_ids:
            warnings.append("템플릿에 프롬프트 placeholder가 없습니다")

        # 각 프롬프트의 존재 및 권한 확인
        for prompt_id in prompt_ids:
            prompt = self.db.query(PromptTemplate).filter_by(id=prompt_id).first()

            if not prompt:
                errors.append(f"프롬프트 ID {prompt_id}를 찾을 수 없습니다")
            elif prompt.user_id != user_id and not prompt.is_public:
                errors.append(f"프롬프트 ID {prompt_id}에 접근 권한이 없습니다")
            else:
                # 실행 결과 확인
                has_execution = self.db.query(PromptExecution)\
                    .filter_by(prompt_id=prompt_id)\
                    .first() is not None

                if not has_execution:
                    warnings.append(f"프롬프트 '{prompt.title}' (ID: {prompt_id})의 실행 결과가 없습니다")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "prompt_ids": prompt_ids
        }


if __name__ == "__main__":
    # 테스트
    from models.report_models import DatabaseManager

    print("=== Template Parser 테스트 ===\n")

    # DB 초기화
    db = DatabaseManager('test_templates.db')
    db.create_tables()
    session = db.get_session()

    try:
        parser = TemplatePlaceholderParser(session)

        # 테스트 템플릿
        template = """
# 2024년 11월 월간 보고서

## 주간 요약
{{prompt:1}}

## 주요 성과
{{prompt:2}}

## 다음 달 계획
{{prompt:3}}
"""

        print("1. Placeholder 추출 테스트")
        prompt_ids = parser.extract_prompt_ids(template)
        print(f"   발견된 프롬프트 ID: {prompt_ids}")

        print("\n2. 템플릿 파싱 테스트")
        result = parser.parse_template(template)
        print(f"   Placeholder 정보: {result['placeholders']}")
        print(f"   누락된 실행 결과: {result['missing_executions']}")

    finally:
        session.close()
        print("\n✅ 테스트 완료")
