#!/usr/bin/env python3
"""
RAG 데이터 관리자 모듈
Streamlit 앱에서 문서 업로드, 처리, 벡터 DB 저장 기능을 제공
"""

# import streamlit as st  # Streamlit 컨텍스트가 필요할 때만 import
import os
import tempfile
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

# FileProcessor import
from module.file_processor import FileProcessor, DocumentType, FileTypeDetector

# Vector DB import
from vector_db_models import VectorDBManager, FileChunk, StructuredChunk

# LangChain imports for embedding
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def create_embedding_client():
    """Embedding 클라이언트 생성 (Azure OpenAI 우선 사용)"""
    try:
        # 1. Azure OpenAI 키 확인
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-ada-002")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        
        if azure_api_key and azure_endpoint:
            print("🔧 Azure OpenAI Embedding 클라이언트 생성 시도...")
            try:
                embedding_client = AzureOpenAIEmbeddings(
                    azure_deployment=azure_deployment,
                    azure_endpoint=azure_endpoint,
                    api_key=azure_api_key,
                    api_version=azure_api_version,
                    openai_api_type="azure"
                )
                # 실제 임베딩 요청으로 배포 존재 여부 확인
                test_embedding = embedding_client.embed_query("test")
                print("✅ Azure OpenAI Embedding 클라이언트 생성 및 테스트 성공")
                return embedding_client
            except Exception as e:
                print(f"❌ Azure OpenAI Embedding 배포 오류: {e}")
                if "DeploymentNotFound" in str(e) or "404" in str(e):
                    print("⚠️ 임베딩 배포가 존재하지 않습니다. 더미 임베딩을 사용합니다.")
                    return DummyEmbeddingClient()
                else:
                    print("🔄 다른 오류로 인해 더미 임베딩을 사용합니다.")
                    return DummyEmbeddingClient()
        
        # 2. 표준 OpenAI API 키 확인 (fallback)
        openai_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        if openai_key:
            print("🔧 표준 OpenAI Embedding 클라이언트 생성 시도...")
            embedding_client = AzureOpenAIEmbeddings(
                openai_api_key=openai_key,
                model="text-embedding-ada-002"
            )
            print("✅ 표준 OpenAI Embedding 클라이언트 생성 성공")
            return embedding_client
        
        # 3. 모든 키가 없으면 더미 임베딩 클라이언트 사용
        print("⚠️ OpenAI 키가 없어서 더미 임베딩을 사용합니다.")
        return DummyEmbeddingClient()
        
    except Exception as e:
        print(f"❌ Embedding 클라이언트 생성 실패: {e}")
        print("🔄 더미 임베딩 클라이언트로 폴백합니다.")
        return DummyEmbeddingClient()

class DummyEmbeddingClient:
    """더미 임베딩 클라이언트 (테스트용)"""
    
    def embed_query(self, text: str):
        """더미 임베딩 생성 (384차원 - ChromaDB 기본 임베딩과 동일)"""
        import random
        # ChromaDB 기본 임베딩과 동일한 384차원
        return [random.random() for _ in range(384)]
    
    def embed_documents(self, texts: list):
        """더미 문서 임베딩 생성"""
        return [self.embed_query(text) for text in texts]

def embed_and_store_chunks(file_processing_result: Dict[str, Any], file_name: str) -> int:
    """
    파일 처리 결과를 임베딩하고 벡터 DB에 저장
    
    Args:
        file_processing_result: FileProcessor.process_file()에서 반환된 결과
        file_name: 원본 파일명
    
    Returns:
        저장된 청크 개수
    """
    try:
        # ChromaDB 기본 임베딩을 사용하므로 별도 임베딩 클라이언트 불필요
        vector_db = VectorDBManager()
        
        # 파일 해시 생성 (중복 방지용)
        file_hash = hashlib.md5(file_name.encode()).hexdigest()
        
        stored_count = 0
        
        # FileProcessor.process_file의 결과 구조 확인
        if not isinstance(file_processing_result, dict):
            print(f"❌ 예상치 못한 결과 타입: {type(file_processing_result)}")
            return 0
        
        print(f"📊 파일 처리 결과 키들: {list(file_processing_result.keys())}")
        
        # processed_pages 배열에서 청크 추출
        processed_pages = file_processing_result.get('processed_pages', [])
        print(f"📄 처리된 페이지 수: {len(processed_pages)}")
        
        for page_idx, page_data in enumerate(processed_pages):
            try:
                print(f"🔍 페이지 {page_idx+1} 처리 중...")
                print(f"📊 페이지 데이터 구조: {type(page_data)}")
                
                if isinstance(page_data, dict):
                    print(f"📊 페이지 데이터 키들: {list(page_data.keys())}")
                    
                    # elements 배열에서 텍스트 추출
                    elements = page_data.get('elements', [])
                    print(f"🔍 elements 개수: {len(elements)}")
                    
                    for element_idx, element in enumerate(elements):
                        try:
                            print(f"🔍 element {element_idx}: {type(element)}")
                            
                            if isinstance(element, dict):
                                # 텍스트 요소 처리
                                if element.get('element_type') == 'text':
                                    content = element.get('content', '')
                                    if content and len(content.strip()) > 10:
                                        print(f"✅ 텍스트 요소에서 내용 추출: {len(content)}자")
                                        
                                        # 청크 ID 생성
                                        chunk_id = str(uuid.uuid4())
                                        
                                        # FileChunk 객체 생성
                                        file_chunk = FileChunk(
                                            chunk_id=chunk_id,
                                            file_name=file_name,
                                            file_hash=file_hash,
                                            text_chunk=content,
                                            architecture="dual_path_hybrid",
                                            processing_method="file_processor",
                                            vision_analysis=False,
                                            section_title=page_data.get('section_title', ''),
                                            page_number=page_data.get('page_number', page_idx + 1),
                                            element_count=1,
                                            file_type=file_processing_result.get('file_type', 'unknown'),
                                            elements=[element],
                                            created_at=datetime.now().isoformat(),
                                            file_size=len(content),
                                            processing_duration=0.0
                                        )
                                        
                                        # 벡터 DB에 저장
                                        vector_db.add_file_chunk(file_chunk)
                                        stored_count += 1
                                        print(f"✅ 텍스트 청크 {stored_count} 저장 완료")
                                
                                # 테이블 요소 처리
                                elif element.get('element_type') == 'table':
                                    table_data = element.get('content', [])
                                    if isinstance(table_data, list) and table_data:
                                        # 테이블을 텍스트로 변환
                                        table_text = ""
                                        for row in table_data:
                                            if isinstance(row, list):
                                                row_text = " | ".join(str(cell) for cell in row if cell)
                                                if row_text:
                                                    table_text += row_text + "\n"
                                        
                                        if table_text and len(table_text.strip()) > 10:
                                            print(f"✅ 테이블 요소에서 내용 추출: {len(table_text)}자")
                                            
                                            # 청크 ID 생성
                                            chunk_id = str(uuid.uuid4())
                                            
                                            # FileChunk 객체 생성
                                            file_chunk = FileChunk(
                                                chunk_id=chunk_id,
                                                file_name=file_name,
                                                file_hash=file_hash,
                                                text_chunk=table_text,
                                                architecture="dual_path_hybrid",
                                                processing_method="file_processor",
                                                vision_analysis=False,
                                                section_title=page_data.get('section_title', ''),
                                                page_number=page_data.get('page_number', page_idx + 1),
                                                element_count=1,
                                                file_type=file_processing_result.get('file_type', 'unknown'),
                                                elements=[element],
                                                created_at=datetime.now().isoformat(),
                                                file_size=len(table_text),
                                                processing_duration=0.0
                                            )
                                            
                                            # 벡터 DB에 저장
                                            vector_db.add_file_chunk(file_chunk)
                                            stored_count += 1
                                            print(f"✅ 테이블 청크 {stored_count} 저장 완료")
                            
                            else:
                                # element가 dict가 아닌 경우 문자열로 변환
                                element_text = str(element)
                                if len(element_text.strip()) > 10:
                                    print(f"✅ element {element_idx}를 문자열로 변환: {len(element_text)}자")
                                    
                                    # 청크 ID 생성
                                    chunk_id = str(uuid.uuid4())
                                    
                                    # FileChunk 객체 생성
                                    file_chunk = FileChunk(
                                        chunk_id=chunk_id,
                                        file_name=file_name,
                                        file_hash=file_hash,
                                        text_chunk=element_text,
                                        architecture="dual_path_hybrid",
                                        processing_method="file_processor",
                                        vision_analysis=False,
                                        section_title=page_data.get('section_title', ''),
                                        page_number=page_data.get('page_number', page_idx + 1),
                                        element_count=1,
                                        file_type=file_processing_result.get('file_type', 'unknown'),
                                        elements=[element],
                                        created_at=datetime.now().isoformat(),
                                        file_size=len(element_text),
                                        processing_duration=0.0
                                    )
                                    
                                    # 벡터 DB에 저장
                                    vector_db.add_file_chunk(file_chunk)
                                    stored_count += 1
                                    print(f"✅ 문자열 청크 {stored_count} 저장 완료")
                        
                        except Exception as e:
                            print(f"❌ element {element_idx} 처리 실패: {e}")
                            continue
                
                else:
                    # page_data가 dict가 아닌 경우 문자열로 처리
                    page_text = str(page_data)
                    if len(page_text.strip()) > 10:
                        print(f"✅ 페이지 {page_idx+1}를 문자열로 변환: {len(page_text)}자")
                        
                        # 청크 ID 생성
                        chunk_id = str(uuid.uuid4())
                        
                        # FileChunk 객체 생성
                        file_chunk = FileChunk(
                            chunk_id=chunk_id,
                            file_name=file_name,
                            file_hash=file_hash,
                            text_chunk=page_text,
                            architecture="dual_path_hybrid",
                            processing_method="file_processor",
                            vision_analysis=False,
                            section_title="",
                            page_number=page_idx + 1,
                            element_count=1,
                            file_type=file_processing_result.get('file_type', 'unknown'),
                            elements=[],
                            created_at=datetime.now().isoformat(),
                            file_size=len(page_text),
                            processing_duration=0.0
                        )
                        
                        # 벡터 DB에 저장
                        vector_db.add_file_chunk(file_chunk)
                        stored_count += 1
                        print(f"✅ 페이지 청크 {stored_count} 저장 완료")
                
            except Exception as e:
                print(f"❌ 페이지 {page_idx+1} 처리 실패: {e}")
                continue
    
        return stored_count
        
    except Exception as e:
        print(f"❌ 청크 임베딩 및 저장 실패: {e}")
        return 0

def get_db_statistics() -> Dict[str, int]:
    """벡터 DB 통계 정보 조회"""
    try:
        vector_db = VectorDBManager()
        
        # 파일 청크 개수 조회
        file_chunks_count = vector_db.get_file_chunks_count()
        
        # 메일 개수 조회
        mails_count = vector_db.get_mails_count()
        
        return {
            "file_chunks": file_chunks_count,
            "mails": mails_count,
            "total_documents": file_chunks_count + mails_count
        }
    except Exception as e:
        print(f"❌ DB 통계 조회 실패: {e}")
        return {"file_chunks": 0, "mails": 0, "total_documents": 0}

def clear_all_data():
    """벡터 DB의 모든 데이터 삭제"""
    try:
        vector_db = VectorDBManager()
        vector_db.clear_all_data()
        print("✅ 모든 데이터가 삭제되었습니다.")
        return True
    except Exception as e:
        print(f"❌ 데이터 삭제 실패: {e}")
        return False

def reset_chromadb():
    """ChromaDB 강제 재설정 (충돌 해결용)"""
    try:
        print("🔄 ChromaDB 재설정을 시작합니다...")
        
        # VectorDBManager 인스턴스 생성 (충돌 방지)
        vector_db = VectorDBManager()
        
        # 강제 재설정 실행
        success = vector_db.force_reset_chromadb()
        
        if success:
            print("✅ ChromaDB 재설정이 완료되었습니다!")
            return True
        else:
            print("❌ ChromaDB 재설정에 실패했습니다.")
            return False
            
    except Exception as e:
        print(f"❌ ChromaDB 재설정 중 오류 발생: {e}")
        return False

def create_rag_manager_tab():
    """RAG 데이터 관리자 탭 생성"""
    import streamlit as st
    
    st.header("📚 RAG 데이터 관리자")
    st.markdown("문서를 업로드하여 벡터 데이터베이스에 저장하고 관리할 수 있습니다.")
    
    # 2단 레이아웃 생성
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📁 파일 처리")
        
        # 파일 업로더
        uploaded_files = st.file_uploader(
            "문서 파일을 업로드하세요",
            type=['docx', 'pptx', 'pdf', 'xlsx', 'xls', 'txt', 'md', 'xml'],
            accept_multiple_files=True,
            help="여러 파일을 동시에 업로드할 수 있습니다. (DOCX, PPTX, PDF, XLSX, XLS, TXT, MD, XML 지원)"
        )
        
        # 파일 처리 버튼
        if st.button("🚀 업로드된 파일 처리 및 임베딩", disabled=not uploaded_files):
            if uploaded_files:
                process_uploaded_files(uploaded_files)
            else:
                st.warning("⚠️ 업로드할 파일을 선택해주세요.")
    
    with col2:
        st.subheader("📊 데이터베이스 현황")
        
        # DB 통계 표시
        stats = get_db_statistics()
        
        st.metric(
            label="📄 총 문서 수",
            value=stats["total_documents"],
            help="파일 청크 + 메일 데이터"
        )
        
        st.metric(
            label="🧩 파일 청크 수",
            value=stats["file_chunks"],
            help="업로드된 파일에서 추출된 청크"
        )
        
        st.metric(
            label="📧 메일 데이터 수",
            value=stats["mails"],
            help="이메일에서 추출된 데이터"
        )
        
        # 데이터 관리 섹션
        with st.expander("🔧 데이터베이스 관리", expanded=False):
            st.markdown("**ChromaDB 충돌 해결**")
            st.info("ChromaDB 인스턴스 충돌이 발생한 경우 아래 버튼을 사용하세요.")
            
            if st.button("🔄 ChromaDB 재설정", type="secondary"):
                with st.spinner("ChromaDB를 재설정하는 중..."):
                    if reset_chromadb():
                        st.success("✅ ChromaDB 재설정이 완료되었습니다!")
                        st.rerun()  # 페이지 새로고침
                    else:
                        st.error("❌ ChromaDB 재설정에 실패했습니다.")
            
            st.markdown("---")
            st.markdown("**전체 데이터 삭제**")
            st.warning("이 작업은 되돌릴 수 없습니다!")
            
            if st.button("🗑️ 모든 데이터 삭제", type="secondary"):
                if clear_all_data():
                    st.rerun()  # 페이지 새로고침

def process_uploaded_files(uploaded_files):
    """업로드된 파일들을 처리"""
    import streamlit as st
    
    # Azure OpenAI 이미지 프로세서 생성
    from module.image_to_text import AzureOpenAIImageProcessor
    azure_processor = AzureOpenAIImageProcessor(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    )
    
    # FileProcessor 인스턴스 생성
    file_processor = FileProcessor(azure_processor)
    
    total_chunks = 0
    processed_files = 0
    
    for uploaded_file in uploaded_files:
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # 파일 처리
            with st.spinner(f"📄 {uploaded_file.name} 처리 중..."):
                # 파일 타입 감지
                doc_type = FileTypeDetector.detect_file_type(tmp_file_path)
                
                # 파일 처리
                result = file_processor.process_file(tmp_file_path)
                
                if result and result.get('processed_pages'):
                    # 청크 임베딩 및 저장
                    chunks_stored = embed_and_store_chunks(
                        result, 
                        uploaded_file.name
                    )
                    
                    if chunks_stored > 0:
                        st.success(f"✅ {uploaded_file.name} 처리 완료! {chunks_stored}개의 청크가 DB에 저장되었습니다.")
                        total_chunks += chunks_stored
                        processed_files += 1
                    else:
                        st.warning(f"⚠️ {uploaded_file.name} 처리 완료되었지만 저장된 청크가 없습니다.")
                else:
                    st.error(f"❌ {uploaded_file.name} 처리 실패")
            
            # 임시 파일 삭제
            os.unlink(tmp_file_path)
            
        except Exception as e:
            st.error(f"❌ {uploaded_file.name} 처리 중 오류 발생: {e}")
    
    # 전체 결과 요약
    if processed_files > 0:
        st.success(f"🎉 총 {processed_files}개 파일 처리 완료! {total_chunks}개의 청크가 저장되었습니다.")
        st.rerun()  # DB 통계 업데이트를 위해 페이지 새로고침

def process_uploaded_files_with_structured_chunking(uploaded_files, use_structured_chunking: bool = True):
    """
    업로드된 파일들을 구조적 청킹으로 처리
    
    Args:
        uploaded_files: Streamlit 업로드된 파일 리스트
        use_structured_chunking: 구조적 청킹 사용 여부
    """
    if not uploaded_files:
        st.warning("⚠️ 업로드된 파일이 없습니다.")
        return
    
    # Vector DB 초기화
    vector_db = VectorDBManager()
    
    # FileProcessor 초기화
    azure_processor = None  # 구조적 청킹에서는 Vision 처리 불필요
    file_processor = FileProcessor(azure_processor)
    
    total_chunks = 0
    processed_files = 0
    
    for uploaded_file in uploaded_files:
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # 파일 처리
            with st.spinner(f"📄 {uploaded_file.name} 구조적 청킹 처리 중..."):
                if use_structured_chunking:
                    # 구조적 청킹 처리
                    structured_chunks = file_processor.process_with_structured_chunking(tmp_file_path)
                    
                    if structured_chunks:
                        # 구조적 청크들을 Vector DB에 저장
                        chunks_stored = 0
                        for structured_chunk in structured_chunks:
                            # StructuredChunk 객체 생성
                            chunk_id = str(uuid.uuid4())
                            file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
                            
                            structured_chunk_obj = StructuredChunk(
                                chunk_id=chunk_id,
                                content=structured_chunk.content,
                                chunk_type=structured_chunk.chunk_type,
                                ticket_id=structured_chunk.ticket_id,
                                field_name=structured_chunk.field_name,
                                field_value=structured_chunk.field_value,
                                priority=structured_chunk.priority,
                                file_name=uploaded_file.name,
                                file_type=Path(tmp_file_path).suffix.lower(),
                                metadata=structured_chunk.metadata,
                                created_at=datetime.now().isoformat(),
                                commenter=structured_chunk.commenter
                            )
                            
                            # Vector DB에 저장
                            if vector_db.add_structured_chunk(structured_chunk_obj):
                                chunks_stored += 1
                        
                        if chunks_stored > 0:
                            st.success(f"✅ {uploaded_file.name} 구조적 청킹 완료! {chunks_stored}개의 구조적 청크가 저장되었습니다.")
                            total_chunks += chunks_stored
                            processed_files += 1
                        else:
                            st.warning(f"⚠️ {uploaded_file.name} 구조적 청킹 완료되었지만 저장된 청크가 없습니다.")
                    else:
                        st.warning(f"⚠️ {uploaded_file.name} 구조적 청킹을 적용할 수 없습니다. 일반 처리로 전환합니다.")
                        # 일반 처리로 폴백
                        result = file_processor.process_file(tmp_file_path)
                        if result and result.get('processed_pages'):
                            chunks_stored = embed_and_store_chunks(result, uploaded_file.name)
                            if chunks_stored > 0:
                                st.success(f"✅ {uploaded_file.name} 일반 처리 완료! {chunks_stored}개의 청크가 저장되었습니다.")
                                total_chunks += chunks_stored
                                processed_files += 1
                else:
                    # 일반 처리
                    result = file_processor.process_file(tmp_file_path)
                    if result and result.get('processed_pages'):
                        chunks_stored = embed_and_store_chunks(result, uploaded_file.name)
                        if chunks_stored > 0:
                            st.success(f"✅ {uploaded_file.name} 처리 완료! {chunks_stored}개의 청크가 저장되었습니다.")
                            total_chunks += chunks_stored
                            processed_files += 1
            
            # 임시 파일 삭제
            os.unlink(tmp_file_path)
            
        except Exception as e:
            st.error(f"❌ {uploaded_file.name} 처리 중 오류 발생: {e}")
    
    # 전체 결과 요약
    if processed_files > 0:
        st.success(f"🎉 총 {processed_files}개 파일 처리 완료! {total_chunks}개의 청크가 저장되었습니다.")
        st.rerun()  # DB 통계 업데이트를 위해 페이지 새로고침

def get_structured_chunk_stats():
    """구조적 청크 통계 조회"""
    try:
        vector_db = VectorDBManager()
        stats = vector_db.get_structured_chunk_stats()
        return stats
    except Exception as e:
        st.error(f"❌ 구조적 청크 통계 조회 실패: {e}")
        return {"total_chunks": 0, "chunk_types": {}, "unique_tickets": 0, "tickets": {}}
