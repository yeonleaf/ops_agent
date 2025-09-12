#!/usr/bin/env python3
"""
OAuth 콜백 서버
Google OAuth 인증 후 콜백을 처리하는 간단한 서버
"""

import os
import sys
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 환경 변수 로드
load_dotenv()

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth 콜백 처리 핸들러"""
    
    def get_user_email_from_google(self, access_token):
        """Google API로 사용자 이메일 조회"""
        try:
            import requests
            
            # Google UserInfo API 호출
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            print(f"🍪 Google UserInfo API 호출: {userinfo_url}")
            response = requests.get(userinfo_url, headers=headers)
            
            if response.status_code == 200:
                user_info = response.json()
                email = user_info.get('email')
                print(f"🍪 Google에서 사용자 이메일 조회: {email}")
                return email
            else:
                print(f"⚠️ Google UserInfo API 호출 실패: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"⚠️ Google 사용자 이메일 조회 중 오류: {e}")
            return None
    
    def save_google_token_by_email_direct(self, user_email, refresh_token):
        """이메일로 직접 Google 토큰 저장 (Google API 호출 불필요)"""
        try:
            # 인증 API 서버에 토큰 저장 요청 (이메일 기반)
            auth_api_url = "http://localhost:8001/user/integrations/google/by-email"
            headers = {"Content-Type": "application/json"}
            data = {
                "email": user_email,
                "refresh_token": refresh_token
            }
            
            print(f"🍪 API 요청: {auth_api_url}")
            print(f"🍪 요청 데이터: {data}")
            
            response = requests.post(auth_api_url, headers=headers, json=data)
            
            print(f"🍪 API 응답 상태: {response.status_code}")
            print(f"🍪 API 응답 내용: {response.text}")
            
            if response.status_code == 200:
                print(f"✅ Google 토큰이 사용자 계정에 저장되었습니다: {user_email}")
                return True
            else:
                print(f"⚠️ Google 토큰 저장 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️ Google 토큰 저장 중 오류: {e}")
            return False
    
    def exchange_code_for_tokens(self, code, state):
        """Authorization Code를 access_token과 refresh_token으로 교환"""
        try:
            # OAuth 설정
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            redirect_uri = "http://localhost:8000/auth/callback"
            token_url = "https://oauth2.googleapis.com/token"
            
            # 토큰 교환 요청
            token_data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            
            token_response = response.json()
            
            return {
                "success": True,
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "expires_in": token_response.get("expires_in"),
                "token_type": token_response.get("token_type", "Bearer")
            }
            
        except Exception as e:
            print(f"❌ 토큰 교환 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def set_secure_cookie(self, name, value, max_age=7*24*60*60):
        """보안 쿠키 설정 (HttpOnly, Secure, SameSite=Strict)"""
        # HttpOnly, Secure, SameSite=Strict 속성으로 쿠키 설정
        cookie_value = f"{name}={value}; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict; Path=/"
        return cookie_value
    
    def do_GET(self):
        """GET 요청 처리"""
        try:
            # URL 파싱
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # OAuth 콜백 파라미터 추출
            code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            error = query_params.get('error', [None])[0]
            
            # state에서 사용자 이메일 추출
            user_email = None
            if state and state.startswith('email_'):
                user_email = state[6:]  # 'email_' 제거
                print(f"🍪 OAuth 콜백: state에서 이메일 추출: {user_email}")
            else:
                print("🍪 OAuth 콜백: state에 이메일이 없음")
            
            if error:
                # OAuth 오류 처리
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                error_message = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>OAuth 인증 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .error {{ color: #d32f2f; font-size: 18px; margin-bottom: 20px; }}
                        .info {{ color: #666; margin-bottom: 15px; }}
                        .button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>❌ OAuth 인증 오류</h1>
                        <div class="error">오류: {error}</div>
                        <div class="info">OAuth 인증 중 오류가 발생했습니다.</div>
                        <div class="info">다시 시도해주세요.</div>
                        <button class="button" onclick="window.close()">창 닫기</button>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(error_message.encode('utf-8'))
                return
            
            if code and state:
                # Authorization Code를 토큰으로 교환
                print(f"🔄 Authorization Code를 토큰으로 교환 중...")
                token_result = self.exchange_code_for_tokens(code, state)
                
                if token_result["success"]:
                    # 토큰 교환 성공
                    access_token = token_result["access_token"]
                    refresh_token = token_result["refresh_token"]
                    expires_in = token_result["expires_in"]
                    
                    # state에서 추출한 이메일로 DB에 토큰 저장
                    if user_email:
                        print(f"🍪 DB에 Google 토큰 저장 시도: {user_email}")
                        self.save_google_token_by_email_direct(user_email, refresh_token)
                    else:
                        print("🍪 이메일이 없어서 DB 저장 불가")
                    
                    # 응답 헤더 설정 (쿠키 로직 제거)
                    self.send_response(302)  # 리디렉션
                    # 토큰을 URL 파라미터로만 전달
                    redirect_url = f"http://localhost:8501?access_token={access_token}&refresh_token={refresh_token}"
                    self.send_header('Location', redirect_url)
                    self.end_headers()
                    
                    # 콘솔에 성공 메시지 출력
                    print(f"\n🎉 OAuth 인증 완료!")
                    print(f"✅ Access Token: {access_token[:20]}...")
                    print(f"✅ Refresh Token: {refresh_token[:20]}...")
                    print(f"⏰ 만료 시간: {expires_in}초")
                    if session_id:
                        print(f"👤 로그인된 사용자에게 Google 토큰 저장 완료")
                    print(f"🔄 Streamlit 앱으로 리디렉션 중...")
                    
                else:
                    # 토큰 교환 실패
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    
                    error_message = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>OAuth 토큰 교환 실패</title>
                        <meta charset="utf-8">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                            .error {{ color: #d32f2f; font-size: 18px; margin-bottom: 20px; }}
                            .info {{ color: #666; margin-bottom: 15px; }}
                            .button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>❌ OAuth 토큰 교환 실패</h1>
                            <div class="error">오류: {token_result["error"]}</div>
                            <div class="info">토큰 교환 중 오류가 발생했습니다.</div>
                            <div class="info">다시 시도해주세요.</div>
                            <button class="button" onclick="window.close()">창 닫기</button>
                        </div>
                    </body>
                    </html>
                    """
                    self.wfile.write(error_message.encode('utf-8'))
                    
                    print(f"❌ 토큰 교환 실패: {token_result['error']}")
                
            else:
                # 잘못된 요청
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                error_message = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>잘못된 요청</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>❌ 잘못된 요청</h1>
                    <p>OAuth 콜백 파라미터가 올바르지 않습니다.</p>
                </body>
                </html>
                """
                self.wfile.write(error_message.encode('utf-8'))
                
        except Exception as e:
            print(f"❌ OAuth 콜백 처리 오류: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
    
    def log_message(self, format, *args):
        """로그 메시지 출력 비활성화"""
        pass

def start_oauth_callback_server(port=8000):
    """OAuth 콜백 서버 시작"""
    try:
        server = HTTPServer(('localhost', port), OAuthCallbackHandler)
        print(f"🚀 OAuth 콜백 서버 시작: http://localhost:{port}")
        print(f"📧 Gmail OAuth 인증을 기다리는 중...")
        print(f"💡 브라우저에서 OAuth URL을 열어 인증을 완료하세요.")
        print(f"🔄 서버를 중지하려면 Ctrl+C를 누르세요.")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print(f"\n🛑 OAuth 콜백 서버 중지")
        server.shutdown()
    except Exception as e:
        print(f"❌ 서버 시작 오류: {e}")

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("❌ 잘못된 포트 번호입니다. 기본값 8000을 사용합니다.")
    
    start_oauth_callback_server(port)
