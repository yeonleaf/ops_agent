#!/usr/bin/env python3
"""
사용자가 만든 파일들로 이중 하이브리드 vs 단순 변환 방식 테스트

테스트할 파일들:
1. sample.pdf - 이중 하이브리드 방식
2. sample.csv - 단순 변환 방식  
3. sample.md - 단순 변환 방식
4. sample.xlsx - 단순 변환 방식
5. sample.txt - 단순 변환 방식
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def main():
    print("🚀 사용자 파일들로 이중 하이브리드 vs 단순 변환 방식 테스트")
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
    
    # 사용자가 만든 파일들
    test_files = [
        ("sample.pdf", "이중 하이브리드 방식"),
        ("sample.csv", "단순 변환 방식"),
        ("sample.md", "단순 변환 방식"),
        ("sample.xlsx", "단순 변환 방식"),
        ("sample.txt", "단순 변환 방식"),
    ]
    
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
                    element_count = metadata.get('element_count', 0)
                    
                    print(f"🏗️  아키텍처: {architecture}")
                    print(f"👁️  Vision 분석: {vision_analysis}")
                    print(f"📝 text_chunk_to_embed 길이: {len(text_content)}")
                    print(f"🔢 요소 개수: {element_count}")
                    
                    # 요소 타입별 통계
                    elements = metadata.get('elements', [])
                    if elements:
                        element_types = {}
                        for element in elements:
                            elem_type = element.get('element_type', 'unknown')
                            element_types[elem_type] = element_types.get(elem_type, 0) + 1
                        
                        print(f"📊 요소 타입별 통계:")
                        for elem_type, count in element_types.items():
                            print(f"     {elem_type}: {count}개")
                    
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
                    "chunks": len(chunks),
                    "elements": element_count
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
            print(f"   요소 수: {result['elements']}")
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
    
    # 아키텍처별 통계
    architectures = {}
    for result in results.values():
        if result["success"]:
            arch = result["architecture"]
            architectures[arch] = architectures.get(arch, 0) + 1
    
    print(f"\n🏗️  아키텍처별 통계:")
    for arch, count in architectures.items():
        print(f"   {arch}: {count}개 파일")
    
    print(f"\n🎉 사용자 파일 테스트 완료!")

if __name__ == "__main__":
    main() 