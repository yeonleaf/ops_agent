#!/usr/bin/env python3
"""
Vector DB 메일 조회 기능 테스트
Streamlit UI 변경 사항 검증용
"""

import sys
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append('/Users/a11479/Desktop/code/ops_agent')

def test_vector_db_mail_lookup():
    """Vector DB 메일 조회 테스트"""

    print("=" * 80)
    print("🧪 Vector DB 메일 조회 테스트")
    print("=" * 80)

    try:
        from vector_db_models import VectorDBManager

        # Vector DB 연결
        vector_db = VectorDBManager()
        print("✅ Vector DB 연결 성공")

        # 모든 컬렉션 확인
        try:
            client = vector_db.client
            collections = client.list_collections()
            print(f"\n📋 전체 컬렉션 목록: {len(collections)}개")
            for collection in collections:
                count = collection.count()
                print(f"   - {collection.name}: {count}개 문서")
        except Exception as e:
            print(f"❌ 컬렉션 목록 조회 실패: {e}")

        # 저장된 메일 목록 확인
        # ChromaDB 컬렉션에서 모든 메일 ID 가져오기
        try:
            print(f"🔍 컬렉션 이름: {vector_db.collection.name}")
            collection = vector_db.collection
            results = collection.get()
            mail_ids = results['ids']

            # 다른 정보도 확인
            metadatas = results.get('metadatas', [])
            documents = results.get('documents', [])

            print(f"📊 저장된 메일 수: {len(mail_ids)}개")

            if mail_ids:
                # 처음 몇 개 메일 ID 표시
                print(f"\n📋 메일 ID 목록 (처음 5개):")
                for i, mail_id in enumerate(mail_ids[:5], 1):
                    print(f"   {i}. {mail_id}")

                # 첫 번째 메일 상세 조회 테스트
                test_mail_id = mail_ids[0]
                print(f"\n🔍 메일 상세 조회 테스트: {test_mail_id}")

                mail = vector_db.get_mail_by_id(test_mail_id)

                if mail:
                    print(f"✅ 메일 조회 성공:")
                    print(f"   - 제목: {mail.subject}")
                    print(f"   - 발신자: {mail.sender}")
                    print(f"   - 원본 콘텐츠 길이: {len(mail.original_content)}자")
                    print(f"   - 정제된 콘텐츠 길이: {len(mail.refined_content)}자")
                    print(f"   - 콘텐츠 타입: {mail.content_type}")
                    print(f"   - 추출 방법: {mail.extraction_method}")

                    # 이미지 정보 포함 여부 확인
                    has_image_info = "[이미지에서 추출된 내용]" in mail.refined_content
                    print(f"   - 이미지 정보 포함: {'✅' if has_image_info else '❌'}")

                    if mail.content_summary:
                        print(f"   - 요약: {mail.content_summary}")

                    if mail.key_points:
                        print(f"   - 핵심 포인트: {len(mail.key_points)}개")
                        for j, point in enumerate(mail.key_points[:3], 1):
                            print(f"     {j}. {point}")

                    # 정제된 콘텐츠 미리보기
                    print(f"\n📝 정제된 콘텐츠 미리보기:")
                    preview = mail.refined_content[:200] + "..." if len(mail.refined_content) > 200 else mail.refined_content
                    print(f"   {preview}")

                else:
                    print(f"❌ 메일 조회 실패: {test_mail_id}")

            else:
                print("📭 저장된 메일이 없습니다.")

        except Exception as e:
            print(f"❌ Vector DB 조회 오류: {str(e)}")

    except Exception as e:
        print(f"❌ Vector DB 연결 실패: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("🧪 테스트 완료")
    print("=" * 80)

if __name__ == "__main__":
    test_vector_db_mail_lookup()