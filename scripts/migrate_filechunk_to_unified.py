#!/usr/bin/env python3
"""
FileChunk → UnifiedChunk 마이그레이션 스크립트

기존 file_chunks 컬렉션의 FileChunk 데이터를
UnifiedChunk 형식으로 변환하여 저장합니다.

Usage:
    # Dry-run (실행하지 않고 계획만 확인)
    python scripts/migrate_filechunk_to_unified.py --dry-run

    # 백업 생성 후 마이그레이션 실행
    python scripts/migrate_filechunk_to_unified.py --backup --execute

    # 롤백 (백업에서 복원)
    python scripts/migrate_filechunk_to_unified.py --rollback
"""

import argparse
import os
import sys
import shutil
from datetime import datetime
from typing import List, Dict, Any
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chromadb_singleton import get_chromadb_client
from models.unified_chunk import UnifiedChunk
from vector_db_models import VectorDBManager


class FileChunkMigrator:
    """FileChunk → UnifiedChunk 마이그레이션 관리자"""

    def __init__(self, db_path: str = "./vector_db"):
        """
        초기화

        Args:
            db_path: ChromaDB 경로
        """
        self.db_path = db_path
        self.backup_path = f"{db_path}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.client = get_chromadb_client()
        self.vector_db = VectorDBManager(db_path=db_path)

    def analyze_current_data(self) -> Dict[str, Any]:
        """
        현재 데이터 분석

        Returns:
            분석 결과 딕셔너리
        """
        print("\n" + "=" * 60)
        print("📊 현재 데이터 분석")
        print("=" * 60)

        try:
            collection = self.client.get_collection("file_chunks")
            total_count = collection.count()

            print(f"✅ file_chunks 컬렉션 발견")
            print(f"   총 청크 개수: {total_count}개")

            if total_count == 0:
                print("⚠️  컬렉션이 비어있습니다. 마이그레이션이 필요 없습니다.")
                return {"total_count": 0, "needs_migration": False}

            # 샘플 데이터 조회 (처음 5개)
            sample_data = collection.get(limit=5, include=["metadatas", "documents"])

            print(f"\n📋 샘플 데이터 구조:")
            if sample_data['metadatas']:
                sample_metadata = sample_data['metadatas'][0]
                print(f"   메타데이터 키: {list(sample_metadata.keys())}")

                # 스키마 버전 확인
                if "data_source" in sample_metadata:
                    print(f"   ✅ 이미 UnifiedChunk 스키마입니다")
                    return {
                        "total_count": total_count,
                        "needs_migration": False,
                        "schema_version": "unified_v1"
                    }
                else:
                    print(f"   🔄 FileChunk 스키마 → UnifiedChunk 스키마 마이그레이션 필요")
                    return {
                        "total_count": total_count,
                        "needs_migration": True,
                        "schema_version": "file_chunk_legacy"
                    }

        except Exception as e:
            print(f"❌ 데이터 분석 실패: {e}")
            return {"total_count": 0, "needs_migration": False, "error": str(e)}

    def backup_database(self) -> bool:
        """
        데이터베이스 백업

        Returns:
            성공 여부
        """
        print("\n" + "=" * 60)
        print("💾 데이터베이스 백업")
        print("=" * 60)

        try:
            if os.path.exists(self.backup_path):
                print(f"⚠️  백업 경로가 이미 존재합니다: {self.backup_path}")
                print(f"   기존 백업을 삭제합니다...")
                shutil.rmtree(self.backup_path)

            print(f"📁 백업 생성 중: {self.db_path} → {self.backup_path}")
            shutil.copytree(self.db_path, self.backup_path)
            print(f"✅ 백업 완료!")
            return True

        except Exception as e:
            print(f"❌ 백업 실패: {e}")
            return False

    def migrate_data(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        데이터 마이그레이션 실행

        Args:
            dry_run: True면 실제 실행하지 않고 계획만 출력

        Returns:
            마이그레이션 결과
        """
        print("\n" + "=" * 60)
        if dry_run:
            print("🔍 마이그레이션 계획 (Dry-run)")
        else:
            print("🚀 마이그레이션 실행")
        print("=" * 60)

        try:
            collection = self.client.get_collection("file_chunks")
            total_count = collection.count()

            print(f"📊 총 {total_count}개 청크 마이그레이션 예정")

            # 모든 데이터 가져오기
            all_data = collection.get(include=["metadatas", "documents", "embeddings"])

            migrated_count = 0
            skipped_count = 0

            for idx, (chunk_id, metadata, document) in enumerate(
                zip(all_data['ids'], all_data['metadatas'], all_data['documents'])
            ):
                # 이미 UnifiedChunk 형식인지 확인
                if "data_source" in metadata:
                    skipped_count += 1
                    if idx < 3:  # 처음 3개만 출력
                        print(f"⏭️  [{idx+1}/{total_count}] {chunk_id}: 이미 UnifiedChunk 형식 (스킵)")
                    continue

                if not dry_run:
                    # FileChunk 메타데이터를 UnifiedChunk 형식으로 변환
                    new_metadata = self._convert_metadata_to_unified(metadata, document)

                    # 기존 데이터 삭제 후 새 형식으로 저장
                    collection.delete(ids=[chunk_id])
                    collection.add(
                        ids=[chunk_id],
                        documents=[document],
                        metadatas=[new_metadata]
                    )

                migrated_count += 1

                # 진행상황 출력 (처음 10개 + 10개마다)
                if idx < 10 or (idx + 1) % 10 == 0:
                    print(f"✅ [{idx+1}/{total_count}] {chunk_id}: 마이그레이션 {'예정' if dry_run else '완료'}")

            print(f"\n📊 마이그레이션 결과:")
            print(f"   ✅ 마이그레이션: {migrated_count}개")
            print(f"   ⏭️  스킵: {skipped_count}개")
            print(f"   📦 총계: {total_count}개")

            return {
                "success": True,
                "migrated_count": migrated_count,
                "skipped_count": skipped_count,
                "total_count": total_count
            }

        except Exception as e:
            print(f"❌ 마이그레이션 실패: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def _convert_metadata_to_unified(self, old_metadata: Dict[str, Any], document: str) -> Dict[str, Any]:
        """
        FileChunk 메타데이터를 UnifiedChunk 메타데이터로 변환

        Args:
            old_metadata: 기존 FileChunk 메타데이터
            document: 문서 텍스트

        Returns:
            UnifiedChunk 메타데이터
        """
        now = datetime.now().isoformat()

        # file_metadata 구성
        file_metadata = {
            "file_name": old_metadata.get("file_name", ""),
            "file_hash": old_metadata.get("file_hash", ""),
            "file_type": old_metadata.get("file_type", ""),
            "file_size": len(document.encode('utf-8')),
            "architecture": old_metadata.get("architecture", ""),
            "processing_method": old_metadata.get("processing_method", ""),
            "vision_analysis": old_metadata.get("vision_analysis", False),
            "processing_duration": old_metadata.get("processing_duration", 0.0),
            "section_title": old_metadata.get("section_title", ""),
            "page_number": old_metadata.get("page_number", 1),
            "element_count": old_metadata.get("element_count", 0),
            "elements": []  # elements는 크기 제한으로 저장하지 않음
        }

        # 새 메타데이터 구성 (UnifiedChunk 형식)
        new_metadata = {
            # 공통 필드
            "chunk_id": old_metadata.get("chunk_id", ""),
            "data_source": "file",  # 현재는 항상 "file"
            "created_at": old_metadata.get("created_at", now),
            "updated_at": now,

            # 주요 필드 (검색 편의성)
            "file_name": file_metadata["file_name"],
            "file_type": file_metadata["file_type"],
            "file_hash": file_metadata["file_hash"],
            "page_number": file_metadata["page_number"],
            "architecture": file_metadata["architecture"],
            "processing_method": file_metadata["processing_method"],
            "vision_analysis": file_metadata["vision_analysis"],
            "section_title": file_metadata["section_title"],
            "element_count": file_metadata["element_count"],

            # 전체 file_metadata (JSON)
            "file_metadata_json": json.dumps(file_metadata, ensure_ascii=False),

            # jira_metadata (현재는 None)
            "jira_metadata_json": None
        }

        return new_metadata

    def rollback(self) -> bool:
        """
        백업에서 복원 (롤백)

        Returns:
            성공 여부
        """
        print("\n" + "=" * 60)
        print("🔄 백업에서 복원 (롤백)")
        print("=" * 60)

        # 가장 최근 백업 찾기
        backup_dirs = [
            d for d in os.listdir(os.path.dirname(self.db_path) or ".")
            if d.startswith("vector_db_backup_")
        ]

        if not backup_dirs:
            print("❌ 백업을 찾을 수 없습니다.")
            return False

        latest_backup = sorted(backup_dirs)[-1]
        backup_full_path = os.path.join(os.path.dirname(self.db_path) or ".", latest_backup)

        print(f"📁 복원할 백업: {backup_full_path}")

        try:
            # 현재 DB 삭제
            if os.path.exists(self.db_path):
                print(f"🗑️  현재 DB 삭제: {self.db_path}")
                shutil.rmtree(self.db_path)

            # 백업 복원
            print(f"📦 백업 복원 중...")
            shutil.copytree(backup_full_path, self.db_path)
            print(f"✅ 복원 완료!")
            return True

        except Exception as e:
            print(f"❌ 롤백 실패: {e}")
            return False


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="FileChunk → UnifiedChunk 마이그레이션 스크립트"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 실행하지 않고 계획만 출력"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="마이그레이션 전 백업 생성"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="마이그레이션 실행"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="백업에서 복원 (롤백)"
    )
    parser.add_argument(
        "--db-path",
        default="./vector_db",
        help="ChromaDB 경로 (기본값: ./vector_db)"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🤖 FileChunk → UnifiedChunk 마이그레이션 도구")
    print("=" * 60)

    migrator = FileChunkMigrator(db_path=args.db_path)

    # 롤백 요청
    if args.rollback:
        success = migrator.rollback()
        sys.exit(0 if success else 1)

    # 현재 데이터 분석
    analysis = migrator.analyze_current_data()

    if not analysis.get("needs_migration", False):
        print("\n✅ 마이그레이션이 필요 없습니다.")
        sys.exit(0)

    # Dry-run
    if args.dry_run:
        migrator.migrate_data(dry_run=True)
        print("\n💡 실제 마이그레이션을 실행하려면 --backup --execute 옵션을 사용하세요.")
        sys.exit(0)

    # 실행 (백업 옵션 확인)
    if args.execute:
        if args.backup:
            if not migrator.backup_database():
                print("\n❌ 백업 실패로 마이그레이션을 중단합니다.")
                sys.exit(1)

        result = migrator.migrate_data(dry_run=False)

        if result["success"]:
            print("\n✅ 마이그레이션 완료!")
            sys.exit(0)
        else:
            print("\n❌ 마이그레이션 실패!")
            if args.backup:
                print("💡 --rollback 옵션으로 백업에서 복원할 수 있습니다.")
            sys.exit(1)

    # 옵션이 없으면 사용법 출력
    else:
        print("\n💡 사용법:")
        print("   1. Dry-run (계획 확인):    python scripts/migrate_filechunk_to_unified.py --dry-run")
        print("   2. 백업 후 실행:           python scripts/migrate_filechunk_to_unified.py --backup --execute")
        print("   3. 롤백:                   python scripts/migrate_filechunk_to_unified.py --rollback")
        sys.exit(0)


if __name__ == "__main__":
    main()
