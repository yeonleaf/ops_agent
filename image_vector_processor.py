#!/usr/bin/env python3
"""
이미지 벡터 프로세서
메일에서 이미지를 추출하고 벡터화하여 저장하는 통합 프로세서
"""

import os
import base64
import io
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime
from PIL import Image
import uuid
from bs4 import BeautifulSoup

from image_embedding_generator import ImageEmbeddingGenerator
from vector_db_models import VectorDBManager, ImageVector

logger = logging.getLogger(__name__)

class ImageVectorProcessor:
    """이미지 벡터 프로세서"""
    
    def __init__(self, use_azure_vision: bool = True):
        """
        초기화
        
        Args:
            use_azure_vision: Azure Vision API 사용 여부
        """
        self.embedding_generator = ImageEmbeddingGenerator(use_azure_vision)
        self.vector_db = VectorDBManager()
        
        logger.info("✅ 이미지 벡터 프로세서 초기화 완료")
    
    def process_mail_images(self, mail_id: str, html_content: str) -> List[Dict[str, any]]:
        """
        메일 HTML에서 이미지를 추출하고 벡터화하여 저장
        
        Args:
            mail_id: 메일 ID
            html_content: HTML 내용
            
        Returns:
            처리된 이미지 정보 리스트
        """
        try:
            logger.info(f"🔍 메일 이미지 처리 시작 - 메일 ID: {mail_id}")
            
            # HTML에서 이미지 추출
            images = self._extract_images_from_html(html_content)
            logger.info(f"🖼️ 발견된 이미지 수: {len(images)}개")
            
            processed_images = []
            
            for i, image_data in enumerate(images):
                try:
                    # 이미지 벡터 생성 및 저장
                    result = self._process_single_image(
                        image_data, 
                        mail_id, 
                        f"{mail_id}_img_{i+1}"
                    )
                    
                    if result:
                        processed_images.append(result)
                        logger.info(f"✅ 이미지 {i+1} 처리 완료")
                    else:
                        logger.warning(f"⚠️ 이미지 {i+1} 처리 실패")
                        
                except Exception as e:
                    logger.error(f"❌ 이미지 {i+1} 처리 중 오류: {e}")
                    continue
            
            logger.info(f"✅ 메일 이미지 처리 완료 - {len(processed_images)}개 성공")
            return processed_images
            
        except Exception as e:
            logger.error(f"❌ 메일 이미지 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_images_from_html(self, html_content: str) -> List[Dict[str, any]]:
        """HTML에서 이미지 추출"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            images = soup.find_all('img')
            
            extracted_images = []
            
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '')
                title = img.get('title', '')
                
                if not src:
                    continue
                
                image_info = {
                    'src': src,
                    'alt': alt,
                    'title': title,
                    'is_base64': src.startswith('data:image'),
                    'is_cid': 'cid:' in src,
                    'is_external': src.startswith('http'),
                    'is_local': not src.startswith('http') and not src.startswith('data:image') and 'cid:' not in src
                }
                
                # Base64 인라인 이미지인 경우 데이터 추출
                if image_info['is_base64']:
                    try:
                        if ';base64,' in src:
                            base64_data = src.split(';base64,')[1]
                            image_bytes = base64.b64decode(base64_data)
                            image_info['image_data'] = image_bytes
                            image_info['image_format'] = src.split(';')[0].split('/')[1]
                        else:
                            continue
                    except Exception as e:
                        logger.warning(f"Base64 이미지 디코딩 실패: {e}")
                        continue
                
                # 외부 이미지인 경우 URL 저장
                elif image_info['is_external']:
                    image_info['image_url'] = src
                
                # CID 첨부 이미지인 경우
                elif image_info['is_cid']:
                    image_info['cid'] = src
                
                # 로컬 이미지인 경우
                elif image_info['is_local']:
                    image_info['local_path'] = src
                
                extracted_images.append(image_info)
            
            return extracted_images
            
        except Exception as e:
            logger.error(f"❌ HTML 이미지 추출 실패: {e}")
            return []
    
    def _process_single_image(self, image_info: Dict[str, any], 
                            mail_id: str, image_id: str) -> Optional[Dict[str, any]]:
        """단일 이미지 처리"""
        try:
            # 이미지 데이터 준비
            if image_info.get('is_base64') and 'image_data' in image_info:
                # Base64 이미지 처리
                image_data = image_info['image_data']
                image = Image.open(io.BytesIO(image_data))
                
            elif image_info.get('is_external'):
                # 외부 이미지 처리 (URL에서 다운로드)
                image_data = self._download_external_image(image_info['image_url'])
                if not image_data:
                    return None
                image = Image.open(io.BytesIO(image_data))
                
            elif image_info.get('is_cid'):
                # CID 첨부 이미지 처리 (메일 첨부파일에서 찾기)
                image_data = self._get_cid_image(image_info['cid'], mail_id)
                if not image_data:
                    return None
                image = Image.open(io.BytesIO(image_data))
                
            elif image_info.get('is_local'):
                # 로컬 이미지 처리
                local_path = image_info['local_path']
                if os.path.exists(local_path):
                    image = Image.open(local_path)
                    with open(local_path, 'rb') as f:
                        image_data = f.read()
                else:
                    logger.warning(f"로컬 이미지 파일을 찾을 수 없습니다: {local_path}")
                    return None
                
            else:
                logger.warning(f"지원하지 않는 이미지 타입: {image_info}")
                return None
            
            # 이미지 임베딩 생성
            embedding_result = self.embedding_generator.generate_embedding(
                image, image_id
            )
            
            if not embedding_result or not embedding_result.get('embedding'):
                logger.error(f"이미지 임베딩 생성 실패: {image_id}")
                return None
            
            # 이미지 설명 생성 (간단한 방법)
            description = self._generate_image_description(image_info, embedding_result)
            
            # 이미지 벡터 객체 생성
            image_vector = ImageVector(
                image_id=image_id,
                mail_id=mail_id,
                image_data=base64.b64encode(image_data).decode('utf-8') if isinstance(image_data, bytes) else image_data,
                image_metadata=embedding_result['metadata'],
                embedding=embedding_result['embedding'],
                description=description,
                tags=self._extract_image_tags(image_info, embedding_result),
                created_at=datetime.now().isoformat(),
                embedding_method=embedding_result['method'],
                file_size=len(image_data) if isinstance(image_data, bytes) else 0,
                processing_duration=0.0  # 실제로는 시간 측정 필요
            )
            
            # Vector DB에 저장
            success = self.vector_db.save_image_vector(image_vector)
            
            if success:
                return {
                    'image_id': image_id,
                    'mail_id': mail_id,
                    'description': description,
                    'tags': image_vector.tags,
                    'embedding_method': embedding_result['method'],
                    'file_size': image_vector.file_size,
                    'success': True
                }
            else:
                logger.error(f"이미지 벡터 저장 실패: {image_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 단일 이미지 처리 실패: {e}")
            return None
    
    def _download_external_image(self, url: str) -> Optional[bytes]:
        """외부 이미지 다운로드"""
        try:
            import requests
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            logger.error(f"외부 이미지 다운로드 실패: {e}")
            return None
    
    def _get_cid_image(self, cid: str, mail_id: str) -> Optional[bytes]:
        """CID 첨부 이미지 가져오기"""
        try:
            # 실제 구현에서는 메일 첨부파일에서 CID로 이미지를 찾아야 함
            # 여기서는 간단한 구현만 제공
            logger.warning(f"CID 이미지 처리 미구현: {cid}")
            return None
            
        except Exception as e:
            logger.error(f"CID 이미지 가져오기 실패: {e}")
            return None
    
    def _generate_image_description(self, image_info: Dict[str, any], 
                                  embedding_result: Dict[str, any]) -> str:
        """이미지 설명 생성"""
        try:
            # Alt 텍스트가 있으면 사용
            if image_info.get('alt'):
                return image_info['alt']
            
            # Title 텍스트가 있으면 사용
            if image_info.get('title'):
                return image_info['title']
            
            # 메타데이터에서 설명 추출
            metadata = embedding_result.get('metadata', {})
            if 'description' in metadata:
                return metadata['description']
            
            # 기본 설명 생성
            if image_info.get('is_base64'):
                return "인라인 이미지"
            elif image_info.get('is_external'):
                return "외부 이미지"
            elif image_info.get('is_cid'):
                return "첨부된 이미지"
            else:
                return "이미지"
                
        except Exception as e:
            logger.error(f"이미지 설명 생성 실패: {e}")
            return "이미지"
    
    def _extract_image_tags(self, image_info: Dict[str, any], 
                          embedding_result: Dict[str, any]) -> List[str]:
        """이미지 태그 추출"""
        try:
            tags = []
            
            # Alt 텍스트에서 태그 추출
            if image_info.get('alt'):
                tags.append(image_info['alt'])
            
            # Title 텍스트에서 태그 추출
            if image_info.get('title'):
                tags.append(image_info['title'])
            
            # 이미지 타입 태그 추가
            if image_info.get('is_base64'):
                tags.append('인라인')
            elif image_info.get('is_external'):
                tags.append('외부')
            elif image_info.get('is_cid'):
                tags.append('첨부')
            
            # 메타데이터에서 태그 추출
            metadata = embedding_result.get('metadata', {})
            if 'tags' in metadata:
                tags.extend(metadata['tags'])
            
            return list(set(tags))  # 중복 제거
            
        except Exception as e:
            logger.error(f"이미지 태그 추출 실패: {e}")
            return []
    
    def search_similar_images(self, query_image_data: Union[str, bytes, Image.Image], 
                            limit: int = 5, mail_id: str = None) -> List[Dict[str, any]]:
        """유사한 이미지 검색"""
        try:
            # 쿼리 이미지의 임베딩 생성
            embedding_result = self.embedding_generator.generate_embedding(
                query_image_data, "query_image"
            )
            
            if not embedding_result or not embedding_result.get('embedding'):
                logger.error("쿼리 이미지 임베딩 생성 실패")
                return []
            
            # 유사 이미지 검색
            similar_images = self.vector_db.search_similar_images(
                embedding_result['embedding'],
                limit=limit,
                mail_id=mail_id
            )
            
            return similar_images
            
        except Exception as e:
            logger.error(f"❌ 유사 이미지 검색 실패: {e}")
            return []
    
    def get_mail_images(self, mail_id: str) -> List[Dict[str, any]]:
        """메일의 모든 이미지 조회"""
        try:
            return self.vector_db.get_images_by_mail_id(mail_id)
        except Exception as e:
            logger.error(f"❌ 메일 이미지 조회 실패: {e}")
            return []


def test_image_vector_processor():
    """이미지 벡터 프로세서 테스트"""
    logger.info("🔧 이미지 벡터 프로세서 테스트...")
    
    try:
        # 프로세서 초기화
        processor = ImageVectorProcessor(use_azure_vision=True)
        
        # 테스트용 HTML (Base64 이미지 포함)
        test_html = '''
        <html>
        <body>
            <p>테스트 메일입니다.</p>
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" alt="테스트 이미지" title="작은 이미지">
            <img src="https://via.placeholder.com/150" alt="외부 이미지">
            <p>감사합니다.</p>
        </body>
        </html>
        '''
        
        # 메일 이미지 처리
        mail_id = "test_mail_001"
        results = processor.process_mail_images(mail_id, test_html)
        
        logger.info(f"✅ 이미지 처리 결과: {len(results)}개")
        for i, result in enumerate(results):
            logger.info(f"   이미지 {i+1}: {result['image_id']} - {result['description']}")
        
        # 메일 이미지 조회 테스트
        mail_images = processor.get_mail_images(mail_id)
        logger.info(f"✅ 메일 이미지 조회: {len(mail_images)}개")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_image_vector_processor()
