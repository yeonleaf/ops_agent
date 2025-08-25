#!/usr/bin/env python3
"""
이중 하이브리드 vs 단순 변환 방식 테스트

파일 타입별 처리 방식:
1. 이중 하이브리드: PPTX, PDF, DOCX
   - 요소 단위 분석 + 전체 Vision 분석
   - text_chunk_to_embed에 전체 맥락 요약

2. 단순 변환: XLSX, CSV, TXT, MD
   - 요소 단위 분석만 수행
   - text_chunk_to_embed는 빈 문자열
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def main():
    print("🚀 이중 하이브리드 vs 단순 변환 방식 테스트")
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
    
    # 테스트할 파일들
    test_files = [
        ("sample.pptx", "이중 하이브리드 방식"),
        ("sample.docx", "이중 하이브리드 방식"),
        # ("sample.pdf", "이중 하이브리드 방식"),  # PDF 파일이 없는 경우
    ]
    
    # 단순 변환 방식 테스트를 위한 샘플 파일 생성
    create_sample_files()
    
    test_files.extend([
        ("sample.xlsx", "단순 변환 방식"),
        ("sample.txt", "단순 변환 방식"),
        ("sample.md", "단순 변환 방식"),
    ])
    
    results = {}
    
    for file_name, expected_method in test_files:
        if not os.path.exists(file_name):
            print(f"⚠️  {file_name} 파일이 없어 건너뜀")
            continue
            
        print(f"\n--- {file_name} {expected_method} 테스트 중 ---")
        
        try:
            # 파일 처리 실행
            result = processor.process_file(file_name)
            
            if result and not result.get("error"):
                print(f"✅ 처리 성공!")
                print(f"📄 파일 타입: {result.get('file_type', 'unknown')}")
                print(f"📄 콘텐츠 타입: {result.get('content_type', 'unknown')}")
                print(f"📄 처리 방법: {result.get('processing_method', 'unknown')}")
                print(f"📄 총 청크 수: {len(result.get('chunks', []))}")
                
                # 아키텍처 분석
                chunks = result.get('chunks', [])
                if chunks:
                    first_chunk = chunks[0]
                    metadata = first_chunk.get('metadata', {})
                    
                    architecture = metadata.get('architecture', 'unknown')
                    vision_analysis = metadata.get('vision_analysis', False)
                    text_content = first_chunk.get('text_chunk_to_embed', '')
                    
                    print(f"🏗️  아키텍처: {architecture}")
                    print(f"👁️  Vision 분석: {vision_analysis}")
                    print(f"📝 text_chunk_to_embed 길이: {len(text_content)}")
                    
                    if architecture == "dual_path_hybrid":
                        print(f"✅ {expected_method} 확인됨")
                    elif architecture == "simple_conversion":
                        print(f"✅ {expected_method} 확인됨")
                    else:
                        print(f"❓ 예상과 다른 아키텍처: {architecture}")
                
                results[file_name] = {
                    "success": True,
                    "method": expected_method,
                    "architecture": metadata.get('architecture', 'unknown'),
                    "chunks": len(chunks)
                }
                
            else:
                print("❌ 처리 실패!")
                if result:
                    print(f"오류: {result.get('message', '알 수 없는 오류')}")
                
                results[file_name] = {
                    "success": False,
                    "method": expected_method,
                    "error": result.get('message', '알 수 없는 오류') if result else '처리 실패'
                }
                
        except Exception as e:
            print(f"❌ 파일 처리 중 오류 발생: {e}")
            results[file_name] = {
                "success": False,
                "method": expected_method,
                "error": str(e)
            }
    
    # 결과 요약
    print("\n" + "=" * 70)
    print("📊 테스트 결과 요약")
    print("=" * 70)
    
    for file_name, result in results.items():
        status = "✅ 성공" if result["success"] else "❌ 실패"
        print(f"{file_name}: {status}")
        if result["success"]:
            print(f"   아키텍처: {result['architecture']}")
            print(f"   청크 수: {result['chunks']}")
        else:
            print(f"   오류: {result['error']}")
        print()
    
    # 성공률 계산
    successful = sum(1 for r in results.values() if r["success"])
    total = len(results)
    success_rate = (successful / total) * 100 if total > 0 else 0
    
    print(f"🎯 전체 성공률: {successful}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("🎉 대부분의 파일이 성공적으로 처리되었습니다!")
    elif success_rate >= 50:
        print("⚠️  일부 파일 처리에 문제가 있었습니다.")
    else:
        print("❌ 많은 파일 처리에 문제가 있었습니다.")
    
    print(f"\n🎉 이중 하이브리드 vs 단순 변환 방식 테스트 완료!")

def create_sample_files():
    """테스트용 샘플 파일들을 생성합니다."""
    
    # XLSX 파일 생성
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "시트1"
        
        # 샘플 데이터
        data = [
            ["이름", "나이", "직업"],
            ["김철수", "25", "개발자"],
            ["이영희", "30", "디자이너"],
            ["박민수", "28", "기획자"]
        ]
        
        for row in data:
            ws.append(row)
        
        wb.save("sample.xlsx")
        print("✅ sample.xlsx 생성 완료")
        
    except Exception as e:
        print(f"⚠️  sample.xlsx 생성 실패: {e}")
    
    # TXT 파일 생성
    try:
        with open("sample.txt", "w", encoding="utf-8") as f:
            f.write("샘플 텍스트 파일\n")
            f.write("이것은 테스트용 텍스트 파일입니다.\n")
            f.write("여러 줄의 텍스트를 포함하고 있습니다.\n")
            f.write("한글도 정상적으로 처리됩니다.")
        print("✅ sample.txt 생성 완료")
        
    except Exception as e:
        print(f"⚠️  sample.txt 생성 실패: {e}")
    
    # MD 파일 생성
    try:
        with open("sample.md", "w", encoding="utf-8") as f:
            f.write("# 샘플 마크다운 파일\n\n")
            f.write("## 소개\n")
            f.write("이것은 테스트용 마크다운 파일입니다.\n\n")
            f.write("## 특징\n")
            f.write("- 마크다운 문법 지원\n")
            f.write("- 구조화된 텍스트\n")
            f.write("- 가독성 좋음\n\n")
            f.write("## 코드 예시\n")
            f.write("```python\n")
            f.write("print('Hello, World!')\n")
            f.write("```")
        print("✅ sample.md 생성 완료")
        
    except Exception as e:
        print(f"⚠️  sample.md 생성 실패: {e}")

if __name__ == "__main__":
    main() 