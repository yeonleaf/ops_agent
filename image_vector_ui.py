#!/usr/bin/env python3
"""
이미지 벡터 검색 UI
Streamlit을 사용한 이미지 벡터 검색 및 관리 인터페이스
"""

import streamlit as st
import base64
import io
from PIL import Image
import json
from typing import List, Dict, Any
import logging

from image_vector_processor import ImageVectorProcessor
from vector_db_models import VectorDBManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_session_state():
    """세션 상태 초기화"""
    if 'image_processor' not in st.session_state:
        st.session_state.image_processor = ImageVectorProcessor(use_azure_vision=True)
    if 'vector_db' not in st.session_state:
        st.session_state.vector_db = VectorDBManager()

def display_image_from_base64(base64_data: str, caption: str = None):
    """Base64 데이터에서 이미지 표시"""
    try:
        if base64_data.startswith('data:image'):
            base64_data = base64_data.split(',')[1]
        
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        st.image(image, caption=caption, use_column_width=True)
        return True
    except Exception as e:
        st.error(f"이미지 표시 실패: {e}")
        return False

def display_image_info(image_info: Dict[str, Any]):
    """이미지 정보 표시"""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 이미지 표시
        if image_info.get('image_data'):
            display_image_from_base64(image_info['image_data'], image_info.get('description', ''))
    
    with col2:
        # 이미지 메타데이터 표시
        st.subheader("이미지 정보")
        st.write(f"**ID:** {image_info.get('image_id', 'N/A')}")
        st.write(f"**메일 ID:** {image_info.get('mail_id', 'N/A')}")
        st.write(f"**설명:** {image_info.get('description', 'N/A')}")
        st.write(f"**태그:** {', '.join(image_info.get('tags', []))}")
        st.write(f"**임베딩 방법:** {image_info.get('embedding_method', 'N/A')}")
        st.write(f"**파일 크기:** {image_info.get('file_size', 0):,} bytes")
        st.write(f"**생성 시간:** {image_info.get('created_at', 'N/A')}")
        
        # 유사도 점수 표시
        if 'similarity_score' in image_info:
            st.write(f"**유사도:** {image_info['similarity_score']:.3f}")

def main():
    """메인 함수"""
    st.set_page_config(
        page_title="이미지 벡터 검색 시스템",
        page_icon="🖼️",
        layout="wide"
    )
    
    st.title("🖼️ 이미지 벡터 검색 시스템")
    st.markdown("이미지를 벡터화하여 저장하고 유사한 이미지를 검색할 수 있습니다.")
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바
    with st.sidebar:
        st.header("🔧 설정")
        
        # 검색 옵션
        search_limit = st.slider("검색 결과 수", 1, 20, 5)
        
        # 메일 ID 필터
        mail_id_filter = st.text_input("메일 ID 필터 (선택사항)", "")
        
        st.header("📊 통계")
        
        # 전체 이미지 수 표시
        try:
            all_images = st.session_state.vector_db.get_images_by_mail_id("")
            st.metric("전체 이미지 수", len(all_images))
        except:
            st.metric("전체 이미지 수", "N/A")
    
    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 이미지 검색", "📧 메일별 이미지", "📊 통계", "⚙️ 관리"])
    
    with tab1:
        st.header("🔍 유사 이미지 검색")
        
        # 검색 방법 선택
        search_method = st.radio(
            "검색 방법을 선택하세요:",
            ["이미지 업로드", "이미지 URL", "기존 이미지 ID"]
        )
        
        query_image = None
        
        if search_method == "이미지 업로드":
            uploaded_file = st.file_uploader(
                "검색할 이미지를 업로드하세요",
                type=['png', 'jpg', 'jpeg', 'gif', 'bmp']
            )
            
            if uploaded_file:
                query_image = Image.open(uploaded_file)
                st.image(query_image, caption="업로드된 이미지", use_column_width=True)
        
        elif search_method == "이미지 URL":
            image_url = st.text_input("이미지 URL을 입력하세요:")
            if image_url:
                try:
                    import requests
                    response = requests.get(image_url, timeout=10)
                    if response.status_code == 200:
                        query_image = Image.open(io.BytesIO(response.content))
                        st.image(query_image, caption="URL 이미지", use_column_width=True)
                    else:
                        st.error("이미지를 다운로드할 수 없습니다.")
                except Exception as e:
                    st.error(f"이미지 로드 실패: {e}")
        
        elif search_method == "기존 이미지 ID":
            image_id = st.text_input("이미지 ID를 입력하세요:")
            if image_id:
                try:
                    image_info = st.session_state.vector_db.get_image_by_id(image_id)
                    if image_info:
                        query_image = image_info
                        display_image_from_base64(image_info['image_data'], "기존 이미지")
                    else:
                        st.error("이미지를 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"이미지 조회 실패: {e}")
        
        # 검색 실행
        if query_image and st.button("🔍 유사 이미지 검색"):
            try:
                with st.spinner("검색 중..."):
                    similar_images = st.session_state.image_processor.search_similar_images(
                        query_image,
                        limit=search_limit,
                        mail_id=mail_id_filter if mail_id_filter else None
                    )
                
                if similar_images:
                    st.success(f"✅ {len(similar_images)}개의 유사 이미지를 찾았습니다.")
                    
                    # 결과 표시
                    for i, image_info in enumerate(similar_images):
                        with st.expander(f"결과 {i+1} - 유사도: {image_info.get('similarity_score', 0):.3f}"):
                            display_image_info(image_info)
                else:
                    st.warning("유사한 이미지를 찾을 수 없습니다.")
                    
            except Exception as e:
                st.error(f"검색 실패: {e}")
                logger.error(f"이미지 검색 실패: {e}")
    
    with tab2:
        st.header("📧 메일별 이미지 조회")
        
        # 메일 ID 입력
        mail_id = st.text_input("메일 ID를 입력하세요:")
        
        if mail_id and st.button("📧 메일 이미지 조회"):
            try:
                with st.spinner("메일 이미지 조회 중..."):
                    mail_images = st.session_state.vector_db.get_images_by_mail_id(mail_id)
                
                if mail_images:
                    st.success(f"✅ 메일 {mail_id}에서 {len(mail_images)}개의 이미지를 찾았습니다.")
                    
                    # 이미지 그리드 표시
                    cols = st.columns(3)
                    for i, image_info in enumerate(mail_images):
                        with cols[i % 3]:
                            with st.expander(f"이미지 {i+1}"):
                                display_image_info(image_info)
                else:
                    st.warning("해당 메일의 이미지를 찾을 수 없습니다.")
                    
            except Exception as e:
                st.error(f"메일 이미지 조회 실패: {e}")
                logger.error(f"메일 이미지 조회 실패: {e}")
    
    with tab3:
        st.header("📊 통계")
        
        try:
            # 전체 이미지 통계
            all_images = st.session_state.vector_db.get_images_by_mail_id("")
            
            if all_images:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("전체 이미지 수", len(all_images))
                
                with col2:
                    # 임베딩 방법별 통계
                    methods = {}
                    for img in all_images:
                        method = img.get('embedding_method', 'unknown')
                        methods[method] = methods.get(method, 0) + 1
                    
                    st.metric("임베딩 방법", f"{len(methods)}종류")
                
                with col3:
                    # 평균 파일 크기
                    total_size = sum(img.get('file_size', 0) for img in all_images)
                    avg_size = total_size // len(all_images) if all_images else 0
                    st.metric("평균 파일 크기", f"{avg_size:,} bytes")
                
                # 임베딩 방법별 분포 차트
                st.subheader("임베딩 방법별 분포")
                methods_data = {}
                for img in all_images:
                    method = img.get('embedding_method', 'unknown')
                    methods_data[method] = methods_data.get(method, 0) + 1
                
                if methods_data:
                    st.bar_chart(methods_data)
                
                # 최근 이미지 목록
                st.subheader("최근 추가된 이미지")
                recent_images = sorted(all_images, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
                
                for img in recent_images:
                    with st.expander(f"{img.get('image_id', 'N/A')} - {img.get('description', 'N/A')}"):
                        display_image_info(img)
            else:
                st.info("저장된 이미지가 없습니다.")
                
        except Exception as e:
            st.error(f"통계 조회 실패: {e}")
            logger.error(f"통계 조회 실패: {e}")
    
    with tab4:
        st.header("⚙️ 관리")
        
        # 데이터베이스 초기화
        st.subheader("데이터베이스 관리")
        
        if st.button("🗑️ 이미지 벡터 데이터베이스 초기화", type="secondary"):
            st.warning("⚠️ 이 작업은 되돌릴 수 없습니다!")
            
            if st.button("✅ 정말로 초기화하시겠습니까?", type="primary"):
                try:
                    # 이미지 벡터 컬렉션 삭제
                    st.session_state.vector_db.client.delete_collection("image_vectors")
                    st.success("✅ 이미지 벡터 데이터베이스가 초기화되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"초기화 실패: {e}")
        
        # 시스템 정보
        st.subheader("시스템 정보")
        st.write(f"**이미지 프로세서:** Azure Vision API")
        st.write(f"**벡터 DB:** ChromaDB")
        st.write(f"**임베딩 차원:** 1536 (OpenAI text-embedding-ada-002)")

if __name__ == "__main__":
    main()
