#!/usr/bin/env python3
"""
이미지 렌더링 기능 테스트
Vector DB에 실제 이미지 URL이 포함된 메일을 저장하고 Streamlit에서 렌더링 테스트
"""

import sys
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

def test_image_rendering():
    """이미지 렌더링 기능 테스트"""

    print("=" * 80)
    print("🧪 이미지 렌더링 기능 테스트")
    print("=" * 80)

    try:
        from vector_db_models import VectorDBManager, Mail

        # Vector DB 연결
        vector_db = VectorDBManager()
        print("✅ Vector DB 연결 성공")

        # 실제 이미지 URL이 포함된 샘플 메일 생성
        print("\n📧 1단계: 실제 이미지 URL이 포함된 샘플 메일 생성")

        sample_mail = Mail(
            message_id="test_image_rendering_001",
            original_content="<html><body><h2>이미지 테스트 메일</h2><p>이 메일에는 실제 이미지가 포함되어 있습니다.</p><img src='https://via.placeholder.com/300x200/0066CC/FFFFFF?text=Sample+Image' alt='샘플 이미지'><p>이미지 아래 텍스트입니다.</p></body></html>",
            refined_content="""이미지 테스트 메일
이 메일에는 실제 이미지가 포함되어 있습니다.

[이미지에서 추출된 내용]
이미지 1: Alt: 샘플 이미지; 외부 이미지: https://via.placeholder.com/300x200/0066CC/FFFFFF?text=Sample+Image

이미지 아래 텍스트입니다.""",
            sender="imagetest@example.com",
            status="acceptable",
            has_attachment=False,
            subject="이미지 렌더링 테스트 메일",
            received_datetime=datetime.now().isoformat(),
            content_type="html",
            extraction_method="enhanced_html_extraction_with_images",
            content_summary="실제 이미지 URL이 포함된 테스트 메일",
            key_points=["이미지 렌더링 테스트", "실제 URL 테스트", "Streamlit 표시 테스트"],
            created_at=datetime.now().isoformat()
        )

        # 메일 저장
        save_success = vector_db.save_mail(sample_mail)
        if save_success:
            print("✅ 이미지 테스트 메일 저장 성공")
        else:
            print("❌ 이미지 테스트 메일 저장 실패")
            return

        # 2. 다양한 이미지 URL 형태가 포함된 메일 생성
        print("\n📧 2단계: 다양한 이미지 URL 형태 테스트 메일 생성")

        sample_mail_2 = Mail(
            message_id="test_image_rendering_002",
            original_content="<html><body><h2>다양한 이미지 형태</h2><p>여러 종류의 이미지 URL을 테스트합니다.</p></body></html>",
            refined_content="""다양한 이미지 형태
여러 종류의 이미지 URL을 테스트합니다.

[이미지에서 추출된 내용]
이미지 1: Alt: 공개 이미지; 외부 이미지: https://httpbin.org/image/png
이미지 2: Alt: 다른 샘플; 외부 이미지: https://via.placeholder.com/400x300/FF6600/FFFFFF?text=Test+Image+2
이미지 3: Alt: 접근 불가 이미지; 외부 이미지: user=724165&end=1

테스트 완료.""",
            sender="multitest@example.com",
            status="acceptable",
            has_attachment=False,
            subject="다양한 이미지 URL 형태 테스트",
            received_datetime=datetime.now().isoformat(),
            content_type="html",
            extraction_method="enhanced_html_extraction_with_images",
            content_summary="다양한 형태의 이미지 URL 테스트",
            key_points=["다양한 URL 형태", "접근 가능/불가능 이미지", "렌더링 테스트"],
            created_at=datetime.now().isoformat()
        )

        # 메일 저장
        save_success_2 = vector_db.save_mail(sample_mail_2)
        if save_success_2:
            print("✅ 다양한 이미지 형태 테스트 메일 저장 성공")
        else:
            print("❌ 다양한 이미지 형태 테스트 메일 저장 실패")

        # 3. 저장된 메일 확인
        print("\n📊 3단계: 저장된 테스트 메일 확인")

        # 첫 번째 테스트 메일 조회
        mail_1 = vector_db.get_mail_by_id("test_image_rendering_001")
        if mail_1:
            print("✅ 첫 번째 테스트 메일 조회 성공")
            print(f"   - 제목: {mail_1.subject}")
            print(f"   - 이미지 정보 포함: {'✅' if '[이미지에서 추출된 내용]' in mail_1.refined_content else '❌'}")

            # 이미지 URL 추출 테스트
            import re
            urls = re.findall(r'외부 이미지:\s*([^\s\n]+)', mail_1.refined_content)
            print(f"   - 추출된 이미지 URL 수: {len(urls)}개")
            for i, url in enumerate(urls, 1):
                print(f"     {i}. {url}")

        # 두 번째 테스트 메일 조회
        mail_2 = vector_db.get_mail_by_id("test_image_rendering_002")
        if mail_2:
            print("✅ 두 번째 테스트 메일 조회 성공")
            print(f"   - 제목: {mail_2.subject}")

            # 이미지 URL 추출 테스트
            import re
            urls = re.findall(r'외부 이미지:\s*([^\s\n]+)', mail_2.refined_content)
            print(f"   - 추출된 이미지 URL 수: {len(urls)}개")
            for i, url in enumerate(urls, 1):
                print(f"     {i}. {url}")

        print("\n🎯 테스트 완료 - Streamlit UI에서 이미지 렌더링 확인")
        print("   1. Streamlit 앱 실행: streamlit run streamlit_outlook_final.py")
        print("   2. 메일 새로고침 후 테스트 메일 찾기")
        print("   3. '전체 내용 보기' 클릭하여 이미지 렌더링 확인")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("🧪 이미지 렌더링 테스트 완료")
    print("=" * 80)

if __name__ == "__main__":
    test_image_rendering()