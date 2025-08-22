import openai
import base64
import sys
import os
from typing import Optional

class AzureOpenAIImageProcessor:
    def __init__(self, api_key: str, endpoint: str, deployment_name: str):
        """
        Azure OpenAI 이미지 처리기 초기화
        
        Args:
            api_key: Azure OpenAI API 키
            endpoint: Azure OpenAI 엔드포인트 (예: https://your-resource.openai.azure.com/)
            deployment_name: 배포된 모델 이름
        """
        # API 키 검증
        if not api_key or api_key.strip() == "":
            raise ValueError("API 키가 제공되지 않았습니다.")
        
        if not endpoint or endpoint.strip() == "":
            raise ValueError("엔드포인트가 제공되지 않았습니다.")
        
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment_name = deployment_name
        
        # Azure OpenAI 클라이언트 설정 (새로운 API)
        try:
            self.client = openai.AzureOpenAI(
                api_key=api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=endpoint,
                azure_deployment=deployment_name
            )
        except Exception as e:
            raise Exception(f"Azure OpenAI 클라이언트 초기화 실패: {str(e)}")
    
    def image_to_text(self, image_path: str, prompt: str = "이 이미지의 내용을 텍스트로 변환해주세요.") -> str:
        """
        이미지를 텍스트로 변환
        
        Args:
            image_path: 이미지 파일 경로
            prompt: 이미지 분석을 위한 프롬프트
            
        Returns:
            변환된 텍스트
        """
        try:
            # 이미지 파일 읽기 및 base64 인코딩
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            
            # Azure OpenAI API 호출 (새로운 API)
            response = self.client.chat.completions.create(
                model=self.deployment_name,  # Azure에서는 deployment_name 사용
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except FileNotFoundError:
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        except Exception as e:
            raise Exception(f"이미지 처리 중 오류가 발생했습니다: {str(e)}")
    
    def image_to_text_with_summary(self, image_path: str, summary_prompt: str = "이미지 내용을 간단히 요약해주세요.") -> dict:
        """
        이미지를 텍스트로 변환하고 요약
        
        Args:
            image_path: 이미지 파일 경로
            summary_prompt: 요약을 위한 프롬프트
            
        Returns:
            원본 텍스트와 요약을 포함한 딕셔너리
        """
        # 원본 텍스트 추출
        original_text = self.image_to_text(image_path, "이 이미지의 모든 텍스트 내용을 추출해주세요.")
        
        # 요약 생성
        summary = self.image_to_text(image_path, summary_prompt)
        
        return {
            "original_text": original_text,
            "summary": summary
        }

def main():
    """메인 함수 - 명령행에서 실행"""
    if len(sys.argv) < 4:
        print("사용법: python image_to_text.py [이미지경로] [API_KEY] [ENDPOINT] [DEPLOYMENT_NAME]")
        print("예시: python image_to_text.py image.jpg your_api_key https://your-resource.openai.azure.com/ gpt-4-vision")
        sys.exit(1)
    
    image_path = sys.argv[1]
    api_key = sys.argv[2]
    endpoint = sys.argv[3]
    deployment_name = sys.argv[4] if len(sys.argv) > 4 else "gpt-4-vision"
    
    try:
        processor = AzureOpenAIImageProcessor(api_key, endpoint, deployment_name)
        result = processor.image_to_text(image_path)
        print("=== 이미지 텍스트 변환 결과 ===")
        print(result)
        
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 