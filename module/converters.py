"""
파일 변환을 위한 변환기 클래스들
"""

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging

from module.exceptions import ConversionError

logger = logging.getLogger(__name__)


class BaseConverter(ABC):
    """파일 변환을 위한 추상 기본 클래스"""
    
    @abstractmethod
    def convert(self, source_path: str, target_path: str) -> bool:
        """
        파일을 변환합니다.
        
        Args:
            source_path: 원본 파일 경로
            target_path: 대상 파일 경로
            
        Returns:
            변환 성공 여부
            
        Raises:
            ConversionError: 변환 실패 시
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """변환기가 사용 가능한지 확인"""
        pass


class LibreOfficeConverter(BaseConverter):
    """LibreOffice를 사용한 파일 변환기"""
    
    def __init__(self):
        self.converter_name = "LibreOffice"
    
    def is_available(self) -> bool:
        """LibreOffice가 설치되어 있는지 확인"""
        try:
            result = subprocess.run(
                ["soffice", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def convert(self, source_path: str, target_path: str) -> bool:
        """LibreOffice를 사용하여 파일을 변환"""
        if not self.is_available():
            raise ConversionError(
                "LibreOffice가 설치되어 있지 않습니다", 
                source_path, 
                Path(target_path).suffix
            )
        
        try:
            # LibreOffice 변환 명령 실행
            cmd = [
                "soffice", 
                "--headless", 
                "--convert-to", 
                Path(target_path).suffix[1:],  # .pdf -> pdf
                "--outdir", 
                os.path.dirname(target_path), 
                source_path
            ]
            
            logger.info(f"LibreOffice 변환 명령 실행: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if result.returncode != 0:
                raise ConversionError(
                    f"LibreOffice 변환 실패: {result.stderr}", 
                    source_path, 
                    Path(target_path).suffix
                )
            
            # 변환된 파일 이름 변경
            converted_filename = Path(source_path).stem + Path(target_path).suffix
            converted_path = os.path.join(os.path.dirname(target_path), converted_filename)
            
            if os.path.exists(converted_path):
                os.rename(converted_path, target_path)
                logger.info(f"LibreOffice 변환 성공: {source_path} -> {target_path}")
                return True
            else:
                raise ConversionError(
                    "변환된 파일을 찾을 수 없습니다", 
                    source_path, 
                    Path(target_path).suffix
                )
                
        except subprocess.TimeoutExpired:
            raise ConversionError(
                "LibreOffice 변환 시간 초과", 
                source_path, 
                Path(target_path).suffix
            )
        except Exception as e:
            raise ConversionError(
                f"LibreOffice 변환 중 오류: {str(e)}", 
                source_path, 
                Path(target_path).suffix
            )


class Docx2PdfConverter(BaseConverter):
    """python-docx2pdf를 사용한 DOCX -> PDF 변환기"""
    
    def __init__(self):
        self.converter_name = "docx2pdf"
    
    def is_available(self) -> bool:
        """docx2pdf가 설치되어 있는지 확인"""
        try:
            import docx2pdf
            return True
        except ImportError:
            return False
    
    def convert(self, source_path: str, target_path: str) -> bool:
        """docx2pdf를 사용하여 DOCX를 PDF로 변환"""
        if not self.is_available():
            raise ConversionError(
                "docx2pdf가 설치되어 있지 않습니다", 
                source_path, 
                ".pdf"
            )
        
        try:
            from docx2pdf import convert
            
            logger.info(f"docx2pdf 변환 시작: {source_path} -> {target_path}")
            convert(source_path, target_path)
            
            if os.path.exists(target_path):
                logger.info(f"docx2pdf 변환 성공: {source_path} -> {target_path}")
                return True
            else:
                raise ConversionError(
                    "변환된 파일을 찾을 수 없습니다", 
                    source_path, 
                    ".pdf"
                )
                
        except Exception as e:
            raise ConversionError(
                f"docx2pdf 변환 중 오류: {str(e)}", 
                source_path, 
                ".pdf"
            )


class Pptx2PdfConverter(BaseConverter):
    """python-pptx2pdf를 사용한 PPTX -> PDF 변환기"""
    
    def __init__(self):
        self.converter_name = "pptx2pdf"
    
    def is_available(self) -> bool:
        """pptx2pdf가 설치되어 있는지 확인"""
        try:
            import pptx2pdf
            return True
        except ImportError:
            return False
    
    def convert(self, source_path: str, target_path: str) -> bool:
        """pptx2pdf를 사용하여 PPTX를 PDF로 변환"""
        if not self.is_available():
            raise ConversionError(
                "pptx2pdf가 설치되어 있지 않습니다", 
                source_path, 
                ".pdf"
            )
        
        try:
            from pptx2pdf import convert
            
            logger.info(f"pptx2pdf 변환 시작: {source_path} -> {target_path}")
            convert(source_path, target_path)
            
            if os.path.exists(target_path):
                logger.info(f"pptx2pdf 변환 성공: {source_path} -> {target_path}")
                return True
            else:
                raise ConversionError(
                    "변환된 파일을 찾을 수 없습니다", 
                    source_path, 
                    ".pdf"
                )
                
        except Exception as e:
            raise ConversionError(
                f"pptx2pdf 변환 중 오류: {str(e)}", 
                source_path, 
                ".pdf"
            )


class ConverterFactory:
    """변환기 팩토리 클래스"""
    
    @staticmethod
    def get_best_converter(source_format: str, target_format: str) -> BaseConverter:
        """
        주어진 변환에 가장 적합한 변환기를 반환합니다.
        
        Args:
            source_format: 원본 파일 형식 (예: "docx", "pptx")
            target_format: 대상 파일 형식 (예: "pdf")
            
        Returns:
            사용 가능한 최적의 변환기
            
        Raises:
            ConversionError: 사용 가능한 변환기가 없을 때
        """
        converters = []
        
        if source_format == "docx" and target_format == "pdf":
            converters = [Docx2PdfConverter(), LibreOfficeConverter()]
        elif source_format == "pptx" and target_format == "pdf":
            converters = [Pptx2PdfConverter(), LibreOfficeConverter()]
        elif source_format == "xlsx" and target_format == "pdf":
            converters = [LibreOfficeConverter()]
        else:
            converters = [LibreOfficeConverter()]
        
        # 사용 가능한 변환기 찾기
        for converter in converters:
            if converter.is_available():
                logger.info(f"선택된 변환기: {converter.converter_name}")
                return converter
        
        # 사용 가능한 변환기가 없음
        raise ConversionError(
            f"사용 가능한 변환기를 찾을 수 없습니다: {source_format} -> {target_format}",
            "",
            target_format
        ) 