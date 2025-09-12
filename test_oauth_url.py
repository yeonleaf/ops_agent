#!/usr/bin/env python3
"""
OAuth URL 생성 테스트
"""

import os
from dotenv import load_dotenv
from oauth_auth_agent import get_oauth_agent

# 환경 변수 로드
load_dotenv()

def test_oauth_url():
    """OAuth URL 생성 테스트"""
    print("🔍 OAuth URL 생성 테스트")
    print("=" * 50)
    
    # 환경 변수 확인
    print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
    print(f"GOOGLE_CLIENT_SECRET: {os.getenv('GOOGLE_CLIENT_SECRET')}")
    print()
    
    # OAuth 에이전트 가져오기
    oauth_agent = get_oauth_agent()
    
    # OAuth URL 생성
    result = oauth_agent.generate_auth_url("gmail")
    
    if result["success"]:
        print("✅ OAuth URL 생성 성공!")
        print(f"🔗 인증 URL: {result['auth_url']}")
        print()
        
        # URL 파라미터 분석
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(result['auth_url'])
        params = parse_qs(parsed_url.query)
        
        print("📋 URL 파라미터 분석:")
        for key, value in params.items():
            print(f"  {key}: {value[0] if value else 'None'}")
        
        # 필수 파라미터 확인
        required_params = ['client_id', 'redirect_uri', 'scope', 'response_type', 'access_type', 'prompt', 'state']
        missing_params = []
        
        for param in required_params:
            if param not in params:
                missing_params.append(param)
        
        if missing_params:
            print(f"\n❌ 누락된 파라미터: {missing_params}")
        else:
            print("\n✅ 모든 필수 파라미터가 포함되어 있습니다!")
            
    else:
        print(f"❌ OAuth URL 생성 실패: {result['error']}")

if __name__ == "__main__":
    test_oauth_url()
