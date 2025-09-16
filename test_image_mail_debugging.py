#!/usr/bin/env python3
"""
이미지 포함 메일의 벡터 DB 저장 및 검색 디버깅 테스트
"""

import logging
import sys
import os
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_image_mail_debug.log')
    ]
)

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

from enhanced_content_extractor import EnhancedContentExtractor
from vector_db_models import VectorDBManager, Mail

def test_image_mail_pipeline():
    """이미지 포함 메일의 전체 파이프라인 테스트"""

    print("=" * 80)
    print("🧪 이미지 포함 메일의 벡터 DB 파이프라인 테스트")
    print("=" * 80)

    # 1. 이미지가 포함된 HTML 메일 샘플
    html_with_image = """
    <html>
    <head>
        <style>
        body { font-family: Arial; }
        .container { padding: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>긴급 시스템 알림</h2>
            <p>시스템에 문제가 발생했습니다.</p>
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                 alt="에러 스크린샷" title="시스템 에러 화면">
            <p>위 스크린샷에서 확인할 수 있듯이 DB 연결에 문제가 있습니다.</p>
            <img src="cid:attachment1" alt="로그 파일">
            <p>즉시 조치가 필요합니다.</p>
        </div>
    </body>
    </html>
    """

    print(f"📧 테스트 메일 HTML 길이: {len(html_with_image)}자")

    # 2. 콘텐츠 추출 테스트
    print("\n" + "="*60)
    print("🔍 1단계: 콘텐츠 추출 테스트")
    print("="*60)

    extractor = EnhancedContentExtractor()
    extracted_result = extractor.extract_clean_content(html_with_image, 'html')

    print(f"✅ 추출 완료:")
    print(f"   - 정리된 텍스트 길이: {len(extracted_result['cleaned_text'])}자")
    print(f"   - 요약: {extracted_result['summary']}")
    print(f"   - 핵심 포인트: {extracted_result['key_points']}")
    print(f"   - 추출 방법: {extracted_result['extraction_method']}")

    # 이미지 정보 포함 여부 확인
    has_image_info = "[이미지에서 추출된 내용]" in extracted_result['cleaned_text']
    print(f"   - 이미지 정보 포함: {'✅' if has_image_info else '❌'}")

    if has_image_info:
        # 이미지 부분만 추출해서 보기
        content = extracted_result['cleaned_text']
        if "[이미지에서 추출된 내용]" in content:
            image_part = content.split("[이미지에서 추출된 내용]")[1]
            print(f"   - 추출된 이미지 정보:\n{image_part}")

    # 3. Mail 객체 생성
    print("\n" + "="*60)
    print("🔍 2단계: Mail 객체 생성")
    print("="*60)

    test_mail = Mail(
        message_id="test_image_mail_001",
        original_content=html_with_image,
        refined_content=extracted_result['cleaned_text'],
        sender="시스템 <system@company.com>",
        status='acceptable',
        has_attachment=True,
        subject="긴급 시스템 알림",
        received_datetime=datetime.now().isoformat(),
        content_type='html',
        extraction_method=extracted_result['extraction_method'],
        content_summary=extracted_result['summary'],
        key_points=extracted_result['key_points'],
        created_at=datetime.now().isoformat()
    )

    print(f"✅ Mail 객체 생성 완료")
    print(f"   - 메시지 ID: {test_mail.message_id}")
    print(f"   - 제목: {test_mail.subject}")
    print(f"   - 정제된 콘텐츠 길이: {len(test_mail.refined_content)}자")

    # 4. Vector DB 저장 테스트
    print("\n" + "="*60)
    print("🔍 3단계: Vector DB 저장 테스트")
    print("="*60)

    vector_db = VectorDBManager()
    save_success = vector_db.save_mail(test_mail)

    if save_success:
        print("✅ Vector DB 저장 성공")
    else:
        print("❌ Vector DB 저장 실패")
        return

    # 5. Vector DB 검색 테스트
    print("\n" + "="*60)
    print("🔍 4단계: Vector DB 검색 테스트")
    print("="*60)

    # 다양한 검색어로 테스트
    search_queries = [
        "시스템 에러",
        "DB 연결",
        "스크린샷",
        "로그 파일",
        "긴급",
        "에러 스크린샷",  # 이미지 alt 텍스트
        "시스템 에러 화면"  # 이미지 title 텍스트
    ]

    for query in search_queries:
        print(f"\n🔍 검색어: '{query}'")
        similar_mails = vector_db.search_similar_mails(query, n_results=3)

        if similar_mails:
            print(f"   검색 결과: {len(similar_mails)}개")
            for j, mail in enumerate(similar_mails, 1):
                print(f"   결과 {j}: {mail.subject} (ID: {mail.message_id})")
        else:
            print("   검색 결과: 없음")

    # 6. 저장된 메일 직접 조회
    print("\n" + "="*60)
    print("🔍 5단계: 저장된 메일 직접 조회")
    print("="*60)

    retrieved_mail = vector_db.get_mail_by_id(test_mail.message_id)
    if retrieved_mail:
        print("✅ 메일 조회 성공")
        print(f"   제목: {retrieved_mail.subject}")
        print(f"   정제된 콘텐츠 길이: {len(retrieved_mail.refined_content)}자")

        # 이미지 정보 확인
        has_image_in_retrieved = "[이미지에서 추출된 내용]" in retrieved_mail.refined_content
        print(f"   이미지 정보 포함: {'✅' if has_image_in_retrieved else '❌'}")

        if has_image_in_retrieved:
            content = retrieved_mail.refined_content
            image_part = content.split("[이미지에서 추출된 내용]")[1]
            print(f"   이미지 정보:\n{image_part}")

    else:
        print("❌ 메일 조회 실패")

    print("\n" + "="*80)
    print("🧪 테스트 완료")
    print("="*80)

if __name__ == "__main__":
    test_image_mail_pipeline()