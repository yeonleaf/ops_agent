#!/usr/bin/env python3
"""
개선된 Gmail 메일 본문 추출 로직 테스트
"""

import logging
import sys
import base64
from typing import Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

# Gmail Provider에서 함수만 직접 가져와서 테스트
import sys
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

def create_test_payload():
    """NCMSAPI 메일과 유사한 복잡한 멀티파트 구조 생성"""

    # 실제 HTML 컨텐츠 (Base64 인코딩)
    html_content = """
    <html>
    <head>
        <style>
        body { font-family: Arial; background: #f9f9f9; }
        .container { padding: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>NCMSAPI Batch 확인 요청</h2>
            <p>안녕하세요, 개발팀입니다.</p>
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                 alt="시스템 스크린샷" title="배치 처리 현황">
            <p>위 이미지에서 확인할 수 있듯이 배치 작업이 완료되었습니다.</p>
            <p>확인 후 회신 부탁드립니다.</p>
        </div>
    </body>
    </html>
    """

    html_data = base64.urlsafe_b64encode(html_content.encode('utf-8')).decode('utf-8')

    # 복잡한 멀티파트 구조 시뮬레이션
    test_payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": base64.urlsafe_b64encode("NCMSAPI Batch 확인 요청\n\n안녕하세요, 개발팀입니다.\n배치 작업이 완료되었습니다.\n확인 후 회신 부탁드립니다.".encode('utf-8')).decode('utf-8')
                        }
                    },
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": html_data
                        }
                    }
                ]
            },
            {
                "mimeType": "application/octet-stream",
                "filename": "log.txt",
                "body": {
                    "attachmentId": "attachment123"
                }
            }
        ]
    }

    return test_payload

class MockGmailProvider:
    """테스트용 Gmail Provider"""

    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """메일 본문 추출 - 재귀적 멀티파트 처리 및 EnhancedContentExtractor 적용"""
        try:
            logging.debug(f"🔍 메일 본문 추출 시작 - MIME 타입: {payload.get('mimeType', 'unknown')}")

            # 재귀적으로 모든 파트에서 텍스트 추출
            extracted_content = self._extract_content_recursive(payload)

            if extracted_content:
                logging.info(f"✅ 메일 본문 추출 성공 - 길이: {len(extracted_content)}자")

                # EnhancedContentExtractor로 내용 정리
                try:
                    from enhanced_content_extractor import EnhancedContentExtractor
                    extractor = EnhancedContentExtractor()

                    # HTML인지 텍스트인지 판단
                    content_type = 'html' if '<' in extracted_content and '>' in extracted_content else 'text'
                    result = extractor.extract_clean_content(extracted_content, content_type, message_id)

                    cleaned_content = result.get('cleaned_text', extracted_content)
                    logging.info(f"✅ EnhancedContentExtractor 적용 완료 - 정리된 길이: {len(cleaned_content)}자")

                    return cleaned_content

                except ImportError as ie:
                    logging.warning(f"⚠️ EnhancedContentExtractor import 실패: {ie}")
                    return extracted_content
                except Exception as ee:
                    logging.warning(f"⚠️ EnhancedContentExtractor 적용 실패: {ee}")
                    return extracted_content

            logging.warning("⚠️ 메일 본문 추출 결과 없음")
            return "메일 내용을 읽을 수 없습니다."

        except Exception as e:
            logging.error(f"❌ 메일 본문 추출 실패: {str(e)}")
            return f"메일 내용 추출 실패: {str(e)}"

    def _extract_content_recursive(self, payload: Dict[str, Any]) -> str:
        """재귀적으로 메일 파트에서 텍스트 추출"""
        try:
            mime_type = payload.get('mimeType', '')

            # 단일 파트 메일 처리
            if 'parts' not in payload:
                if mime_type in ['text/plain', 'text/html']:
                    body = payload.get('body', {})
                    data = body.get('data')
                    if data:
                        content = base64.urlsafe_b64decode(data).decode('utf-8')
                        logging.debug(f"✅ 단일 파트 추출 ({mime_type}): {len(content)}자")
                        return content
                return ""

            # 멀티파트 메일 처리
            parts = payload.get('parts', [])
            logging.debug(f"🔍 멀티파트 처리 - {len(parts)}개 파트, MIME: {mime_type}")

            best_content = ""
            best_score = 0

            for i, part in enumerate(parts):
                part_mime = part.get('mimeType', '')
                logging.debug(f"🔍 파트 {i+1}: {part_mime}")

                # 재귀적으로 각 파트 처리
                part_content = self._extract_content_recursive(part)

                if part_content:
                    # 컨텐츠 우선순위 점수 계산
                    score = self._calculate_content_score(part_mime, part_content)
                    logging.debug(f"📊 파트 {i+1} 점수: {score}, 길이: {len(part_content)}자")

                    if score > best_score:
                        best_content = part_content
                        best_score = score
                        logging.debug(f"🏆 최적 콘텐츠 갱신 - 타입: {part_mime}")

            return best_content

        except Exception as e:
            logging.error(f"❌ 재귀적 콘텐츠 추출 실패: {str(e)}")
            return ""

    def _calculate_content_score(self, mime_type: str, content: str) -> int:
        """콘텐츠 우선순위 점수 계산"""
        score = 0

        # MIME 타입별 기본 점수
        if mime_type == 'text/html':
            score += 10  # HTML 우선
        elif mime_type == 'text/plain':
            score += 5   # 텍스트는 차선책

        # 콘텐츠 길이 점수
        if len(content) > 100:
            score += 3
        elif len(content) > 50:
            score += 1

        # 유의미한 콘텐츠 확인
        if any(keyword in content.lower() for keyword in ['subject', 'body', 'content', '제목', '내용']):
            score += 2

        return score

def test_improved_extraction():
    """개선된 메일 본문 추출 테스트"""

    print("=" * 80)
    print("🧪 개선된 Gmail 메일 본문 추출 테스트")
    print("=" * 80)

    # Mock Gmail Provider 생성 (인증 없이 테스트)
    provider = MockGmailProvider()

    # 테스트 페이로드 생성
    test_payload = create_test_payload()
    print(f"📧 테스트 페이로드 생성 완료 - MIME: {test_payload['mimeType']}")
    print(f"📧 파트 수: {len(test_payload['parts'])}개")

    # 메일 본문 추출 테스트
    print("\n" + "="*60)
    print("🔍 메일 본문 추출 테스트")
    print("="*60)

    try:
        extracted_body = provider._extract_email_body(test_payload)

        print(f"✅ 추출 성공")
        print(f"   - 추출된 본문 길이: {len(extracted_body)}자")
        print(f"   - 추출된 본문 미리보기:")
        print(f"     {extracted_body[:200]}...")

        # 이미지 정보 포함 여부 확인
        has_image_info = "[이미지에서 추출된 내용]" in extracted_body
        print(f"   - 이미지 정보 포함: {'✅' if has_image_info else '❌'}")

        # CSS 제거 여부 확인
        has_css = any(css_keyword in extracted_body.lower() for css_keyword in ['<style', 'font-family', 'background'])
        print(f"   - CSS 제거됨: {'✅' if not has_css else '❌'}")

        if has_image_info:
            # 이미지 부분 추출해서 보기
            image_part = extracted_body.split("[이미지에서 추출된 내용]")[1]
            print(f"   - 추출된 이미지 정보:")
            print(f"     {image_part[:100]}...")

    except Exception as e:
        print(f"❌ 추출 실패: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("🧪 테스트 완료")
    print("="*80)

if __name__ == "__main__":
    test_improved_extraction()