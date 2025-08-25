#!/usr/bin/env python3
"""
데이터베이스 초기화 후 기본 기능 테스트
"""

def test_sqlite_database():
    """SQLite 데이터베이스 테스트"""
    print("🗄️ SQLite 데이터베이스 테스트 시작...")
    
    try:
        from sqlite_ticket_models import SQLiteTicketManager, Ticket
        from datetime import datetime
        
        # 매니저 생성
        ticket_manager = SQLiteTicketManager()
        print("  ✅ SQLiteTicketManager 생성 성공")
        
        # 테스트 티켓 생성
        test_ticket = Ticket(
            ticket_id=None,
            original_message_id="test_msg_001",
            status="new",
            title="테스트 티켓",
            description="데이터베이스 초기화 테스트용 티켓입니다.",
            priority="Medium",
            ticket_type="Task",
            reporter="테스터",
            reporter_email="tester@test.com",
            labels=["test", "initialization"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # 티켓 삽입
        ticket_id = ticket_manager.insert_ticket(test_ticket)
        print(f"  ✅ 테스트 티켓 삽입 성공: ID={ticket_id}")
        
        # 티켓 조회
        retrieved_ticket = ticket_manager.get_ticket_by_id(ticket_id)
        if retrieved_ticket:
            print(f"  ✅ 티켓 조회 성공: {retrieved_ticket.title}")
        else:
            print("  ❌ 티켓 조회 실패")
        
        # 모든 티켓 조회
        all_tickets = ticket_manager.get_all_tickets()
        print(f"  ✅ 전체 티켓 조회 성공: {len(all_tickets)}개")
        
        print("✅ SQLite 데이터베이스 테스트 완료")
        return True
        
    except Exception as e:
        print(f"  ❌ SQLite 테스트 실패: {str(e)}")
        return False

def test_vector_database():
    """VectorDB 테스트"""
    print("🧠 VectorDB 테스트 시작...")
    
    try:
        from vector_db_models import VectorDBManager, Mail
        from datetime import datetime
        
        # 매니저 생성
        vector_db = VectorDBManager()
        print("  ✅ VectorDBManager 생성 성공")
        
        # 테스트 메일 생성
        test_mail = Mail(
            message_id="test_mail_001",
            original_content="이것은 테스트 메일의 원본 내용입니다.",
            refined_content="테스트 메일의 핵심 내용",
            sender="test@example.com",
            status="pending",
            subject="테스트 메일",
            received_datetime=datetime.now().isoformat(),
            content_type="text",
            has_attachment=False,
            extraction_method="test",
            content_summary="테스트용 메일 요약",
            key_points=["테스트", "초기화", "검증"],
            created_at=datetime.now().isoformat()
        )
        
        # 메일 저장
        result = vector_db.save_mail(test_mail)
        if result:
            print("  ✅ 테스트 메일 저장 성공")
        else:
            print("  ❌ 테스트 메일 저장 실패")
        
        # 메일 조회
        retrieved_mail = vector_db.get_mail_by_id("test_mail_001")
        if retrieved_mail:
            print(f"  ✅ 메일 조회 성공: {retrieved_mail.subject}")
        else:
            print("  ❌ 메일 조회 실패")
        
        # 전체 메일 수 확인
        all_mails = vector_db.get_all_mails()
        print(f"  ✅ 전체 메일 조회 성공: {len(all_mails)}개")
        
        print("✅ VectorDB 테스트 완료")
        return True
        
    except Exception as e:
        print(f"  ❌ VectorDB 테스트 실패: {str(e)}")
        return False

def main():
    """메인 테스트 함수"""
    print("🧪 데이터베이스 초기화 후 기능 테스트")
    print("=" * 50)
    
    # SQLite 테스트
    sqlite_success = test_sqlite_database()
    
    print()
    
    # VectorDB 테스트
    vector_success = test_vector_database()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약:")
    print(f"  SQLite: {'✅ 성공' if sqlite_success else '❌ 실패'}")
    print(f"  VectorDB: {'✅ 성공' if vector_success else '❌ 실패'}")
    
    if sqlite_success and vector_success:
        print("\n🎉 모든 데이터베이스가 정상적으로 작동합니다!")
    else:
        print("\n⚠️ 일부 데이터베이스에 문제가 있습니다.")

if __name__ == "__main__":
    main() 