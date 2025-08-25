#!/usr/bin/env python3
"""
Azure OpenAI 프로세서를 사용한 Vision-First 분류 전략 PPTX 처리 테스트
"""

import os
import sys
from pathlib import Path

# module 디렉토리를 Python 경로에 추가
sys.path.append('module')

from logging_config import setup_logging
from file_processor_refactored import FileProcessor

def test_azure_vision_first_pptx():
    """Azure OpenAI 프로세서를 사용한 Vision-First 분류 전략 테스트"""
    print("🚀 Azure OpenAI Vision-First 분류 전략 PPTX 처리 테스트")
    print("=" * 70)
    
    # 로깅 설정
    setup_logging(level="INFO", log_file="logs/azure_vision_first_test.log")
    
    # 환경 변수 확인
    print("🔍 Azure OpenAI 환경 변수 확인:")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4-vision")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    
    print(f"   AZURE_OPENAI_API_KEY: {'설정됨' if api_key else '설정되지 않음'}")
    print(f"   AZURE_OPENAI_ENDPOINT: {'설정됨' if endpoint else '설정되지 않음'}")
    print(f"   AZURE_OPENAI_DEPLOYMENT_NAME: {deployment_name}")
    print(f"   AZURE_OPENAI_API_VERSION: {api_version}")
    
    if not api_key or not endpoint:
        print("\n❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일을 생성하고 다음 정보를 설정해주세요:")
        print("   AZURE_OPENAI_ENDPOINT=your_endpoint_here")
        print("   AZURE_OPENAI_API_KEY=your_api_key_here")
        print("   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision")
        print("   AZURE_OPENAI_API_VERSION=2024-10-21")
        return
    
    # Azure OpenAI 프로세서 초기화
    azure_processor = None
    try:
        from module.image_to_text import AzureOpenAIImageProcessor
        
        azure_processor = AzureOpenAIImageProcessor(api_key, endpoint, deployment_name)
        print("✅ Azure OpenAI 프로세서 초기화 성공")
        
    except Exception as e:
        print(f"❌ Azure OpenAI 프로세서 초기화 실패: {e}")
        return
    
    # 파일 처리기 초기화
    print("📋 파일 처리기 초기화...")
    file_processor = FileProcessor(azure_processor=azure_processor)
    
    # PPTX 파일 테스트
    pptx_file = "sample.pptx"
    if not os.path.exists(pptx_file):
        print(f"❌ 파일을 찾을 수 없습니다: {pptx_file}")
        return
    
    print(f"\n--- {pptx_file} Azure Vision-First 처리 중 ---")
    try:
        # 파일 처리
        result = file_processor.process_file(pptx_file)
        
        if "error" not in result:
            print(f"✅ 처리 성공!")
            print(f"📄 파일 타입: {result['file_info']['file_type']}")
            print(f"📄 콘텐츠 타입: {result['file_info']['content_type']}")
            print(f"📄 처리 방법: {result['file_info']['processing_method']}")
            print(f"📄 총 청크 수: {result['file_info']['total_chunks']}")
            
            # 결과를 파일로 저장
            output_dir = "azure_vision_first_output"
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = Path(pptx_file).stem
            
            # JSON 형식으로 저장
            json_path = os.path.join(output_dir, f"{base_name}_azure_vision_first.json")
            file_processor.save_result_to_file(result, json_path, "json")
            
            # Markdown 형식으로 저장
            md_path = os.path.join(output_dir, f"{base_name}_azure_vision_first.md")
            file_processor.save_result_to_file(result, md_path, "md")
            
            print(f"💾 결과 저장됨:")
            print(f"   JSON: {json_path}")
            print(f"   MD: {md_path}")
            
            # Azure Vision-First 분류 결과 분석
            print(f"\n🔍 Azure Vision-First 분류 결과 분석:")
            chunks = result.get('chunks', [])
            
            # 처리 방식별 통계
            processing_methods = {}
            vision_classifications = {}
            element_types = {}
            
            for chunk in chunks:
                method = chunk.get('metadata', {}).get('processing_method', 'unknown')
                vision_class = chunk.get('metadata', {}).get('vision_classification', 'unknown')
                element_type = chunk.get('metadata', {}).get('element_type', 'unknown')
                
                processing_methods[method] = processing_methods.get(method, 0) + 1
                if vision_class != 'unknown':
                    vision_classifications[vision_class] = vision_classifications.get(vision_class, 0) + 1
                element_types[element_type] = element_types.get(element_type, 0) + 1
            
            print(f"📊 처리 방식별 통계:")
            for method, count in processing_methods.items():
                print(f"   {method}: {count}개 청크")
            
            if vision_classifications:
                print(f"📊 Vision 분류 결과:")
                for vision_class, count in vision_classifications.items():
                    print(f"   {vision_class}: {count}개 청크")
            
            print(f"📊 요소 타입별 통계:")
            for element_type, count in element_types.items():
                print(f"   {element_type}: {count}개 청크")
            
            # 슬라이드별 처리 방식 분석
            print(f"\n📊 슬라이드별 처리 방식 분석:")
            slides_processing = {}
            
            for chunk in chunks:
                slide_num = chunk.get('metadata', {}).get('slide_number', 'unknown')
                processing_method = chunk.get('metadata', {}).get('processing_method', 'unknown')
                element_type = chunk.get('metadata', {}).get('element_type', 'unknown')
                vision_class = chunk.get('metadata', {}).get('vision_classification', 'N/A')
                
                if slide_num not in slides_processing:
                    slides_processing[slide_num] = {
                        'method': processing_method,
                        'chunks': 0,
                        'types': set(),
                        'vision_class': vision_class
                    }
                
                slides_processing[slide_num]['chunks'] += 1
                slides_processing[slide_num]['types'].add(element_type)
            
            # 슬라이드별 결과 출력
            for slide_num in sorted(slides_processing.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                info = slides_processing[slide_num]
                vision_info = f" (Vision: {info['vision_class']})" if info['vision_class'] != 'N/A' else ""
                print(f"   슬라이드 {slide_num}: {info['method']} 방식, {info['chunks']}개 청크{vision_info}")
                print(f"     요소 타입: {', '.join(sorted(info['types']))}")
            
            # Vision 처리된 청크 내용 미리보기
            vision_chunks = [chunk for chunk in chunks if chunk.get('metadata', {}).get('element_type') == 'vision_processed']
            if vision_chunks:
                print(f"\n🔍 Vision 처리된 청크 미리보기:")
                for i, chunk in enumerate(vision_chunks[:3]):  # 처음 3개만
                    print(f"   Vision 청크 {i+1}:")
                    print(f"     슬라이드: {chunk['metadata'].get('slide_number', 'N/A')}")
                    print(f"     처리 방식: {chunk['metadata'].get('processing_method', 'N/A')}")
                    content_preview = chunk['text_chunk_to_embed'][:150]
                    print(f"     내용: {content_preview}...")
                    print()
            else:
                print(f"\n⚠️ Vision 처리된 청크가 없습니다.")
                
        else:
            print(f"❌ 처리 실패: {result.get('message', '알 수 없는 오류')}")
            
    except Exception as e:
        print(f"❌ 처리 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    # 처리 통계 출력
    print(f"\n📊 처리 통계:")
    stats = file_processor.get_processing_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n🎉 Azure OpenAI Vision-First 분류 전략 테스트 완료!")

def main():
    """메인 함수"""
    print("Azure OpenAI Vision-First 분류 전략 PPTX 처리 테스트 시작")
    print("=" * 70)
    
    # Azure Vision-First 분류 전략 테스트
    test_azure_vision_first_pptx()
    
    print("\n📁 생성된 파일들:")
    print("   - azure_vision_first_output/: Azure Vision-First 처리 결과")
    print("   - logs/: 로그 파일")
    
    print("\n💡 Azure OpenAI Vision-First 분류 전략의 장점:")
    print("   1. 실제 GPT-Vision API를 사용한 정확한 슬라이드 분류")
    print("   2. 이미지 기반 시각적 요소 분석으로 더 정확한 판별")
    print("   3. 복잡한 레이아웃과 다이어그램의 정확한 인식")
    print("   4. 각 슬라이드에 최적화된 처리 방식 자동 선택")

if __name__ == "__main__":
    main() 