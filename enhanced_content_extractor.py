#!/usr/bin/env python3
"""
향상된 메일 내용 추출기
HTML 정제 + unstructured 라이브러리로 핵심 내용만 추출
"""

import re
import html
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import html2text
from unstructured.partition.html import partition_html
from unstructured.chunking.title import chunk_by_title
from unstructured.staging.base import convert_to_dict


class EnhancedContentExtractor:
    """향상된 메일 내용 추출기"""
    
    def __init__(self):
        """초기화"""
        # html2text 설정
        self.html2text_converter = html2text.HTML2Text()
        self.html2text_converter.ignore_links = True
        self.html2text_converter.ignore_images = True
        self.html2text_converter.body_width = 0
        self.html2text_converter.unicode_snob = True
        self.html2text_converter.escape_all = False
        
        # 불필요한 패턴들
        self.noise_patterns = [
            # Microsoft 메일 특수 패턴
            r'<meta[^>]*>',
            r'<style[^>]*>.*?</style>',
            r'<script[^>]*>.*?</script>',
            r'<!DOCTYPE[^>]*>',
            r'<!--.*?-->',
            
            # 추적용 이미지 및 링크
            r'<img[^>]*aria-hidden[^>]*>',
            r'<img[^>]*role="presentation"[^>]*>',
            r'<img[^>]*height="1"[^>]*width="1"[^>]*>',
            
            # 자동 생성 메일 패턴
            r'You are receiving this email because.*?',
            r'Privacy\s*Statement.*?',
            r'https://[^\s]*tracking[^\s]*',
            r'https://[^\s]*unsubscribe[^\s]*',
            
            # 반복되는 빈 태그들
            r'<p[^>]*>\s*</p>',
            r'<div[^>]*>\s*</div>',
            r'<span[^>]*>\s*</span>',
            
            # 과도한 공백
            r'\n\s*\n\s*\n',
            r'\r\n\s*\r\n\s*\r\n',
        ]
        
        # 중요한 콘텐츠 식별 패턴
        self.important_patterns = [
            # 업무 관련 키워드
            r'(?i)(urgent|important|deadline|meeting|project|task|issue|bug|error)',
            r'(?i)(request|approve|review|feedback|action|required)',
            r'(?i)(schedule|appointment|conference|call)',
            
            # 연락처 정보
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'\+?[\d\s\-\(\)]{10,}',
            
            # 날짜/시간
            r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',
            r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)?',
        ]

    def extract_clean_content(self, content: str, content_type: str = 'html') -> Dict[str, str]:
        """메일 내용에서 핵심 정보만 추출"""
        
        if not content or not content.strip():
            return {
                'cleaned_text': '',
                'summary': '',
                'key_points': [],
                'extraction_method': 'empty_content'
            }
        
        try:
            if content_type.lower() == 'html':
                return self._extract_from_html(content)
            else:
                return self._extract_from_text(content)
                
        except Exception as e:
            # 폴백: 기본 텍스트 정리
            return {
                'cleaned_text': self._basic_text_clean(content),
                'summary': self._basic_text_clean(content)[:200] + "..." if len(content) > 200 else self._basic_text_clean(content),
                'key_points': [],
                'extraction_method': f'fallback_due_to_error: {str(e)}'
            }

    def _extract_from_html(self, html_content: str) -> Dict[str, str]:
        """HTML 콘텐츠에서 정보 추출"""
        
        # 1단계: HTML 구조 정리
        cleaned_html = self._clean_html_structure(html_content)
        
        # 2단계: unstructured로 구조화된 추출
        try:
            elements = partition_html(text=cleaned_html)
            
            # 3단계: 요소별 분류 및 정리
            text_elements = []
            important_elements = []
            
            for element in elements:
                element_text = str(element).strip()
                if element_text:
                    text_elements.append(element_text)
                    
                    # 중요한 내용 식별
                    if self._is_important_content(element_text):
                        important_elements.append(element_text)
            
            # 4단계: 최종 정리
            cleaned_text = self._merge_and_clean_text(text_elements)
            summary = self._generate_summary(important_elements, cleaned_text)
            key_points = self._extract_key_points(important_elements)
            
            return {
                'cleaned_text': cleaned_text,
                'summary': summary,
                'key_points': key_points,
                'extraction_method': 'unstructured_html'
            }
            
        except Exception as e:
            # unstructured 실패 시 html2text 폴백
            return self._extract_with_html2text(cleaned_html)

    def _extract_from_text(self, text_content: str) -> Dict[str, str]:
        """일반 텍스트에서 정보 추출"""
        
        try:
            # unstructured로 텍스트 구조화
            lines = text_content.split('\n')
            cleaned_lines = []
            important_lines = []
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 3:  # 의미있는 길이의 라인만
                    cleaned_lines.append(line)
                    
                    if self._is_important_content(line):
                        important_lines.append(line)
            
            cleaned_text = '\n'.join(cleaned_lines)
            summary = self._generate_summary(important_lines, cleaned_text)
            key_points = self._extract_key_points(important_lines)
            
            return {
                'cleaned_text': cleaned_text,
                'summary': summary,
                'key_points': key_points,
                'extraction_method': 'structured_text'
            }
            
        except Exception as e:
            return {
                'cleaned_text': self._basic_text_clean(text_content),
                'summary': text_content[:200] + "..." if len(text_content) > 200 else text_content,
                'key_points': [],
                'extraction_method': f'text_fallback: {str(e)}'
            }

    def _clean_html_structure(self, html_content: str) -> str:
        """HTML 구조 정리"""
        
        # 불필요한 패턴 제거
        for pattern in self.noise_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # BeautifulSoup으로 구조 정리
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 불필요한 태그 제거
            for tag in soup.find_all(['script', 'style', 'meta', 'link']):
                tag.decompose()
            
            # 빈 태그 제거
            for tag in soup.find_all():
                if not tag.get_text(strip=True) and not tag.find_all():
                    tag.decompose()
            
            return str(soup)
            
        except Exception:
            return html_content

    def _extract_with_html2text(self, html_content: str) -> Dict[str, str]:
        """html2text를 사용한 폴백 추출"""
        
        try:
            text = self.html2text_converter.handle(html_content)
            cleaned_text = self._basic_text_clean(text)
            
            # 중요한 라인 추출
            lines = cleaned_text.split('\n')
            important_lines = [line for line in lines if self._is_important_content(line)]
            
            summary = self._generate_summary(important_lines, cleaned_text)
            key_points = self._extract_key_points(important_lines)
            
            return {
                'cleaned_text': cleaned_text,
                'summary': summary,
                'key_points': key_points,
                'extraction_method': 'html2text_fallback'
            }
            
        except Exception as e:
            return {
                'cleaned_text': self._basic_text_clean(html_content),
                'summary': '',
                'key_points': [],
                'extraction_method': f'html2text_error: {str(e)}'
            }

    def _basic_text_clean(self, text: str) -> str:
        """기본 텍스트 정리"""
        
        if not text:
            return ""
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        # 과도한 공백 정리
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 특수문자 정리
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}@#\$%\^&\*\+\=\|\\\/\'\"`~<>]', '', text)
        
        return text.strip()

    def _merge_and_clean_text(self, text_elements: List[str]) -> str:
        """텍스트 요소들을 병합하고 정리"""
        
        if not text_elements:
            return ""
        
        # 중복 제거
        unique_elements = []
        seen = set()
        
        for element in text_elements:
            element_clean = element.strip().lower()
            if element_clean and element_clean not in seen and len(element_clean) > 5:
                unique_elements.append(element.strip())
                seen.add(element_clean)
        
        # 의미있는 순서로 재배열
        merged_text = '\n'.join(unique_elements)
        return self._basic_text_clean(merged_text)

    def _is_important_content(self, text: str) -> bool:
        """중요한 내용인지 판단"""
        
        if not text or len(text.strip()) < 10:
            return False
        
        # 중요한 패턴 매칭
        for pattern in self.important_patterns:
            if re.search(pattern, text):
                return True
        
        # 길이 기반 중요도 (너무 짧거나 너무 긴 것 제외)
        if 10 <= len(text.strip()) <= 500:
            return True
        
        return False

    def _generate_summary(self, important_elements: List[str], full_text: str) -> str:
        """요약 생성"""
        
        if important_elements:
            # 중요한 요소들로 요약 생성
            summary = ' '.join(important_elements[:3])  # 처음 3개 중요 요소
        else:
            # 전체 텍스트에서 첫 200자
            summary = full_text
        
        # 길이 제한
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        return summary.strip()

    def _extract_key_points(self, important_elements: List[str]) -> List[str]:
        """핵심 포인트 추출"""
        
        key_points = []
        
        for element in important_elements[:5]:  # 최대 5개
            element = element.strip()
            if len(element) > 15 and len(element) < 200:  # 적절한 길이
                key_points.append(element)
        
        return key_points


def test_enhanced_extractor():
    """테스트 함수"""
    
    extractor = EnhancedContentExtractor()
    
    # HTML 테스트
    html_test = """
    <html>
    <head><style>body{color:red}</style></head>
    <body>
        <p>Hi John,</p>
        <p>We need to schedule an urgent meeting about the project deadline.</p>
        <p>Please contact me at john.doe@company.com or call +1-555-0123.</p>
        <p>Meeting time: 2024-12-15 at 2:00 PM</p>
        <div style="color:gray">This is an automated message...</div>
    </body>
    </html>
    """
    
    result = extractor.extract_clean_content(html_test, 'html')
    print("HTML 테스트 결과:")
    print(f"정리된 텍스트: {result['cleaned_text'][:100]}...")
    print(f"요약: {result['summary']}")
    print(f"핵심 포인트: {result['key_points']}")
    print(f"추출 방법: {result['extraction_method']}")


if __name__ == "__main__":
    test_enhanced_extractor()