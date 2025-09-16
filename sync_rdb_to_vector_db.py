#!/usr/bin/env python3
"""
RDB와 Vector DB 동기화 스크립트
RDB에 있지만 Vector DB에 없는 메일들을 동기화합니다.
"""

from database_models import DatabaseManager
from vector_db_models import VectorDBManager, Mail
from datetime import datetime
import json
import re

def sync_rdb_to_vector_db():
    """RDB 티켓들을 Vector DB와 동기화"""
    print("🔄 RDB → Vector DB 동기화 시작")
    print("=" * 50)

    # 매니저 초기화
    db_manager = DatabaseManager()
    vector_db = VectorDBManager()

    # RDB에서 모든 티켓 조회
    tickets = db_manager.get_all_tickets()
    print(f"📋 RDB에서 {len(tickets)}개 티켓 발견")

    synced_count = 0
    skipped_count = 0
    failed_count = 0

    for i, ticket in enumerate(tickets, 1):
        message_id = getattr(ticket, 'original_message_id', None)

        if not message_id:
            print(f"⚠️  티켓 {ticket.ticket_id}: original_message_id가 없음, 건너뜀")
            skipped_count += 1
            continue

        print(f"\n{i}. 티켓 ID {ticket.ticket_id} (메시지 ID: {message_id})")
        print(f"   제목: {ticket.title}")

        # Vector DB에 이미 있는지 확인
        existing_mail = vector_db.get_mail_by_id(message_id)
        if existing_mail:
            print(f"   ✅ 이미 Vector DB에 존재함, 건너뜀")
            skipped_count += 1
            continue

        # RDB 티켓 정보로 Mail 객체 생성
        try:
            # description에서 실제 메일 내용 추출 시도
            description = getattr(ticket, 'description', '')

            # 메일 내용이 "이메일 내용:" 으로 시작하는 경우 원본 추출
            email_content = description
            if '이메일 내용:' in description:
                # AI 분석 부분 제거하고 실제 메일 내용만 추출
                parts = description.split('AI 분석:')
                if len(parts) > 0:
                    email_part = parts[0].replace('이메일 내용:', '').strip()
                    if email_part:
                        email_content = email_part

            # 키포인트 추출
            key_points = getattr(ticket, 'labels', []) if hasattr(ticket, 'labels') else []
            if isinstance(key_points, str):
                try:
                    key_points = json.loads(key_points)
                except:
                    key_points = [key_points] if key_points else []

            # Mail 객체 생성
            mail = Mail(
                message_id=message_id,
                original_content=email_content,
                refined_content=email_content[:1000] if email_content else description[:1000],
                sender=getattr(ticket, 'reporter', '알 수 없음'),
                status='acceptable',
                subject=ticket.title,
                received_datetime=getattr(ticket, 'created_at', datetime.now().isoformat()),
                content_type='html' if '<' in email_content else 'text',
                has_attachment=bool('[image:' in email_content or '스크린샷' in email_content or '첨부' in email_content),
                extraction_method='rdb_sync',
                content_summary=email_content[:200] + '...' if len(email_content) > 200 else email_content,
                key_points=key_points,
                created_at=getattr(ticket, 'created_at', datetime.now().isoformat())
            )

            # Vector DB에 저장
            success = vector_db.save_mail(mail)

            if success:
                print(f"   ✅ Vector DB 저장 성공")
                synced_count += 1
            else:
                print(f"   ❌ Vector DB 저장 실패")
                failed_count += 1

        except Exception as e:
            print(f"   ❌ 동기화 실패: {e}")
            failed_count += 1

    print(f"\n🎯 동기화 완료!")
    print(f"=" * 50)
    print(f"✅ 성공: {synced_count}개")
    print(f"⏭️  건너뜀: {skipped_count}개")
    print(f"❌ 실패: {failed_count}개")
    print(f"📊 전체: {len(tickets)}개")

    return synced_count > 0

def verify_sync():
    """동기화 결과 검증"""
    print(f"\n🔍 동기화 결과 검증")
    print("=" * 30)

    db_manager = DatabaseManager()
    vector_db = VectorDBManager()

    # RDB 티켓들
    tickets = db_manager.get_all_tickets()
    print(f"📋 RDB 티켓 수: {len(tickets)}")

    # Vector DB 메일들
    try:
        result = vector_db.collection.get(include=['metadatas'])
        vector_mails = len(result.get('ids', []))
        print(f"💾 Vector DB 메일 수: {vector_mails}")

        # 각 티켓에 대해 Vector DB 조회 테스트
        missing_count = 0
        for ticket in tickets:
            message_id = getattr(ticket, 'original_message_id', None)
            if message_id:
                mail = vector_db.get_mail_by_id(message_id)
                if not mail:
                    print(f"⚠️  누락: {ticket.ticket_id} - {message_id}")
                    missing_count += 1

        if missing_count == 0:
            print(f"✅ 모든 티켓이 Vector DB에 동기화됨")
        else:
            print(f"❌ {missing_count}개 티켓이 여전히 누락됨")

    except Exception as e:
        print(f"❌ 검증 실패: {e}")

if __name__ == "__main__":
    print("🚀 RDB ↔ Vector DB 동기화 스크립트 실행")
    print()

    success = sync_rdb_to_vector_db()

    if success:
        verify_sync()
    else:
        print("❌ 동기화할 데이터가 없습니다.")