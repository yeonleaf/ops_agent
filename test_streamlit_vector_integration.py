#!/usr/bin/env python3
"""
Streamlit Vector DB 통합 테스트
샘플 메일을 저장하고 조회 기능을 테스트
"""

import sys
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

def test_streamlit_vector_integration():
    """Streamlit Vector DB 통합 테스트"""

    print("=" * 80)
    print("🧪 Streamlit Vector DB 통합 테스트")
    print("=" * 80)

    try:
        from vector_db_models import VectorDBManager, Mail

        # Vector DB 연결
        vector_db = VectorDBManager()
        print("✅ Vector DB 연결 성공")

        # 1. 샘플 메일 생성 및 저장
        print("\n📧 1단계: 샘플 메일 생성 및 저장")

        sample_mail = Mail(
            message_id="test_streamlit_mail_001",
            original_content="<html><body><h2>테스트 메일</h2><p>이것은 Streamlit 통합 테스트용 메일입니다.</p><img src='test.jpg' alt='테스트 이미지' title='샘플 이미지'></body></html>",
            refined_content="테스트 메일\n이것은 Streamlit 통합 테스트용 메일입니다.\n\n[이미지에서 추출된 내용]\n이미지 1: Alt: 테스트 이미지; Title: 샘플 이미지; 외부 이미지: test.jpg",
            sender="test@example.com",
            status="acceptable",
            has_attachment=True,  # 필수 필드 추가
            subject="Streamlit 통합 테스트 메일",
            received_datetime=datetime.now().isoformat(),
            content_type="html",
            extraction_method="enhanced_html_extraction_with_images",
            content_summary="Streamlit Vector DB 통합 테스트를 위한 샘플 메일",
            key_points=["Streamlit 통합 테스트", "Vector DB 조회 테스트", "이미지 정보 포함"],
            created_at=datetime.now().isoformat()
        )

        # 메일 저장
        save_success = vector_db.save_mail(sample_mail)
        if save_success:
            print("✅ 샘플 메일 저장 성공")
        else:
            print("❌ 샘플 메일 저장 실패")
            return

        # 2. Streamlit 함수 직접 테스트
        print("\n📋 2단계: Streamlit 조회 함수 테스트")

        # Streamlit 함수 import
        sys.path.append('/Users/a11479/Desktop/code/ops_agent')
        from streamlit_outlook_final import get_email_body_from_vector_db

        # Vector DB 조회 테스트
        result = get_email_body_from_vector_db("test_streamlit_mail_001")

        if result and result.get('success'):
            print("✅ Vector DB 조회 성공")
            print(f"   - 제목: {result.get('subject')}")
            print(f"   - 발신자: {result.get('sender')}")
            print(f"   - 원본 콘텐츠 길이: {len(result.get('original_content', ''))}자")
            print(f"   - 정제된 콘텐츠 길이: {len(result.get('refined_content', ''))}자")
            print(f"   - 추출 방법: {result.get('extraction_method')}")
            print(f"   - 요약: {result.get('content_summary')}")

            # 이미지 정보 확인
            refined_content = result.get('refined_content', '')
            has_image_info = "[이미지에서 추출된 내용]" in refined_content
            print(f"   - 이미지 정보 포함: {'✅' if has_image_info else '❌'}")

            # 핵심 포인트 확인
            key_points = result.get('key_points', [])
            if key_points:
                print(f"   - 핵심 포인트: {len(key_points)}개")
                for i, point in enumerate(key_points, 1):
                    print(f"     {i}. {point}")

        else:
            print("❌ Vector DB 조회 실패")

        # 3. 존재하지 않는 메일 ID 테스트
        print("\n🔍 3단계: 존재하지 않는 메일 ID 테스트")

        result_not_found = get_email_body_from_vector_db("non_existent_mail_id")

        if result_not_found is None:
            print("✅ 존재하지 않는 메일 처리 정상 (None 반환)")
        else:
            print(f"⚠️ 예상과 다른 결과: {result_not_found}")

        # 4. 저장된 메일 수 확인
        print("\n📊 4단계: 저장된 메일 수 확인")

        collection = vector_db.collection
        count = collection.count()
        print(f"   총 저장된 메일 수: {count}개")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("🧪 테스트 완료")
    print("=" * 80)

if __name__ == "__main__":
    test_streamlit_vector_integration()