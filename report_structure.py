#!/usr/bin/env python3
"""
Report Structure - 월간보고서 구조 정의

보고서의 섹션, 하위 섹션, 컴포넌트 계층 구조를 정의합니다.
"""

from typing import Dict, List, Any
from datetime import datetime


def get_report_structure(year: int = None, month: int = None) -> Dict[str, Any]:
    """
    월간보고서 구조 반환

    Args:
        year: 연도 (기본값: 현재 연도)
        month: 월 (기본값: 현재 월)

    Returns:
        보고서 구조 딕셔너리
    """
    if year is None or month is None:
        now = datetime.now()
        year = now.year if year is None else year
        month = now.month if month is None else month

    # 날짜 포맷팅
    date_str = f"{year}-{month:02d}-01"
    title_date = f"{year}.{month:02d}"

    return {
        "title": f"월간보고 ({title_date})",
        "date": date_str,
        "sections": [
            {
                "id": "overview",
                "title": "1. 전체 운영 업무 현황",
                "components": [
                    {
                        "name": "operation_status",
                        "prompt_file": "operation_status.txt",
                        "description": "프로젝트별 진행 중인 이슈 현황"
                    }
                ]
            },
            {
                "id": "bmt",
                "title": "2. BMT 현황",
                "subsections": [
                    {
                        "id": "bmt_ncms",
                        "title": "2.1 NCMS BMT",
                        "components": [
                            {
                                "name": "ncms_bmt",
                                "prompt_file": "ncms_bmt.txt",
                                "description": "NCMS BMT 이슈 목록 및 현황"
                            }
                        ]
                    },
                    {
                        "id": "bmt_edmp",
                        "title": "2.2 EDMP BMT",
                        "components": [
                            {
                                "name": "edmp_bmt",
                                "prompt_file": "edmp_bmt.txt",
                                "description": "EDMP BMT 이슈 목록 및 현황"
                            }
                        ]
                    }
                ]
            },
            {
                "id": "pm",
                "title": "3. PM 현황",
                "subsections": [
                    {
                        "id": "pm_ncms",
                        "title": "3.1 NCMS PM",
                        "components": [
                            {
                                "name": "ncms_pm",
                                "prompt_file": "ncms_pm.txt",
                                "description": "NCMS PM 이슈 목록 및 현황"
                            }
                        ]
                    },
                    {
                        "id": "pm_acs",
                        "title": "3.2 ACS PM",
                        "components": [
                            {
                                "name": "acs_pm",
                                "prompt_file": "acs_pm.txt",
                                "description": "ACS PM 이슈 목록 및 현황"
                            }
                        ]
                    }
                ]
            },
            {
                "id": "db_work",
                "title": "4. 상용 DB작업",
                "subsections": [
                    {
                        "id": "db_ncms",
                        "title": "4.1 NCMS DB작업",
                        "components": [
                            {
                                "name": "ncms_db",
                                "prompt_file": "ncms_db.txt",
                                "description": "NCMS 상용 DB작업 현황"
                            }
                        ]
                    },
                    {
                        "id": "db_euxp",
                        "title": "4.2 EUXP DB작업",
                        "components": [
                            {
                                "name": "euxp_db",
                                "prompt_file": "euxp_db.txt",
                                "description": "EUXP 상용 DB작업 현황"
                            }
                        ]
                    },
                    {
                        "id": "db_acs",
                        "title": "4.3 ACS DB작업",
                        "components": [
                            {
                                "name": "acs_db",
                                "prompt_file": "acs_db.txt",
                                "description": "ACS 상용 DB작업 현황"
                            }
                        ]
                    }
                ]
            }
        ]
    }


# 모든 컴포넌트 목록 추출 함수
def get_all_components(structure: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    구조에서 모든 컴포넌트 목록 추출

    Args:
        structure: 보고서 구조 딕셔너리

    Returns:
        모든 컴포넌트 리스트
    """
    components = []

    for section in structure.get("sections", []):
        # 직접 컴포넌트가 있는 경우
        if "components" in section:
            components.extend(section["components"])

        # 하위 섹션이 있는 경우
        if "subsections" in section:
            for subsection in section["subsections"]:
                if "components" in subsection:
                    components.extend(subsection["components"])

    return components


# 컴포넌트 이름 목록 추출
def get_component_names(structure: Dict[str, Any]) -> List[str]:
    """
    구조에서 모든 컴포넌트 이름 추출

    Args:
        structure: 보고서 구조 딕셔너리

    Returns:
        컴포넌트 이름 리스트
    """
    components = get_all_components(structure)
    return [comp["name"] for comp in components]


if __name__ == "__main__":
    # 테스트
    import json

    structure = get_report_structure(2025, 9)
    print("=== 보고서 구조 ===")
    print(json.dumps(structure, ensure_ascii=False, indent=2))

    print("\n=== 모든 컴포넌트 이름 ===")
    names = get_component_names(structure)
    for name in names:
        print(f"  - {name}")
