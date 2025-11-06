#!/usr/bin/env python3
"""
Jira 동기화 배치 메인 모듈

Jira API를 통해 이슈를 가져와 UnifiedChunk로 변환하고
ChromaDB에 저장합니다.
"""

import logging
import argparse
import sys
import os
from typing import Dict, List
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 로컬 모듈 import
from batch.jira_config import (
    create_batch_history_table,
    load_jira_config,
    get_last_sync_time,
    update_batch_history
)
from batch.jira_client import JiraClient, JiraAPIError
from batch.chunking import build_jira_jql, process_issues_to_chunks
from models.unified_chunk import UnifiedChunk
from chromadb_singleton import get_chromadb_client

logger = logging.getLogger(__name__)


def save_chunks_to_chromadb(chunks: List[UnifiedChunk]) -> int:
    """
    UnifiedChunk를 ChromaDB에 저장 (upsert)

    Args:
        chunks: UnifiedChunk 리스트

    Returns:
        저장된 청크 개수

    Raises:
        Exception: ChromaDB 저장 실패 시
    """
    if not chunks:
        logger.warning("⚠️ 저장할 청크가 없습니다")
        return 0

    try:
        # ChromaDB 클라이언트 가져오기
        client = get_chromadb_client()

        # jira_chunks 컬렉션 가져오기/생성
        try:
            collection = client.get_collection("jira_chunks")
            logger.debug("✅ 기존 jira_chunks 컬렉션 사용")
        except:
            collection = client.create_collection(
                name="jira_chunks",
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Jira issue chunks for RAG system",
                    "schema_version": "unified_v1",
                    "created_at": datetime.now().isoformat()
                }
            )
            logger.info("✅ jira_chunks 컬렉션 생성")

        # Upsert 로직
        saved_count = 0
        for chunk in chunks:
            try:
                # 메타데이터 준비
                metadata = {
                    # 공통 필드
                    "data_source": chunk.data_source,
                    "created_at": chunk.created_at,
                    "updated_at": chunk.updated_at,
                }

                # jira_metadata 주요 필드 추출
                if chunk.jira_metadata:
                    metadata["issue_key"] = chunk.jira_metadata.get("issue_key", "")
                    metadata["chunk_type"] = chunk.jira_metadata.get("chunk_type", "")
                    metadata["chunk_index"] = chunk.jira_metadata.get("chunk_index", 0)
                    metadata["issue_type"] = chunk.jira_metadata.get("issue_type", "")
                    metadata["status"] = chunk.jira_metadata.get("status", "")
                    metadata["priority"] = chunk.jira_metadata.get("priority", "")
                    metadata["project_key"] = chunk.jira_metadata.get("project_key", "")
                    metadata["source_url"] = chunk.jira_metadata.get("source_url", "")

                    # 리스트 필드는 JSON 직렬화
                    import json
                    if chunk.jira_metadata.get("labels"):
                        metadata["labels"] = json.dumps(chunk.jira_metadata["labels"], ensure_ascii=False)
                    if chunk.jira_metadata.get("components"):
                        metadata["components"] = json.dumps(chunk.jira_metadata["components"], ensure_ascii=False)
                    if chunk.jira_metadata.get("fix_versions"):
                        metadata["fix_versions"] = json.dumps(chunk.jira_metadata["fix_versions"], ensure_ascii=False)

                    # 선택적 필드
                    if chunk.jira_metadata.get("assignee"):
                        metadata["assignee"] = chunk.jira_metadata["assignee"]
                    if chunk.jira_metadata.get("reporter"):
                        metadata["reporter"] = chunk.jira_metadata["reporter"]
                    if chunk.jira_metadata.get("summary"):
                        metadata["summary"] = chunk.jira_metadata["summary"]
                    if chunk.jira_metadata.get("comment_author"):
                        metadata["comment_author"] = chunk.jira_metadata["comment_author"]

                # None 값 제거 (ChromaDB는 None 허용 안 함)
                metadata = {k: v for k, v in metadata.items() if v is not None}

                # Upsert
                collection.upsert(
                    ids=[chunk.chunk_id],
                    documents=[chunk.text_chunk],
                    metadatas=[metadata]
                )

                saved_count += 1

                # 진행상황 로깅 (100개마다)
                if saved_count % 100 == 0:
                    logger.info(f"   💾 {saved_count}/{len(chunks)} 저장 중...")

            except Exception as e:
                logger.error(f"❌ 청크 저장 실패 ({chunk.chunk_id}): {e}")
                continue

        logger.info(f"✅ ChromaDB 저장 완료: {saved_count}개 청크")
        return saved_count

    except Exception as e:
        logger.error(f"❌ ChromaDB 저장 실패: {e}")
        raise


def run_jira_sync_batch(
    user_id: int,
    db_path: str = "tickets.db",
    force_full_sync: bool = False
) -> Dict:
    """
    Jira 동기화 배치 실행

    Args:
        user_id: 사용자 ID
        db_path: SQLite DB 경로
        force_full_sync: True면 마지막 실행 시각 무시하고 전체 동기화 (7일)

    Returns:
        {
            "status": "success" | "failed",
            "processed_count": 숫자,
            "issues_count": 숫자,
            "error": 에러 메시지 (실패 시)
        }
    """
    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info(f"🚀 Jira 동기화 배치 시작")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   시작 시각: {start_time}")
    logger.info("=" * 60)

    try:
        # 1. Jira 설정 로드
        logger.info("\n[1/7] Jira 설정 로드")
        config = load_jira_config(user_id, db_path)
        if not config or not config.get("token"):
            raise ValueError("Jira 연동 정보가 없거나 토큰이 없습니다")

        logger.info(f"   ✅ Endpoint: {config['endpoint']}")
        logger.info(f"   ✅ Projects: {config.get('projects', [])}")

        # 2. 마지막 실행 시각 조회
        logger.info("\n[2/7] 마지막 동기화 시각 조회")
        if force_full_sync:
            from datetime import timedelta
            last_sync_time = datetime.now() - timedelta(days=7)
            logger.info(f"   🔄 전체 동기화 모드: 7일 전부터")
        else:
            last_sync_time = get_last_sync_time(user_id, "jira_sync", db_path)
        logger.info(f"   📅 조회 시작 시각: {last_sync_time}")

        # 3. JQL 쿼리 생성
        logger.info("\n[3/7] JQL 쿼리 생성")
        jql = build_jira_jql(config, last_sync_time)
        logger.info(f"   📝 JQL: {jql}")

        # 4. Jira 이슈 가져오기
        logger.info("\n[4/7] Jira API 호출")
        client = JiraClient(config["endpoint"], config["token"])

        # 연결 테스트
        if not client.test_connection():
            raise JiraAPIError("Jira 연결 실패")

        issues = client.search_issues(jql, max_results=100)
        logger.info(f"   ✅ 조회된 이슈: {len(issues)}개")

        if len(issues) == 0:
            logger.info("   ℹ️ 새로운 이슈가 없습니다")
            update_batch_history(
                user_id=user_id,
                batch_type="jira_sync",
                status="success",
                processed_count=0,
                db_path=db_path
            )
            return {
                "status": "success",
                "processed_count": 0,
                "issues_count": 0
            }

        # 5. UnifiedChunk로 변환
        logger.info("\n[5/7] 이슈 → 청크 변환")
        all_chunks = process_issues_to_chunks(issues, config["endpoint"])
        logger.info(f"   ✅ 생성된 청크: {len(all_chunks)}개")

        # 6. ChromaDB 저장
        logger.info("\n[6/7] ChromaDB 저장")
        processed_count = save_chunks_to_chromadb(all_chunks)

        # 7. 배치 이력 저장
        logger.info("\n[7/7] 배치 이력 저장")
        update_batch_history(
            user_id=user_id,
            batch_type="jira_sync",
            status="success",
            processed_count=processed_count,
            db_path=db_path
        )

        # 완료
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("\n" + "=" * 60)
        logger.info(f"✅ Jira 동기화 배치 완료")
        logger.info(f"   이슈 수: {len(issues)}개")
        logger.info(f"   청크 수: {processed_count}개")
        logger.info(f"   소요 시간: {duration:.2f}초")
        logger.info("=" * 60)

        return {
            "status": "success",
            "processed_count": processed_count,
            "issues_count": len(issues),
            "duration": duration
        }

    except Exception as e:
        logger.error(f"\n❌ Jira 동기화 배치 실패: {e}", exc_info=True)

        # 배치 이력 저장 (실패)
        update_batch_history(
            user_id=user_id,
            batch_type="jira_sync",
            status="failed",
            processed_count=0,
            error_message=str(e),
            db_path=db_path
        )

        return {
            "status": "failed",
            "error": str(e)
        }


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(
        description="Jira 이슈 동기화 배치",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 단일 사용자 실행
  python batch/jira_sync.py --user-id 1

  # 모든 Jira 사용자 실행
  python batch/jira_sync.py --all-users

  # 특정 사용자들만 실행
  python batch/jira_sync.py --user-ids 1,2,3

  # 병렬 실행
  python batch/jira_sync.py --all-users --parallel --max-workers 5

  # 전체 동기화 (7일간)
  python batch/jira_sync.py --user-id 1 --full-sync

  # DB 초기화
  python batch/jira_sync.py --init-db
        """
    )

    # 사용자 선택 옵션 (mutually exclusive)
    user_group = parser.add_mutually_exclusive_group(required=False)
    user_group.add_argument(
        "--user-id",
        type=int,
        help="단일 사용자 ID"
    )
    user_group.add_argument(
        "--all-users",
        action="store_true",
        help="모든 Jira 연동 사용자 실행"
    )
    user_group.add_argument(
        "--user-ids",
        type=str,
        help="사용자 ID 목록 (쉼표 구분, 예: 1,2,3)"
    )

    # 공통 옵션
    parser.add_argument(
        "--db-path",
        type=str,
        default="tickets.db",
        help="SQLite DB 경로 (기본값: tickets.db)"
    )
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="전체 동기화 (마지막 실행 시각 무시)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 모드 (상세 로그 출력)"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="batch_history 테이블 초기화"
    )

    # 다중 사용자 옵션
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="병렬 실행 (--all-users 또는 --user-ids와 함께 사용)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="병렬 실행 시 최대 워커 수 (기본값: 3)"
    )

    args = parser.parse_args()

    # 로깅 설정
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # DB 초기화 (선택적)
    if args.init_db:
        print("🔧 batch_history 테이블 초기화 중...")
        success = create_batch_history_table(args.db_path)
        if success:
            print("✅ 초기화 완료")
        else:
            print("❌ 초기화 실패")
            sys.exit(1)
        # init-db만 실행하고 종료
        if not (args.user_id or args.all_users or args.user_ids):
            sys.exit(0)

    # 사용자 선택 확인
    if not (args.user_id or args.all_users or args.user_ids):
        parser.error("--user-id, --all-users, 또는 --user-ids 중 하나는 필수입니다")

    # 다중 사용자 배치 실행
    if args.all_users or args.user_ids:
        from batch.multi_user_sync import run_multi_user_batch, print_batch_summary

        # 사용자 ID 목록 생성
        user_ids = None
        if args.user_ids:
            try:
                user_ids = [int(uid.strip()) for uid in args.user_ids.split(",")]
            except ValueError:
                print("❌ --user-ids 형식 오류: 쉼표로 구분된 숫자를 입력하세요 (예: 1,2,3)")
                sys.exit(1)

        # 다중 사용자 배치 실행
        result = run_multi_user_batch(
            user_ids=user_ids,
            db_path=args.db_path,
            parallel=args.parallel,
            max_workers=args.max_workers,
            force_full_sync=args.full_sync
        )

        # 결과 출력
        print_batch_summary(result)

        # 종료 코드 결정
        if result["failed"] == 0:
            sys.exit(0)
        elif result["successful"] > 0:
            sys.exit(2)  # 일부 성공, 일부 실패
        else:
            sys.exit(1)  # 전체 실패

    # 단일 사용자 배치 실행
    else:
        result = run_jira_sync_batch(
            user_id=args.user_id,
            db_path=args.db_path,
            force_full_sync=args.full_sync
        )

        # 결과 출력
        print("\n📊 배치 실행 결과:")
        print(f"   상태: {result['status']}")
        if result["status"] == "success":
            print(f"   처리 이슈: {result.get('issues_count', 0)}개")
            print(f"   저장 청크: {result.get('processed_count', 0)}개")
            print(f"   소요 시간: {result.get('duration', 0):.2f}초")
            sys.exit(0)
        else:
            print(f"   에러: {result.get('error', 'Unknown')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
