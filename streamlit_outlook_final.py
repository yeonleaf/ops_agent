#!/usr/bin/env python3
"""
최종 안정화된 Streamlit Outlook 앱
간단하고 신뢰할 수 있는 상태 관리
"""

import streamlit as st
import os
import requests
import urllib.parse
from dotenv import load_dotenv
import secrets
import base64
import hashlib
import time
import json
import glob

# .env 파일 로드
load_dotenv()

# 로깅 설정 추가
from module.logging_config import setup_logging
import logging

# 로깅 초기화
setup_logging(level="INFO", log_file="logs/streamlit_outlook_final.log", console_output=True)
logger = logging.getLogger(__name__)

# 세션 상태 초기화
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

# 페이지 설정
st.set_page_config(
    page_title="📧 Outlook Final",
    page_icon="📧",
    layout="wide"
)

def get_azure_config():
    """Azure 설정 정보"""
    client_id = os.getenv("AZURE_CLIENT_ID")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    
    if not client_id or not tenant_id:
        st.error("❌ .env 파일에 AZURE_CLIENT_ID와 AZURE_TENANT_ID를 설정해주세요.")
        st.stop()
    
    return {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "redirect_uri": "http://localhost:8504",  # 새로운 포트
        "scope": "https://graph.microsoft.com/Mail.Read",
        "authority": f"https://login.microsoftonline.com/{tenant_id}"
    }

def create_pkce_pair():
    """RFC 7636 표준 PKCE 쌍 생성"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    # 길이 검증
    assert len(code_challenge) == 43, f"code_challenge 길이 오류: {len(code_challenge)}자"
    assert len(code_verifier) >= 43, f"code_verifier 길이 오류: {len(code_verifier)}자"
    
    return code_verifier, code_challenge

def save_auth_data(state, code_verifier):
    """인증 데이터를 예측 가능한 파일명으로 저장"""
    # state를 기반으로 한 파일명 생성 (예측 가능하고 고유함)
    import tempfile
    temp_dir = tempfile.gettempdir()
    
    # state에서 타임스탬프 추출하여 파일명 생성
    timestamp_part = state.split('_')[1] if '_' in state else str(int(time.time()))
    file_name = f"streamlit_auth_{timestamp_part}.json"
    file_path = os.path.join(temp_dir, file_name)
    
    auth_data = {
        "code_verifier": code_verifier,
        "state": state,
        "timestamp": int(time.time()),
        "file_path": file_path
    }
    
    with open(file_path, 'w') as f:
        json.dump(auth_data, f)
    
    st.info(f"🗃️ 인증 데이터 저장: {file_path}")
    return file_path

def load_auth_data_by_state(returned_state):
    """state를 기반으로 인증 데이터 로드"""
    import tempfile
    temp_dir = tempfile.gettempdir()
    
    # state에서 타임스탬프 추출
    try:
        timestamp_part = returned_state.split('_')[1] if '_' in returned_state else None
        if not timestamp_part:
            st.error("❌ 잘못된 state 형식입니다.")
            return None
            
        file_name = f"streamlit_auth_{timestamp_part}.json"
        file_path = os.path.join(temp_dir, file_name)
        
        st.info(f"🔍 인증 파일 찾는 중: {file_path}")
        
        if not os.path.exists(file_path):
            st.error(f"❌ 인증 파일을 찾을 수 없습니다: {file_path}")
            
            # 임시 디렉토리의 모든 인증 파일 목록 표시
            auth_files = glob.glob(os.path.join(temp_dir, "streamlit_auth_*.json"))
            if auth_files:
                st.info(f"🗂️ 발견된 인증 파일들: {len(auth_files)}개")
                for af in auth_files[:5]:  # 최대 5개만 표시
                    st.text(f"  - {os.path.basename(af)}")
            else:
                st.warning("🔍 임시 디렉토리에 인증 파일이 없습니다.")
            
            return None
        
        with open(file_path, 'r') as f:
            auth_data = json.load(f)
        
        # 파일 정리
        os.unlink(file_path)
        st.success(f"✅ 인증 데이터 로드 완료")
        
        return auth_data
        
    except Exception as e:
        st.error(f"❌ 인증 데이터 로드 오류: {str(e)}")
        return None

def generate_auth_url():
    """인증 URL 생성"""
    config = get_azure_config()
    
    # PKCE 파라미터 생성
    code_verifier, code_challenge = create_pkce_pair()
    
    # 현재 시간을 포함한 state 생성
    timestamp = int(time.time())
    random_part = secrets.token_urlsafe(8)
    state = f"st_{timestamp}_{random_part}"
    
    # 인증 데이터 저장
    auth_file = save_auth_data(state, code_verifier)
    
    # 인증 URL 구성
    auth_params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": config["redirect_uri"],
        "scope": config["scope"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account"
    }
    
    auth_url = f"{config['authority']}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(auth_params)
    
    st.success(f"🔑 PKCE 생성 완료!")
    st.info(f"📏 길이: verifier={len(code_verifier)}자, challenge={len(code_challenge)}자")
    st.info(f"🏷️ State: {state}")
    
    return auth_url

def exchange_code_for_token(auth_code, returned_state):
    """인증 코드를 토큰으로 교환"""
    config = get_azure_config()
    
    # state 기반으로 인증 데이터 로드
    auth_data = load_auth_data_by_state(returned_state)
    if not auth_data:
        return None
    
    code_verifier = auth_data['code_verifier']
    original_state = auth_data['state']
    timestamp = auth_data['timestamp']
    
    # State 검증
    if returned_state != original_state:
        st.error(f"❌ State 불일치!")
        st.code(f"예상: {original_state}\n실제: {returned_state}")
        return None
    
    # 시간 검증 (10분)
    if int(time.time()) - timestamp > 600:
        st.error("❌ 인증 세션이 만료되었습니다. (10분 초과)")
        return None
    
    st.success("✅ State 검증 완료")
    st.info(f"🔑 Code Verifier 사용: {code_verifier[:20]}...")
    
    # 토큰 요청
    token_data = {
        "client_id": config["client_id"],
        "scope": config["scope"],
        "code": auth_code,
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
        "code_verifier": code_verifier
    }
    
    token_url = f"{config['authority']}/oauth2/v2.0/token"
    
    try:
        st.info("🔄 토큰 교환 요청 중...")
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            st.success("✅ 토큰 획득 완료!")
            return response.json()
        else:
            st.error(f"❌ 토큰 교환 실패: {response.status_code}")
            error_details = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            
            with st.expander("오류 상세 정보"):
                st.json(error_details)
            
            return None
            
    except Exception as e:
        st.error(f"❌ 토큰 교환 오류: {str(e)}")
        return None

def get_unread_emails(access_token):
    """읽지 않은 메일 조회"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    api_url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
    params = {
        "$filter": "isRead eq false",
        "$select": "subject,sender,receivedDateTime,bodyPreview,importance,hasAttachments",
        "$orderby": "receivedDateTime desc",
        "$top": 15
    }
    
    try:
        with st.spinner("📧 메일 조회 중..."):
            response = requests.get(api_url, headers=headers, params=params)
            
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"❌ API 호출 실패: {response.status_code}")
            with st.expander("오류 상세 정보"):
                st.json(response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
            return None
            
    except Exception as e:
        st.error(f"❌ API 호출 오류: {str(e)}")
        return None

def display_emails(emails_data):
    """이메일 목록 표시"""
    if not emails_data or 'value' not in emails_data:
        st.warning("📭 메일 데이터를 가져올 수 없습니다.")
        return
    
    emails = emails_data['value']
    
    if not emails:
        st.success("📭 읽지 않은 메일이 없습니다!")
        return
    
    st.success(f"📬 읽지 않은 메일 {len(emails)}개를 찾았습니다!")
    
    for i, email in enumerate(emails, 1):
        with st.container():
            # 제목
            subject = email.get('subject', '제목 없음')
            importance_icon = ""
            if email.get('importance') == 'high':
                importance_icon = "🔴 "
            elif email.get('hasAttachments'):
                importance_icon = "📎 "
            
            st.markdown(f"### {importance_icon}{i}. {subject}")
            
            # 보낸이
            sender = email.get('sender', {}).get('emailAddress', {})
            sender_name = sender.get('name', '알 수 없음')
            sender_email = sender.get('address', '')
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**📧 보낸이:** {sender_name}")
                st.markdown(f"**📮 이메일:** `{sender_email}`")
                
                # 수신 시간
                received_time = email.get('receivedDateTime', '')
                if received_time:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(received_time.replace('Z', '+00:00'))
                        time_str = dt.strftime('%Y-%m-%d %H:%M')
                        st.markdown(f"**🕐 수신시간:** {time_str}")
                    except:
                        st.markdown(f"**🕐 수신시간:** {received_time}")
                
                # 본문 미리보기
                body_preview = email.get('bodyPreview', '')
                if body_preview:
                    preview = body_preview[:200] + "..." if len(body_preview) > 200 else body_preview
                    st.markdown(f"**💬 미리보기:** _{preview}_")
            
            with col2:
                st.markdown("**🟡 NEW**")
            
            st.markdown("---")

def cleanup_old_auth_files():
    """오래된 인증 파일들 정리"""
    import tempfile
    temp_dir = tempfile.gettempdir()
    
    try:
        auth_files = glob.glob(os.path.join(temp_dir, "streamlit_auth_*.json"))
        current_time = int(time.time())
        
        cleaned = 0
        for file_path in auth_files:
            try:
                # 파일명에서 타임스탬프 추출
                filename = os.path.basename(file_path)
                timestamp_str = filename.replace('streamlit_auth_', '').replace('.json', '')
                timestamp = int(timestamp_str)
                
                # 1시간 이상 된 파일 삭제
                if current_time - timestamp > 3600:
                    os.unlink(file_path)
                    cleaned += 1
            except:
                pass  # 파일명 형식이 맞지 않는 경우 무시
        
        if cleaned > 0:
            st.info(f"🗑️ 오래된 인증 파일 {cleaned}개 정리 완료")
            
    except Exception as e:
        st.warning(f"⚠️ 파일 정리 중 오류: {str(e)}")

def main():
    """메인 앱"""
    st.title("📧 Outlook 메일 조회 Final (안정화 버전)")
    
    # 오래된 파일 정리
    cleanup_old_auth_files()
    
    # URL 파라미터 확인
    query_params = st.query_params
    
    # 세션 정리 버튼
    if st.sidebar.button("🗑️ 세션 정리"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.query_params.clear()
        st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
    
    if 'code' in query_params and 'state' in query_params:
        # 인증 코드 처리
        auth_code = query_params['code']
        returned_state = query_params['state']
        
        st.info("🔄 Microsoft 로그인 처리 중...")
        st.info(f"📥 받은 State: {returned_state}")
        
        # 중복 처리 방지
        if not st.session_state.get('token_processed'):
            token_response = exchange_code_for_token(auth_code, returned_state)
            
            if token_response and 'access_token' in token_response:
                st.session_state.access_token = token_response['access_token']
                st.session_state.token_processed = True
                st.success("✅ 로그인 성공!")
                
                # URL 정리
                st.query_params.clear()
                time.sleep(1)
                st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
            else:
                st.error("❌ 로그인 실패")
                if st.button("🔄 다시 시도"):
                    st.query_params.clear()
                    st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
    
    # 토큰이 있는 경우 - 메일 조회
    elif 'access_token' in st.session_state:
        st.markdown("### 📬 읽지 않은 메일 조회")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("🔄 메일 새로고침", type="primary"):
                emails_data = get_unread_emails(st.session_state.access_token)
                if emails_data:
                    st.session_state.emails_data = emails_data
        
        with col2:
            if st.button("🚪 로그아웃"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.session_state.refresh_trigger = st.session_state.get('refresh_trigger', 0) + 1
        
        # 저장된 메일 데이터 표시
        if 'emails_data' in st.session_state:
            display_emails(st.session_state.emails_data)
        else:
            st.info("📧 '메일 새로고침' 버튼을 눌러 메일을 조회하세요.")
    
    else:
        # 로그인 화면
        st.markdown("### 🔐 Microsoft 계정 로그인")
        
        st.info("🎯 **Final 버전**: 예측 가능한 파일명 기반 상태 관리")
        
        config = get_azure_config()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info("Outlook 메일에 접근하려면 Microsoft 계정으로 로그인해주세요.")
            
            if st.button("📧 메일 가져오기 (로그인)", type="primary", use_container_width=True):
                auth_url = generate_auth_url()
                st.markdown(f"### 🔗 [Microsoft 로그인 하기]({auth_url})")
                st.markdown("**위 링크를 클릭하여 로그인하세요.**")
                st.warning("⚠️ **중요**: Azure에서 리디렉션 URI를 `http://localhost:8504`로 설정해야 합니다!")
        
        with col2:
            st.markdown("**⚙️ 설정 정보**")
            st.code(f"""
포트: 8504 (Final)
Client ID: {config['client_id'][:8]}...
Tenant ID: {config['tenant_id'][:8]}...
Redirect URI: {config['redirect_uri']}
            """)
    
    # 도움말
    with st.expander("ℹ️ Final 버전 특징"):
        st.markdown("""
        **✅ Final 버전 개선사항:**
        - 🗃️ 예측 가능한 파일명 (타임스탬프 기반)
        - 🔍 상세한 디버깅 정보 제공
        - 🗑️ 자동 파일 정리 (1시간 후)
        - 📁 임시 파일 위치 표시
        - ⚡ 새로운 포트 (8504) 사용
        
        **🔧 Azure 설정:**
        리디렉션 URI: `http://localhost:8504`
        
        **🐛 문제 해결:**
        - 파일을 찾을 수 없음: 디버깅 정보 확인
        - 세션 오류: "세션 정리" 후 재시도
        - 시간 만료: 10분 이내 완료 필요
        """)

if __name__ == "__main__":
    main()