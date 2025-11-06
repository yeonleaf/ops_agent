#!/usr/bin/env python3
"""
HTMLGeneratorTool 테스트 스크립트
"""

import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from tools.html_generator_tool import HTMLGeneratorTool

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_html_generator():
    """
    HTMLGeneratorTool 기본 테스트
    """
    print("=" * 70)
    print("🧪 HTMLGeneratorTool 테스트")
    print("=" * 70)

    # 1. 초기화
    print("\n[1] HTMLGeneratorTool 초기화")
    tool = HTMLGeneratorTool()
    print("   ✅ 초기화 성공")

    # 2. 샘플 데이터 생성
    print("\n[2] 샘플 데이터 생성")
    sample_issues = [
        {
            "key": "BTVO-61032",
            "summary": "[NCMS] PD_PRD_GRP_SUB_EPSD_REL 테이블의 SRIS_ID 보정",
            "status": "신규",
            "assignee": "[SK C&C] 조주연",
            "created": "2025-10-15T10:30:00",
            "updated": "2025-10-16T14:20:00",
            "priority": "Medium",
            "reporter": "user1",
            "labels": ["NCMS", "DB"],
            "components": ["Database"],
            "issuetype": "Task",
            "_query_user": "user1"
        },
        {
            "key": "BTVO-61033",
            "summary": "[테스트] 두 번째 이슈 - 완료 상태",
            "status": "완료",
            "assignee": "김철수",
            "created": "2025-10-16T09:00:00",
            "updated": "2025-10-17T15:30:00",
            "priority": "High",
            "reporter": "user1",
            "labels": ["Backend"],
            "components": [],
            "issuetype": "Bug",
            "_query_user": "user1"
        },
        {
            "key": "PROJ-456",
            "summary": "다른 프로젝트 이슈 - 진행중",
            "status": "진행중",
            "assignee": "박영희",
            "created": "2025-10-17T11:20:00",
            "updated": "2025-10-18T10:00:00",
            "priority": "Low",
            "reporter": "user2",
            "labels": ["Frontend", "UI"],
            "components": ["UI"],
            "issuetype": "Story",
            "_query_user": "user2"
        },
        {
            "key": "PROJ-457",
            "summary": "네 번째 이슈 - 보류",
            "status": "보류",
            "assignee": "이영수",
            "created": "2025-10-18T14:00:00",
            "updated": "2025-10-19T09:30:00",
            "priority": "Medium",
            "reporter": "user2",
            "labels": [],
            "components": ["API"],
            "issuetype": "Task",
            "_query_user": "user2"
        }
    ]

    print(f"   생성된 샘플 이슈: {len(sample_issues)}개")

    # 3. 테이블 생성 테스트
    print("\n[3] 테이블 HTML 생성 테스트")
    output_format = {
        "type": "table",
        "columns": ["key", "summary", "status", "assignee", "created", "labels"]
    }

    table_html = tool.generate_table(
        issues=sample_issues,
        columns=output_format['columns'],
        group_by_user=True
    )

    print(f"   ✅ 테이블 HTML 생성 성공 (길이: {len(table_html)} bytes)")
    assert len(table_html) > 0, "테이블 HTML이 비어있습니다"
    assert "BTVO-61032" in table_html, "이슈 키가 HTML에 없습니다"

    # 4. 페이지 생성 테스트
    print("\n[4] 페이지 HTML 생성 테스트")
    page_html = tool.generate_page(
        page_title="테스트 페이지 - DB 작업 현황",
        issues=sample_issues,
        output_format=output_format,
        report_period="2025-10"
    )

    print(f"   ✅ 페이지 HTML 생성 성공 (길이: {len(page_html)} bytes)")
    assert "테스트 페이지 - DB 작업 현황" in page_html, "페이지 제목이 없습니다"

    # 5. 전체 보고서 생성 테스트
    print("\n[5] 전체 보고서 HTML 생성 테스트")

    pages_data = [
        {
            "page_title": "DB 작업 현황",
            "issues": sample_issues[:2],  # user1 이슈
            "output_format": {
                "type": "table",
                "columns": ["key", "summary", "status", "assignee", "created"]
            }
        },
        {
            "page_title": "API 개발 현황",
            "issues": sample_issues[2:],  # user2 이슈
            "output_format": {
                "type": "table",
                "columns": ["key", "summary", "status", "assignee", "labels", "components"]
            }
        }
    ]

    full_html = tool.generate_full_report(
        pages_data=pages_data,
        report_title="2025년 10월 월간 보고서",
        report_period="2025-10"
    )

    print(f"   ✅ 전체 보고서 생성 성공 (길이: {len(full_html)} bytes)")
    assert "<!DOCTYPE html>" in full_html, "HTML 문서 형식이 아닙니다"
    assert "DB 작업 현황" in full_html, "첫 번째 페이지가 없습니다"
    assert "API 개발 현황" in full_html, "두 번째 페이지가 없습니다"

    # 6. 파일로 저장
    print("\n[6] HTML 파일 저장")
    output_file = "test_output.html"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"   ✅ {output_file} 저장 완료")
        print(f"   📁 파일 크기: {len(full_html)} bytes")

        # 절대 경로 출력
        abs_path = os.path.abspath(output_file)
        print(f"   📂 파일 위치: {abs_path}")
        print(f"   🌐 브라우저로 확인: file://{abs_path}")
    except Exception as e:
        print(f"   ❌ 파일 저장 실패: {e}")

    # 7. 빈 이슈 처리 테스트
    print("\n[7] 빈 이슈 처리 테스트")
    empty_html = tool.generate_table(
        issues=[],
        columns=["key", "summary"],
        group_by_user=False
    )
    print(f"   ✅ 빈 이슈 처리 성공")
    assert "조회된 이슈가 없습니다" in empty_html, "빈 상태 메시지가 없습니다"

    print("\n" + "=" * 70)
    print("✅ 모든 테스트 통과!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_html_generator()
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
