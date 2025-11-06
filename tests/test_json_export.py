#!/usr/bin/env python3
"""
JSON Export 기능 테스트
"""

import json
from datetime import datetime


def test_json_export():
    """
    JSON export 기능 테스트
    """
    print("=" * 70)
    print("🧪 JSON Export 테스트")
    print("=" * 70)

    # 1. 샘플 데이터 생성 (Streamlit에서 생성되는 형식)
    print("\n[1] 샘플 데이터 생성")

    pages_data = [
        {
            "page_title": "DB 작업 현황",
            "issues": [
                {
                    "key": "BTVO-61032",
                    "summary": "[NCMS] 데이터베이스 보정 작업",
                    "status": "신규",
                    "assignee": "조주연",
                    "created": "2025-10-15T10:30:00",
                    "updated": "2025-10-16T14:20:00",
                    "priority": "Medium",
                    "reporter": "user1",
                    "labels": ["NCMS", "DB"],
                    "components": ["Database"],
                    "_query_user": "user1"
                },
                {
                    "key": "BTVO-61033",
                    "summary": "테이블 스키마 변경",
                    "status": "완료",
                    "assignee": "김철수",
                    "created": "2025-10-16T09:00:00",
                    "updated": "2025-10-17T15:30:00",
                    "priority": "High",
                    "reporter": "user1",
                    "labels": ["Backend"],
                    "components": [],
                    "_query_user": "user1"
                }
            ],
            "output_format": {
                "type": "table",
                "columns": ["key", "summary", "status", "assignee", "created"]
            },
            "queries": [
                {"user": "user1", "jql": "project = BTVO AND labels = 'NCMS'"}
            ]
        },
        {
            "page_title": "API 개발 현황",
            "issues": [
                {
                    "key": "PROJ-456",
                    "summary": "REST API 엔드포인트 추가",
                    "status": "진행중",
                    "assignee": "박영희",
                    "created": "2025-10-17T11:20:00",
                    "updated": "2025-10-18T10:00:00",
                    "priority": "Low",
                    "reporter": "user2",
                    "labels": ["API", "Backend"],
                    "components": ["API"],
                    "_query_user": "user2"
                }
            ],
            "output_format": {
                "type": "table",
                "columns": ["key", "summary", "status", "assignee"]
            },
            "queries": [
                {"user": "user2", "jql": "project = PROJ AND component = 'API'"}
            ]
        }
    ]

    report_period = "2025-10"
    print(f"   생성된 페이지: {len(pages_data)}개")
    print(f"   총 이슈: {sum(len(p['issues']) for p in pages_data)}개")

    # 2. JSON export 데이터 생성
    print("\n[2] JSON export 데이터 생성")

    json_export = {
        "metadata": {
            "export_time": datetime.now().isoformat(),
            "report_period": report_period,
            "total_pages": len(pages_data),
            "total_issues": sum(len(p['issues']) for p in pages_data)
        },
        "pages": []
    }

    for page_data in pages_data:
        page_export = {
            "page_title": page_data['page_title'],
            "issue_count": len(page_data['issues']),
            "output_format": page_data['output_format'],
            "queries": page_data.get('queries', []),
            "issues": page_data['issues']
        }
        json_export["pages"].append(page_export)

    print(f"   ✅ JSON 데이터 생성 완료")

    # 3. JSON 문자열로 변환
    print("\n[3] JSON 문자열 변환")

    json_str = json.dumps(json_export, indent=2, ensure_ascii=False)
    print(f"   JSON 크기: {len(json_str)} bytes")
    print(f"   ✅ 변환 성공")

    # 4. 파일로 저장
    print("\n[4] JSON 파일 저장")

    filename = f"test_jira_issues_{report_period.replace('-', '')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(json_str)

    print(f"   ✅ {filename} 저장 완료")

    # 5. 저장된 파일 읽기 및 검증
    print("\n[5] 저장된 파일 검증")

    with open(filename, "r", encoding="utf-8") as f:
        loaded_data = json.load(f)

    # 검증
    assert "metadata" in loaded_data, "metadata 필드가 없습니다"
    assert "pages" in loaded_data, "pages 필드가 없습니다"
    assert loaded_data["metadata"]["total_pages"] == 2, "페이지 수가 일치하지 않습니다"
    assert loaded_data["metadata"]["total_issues"] == 3, "이슈 수가 일치하지 않습니다"
    assert len(loaded_data["pages"]) == 2, "페이지 수가 일치하지 않습니다"
    assert loaded_data["pages"][0]["page_title"] == "DB 작업 현황", "페이지 제목이 일치하지 않습니다"
    assert len(loaded_data["pages"][0]["issues"]) == 2, "첫 번째 페이지 이슈 수가 일치하지 않습니다"

    print(f"   ✅ 모든 검증 통과")

    # 6. 데이터 구조 출력
    print("\n[6] JSON 구조 미리보기")
    print(json.dumps(json_export, indent=2, ensure_ascii=False)[:500] + "...")

    # 7. 활용 예시
    print("\n[7] 활용 예시")
    print("   Python에서 읽기:")
    print(f"     data = json.load(open('{filename}'))")
    print(f"     total_issues = data['metadata']['total_issues']")
    print(f"     # 결과: {loaded_data['metadata']['total_issues']}")

    print("\n   페이지별 이슈 조회:")
    for i, page in enumerate(loaded_data['pages']):
        print(f"     페이지 {i+1}: {page['page_title']} - {page['issue_count']}개")

    print("\n" + "=" * 70)
    print("✅ 모든 테스트 통과!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_json_export()
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
