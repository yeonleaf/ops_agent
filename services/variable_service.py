#!/usr/bin/env python3
"""
Variable Service - 변수 치환 서비스
"""

import re
from typing import Dict, List, Tuple
import logging

from models.report_models import DatabaseManager, Variable
import os

logger = logging.getLogger(__name__)


class UndefinedVariableError(Exception):
    """정의되지 않은 변수 에러"""

    def __init__(self, variable_names: List[str]):
        self.variable_names = variable_names
        variables_str = "', '".join(variable_names)
        super().__init__(f"정의되지 않은 변수: '{variables_str}'")


class VariableService:
    """변수 관리 및 치환 서비스"""

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: 데이터베이스 경로 (None이면 환경변수 사용)
        """
        if db_path is None:
            db_path = os.getenv('REPORTS_DB_PATH', 'reports.db')

        self.db_manager = DatabaseManager(db_path)

    def substitute_variables(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        텍스트에서 {{변수명}} 패턴을 실제 값으로 치환

        Args:
            text: 치환할 텍스트

        Returns:
            (치환된 텍스트, 치환 매핑 딕셔너리)

        Raises:
            UndefinedVariableError: 정의되지 않은 변수가 있을 경우
        """
        # {{변수명}} 패턴 찾기
        pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
        matches = re.findall(pattern, text)

        if not matches:
            # 변수가 없으면 원본 텍스트 그대로 반환
            return text, {}

        # 중복 제거
        variable_names = list(set(matches))

        # 데이터베이스에서 변수 값 조회
        session = self.db_manager.get_session()

        try:
            variables_map = {}
            undefined_variables = []

            for var_name in variable_names:
                variable = session.query(Variable).filter_by(name=var_name).first()

                if variable:
                    variables_map[var_name] = variable.value
                else:
                    undefined_variables.append(var_name)

            # 정의되지 않은 변수가 있으면 에러
            if undefined_variables:
                raise UndefinedVariableError(undefined_variables)

            # 텍스트 치환
            result = text
            for var_name, var_value in variables_map.items():
                result = result.replace(f"{{{{{var_name}}}}}", var_value)

            logger.info(f"✅ 변수 치환 완료: {len(variables_map)}개 변수")
            logger.debug(f"   치환 매핑: {variables_map}")

            return result, variables_map

        finally:
            session.close()

    def extract_variables(self, text: str) -> List[str]:
        """
        텍스트에서 사용된 변수명 추출

        Args:
            text: 분석할 텍스트

        Returns:
            변수명 리스트
        """
        pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
        matches = re.findall(pattern, text)
        return list(set(matches))

    def validate_variables(self, text: str) -> Tuple[bool, List[str]]:
        """
        텍스트에 사용된 모든 변수가 정의되어 있는지 확인

        Args:
            text: 검증할 텍스트

        Returns:
            (모두 유효 여부, 정의되지 않은 변수명 리스트)
        """
        variable_names = self.extract_variables(text)

        if not variable_names:
            return True, []

        session = self.db_manager.get_session()

        try:
            undefined_variables = []

            for var_name in variable_names:
                variable = session.query(Variable).filter_by(name=var_name).first()
                if not variable:
                    undefined_variables.append(var_name)

            is_valid = len(undefined_variables) == 0
            return is_valid, undefined_variables

        finally:
            session.close()

    def get_all_variables(self) -> Dict[str, str]:
        """
        모든 변수를 딕셔너리로 반환

        Returns:
            {변수명: 값} 딕셔너리
        """
        session = self.db_manager.get_session()

        try:
            variables = session.query(Variable).all()
            return {var.name: var.value for var in variables}

        finally:
            session.close()


# 싱글톤 인스턴스 (편의를 위해)
_variable_service_instance = None


def get_variable_service() -> VariableService:
    """VariableService 싱글톤 인스턴스 반환"""
    global _variable_service_instance

    if _variable_service_instance is None:
        _variable_service_instance = VariableService()

    return _variable_service_instance


if __name__ == "__main__":
    # 테스트
    print("=" * 60)
    print("Variable Service 테스트")
    print("=" * 60)

    service = VariableService()

    # 테스트 텍스트
    test_text = "project = {{projectKey}} AND fixVersion = {{fixVersion}}"
    print(f"\n원본: {test_text}")

    try:
        result, mapping = service.substitute_variables(test_text)
        print(f"치환: {result}")
        print(f"매핑: {mapping}")
    except UndefinedVariableError as e:
        print(f"에러: {e}")

    # 변수 추출 테스트
    variables = service.extract_variables(test_text)
    print(f"\n사용된 변수: {variables}")

    # 변수 검증 테스트
    is_valid, undefined = service.validate_variables(test_text)
    print(f"\n유효성: {is_valid}")
    if not is_valid:
        print(f"정의되지 않은 변수: {undefined}")

    print("\n" + "=" * 60)
