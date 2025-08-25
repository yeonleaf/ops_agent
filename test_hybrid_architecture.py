#!/usr/bin/env python3
"""
이중 경로 하이브리드 아키텍처 PPTX 처리 테스트

새로운 아키텍처:
1. 경로 1: 요소 단위 분석 - 개별 도형, 텍스트, 표, 이미지 추출
2. 경로 2: 페이지 단위 분석 - 전체 슬라이드 Vision 분석
3. 결과 합성: 페이지 요약 + 요소 데이터를 하나의 풍부한 JSON으로
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def main():
    print("🚀 이중 경로 하이브리드 아키텍처 PPTX 처리 테스트")
    print("=" * 70)
    
    # Azure OpenAI 환경 변수 확인
    print("🔍 Azure OpenAI 환경 변수 확인:")
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", 
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   {var}: 설정됨")
        else:
            print(f"   {var}: 설정되지 않음")
            print("❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
            return
    
    print("✅ Azure OpenAI 환경 변수 확인 완료")
    
    # 파일 처리기 초기화
    print("📋 파일 처리기 초기화...")
    try:
        from module.file_processor_refactored import FileProcessor
        
        processor = FileProcessor()
        print("✅ 파일 처리기 초기화 성공")
        
    except Exception as e:
        print(f"❌ 파일 처리기 초기화 실패: {e}")
        return
    
    # sample.pptx 파일 처리
    pptx_file = "sample.pptx"
    if not os.path.exists(pptx_file):
        print(f"❌ {pptx_file} 파일을 찾을 수 없습니다.")
        return
    
    print(f"\n--- {pptx_file} 이중 경로 하이브리드 처리 중 ---")
    
    try:
        # 파일 처리 실행
        result = processor.process_file(pptx_file)
        
        if result and not result.get("error"):
            print("✅ 처리 성공!")
            print(f"📄 파일 타입: {result.get('file_type', 'unknown')}")
            print(f"📄 콘텐츠 타입: {result.get('content_type', 'unknown')}")
            print(f"📄 처리 방법: {result.get('processing_method', 'unknown')}")
            print(f"📄 총 청크 수: {len(result.get('chunks', []))}")
            
            # 결과 저장
            output_dir = "hybrid_architecture_output"
            os.makedirs(output_dir, exist_ok=True)
            
            # JSON 파일로 저장
            json_path = os.path.join(output_dir, "sample_hybrid.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"💾 JSON 결과 저장: {json_path}")
            
            # Markdown 파일로 저장
            md_path = os.path.join(output_dir, "sample_hybrid.md")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("# 이중 경로 하이브리드 아키텍처 처리 결과\n\n")
                f.write(f"**파일**: {pptx_file}\n")
                f.write(f"**처리 방법**: {result.get('processing_method', 'unknown')}\n")
                f.write(f"**총 청크 수**: {len(result.get('chunks', []))}\n\n")
                
                for i, chunk in enumerate(result.get('chunks', []), 1):
                    f.write(f"## 청크 {i}\n\n")
                    f.write(f"**요소 타입**: {chunk.get('metadata', {}).get('element_type', 'unknown')}\n")
                    f.write(f"**슬라이드 번호**: {chunk.get('metadata', {}).get('slide_number', 'unknown')}\n")
                    f.write(f"**요소 개수**: {chunk.get('metadata', {}).get('element_count', 0)}\n\n")
                    
                    # text_chunk_to_embed (페이지 단위 요약)
                    f.write("### 전체 맥락 요약\n\n")
                    f.write(chunk.get('text_chunk_to_embed', '내용 없음') + "\n\n")
                    
                    # metadata의 elements (요소 단위 데이터)
                    elements = chunk.get('metadata', {}).get('elements', [])
                    if elements:
                        f.write("### 요소 단위 분석\n\n")
                        for j, element in enumerate(elements, 1):
                            f.write(f"#### 요소 {j}: {element.get('element_type', 'unknown')}\n\n")
                            f.write(f"- **도형 타입**: {element.get('shape_type', 'unknown')}\n")
                            f.write(f"- **위치**: {element.get('position', {})}\n")
                            f.write(f"- **내용**: {element.get('content', '내용 없음')}\n\n")
            
            print(f"💾 Markdown 결과 저장: {md_path}")
            
            # 결과 분석
            print("\n🔍 이중 경로 하이브리드 아키텍처 결과 분석:")
            chunks = result.get('chunks', [])
            
            if chunks:
                print(f"📊 총 슬라이드 수: {len(chunks)}")
                
                # 아키텍처 정보 확인
                for i, chunk in enumerate(chunks, 1):
                    metadata = chunk.get('metadata', {})
                    print(f"\n📋 슬라이드 {i}:")
                    print(f"   아키텍처: {metadata.get('architecture', 'unknown')}")
                    print(f"   처리 방법: {metadata.get('processing_method', 'unknown')}")
                    print(f"   요소 개수: {metadata.get('element_count', 0)}")
                    print(f"   Vision 분석: {metadata.get('vision_analysis', False)}")
                    
                    # 요소 타입별 통계
                    elements = metadata.get('elements', [])
                    if elements:
                        element_types = {}
                        for element in elements:
                            elem_type = element.get('element_type', 'unknown')
                            element_types[elem_type] = element_types.get(elem_type, 0) + 1
                        
                        print(f"   요소 타입별 통계:")
                        for elem_type, count in element_types.items():
                            print(f"     {elem_type}: {count}개")
                
                print(f"\n💡 이중 경로 하이브리드 아키텍처의 장점:")
                print("   1. 모든 슬라이드에 대해 일관된 처리 방식")
                print("   2. 요소 단위의 정확한 데이터 추출")
                print("   3. 페이지 단위의 전체 맥락 이해")
                print("   4. 풍부한 메타데이터와 구조화된 정보")
                
            else:
                print("❌ 처리된 청크가 없습니다.")
                
        else:
            print("❌ 처리 실패!")
            if result:
                print(f"오류: {result.get('message', '알 수 없는 오류')}")
                
    except Exception as e:
        print(f"❌ 파일 처리 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 이중 경로 하이브리드 아키텍처 테스트 완료!")
    print(f"\n📁 생성된 파일들:")
    print(f"   - {output_dir}/: 이중 경로 하이브리드 처리 결과")

if __name__ == "__main__":
    main() 