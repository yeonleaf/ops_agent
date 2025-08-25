#!/usr/bin/env python3
"""
Vector DB용 Mail 모델 및 관리자
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import chromadb
from chromadb.config import Settings
import json

@dataclass
class Mail:
    """메일 모델 - Vector DB Collection용"""
    message_id: str  # PK - 원본 메일 ID (연결 키)
    original_content: str  # HTML/Text 원본 내용
    refined_content: str  # 추출된 핵심 내용
    sender: str  # 보낸 사람
    status: str  # acceptable, unacceptable 등
    subject: str  # 메일 제목
    received_datetime: str  # 수신 시간
    content_type: str  # html, text
    has_attachment: bool  # 첨부파일 여부
    extraction_method: str  # 추출 방법
    content_summary: str  # 내용 요약
    key_points: List[str]  # 핵심 포인트
    created_at: str  # 생성 시각

@dataclass
class FileChunk:
    """파일 청크 모델 - Vector DB Collection용"""
    chunk_id: str  # PK - 고유 청크 ID
    file_name: str  # 원본 파일명
    file_hash: str  # 파일 해시값 (중복 방지용)
    text_chunk: str  # 임베딩할 텍스트 내용
    architecture: str  # dual_path_hybrid 또는 simple_conversion
    processing_method: str  # 처리 방법
    vision_analysis: bool  # Vision 분석 적용 여부
    section_title: str  # 섹션 제목
    page_number: int  # 페이지/슬라이드 번호
    element_count: int  # 요소 개수
    file_type: str  # pptx, docx, pdf, xlsx, txt, md, csv, scds
    elements: List[Dict[str, Any]]  # 요소별 상세 정보
    created_at: str  # 생성 시각
    file_size: int  # 파일 크기 (bytes)
    processing_duration: float  # 처리 소요 시간 (초)

class VectorDBManager:
    """Vector DB 관리자 - ChromaDB 사용"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화"""
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection_name = "mail_collection"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """컬렉션 생성 또는 가져오기"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except Exception:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "description": "Email messages for ticket generation",
                    "created_at": datetime.now().isoformat()
                }
            )
    
    def save_mail(self, mail: Mail) -> bool:
        """메일을 Vector DB에 저장"""
        try:
            # 메타데이터 준비
            metadata = {
                "sender": mail.sender,
                "status": mail.status,
                "subject": mail.subject,
                "received_datetime": mail.received_datetime,
                "content_type": mail.content_type,
                "has_attachment": mail.has_attachment,
                "extraction_method": mail.extraction_method,
                "created_at": mail.created_at
            }
            
            # 문서 내용 (임베딩할 텍스트)
            document_text = f"""
            Subject: {mail.subject}
            Sender: {mail.sender}
            Content: {mail.refined_content}
            Summary: {mail.content_summary}
            Key Points: {', '.join(mail.key_points)}
            """
            
            # ChromaDB에 저장
            self.collection.add(
                documents=[document_text],
                metadatas=[metadata],
                ids=[mail.message_id]
            )
            
            return True
            
        except Exception as e:
            print(f"Vector DB 저장 오류: {e}")
            return False
    
    def get_mail_by_id(self, message_id: str) -> Optional[Mail]:
        """메시지 ID로 메일 조회"""
        try:
            result = self.collection.get(
                ids=[message_id],
                include=["metadatas", "documents"]
            )
            
            if not result['ids']:
                return None
            
            metadata = result['metadatas'][0]
            document = result['documents'][0]
            
            # document에서 원본 내용 추출 (실제로는 더 정교한 파싱 필요)
            lines = document.strip().split('\n')
            refined_content = ""
            content_summary = ""
            key_points = []
            
            for line in lines:
                if line.startswith("Content:"):
                    refined_content = line.replace("Content:", "").strip()
                elif line.startswith("Summary:"):
                    content_summary = line.replace("Summary:", "").strip()
                elif line.startswith("Key Points:"):
                    key_points_str = line.replace("Key Points:", "").strip()
                    key_points = [kp.strip() for kp in key_points_str.split(',') if kp.strip()]
            
            return Mail(
                message_id=message_id,
                original_content="",  # Vector DB에서는 원본 내용을 별도 저장하지 않음
                refined_content=refined_content,
                sender=metadata.get("sender", ""),
                status=metadata.get("status", "acceptable"),
                subject=metadata.get("subject", ""),
                received_datetime=metadata.get("received_datetime", ""),
                content_type=metadata.get("content_type", "text"),
                has_attachment=metadata.get("has_attachment", False),
                extraction_method=metadata.get("extraction_method", ""),
                content_summary=content_summary,
                key_points=key_points,
                created_at=metadata.get("created_at", "")
            )
            
        except Exception as e:
            print(f"Vector DB 조회 오류: {e}")
            return None
    
    def search_similar_mails(self, query: str, n_results: int = 5) -> List[Mail]:
        """유사한 메일 검색"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["metadatas", "documents", "distances"]
            )
            
            mails = []
            for i, message_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                
                # 문서에서 내용 파싱
                lines = document.strip().split('\n')
                refined_content = ""
                content_summary = ""
                key_points = []
                
                for line in lines:
                    if line.startswith("Content:"):
                        refined_content = line.replace("Content:", "").strip()
                    elif line.startswith("Summary:"):
                        content_summary = line.replace("Summary:", "").strip()
                    elif line.startswith("Key Points:"):
                        key_points_str = line.replace("Key Points:", "").strip()
                        key_points = [kp.strip() for kp in key_points_str.split(',') if kp.strip()]
                
                mail = Mail(
                    message_id=message_id,
                    original_content="",
                    refined_content=refined_content,
                    sender=metadata.get("sender", ""),
                    status=metadata.get("status", "acceptable"),
                    subject=metadata.get("subject", ""),
                    received_datetime=metadata.get("received_datetime", ""),
                    content_type=metadata.get("content_type", "text"),
                    has_attachment=metadata.get("has_attachment", False),
                    extraction_method=metadata.get("extraction_method", ""),
                    content_summary=content_summary,
                    key_points=key_points,
                    created_at=metadata.get("created_at", "")
                )
                mails.append(mail)
            
            return mails
            
        except Exception as e:
            print(f"Vector DB 검색 오류: {e}")
            return []
    
    def update_mail_status(self, message_id: str, new_status: str) -> bool:
        """메일 상태 업데이트"""
        try:
            # ChromaDB는 메타데이터 직접 업데이트를 지원하지 않으므로
            # 기존 데이터를 가져와서 삭제 후 다시 삽입
            mail = self.get_mail_by_id(message_id)
            if not mail:
                return False
            
            # 기존 데이터 삭제
            self.collection.delete(ids=[message_id])
            
            # 상태 업데이트 후 다시 저장
            mail.status = new_status
            return self.save_mail(mail)
            
        except Exception as e:
            print(f"Vector DB 업데이트 오류: {e}")
            return False
    
    def get_all_mails(self, limit: int = 100) -> List[Mail]:
        """모든 메일 조회 (최근 순)"""
        try:
            # ChromaDB의 모든 데이터 조회
            result = self.collection.get(
                include=["metadatas", "documents"]
            )
            
            mails = []
            for i, message_id in enumerate(result['ids']):
                metadata = result['metadatas'][i]
                document = result['documents'][i]
                
                # 문서에서 내용 파싱
                lines = document.strip().split('\n')
                refined_content = ""
                content_summary = ""
                key_points = []
                
                for line in lines:
                    if line.startswith("Content:"):
                        refined_content = line.replace("Content:", "").strip()
                    elif line.startswith("Summary:"):
                        content_summary = line.replace("Summary:", "").strip()
                    elif line.startswith("Key Points:"):
                        key_points_str = line.replace("Key Points:", "").strip()
                        key_points = [kp.strip() for kp in key_points_str.split(',') if kp.strip()]
                
                mail = Mail(
                    message_id=message_id,
                    original_content="",
                    refined_content=refined_content,
                    sender=metadata.get("sender", ""),
                    status=metadata.get("status", "acceptable"),
                    subject=metadata.get("subject", ""),
                    received_datetime=metadata.get("received_datetime", ""),
                    content_type=metadata.get("content_type", "text"),
                    has_attachment=metadata.get("has_attachment", False),
                    extraction_method=metadata.get("extraction_method", ""),
                    content_summary=content_summary,
                    key_points=key_points,
                    created_at=metadata.get("created_at", "")
                )
                mails.append(mail)
            
            # 생성 시간 기준 정렬 (최근 순)
            mails.sort(key=lambda x: x.created_at, reverse=True)
            
            return mails[:limit]
            
        except Exception as e:
            print(f"Vector DB 전체 조회 오류: {e}")
            return []
    
    def reset_collection(self):
        """컬렉션 초기화 (개발용)"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            return True
        except Exception as e:
            print(f"컬렉션 초기화 오류: {e}")
            return False

class SystemInfoVectorDBManager:
    """시스템 정보 파일 저장용 Vector DB 관리자 - ChromaDB 사용"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화"""
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection_name = "system_info"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """system_info 컬렉션 생성 또는 가져오기"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except Exception:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "description": "System information and document chunks for knowledge base",
                    "created_at": datetime.now().isoformat(),
                    "type": "document_chunks"
                }
            )
    
    def _calculate_file_hash(self, file_content: bytes) -> str:
        """파일 내용의 SHA-256 해시 계산"""
        import hashlib
        return hashlib.sha256(file_content).hexdigest()
    
    def _is_file_already_processed(self, file_hash: str) -> bool:
        """파일이 이미 처리되었는지 확인 (해시 기반 중복 방지)"""
        try:
            # 메타데이터에서 file_hash 검색
            results = self.collection.get(
                where={"file_hash": file_hash},
                include=["metadatas"]
            )
            return len(results['ids']) > 0
        except Exception:
            return False
    
    def save_file_chunks(self, chunks: List[Dict[str, Any]], file_content: bytes, 
                        file_name: str, processing_duration: float) -> Dict[str, Any]:
        """파일 청크들을 Vector DB에 저장 (중복 방지 포함)"""
        try:
            # 파일 해시 계산
            file_hash = self._calculate_file_hash(file_content)
            
            # 중복 파일 확인
            if self._is_file_already_processed(file_hash):
                return {
                    "success": True,
                    "message": f"✅ {file_name}은 이미 처리된 파일입니다 (중복 방지)",
                    "file_hash": file_hash,
                    "duplicate": True,
                    "chunks_saved": 0
                }
            
            # 각 청크를 Vector DB에 저장
            saved_chunks = []
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                
                # 메타데이터 준비
                metadata = {
                    "file_name": file_name,
                    "file_hash": file_hash,
                    "architecture": chunk.get('metadata', {}).get('architecture', 'unknown'),
                    "processing_method": chunk.get('metadata', {}).get('processing_method', 'unknown'),
                    "vision_analysis": chunk.get('metadata', {}).get('vision_analysis', False),
                    "section_title": chunk.get('metadata', {}).get('section_title', ''),
                    "page_number": chunk.get('metadata', {}).get('page_number', 1),
                    "element_count": chunk.get('metadata', {}).get('element_count', 0),
                    "file_type": chunk.get('metadata', {}).get('file_type', 'unknown'),
                    "file_size": len(file_content),
                    "processing_duration": processing_duration,
                    "created_at": datetime.now().isoformat()
                }
                
                # 요소 정보를 JSON 문자열로 변환 (ChromaDB 메타데이터 제한)
                elements = chunk.get('metadata', {}).get('elements', [])
                if elements:
                    metadata["elements_summary"] = f"{len(elements)}개 요소: {', '.join([e.get('element_type', 'unknown') for e in elements[:5]])}"
                    if len(elements) > 5:
                        metadata["elements_summary"] += f" 외 {len(elements) - 5}개"
                
                # 텍스트 내용 (임베딩할 텍스트)
                text_content = chunk.get('text_chunk_to_embed', '')
                if not text_content:
                    text_content = f"파일: {file_name}, 아키텍처: {metadata['architecture']}, 요소: {metadata['element_count']}개"
                
                # ChromaDB에 저장
                self.collection.add(
                    documents=[text_content],
                    metadatas=[metadata],
                    ids=[chunk_id]
                )
                
                saved_chunks.append(chunk_id)
            
            return {
                "success": True,
                "message": f"✅ {file_name} 처리가 완료되어 {len(saved_chunks)}개의 청크가 system_info 컬렉션에 저장되었습니다.",
                "file_hash": file_hash,
                "duplicate": False,
                "chunks_saved": len(saved_chunks),
                "chunk_ids": saved_chunks
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ {file_name} 저장 중 오류 발생: {str(e)}"
            }
    
    def search_similar_chunks(self, query: str, n_results: int = 5, 
                             file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """유사한 청크 검색"""
        try:
            # 검색 조건 설정
            where_filter = {}
            if file_type:
                where_filter["file_type"] = file_type
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["metadatas", "documents", "distances"]
            )
            
            chunks = []
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                distance = results['distances'][0][i] if 'distances' in results else None
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "text_content": document,
                    "metadata": metadata,
                    "similarity_score": 1 - distance if distance is not None else None
                })
            
            return chunks
            
        except Exception as e:
            print(f"Vector DB 검색 오류: {e}")
            return []
    
    def get_file_chunks(self, file_name: str) -> List[Dict[str, Any]]:
        """특정 파일의 모든 청크 조회"""
        try:
            results = self.collection.get(
                where={"file_name": file_name},
                include=["metadatas", "documents"]
            )
            
            chunks = []
            for i, chunk_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                document = results['documents'][i]
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "text_content": document,
                    "metadata": metadata
                })
            
            return chunks
            
        except Exception as e:
            print(f"Vector DB 조회 오류: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 정보 조회"""
        try:
            # 전체 데이터 조회
            result = self.collection.get(include=["metadatas"])
            
            if not result['ids']:
                return {
                    "total_chunks": 0, 
                    "file_types": {}, 
                    "total_files": 0,
                    "collection_name": self.collection_name
                }
            
            # 파일 타입별 통계
            file_types = {}
            unique_files = set()
            
            for metadata in result['metadatas']:
                file_type = metadata.get('file_type', 'unknown')
                file_types[file_type] = file_types.get(file_type, 0) + 1
                
                file_name = metadata.get('file_name', '')
                if file_name:
                    unique_files.add(file_name)
            
            return {
                "total_chunks": len(result['ids']),
                "file_types": file_types,
                "total_files": len(unique_files),
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            print(f"컬렉션 통계 조회 오류: {e}")
            return {
                "error": str(e),
                "total_chunks": 0,
                "file_types": {},
                "total_files": 0,
                "collection_name": self.collection_name
            }
    
    def reset_collection(self):
        """컬렉션 초기화"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            print(f"✅ {self.collection_name} 컬렉션이 초기화되었습니다.")
        except Exception as e:
            print(f"❌ 컬렉션 초기화 실패: {e}")