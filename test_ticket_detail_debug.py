#!/usr/bin/env python3
"""
티켓 상세 페이지에서 메일 조회 과정을 디버깅하는 스크립트
"""

def test_ticket_detail_mail_retrieval():
    """티켓 상세 페이지에서 메일 조회 과정을 단계별로 테스트"""
    
    print("🔍 티켓 상세 페이지 메일 조회 디버깅")
    print("=" * 60)
    
    try:
        from database_models import DatabaseManager
        from vector_db_models import VectorDBManager
        from gmail_api_client import get_gmail_client
        from dotenv import load_dotenv
        load_dotenv()
        load_dotenv('oauth_config.env')
        
        # 1. 현재 저장된 티켓 조회
        print("\n📋 1단계: 저장된 티켓 조회")
        db_manager = DatabaseManager()
        tickets = db_manager.get_all_tickets()
        
        if not tickets:
            print("❌ 저장된 티켓이 없습니다.")
            return
        
        print(f"✅ {len(tickets)}개 티켓 발견")
        
        for i, ticket in enumerate(tickets):
            print(f"\n🎫 티켓 {i+1}: ID={ticket.ticket_id}")
            print(f"   제목: {ticket.title}")
            print(f"   original_message_id: {ticket.original_message_id}")
            print(f"   우선순위: {ticket.priority}")
            print(f"   레이블: {ticket.labels}")
            
            # 2. VectorDB에서 메일 조회 시도
            print(f"\n📧 2단계: VectorDB에서 메일 조회 (ID: {ticket.original_message_id})")
            try:
                vector_db = VectorDBManager()
                mail = vector_db.get_mail_by_id(ticket.original_message_id)
                
                if mail:
                    print(f"✅ VectorDB에서 메일 발견!")
                    print(f"   original_content 길이: {len(mail.original_content)}")
                    print(f"   extraction_method: {mail.extraction_method}")
                    print(f"   sender: {mail.sender}")
                    print(f"   subject: {mail.subject}")
                    
                    if mail.original_content == "메일 내용을 읽을 수 없습니다.":
                        print("❌ VectorDB에 저장된 본문이 'cannot read' 상태")
                    else:
                        print("✅ VectorDB에 실제 본문 저장됨")
                        preview = mail.original_content[:100].replace('\n', ' ')
                        print(f"   본문 미리보기: {preview}...")
                else:
                    print("❌ VectorDB에서 메일을 찾을 수 없음")
                    
                    # 3. Gmail API에서 직접 조회 시도
                    print(f"\n🔄 3단계: Gmail API에서 메일 직접 조회")
                    
                    # 토큰 재발급 로직
                    import sqlite3
                    import os
                    from google.oauth2.credentials import Credentials
                    from google.auth.transport.requests import Request
                    
                    with sqlite3.connect('tickets.db') as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT google_refresh_token FROM users WHERE google_refresh_token IS NOT NULL LIMIT 1')
                        result = cursor.fetchone()
                        
                        if result and result[0]:
                            refresh_token = result[0]
                            print(f"✅ refresh_token 발견: {refresh_token[:20]}...")
                            
                            client_id = os.getenv('GOOGLE_CLIENT_ID')
                            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
                            
                            if client_id and client_secret:
                                credentials = Credentials(
                                    token=None,
                                    refresh_token=refresh_token,
                                    token_uri='https://oauth2.googleapis.com/token',
                                    client_id=client_id,
                                    client_secret=client_secret
                                )
                                
                                request = Request()
                                credentials.refresh(request)
                                access_token = credentials.token
                                print(f"✅ access_token 재발급 성공: {access_token[:20]}...")
                                
                                # Gmail API 클라이언트로 조회
                                gmail_client = get_gmail_client()
                                auth_success = gmail_client.authenticate(access_token=access_token)
                                
                                if auth_success:
                                    print("✅ Gmail API 인증 성공")
                                    mail_detail = gmail_client.get_email_details(ticket.original_message_id)
                                    
                                    if mail_detail:
                                        print("✅ Gmail API에서 메일 조회 성공!")
                                        body = mail_detail.get('body', '')
                                        print(f"   본문 길이: {len(body)}")
                                        print(f"   제목: {mail_detail.get('subject', '')}")
                                        print(f"   발신자: {mail_detail.get('from', '')}")
                                        
                                        if body and body != "메일 내용을 읽을 수 없습니다.":
                                            print("✅ Gmail API에서 실제 본문 추출 성공!")
                                            preview = body[:100].replace('\n', ' ')
                                            print(f"   본문 미리보기: {preview}...")
                                        else:
                                            print("❌ Gmail API에서도 본문 추출 실패")
                                    else:
                                        print("❌ Gmail API에서 메일을 찾을 수 없음")
                                        print(f"   요청한 메일 ID: {ticket.original_message_id}")
                                else:
                                    print("❌ Gmail API 인증 실패")
                            else:
                                print("❌ Google OAuth 설정이 없음")
                        else:
                            print("❌ refresh_token이 없음")
                            
            except Exception as e:
                print(f"❌ VectorDB 조회 중 오류: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n🎯 디버깅 결론:")
        print(f"   - 이제 Streamlit UI에서 티켓 상세 페이지를 열면")
        print(f"   - 위와 같은 과정을 거쳐 메일 본문을 찾으려고 시도합니다.")
        print(f"   - VectorDB에 없으면 Gmail API fallback이 작동합니다.")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ticket_detail_mail_retrieval()
