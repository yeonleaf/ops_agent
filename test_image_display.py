#!/usr/bin/env python3
"""
이미지 표시 테스트
"""

import streamlit as st
import base64
import io
from PIL import Image
from vector_db_models import VectorDBManager

def main():
    st.title("🖼️ 이미지 표시 테스트")
    
    # 메일 ID 입력
    mail_id = st.text_input("메일 ID를 입력하세요:", value="19947b9595e5becd")
    
    if st.button("이미지 조회 테스트"):
        try:
            st.info(f"메일 ID '{mail_id}'의 이미지를 조회 중...")
            
            # 벡터 DB에서 이미지 조회
            vector_db = VectorDBManager()
            mail_images = vector_db.get_images_by_mail_id(mail_id)
            
            st.success(f"✅ {len(mail_images)}개의 이미지를 찾았습니다.")
            
            if mail_images:
                for i, img_info in enumerate(mail_images, 1):
                    st.subheader(f"이미지 {i}")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Base64 이미지 표시
                        if img_info.get('image_data'):
                            try:
                                # Base64 데이터 디코딩
                                base64_data = img_info['image_data']
                                if base64_data.startswith('data:image'):
                                    base64_data = base64_data.split(',')[1]
                                
                                image_bytes = base64.b64decode(base64_data)
                                image = Image.open(io.BytesIO(image_bytes))
                                
                                st.image(image, caption=img_info.get('description', ''), use_column_width=True)
                                st.success("✅ 이미지 표시 성공!")
                                
                            except Exception as e:
                                st.error(f"❌ 이미지 표시 실패: {e}")
                                st.text(f"Base64 데이터 길이: {len(img_info.get('image_data', ''))}")
                                st.text(f"Base64 시작: {img_info.get('image_data', '')[:100]}...")
                        else:
                            st.warning("이미지 데이터가 없습니다.")
                    
                    with col2:
                        st.write(f"**ID:** {img_info.get('image_id', 'N/A')}")
                        st.write(f"**설명:** {img_info.get('description', 'N/A')}")
                        st.write(f"**태그:** {', '.join(img_info.get('tags', []))}")
                        st.write(f"**임베딩 방법:** {img_info.get('embedding_method', 'N/A')}")
                        st.write(f"**파일 크기:** {img_info.get('file_size', 0):,} bytes")
                        st.write(f"**데이터 길이:** {len(img_info.get('image_data', ''))}")
            else:
                st.warning("이미지를 찾을 수 없습니다.")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")
            import traceback
            st.text(traceback.format_exc())

if __name__ == "__main__":
    main()
