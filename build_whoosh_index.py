#!/usr/bin/env python3
"""
Whoosh 인덱스 생성 스크립트
모든 문서를 디스크 기반 인덱스로 구축하여 메모리 효율적인 키워드 검색을 지원
"""

import os
import logging
from typing import List, Dict, Any
from whoosh import index
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
from whoosh.analysis import StandardAnalyzer
from vector_db_models import VectorDBManager
from text_preprocessor import preprocess_for_embedding

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhooshIndexBuilder:
    """Whoosh 인덱스 빌더"""
    
    def __init__(self, index_dir: str = "whoosh_index"):
        self.index_dir = index_dir
        self.schema = Schema(
            id=ID(stored=True, unique=True),
            content=TEXT(analyzer=StandardAnalyzer(), stored=True),
            source_type=TEXT(stored=True),
            metadata=TEXT(stored=True)
        )
        self.vector_db_manager = VectorDBManager()
        
    def create_index(self):
        """인덱스 디렉토리 생성 및 초기화"""
        try:
            if not os.path.exists(self.index_dir):
                os.makedirs(self.index_dir)
                logger.info(f"✅ 인덱스 디렉토리 생성: {self.index_dir}")
            
            # 기존 인덱스가 있으면 삭제
            if index.exists_in(self.index_dir):
                index.create_in(self.index_dir, self.schema)
                logger.info("✅ 기존 인덱스 삭제 후 새로 생성")
            else:
                index.create_in(self.index_dir, self.schema)
                logger.info("✅ 새 인덱스 생성")
                
        except Exception as e:
            logger.error(f"❌ 인덱스 생성 실패: {e}")
            raise
    
    def add_documents_batch(self, documents: List[Dict[str, Any]], batch_size: int = 100):
        """문서들을 배치 단위로 인덱스에 추가"""
        try:
            ix = index.open_dir(self.index_dir)
            writer = ix.writer()
            
            total_added = 0
            for i, doc in enumerate(documents):
                try:
                    # 문서 내용 전처리
                    content = doc.get('content', '')
                    if not content or len(content.strip()) == 0:
                        continue
                    
                    # 텍스트 전처리 적용
                    processed_content = preprocess_for_embedding(content)
                    
                    # 메타데이터 직렬화
                    metadata = doc.get('metadata', {})
                    metadata_str = str(metadata) if metadata else ""
                    
                    # 문서 ID 생성
                    doc_id = doc.get('chunk_id', doc.get('message_id', f"doc_{i}"))
                    
                    # 인덱스에 문서 추가
                    writer.add_document(
                        id=doc_id,
                        content=processed_content,
                        source_type=doc.get('source_type', 'unknown'),
                        metadata=metadata_str
                    )
                    
                    total_added += 1
                    
                    # 배치 단위로 커밋
                    if total_added % batch_size == 0:
                        writer.commit()
                        writer = ix.writer()
                        logger.info(f"📝 {total_added}개 문서 인덱싱 완료")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 문서 {i} 인덱싱 실패: {e}")
                    continue
            
            # 마지막 배치 커밋
            writer.commit()
            logger.info(f"✅ 총 {total_added}개 문서 인덱싱 완료")
            
        except Exception as e:
            logger.error(f"❌ 배치 인덱싱 실패: {e}")
            raise
    
    def collect_all_documents(self) -> List[Dict[str, Any]]:
        """모든 문서 수집 (메모리 효율적으로)"""
        all_documents = []
        
        try:
            logger.info("📚 문서 수집 시작...")
            
            # 1. 파일 청크 문서 수집
            logger.info("📄 파일 청크 문서 수집 중...")
            file_chunks = self.vector_db_manager.get_all_file_chunks()
            for chunk in file_chunks:
                chunk['source_type'] = 'file_chunk'
                all_documents.append(chunk)
            logger.info(f"✅ 파일 청크 문서 {len(file_chunks)}개 수집")
            
            # 2. 메일 문서 수집
            logger.info("📧 메일 문서 수집 중...")
            mails = self.vector_db_manager.get_all_mails()
            for mail in mails:
                mail['source_type'] = 'mail'
                all_documents.append(mail)
            logger.info(f"✅ 메일 문서 {len(mails)}개 수집")
            
            # 3. 구조적 청크 문서 수집
            logger.info("🏗️ 구조적 청크 문서 수집 중...")
            structured_chunks = self.vector_db_manager.get_all_structured_chunks()
            for chunk in structured_chunks:
                chunk['source_type'] = 'structured_chunk'
                all_documents.append(chunk)
            logger.info(f"✅ 구조적 청크 문서 {len(structured_chunks)}개 수집")
            
            logger.info(f"✅ 총 {len(all_documents)}개 문서 수집 완료")
            return all_documents
            
        except Exception as e:
            logger.error(f"❌ 문서 수집 실패: {e}")
            return []
    
    def build_index(self):
        """전체 인덱스 구축 프로세스"""
        try:
            logger.info("🚀 Whoosh 인덱스 구축 시작...")
            
            # 1. 인덱스 생성
            self.create_index()
            
            # 2. 문서 수집
            documents = self.collect_all_documents()
            if not documents:
                logger.warning("⚠️ 수집된 문서가 없습니다.")
                return
            
            # 3. 배치 단위로 인덱싱
            self.add_documents_batch(documents, batch_size=50)
            
            logger.info("🎉 Whoosh 인덱스 구축 완료!")
            
        except Exception as e:
            logger.error(f"❌ 인덱스 구축 실패: {e}")
            raise

def main():
    """메인 실행 함수"""
    try:
        builder = WhooshIndexBuilder()
        builder.build_index()
        
        # 인덱스 정보 출력
        if index.exists_in("whoosh_index"):
            ix = index.open_dir("whoosh_index")
            with ix.searcher() as searcher:
                doc_count = searcher.doc_count()
                logger.info(f"📊 인덱스 통계: {doc_count}개 문서")
        
    except Exception as e:
        logger.error(f"❌ 메인 실행 실패: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
