#!/usr/bin/env python3
"""
manual.md를 [제목] 단위로 파싱하여 RAG 컬렉션에 추가하는 스크립트
"""

import os
import re
import sys
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class ManualChunkParser:
    """manual.md를 [제목] 단위로 파싱하는 클래스"""

    def __init__(self, manual_path: str):
        """
        초기화

        Args:
            manual_path: manual.md 파일 경로
        """
        self.manual_path = manual_path
        self.chunks = []

    def parse(self) -> List[Dict[str, Any]]:
        """
        manual.md를 [제목] 단위로 파싱

        Returns:
            청크 리스트 [{'title': '...', 'content': '...', 'metadata': {...}}, ...]
        """
        print(f"📖 {self.manual_path} 파싱 시작...")

        with open(self.manual_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # [제목] 패턴으로 분리
        # 정규식: [로 시작하고 ]로 끝나는 패턴
        pattern = r'\[([^\]]+)\]'

        # [제목]의 위치 찾기
        matches = list(re.finditer(pattern, content))

        if not matches:
            print("⚠️ [제목] 형태를 찾을 수 없습니다.")
            return []

        print(f"✅ {len(matches)}개의 [제목] 발견")

        # 각 [제목]부터 다음 [제목] 전까지를 하나의 청크로 구성
        for i, match in enumerate(matches):
            title = match.group(1).strip()  # [제목]에서 제목만 추출
            start_pos = match.start()

            # 다음 [제목]의 시작 위치 찾기
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(content)

            # 청크 내용 추출 ([제목] 포함)
            chunk_content = content[start_pos:end_pos].strip()

            # 청크가 너무 짧으면 제외 (제목만 있는 경우)
            if len(chunk_content) < 10:
                print(f"⚠️ 청크가 너무 짧아 건너뜀: [{title}]")
                continue

            # 메타데이터 구성
            metadata = {
                'source': 'manual.md',
                'doc_type': 'procedural_manual',
                'title': title,
                'chunk_index': i,
                'created_at': datetime.now().isoformat(),
                'ticket_id': f'MANUAL-{i+1:03d}',  # 평가용 임시 ID
                'is_manual': True
            }

            chunk = {
                'title': title,
                'content': chunk_content,
                'metadata': metadata
            }

            self.chunks.append(chunk)
            print(f"  {i+1}. [{title}] - {len(chunk_content)}자")

        print(f"\n✅ 파싱 완료: {len(self.chunks)}개 청크 생성")
        return self.chunks


class ManualRAGIngester:
    """manual 청크를 RAG 컬렉션에 추가하는 클래스"""

    def __init__(self, collection_name: str = "jira_chunks", db_path: str = "./vector_db"):
        """
        초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
            db_path: Vector DB 경로
        """
        self.collection_name = collection_name
        self.db_path = db_path

        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # 컬렉션 가져오기
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"✅ 기존 컬렉션 사용: {collection_name} ({self.collection.count()}개 문서)")
        except Exception as e:
            print(f"❌ 컬렉션을 찾을 수 없습니다: {e}")
            raise e

    def ingest_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        청크들을 컬렉션에 추가 (ChromaDB 기본 임베딩 사용)

        Args:
            chunks: 청크 리스트

        Returns:
            추가된 청크 수
        """
        print(f"\n📥 {len(chunks)}개 청크를 '{self.collection_name}' 컬렉션에 추가 중...")

        success_count = 0

        # 배치로 처리 (ChromaDB가 자동으로 임베딩 생성)
        try:
            # 모든 청크의 content 수집
            contents = [chunk['content'] for chunk in chunks]
            metadatas = [chunk['metadata'] for chunk in chunks]
            ids = [f"manual_{chunk['metadata']['chunk_index']:03d}_{uuid.uuid4().hex[:8]}"
                   for chunk in chunks]

            # 컬렉션에 배치 추가 (ChromaDB가 자동으로 임베딩 계산)
            print("  🔄 컬렉션에 추가 중 (ChromaDB 기본 임베딩 사용)...")
            self.collection.add(
                documents=contents,
                metadatas=metadatas,
                ids=ids
            )

            success_count = len(chunks)
            for i, chunk in enumerate(chunks, 1):
                print(f"  ✅ {i}/{len(chunks)}: [{chunk['title']}] 추가 완료 (ID: {ids[i-1]})")

        except Exception as e:
            print(f"  ❌ 배치 추가 실패: {e}")
            print("  🔄 개별 추가 시도 중...")

            # 실패 시 개별 추가
            for i, chunk in enumerate(chunks, 1):
                try:
                    # 고유 ID 생성 (manual 기반)
                    chunk_id = f"manual_{chunk['metadata']['chunk_index']:03d}_{uuid.uuid4().hex[:8]}"

                    # 컬렉션에 추가 (ChromaDB가 자동으로 임베딩 계산)
                    self.collection.add(
                        documents=[chunk['content']],
                        metadatas=[chunk['metadata']],
                        ids=[chunk_id]
                    )

                    success_count += 1
                    print(f"  ✅ {i}/{len(chunks)}: [{chunk['title']}] 추가 완료 (ID: {chunk_id})")

                except Exception as e:
                    print(f"  ❌ {i}/{len(chunks)}: [{chunk['title']}] 추가 실패 - {e}")

        print(f"\n✅ 추가 완료: {success_count}/{len(chunks)}개 청크")
        print(f"📊 현재 컬렉션 크기: {self.collection.count()}개 문서")

        return success_count

    def verify_ingestion(self, sample_query: str = "DB 마이그레이션") -> List[Dict[str, Any]]:
        """
        추가된 데이터 검증

        Args:
            sample_query: 샘플 검색 쿼리

        Returns:
            검색 결과
        """
        print(f"\n🔍 검증 쿼리: '{sample_query}'")

        results = self.collection.query(
            query_texts=[sample_query],
            n_results=5
        )

        print(f"✅ 검색 결과: {len(results['documents'][0])}개")

        formatted_results = []
        for i in range(len(results['documents'][0])):
            result = {
                'id': results['ids'][0][i],
                'content': results['documents'][0][i][:200] + "...",
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            }
            formatted_results.append(result)

            print(f"\n  {i+1}. {result['metadata'].get('title', 'N/A')}")
            print(f"     거리: {result['distance']:.4f}")
            print(f"     내용: {result['content'][:100]}...")

        return formatted_results


def main():
    """메인 실행 함수"""
    print("="*80)
    print("📚 manual.md를 RAG 컬렉션에 학습시키기")
    print("="*80)

    try:
        # 1. manual.md 파싱
        manual_path = "./manual.md"

        if not os.path.exists(manual_path):
            print(f"❌ {manual_path} 파일을 찾을 수 없습니다.")
            return

        parser = ManualChunkParser(manual_path)
        chunks = parser.parse()

        if not chunks:
            print("❌ 파싱된 청크가 없습니다.")
            return

        # 2. 컬렉션에 추가
        # evaluate_rag_system.py에서 사용하는 컬렉션 이름 확인 필요
        # 기본적으로 "jira_chunks" 사용
        ingester = ManualRAGIngester(collection_name="jira_chunks")

        success_count = ingester.ingest_chunks(chunks)

        if success_count > 0:
            # 3. 검증
            print("\n" + "="*80)
            print("🧪 추가된 데이터 검증")
            print("="*80)

            # test_data.csv의 첫 번째 쿼리로 검증
            test_queries = [
                "DB 마이그레이션",
                "배치 재기동",
                "CP사 이관"
            ]

            for query in test_queries:
                ingester.verify_ingestion(query)
                print()

        print("\n" + "="*80)
        print("✅ 모든 작업 완료!")
        print("="*80)
        print(f"📊 총 {success_count}개의 manual 청크가 컬렉션에 추가되었습니다.")
        print(f"💡 이제 evaluate_rag_system.py를 실행하여 found rate를 측정할 수 있습니다.")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
