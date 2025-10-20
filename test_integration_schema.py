#!/usr/bin/env python3
"""
새로운 Integration 스키마 테스트
"""

from database_models import DatabaseManager, Integration, User
from datetime import datetime

def test_integration_crud():
    """Integration CRUD 테스트"""
    print("=" * 60)
    print("Integration 스키마 테스트 시작")
    print("=" * 60)

    db_manager = DatabaseManager()

    # 테스트용 사용자 생성
    print("\n[1] 테스트 사용자 생성...")
    test_user = User(
        id=None,
        email="test@example.com",
        password_hash="test_hash",
        created_at=datetime.now().isoformat()
    )

    try:
        user_id = db_manager.insert_user(test_user)
        print(f"✅ 사용자 생성 성공: user_id={user_id}")
    except Exception as e:
        # 이미 존재하는 경우
        existing_user = db_manager.get_user_by_email("test@example.com")
        user_id = existing_user.id
        print(f"⚠️  기존 사용자 사용: user_id={user_id}")

    # Jira Integration 추가 테스트
    print("\n[2] Jira Integration 추가...")

    # Jira Endpoint 추가
    jira_endpoint = Integration(
        id=None,
        user_id=user_id,
        source='jira',
        type='endpoint',
        value='https://test.atlassian.net',
        created_at=None,
        updated_at=None
    )
    endpoint_id = db_manager.insert_integration(jira_endpoint)
    print(f"✅ Jira Endpoint 추가 성공: id={endpoint_id}")

    # Jira Token 추가
    jira_token = Integration(
        id=None,
        user_id=user_id,
        source='jira',
        type='token',
        value='encrypted_jira_token_12345',
        created_at=None,
        updated_at=None
    )
    token_id = db_manager.insert_integration(jira_token)
    print(f"✅ Jira Token 추가 성공: id={token_id}")

    # Gmail Integration 추가 테스트
    print("\n[3] Gmail Integration 추가...")
    gmail_token = Integration(
        id=None,
        user_id=user_id,
        source='gmail',
        type='token',
        value='encrypted_gmail_token_67890',
        created_at=None,
        updated_at=None
    )
    gmail_id = db_manager.insert_integration(gmail_token)
    print(f"✅ Gmail Token 추가 성공: id={gmail_id}")

    # Kakao Integration 추가 테스트
    print("\n[4] Kakao Integration 추가...")

    kakao_bot_key = Integration(
        id=None,
        user_id=user_id,
        source='kakao',
        type='botUserKey',
        value='kakao_bot_user_key_abc',
        created_at=None,
        updated_at=None
    )
    kakao_bot_id = db_manager.insert_integration(kakao_bot_key)
    print(f"✅ Kakao BotUserKey 추가 성공: id={kakao_bot_id}")

    kakao_api_key = Integration(
        id=None,
        user_id=user_id,
        source='kakao',
        type='apiKey',
        value='kakao_api_key_xyz',
        created_at=None,
        updated_at=None
    )
    kakao_api_id = db_manager.insert_integration(kakao_api_key)
    print(f"✅ Kakao API Key 추가 성공: id={kakao_api_id}")

    # 조회 테스트
    print("\n[5] Integration 조회 테스트...")

    # 특정 Integration 조회
    jira_endpoint_data = db_manager.get_integration(user_id, 'jira', 'endpoint')
    print(f"✅ Jira Endpoint 조회: {jira_endpoint_data.value}")

    jira_token_data = db_manager.get_integration(user_id, 'jira', 'token')
    print(f"✅ Jira Token 조회: {jira_token_data.value}")

    # 소스별 전체 조회
    jira_all = db_manager.get_integrations_by_source(user_id, 'jira')
    print(f"✅ Jira 전체 설정 조회: {len(jira_all)}개")
    for integration in jira_all:
        print(f"   - {integration.type}: {integration.value}")

    kakao_all = db_manager.get_integrations_by_source(user_id, 'kakao')
    print(f"✅ Kakao 전체 설정 조회: {len(kakao_all)}개")
    for integration in kakao_all:
        print(f"   - {integration.type}: {integration.value}")

    # 사용자별 전체 조회
    all_integrations = db_manager.get_all_integrations_by_user(user_id)
    print(f"✅ 사용자의 모든 Integration 조회: {len(all_integrations)}개")
    for integration in all_integrations:
        print(f"   - {integration.source}/{integration.type}: {integration.value}")

    # 업데이트 테스트
    print("\n[6] Integration 업데이트 테스트...")
    db_manager.update_integration_value(user_id, 'jira', 'endpoint', 'https://updated.atlassian.net')
    updated_endpoint = db_manager.get_integration(user_id, 'jira', 'endpoint')
    print(f"✅ Jira Endpoint 업데이트: {updated_endpoint.value}")

    # 삭제 테스트
    print("\n[7] Integration 삭제 테스트...")

    # 특정 타입만 삭제
    db_manager.delete_integration(user_id, 'kakao', 'apiKey')
    kakao_after_delete = db_manager.get_integrations_by_source(user_id, 'kakao')
    print(f"✅ Kakao apiKey 삭제 후: {len(kakao_after_delete)}개 남음")

    # 소스 전체 삭제
    db_manager.delete_integration_source(user_id, 'kakao')
    kakao_after_source_delete = db_manager.get_integrations_by_source(user_id, 'kakao')
    print(f"✅ Kakao 전체 삭제 후: {len(kakao_after_source_delete)}개 남음")

    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    test_integration_crud()
