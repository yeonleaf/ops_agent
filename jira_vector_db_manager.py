#!/usr/bin/env python3
"""
Jira 전문화된 청크를 Vector DB에 저장하는 관리자
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import chromadb
from chromadb.config import Settings

from jira_chunk_models import JiraChunk, JiraTicketChunks, JiraChunkType
from jira_chunk_processor import JiraChunkProcessor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JiraVectorDBManager:
    """Jira 전문화된 청크를 Vector DB에 저장하는 관리자"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """
        초기화
        
        Args:
            db_path: Vector DB 저장 경로
        """
        self.db_path = db_path
        self.collection_name = "jira_specialized_chunks"
        
        # Vector DB 폴더 생성 및 권한 설정
        if not os.path.exists(db_path):
            os.makedirs(db_path, mode=0o755, exist_ok=True)
            logger.info(f"✅ Vector DB 폴더 생성 및 권한 설정: {db_path}")
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 컬렉션 생성 또는 가져오기
        self.collection = self._get_or_create_collection()
        
        # ChromaDB 파일 권한 자동 설정
        self._set_chroma_permissions()
        
        logger.info(f"Jira Vector DB 관리자 초기화 완료: {db_path}")
    
    def _get_or_create_collection(self):
        """컬렉션 생성 또는 가져오기"""
        try:
            # 기존 컬렉션 가져오기 시도
            collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"기존 컬렉션 사용: {self.collection_name}")
            return collection
        except Exception:
            # 컬렉션이 없으면 새로 생성
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Jira 전문화된 청크 컬렉션"}
            )
            logger.info(f"새 컬렉션 생성: {self.collection_name}")
            return collection
    
    def _set_chroma_permissions(self):
        """ChromaDB 파일 권한 설정"""
        try:
            chroma_file = os.path.join(self.db_path, "chroma.sqlite3")
            if os.path.exists(chroma_file):
                os.chmod(chroma_file, 0o666)
                logger.info(f"✅ ChromaDB 파일 권한 자동 설정: {chroma_file}")
        except Exception as e:
            logger.warning(f"ChromaDB 파일 권한 설정 실패: {e}")
    
    def store_jira_chunks(self, ticket_chunks_list: List[JiraTicketChunks]) -> int:
        """
        Jira 청크들을 Vector DB에 저장
        
        Args:
            ticket_chunks_list: 티켓별 청크 리스트
            
        Returns:
            저장된 청크 수
        """
        logger.info(f"Jira 청크들을 Vector DB에 저장 시작...")
        
        total_stored = 0
        
        for ticket_chunks in ticket_chunks_list:
            try:
                stored_count = self._store_ticket_chunks(ticket_chunks)
                total_stored += stored_count
                logger.info(f"티켓 {ticket_chunks.ticket_id}: {stored_count}개 청크 저장 완료")
                
            except Exception as e:
                logger.error(f"티켓 {ticket_chunks.ticket_id} 저장 실패: {e}")
                continue
        
        logger.info(f"Jira 청크 저장 완료: 총 {total_stored}개 청크")
        return total_stored
    
    def _store_ticket_chunks(self, ticket_chunks: JiraTicketChunks) -> int:
        """하나의 티켓 청크들을 저장"""
        if not ticket_chunks.chunks:
            return 0
        
        # 청크 데이터 준비
        chunk_data = []
        metadatas = []
        ids = []
        
        for chunk in ticket_chunks.chunks:
            # 청크 ID
            chunk_id = chunk.chunk_id
            ids.append(chunk_id)
            
            # 청크 내용 (임베딩할 텍스트)
            chunk_data.append(chunk.content)
            
            # 메타데이터
            metadata = chunk.to_vector_db_dict()
            metadatas.append(metadata)
        
        # Vector DB에 저장
        self.collection.add(
            documents=chunk_data,
            metadatas=metadatas,
            ids=ids
        )
        
        return len(chunk_data)
    
    def search_jira_chunks(self, 
                          query: str, 
                          chunk_types: Optional[List[JiraChunkType]] = None,
                          ticket_ids: Optional[List[str]] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        Jira 청크 검색
        
        Args:
            query: 검색 쿼리
            chunk_types: 검색할 청크 타입들
            ticket_ids: 검색할 티켓 ID들
            limit: 결과 개수 제한
            
        Returns:
            검색 결과 리스트
        """
        logger.info(f"Jira 청크 검색: '{query}'")
        
        # 검색 필터 구성
        where_filter = {}
        
        if chunk_types:
            chunk_type_values = [ct.value for ct in chunk_types]
            where_filter["chunk_type"] = {"$in": chunk_type_values}
        
        if ticket_ids:
            where_filter["ticket_id"] = {"$in": ticket_ids}
        
        # 검색 실행
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_filter if where_filter else None
            )
            
            # 결과 정리
            search_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    result = {
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {},
                        'distance': results['distances'][0][i] if results['distances'] and results['distances'][0] else 0.0,
                        'id': results['ids'][0][i] if results['ids'] and results['ids'][0] else None
                    }
                    search_results.append(result)
            
            logger.info(f"검색 결과: {len(search_results)}개")
            return search_results
            
        except Exception as e:
            logger.error(f"검색 실패: {e}")
            return []
    
    def search_by_ticket_id(self, ticket_id: str) -> List[Dict[str, Any]]:
        """특정 티켓의 모든 청크 검색"""
        return self.search_jira_chunks(
            query="",  # 빈 쿼리로 모든 청크 검색
            ticket_ids=[ticket_id],
            limit=100
        )
    
    def search_summary_chunks(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """요약 청크만 검색"""
        return self.search_jira_chunks(
            query=query,
            chunk_types=[JiraChunkType.SUMMARY],
            limit=limit
        )
    
    def search_description_chunks(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """설명 청크만 검색"""
        return self.search_jira_chunks(
            query=query,
            chunk_types=[JiraChunkType.DESCRIPTION],
            limit=limit
        )
    
    def search_comment_chunks(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """댓글 청크만 검색"""
        return self.search_jira_chunks(
            query=query,
            chunk_types=[JiraChunkType.COMMENT],
            limit=limit
        )
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 정보"""
        try:
            count = self.collection.count()
            
            # 청크 타입별 통계
            chunk_type_stats = {}
            for chunk_type in JiraChunkType:
                results = self.collection.query(
                    query_texts=[""],
                    n_results=1000,
                    where={"chunk_type": chunk_type.value}
                )
                chunk_type_stats[chunk_type.value] = len(results['ids'][0]) if results['ids'] and results['ids'][0] else 0
            
            stats = {
                "total_chunks": count,
                "chunk_type_distribution": chunk_type_stats,
                "collection_name": self.collection_name,
                "db_path": self.db_path
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
    
    def clear_collection(self):
        """컬렉션 초기화"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            logger.info(f"컬렉션 초기화 완료: {self.collection_name}")
        except Exception as e:
            logger.error(f"컬렉션 초기화 실패: {e}")
    
    def export_chunks_to_json(self, output_file: str):
        """모든 청크를 JSON 파일로 내보내기"""
        logger.info(f"청크들을 JSON 파일로 내보내기: {output_file}")
        
        try:
            # 모든 청크 조회
            results = self.collection.query(
                query_texts=[""],
                n_results=10000  # 충분히 큰 수
            )
            
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_chunks": len(results['ids'][0]) if results['ids'] and results['ids'][0] else 0,
                "chunks": []
            }
            
            if results['ids'] and results['ids'][0]:
                for i, chunk_id in enumerate(results['ids'][0]):
                    chunk_data = {
                        "id": chunk_id,
                        "content": results['documents'][0][i] if results['documents'] and results['documents'][0] else "",
                        "metadata": results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
                    }
                    export_data["chunks"].append(chunk_data)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON 파일 내보내기 완료: {output_file}")
            
        except Exception as e:
            logger.error(f"JSON 파일 내보내기 실패: {e}")


def main():
    """테스트용 메인 함수"""
    # 샘플 CSV 파일로 테스트
    csv_file = "/Users/a11479/Desktop/code/ops_agent/sample_jira_tickets.csv"
    
    if not os.path.exists(csv_file):
        print(f"CSV 파일이 존재하지 않습니다: {csv_file}")
        return
    
    try:
        # 1. Jira 청크 프로세서로 CSV 처리
        print("=== 1단계: Jira CSV 파일 처리 ===")
        processor = JiraChunkProcessor(enable_text_cleaning=True)
        ticket_chunks_list = processor.process_csv_file(csv_file)
        
        # 2. Vector DB 관리자로 저장
        print("\n=== 2단계: Vector DB에 저장 ===")
        vector_db = JiraVectorDBManager()
        
        # 기존 데이터 초기화 (테스트용)
        vector_db.clear_collection()
        
        # 청크들 저장
        stored_count = vector_db.store_jira_chunks(ticket_chunks_list)
        print(f"저장된 청크 수: {stored_count}")
        
        # 3. 통계 정보 출력
        print("\n=== 3단계: 통계 정보 ===")
        stats = vector_db.get_collection_stats()
        print(f"총 청크 수: {stats.get('total_chunks', 0)}")
        print("청크 타입별 분포:")
        for chunk_type, count in stats.get('chunk_type_distribution', {}).items():
            print(f"  - {chunk_type}: {count}개")
        
        # 4. 검색 테스트
        print("\n=== 4단계: 검색 테스트 ===")
        
        # 요약 청크 검색
        summary_results = vector_db.search_summary_chunks("서버 접속", limit=3)
        print(f"요약 청크 검색 결과: {len(summary_results)}개")
        for result in summary_results:
            print(f"  - {result['metadata'].get('ticket_id', '')}: {result['content'][:50]}...")
        
        # 설명 청크 검색
        description_results = vector_db.search_description_chunks("HTTP 500", limit=3)
        print(f"설명 청크 검색 결과: {len(description_results)}개")
        for result in description_results:
            print(f"  - {result['metadata'].get('ticket_id', '')}: {result['content'][:50]}...")
        
        # 5. JSON 내보내기
        print("\n=== 5단계: JSON 내보내기 ===")
        export_file = "/Users/a11479/Desktop/code/ops_agent/jira_chunks_export.json"
        vector_db.export_chunks_to_json(export_file)
        print(f"JSON 파일 내보내기 완료: {export_file}")
        
    except Exception as e:
        print(f"처리 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
