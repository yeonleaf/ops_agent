#!/usr/bin/env python3
"""
OAuth 클라이언트 통합 스크립트
Streamlit 앱에서 OAuth 인증을 사용하는 예제
"""

import streamlit as st
import requests
import json
from typing import Optional, Dict, Any

# OAuth 서버 설정
OAUTH_SERVER_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8505"

class OAuthClient:
    """OAuth 클라이언트"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_auth_url(self, provider: str) -> str:
        """OAuth 인증 URL 생성"""
        return f"{OAUTH_SERVER_URL}/auth/login/{provider}"
    
    def check_auth_status(self) -> Dict[str, Any]:
        """인증 상태 확인"""
        try:
            response = self.session.get(f"{OAUTH_SERVER_URL}/auth/status")
            return response.json()
        except Exception as e:
            return {"authenticated": False, "error": str(e)}
    
    def refresh_token(self, provider: str) -> Dict[str, Any]:
        """토큰 재발급"""
        try:
            response = self.session.post(
                f"{OAUTH_SERVER_URL}/auth/refresh",
                json={"provider": provider}
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def logout(self) -> Dict[str, Any]:
        """로그아웃"""
        try:
            response = self.session.post(f"{OAUTH_SERVER_URL}/auth/logout")
            return response.json()
        except Exception as e:
            return {"error": str(e)}

def main():
    """Streamlit 메인 앱"""
    st.set_page_config(
        page_title="OAuth 이메일 서비스",
        page_icon="📧",
        layout="wide"
    )
    
    st.title("📧 OAuth 이메일 서비스")
    
    # OAuth 클라이언트 초기화
    oauth_client = OAuthClient()
    
    # 세션 상태 초기화
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'provider' not in st.session_state:
        st.session_state.provider = None
    
    # 사이드바 - 인증 상태
    with st.sidebar:
        st.header("🔐 인증 상태")
        
        # 인증 상태 확인
        auth_status = oauth_client.check_auth_status()
        
        if auth_status.get("authenticated"):
            st.success("✅ 인증됨")
            st.write(f"**제공자:** {auth_status.get('provider', 'Unknown')}")
            
            if st.button("🚪 로그아웃"):
                logout_result = oauth_client.logout()
                if "error" not in logout_result:
                    st.session_state.authenticated = False
                    st.session_state.access_token = None
                    st.session_state.provider = None
                    st.rerun()
                else:
                    st.error(f"로그아웃 실패: {logout_result['error']}")
        else:
            st.warning("⚠️ 인증 필요")
            
            # OAuth 로그인 버튼들
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📧 Gmail 로그인", use_container_width=True):
                    auth_url = oauth_client.get_auth_url("gmail")
                    st.markdown(f"[Gmail로 로그인]({auth_url})")
            
            with col2:
                if st.button("📨 Outlook 로그인", use_container_width=True):
                    auth_url = oauth_client.get_auth_url("outlook")
                    st.markdown(f"[Outlook으로 로그인]({auth_url})")
    
    # URL 파라미터에서 토큰 확인
    query_params = st.query_params
    
    if 'access_token' in query_params and 'provider' in query_params:
        # OAuth 콜백에서 리디렉션됨
        st.session_state.access_token = query_params['access_token']
        st.session_state.provider = query_params['provider']
        st.session_state.authenticated = True
        
        # URL 정리
        st.query_params.clear()
        st.rerun()
    
    # 메인 콘텐츠
    if st.session_state.authenticated and st.session_state.access_token:
        st.success("🎉 인증이 완료되었습니다!")
        
        # 이메일 서비스 사용
        st.header("📬 이메일 서비스")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("이메일 조회")
            
            # 필터 옵션
            filters = {}
            
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                is_read = st.selectbox("읽음 상태", ["전체", "읽은 메일", "안 읽은 메일"])
                if is_read == "읽은 메일":
                    filters["is_read"] = True
                elif is_read == "안 읽은 메일":
                    filters["is_read"] = False
            
            with col_filter2:
                max_results = st.number_input("최대 결과 수", min_value=1, max_value=100, value=20)
            
            if st.button("📥 이메일 가져오기", type="primary"):
                with st.spinner("이메일을 가져오는 중..."):
                    try:
                        # MCP 서버에 요청
                        response = requests.get(
                            f"{MCP_SERVER_URL}/get_authenticated_emails",
                            params={
                                "provider": st.session_state.provider,
                                "filters": json.dumps(filters),
                                "max_results": max_results
                            },
                            headers={
                                "Authorization": f"Bearer {st.session_state.access_token}"
                            }
                        )
                        
                        if response.status_code == 200:
                            emails = response.json()
                            st.success(f"✅ {len(emails)}개의 이메일을 가져왔습니다.")
                            
                            # 이메일 목록 표시
                            for i, email in enumerate(emails):
                                with st.expander(f"📧 {email.get('subject', '제목 없음')} - {email.get('sender', '발신자 없음')}"):
                                    st.write(f"**발신자:** {email.get('sender')}")
                                    st.write(f"**수신일:** {email.get('received_date')}")
                                    st.write(f"**읽음 상태:** {'읽음' if email.get('is_read') else '안 읽음'}")
                                    st.write(f"**우선순위:** {email.get('priority', 'Medium')}")
                                    st.write(f"**첨부파일:** {'있음' if email.get('has_attachments') else '없음'}")
                                    
                                    if email.get('body'):
                                        st.write("**내용:**")
                                        st.text(email.get('body')[:500] + "..." if len(email.get('body', '')) > 500 else email.get('body'))
                        else:
                            st.error(f"이메일 가져오기 실패: {response.text}")
                    
                    except Exception as e:
                        st.error(f"오류 발생: {e}")
        
        with col2:
            st.subheader("서비스 상태")
            
            # MCP 서버 상태 확인
            try:
                health_response = requests.get(f"{MCP_SERVER_URL}/health")
                if health_response.status_code == 200:
                    st.success("✅ MCP 서버 연결됨")
                else:
                    st.error("❌ MCP 서버 연결 실패")
            except:
                st.error("❌ MCP 서버 연결 실패")
            
            # 토큰 재발급 버튼
            if st.button("🔄 토큰 재발급"):
                with st.spinner("토큰을 재발급하는 중..."):
                    refresh_result = oauth_client.refresh_token(st.session_state.provider)
                    if "error" not in refresh_result:
                        st.session_state.access_token = refresh_result["access_token"]
                        st.success("✅ 토큰 재발급 완료")
                    else:
                        st.error(f"토큰 재발급 실패: {refresh_result['error']}")
    
    else:
        st.info("👆 사이드바에서 로그인하세요.")
        
        # 서비스 소개
        st.markdown("""
        ## 🚀 OAuth 이메일 서비스
        
        이 서비스는 안전한 OAuth2 인증을 사용하여 이메일을 관리합니다.
        
        ### ✨ 주요 기능
        - **🔐 안전한 인증**: OAuth2 표준 인증
        - **🍪 세션 관리**: HttpOnly 쿠키 기반 세션
        - **📧 이메일 조회**: Gmail, Outlook 지원
        - **🔄 자동 토큰 갱신**: 만료된 토큰 자동 재발급
        
        ### 🛡️ 보안 특징
        - HttpOnly 쿠키로 XSS 방지
        - SameSite=Strict로 CSRF 방지
        - Secure 플래그로 HTTPS 강제
        - 세션 기반 상태 관리
        """)

if __name__ == "__main__":
    main()
