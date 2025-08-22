import os
import sys
import json
import tempfile
import shutil
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document
from pptx import Presentation
import pandas as pd
from openpyxl import load_workbook
from PIL import Image
import io

from module.image_to_text import AzureOpenAIImageProcessor

class DocumentType(Enum):
    """문서 타입"""
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    XLSX = "xlsx"
    TEXT = "text"

class ContentType(Enum):
    """콘텐츠 타입 (text-based vs layout-based)"""
    TEXT_BASED = "text_based"
    LAYOUT_BASED = "layout_based"

class ElementType(Enum):
    """문서 요소 타입"""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    SHAPE = "shape"

class DocumentElement:
    """문서 요소 클래스"""
    def __init__(self, element_type: ElementType, content: Any, metadata: Dict = None):
        self.element_type = element_type
        self.content = content
        self.metadata = metadata or {}
    
    def __str__(self):
        return f"{self.element_type.value}: {str(self.content)[:50]}..."

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "element_type": self.element_type.value,
            "content": self.content,
            "metadata": self.metadata
        }

class ProcessedPage:
    """처리된 페이지/슬라이드 정보"""
    def __init__(self, page_number: int, elements: List[DocumentElement], 
                 page_type: str = "page", metadata: Dict = None):
        self.page_number = page_number
        self.elements = elements
        self.page_type = page_type  # "page", "slide", "sheet"
        self.metadata = metadata or {}
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "page_number": self.page_number,
            "page_type": self.page_type,
            "elements": [elem.to_dict() for elem in self.elements],
            "metadata": self.metadata
        }

class FileTypeDetector:
    """파일 타입 판별기"""
    
    @staticmethod
    def detect_file_type(file_path: str) -> DocumentType:
        """파일 확장자로부터 문서 타입 판별"""
        ext = Path(file_path).suffix.lower()
        if ext == '.docx':
            return DocumentType.DOCX
        elif ext == '.pptx':
            return DocumentType.PPTX
        elif ext == '.pdf':
            return DocumentType.PDF
        elif ext == '.xlsx':
            return DocumentType.XLSX
        elif ext in ['.txt', '.md']:
            return DocumentType.TEXT
        else:
            raise ValueError(f"지원하지 않는 파일 타입: {ext}")
    
    @staticmethod
    def detect_content_type(file_path: str, doc_type: DocumentType) -> ContentType:
        """콘텐츠가 text-based인지 layout-based인지 판별"""
        try:
            if doc_type == DocumentType.PDF:
                return FileTypeDetector._analyze_pdf_content(file_path)
            elif doc_type == DocumentType.DOCX:
                return FileTypeDetector._analyze_docx_content(file_path)
            elif doc_type == DocumentType.PPTX:
                return FileTypeDetector._analyze_pptx_content(file_path)
            elif doc_type == DocumentType.XLSX:
                return FileTypeDetector._analyze_xlsx_content(file_path)
            else:
                return ContentType.TEXT_BASED
        except Exception as e:
            print(f"콘텐츠 타입 판별 오류: {e}")
            return ContentType.LAYOUT_BASED  # 오류 시 안전하게 layout-based로 분류
    
    @staticmethod
    def _analyze_pdf_content(file_path: str) -> ContentType:
        """PDF 콘텐츠 분석"""
        try:
            doc = fitz.open(file_path)
            text_content = ""
            image_count = 0
            
            for page in doc:
                text_content += page.get_text()
                image_list = page.get_images()
                image_count += len(image_list)
            
            doc.close()
            
            # 텍스트가 충분하고 이미지가 적으면 text-based
            if len(text_content.strip()) > 100 and image_count < 3:
                return ContentType.TEXT_BASED
        else:
                return ContentType.LAYOUT_BASED
                
        except Exception:
            return ContentType.LAYOUT_BASED
    
    @staticmethod
    def _analyze_docx_content(file_path: str) -> ContentType:
        """DOCX 콘텐츠 분석"""
        try:
            doc = Document(file_path)
            text_content = ""
            image_count = 0
            
            for para in doc.paragraphs:
                text_content += para.text + "\n"
            
            # 이미지 개수 확인 (간단한 방법)
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    image_count += 1
            
            if len(text_content.strip()) > 100 and image_count < 3:
                return ContentType.TEXT_BASED
            else:
                return ContentType.LAYOUT_BASED
                
        except Exception:
            return ContentType.LAYOUT_BASED
    
    @staticmethod
    def _analyze_pptx_content(file_path: str) -> ContentType:
        """PPTX 콘텐츠 분석"""
        try:
            prs = Presentation(file_path)
            text_content = ""
            image_count = 0
            
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text_content += shape.text + "\n"
                    if shape.shape_type == 13:  # 이미지 타입
                        image_count += 1
            
            if len(text_content.strip()) > 50 and image_count < 5:
                return ContentType.TEXT_BASED
            else:
                return ContentType.LAYOUT_BASED
                
        except Exception:
            return ContentType.LAYOUT_BASED
    
    @staticmethod
    def _analyze_xlsx_content(file_path: str) -> ContentType:
        """XLSX 콘텐츠 분석"""
        try:
            wb = load_workbook(file_path, data_only=True)
            text_content = ""
            
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell:
                            text_content += str(cell) + " "
            
            wb.close()
            
            # 엑셀은 대부분 text-based
            if len(text_content.strip()) > 50:
                return ContentType.TEXT_BASED
            else:
                return ContentType.LAYOUT_BASED
                
        except Exception:
            return ContentType.LAYOUT_BASED

class TextBasedProcessor:
    """Text-based 파일 처리기"""
    
    def __init__(self, azure_processor: AzureOpenAIImageProcessor):
        self.azure_processor = azure_processor
    
    def process_docx(self, file_path: str) -> List[ProcessedPage]:
        """DOCX 파일을 페이지별로 처리"""
        try:
            doc = Document(file_path)
            elements = []
            
            # 문단별로 요소 추출
            for para in doc.paragraphs:
                if para.text.strip():
                    elements.append(DocumentElement(
                        ElementType.TEXT, 
                        para.text.strip(),
                        {"paragraph_style": para.style.name if para.style else "Normal"}
                    ))
            
            # 테이블 처리
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text.strip())
                    table_data.append(row_data)
                
                if table_data:
                    elements.append(DocumentElement(
                        ElementType.TABLE,
                        table_data,
                        {"table_type": "docx_table"}
                    ))
            
            # 이미지 처리
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        image_path = rel.target_path
                        elements.append(DocumentElement(
                            ElementType.IMAGE,
                            image_path,
                            {"image_source": "docx_embed"}
                        ))
                    except Exception as e:
                        print(f"이미지 처리 오류: {e}")
            
            # 단일 페이지로 처리 (DOCX는 페이지 구분이 명확하지 않음)
            return [ProcessedPage(1, elements, "page", {"file_type": "docx"})]
            
        except Exception as e:
            print(f"DOCX 처리 오류: {e}")
            return []
    
    def process_pptx(self, file_path: str) -> List[ProcessedPage]:
        """PPTX 파일을 슬라이드별로 처리"""
        try:
            prs = Presentation(file_path)
            processed_slides = []
            
            for slide_num, slide in enumerate(prs.slides, 1):
                elements = []
                
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        elements.append(DocumentElement(
                            ElementType.TEXT,
                            shape.text.strip(),
                            {"shape_type": str(shape.shape_type)}
                        ))
                    
                    if shape.shape_type == 13:  # 이미지
                        try:
                            # 이미지 추출 및 저장
                            image_path = self._extract_pptx_image(shape, slide_num, len(elements))
                            elements.append(DocumentElement(
                                ElementType.IMAGE,
                                image_path,
                                {"image_source": "pptx_slide"}
                            ))
                        except Exception as e:
                            print(f"PPTX 이미지 추출 오류: {e}")
                
                processed_slides.append(ProcessedPage(
                    slide_num, elements, "slide", 
                    {"file_type": "pptx", "slide_layout": slide.slide_layout.name}
                ))
            
            return processed_slides
            
        except Exception as e:
            print(f"PPTX 처리 오류: {e}")
            return []
    
    def process_xlsx(self, file_path: str) -> List[ProcessedPage]:
        """XLSX 파일을 시트별로 처리"""
        try:
            wb = load_workbook(file_path, data_only=True)
            processed_sheets = []
            
            for sheet_num, sheet_name in enumerate(wb.sheetnames, 1):
                ws = wb[sheet_name]
                elements = []
                
                # 시트 데이터를 표로 변환
                table_data = []
                for row in ws.iter_rows(values_only=True):
                    if any(cell is not None for cell in row):
                        table_data.append([str(cell) if cell is not None else "" for cell in row])
                
                if table_data:
                    elements.append(DocumentElement(
                        ElementType.TABLE,
                        table_data,
                        {"table_type": "xlsx_sheet", "sheet_name": sheet_name}
                    ))
                
                processed_sheets.append(ProcessedPage(
                    sheet_num, elements, "sheet",
                    {"file_type": "xlsx", "sheet_name": sheet_name}
                ))
            
            wb.close()
            return processed_sheets
            
        except Exception as e:
            print(f"XLSX 처리 오류: {e}")
            return []
    
    def _extract_pptx_image(self, shape, slide_num: int, element_index: int) -> str:
        """PPTX에서 이미지 추출"""
        try:
            image = shape.image
            image_bytes = image.blob
            
            # 임시 디렉토리에 저장
            temp_dir = "temp_images"
            os.makedirs(temp_dir, exist_ok=True)
            
            image_filename = f"pptx_slide{slide_num}_img{element_index}.png"
            image_path = os.path.join(temp_dir, image_filename)
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            return image_path
            
        except Exception as e:
            raise Exception(f"이미지 추출 실패: {e}")

class LayoutBasedProcessor:
    """Layout-based 파일 처리기 (PDF 변환 후 이미지 처리)"""
    
    def __init__(self, azure_processor: AzureOpenAIImageProcessor):
        self.azure_processor = azure_processor
    
    def process_file(self, file_path: str, doc_type: DocumentType) -> List[ProcessedPage]:
        """Layout-based 파일을 PDF로 변환 후 처리"""
        try:
            # PDF로 변환
            pdf_path = self._convert_to_pdf(file_path, doc_type)
            
            # PDF를 이미지로 변환하여 처리
            return self._process_pdf_as_images(pdf_path)
            
        except Exception as e:
            print(f"Layout-based 처리 오류: {e}")
            return []
    
    def _convert_to_pdf(self, file_path: str, doc_type: DocumentType) -> str:
        """파일을 PDF로 변환"""
        try:
            if doc_type == DocumentType.PDF:
                return file_path
            
            # 임시 PDF 파일 경로
            temp_dir = "temp_pdfs"
            os.makedirs(temp_dir, exist_ok=True)
            
            pdf_filename = f"converted_{Path(file_path).stem}.pdf"
            pdf_path = os.path.join(temp_dir, pdf_filename)
            
            if doc_type == DocumentType.DOCX:
                self._convert_docx_to_pdf(file_path, pdf_path)
            elif doc_type == DocumentType.PPTX:
                self._convert_pptx_to_pdf(file_path, pdf_path)
            elif doc_type == DocumentType.XLSX:
                self._convert_xlsx_to_pdf(file_path, pdf_path)
            
            return pdf_path
            
        except Exception as e:
            raise Exception(f"PDF 변환 실패: {e}")
    
    def _convert_docx_to_pdf(self, docx_path: str, pdf_path: str):
        """DOCX를 PDF로 변환 (LibreOffice 사용)"""
        try:
            import subprocess
            # LibreOffice를 사용하여 변환
            cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", 
                   os.path.dirname(pdf_path), docx_path]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # 변환된 파일 이름 변경
            converted_path = docx_path.replace('.docx', '.pdf')
            if os.path.exists(converted_path):
                shutil.move(converted_path, pdf_path)
                
        except Exception as e:
            print(f"LibreOffice 변환 실패, 대안 방법 사용: {e}")
            # 대안: python-docx2pdf 사용
            try:
                from docx2pdf import convert
                convert(docx_path, pdf_path)
            except ImportError:
                raise Exception("PDF 변환을 위한 라이브러리가 설치되지 않았습니다.")
    
    def _convert_pptx_to_pdf(self, pptx_path: str, pdf_path: str):
        """PPTX를 PDF로 변환"""
        try:
            from pptx2pdf import convert
            convert(pptx_path, pdf_path)
        except ImportError:
            # 대안: LibreOffice 사용
            self._convert_docx_to_pdf(pptx_path, pdf_path)
    
    def _convert_xlsx_to_pdf(self, xlsx_path: str, pdf_path: str):
        """XLSX를 PDF로 변환"""
        try:
            # pandas를 사용하여 HTML로 변환 후 PDF 변환
            df = pd.read_excel(xlsx_path)
            html_path = xlsx_path.replace('.xlsx', '.html')
            df.to_html(html_path)
            
            # HTML을 PDF로 변환 (weasyprint 사용)
            try:
                from weasyprint import HTML
                HTML(html_path).write_pdf(pdf_path)
                os.remove(html_path)
            except ImportError:
                # 대안: LibreOffice 사용
                self._convert_docx_to_pdf(xlsx_path, pdf_path)
                
        except Exception as e:
            print(f"XLSX 변환 실패, LibreOffice 사용: {e}")
            self._convert_docx_to_pdf(xlsx_path, pdf_path)
    
    def _process_pdf_as_images(self, pdf_path: str) -> List[ProcessedPage]:
        """PDF를 이미지로 변환하여 GPT Vision으로 처리"""
        try:
            doc = fitz.open(pdf_path)
            processed_pages = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 페이지를 이미지로 변환
                mat = fitz.Matrix(2.0, 2.0)  # 2배 확대
                pix = page.get_pixmap(matrix=mat)
                
                # 이미지 저장
                                    temp_dir = "temp_images"
                                    os.makedirs(temp_dir, exist_ok=True)
                                    
                image_filename = f"pdf_page{page_num + 1}.png"
                                    image_path = os.path.join(temp_dir, image_filename)
                pix.save(image_path)
                
                # GPT Vision으로 이미지 처리
                prompt = "이 페이지의 모든 텍스트 내용을 추출하고, 표나 이미지가 있다면 설명해주세요."
                text_content = self.azure_processor.image_to_text(image_path, prompt)
                
                # 결과를 텍스트 요소로 저장
                elements = [DocumentElement(
                    ElementType.TEXT,
                    text_content,
                    {"page_number": page_num + 1, "source": "gpt_vision"}
                )]
                
                processed_pages.append(ProcessedPage(
                    page_num + 1, elements, "page",
                    {"file_type": "pdf", "processing_method": "gpt_vision"}
                ))
            
            doc.close()
            return processed_pages
            
        except Exception as e:
            raise Exception(f"PDF 이미지 처리 실패: {e}")

class FileProcessor:
    """메인 파일 처리기"""
    
    def __init__(self, azure_processor: AzureOpenAIImageProcessor):
        self.azure_processor = azure_processor
        self.text_processor = TextBasedProcessor(azure_processor)
        self.layout_processor = LayoutBasedProcessor(azure_processor)
        self.temp_storage = {}
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """파일을 처리하고 결과를 반환"""
        try:
            # 1. 파일 타입 판별
            doc_type = FileTypeDetector.detect_file_type(file_path)
            content_type = FileTypeDetector.detect_content_type(file_path, doc_type)
            
            print(f"파일 타입: {doc_type.value}, 콘텐츠 타입: {content_type.value}")
            
            # 2. 콘텐츠 타입에 따른 처리
            if content_type == ContentType.TEXT_BASED:
                processed_pages = self._process_text_based(file_path, doc_type)
            else:
                processed_pages = self._process_layout_based(file_path, doc_type)
            
            # 3. 결과를 메타데이터와 함께 임시 저장
            result = {
                "file_path": file_path,
                "file_type": doc_type.value,
                "content_type": content_type.value,
                "processed_pages": [page.to_dict() for page in processed_pages],
                "total_pages": len(processed_pages),
                "processing_timestamp": str(pd.Timestamp.now())
            }
            
            # 임시 저장
            self._save_to_temp_storage(file_path, result)
            
            return result

        except Exception as e:
            print(f"파일 처리 오류: {e}")
            return {"error": str(e)}
    
    def _process_text_based(self, file_path: str, doc_type: DocumentType) -> List[ProcessedPage]:
        """Text-based 파일 처리"""
        if doc_type == DocumentType.DOCX:
            return self.text_processor.process_docx(file_path)
        elif doc_type == DocumentType.PPTX:
            return self.text_processor.process_pptx(file_path)
        elif doc_type == DocumentType.XLSX:
            return self.text_processor.process_xlsx(file_path)
        elif doc_type == DocumentType.PDF:
            # PDF는 별도 처리
            return self._process_pdf_text_based(file_path)
        else:
            return []

    def _process_layout_based(self, file_path: str, doc_type: DocumentType) -> List[ProcessedPage]:
        """Layout-based 파일 처리"""
        return self.layout_processor.process_file(file_path, doc_type)
    
    def _process_pdf_text_based(self, file_path: str) -> List[ProcessedPage]:
        """Text-based PDF 처리"""
        try:
            doc = fitz.open(file_path)
            processed_pages = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                elements = []
                
                # 텍스트 블록 추출
                text_blocks = page.get_text("blocks")
                for block in text_blocks:
                    x0, y0, x1, y1, text, block_no, block_type = block[:7]
                    
                    if block_type == 0 and text.strip():  # 텍스트 블록
                            elements.append(DocumentElement(
                                ElementType.TEXT, 
                                text.strip(),
                            {"page": page_num + 1, "bbox": (x0, y0, x1, y1)}
                        ))
                
                if elements:
                    processed_pages.append(ProcessedPage(
                        page_num + 1, elements, "page",
                        {"file_type": "pdf", "processing_method": "text_extraction"}
                        ))
            
            doc.close()
            return processed_pages
            
        except Exception as e:
            print(f"PDF 텍스트 처리 오류: {e}")
            return []
    
    def _save_to_temp_storage(self, file_path: str, result: Dict[str, Any]):
        """결과를 임시 저장소에 저장"""
        file_key = Path(file_path).name
        self.temp_storage[file_key] = result
        
        # JSON 파일로도 저장
        temp_dir = "temp_results"
        os.makedirs(temp_dir, exist_ok=True)
        
        json_filename = f"{Path(file_path).stem}_result.json"
        json_path = os.path.join(temp_dir, json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"결과가 임시 저장되었습니다: {json_path}")
    
    def get_temp_result(self, file_name: str) -> Optional[Dict[str, Any]]:
        """임시 저장된 결과 조회"""
        return self.temp_storage.get(file_name)
    
    def clear_temp_storage(self):
        """임시 저장소 정리"""
        self.temp_storage.clear()
        
        # 임시 파일들도 정리
        temp_dirs = ["temp_images", "temp_pdfs", "temp_results"]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"임시 디렉토리 정리됨: {temp_dir}") 