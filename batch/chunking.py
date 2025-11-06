#!/usr/bin/env python3
"""
Jira 이슈 청킹 모듈

Jira 이슈를 UnifiedChunk로 변환하고 텍스트를 청킹합니다.
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging
import sys
import os

# UnifiedChunk import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.unified_chunk import UnifiedChunk

logger = logging.getLogger(__name__)


def build_jira_jql(config: Dict, last_sync_time: datetime) -> str:
    """
    JQL 쿼리 생성

    Args:
        config: {
            "projects": ["BTVO"],
            "labels": {"BTVO": ["NCMS"]}
        }
        last_sync_time: 마지막 동기화 시각

    Returns:
        JQL 쿼리 문자열

    Example:
        project = BTVO AND labels IN (NCMS) AND updated >= '2025-10-23 09:00'
    """
    labels = config.get("labels", {})

    if not labels:
        # labels가 없으면 projects만 사용
        projects = config.get("projects", [])
        if not projects:
            raise ValueError("projects 또는 labels 중 하나는 필수입니다")

        project_conditions = [f"project = {p}" for p in projects]
        jql_base = " OR ".join(project_conditions)
    else:
        # 각 프로젝트별 조건 생성
        conditions = []
        for project, project_labels in labels.items():
            if project_labels:
                # 라벨이 있는 경우
                label_str = ", ".join(project_labels)
                conditions.append(
                    f"(project = {project} AND labels IN ({label_str}))"
                )
            else:
                # 라벨이 없으면 프로젝트만
                conditions.append(f"project = {project}")

        jql_base = " OR ".join(conditions)

    # 시간 조건 추가 (Jira JQL은 날짜만 지원)
    date_str = last_sync_time.strftime("%Y-%m-%d")
    jql = f"({jql_base}) AND updated >= '{date_str}'"

    # 정렬 추가 (최신순)
    jql += " ORDER BY updated DESC"

    logger.debug(f"생성된 JQL: {jql}")
    return jql


def chunk_text(text: str, max_length: int = 1000) -> List[str]:
    """
    긴 텍스트를 max_length 단위로 분할 (문장 경계 고려)

    Args:
        text: 분할할 텍스트
        max_length: 최대 청크 길이

    Returns:
        청크 리스트
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    # 문장 단위로 분할 (. 또는 \n 기준)
    sentences = text.replace("\n", ". ").split(". ")

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # 현재 청크에 추가 가능한지 확인
        if len(current_chunk) + len(sentence) + 2 <= max_length:
            current_chunk += sentence + ". "
        else:
            # 현재 청크 저장
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "

    # 마지막 청크 저장
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def issue_to_unified_chunks(issue: Dict, jira_endpoint: str) -> List[UnifiedChunk]:
    """
    하나의 Jira 이슈를 여러 UnifiedChunk로 변환

    청킹 전략:
    1. Summary (제목) → 1개 청크
    2. Description (본문) → 긴 경우 여러 청크 (1000자 단위)
    3. Comments → 각 코멘트당 1개 청크

    Args:
        issue: Jira 이슈 데이터
        jira_endpoint: Jira 서버 URL

    Returns:
        UnifiedChunk 리스트
    """
    issue_key = issue["key"]
    fields = issue["fields"]

    chunks = []
    now = datetime.now().isoformat()

    logger.debug(f"   📝 이슈 처리 중: {issue_key}")

    # 공통 메타데이터
    base_metadata = {
        "issue_key": issue_key,
        "issue_type": fields.get("issuetype", {}).get("name", "Unknown"),
        "status": fields.get("status", {}).get("name", "Unknown"),
        "priority": fields.get("priority", {}).get("name", "None"),
        "source_url": f"{jira_endpoint}/browse/{issue_key}",
        "labels": fields.get("labels", []),
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "project_key": fields.get("project", {}).get("key", "Unknown"),
        "summary": fields.get("summary", ""),
        "components": [c["name"] for c in fields.get("components", [])],
        "fix_versions": [v["name"] for v in fields.get("fixVersions", [])]
    }

    # 1. Summary 청크
    summary = fields.get("summary", "")
    if summary:
        chunks.append(UnifiedChunk(
            chunk_id=f"chunk_jira_{issue_key}_summary_0",
            data_source="jira",
            text_chunk=summary,
            created_at=now,
            updated_at=now,
            file_metadata=None,
            jira_metadata={
                **base_metadata,
                "chunk_type": "summary",
                "chunk_index": 0
            }
        ))
        logger.debug(f"      ✅ Summary 청크 생성")

    # 2. Description 청킹
    description = fields.get("description")
    if description and description.strip():
        desc_chunks = chunk_text(description, max_length=1000)
        for i, chunk_text_str in enumerate(desc_chunks):
            chunks.append(UnifiedChunk(
                chunk_id=f"chunk_jira_{issue_key}_description_{i}",
                data_source="jira",
                text_chunk=chunk_text_str,
                created_at=now,
                updated_at=now,
                file_metadata=None,
                jira_metadata={
                    **base_metadata,
                    "chunk_type": "description",
                    "chunk_index": i
                }
            ))
        logger.debug(f"      ✅ Description 청크 {len(desc_chunks)}개 생성")

    # 3. Comments
    comment_data = fields.get("comment", {})
    comments = comment_data.get("comments", []) if isinstance(comment_data, dict) else []

    for i, comment in enumerate(comments):
        comment_body = comment.get("body", "").strip()
        if comment_body:
            # 코멘트 작성자 정보
            comment_author = comment.get("author", {}).get("displayName", "Unknown")

            chunks.append(UnifiedChunk(
                chunk_id=f"chunk_jira_{issue_key}_comment_{i}",
                data_source="jira",
                text_chunk=comment_body,
                created_at=now,
                updated_at=now,
                file_metadata=None,
                jira_metadata={
                    **base_metadata,
                    "chunk_type": "comment",
                    "chunk_index": i,
                    "comment_author": comment_author
                }
            ))

    if comments:
        logger.debug(f"      ✅ Comment 청크 {len(comments)}개 생성")

    logger.debug(f"   총 {len(chunks)}개 청크 생성")
    return chunks


def process_issues_to_chunks(
    issues: List[Dict],
    jira_endpoint: str
) -> List[UnifiedChunk]:
    """
    여러 이슈를 UnifiedChunk로 변환

    Args:
        issues: Jira 이슈 리스트
        jira_endpoint: Jira 서버 URL

    Returns:
        UnifiedChunk 리스트
    """
    all_chunks = []

    logger.info(f"🔄 이슈 → 청크 변환 시작: {len(issues)}개 이슈")

    for issue in issues:
        try:
            chunks = issue_to_unified_chunks(issue, jira_endpoint)
            all_chunks.extend(chunks)
        except Exception as e:
            issue_key = issue.get("key", "Unknown")
            logger.error(f"❌ 이슈 처리 실패 ({issue_key}): {e}")
            continue

    logger.info(f"✅ 청크 변환 완료: {len(all_chunks)}개 청크 생성")
    return all_chunks


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("🧪 Chunking 모듈 테스트")
    print("=" * 60)

    # 1. JQL 생성 테스트
    print("\n[1] JQL 생성 테스트")
    config = {
        "projects": ["BTVO"],
        "labels": {"BTVO": ["NCMS"]}
    }
    last_sync = datetime(2025, 10, 23, 9, 0, 0)
    jql = build_jira_jql(config, last_sync)
    print(f"   JQL: {jql}")

    # 2. 텍스트 청킹 테스트
    print("\n[2] 텍스트 청킹 테스트")
    long_text = "이것은 테스트 문장입니다. " * 100  # 약 1400자
    chunks = chunk_text(long_text, max_length=1000)
    print(f"   원본 길이: {len(long_text)}자")
    print(f"   청크 개수: {len(chunks)}개")
    for i, chunk in enumerate(chunks):
        print(f"   청크 {i+1}: {len(chunk)}자")

    # 3. Mock 이슈 → 청크 변환 테스트
    print("\n[3] Mock 이슈 → 청크 변환 테스트")
    mock_issue = {
        "key": "BTVO-123",
        "fields": {
            "summary": "테스트 이슈",
            "description": "이것은 테스트 설명입니다.",
            "issuetype": {"name": "Bug"},
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "labels": ["NCMS"],
            "project": {"key": "BTVO"},
            "components": [],
            "fixVersions": [],
            "comment": {
                "comments": [
                    {"body": "테스트 코멘트", "author": {"displayName": "사용자1"}}
                ]
            }
        }
    }

    chunks = issue_to_unified_chunks(mock_issue, "https://jira.example.com")
    print(f"   생성된 청크: {len(chunks)}개")
    for chunk in chunks:
        print(f"   - {chunk.chunk_id}: {chunk.jira_metadata['chunk_type']}")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
