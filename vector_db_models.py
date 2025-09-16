#!/usr/bin/env python3
"""
Vector DB용 Mail 모델 및 관리자
"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import chromadb
from chromadb.config import Settings
import json
from chromadb_singleton import get_chromadb_client, get_chromadb_collection, reset_chromadb_singleton

# 텍스트 전처리 모듈 import
from text_preprocessor import preprocess_for_embedding

# 환경 변수 로드
load_dotenv()

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
    file_size: int  # 파일 크기 (바이트)
    processing_duration: float  # 처리 시간 (초)

@dataclass
class StructuredChunk:
    """구조적 청크 모델 - Vector DB Collection용"""
    chunk_id: str  # PK - 고유 청크 ID
    content: str  # 임베딩할 텍스트 내용
    chunk_type: str  # 'header', 'comment'
    ticket_id: str  # 티켓 ID
    field_name: str  # 필드명
    field_value: str  # 필드값
    priority: int  # 우선순위 (1: 높음, 2: 중간, 3: 낮음)
    file_name: str  # 원본 파일명
    file_type: str  # 파일 타입
    metadata: Dict[str, Any]  # 추가 메타데이터
    created_at: str  # 생성 시각
    commenter: Optional[str] = None  # 댓글 작성자 (comment 타입일 때만)

class VectorDBManager:
    """Vector DB 관리자 - ChromaDB 사용"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화 (싱글톤 사용)"""
        self.db_path = db_path
        
        # 싱글톤 클라이언트 사용
        try:
            self.client = get_chromadb_client()
            print("✅ ChromaDB 싱글톤 클라이언트 사용")
        except Exception as e:
            print(f"⚠️ ChromaDB 싱글톤 클라이언트 실패, 재설정 시도: {e}")
            try:
                reset_chromadb_singleton()
                self.client = get_chromadb_client()
                print("✅ ChromaDB 싱글톤 재설정 후 성공")
            except Exception as e2:
                print(f"❌ ChromaDB 싱글톤 재설정 실패: {e2}")
                raise e2
        
        self.collection_name = "mail_collection"
        self.collection = self._get_or_create_collection()
        
        # ChromaDB 파일 권한 자동 설정
        try:
            chroma_file = os.path.join(db_path, "chroma.sqlite3")
            if os.path.exists(chroma_file):
                os.chmod(chroma_file, 0o666)
                print(f"✅ ChromaDB 파일 권한 자동 설정: {chroma_file}")
        except Exception as e:
            print(f"⚠️ ChromaDB 파일 권한 설정 실패: {e}")
    
    def _ensure_vector_db_permissions(self):
        """Vector DB 폴더 및 파일 권한을 확실히 설정"""
        try:
            import os
            
            # Vector DB 폴더 권한 설정 (초기화 시 설정한 경로 사용)
            vector_db_path = "./vector_db"
            if os.path.exists(vector_db_path):
                os.chmod(vector_db_path, 0o755)
            
            # ChromaDB 관련 모든 파일 권한 설정
            for root, dirs, files in os.walk(vector_db_path):
                # 폴더 권한 설정
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.chmod(dir_path, 0o755)
                    except Exception:
                        pass
                
                # 파일 권한 설정
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    try:
                        os.chmod(file_path, 0o666)
                    except Exception:
                        pass
            
            print(f"✅ Vector DB 권한 재설정 완료: {vector_db_path}")
            
        except Exception as e:
            print(f"⚠️ Vector DB 권한 재설정 실패: {e}")
    
    def _get_or_create_collection(self, collection_name: str = None):
        """컬렉션 생성 또는 가져오기"""
        if collection_name is None:
            collection_name = self.collection_name
        
        try:
            return self.client.get_collection(name=collection_name)
        except Exception:
            return self.client.create_collection(
                name=collection_name,
                metadata={
                    "description": f"Collection for {collection_name}",
                    "created_at": datetime.now().isoformat()
                }
            )
    
    def save_mail(self, mail: Mail) -> bool:
        """메일을 Vector DB에 저장 (상세 로그 포함)"""
        print(f"\n💾 [VectorDB] 메일 저장 시작: {mail.message_id}")
        print(f"   📊 [VectorDB] 저장할 메일 정보:")
        print(f"      - 제목: {mail.subject}")
        print(f"      - 발신자: {mail.sender}")
        print(f"      - original_content 길이: {len(mail.original_content)} 문자")
        print(f"      - refined_content 길이: {len(mail.refined_content)} 문자")

        try:
            # 저장 전 Vector DB 폴더 및 파일 권한 재설정
            self._ensure_vector_db_permissions()

            # ChromaDB 파일 권한 특별 확인
            import os
            import stat
            chroma_file = os.path.join("./vector_db", "chroma.sqlite3")
            if os.path.exists(chroma_file):
                # 현재 권한 확인
                current_perms = os.stat(chroma_file).st_mode
                if not (current_perms & stat.S_IWUSR):
                    print(f"⚠️ ChromaDB 파일이 읽기 전용입니다. 권한을 강제로 설정합니다.")
                    # 강제로 쓰기 권한 부여
                    os.chmod(chroma_file, 0o666)
                    # 소유자 권한도 확인
                    current_perms = os.stat(chroma_file).st_mode
                    if not (current_perms & stat.S_IWUSR):
                        os.chmod(chroma_file, current_perms | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
                    print(f"✅ ChromaDB 파일 권한 강제 설정 완료")

            # 메타데이터 준비 (datetime 객체를 문자열로 변환)
            print(f"   🏗️ [VectorDB] 메타데이터 준비 중...")
            metadata = {
                "sender": mail.sender,
                "status": mail.status,
                "subject": mail.subject,
                "received_datetime": mail.received_datetime.isoformat() if hasattr(mail.received_datetime, 'isoformat') else str(mail.received_datetime),
                "content_type": mail.content_type,
                "has_attachment": mail.has_attachment,
                "extraction_method": mail.extraction_method,
                "content_summary": mail.content_summary,
                "key_points": json.dumps(mail.key_points),
                "labels": json.dumps(mail.key_points),  # labels 필드 추가
                "created_at": mail.created_at.isoformat() if hasattr(mail.created_at, 'isoformat') else str(mail.created_at),
                "original_content": mail.original_content,  # 원본 내용 추가
                "refined_content": mail.refined_content    # 정제된 내용 추가
            }

            print(f"   ✅ [VectorDB] 메타데이터 준비 완료:")
            print(f"      - original_content in metadata: {len(metadata['original_content'])} 문자")
            print(f"      - refined_content in metadata: {len(metadata['refined_content'])} 문자")
            
            # 문서 내용 (임베딩할 텍스트)
            print(f"   📝 [VectorDB] 임베딩용 문서 텍스트 준비 중...")
            document_text = f"""
            Subject: {mail.subject}
            Sender: {mail.sender}
            Content: {mail.refined_content}
            Summary: {mail.content_summary}
            Key Points: {', '.join(mail.key_points)}
            Labels: {', '.join(mail.key_points)}
            """

            print(f"   🔧 [VectorDB] 텍스트 전처리 적용 중...")
            # 텍스트 전처리 적용
            preprocessed_document = preprocess_for_embedding(document_text)
            print(f"   ✅ [VectorDB] 전처리 완료: {len(preprocessed_document)} 문자")

            print(f"   💿 [VectorDB] ChromaDB에 저장 중... (ID: {mail.message_id})")
            # ChromaDB에 저장 (전처리된 텍스트)
            self.collection.add(
                documents=[preprocessed_document],
                metadatas=[metadata],
                ids=[mail.message_id]
            )

            print(f"   🔒 [VectorDB] 저장 후 권한 재확인 중...")
            # 저장 후 권한 재확인
            self._ensure_vector_db_permissions()

            print(f"   ✅ [VectorDB] 메일 저장 성공: {mail.message_id}")
            return True

        except Exception as e:
            print(f"   ❌ [VectorDB] 저장 오류: {e}")
            import traceback
            print(f"   📋 [VectorDB] 상세 저장 오류:")
            traceback.print_exc()
            # 오류 발생 시 권한 재설정 시도
            try:
                print(f"   🔧 [VectorDB] 오류 후 권한 재설정 시도...")
                self._ensure_vector_db_permissions()
            except:
                pass
            return False
    
    def get_mail_by_id(self, message_id: str) -> Optional[Mail]:
        """메시지 ID로 메일 조회 (상세 로그 포함)"""
        print(f"\n🔍 [VectorDB] 메일 조회 시작: {message_id}")
        try:
            print(f"   📊 [VectorDB] ChromaDB 컬렉션에서 조회 중...")
            result = self.collection.get(
                ids=[message_id],
                include=["metadatas", "documents"]
            )

            print(f"   📋 [VectorDB] 조회 결과: {len(result.get('ids', []))}개 아이템 발견")
            if not result['ids']:
                print(f"   ❌ [VectorDB] 메일을 찾을 수 없음: {message_id}")
                return None

            metadata = result['metadatas'][0]
            document = result['documents'][0]

            print(f"   ✅ [VectorDB] 메일 발견! 메타데이터 키: {list(metadata.keys())}")

            # 메타데이터에서 직접 내용 가져오기 (더 안정적)
            refined_content = metadata.get("refined_content", "")
            original_content = metadata.get("original_content", "")
            content_summary = metadata.get("content_summary", "")
            key_points_str = metadata.get("key_points", "[]")
            labels_str = metadata.get("labels", "[]")  # labels 필드 추가

            print(f"   📝 [VectorDB] 내용 길이 확인:")
            print(f"      - original_content: {len(original_content)} 문자")
            print(f"      - refined_content: {len(refined_content)} 문자")
            print(f"      - content_summary: {len(content_summary)} 문자")
            print(f"      - document: {len(document)} 문자")
            
            # key_points와 labels가 JSON 문자열인 경우 파싱
            try:
                key_points = json.loads(key_points_str) if key_points_str else []
            except (json.JSONDecodeError, TypeError):
                key_points = []
                
            try:
                labels = json.loads(labels_str) if labels_str else []
                # labels가 있으면 key_points에 병합 (레이블 우선)
                if labels:
                    key_points = labels
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            # 메타데이터에 내용이 없으면 document에서 파싱 시도
            if not refined_content:
                print(f"   🔄 [VectorDB] refined_content가 없음, document에서 파싱 시도...")
                lines = document.strip().split('\n')
                for line in lines:
                    if line.startswith("Content:"):
                        refined_content = line.replace("Content:", "").strip()
                        print(f"      📄 Document에서 Content 파싱: {len(refined_content)} 문자")
                    elif line.startswith("Summary:"):
                        content_summary = line.replace("Summary:", "").strip()
                        print(f"      📋 Document에서 Summary 파싱: {len(content_summary)} 문자")
                    elif line.startswith("Key Points:"):
                        key_points_str = line.replace("Key Points:", "").strip()
                        key_points = [kp.strip() for kp in key_points_str.split(',') if kp.strip()]
                        print(f"      🔑 Document에서 Key Points 파싱: {len(key_points)}개 포인트")

            # 최종 결과 로그
            print(f"   ✨ [VectorDB] Mail 객체 생성:")
            print(f"      - 제목: {metadata.get('subject', '제목 없음')}")
            print(f"      - 발신자: {metadata.get('sender', '발신자 불명')}")
            print(f"      - original_content 최종 길이: {len(original_content)} 문자")
            print(f"      - refined_content 최종 길이: {len(refined_content)} 문자")

            if len(original_content) == 0:
                print(f"   ⚠️ [VectorDB] 경고: original_content가 비어있습니다!")
                # 메타데이터 전체 내용 출력
                print(f"   🔍 [VectorDB] 전체 메타데이터 디버그:")
                for key, value in metadata.items():
                    value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"      - {key}: {value_preview}")

            mail_obj = Mail(
                message_id=message_id,
                original_content=original_content,
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

            print(f"   ✅ [VectorDB] Mail 객체 생성 완료!")
            return mail_obj

        except Exception as e:
            print(f"   ❌ [VectorDB] 조회 오류: {e}")
            import traceback
            print(f"   📋 [VectorDB] 상세 오류:")
            traceback.print_exc()
            return None
    
    def search_similar_mails(self, query: str, n_results: int = 5) -> List[Mail]:
        """유사한 메일 검색"""
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            results = self.collection.query(
                query_texts=[preprocessed_query],
                n_results=n_results,
                include=["metadatas", "documents", "distances"]
            )
            
            mails = []
            for i, message_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                
                # 메타데이터에서 직접 내용 가져오기 (더 안정적)
                refined_content = metadata.get("refined_content", "")
                original_content = metadata.get("original_content", "")
                content_summary = metadata.get("content_summary", "")
                key_points_str = metadata.get("key_points", "[]")
                
                # key_points가 JSON 문자열인 경우 파싱
                try:
                    key_points = json.loads(key_points_str) if key_points_str else []
                except (json.JSONDecodeError, TypeError):
                    key_points = []
                
                # 메타데이터에 내용이 없으면 document에서 파싱 시도
                if not refined_content:
                    lines = document.strip().split('\n')
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
                    original_content=original_content,
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

    def update_mail_labels(self, message_id: str, new_labels: List[str]) -> bool:
        """메일 레이블 업데이트"""
        try:
            # ChromaDB는 메타데이터 직접 업데이트를 지원하지 않으므로
            # 기존 데이터를 가져와서 삭제 후 다시 삽입
            mail = self.get_mail_by_id(message_id)
            if not mail:
                print(f"⚠️ 메일을 찾을 수 없습니다: {message_id}")
                return False
            
            # 기존 데이터 삭제
            self.collection.delete(ids=[message_id])
            
            # 레이블을 key_points에 저장 (기존 구조 유지)
            mail.key_points = new_labels
            
            # 저장 성공 여부 확인
            success = self.save_mail(mail)
            if success:
                print(f"✅ VectorDB 레이블 업데이트 성공: {message_id} -> {new_labels}")
            else:
                print(f"❌ VectorDB 레이블 업데이트 실패: {message_id}")
            
            return success
            
        except Exception as e:
            print(f"Vector DB 레이블 업데이트 오류: {e}")
            return False
    
    def search_similar_file_chunks(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """유사한 파일 청크 검색 (헤더 테이블 필터링 포함)"""
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            # file_chunks 컬렉션 가져오기
            file_chunks_collection = self.client.get_collection("file_chunks")
            
            # 더 많은 결과를 가져와서 필터링 후 원하는 개수만 반환
            results = file_chunks_collection.query(
                query_texts=[preprocessed_query],
                n_results=n_results * 3,  # 필터링을 위해 3배 더 가져오기
                include=["metadatas", "documents", "distances"]
            )
            
            file_chunks = []
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                distance = results['distances'][0][i] if results['distances'] else 0.0
                
                # 헤더 테이블 필터링 (메타데이터나 짧은 내용 제외)
                if self._is_header_table_content(document):
                    print(f"🚫 헤더 테이블 내용 필터링: {document[:50]}...")
                    continue
                
                # 유사도 점수 계산 (거리가 작을수록 유사도 높음)
                similarity_score = max(0.0, 1.0 - distance)
                
                file_chunk = {
                    "chunk_id": chunk_id,
                    "file_name": metadata.get("file_name", ""),
                    "file_type": metadata.get("file_type", ""),
                    "content": document,
                    "page_number": metadata.get("page_number", 1),
                    "element_type": metadata.get("element_type", "text"),
                    "similarity_score": similarity_score,
                    "created_at": metadata.get("created_at", "")
                }
                file_chunks.append(file_chunk)
                
                # 원하는 개수만큼 수집되면 중단
                if len(file_chunks) >= n_results:
                    break
            
            print(f"✅ 유사 파일 청크 검색 완료: {len(file_chunks)}개 결과 (헤더 테이블 필터링 적용)")
            return file_chunks
            
        except Exception as e:
            print(f"❌ 유사 파일 청크 검색 실패: {str(e)}")
            return []
    
    def _is_header_table_content(self, document: str) -> bool:
        """헤더 테이블 내용인지 판단"""
        if not document or len(document.strip()) < 10:
            return True
        
        # 헤더 테이블 관련 키워드들
        header_keywords = [
            "2025-09-07 20:31에서187이슈를 표시",
            "2025-09-07 20:32에서845이슈를 표시",
            "2025-09-07 20:26에서672이슈를 표시",
            "Jira 2025-09-07 20:26",
            "Jira 9.12.19#9120019-sha1",
            "에서 672 이슈를 표시",
            "에서 845 이슈를 표시",
            "에서 187 이슈를 표시",
            "Jira 9.12.19",
            "SK C&C] 조주연에 의해",
            "Sun Sep 07 20:26:15 KST 2025에서 생성됨",
            "에서672이슈를 표시",
            "에서845이슈를 표시",
            "에서187이슈를 표시"
        ]
        
        # 키워드 중 하나라도 포함되어 있으면 헤더 테이블로 판단
        for keyword in header_keywords:
            if keyword in document:
                return True
        
        # 너무 짧은 내용도 제외 (실제 티켓 데이터는 더 길어야 함)
        if len(document.strip()) < 50:
            return True
            
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
                
                # 메타데이터에서 직접 내용 가져오기 (더 안정적)
                refined_content = metadata.get("refined_content", "")
                original_content = metadata.get("original_content", "")
                content_summary = metadata.get("content_summary", "")
                key_points_str = metadata.get("key_points", "[]")
                
                # key_points가 JSON 문자열인 경우 파싱
                try:
                    key_points = json.loads(key_points_str) if key_points_str else []
                except (json.JSONDecodeError, TypeError):
                    key_points = []
                
                # 메타데이터에 내용이 없으면 document에서 파싱 시도
                if not refined_content:
                    lines = document.strip().split('\n')
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
                    original_content=original_content,
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
    
    def force_reset_chromadb(self):
        """ChromaDB 강제 재설정 (충돌 해결용)"""
        try:
            import shutil
            import os
            
            # 현재 클라이언트 정리
            try:
                self.client = None
            except:
                pass
            
            # vector_db 디렉토리 백업 후 삭제
            vector_db_path = "./vector_db"
            backup_path = "./vector_db_backup"
            
            if os.path.exists(vector_db_path):
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                shutil.move(vector_db_path, backup_path)
                print(f"✅ 기존 vector_db를 {backup_path}로 백업했습니다.")
            
            # 새로운 디렉토리 생성
            os.makedirs(vector_db_path, mode=0o755, exist_ok=True)
            
            # 새로운 클라이언트 생성
            self.client = chromadb.PersistentClient(
                path=vector_db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 컬렉션 재생성
            self.collection = self._get_or_create_collection()
            
            print("✅ ChromaDB 강제 재설정 완료!")
            return True
            
        except Exception as e:
            print(f"❌ ChromaDB 강제 재설정 실패: {e}")
            return False
    
    def get_file_chunks_count(self) -> int:
        """파일 청크 개수 조회"""
        try:
            collection = self.client.get_collection("file_chunks")
            count = collection.count()
            return count
        except Exception as e:
            # 컬렉션이 존재하지 않는 경우는 정상적인 상황
            if "does not exists" in str(e) or "not found" in str(e).lower():
                return 0
            print(f"파일 청크 개수 조회 실패: {e}")
            return 0
    
    def get_mails_count(self) -> int:
        """메일 데이터 개수 조회"""
        try:
            collection = self.client.get_collection("mails")
            count = collection.count()
            return count
        except Exception as e:
            # 컬렉션이 존재하지 않는 경우는 정상적인 상황
            if "does not exists" in str(e) or "not found" in str(e).lower():
                return 0
            print(f"메일 개수 조회 실패: {e}")
            return 0
    
    def add_file_chunk(self, file_chunk: FileChunk, embedding_client=None):
        """파일 청크를 벡터 DB에 추가 (ChromaDB 기본 임베딩 사용)"""
        try:
            # 파일 청크용 별도 Collection 생성 (메일 컬렉션과 분리)
            try:
                collection = self.client.get_collection(name="file_chunks")
            except Exception:
                # 새 컬렉션 생성 (ChromaDB 기본 임베딩 사용)
                collection = self.client.create_collection(
                    name="file_chunks",
                    metadata={
                        "hnsw:space": "cosine",
                        "description": "File chunks for RAG system",
                        "created_at": datetime.now().isoformat()
                    }
                )
            
            # 메타데이터 준비
            metadata = {
                "chunk_id": file_chunk.chunk_id,
                "file_name": file_chunk.file_name,
                "file_hash": file_chunk.file_hash,
                "architecture": file_chunk.architecture,
                "processing_method": file_chunk.processing_method,
                "vision_analysis": file_chunk.vision_analysis,
                "section_title": file_chunk.section_title,
                "page_number": file_chunk.page_number,
                "element_count": file_chunk.element_count,
                "file_type": file_chunk.file_type,
                "created_at": file_chunk.created_at
            }
            
            # 텍스트 전처리 적용
            preprocessed_text = preprocess_for_embedding(file_chunk.text_chunk)
            
            # ChromaDB 기본 임베딩 사용 (전처리된 텍스트)
            collection.add(
                documents=[preprocessed_text],
                metadatas=[metadata],
                ids=[file_chunk.chunk_id]
            )
            
            print(f"✅ 파일 청크 저장 완료: {file_chunk.file_name} (ID: {file_chunk.chunk_id})")
            
        except Exception as e:
            print(f"❌ 파일 청크 저장 실패: {e}")
            raise e
    
    def clear_all_data(self):
        """모든 데이터 삭제"""
        try:
            # 모든 컬렉션 삭제
            collections = self.client.list_collections()
            for collection in collections:
                self.client.delete_collection(collection.name)
                print(f"✅ 컬렉션 삭제 완료: {collection.name}")
            
            print("✅ 모든 벡터 DB 데이터가 삭제되었습니다.")
            
        except Exception as e:
            print(f"❌ 데이터 삭제 실패: {e}")
            raise e
    
    def add_structured_chunk(self, structured_chunk: StructuredChunk) -> bool:
        """
        구조적 청크를 Vector DB에 추가
        
        Args:
            structured_chunk: 구조적 청크 객체
            
        Returns:
            성공 여부
        """
        try:
            # 구조적 청크 전용 컬렉션 가져오기
            collection = self._get_or_create_structured_chunk_collection()
            
            # 메타데이터 준비
            metadata = {
                "chunk_id": structured_chunk.chunk_id,
                "chunk_type": structured_chunk.chunk_type,
                "ticket_id": structured_chunk.ticket_id,
                "field_name": structured_chunk.field_name,
                "field_value": structured_chunk.field_value,
                "priority": structured_chunk.priority,
                "file_name": structured_chunk.file_name,
                "file_type": structured_chunk.file_type,
                "created_at": structured_chunk.created_at,
                "commenter": structured_chunk.commenter or "",
                **structured_chunk.metadata
            }
            
            # ChromaDB에 추가
            collection.add(
                ids=[structured_chunk.chunk_id],
                documents=[structured_chunk.content],
                metadatas=[metadata]
            )
            
            print(f"✅ 구조적 청크 저장 완료: {structured_chunk.ticket_id} - {structured_chunk.field_name}")
            return True
            
        except Exception as e:
            print(f"❌ 구조적 청크 저장 실패: {str(e)}")
            return False
    
    def _get_or_create_structured_chunk_collection(self):
        """구조적 청크 전용 컬렉션 가져오기 또는 생성"""
        try:
            collection = self.client.get_collection("structured_chunks")
            return collection
        except:
            # 컬렉션이 없으면 생성
            collection = self.client.create_collection(
                name="structured_chunks",
                metadata={"description": "구조적 청크 컬렉션"}
            )
            print("✅ 구조적 청크 컬렉션 생성 완료")
            return collection
    
    def search_structured_chunks(self, query: str, n_results: int = 5, 
                                chunk_types: List[str] = None, 
                                ticket_ids: List[str] = None,
                                priority_filter: int = None) -> List[Dict[str, Any]]:
        """
        구조적 청크 검색
        
        Args:
            query: 검색 쿼리
            n_results: 반환할 결과 수
            chunk_types: 검색할 청크 타입 필터
            ticket_ids: 검색할 티켓 ID 필터
            priority_filter: 우선순위 필터 (1: 높음, 2: 중간, 3: 낮음)
            
        Returns:
            검색 결과 리스트
        """
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            collection = self._get_or_create_structured_chunk_collection()
            
            # 필터 조건 구성
            where_conditions = {}
            if chunk_types:
                where_conditions["chunk_type"] = {"$in": chunk_types}
            if ticket_ids:
                where_conditions["ticket_id"] = {"$in": ticket_ids}
            if priority_filter:
                where_conditions["priority"] = {"$lte": priority_filter}
            
            # ChromaDB는 단일 조건만 지원하므로 첫 번째 조건만 사용
            if len(where_conditions) > 1:
                # 우선순위: chunk_types > ticket_ids > priority_filter
                if "chunk_type" in where_conditions:
                    where_conditions = {"chunk_type": where_conditions["chunk_type"]}
                elif "ticket_id" in where_conditions:
                    where_conditions = {"ticket_id": where_conditions["ticket_id"]}
                elif "priority" in where_conditions:
                    where_conditions = {"priority": where_conditions["priority"]}
            
            # 검색 실행 (전처리된 쿼리 사용)
            results = collection.query(
                query_texts=[preprocessed_query],
                n_results=n_results,
                where=where_conditions if where_conditions else None,
                include=["metadatas", "documents", "distances"]
            )
            
            structured_chunks = []
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                distance = results['distances'][0][i] if results['distances'] else 0.0
                
                # 유사도 점수 계산
                similarity_score = max(0.0, 1.0 - distance)
                
                structured_chunk = {
                    "chunk_id": chunk_id,
                    "content": document,
                    "chunk_type": metadata.get("chunk_type", ""),
                    "ticket_id": metadata.get("ticket_id", ""),
                    "field_name": metadata.get("field_name", ""),
                    "field_value": metadata.get("field_value", ""),
                    "priority": metadata.get("priority", 3),
                    "file_name": metadata.get("file_name", ""),
                    "file_type": metadata.get("file_type", ""),
                    "similarity_score": similarity_score,
                    "created_at": metadata.get("created_at", ""),
                    "metadata": {k: v for k, v in metadata.items() 
                               if k not in ["chunk_id", "chunk_type", "ticket_id", 
                                          "field_name", "field_value", "priority", 
                                          "file_name", "file_type", "created_at"]}
                }
                structured_chunks.append(structured_chunk)
            
            print(f"✅ 구조적 청크 검색 완료: {len(structured_chunks)}개 결과")
            return structured_chunks
            
        except Exception as e:
            print(f"❌ 구조적 청크 검색 실패: {str(e)}")
            return []
    
    def get_structured_chunk_stats(self) -> Dict[str, Any]:
        """구조적 청크 통계 조회"""
        try:
            collection = self._get_or_create_structured_chunk_collection()
            count = collection.count()
            
            # 청크 타입별 통계
            all_chunks = collection.get(include=["metadatas"])
            chunk_type_stats = {}
            ticket_stats = {}
            
            for metadata in all_chunks['metadatas']:
                chunk_type = metadata.get('chunk_type', 'unknown')
                ticket_id = metadata.get('ticket_id', 'unknown')
                
                chunk_type_stats[chunk_type] = chunk_type_stats.get(chunk_type, 0) + 1
                ticket_stats[ticket_id] = ticket_stats.get(ticket_id, 0) + 1
            
            return {
                "total_chunks": count,
                "chunk_types": chunk_type_stats,
                "unique_tickets": len(ticket_stats),
                "tickets": ticket_stats
            }
            
        except Exception as e:
            print(f"❌ 구조적 청크 통계 조회 실패: {str(e)}")
            return {"total_chunks": 0, "chunk_types": {}, "unique_tickets": 0, "tickets": {}}
    
    # ==================== 하이브리드 검색을 위한 문서 수집 메서드들 ====================
    
    def get_all_file_chunks(self) -> List[Dict[str, Any]]:
        """모든 파일 청크 데이터 반환"""
        try:
            # file_chunks 컬렉션에서 모든 데이터 가져오기
            file_chunks_collection = self._get_or_create_collection("file_chunks")
            results = file_chunks_collection.get(include=["metadatas", "documents"])
            
            file_chunks = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    file_chunks.append({
                        'chunk_id': metadata.get('chunk_id', f'chunk_{i}'),
                        'file_name': metadata.get('file_name', ''),
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': 0.0  # 기본값
                    })
            
            return file_chunks
            
        except Exception as e:
            print(f"파일 청크 수집 실패: {e}")
            return []
    
    def get_all_mails(self) -> List[Dict[str, Any]]:
        """모든 메일 데이터 반환"""
        try:
            # mail_collection에서 모든 데이터 가져오기
            results = self.collection.get(include=["metadatas", "documents"])
            
            mails = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    mails.append({
                        'message_id': metadata.get('message_id', f'mail_{i}'),
                        'subject': metadata.get('subject', ''),
                        'sender': metadata.get('sender', ''),
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': 0.0  # 기본값
                    })
            
            return mails
            
        except Exception as e:
            print(f"메일 수집 실패: {e}")
            return []
    
    def get_all_structured_chunks(self) -> List[Dict[str, Any]]:
        """모든 구조적 청크 데이터 반환"""
        try:
            # structured_chunks 컬렉션에서 모든 데이터 가져오기
            structured_collection = self._get_or_create_collection("structured_chunks")
            results = structured_collection.get(include=["metadatas", "documents"])
            
            structured_chunks = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    structured_chunks.append({
                        'chunk_id': metadata.get('chunk_id', f'structured_{i}'),
                        'ticket_id': metadata.get('ticket_id', ''),
                        'chunk_type': metadata.get('chunk_type', ''),
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': 0.0  # 기본값
                    })
            
            return structured_chunks
            
        except Exception as e:
            print(f"구조적 청크 수집 실패: {e}")
            return []
    
    def get_all_documents_for_hybrid_search(self) -> List[Dict[str, Any]]:
        """하이브리드 검색을 위한 모든 문서 통합 반환"""
        try:
            all_documents = []
            
            # 파일 청크 추가
            file_chunks = self.get_all_file_chunks()
            for chunk in file_chunks:
                chunk['source_type'] = 'file_chunk'
                all_documents.append(chunk)
            
            # 메일 추가
            mails = self.get_all_mails()
            for mail in mails:
                mail['source_type'] = 'mail'
                all_documents.append(mail)
            
            # 구조적 청크 추가
            structured_chunks = self.get_all_structured_chunks()
            for chunk in structured_chunks:
                chunk['source_type'] = 'structured_chunk'
                all_documents.append(chunk)
            
            print(f"✅ 하이브리드 검색용 문서 수집 완료: {len(all_documents)}개")
            return all_documents
            
        except Exception as e:
            print(f"하이브리드 검색용 문서 수집 실패: {e}")
            return []

class UserActionVectorDBManager:
    """사용자 액션 저장용 Vector DB 관리자 - ChromaDB 사용 (장기 기억)"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화"""
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection_name = "user_action"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """user_action 컬렉션 생성 또는 가져오기"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except Exception:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "description": "User actions and AI decisions for long-term memory",
                    "created_at": datetime.now().isoformat(),
                    "type": "memory_actions"
                }
            )
    
    def save_action_memory(self, action_id: str, memory_sentence: str, 
                          action_type: str, ticket_id: Optional[int] = None, 
                          message_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """액션 기억을 Vector DB에 저장"""
        try:
            # 메타데이터 준비
            metadata = {
                "action_type": action_type,
                "ticket_id": ticket_id,
                "message_id": message_id,
                "user_id": user_id or "ai_system",
                "created_at": datetime.now().isoformat()
            }
            
            # ChromaDB에 저장 (memory_sentence가 임베딩될 텍스트)
            self.collection.add(
                documents=[memory_sentence],
                metadatas=[metadata],
                ids=[action_id]
            )
            
            return True
            
        except Exception as e:
            print(f"사용자 액션 Vector DB 저장 오류: {e}")
            return False
    
    def search_similar_actions(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """유사한 과거 액션들을 검색 (AI 결정 + 사용자 피드백 모두 포함)"""
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            results = self.collection.query(
                query_texts=[preprocessed_query],
                n_results=n_results,
                include=["metadatas", "documents", "distances"]
            )
            
            actions = []
            for i, action_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                memory_sentence = results['documents'][0][i]
                distance = results['distances'][0][i] if 'distances' in results else None
                
                actions.append({
                    "action_id": action_id,
                    "memory_sentence": memory_sentence,
                    "action_type": metadata.get('action_type', ''),
                    "ticket_id": metadata.get('ticket_id'),
                    "message_id": metadata.get('message_id'),
                    "user_id": metadata.get('user_id', 'ai_system'),
                    "created_at": metadata.get('created_at', ''),
                    "similarity_score": 1 - distance if distance is not None else None
                })
            
            return actions
            
        except Exception as e:
            print(f"사용자 액션 Vector DB 검색 오류: {e}")
            return []
    
    def get_all_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """모든 액션 기억 조회 (최근 순)"""
        try:
            result = self.collection.get(
                include=["metadatas", "documents"]
            )
            
            actions = []
            for i, action_id in enumerate(result['ids']):
                metadata = result['metadatas'][i]
                memory_sentence = result['documents'][i]
                
                actions.append({
                    "action_id": action_id,
                    "memory_sentence": memory_sentence,
                    "action_type": metadata.get('action_type', ''),
                    "ticket_id": metadata.get('ticket_id'),
                    "message_id": metadata.get('message_id'),
                    "user_id": metadata.get('user_id', 'ai_system'),
                    "created_at": metadata.get('created_at', '')
                })
            
            # 생성 시간 기준 정렬 (최근 순)
            actions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return actions[:limit]
            
        except Exception as e:
            print(f"사용자 액션 Vector DB 전체 조회 오류: {e}")
            return []
    
    def reset_collection(self):
        """컬렉션 초기화"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            print(f"✅ {self.collection_name} 컬렉션이 초기화되었습니다.")
        except Exception as e:
            print(f"❌ 컬렉션 초기화 실패: {e}")

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
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            # 검색 조건 설정
            where_filter = {}
            if file_type:
                where_filter["file_type"] = file_type
            
            results = self.collection.query(
                query_texts=[preprocessed_query],
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

class JiraInfoVectorDBManager:
    """JIRA 정보 저장용 Vector DB 관리자 - ChromaDB 사용"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화"""
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection_name = "jira_info"
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """jira_info 컬렉션 생성 또는 가져오기"""
        try:
            return self.client.get_collection(name=self.collection_name)
        except Exception:
            return self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "description": "JIRA issues and knowledge base for ticket resolution",
                    "created_at": datetime.now().isoformat(),
                    "type": "jira_issues"
                }
            )
    
    def save_jira_issue(self, issue_data: Dict[str, Any]) -> bool:
        """JIRA 이슈를 Vector DB에 저장"""
        try:
            issue_key = issue_data.get('key', str(uuid.uuid4()))
            
            # 메타데이터 준비
            metadata = {
                "issue_key": issue_key,
                "summary": issue_data.get('summary', ''),
                "issue_type": issue_data.get('issue_type', ''),
                "status": issue_data.get('status', ''),
                "priority": issue_data.get('priority', ''),
                "assignee": issue_data.get('assignee', ''),
                "reporter": issue_data.get('reporter', ''),
                "project_key": issue_data.get('project_key', ''),
                "created": issue_data.get('created', ''),
                "updated": issue_data.get('updated', ''),
                "created_at": datetime.now().isoformat()
            }
            
            # 문서 내용 (임베딩할 텍스트)
            document_text = f"""
            Issue: {issue_data.get('summary', '')}
            Description: {issue_data.get('description', '')}
            Type: {issue_data.get('issue_type', '')}
            Status: {issue_data.get('status', '')}
            Priority: {issue_data.get('priority', '')}
            Assignee: {issue_data.get('assignee', '')}
            Reporter: {issue_data.get('reporter', '')}
            Project: {issue_data.get('project_key', '')}
            """
            
            # ChromaDB에 저장
            self.collection.add(
                documents=[document_text],
                metadatas=[metadata],
                ids=[issue_key]
            )
            
            return True
            
        except Exception as e:
            print(f"JIRA 이슈 Vector DB 저장 오류: {e}")
            return False
    
    def search_similar_issues(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """유사한 JIRA 이슈 검색"""
        try:
            # 쿼리 전처리 적용
            preprocessed_query = preprocess_for_embedding(query)
            
            results = self.collection.query(
                query_texts=[preprocessed_query],
                n_results=n_results,
                include=["metadatas", "documents", "distances"]
            )
            
            issues = []
            for i, issue_key in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                distance = results['distances'][0][i] if 'distances' in results else None
                
                issues.append({
                    "issue_key": issue_key,
                    "summary": metadata.get('summary', ''),
                    "description": document,
                    "issue_type": metadata.get('issue_type', ''),
                    "status": metadata.get('status', ''),
                    "priority": metadata.get('priority', ''),
                    "similarity_score": 1 - distance if distance is not None else None
                })
            
            return issues
            
        except Exception as e:
            print(f"JIRA 이슈 검색 오류: {e}")
            return []
    
    def get_all_issues(self, limit: int = 100) -> List[Dict[str, Any]]:
        """모든 JIRA 이슈 조회"""
        try:
            result = self.collection.get(
                include=["metadatas", "documents"]
            )
            
            issues = []
            for i, issue_key in enumerate(result['ids']):
                metadata = result['metadatas'][i]
                document = result['documents'][i]
                
                issues.append({
                    "issue_key": issue_key,
                    "summary": metadata.get('summary', ''),
                    "description": document,
                    "issue_type": metadata.get('issue_type', ''),
                    "status": metadata.get('status', ''),
                    "priority": metadata.get('priority', ''),
                    "assignee": metadata.get('assignee', ''),
                    "reporter": metadata.get('reporter', ''),
                    "project_key": metadata.get('project_key', ''),
                    "created": metadata.get('created', ''),
                    "updated": metadata.get('updated', '')
                })
            
            # 업데이트 시간 기준 정렬 (최근 순)
            issues.sort(key=lambda x: x.get('updated', ''), reverse=True)
            
            return issues[:limit]
            
        except Exception as e:
            print(f"JIRA 이슈 전체 조회 오류: {e}")
            return []

class AIRecommendationEngine:
    """AI 추천 해결방법 생성 엔진"""
    
    def __init__(self):
        self.system_info_db = SystemInfoVectorDBManager()
        self.jira_info_db = JiraInfoVectorDBManager()
    
    def generate_solution_recommendation(self, mail_content: str, ticket_history: str, output_placeholder=None) -> str:
        """메일 원문과 티켓 이력을 바탕으로 AI 추천 해결방법 생성 (스트리밍 버전)"""
        try:
            # 1. 관련 시스템 정보 검색
            system_context = self._search_system_info(mail_content, ticket_history)
            
            # 2. 관련 JIRA 이슈 검색
            jira_context = self._search_jira_issues(mail_content, ticket_history)
            
            # 3. AI 추천 해결방법 생성
            recommendation = self._create_ai_recommendation(
                mail_content, ticket_history, system_context, jira_context, output_placeholder
            )
            
            return recommendation
            
        except Exception as e:
            print(f"AI 추천 생성 중 오류: {e}")
            return "AI 추천 해결방법을 생성하는 중 오류가 발생했습니다."
    
    def _search_system_info(self, mail_content: str, ticket_history: str) -> List[Dict[str, Any]]:
        """시스템 정보에서 관련 내용 검색"""
        try:
            # 메일 내용과 티켓 이력을 결합하여 검색
            search_query = f"{mail_content[:200]} {ticket_history[:200]}"
            
            # system_info 컬렉션에서 유사한 청크 검색
            similar_chunks = self.system_info_db.search_similar_chunks(
                search_query, n_results=3
            )
            
            return similar_chunks
            
        except Exception as e:
            print(f"시스템 정보 검색 오류: {e}")
            return []
    
    def _search_jira_issues(self, mail_content: str, ticket_history: str) -> List[Dict[str, Any]]:
        """JIRA 이슈에서 관련 내용 검색"""
        try:
            # 메일 내용과 티켓 이력을 결합하여 검색
            search_query = f"{mail_content[:200]} {ticket_history[:200]}"
            
            # jira_info 컬렉션에서 유사한 이슈 검색
            similar_issues = self.jira_info_db.search_similar_issues(
                search_query, n_results=3
            )
            
            return similar_issues
            
        except Exception as e:
            print(f"JIRA 이슈 검색 오류: {e}")
            return []
    
    def _create_ai_recommendation(self, mail_content: str, ticket_history: str, 
                                 system_context: List[Dict[str, Any]], 
                                 jira_context: List[Dict[str, Any]], 
                                 output_placeholder=None) -> str:
        """AI 추천 해결방법 생성 - LLM 전용 (스트리밍 버전)"""
        try:
            # 컨텍스트 정보 정리
            system_info_text = ""
            if system_context:
                system_info_text = "\n\n관련 시스템 정보:\n"
                for chunk in system_context:
                    system_info_text += f"- {chunk.get('text_content', '')[:300]}...\n"
            
            jira_info_text = ""
            if jira_context:
                jira_info_text = "\n\n관련 JIRA 이슈:\n"
                for issue in jira_context:
                    jira_info_text += f"- {issue.get('summary', '')}: {issue.get('description', '')[:300]}...\n"
            
            # LLM 프롬프트 구성 (f-string 포맷팅 오류 방지)
            prompt = """
당신은 IT 운영 전문가입니다. 다음 정보를 바탕으로 구체적이고 실행 가능한 해결방법을 제시해주세요.

📧 **메일 내용:**
{mail_content}

📋 **티켓 히스토리:**
{ticket_history}

📚 **관련 시스템 정보:**
{system_info}

🎫 **관련 JIRA 이슈:**
{jira_info}

위 정보를 종합적으로 분석하여 다음 형식으로 구체적인 해결방법을 제시해주세요:

🤖 **AI 추천 해결방법**

🔍 **문제 분석:**
[메일 내용과 티켓 히스토리를 바탕으로 구체적인 문제 상황 분석]

🎯 **권장 조치:**
1. [구체적인 첫 번째 조치]
2. [구체적인 두 번째 조치]
3. [구체적인 세 번째 조치]

📚 **참고 자료 활용:**
[시스템 정보와 JIRA 이슈를 바탕으로 한 구체적인 참고사항]

💡 **추가 권장사항:**
- [맥락에 맞는 구체적인 권장사항]
- [맥락에 맞는 구체적인 권장사항]
- [맥락에 맞는 구체적인 권장사항]

⚠️ **주의사항:**
[해당 상황에서 주의해야 할 점이나 위험요소]

위 형식에 맞춰 구체적이고 실행 가능한 해결방법을 제시해주세요. 일반적인 내용이 아닌, 제공된 정보를 바탕으로 한 맥락에 맞는 구체적인 내용이어야 합니다.
"""
            
            # LLM 호출 (Azure OpenAI 사용)
            try:
                from langchain_openai import AzureChatOpenAI
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser
                
                # 환경 변수에서 Azure OpenAI 설정 가져오기
                import os
                azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
                api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
                
                if azure_endpoint and deployment_name and api_key:
                    # Azure OpenAI 클라이언트 생성
                    llm = AzureChatOpenAI(
                        azure_endpoint=azure_endpoint,
                        deployment_name=deployment_name,
                        openai_api_key=api_key,
                        openai_api_version=api_version,
                        temperature=0.3  # 창의성과 일관성의 균형
                    )
                    
                    # 프롬프트 템플릿 생성
                    prompt_template = ChatPromptTemplate.from_template(prompt)
                    
                    # 체인 실행
                    chain = prompt_template | llm | StrOutputParser()
                    
                    # 변수 매핑
                    variables = {
                        "mail_content": mail_content[:1000],
                        "ticket_history": ticket_history[:1000] if ticket_history else "없음",
                        "system_info": system_info_text if system_info_text else "관련 시스템 정보 없음",
                        "jira_info": jira_info_text if jira_info_text else "관련 JIRA 이슈 없음"
                    }
                    
                    # 스트리밍 처리
                    if output_placeholder:
                        current_output = ""
                        final_recommendation = ""
                        
                        for chunk in chain.stream(variables):
                            current_output += chunk
                            final_recommendation = current_output
                            
                            # 실시간 출력 업데이트
                            with output_placeholder.container():
                                st.markdown("### 🤖 AI 추천 생성 중...")
                                st.markdown(current_output)
                                st.info("🔄 AI 추천을 생성하고 있습니다...")
                        
                        # 최종 완료 표시
                        with output_placeholder.container():
                            st.success("✅ AI 추천 생성 완료!")
                        
                        return final_recommendation
                    else:
                        # 일반 처리 (스트리밍 없음)
                        recommendation = chain.invoke(variables)
                        return recommendation
                else:
                    # Azure OpenAI 설정이 없으면 오류 메시지 반환
                    return "❌ Azure OpenAI 설정이 없습니다. 환경 변수를 확인해주세요."
                    
            except Exception as e:
                print(f"LLM 호출 중 오류: {e}")
                return f"❌ AI 추천 생성 실패: {str(e)}"
            
        except Exception as e:
            print(f"AI 추천 생성 오류: {e}")
            return f"❌ AI 추천 생성 중 오류가 발생했습니다: {str(e)}"
    
