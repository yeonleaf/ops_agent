#!/usr/bin/env python3
"""
다중 사용자 Jira 동기화 배치

여러 사용자에 대해 Jira 동기화 배치를 실행합니다.
"""

import logging
from typing import List, Dict
from datetime import datetime
import concurrent.futures
from collections import defaultdict

# 로컬 모듈
from batch.jira_config import get_all_jira_users, validate_jira_config
from batch.jira_sync import run_jira_sync_batch

logger = logging.getLogger(__name__)


def run_multi_user_batch(
    user_ids: List[int] = None,
    db_path: str = "tickets.db",
    parallel: bool = False,
    max_workers: int = 3,
    force_full_sync: bool = False
) -> Dict:
    """
    여러 사용자에 대해 Jira 동기화 배치 실행

    Args:
        user_ids: 사용자 ID 리스트 (None이면 모든 Jira 사용자)
        db_path: SQLite DB 경로
        parallel: 병렬 실행 여부
        max_workers: 병렬 실행 시 최대 워커 수
        force_full_sync: 전체 동기화 여부

    Returns:
        {
            "total_users": 전체 사용자 수,
            "successful": 성공한 사용자 수,
            "failed": 실패한 사용자 수,
            "skipped": 스킵된 사용자 수,
            "results": [사용자별 결과],
            "summary": {
                "total_issues": 전체 이슈 수,
                "total_chunks": 전체 청크 수
            }
        }
    """
    start_time = datetime.now()

    logger.info("=" * 70)
    logger.info("🚀 다중 사용자 Jira 동기화 배치 시작")
    logger.info(f"   시작 시각: {start_time}")
    logger.info(f"   병렬 실행: {'✅ Yes' if parallel else '❌ No'}")
    if parallel:
        logger.info(f"   최대 워커: {max_workers}")
    logger.info("=" * 70)

    # 1. 사용자 ID 결정
    if user_ids is None:
        logger.info("\n[1/3] 모든 Jira 사용자 조회")
        user_ids = get_all_jira_users(db_path)
        if not user_ids:
            logger.warning("⚠️ Jira 연동 사용자가 없습니다")
            return {
                "total_users": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
                "summary": {"total_issues": 0, "total_chunks": 0}
            }
    else:
        logger.info(f"\n[1/3] 지정된 사용자: {user_ids}")

    logger.info(f"   총 {len(user_ids)}명의 사용자에 대해 배치 실행")

    # 2. 사용자 설정 검증
    logger.info("\n[2/3] 사용자 설정 검증")
    valid_users = []
    invalid_users = []

    for user_id in user_ids:
        if validate_jira_config(user_id, db_path):
            valid_users.append(user_id)
            logger.info(f"   ✅ User {user_id}: 설정 유효")
        else:
            invalid_users.append(user_id)
            logger.warning(f"   ⚠️ User {user_id}: 설정 무효 (스킵)")

    logger.info(f"   유효 사용자: {len(valid_users)}명")
    logger.info(f"   무효 사용자: {len(invalid_users)}명")

    if not valid_users:
        logger.warning("⚠️ 유효한 사용자가 없습니다")
        return {
            "total_users": len(user_ids),
            "successful": 0,
            "failed": 0,
            "skipped": len(invalid_users),
            "results": [],
            "summary": {"total_issues": 0, "total_chunks": 0}
        }

    # 3. 배치 실행
    logger.info(f"\n[3/3] 배치 실행 ({len(valid_users)}명)")

    results = []
    if parallel:
        # 병렬 실행
        logger.info(f"   🔄 병렬 실행 모드 (max_workers={max_workers})")
        results = _run_parallel_batch(valid_users, db_path, force_full_sync, max_workers)
    else:
        # 순차 실행
        logger.info(f"   🔄 순차 실행 모드")
        results = _run_sequential_batch(valid_users, db_path, force_full_sync)

    # 4. 결과 집계
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_issues = sum(r.get("issues_count", 0) for r in results if r["status"] == "success")
    total_chunks = sum(r.get("processed_count", 0) for r in results if r["status"] == "success")

    # 완료
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("\n" + "=" * 70)
    logger.info("✅ 다중 사용자 Jira 동기화 배치 완료")
    logger.info(f"   전체 사용자: {len(user_ids)}명")
    logger.info(f"   성공: {successful}명")
    logger.info(f"   실패: {failed}명")
    logger.info(f"   스킵: {len(invalid_users)}명")
    logger.info(f"   전체 이슈: {total_issues}개")
    logger.info(f"   전체 청크: {total_chunks}개")
    logger.info(f"   소요 시간: {duration:.2f}초")
    logger.info("=" * 70)

    return {
        "total_users": len(user_ids),
        "successful": successful,
        "failed": failed,
        "skipped": len(invalid_users),
        "results": results,
        "summary": {
            "total_issues": total_issues,
            "total_chunks": total_chunks,
            "duration": duration
        }
    }


def _run_sequential_batch(
    user_ids: List[int],
    db_path: str,
    force_full_sync: bool
) -> List[Dict]:
    """
    순차 실행

    Args:
        user_ids: 사용자 ID 리스트
        db_path: DB 경로
        force_full_sync: 전체 동기화 여부

    Returns:
        사용자별 결과 리스트
    """
    results = []

    for i, user_id in enumerate(user_ids, 1):
        logger.info(f"\n   [{i}/{len(user_ids)}] User {user_id} 배치 실행")
        logger.info(f"   " + "-" * 60)

        try:
            result = run_jira_sync_batch(
                user_id=user_id,
                db_path=db_path,
                force_full_sync=force_full_sync
            )
            result["user_id"] = user_id
            results.append(result)

            if result["status"] == "success":
                logger.info(f"   ✅ User {user_id}: 성공 (이슈 {result.get('issues_count', 0)}개, 청크 {result.get('processed_count', 0)}개)")
            else:
                logger.error(f"   ❌ User {user_id}: 실패 - {result.get('error', 'Unknown')}")

        except Exception as e:
            logger.error(f"   ❌ User {user_id}: 예외 발생 - {e}")
            results.append({
                "user_id": user_id,
                "status": "failed",
                "error": str(e)
            })

    return results


def _run_parallel_batch(
    user_ids: List[int],
    db_path: str,
    force_full_sync: bool,
    max_workers: int
) -> List[Dict]:
    """
    병렬 실행

    Args:
        user_ids: 사용자 ID 리스트
        db_path: DB 경로
        force_full_sync: 전체 동기화 여부
        max_workers: 최대 워커 수

    Returns:
        사용자별 결과 리스트
    """
    results = []

    def execute_batch(user_id: int) -> Dict:
        """단일 사용자 배치 실행 (워커 함수)"""
        try:
            logger.info(f"   🔄 User {user_id} 시작")
            result = run_jira_sync_batch(
                user_id=user_id,
                db_path=db_path,
                force_full_sync=force_full_sync
            )
            result["user_id"] = user_id

            if result["status"] == "success":
                logger.info(f"   ✅ User {user_id} 완료: 이슈 {result.get('issues_count', 0)}개, 청크 {result.get('processed_count', 0)}개")
            else:
                logger.error(f"   ❌ User {user_id} 실패: {result.get('error', 'Unknown')}")

            return result

        except Exception as e:
            logger.error(f"   ❌ User {user_id} 예외: {e}")
            return {
                "user_id": user_id,
                "status": "failed",
                "error": str(e)
            }

    # ThreadPoolExecutor로 병렬 실행
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_user = {executor.submit(execute_batch, user_id): user_id for user_id in user_ids}

        for future in concurrent.futures.as_completed(future_to_user):
            user_id = future_to_user[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"   ❌ User {user_id} Future 예외: {e}")
                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "error": str(e)
                })

    return results


def print_batch_summary(result: Dict):
    """
    배치 결과 요약 출력

    Args:
        result: run_multi_user_batch() 결과
    """
    print("\n" + "=" * 70)
    print("📊 다중 사용자 배치 결과 요약")
    print("=" * 70)

    print(f"\n전체 통계:")
    print(f"  - 전체 사용자: {result['total_users']}명")
    print(f"  - 성공: {result['successful']}명")
    print(f"  - 실패: {result['failed']}명")
    print(f"  - 스킵: {result['skipped']}명")

    print(f"\n데이터 통계:")
    print(f"  - 전체 이슈: {result['summary']['total_issues']}개")
    print(f"  - 전체 청크: {result['summary']['total_chunks']}개")
    print(f"  - 소요 시간: {result['summary'].get('duration', 0):.2f}초")

    # 사용자별 상세 결과
    if result['results']:
        print(f"\n사용자별 결과:")
        print(f"  {'User ID':<10} {'Status':<10} {'Issues':<10} {'Chunks':<10} {'Error':<30}")
        print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*30}")

        for r in result['results']:
            user_id = r['user_id']
            status = r['status']
            issues = r.get('issues_count', 0) if status == 'success' else '-'
            chunks = r.get('processed_count', 0) if status == 'success' else '-'
            error = r.get('error', '')[:28] if status == 'failed' else ''

            status_icon = "✅" if status == "success" else "❌"
            print(f"  {user_id:<10} {status_icon} {status:<8} {issues:<10} {chunks:<10} {error:<30}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    # 테스트 코드
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description="다중 사용자 Jira 동기화 배치 테스트")
    parser.add_argument("--parallel", action="store_true", help="병렬 실행")
    parser.add_argument("--max-workers", type=int, default=3, help="최대 워커 수")
    parser.add_argument("--user-ids", type=str, help="사용자 ID (쉼표 구분)")

    args = parser.parse_args()

    user_ids = None
    if args.user_ids:
        user_ids = [int(uid.strip()) for uid in args.user_ids.split(",")]

    result = run_multi_user_batch(
        user_ids=user_ids,
        parallel=args.parallel,
        max_workers=args.max_workers
    )

    print_batch_summary(result)
