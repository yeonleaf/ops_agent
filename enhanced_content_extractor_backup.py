#!/usr/bin/env python3
"""
향상된 메일 내용 추출기
HTML 정제 + 정규식 + 중복 제거로 핵심 내용만 추출
"""

import re
import html
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import logging

# 로거 설정
logger = logging.getLogger(__name__)


class EnhancedContentExtractor:
    """향상된 메일 내용 추출기"""
    
    def __init__(self):
        """초기화"""
        # 불필요한 패턴들 (이미지 태그는 제외)
        self.noise_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<meta[^>]*>',
            r'<link[^>]*>',
            r'<!--.*?-->',
            r'You are receiving this email because.*?',
            r'Privacy\s*Statement.*?',
            r'This email is generated through.*?',
            r'Notification settings:.*?',
            r'Unsubscribe.*?',
            r'Contoso\'s use of Microsoft 365.*?',
            # CSS 스타일 패턴들
            r'[a-zA-Z0-9_-]+\s*\{[^}]*\}',
            r'@media[^{]*\{[^}]*\}',
            r'/\*.*?\*/',
            r'#[a-zA-Z0-9_-]+\s*\{[^}]*\}',
            r'\.[a-zA-Z0-9_-]+\s*\{[^}]*\}',
            r'[a-zA-Z0-9_-]+\s*:\s*[^;]+;',
            r'!important',
        ]
        
        # 중요한 패턴들
        self.important_patterns = [
            r'(?i)(urgent|important|deadline|meeting|project|task|issue|bug|error|critical)',
            r'(?i)(request|approve|review|feedback|action|required|needed)',
            r'(?i)(schedule|appointment|conference|call|meeting)',
            r'(?i)(due|deadline|expire|expiry|expires)',
            r'(?i)(order|smoothie|stuff|logistics)',
            r'(?i)(open in|browser|teams)',
            r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)?',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'\+?[\d\s\-\(\)]{10,}',
        ]

    def extract_clean_content(self, content: str, content_type: str = 'html') -> Dict[str, str]:
        """메일 내용에서 핵심 정보만 추출"""

        logger.info(f"🔍 컨텐츠 추출 시작 - 타입: {content_type}, 길이: {len(content) if content else 0}자")
        
        if not content or not content.strip():
            logger.warning("❌ 빈 컨텐츠 - 추출 중단")
            return {
                'cleaned_text': '',
                'summary': '',
                'key_points': [],
                'extraction_method': 'empty_content'
            }
        
        try:
            if content_type.lower() == 'html':
                logger.info("🔍 HTML 컨텐츠 추출 시작")
                result = self._extract_from_html(content)
                logger.info(f"✅ HTML 컨텐츠 추출 완료 - 정리된 텍스트: {len(result['cleaned_text'])}자")
                return result
            else:
                logger.info("🔍 텍스트 컨텐츠 추출 시작")
                result = self._extract_from_text(content)
                logger.info(f"✅ 텍스트 컨텐츠 추출 완료 - 정리된 텍스트: {len(result['cleaned_text'])}자")
                return result
                
        except Exception as e:
            logger.error(f"❌ 컨텐츠 추출 중 오류: {str(e)}")
            return {
                'cleaned_text': self._basic_text_clean(content),
                'summary': self._basic_text_clean(content)[:200] + "..." if len(content) > 200 else self._basic_text_clean(content),
                'key_points': [],
                'extraction_method': f'fallback_due_to_error: {str(e)}'
            }

    def _extract_from_html(self, html_content: str) -> Dict[str, str]:
        """HTML 콘텐츠에서 정보 추출"""
        
        logger.debug(f"🔍 HTML 원본 미리보기: {html_content[:200]}...")

        # 1단계: 불필요한 패턴 제거
        logger.debug("🔍 1단계: 불필요한 패턴 제거 시작")
        cleaned_html = html_content
        for pattern in self.noise_patterns:
            before_len = len(cleaned_html)
            cleaned_html = re.sub(pattern, '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
            after_len = len(cleaned_html)
            if before_len != after_len:
                logger.debug(f"   패턴 제거: {before_len} -> {after_len}자 ({before_len - after_len}자 제거)")

        # 2단계: BeautifulSoup으로 파싱
        logger.debug("🔍 2단계: BeautifulSoup 파싱")
        soup = BeautifulSoup(cleaned_html, 'html.parser')

        # 3단계: 이미지 처리 (인라인 이미지 추출)
        logger.debug("🔍 3단계: 이미지 처리 시작")
        images_found = len(soup.find_all('img'))
        logger.info(f"🖼️ 발견된 이미지 수: {images_found}개")

        image_text = self._extract_image_content(soup)
        if image_text and image_text.strip():
            logger.info(f"✅ 이미지에서 텍스트 추출 성공: {len(image_text)}자")
            logger.debug(f"   추출된 이미지 텍스트: {image_text[:200]}...")
        else:
            logger.warning("❌ 이미지에서 텍스트 추출 실패 또는 빈 결과")

        # 4단계: 이미지 태그 제거 (정보 추출 후)
        logger.debug("🔍 4단계: 이미지 태그 제거")
        for img in soup.find_all('img'):
            img.decompose()

        # 5단계: 텍스트 추출
        logger.debug("🔍 5단계: 텍스트 추출")
        text = soup.get_text()
        logger.debug(f"   기본 텍스트 길이: {len(text)}자")

        # 6단계: 이미지에서 추출된 텍스트 추가
        logger.debug("🔍 6단계: 이미지 텍스트 결합")
        if image_text and image_text.strip():
            text += "\n\n[이미지에서 추출된 내용]\n" + image_text
            logger.info(f"✅ 이미지 텍스트 결합 완료 - 최종 길이: {len(text)}자")
        else:
            logger.warning("⚠️ 이미지 텍스트가 없어 결합 건너뜀")

        # 7단계: 텍스트 정리
        cleaned_text = self._clean_text(text)

        # 8단계: 중요한 정보 추출
        important_lines = self._extract_important_lines(cleaned_text)

        # 9단계: 요약 및 핵심 포인트 생성
        summary = self._generate_summary(important_lines, cleaned_text)
        key_points = self._extract_key_points(important_lines)

        return {
            'cleaned_text': cleaned_text,
            'summary': summary,
            'key_points': key_points,
            'extraction_method': 'enhanced_html_extraction_with_images'
        }

    def _extract_from_text(self, text_content: str) -> Dict[str, str]:
        """일반 텍스트에서 정보 추출"""
        
        # 텍스트 정리
        cleaned_text = self._clean_text(text_content)
        
        # 중요한 정보 추출
        important_lines = self._extract_important_lines(cleaned_text)
        
        # 요약 및 핵심 포인트 생성
        summary = self._generate_summary(important_lines, cleaned_text)
        key_points = self._extract_key_points(important_lines)
        
        return {
            'cleaned_text': cleaned_text,
            'summary': summary,
            'key_points': key_points,
            'extraction_method': 'enhanced_text_extraction'
        }

    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        
        if not text:
            return ""
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        # CSS 스타일 제거 (더 정교한 패턴)
        css_patterns = [
            # CSS 블록 패턴 (중괄호로 둘러싸인)
            r'\{[^}]*\}',  # 중괄호 블록 전체 제거
            r'@media[^{]*\{[^}]*\}',  # 미디어 쿼리
            r'/\*.*?\*/',  # CSS 주석
            r'@import[^;]*;',  # import 문
            r'@font-face[^}]*\}',  # font-face

            # CSS 속성들 (더 구체적인 패턴)
            r'(?:color|background|font|margin|padding|border|width|height|position|display|float|text-align|text-decoration):[^;]+;',
            r'(?:top|left|right|bottom|z-index|opacity|visibility|overflow):[^;]+;',

            # CSS 선택자 (더 안전한 패턴)
            r'^\s*\.[a-zA-Z0-9_-]+\s*$',  # 단독 클래스명 라인
            r'^\s*#[a-zA-Z0-9_-]+\s*$',  # 단독 ID 라인

            # !important
            r'!important',
        ]

        for pattern in css_patterns:
            text = re.sub(pattern, ' ', text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
        
        # 과도한 공백 정리
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 특수문자 정리
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}@#\$%\^&\*\+\=\|\\\/\'\"`~<>]', ' ', text)
        
        # 문장 단위로 분리 (더 정교한 분리)
        # 마침표, 느낌표, 물음표, 줄바꿈으로 문장 분리
        sentences = re.split(r'[.!?\n]+', text)
        
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 5:
                # CSS 잔재 제거 (문장 단위)
                sentence = re.sub(r'^[0-9]+\s*', '', sentence)  # 숫자로 시작하는 패턴
                sentence = re.sub(r'^[a-zA-Z0-9_-]+\s*$', '', sentence)  # CSS 클래스명만 있는 라인
                sentence = re.sub(r'^[#\.][a-zA-Z0-9_-]+\s*$', '', sentence)  # CSS 선택자만 있는 라인
                sentence = re.sub(r'^[a-zA-Z0-9_-]+\s*:\s*$', '', sentence)  # CSS 속성명만 있는 라인
                sentence = re.sub(r'^[a-zA-Z0-9_-]+\s*,\s*#\s*$', '', sentence)  # "Reddit , #" 같은 패턴
                sentence = re.sub(r'^[a-zA-Z0-9_-]+\s*,\s*$', '', sentence)  # "Reddit ," 같은 패턴
                
                if sentence and len(sentence) > 5:
                    # 추가로 특정 키워드로 분리
                    sub_sentences = re.split(r'(?i)(open in|due in|in the plan|privacy statement)', sentence)
                    for sub_sentence in sub_sentences:
                        sub_sentence = sub_sentence.strip()
                        if sub_sentence and len(sub_sentence) > 3:
                            cleaned_sentences.append(sub_sentence)
        
        # 중복 제거 (순서 유지)
        unique_sentences = []
        seen = set()
        
        for sentence in cleaned_sentences:
            if sentence not in seen:
                unique_sentences.append(sentence)
                seen.add(sentence)
        
        return '\n'.join(unique_sentences)

    def _extract_important_lines(self, text: str) -> List[str]:
        """중요한 라인 추출"""
        
        lines = text.split('\n')
        important_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 5:
                # 중요한 패턴 확인
                is_important = False
        for pattern in self.important_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        is_important = True
                        break
                
                # 길이 기반 중요도
                if not is_important and 10 <= len(line) <= 500:
                    is_important = True
                
                if is_important:
                    important_lines.append(line)
        
        return important_lines

    def _generate_summary(self, important_lines: List[str], full_text: str) -> str:
        """요약 생성"""
        
        if important_lines:
            # 중요한 라인들로 요약 생성 (중복 제거)
            summary_parts = []
            for line in important_lines[:3]:
                if line not in summary_parts:
                    summary_parts.append(line)
            summary = ' | '.join(summary_parts)
        else:
            # 전체 텍스트에서 첫 200자
            summary = full_text
        
        # 길이 제한
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        return summary.strip()

    def _extract_key_points(self, important_lines: List[str]) -> List[str]:
        """핵심 포인트 추출"""
        
        key_points = []
        
        for line in important_lines[:5]:
            line = line.strip()
            if len(line) > 15 and len(line) < 300:
                if line not in key_points:
                    key_points.append(line)
        
        return key_points[:5]

    def _extract_image_content(self, soup: BeautifulSoup) -> str:
        """HTML에서 인라인 이미지 정보 추출"""
        try:
            image_texts = []
            images = soup.find_all('img')

            logger.debug(f"🖼️ 이미지 태그 {len(images)}개 발견")

            for i, img in enumerate(images, 1):
                logger.debug(f"🖼️ 이미지 {i} 처리 시작")

                # Alt 텍스트 추출
                alt_text = img.get('alt', '')
                if alt_text:
                    logger.debug(f"   Alt 텍스트: '{alt_text}'")

                # Title 속성 추출
                title_text = img.get('title', '')
                if title_text:
                    logger.debug(f"   Title 텍스트: '{title_text}'")

                # src 분석 (base64 인코딩된 이미지인지 확인)
                src = img.get('src', '')
                logger.debug(f"   Src: '{src[:100]}{'...' if len(src) > 100 else ''}'")

                # 이미지 설명 생성
                img_description = []

                # Alt 텍스트가 있으면 우선 사용
                if alt_text and alt_text.strip():
                    img_description.append(alt_text.strip())
                elif title_text and title_text.strip():
                    img_description.append(title_text.strip())

                # 이미지 타입별 처리
                if src.startswith('data:image'):
                    # Base64 인코딩된 이미지
                    if not any('인라인' in desc for desc in img_description):
                        img_description.append("인라인 이미지")
                    logger.info(f"🖼️ Base64 이미지 발견 - 텍스트 추출 시도")

                    # base64 이미지에서 텍스트 추출 시도
                    extracted_text = self._extract_text_from_base64_image(src)
                    if extracted_text and extracted_text.strip() and '텍스트 추출 실패' not in extracted_text:
                        img_description.append(f"추출된 텍스트: {extracted_text}")
                        logger.info(f"✅ Base64 이미지에서 텍스트 추출 성공: {len(extracted_text)}자")
                    else:
                        logger.warning("❌ Base64 이미지에서 텍스트 추출 실패")

                elif 'cid:' in src:
                    # 첨부된 이미지
                    if not any('첨부' in desc for desc in img_description):
                        img_description.append("첨부된 이미지")
                    logger.debug("🖼️ 첨부 이미지 (CID) 발견")

                elif src:
                    # 외부 이미지 URL 처리
                    if 'user=' in src and 'end=' in src:
                        if not any('사용자' in desc for desc in img_description):
                            img_description.append("사용자 관련 이미지")
                    elif 'http' in src:
                        # URL에서 도메인만 추출
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(src)
                            domain = parsed.netloc
                            if domain and not any(domain in desc for desc in img_description):
                                img_description.append(f"외부 이미지 ({domain})")
                        except:
                            if not any('외부' in desc for desc in img_description):
                                img_description.append("외부 이미지")
                    else:
                        if not any('외부' in desc for desc in img_description):
                            img_description.append("외부 이미지")
                    logger.debug("🖼️ 외부 이미지 URL 발견")

                if img_description:
                    # 의미있는 설명이 있으면 간단하게 표시
                    if len(img_description) == 1 and not any(x in img_description[0].lower() for x in ['외부 이미지', '인라인 이미지', '첨부된 이미지']):
                        image_texts.append(f"이미지 {i}: {img_description[0]}")
                    else:
                        # 여러 정보가 있으면 결합
                        combined_desc = '; '.join(img_description)
                        image_texts.append(f"이미지 {i}: {combined_desc}")
                    logger.debug(f"✅ 이미지 {i} 정보 수집 완료")
                else:
                    image_texts.append(f"이미지 {i}: 이미지")
                    logger.debug(f"⚠️ 이미지 {i} 정보 없음")

            result = '\n'.join(image_texts) if image_texts else ""
            logger.info(f"🖼️ 전체 이미지 정보 추출 완료: {len(result)}자")
            return result

        except Exception as e:
            logger.error(f"❌ 이미지 처리 중 오류: {str(e)}")
            return f"이미지 처리 중 오류: {str(e)}"

    def _extract_text_from_base64_image(self, base64_src: str) -> str:
        """Base64 인코딩된 이미지에서 텍스트 추출"""
        try:
            import base64
            import io
            from PIL import Image
            import os

            # data:image/png;base64,iVBORw0KGgoAAAA... 형식에서 base64 부분 추출
            if ';base64,' in base64_src:
                base64_data = base64_src.split(';base64,')[1]
            else:
                return ""

            # base64 디코딩
            image_data = base64.b64decode(base64_data)

            # PIL Image로 변환
            image = Image.open(io.BytesIO(image_data))

            # 임시 파일로 저장
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                image.save(temp_file.name, 'PNG')
                temp_path = temp_file.name

            try:
                # Azure Vision API로 텍스트 추출 시도
                azure_text = self._extract_with_azure_vision(temp_path)
                if azure_text and len(azure_text.strip()) > 10:
                    return azure_text

                # Tesseract로 텍스트 추출 시도
                tesseract_text = self._extract_with_tesseract(temp_path)
                if tesseract_text and len(tesseract_text.strip()) > 5:
                    return tesseract_text

                return "텍스트 추출 실패"

            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return f"Base64 이미지 처리 오류: {str(e)}"

    def _extract_with_azure_vision(self, image_path: str) -> str:
        """Azure Vision API로 이미지에서 텍스트 추출"""
        try:
            import requests
            import time
            import os

            endpoint = os.getenv("AZURE_VISION_ENDPOINT")
            key = os.getenv("AZURE_VISION_KEY")

            if not endpoint or not key:
                return ""

            # 이미지 파일 읽기
            with open(image_path, 'rb') as image_data:
                image_bytes = image_data.read()

            # OCR API 호출
            ocr_url = f"{endpoint}/vision/v3.2/read/analyze"
            headers = {
                'Ocp-Apim-Subscription-Key': key,
                'Content-Type': 'application/octet-stream'
            }

            response = requests.post(ocr_url, headers=headers, data=image_bytes)
            response.raise_for_status()

            # 결과 URL 가져오기
            operation_location = response.headers["Operation-Location"]

            # 결과 대기 및 가져오기
            for i in range(10):  # 2초씩 10번 = 20초
                time.sleep(2)
                result_response = requests.get(operation_location, headers={'Ocp-Apim-Subscription-Key': key})
                result = result_response.json()

                if result["status"] == "succeeded":
                    # 텍스트 추출
                    extracted_text = ""
                    for page in result.get("analyzeResult", {}).get("readResults", []):
                        for line in page.get("lines", []):
                            extracted_text += line.get("text", "") + "\n"

                    return extracted_text.strip()
                elif result["status"] == "failed":
                    break

            return ""

        except Exception:
            return ""

    def _extract_with_tesseract(self, image_path: str) -> str:
        """Tesseract로 이미지에서 텍스트 추출"""
        try:
            import pytesseract
            from PIL import Image

            # 이미지 열기
            image = Image.open(image_path)

            # OCR 수행
            text = pytesseract.image_to_string(image, lang='kor+eng')

            return text.strip()

        except ImportError:
            return ""
        except Exception:
            return ""

    def _basic_text_clean(self, text: str) -> str:
        """기본 텍스트 정리 (폴백용)"""
        
        if not text:
            return ""
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        # 과도한 공백 정리
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()


def test_enhanced_extractor():
    """테스트 함수"""
    
    extractor = EnhancedContentExtractor()
    
    # HTML 테스트
    html_test = """
    <html>
    <head><style>body{color:red}</style></head>
    <body>
        <h2>Urgent Meeting Request</h2>
        <p>Hi John,</p>
        <p>We need to schedule an <strong>urgent meeting</strong> about the project deadline.</p>
        <p>Please contact me at <a href="mailto:john.doe@company.com">john.doe@company.com</a> or call +1-555-0123.</p>
        <p>Meeting time: <strong>2024-12-15 at 2:00 PM</strong></p>
        <div style="color:gray">This is an automated message...</div>
        <table><tr><td>Unsubscribe</td></tr></table>
    </body>
    </html>
    """
    
    result = extractor.extract_clean_content(html_test, 'html')
    print("향상된 HTML 테스트 결과:")
    print(f"정리된 텍스트:\n{result['cleaned_text']}")
    print(f"\n요약: {result['summary']}")
    print(f"핵심 포인트: {result['key_points']}")
    print(f"추출 방법: {result['extraction_method']}")


if __name__ == "__main__":
    test_enhanced_extractor()