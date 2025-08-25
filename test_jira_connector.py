#!/usr/bin/env python3
"""
Jira 연동 기능 테스트 스크립트

JiraConnector 클래스의 기능을 테스트합니다.
"""

import os
import sys
from datetime import datetime

def test_jira_connector():
    """JiraConnector 테스트"""
    print("🚀 JiraConnector 테스트 시작")
    print("=" * 60)
    
    try:
        # JiraConnector import
        from jira_connector import JiraConnector
        from dotenv import load_dotenv
        
        print("✅ JiraConnector import 성공")
        
        # .env 파일 로드
        load_dotenv()
        
        # 환경 변수에서 Jira 설정 가져오기 (.env 파일 우선)
        jira_url = os.getenv('JIRA_API_ENDPOINT', '').replace('/rest/api/2/', '')
        jira_email = os.getenv('JIRA_USER_EMAIL')
        jira_token = os.getenv('JIRA_API_TOKEN')
        
        if not all([jira_url, jira_email, jira_token]):
            print("⚠️  .env 파일에 Jira 설정이 완전하지 않습니다.")
            print("다음 환경 변수가 .env 파일에 설정되어 있는지 확인해주세요:")
            print("  - JIRA_API_ENDPOINT: Jira API 엔드포인트")
            print("  - JIRA_USER_EMAIL: Jira 계정 이메일")
            print("  - JIRA_API_TOKEN: Jira API 토큰")
            return
        
        print(f"🔗 Jira 설정 확인 (.env 파일에서 자동 로드):")
        print(f"  - URL: {jira_url}")
        print(f"  - Email: {jira_email}")
        print(f"  - Token: {jira_token[:10]}...")
        
        # JiraConnector 인스턴스 생성 (인자 없이 자동 설정)
        print(f"\n🔧 JiraConnector 초기화 중...")
        try:
            connector = JiraConnector()  # .env 파일에서 자동으로 설정 읽기
            print("✅ JiraConnector 초기화 성공")
        except ValueError as e:
            print(f"❌ JiraConnector 초기화 실패 (설정 오류): {e}")
            return
        except Exception as e:
            print(f"❌ JiraConnector 초기화 실패 (예상치 못한 오류): {e}")
            return
        
        # 1. 마지막 동기화 시각 조회 테스트
        print(f"\n📅 마지막 동기화 시각 조회 테스트...")
        last_sync = connector.get_last_sync_time()
        print(f"✅ 마지막 동기화: {last_sync}")
        
        # 2. 업데이트된 티켓 조회 테스트
        print(f"\n🔍 업데이트된 티켓 조회 테스트...")
        tickets = connector.fetch_updated_tickets(last_sync)
        print(f"✅ 조회된 티켓 수: {len(tickets)}")
        
        if tickets:
            print(f"📋 첫 번째 티켓 정보:")
            first_ticket = tickets[0]
            print(f"  - 키: {first_ticket['key']}")
            print(f"  - 요약: {first_ticket['summary'][:50]}...")
            print(f"  - 상태: {first_ticket['status']}")
            print(f"  - 우선순위: {first_ticket['priority']}")
            print(f"  - 담당자: {first_ticket['assignee']}")
            print(f"  - 코멘트 수: {len(first_ticket['comments'])}")
        
        # 3. 동기화 실행 테스트
        print(f"\n🚀 Jira 동기화 실행 테스트...")
        sync_result = connector.sync_jira()
        
        if sync_result["success"]:
            print("✅ 동기화 성공!")
            print(f"  - 메시지: {sync_result['message']}")
            print(f"  - 처리된 티켓: {sync_result['tickets_processed']}")
            print(f"  - 발견된 티켓: {sync_result['total_tickets_found']}")
            print(f"  - 동기화 시간: {sync_result['sync_duration']:.2f}초")
            print(f"  - 마지막 동기화: {sync_result['last_sync_time']}")
        else:
            print("❌ 동기화 실패!")
            print(f"  - 오류: {sync_result.get('error', '알 수 없는 오류')}")
            print(f"  - 메시지: {sync_result['message']}")
        
        # 4. 리소스 정리
        connector.close()
        print(f"\n✅ 리소스 정리 완료")
        
    except ImportError as e:
        print(f"❌ Import 오류: {e}")
        print("💡 필요한 라이브러리를 설치해주세요:")
        print("  pip install jira")
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def test_without_credentials():
    """인증 정보 없이 기본 기능 테스트"""
    print("🧪 인증 정보 없이 기본 기능 테스트")
    print("=" * 60)
    
    try:
        # JiraConnector import
        from jira_connector import JiraConnector
        
        print("✅ JiraConnector import 성공")
        
        # 가짜 인증 정보로 테스트 (연결은 실패하지만 클래스 구조는 확인 가능)
        print("🔧 JiraConnector 클래스 구조 확인...")
        
        # 클래스의 메서드들 확인
        methods = [method for method in dir(JiraConnector) if not method.startswith('_')]
        print(f"✅ 사용 가능한 메서드: {', '.join(methods)}")
        
        # 클래스 문서 확인
        if JiraConnector.__doc__:
            print(f"📚 클래스 설명: {JiraConnector.__doc__.strip()}")
        
        print("✅ 기본 기능 테스트 완료")
        
    except Exception as e:
        print(f"❌ 기본 기능 테스트 실패: {e}")

if __name__ == "__main__":
    print("🚀 Jira 연동 기능 테스트")
    print("=" * 60)
    
    # .env 파일 로드
    from dotenv import load_dotenv
    load_dotenv()
    
    # 환경 변수 확인 (.env 파일 우선)
    jira_url = os.getenv('JIRA_API_ENDPOINT', '').replace('/rest/api/2/', '')
    jira_email = os.getenv('JIRA_USER_EMAIL')
    jira_token = os.getenv('JIRA_API_TOKEN')
    
    if all([jira_url, jira_email, jira_token]):
        print("🔑 .env 파일에서 Jira 인증 정보를 찾았습니다. 전체 테스트를 실행합니다.")
        test_jira_connector()
    else:
        print("⚠️  .env 파일에 Jira 인증 정보가 완전하지 않습니다. 기본 기능 테스트만 실행합니다.")
        test_without_credentials()
    
    print("\n🎉 테스트 완료!")
    print("\n💡 전체 테스트를 실행하려면 .env 파일에 다음 설정을 추가하세요:")
    print("  JIRA_API_ENDPOINT=https://your-domain.atlassian.net/rest/api/2/")
    print("  JIRA_USER_EMAIL=your-email@company.com")
    print("  JIRA_API_TOKEN=your-api-token") 