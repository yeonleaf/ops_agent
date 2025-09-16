#!/usr/bin/env python3
"""
이미지 포함 메일 콘텐츠 추출 테스트
"""

from enhanced_content_extractor import EnhancedContentExtractor

def test_css_removal():
    """CSS 제거 테스트"""
    print("🧪 CSS 제거 테스트")
    print("=" * 50)

    extractor = EnhancedContentExtractor()

    # CSS가 포함된 HTML 테스트
    html_with_css = """
    <html>
    <head>
        <style>
        body { color: red; font-size: 14px; }
        .container { margin: 10px; padding: 5px; }
        #header { background: blue; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 id="header">긴급 회의 요청</h1>
            <p style="color: green; font-weight: bold;">안녕하세요,</p>
            <p>다음 주 월요일 오후 2시에 프로젝트 회의가 있습니다.</p>
            <p>참석 부탁드립니다.</p>
        </div>
        <!-- CSS 주석 -->
        <div style="display: none;">숨겨진 내용</div>
    </body>
    </html>
    """

    result = extractor.extract_clean_content(html_with_css, 'html')

    print("원본 HTML:")
    print(html_with_css[:200] + "...")
    print(f"\n정제된 텍스트:")
    print(result['cleaned_text'])
    print(f"\n요약: {result['summary']}")
    print(f"핵심 포인트: {result['key_points']}")

def test_image_extraction():
    """이미지 포함 HTML 테스트"""
    print("\n🖼️ 이미지 포함 HTML 테스트")
    print("=" * 50)

    extractor = EnhancedContentExtractor()

    # 이미지가 포함된 HTML
    html_with_images = """
    <html>
    <body>
        <h2>업무 보고</h2>
        <p>첨부된 이미지를 확인해주세요.</p>
        <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" alt="샘플 이미지" title="프로젝트 차트">
        <p>위 차트에서 보듯이 성과가 개선되었습니다.</p>
        <img src="cid:attachment1" alt="월별 보고서">
        <img src="https://example.com/chart.png" alt="외부 차트">
        <p>질문이 있으시면 연락주세요.</p>
    </body>
    </html>
    """

    result = extractor.extract_clean_content(html_with_images, 'html')

    print("원본 HTML:")
    print(html_with_images[:300] + "...")
    print(f"\n정제된 텍스트:")
    print(result['cleaned_text'])
    print(f"\n요약: {result['summary']}")
    print(f"핵심 포인트: {result['key_points']}")

    # 이미지 추출 함수 직접 테스트
    print(f"\n🔍 이미지 추출 함수 직접 테스트:")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_with_images, 'html.parser')
    image_content = extractor._extract_image_content(soup)
    print(f"추출된 이미지 정보:")
    print(repr(image_content))
    print(f"이미지 정보 길이: {len(image_content)}")
    print(f"이미지 정보가 있는가? {bool(image_content and image_content.strip())}")

    # 내부 과정 디버깅
    print(f"\n🔍 HTML 처리 과정 디버깅:")
    import re
    html_content = html_with_images

    # 1단계: 불필요한 패턴 제거
    cleaned_html = html_content
    for pattern in extractor.noise_patterns:
        cleaned_html = re.sub(pattern, '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)

    # 2단계: BeautifulSoup으로 파싱
    soup = BeautifulSoup(cleaned_html, 'html.parser')

    # 3단계: 이미지 처리
    image_text = extractor._extract_image_content(soup)
    print(f"이미지 텍스트: {repr(image_text)}")

    # 4단계: 텍스트 추출
    text = soup.get_text()
    print(f"기본 텍스트: {repr(text[:200])}")

    # 5단계: 이미지 텍스트 추가
    if image_text and image_text.strip():
        text += "\n\n[이미지에서 추출된 내용]\n" + image_text
        print(f"이미지 텍스트가 추가됨")
    else:
        print(f"이미지 텍스트가 추가되지 않음")

    print(f"최종 텍스트: {repr(text[:400])}")

def test_mixed_content():
    """CSS + 이미지 혼합 컨텐츠 테스트"""
    print("\n🔧 CSS + 이미지 혼합 테스트")
    print("=" * 50)

    extractor = EnhancedContentExtractor()

    # 복잡한 HTML (CSS + 이미지)
    complex_html = """
    <html>
    <head>
        <style>
        .email-body { font-family: Arial; background: #f5f5f5; }
        .header { color: #333; border-bottom: 1px solid #ccc; }
        .content { padding: 20px; }
        .image-section { text-align: center; margin: 15px 0; }
        </style>
    </head>
    <body class="email-body">
        <div class="header">
            <h1 style="color: red !important;">🚨 시스템 장애 보고</h1>
        </div>
        <div class="content">
            <p>안녕하세요,</p>
            <p style="font-weight: bold; color: #d00;">긴급히 확인이 필요한 시스템 장애가 발생했습니다.</p>
            <div class="image-section">
                <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                     alt="시스템 에러 로그" title="에러 상세 정보">
                <p>위 스크린샷은 현재 에러 상황을 보여줍니다.</p>
            </div>
            <p>즉시 대응이 필요합니다.</p>
            <p>담당자: 김개발 (<a href="mailto:dev@company.com">dev@company.com</a>)</p>
        </div>
        <div style="font-size: 12px; color: #666; margin-top: 30px;">
            이 메일은 자동으로 생성된 시스템 알림입니다.
        </div>
    </body>
    </html>
    """

    result = extractor.extract_clean_content(complex_html, 'html')

    print("원본 HTML:")
    print(complex_html[:400] + "...")
    print(f"\n정제된 텍스트:")
    print(result['cleaned_text'])
    print(f"\n요약: {result['summary']}")
    print(f"핵심 포인트: {result['key_points']}")
    print(f"추출 방법: {result['extraction_method']}")

if __name__ == "__main__":
    test_css_removal()
    test_image_extraction()
    test_mixed_content()