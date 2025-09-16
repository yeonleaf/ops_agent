#!/usr/bin/env python3
"""
FastMCP 메인 앱에서 이미지 렌더링 기능 테스트
Vector DB에 이미지가 포함된 메일을 저장하고 메인 앱에서 표시 확인
"""

import sys
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

def test_fastmcp_image_rendering():
    """FastMCP 메인 앱 이미지 렌더링 테스트"""

    print("=" * 80)
    print("🧪 FastMCP 메인 앱 이미지 렌더링 테스트")
    print("=" * 80)

    try:
        from vector_db_models import VectorDBManager, Mail

        # Vector DB 연결
        vector_db = VectorDBManager()
        print("✅ Vector DB 연결 성공")

        # 메인 앱에서 사용할 이미지 포함 메일 생성
        print("\n📧 1단계: 메인 앱용 이미지 포함 테스트 메일 생성")

        # 실제 NCMS 스타일의 메일 시뮬레이션
        sample_mail = Mail(
            message_id="fastmcp_image_test_001",
            original_content="""<html><body>
<h2>NCMSAPI Batch 확인 요청</h2>
<p>안녕하세요. 다음 배치 작업에 대한 확인이 필요합니다.</p>
<img src="https://via.placeholder.com/600x400/FF6600/FFFFFF?text=NCMS+API+Status" alt="NCMS API 상태" title="API 상태 확인">
<p>배치 실행 결과:</p>
<ul>
<li>처리된 건수: 1,234건</li>
<li>오류 건수: 5건</li>
<li>성공률: 99.6%</li>
</ul>
<img src="https://via.placeholder.com/500x300/0066CC/FFFFFF?text=Error+Log" alt="오류 로그" title="오류 상세 정보">
<p>확인 후 회신 부탁드립니다.</p>
</body></html>""",
            refined_content="""NCMSAPI Batch 확인 요청
안녕하세요. 다음 배치 작업에 대한 확인이 필요합니다.

[이미지에서 추출된 내용]
이미지 1: Alt: NCMS API 상태; Title: API 상태 확인; 외부 이미지: https://via.placeholder.com/600x400/FF6600/FFFFFF?text=NCMS+API+Status
이미지 2: Alt: 오류 로그; Title: 오류 상세 정보; 외부 이미지: https://via.placeholder.com/500x300/0066CC/FFFFFF?text=Error+Log

배치 실행 결과:
- 처리된 건수: 1,234건
- 오류 건수: 5건
- 성공률: 99.6%

확인 후 회신 부탁드립니다.""",
            sender="ncms@company.com",
            status="pending",  # 메인 앱에서 처리할 수 있도록
            has_attachment=False,
            subject="NCMSAPI Batch 확인 요청",
            received_datetime=datetime.now().isoformat(),
            content_type="html",
            extraction_method="enhanced_html_extraction_with_images",
            content_summary="NCMS API 배치 작업 결과 확인 요청 - 이미지 포함",
            key_points=["NCMS API", "배치 작업", "확인 요청", "이미지 포함"],
            created_at=datetime.now().isoformat()
        )

        # 메일 저장
        save_success = vector_db.save_mail(sample_mail)
        if save_success:
            print("✅ NCMS 스타일 이미지 포함 메일 저장 성공")
        else:
            print("❌ NCMS 스타일 메일 저장 실패")
            return

        # 2. 또 다른 이미지 포함 메일 생성 (업무용이 아니라고 잘못 분류될 수 있는 메일)
        print("\n📧 2단계: 분류 테스트용 이미지 포함 메일 생성")

        sample_mail_2 = Mail(
            message_id="fastmcp_image_test_002",
            original_content="""<html><body>
<h2>점심 메뉴 추천</h2>
<p>오늘의 점심 메뉴를 추천드립니다!</p>
<img src="https://via.placeholder.com/400x300/FF0066/FFFFFF?text=Lunch+Menu" alt="점심 메뉴" title="오늘의 메뉴">
<p>맛있게 드세요!</p>
<img src="user=999&end=1" alt="접근 불가 이미지">
</body></html>""",
            refined_content="""점심 메뉴 추천
오늘의 점심 메뉴를 추천드립니다!

[이미지에서 추출된 내용]
이미지 1: Alt: 점심 메뉴; Title: 오늘의 메뉴; 외부 이미지: https://via.placeholder.com/400x300/FF0066/FFFFFF?text=Lunch+Menu
이미지 2: Alt: 접근 불가 이미지; 외부 이미지: user=999&end=1

맛있게 드세요!""",
            sender="lunch@company.com",
            status="non_work",  # 업무용이 아님
            has_attachment=False,
            subject="점심 메뉴 추천",
            received_datetime=datetime.now().isoformat(),
            content_type="html",
            extraction_method="enhanced_html_extraction_with_images",
            content_summary="점심 메뉴 추천 - 이미지 포함 (업무용 아님)",
            key_points=["점심", "메뉴 추천", "이미지 포함"],
            created_at=datetime.now().isoformat()
        )

        save_success_2 = vector_db.save_mail(sample_mail_2)
        if save_success_2:
            print("✅ 점심 메뉴 이미지 포함 메일 저장 성공")
        else:
            print("❌ 점심 메뉴 메일 저장 실패")

        # 3. 저장된 메일 확인
        print("\n📊 3단계: 저장된 테스트 메일 확인")

        # 첫 번째 메일 조회
        mail_1 = vector_db.get_mail_by_id("fastmcp_image_test_001")
        if mail_1:
            print("✅ NCMS 테스트 메일 조회 성공")
            print(f"   - 제목: {mail_1.subject}")
            print(f"   - 상태: {mail_1.status}")
            print(f"   - 이미지 정보 포함: {'✅' if '[이미지에서 추출된 내용]' in mail_1.refined_content else '❌'}")

        # 두 번째 메일 조회
        mail_2 = vector_db.get_mail_by_id("fastmcp_image_test_002")
        if mail_2:
            print("✅ 점심 메뉴 테스트 메일 조회 성공")
            print(f"   - 제목: {mail_2.subject}")
            print(f"   - 상태: {mail_2.status}")
            print(f"   - 이미지 정보 포함: {'✅' if '[이미지에서 추출된 내용]' in mail_2.refined_content else '❌'}")

        print("\n🎯 테스트 완료 - FastMCP 메인 앱에서 확인")
        print("   1. FastMCP 앱 실행: streamlit run fastmcp_chatbot_app.py")
        print("   2. '업무용이 아니라고 판단된 메일' 섹션에서 점심 메뉴 메일 확인")
        print("   3. '이미지 포함 전체 보기' 버튼으로 이미지 렌더링 확인")
        print("   4. NCMS 메일은 업무용으로 분류되어 일반 메일 처리 플로우에서 확인")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("🧪 FastMCP 이미지 렌더링 테스트 완료")
    print("=" * 80)

if __name__ == "__main__":
    test_fastmcp_image_rendering()