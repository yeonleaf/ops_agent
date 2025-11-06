#!/usr/bin/env python3
"""
Report Utils - 보고서 생성 유틸리티 함수

구조 필터링, 검증 등의 유틸리티 함수를 제공합니다.
"""

from typing import Dict, List, Any
import copy


def filter_structure(
    structure: Dict[str, Any],
    selected_components: List[str]
) -> Dict[str, Any]:
    """
    선택된 컴포넌트만 포함하도록 구조 필터링

    Args:
        structure: 전체 보고서 구조 (report_structure.get_report_structure() 결과)
        selected_components: 선택된 컴포넌트 name 리스트
                            예: ["operation_status", "ncms_bmt", "acs_db"]

    Returns:
        필터링된 구조 (선택 안 된 컴포넌트 제외)

    Examples:
        >>> structure = get_report_structure(2025, 9)
        >>> selected = ["operation_status", "ncms_bmt"]
        >>> filtered = filter_structure(structure, selected)
    """
    if not selected_components:
        raise ValueError("선택된 컴포넌트가 없습니다. 최소 1개 이상 선택해주세요.")

    # 구조를 복사하여 원본 보존
    filtered = copy.deepcopy(structure)

    # 선택된 컴포넌트 set으로 변환 (빠른 조회)
    selected_set = set(selected_components)

    # 필터링된 섹션 리스트
    filtered_sections = []

    for section in filtered.get("sections", []):
        filtered_section = _filter_section(section, selected_set)

        # 컴포넌트가 남아있는 섹션만 포함
        if filtered_section:
            filtered_sections.append(filtered_section)

    filtered["sections"] = filtered_sections

    return filtered


def _filter_section(
    section: Dict[str, Any],
    selected_set: set
) -> Dict[str, Any] or None:
    """
    섹션 필터링 (내부 함수)

    Args:
        section: 섹션 딕셔너리
        selected_set: 선택된 컴포넌트 이름 set

    Returns:
        필터링된 섹션 (컴포넌트가 없으면 None)
    """
    filtered_section = copy.deepcopy(section)

    # 직접 컴포넌트가 있는 경우
    if "components" in section:
        filtered_components = [
            comp for comp in section["components"]
            if comp.get("name") in selected_set
        ]

        if filtered_components:
            filtered_section["components"] = filtered_components
            return filtered_section
        else:
            # 직접 컴포넌트가 없으면 하위 섹션 확인
            del filtered_section["components"]

    # 하위 섹션이 있는 경우
    if "subsections" in section:
        filtered_subsections = []

        for subsection in section["subsections"]:
            if "components" in subsection:
                filtered_components = [
                    comp for comp in subsection["components"]
                    if comp.get("name") in selected_set
                ]

                if filtered_components:
                    filtered_subsection = copy.deepcopy(subsection)
                    filtered_subsection["components"] = filtered_components
                    filtered_subsections.append(filtered_subsection)

        if filtered_subsections:
            filtered_section["subsections"] = filtered_subsections
            return filtered_section

    # 컴포넌트가 하나도 없으면 None 반환
    return None


def validate_components(
    structure: Dict[str, Any],
    selected_components: List[str]
) -> Dict[str, Any]:
    """
    선택된 컴포넌트 검증

    Args:
        structure: 전체 보고서 구조
        selected_components: 선택된 컴포넌트 name 리스트

    Returns:
        {
            "valid": bool,
            "invalid_components": List[str],  # 존재하지 않는 컴포넌트
            "message": str
        }
    """
    # 구조에서 모든 컴포넌트 이름 추출
    all_components = set()

    for section in structure.get("sections", []):
        if "components" in section:
            for comp in section["components"]:
                all_components.add(comp.get("name"))

        if "subsections" in section:
            for subsection in section["subsections"]:
                if "components" in subsection:
                    for comp in subsection["components"]:
                        all_components.add(comp.get("name"))

    # 선택된 컴포넌트 검증
    selected_set = set(selected_components)
    invalid = selected_set - all_components

    if invalid:
        return {
            "valid": False,
            "invalid_components": list(invalid),
            "message": f"존재하지 않는 컴포넌트: {', '.join(invalid)}"
        }

    return {
        "valid": True,
        "invalid_components": [],
        "message": "모든 컴포넌트가 유효합니다."
    }


def count_components(structure: Dict[str, Any]) -> int:
    """
    구조에 포함된 총 컴포넌트 개수 계산

    Args:
        structure: 보고서 구조

    Returns:
        컴포넌트 개수
    """
    count = 0

    for section in structure.get("sections", []):
        if "components" in section:
            count += len(section["components"])

        if "subsections" in section:
            for subsection in section["subsections"]:
                if "components" in subsection:
                    count += len(subsection["components"])

    return count


def get_section_summary(structure: Dict[str, Any]) -> Dict[str, int]:
    """
    섹션별 컴포넌트 개수 요약

    Args:
        structure: 보고서 구조

    Returns:
        섹션 ID를 키로 하는 컴포넌트 개수 딕셔너리
    """
    summary = {}

    for section in structure.get("sections", []):
        section_id = section.get("id", "")
        count = 0

        if "components" in section:
            count += len(section["components"])

        if "subsections" in section:
            for subsection in section["subsections"]:
                if "components" in subsection:
                    count += len(subsection["components"])

        summary[section_id] = count

    return summary


if __name__ == "__main__":
    # 테스트 코드
    from report_structure import get_report_structure

    print("=== Report Utils 테스트 ===\n")

    # 구조 생성
    structure = get_report_structure(2025, 9)

    # 1. 전체 컴포넌트 개수
    total = count_components(structure)
    print(f"1. 전체 컴포넌트 개수: {total}")

    # 2. 섹션별 요약
    print("\n2. 섹션별 컴포넌트 개수:")
    summary = get_section_summary(structure)
    for section_id, count in summary.items():
        print(f"   - {section_id}: {count}개")

    # 3. 컴포넌트 검증
    print("\n3. 컴포넌트 검증:")
    selected = ["operation_status", "ncms_bmt", "invalid_component"]
    result = validate_components(structure, selected)
    print(f"   Valid: {result['valid']}")
    print(f"   Message: {result['message']}")

    # 4. 구조 필터링
    print("\n4. 구조 필터링:")
    selected = ["operation_status", "ncms_bmt", "acs_db"]
    filtered = filter_structure(structure, selected)
    filtered_count = count_components(filtered)
    print(f"   선택된 컴포넌트: {len(selected)}개")
    print(f"   필터링 후 컴포넌트: {filtered_count}개")
    print(f"   필터링 후 섹션 개수: {len(filtered['sections'])}개")
