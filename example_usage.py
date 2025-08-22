#!/usr/bin/env python3
"""
새로운 파일 처리 시스템 사용 예시
PPTX, PDF, DOCX, XLSX 파일을 처리하고 텍스트로 변환
"""

import os
import sys
from pathlib import Path
from module.image_to_text import AzureOpenAIImageProcessor
from module.file_processor import FileProcessor, FileTypeDetector, DocumentType, ContentType

def setup_azure_processor():
    """Azure OpenAI 프로세서 설정"""
    # 환경 변수에서 설정 가져오기
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4-vision")
    
    if not api_key or not endpoint:
        print("환경 변수를 설정해주세요:")
        print("export AZURE_OPENAI_API_KEY='your_api_key'")
        print("export AZURE_OPENAI_ENDPOINT='your_endpoint'")
        print("export AZURE_OPENAI_DEPLOYMENT_NAME='your_deployment_name'")
        return None
    
    try:
        processor = AzureOpenAIImageProcessor(api_key, endpoint, deployment_name)
        print("Azure OpenAI 프로세서 초기화 성공")
        return processor
    except Exception as e:
        print(f"Azure OpenAI 프로세서 초기화 실패: {e}")
        return None

def example_basic_processing():
    """기본 파일 처리 예시"""
    print("\n=== 기본 파일 처리 예시 ===")
    
    # Azure 프로세서 설정
    azure_processor = setup_azure_processor()
    if not azure_processor:
        return
    
    # 파일 처리기 초기화
    file_processor = FileProcessor(azure_processor)
    
    # 샘플 파일들 처리
    sample_files = [
        "sample.docx",
        "sample.pptx"
    ]
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            print(f"\n--- {file_path} 처리 중 ---")
            try:
                result = file_processor.process_file(file_path)
                
                if "error" not in result:
                    print(f"파일 타입: {result['file_type']}")
                    print(f"콘텐츠 타입: {result['content_type']}")
                    print(f"총 페이지/슬라이드 수: {result['total_pages']}")
                    print(f"처리 시간: {result['processing_timestamp']}")
                    
                    # 첫 번째 페이지의 첫 번째 요소 내용 출력
                    if result['processed_pages']:
                        first_page = result['processed_pages'][0]
                        if first_page['elements']:
                            first_element = first_page['elements'][0]
                            print(f"첫 번째 요소: {first_element['element_type']}")
                            content_preview = str(first_element['content'])[:100]
                            print(f"내용 미리보기: {content_preview}...")
                else:
                    print(f"처리 오류: {result['error']}")
                    
            except Exception as e:
                print(f"파일 처리 중 오류: {e}")
        else:
            print(f"파일을 찾을 수 없습니다: {file_path}")

def example_content_type_detection():
    """콘텐츠 타입 판별 예시"""
    print("\n=== 콘텐츠 타입 판별 예시 ===")
    
    sample_files = [
        "sample.docx",
        "sample.pptx"
    ]
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            try:
                # 파일 타입 판별
                doc_type = FileTypeDetector.detect_file_type(file_path)
                content_type = FileTypeDetector.detect_content_type(file_path, doc_type)
                
                print(f"{file_path}:")
                print(f"  - 문서 타입: {doc_type.value}")
                print(f"  - 콘텐츠 타입: {content_type.value}")
                
            except Exception as e:
                print(f"{file_path} 분석 오류: {e}")
        else:
            print(f"파일을 찾을 수 없습니다: {file_path}")

def example_page_level_processing():
    """페이지/슬라이드 단위 처리 예시"""
    print("\n=== 페이지/슬라이드 단위 처리 예시 ===")
    
    azure_processor = setup_azure_processor()
    if not azure_processor:
        return
    
    file_processor = FileProcessor(azure_processor)
    
    # PPTX 파일 처리 (슬라이드별)
    pptx_file = "sample.pptx"
    if os.path.exists(pptx_file):
        try:
            result = file_processor.process_file(pptx_file)
            
            if "error" not in result:
                print(f"\n{pptx_file} 처리 결과:")
                print(f"총 슬라이드 수: {result['total_pages']}")
                
                for page in result['processed_pages']:
                    print(f"\n--- 슬라이드 {page['page_number']} ---")
                    print(f"슬라이드 타입: {page['page_type']}")
                    print(f"요소 수: {len(page['elements'])}")
                    
                    for i, element in enumerate(page['elements']):
                        print(f"  요소 {i+1}: {element['element_type']}")
                        if element['element_type'] == 'text':
                            content_preview = str(element['content'])[:50]
                            print(f"    내용: {content_preview}...")
                        elif element['element_type'] == 'table':
                            print(f"    표 데이터: {len(element['content'])}행")
                
        except Exception as e:
            print(f"PPTX 처리 오류: {e}")
    else:
        print(f"파일을 찾을 수 없습니다: {pptx_file}")

def example_temp_storage():
    """임시 저장소 사용 예시"""
    print("\n=== 임시 저장소 사용 예시 ===")
    
    azure_processor = setup_azure_processor()
    if not azure_processor:
        return
    
    file_processor = FileProcessor(azure_processor)
    
    # 파일 처리
    docx_file = "sample.docx"
    if os.path.exists(docx_file):
        try:
            result = file_processor.process_file(docx_file)
            
            if "error" not in result:
                print(f"{docx_file} 처리 완료")
                
                # 임시 저장소에서 결과 조회
                file_name = Path(docx_file).name
                stored_result = file_processor.get_temp_result(file_name)
                
                if stored_result:
                    print("임시 저장소에서 결과 조회 성공")
                    print(f"저장된 파일 타입: {stored_result['file_type']}")
                else:
                    print("임시 저장소에서 결과를 찾을 수 없습니다")
                
                # 임시 저장소 정리
                print("\n임시 저장소 정리 중...")
                file_processor.clear_temp_storage()
                print("임시 저장소 정리 완료")
                
        except Exception as e:
            print(f"파일 처리 오류: {e}")
    else:
        print(f"파일을 찾을 수 없습니다: {docx_file}")

def example_batch_processing():
    """일괄 처리 예시"""
    print("\n=== 일괄 처리 예시 ===")
    
    azure_processor = setup_azure_processor()
    if not azure_processor:
        return
    
    file_processor = FileProcessor(azure_processor)
    
    # 지원하는 파일 확장자
    supported_extensions = ['.docx', '.pptx', '.pdf', '.xlsx']
    
    # 현재 디렉토리에서 지원하는 파일들 찾기
    current_dir = Path(".")
    target_files = []
    
    for ext in supported_extensions:
        target_files.extend(current_dir.glob(f"*{ext}"))
    
    if not target_files:
        print("처리할 파일을 찾을 수 없습니다.")
        print("지원하는 확장자:", ", ".join(supported_extensions))
        return
    
    print(f"처리할 파일 수: {len(target_files)}")
    
    # 각 파일 처리
    for file_path in target_files:
        print(f"\n--- {file_path.name} 처리 중 ---")
        try:
            result = file_processor.process_file(str(file_path))
            
            if "error" not in result:
                print(f"✓ 처리 완료: {result['file_type']} ({result['content_type']})")
                print(f"  페이지/슬라이드 수: {result['total_pages']}")
            else:
                print(f"✗ 처리 실패: {result['error']}")
                
        except Exception as e:
            print(f"✗ 처리 오류: {e}")
    
    print(f"\n일괄 처리 완료: {len(target_files)}개 파일")

def main():
    """메인 함수"""
    print("새로운 파일 처리 시스템 사용 예시")
    print("=" * 50)
    
    # 환경 변수 확인
    if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
        print("Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        print("환경 변수를 설정한 후 다시 실행하세요.")
        return
    
    # 예시 실행
    example_content_type_detection()
    example_basic_processing()
    example_page_level_processing()
    example_temp_storage()
    example_batch_processing()
    
    print("\n모든 예시 실행 완료!")

if __name__ == "__main__":
    main() 