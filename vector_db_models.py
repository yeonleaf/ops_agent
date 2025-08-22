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