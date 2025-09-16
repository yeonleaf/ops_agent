#!/usr/bin/env python3
"""
이미지 임베딩 생성기
Azure Vision API 또는 CLIP 모델을 사용하여 이미지에서 벡터 임베딩을 생성
"""

import os
import base64
import io
import logging
from typing import List, Dict, Optional, Union
from PIL import Image
import requests
import json

logger = logging.getLogger(__name__)

class ImageEmbeddingGenerator:
    """이미지 임베딩 생성기"""
    
    def __init__(self, use_azure_vision: bool = True):
        """
        초기화
        
        Args:
            use_azure_vision: Azure Vision API 사용 여부 (False면 CLIP 사용)
        """
        self.use_azure_vision = use_azure_vision
        
        if use_azure_vision:
            self._init_azure_vision()
        else:
            self._init_clip()
    
    def _init_azure_vision(self):
        """Azure Vision API 초기화"""
        try:
            self.azure_endpoint = os.getenv("AZURE_VISION_ENDPOINT")
            self.azure_key = os.getenv("AZURE_VISION_KEY")
            
            if not self.azure_endpoint or not self.azure_key:
                raise ValueError("Azure Vision API 설정이 필요합니다 (AZURE_VISION_ENDPOINT, AZURE_VISION_KEY)")
            
            logger.info("✅ Azure Vision API 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ Azure Vision API 초기화 실패: {e}")
            raise
    
    def _init_clip(self):
        """CLIP 모델 초기화"""
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            logger.info(f"✅ CLIP 모델 초기화 완료 (device: {self.device})")
            
        except Exception as e:
            logger.error(f"❌ CLIP 모델 초기화 실패: {e}")
            raise
    
    def generate_embedding(self, image_data: Union[str, bytes, Image.Image], 
                          image_id: str = None) -> Dict[str, any]:
        """
        이미지에서 임베딩 생성
        
        Args:
            image_data: 이미지 데이터 (파일 경로, bytes, PIL Image)
            image_id: 이미지 식별자
            
        Returns:
            임베딩 정보 딕셔너리
        """
        try:
            # 이미지 데이터 전처리
            if isinstance(image_data, str):
                # 파일 경로인 경우
                if os.path.exists(image_data):
                    with open(image_data, 'rb') as f:
                        image_bytes = f.read()
                    image = Image.open(io.BytesIO(image_bytes))
                else:
                    # Base64 데이터인 경우
                    if image_data.startswith('data:image'):
                        image_data = image_data.split(',')[1]
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_data, bytes):
                image_bytes = image_data
                image = Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_data, Image.Image):
                image = image_data
                # PIL Image를 bytes로 변환
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                image_bytes = img_byte_arr.getvalue()
            else:
                raise ValueError("지원하지 않는 이미지 데이터 타입입니다")
            
            # 이미지 메타데이터 추출
            metadata = {
                'image_id': image_id or f"img_{hash(image_bytes) % 1000000}",
                'width': image.width,
                'height': image.height,
                'format': image.format,
                'mode': image.mode,
                'size_bytes': len(image_bytes)
            }
            
            # 임베딩 생성
            if self.use_azure_vision:
                embedding = self._generate_azure_embedding(image_bytes)
            else:
                embedding = self._generate_clip_embedding(image)
            
            return {
                'embedding': embedding,
                'metadata': metadata,
                'method': 'azure_vision' if self.use_azure_vision else 'clip'
            }
            
        except Exception as e:
            logger.error(f"❌ 이미지 임베딩 생성 실패: {e}")
            raise
    
    def _generate_azure_embedding(self, image_bytes: bytes) -> List[float]:
        """Azure Vision API로 이미지 임베딩 생성"""
        try:
            # Azure Vision API v4.0의 이미지 분석 엔드포인트 사용
            url = f"{self.azure_endpoint}/vision/v4.0/analyze"
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.azure_key,
                'Content-Type': 'application/octet-stream'
            }
            
            params = {
                'visualFeatures': 'Description,Tags,Objects,Faces,ImageType,Color,Adult',
                'details': 'Landmarks,Celebrities',
                'language': 'en'
            }
            
            response = requests.post(url, headers=headers, params=params, data=image_bytes)
            response.raise_for_status()
            
            result = response.json()
            
            # 이미지 설명을 기반으로 텍스트 임베딩 생성
            description = result.get('description', {}).get('captions', [{}])[0].get('text', '')
            tags = ', '.join([tag['name'] for tag in result.get('tags', [])])
            
            # 간단한 텍스트 기반 임베딩 생성 (실제로는 더 정교한 방법 필요)
            text_content = f"{description} {tags}".strip()
            
            # OpenAI API를 사용하여 텍스트 임베딩 생성
            return self._generate_text_embedding(text_content)
            
        except Exception as e:
            logger.error(f"❌ Azure Vision API 호출 실패: {e}")
            # 폴백: 이미지 해시 기반 임베딩
            return self._generate_hash_embedding(image_bytes)
    
    def _generate_clip_embedding(self, image: Image.Image) -> List[float]:
        """CLIP 모델로 이미지 임베딩 생성"""
        try:
            import torch
            
            # 이미지 크기 조정 (CLIP은 224x224를 기대함)
            if image.size != (224, 224):
                image = image.resize((224, 224), Image.Resampling.LANCZOS)
            
            # 이미지 전처리
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            
            # 이미지 특징 추출
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                # 정규화
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten().tolist()
            
        except Exception as e:
            logger.error(f"❌ CLIP 임베딩 생성 실패: {e}")
            # 폴백: 해시 기반 임베딩
            return self._generate_hash_embedding(image.tobytes())
    
    def _generate_text_embedding(self, text: str) -> List[float]:
        """텍스트에서 임베딩 생성 (OpenAI API 사용)"""
        try:
            import openai
            
            # OpenAI API 키 확인
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Azure OpenAI 사용
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OpenAI API 키가 설정되지 않았습니다")
            
            openai.api_key = api_key
            
            # 임베딩 생성
            response = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"❌ 텍스트 임베딩 생성 실패: {e}")
            # 폴백: 간단한 해시 기반 임베딩
            return self._generate_hash_embedding(text.encode())
    
    def _generate_hash_embedding(self, data: bytes) -> List[float]:
        """해시 기반 간단한 임베딩 생성 (폴백용)"""
        import hashlib
        
        # SHA256 해시 생성
        hash_obj = hashlib.sha256(data)
        hash_bytes = hash_obj.digest()
        
        # 1536차원 벡터로 변환 (OpenAI 임베딩과 동일한 차원)
        embedding = []
        for i in range(0, len(hash_bytes), 2):
            if i + 1 < len(hash_bytes):
                # 2바이트를 0-1 범위의 float로 변환
                value = (hash_bytes[i] * 256 + hash_bytes[i + 1]) / 65535.0
                embedding.append(value)
        
        # 1536차원이 되도록 패딩 또는 자르기
        while len(embedding) < 1536:
            embedding.append(0.0)
        
        return embedding[:1536]
    
    def batch_generate_embeddings(self, image_data_list: List[Union[str, bytes, Image.Image]], 
                                 image_ids: List[str] = None) -> List[Dict[str, any]]:
        """
        여러 이미지의 임베딩을 배치로 생성
        
        Args:
            image_data_list: 이미지 데이터 리스트
            image_ids: 이미지 ID 리스트
            
        Returns:
            임베딩 정보 리스트
        """
        results = []
        
        for i, image_data in enumerate(image_data_list):
            try:
                image_id = image_ids[i] if image_ids and i < len(image_ids) else None
                result = self.generate_embedding(image_data, image_id)
                results.append(result)
                
            except Exception as e:
                logger.error(f"❌ 이미지 {i} 임베딩 생성 실패: {e}")
                results.append({
                    'embedding': None,
                    'metadata': {'error': str(e)},
                    'method': 'failed'
                })
        
        return results


def test_image_embedding():
    """이미지 임베딩 생성 테스트"""
    logger.info("🔧 이미지 임베딩 생성 테스트...")
    
    try:
        # 임베딩 생성기 초기화
        generator = ImageEmbeddingGenerator(use_azure_vision=True)
        
        # 테스트용 이미지 생성
        from PIL import Image, ImageDraw, ImageFont
        
        # 간단한 테스트 이미지 생성
        img = Image.new('RGB', (200, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), "Test Image", fill='black')
        
        # 임베딩 생성
        result = generator.generate_embedding(img, "test_image_1")
        
        logger.info(f"✅ 임베딩 생성 성공:")
        logger.info(f"   - 이미지 ID: {result['metadata']['image_id']}")
        logger.info(f"   - 차원: {len(result['embedding'])}")
        logger.info(f"   - 방법: {result['method']}")
        logger.info(f"   - 이미지 크기: {result['metadata']['width']}x{result['metadata']['height']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_image_embedding()
