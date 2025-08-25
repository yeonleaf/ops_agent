#!/usr/bin/env python3
"""
파일 헤더 분석 도구
업로드된 파일의 실제 형식을 확인합니다.
"""

import os
from pathlib import Path

def analyze_file_header(file_path: str):
    """파일 헤더를 분석하여 실제 형식 확인"""
    print(f"🔍 파일 분석: {file_path}")
    print("=" * 50)
    
    if not os.path.exists(file_path):
        print(f"❌ 파일이 존재하지 않습니다: {file_path}")
        return
    
    # 파일 크기 확인
    file_size = os.path.getsize(file_path)
    print(f"📏 파일 크기: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    
    # 파일 확장자
    file_ext = Path(file_path).suffix.lower()
    print(f"📁 파일 확장자: {file_ext}")
    
    # 파일 헤더 읽기 (처음 32바이트)
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
            hex_header = ' '.join(f'{b:02x}' for b in header)
            print(f"🔢 파일 헤더 (32바이트): {hex_header}")
            
            # ASCII로 해석 시도
            ascii_header = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)
            print(f"📝 ASCII 해석: {ascii_header}")
            
            # 파일 형식 판별
            if header.startswith(b'PK\x03\x04'):
                print("✅ ZIP 압축 파일 (PPTX, DOCX, XLSX 등)")
                # ZIP 파일 내부 구조 확인
                print("🔍 ZIP 파일 내부 구조 분석 중...")
                try:
                    import zipfile
                    with zipfile.ZipFile(file_path, 'r') as zip_file:
                        file_list = zip_file.namelist()
                        print(f"📁 ZIP 내부 파일들 ({len(file_list)}개):")
                        for i, name in enumerate(file_list[:10]):  # 처음 10개만
                            print(f"  {i+1}. {name}")
                        if len(file_list) > 10:
                            print(f"  ... 외 {len(file_list) - 10}개")
                except Exception as zip_error:
                    print(f"⚠️  ZIP 파일 분석 실패: {zip_error}")
                    
            elif header.startswith(b'%PDF'):
                print("✅ PDF 파일")
            elif header.startswith(b'\xff\xfe') or header.startswith(b'\xfe\xff'):
                print("✅ 유니코드 텍스트 파일")
            elif header.startswith(b'\xef\xbb\xbf'):
                print("✅ UTF-8 BOM 텍스트 파일")
            elif all(32 <= b <= 126 or b in [9, 10, 13] for b in header):
                print("✅ 일반 텍스트 파일")
            else:
                print("❓ 알 수 없는 바이너리 파일")
                
                # 추가 분석 시도
                if file_size < 1024:  # 작은 파일은 전체 내용 확인
                    print("🔍 작은 파일 전체 내용:")
                    with open(file_path, 'rb') as f:
                        full_content = f.read()
                        hex_full = ' '.join(f'{b:02x}' for b in full_content)
                        print(f"전체 헥스: {hex_full}")
                        
                        # 텍스트로 해석 시도
                        try:
                            text_content = full_content.decode('utf-8', errors='ignore')
                            if text_content.strip():
                                print(f"텍스트 내용: {text_content[:200]}...")
                        except:
                            pass
                
    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")
    
    print("=" * 50)

def main():
    print("🚀 파일 헤더 분석 도구")
    print()
    
    # 현재 디렉토리의 파일들 확인
    current_dir = os.getcwd()
    print(f"📁 현재 디렉토리: {current_dir}")
    print()
    
    # PPTX 파일 찾기
    pptx_files = list(Path(current_dir).glob("*.pptx"))
    if pptx_files:
        print(f"📎 발견된 PPTX 파일들:")
        for pptx_file in pptx_files:
            print(f"  • {pptx_file.name}")
        print()
        
        # 첫 번째 PPTX 파일 분석
        first_pptx = str(pptx_files[0])
        analyze_file_header(first_pptx)
        
        # 다른 파일들도 분석
        for pptx_file in pptx_files[1:]:
            print()
            analyze_file_header(str(pptx_file))
    else:
        print("❌ PPTX 파일을 찾을 수 없습니다.")
        
        # 다른 문서 파일들 확인
        doc_files = list(Path(current_dir).glob("*.doc*"))
        pdf_files = list(Path(current_dir).glob("*.pdf"))
        
        if doc_files:
            print(f"📄 발견된 DOC 파일들:")
            for doc_file in doc_files:
                print(f"  • {doc_file.name}")
        
        if pdf_files:
            print(f"📕 발견된 PDF 파일들:")
            for pdf_file in pdf_files:
                print(f"  • {pdf_file.name}")

if __name__ == "__main__":
    main() 