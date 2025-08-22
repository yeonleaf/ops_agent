#!/usr/bin/env python3
"""
공통 타입 정의
"""

from enum import Enum
from typing import Dict, List, Any
from dataclasses import dataclass, field

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

@dataclass
class ContentMetrics:
    """콘텐츠 분석 메트릭"""
    # 텍스트 관련
    text_length: int = 0
    word_count: int = 0
    line_count: int = 0
    paragraph_count: int = 0
    avg_line_length: float = 0.0
    
    # 이미지 관련
    image_count: int = 0
    image_area_ratio: float = 0.0  # 이미지가 차지하는 비율
    large_image_count: int = 0  # 큰 이미지 개수
    
    # 표 관련
    table_count: int = 0
    table_cell_count: int = 0
    table_area_ratio: float = 0.0
    
    # 레이아웃 관련
    text_block_count: int = 0
    text_density: float = 0.0  # 페이지 당 텍스트 밀도
    whitespace_ratio: float = 0.0
    font_variation: int = 0  # 폰트 종류 수
    
    # 구조적 요소
    heading_count: int = 0
    list_count: int = 0
    hyperlink_count: int = 0
    
    # 색상 및 스타일
    color_count: int = 0
    style_variation: int = 0

@dataclass
class ClassificationResult:
    """분류 결과"""
    content_type: ContentType
    confidence: float  # 0.0 ~ 1.0
    reasoning: List[str] = field(default_factory=list)  # 판별 근거
    metrics: ContentMetrics = field(default_factory=ContentMetrics)
    feature_scores: Dict[str, float] = field(default_factory=dict)  # 각 특성별 점수