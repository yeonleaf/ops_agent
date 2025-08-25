"""
파일 처리 시스템을 위한 사용자 정의 예외 클래스들
"""

class ProcessingError(Exception):
    """파일 처리 중 발생하는 일반적인 오류"""
    
    def __init__(self, message: str, file_path: str = None, error_code: str = None):
        self.message = message
        self.file_path = file_path
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """예외를 JSON 직렬화 가능한 딕셔너리로 변환"""
        return {
            "error": True,
            "error_type": self.__class__.__name__,
            "message": self.message,
            "file_path": self.file_path,
            "error_code": self.error_code
        }


class FileTypeNotSupportedError(ProcessingError):
    """지원하지 않는 파일 타입"""
    
    def __init__(self, file_path: str, file_type: str):
        message = f"지원하지 않는 파일 타입: {file_type}"
        super().__init__(message, file_path, "UNSUPPORTED_FILE_TYPE")


class ConversionError(ProcessingError):
    """파일 변환 중 발생하는 오류"""
    
    def __init__(self, message: str, source_file: str, target_format: str):
        message = f"파일 변환 실패 ({source_file} -> {target_format}): {message}"
        super().__init__(message, source_file, "CONVERSION_FAILED")


class ContentExtractionError(ProcessingError):
    """콘텐츠 추출 중 발생하는 오류"""
    
    def __init__(self, message: str, file_path: str, element_type: str = None):
        message = f"콘텐츠 추출 실패: {message}"
        super().__init__(message, file_path, "CONTENT_EXTRACTION_FAILED")


class MetadataError(ProcessingError):
    """메타데이터 처리 중 발생하는 오류"""
    
    def __init__(self, message: str, file_path: str):
        message = f"메타데이터 처리 실패: {message}"
        super().__init__(message, file_path, "METADATA_ERROR") 