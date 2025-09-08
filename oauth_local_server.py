#!/usr/bin/env python3
"""
OAuth 2.0 리디렉션을 처리하는 간단한 로컬 서버 - 시크릿 모드 자동 연결
"""

import http.server
import socketserver
import urllib.parse
import threading
import time
import webbrowser
from urllib.parse import parse_qs, urlparse

class OAuthHandler(http.server.BaseHTTPRequestHandler):
    """OAuth 리디렉션을 처리하는 HTTP 핸들러"""
    
    # 클래스 변수로 인증 코드 저장
    auth_code = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """GET 요청 처리"""
        try:
            # URL 파싱
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            print(f"🔍 요청 받음: {self.path}")
            print(f"📝 쿼리 파라미터: {query_params}")
            
            # 인증 코드 추출
            if 'code' in query_params:
                OAuthHandler.auth_code = query_params['code'][0]
                print(f"✅ 인증 코드 추출: {OAuthHandler.auth_code}")
                
                # 성공 페이지 응답
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                success_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>OAuth 인증 성공</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                        .success {{ color: #28a745; font-size: 24px; margin-bottom: 20px; }}
                        .code {{ background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; margin: 20px 0; }}
                        .info {{ color: #6c757d; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="success">✅ OAuth 인증 성공!</div>
                    <p>인증 코드가 생성되었습니다.</p>
                    <div class="code">{OAuthHandler.auth_code}</div>
                    <p>이제 메인 앱에서 자동으로 토큰이 처리됩니다.</p>
                    <div class="info">이 창은 닫아도 됩니다.</div>
                </body>
                </html>
                """
                
                try:
                    self.wfile.write(success_html.encode('utf-8'))
                    print("✅ 성공 페이지 응답 완료")
                except Exception as e:
                    print(f"❌ 응답 작성 실패: {e}")
                
                # 서버 종료 신호
                try:
                    self.server.should_stop = True
                    print("🛑 서버 종료 신호 전송")
                except Exception as e:
                    print(f"❌ 서버 종료 신호 실패: {e}")
                
            else:
                print(f"⚠️  인증 코드 없음: {query_params}")
                # 오류 페이지 응답
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>OAuth 인증 오류</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .error { color: #dc3545; font-size: 24px; margin-bottom: 20px; }
                    </style>
                </head>
                <body>
                    <div class="error">❌ OAuth 인증 오류</div>
                    <p>인증 코드를 찾을 수 없습니다.</p>
                </body>
                </html>
                """
                
                try:
                    self.wfile.write(error_html.encode('utf-8'))
                except Exception as e:
                    print(f"❌ 오류 페이지 응답 실패: {e}")
                
        except Exception as e:
            print(f"❌ OAuth 핸들러 오류: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Internal Server Error: {str(e)}".encode('utf-8'))
            except:
                pass
    
    def log_message(self, format, *args):
        """로그 메시지 비활성화"""
        pass

class OAuthLocalServer:
    """OAuth 리디렉션을 처리하는 로컬 서버"""
    
    def __init__(self, port=8081):
        self.port = port
        self.server = None
        self.auth_code = None
        self.handler_instance = None
    
    def start(self):
        """서버 시작"""
        try:
            # 서버 설정
            handler = type('OAuthHandler', (OAuthHandler,), {})
            handler.auth_code = None
            
            with socketserver.TCPServer(("", self.port), handler) as httpd:
                self.server = httpd
                self.server.should_stop = False
                
                print(f"🌐 OAuth 리디렉션 서버가 포트 {self.port}에서 시작되었습니다.")
                print(f"🔗 리디렉션 URI: http://localhost:{self.port}")
                
                # 서버 실행 (별도 스레드)
                server_thread = threading.Thread(target=self._run_server)
                server_thread.daemon = True
                server_thread.start()
                
                # 인증 코드 대기
                while not self.server.should_stop:
                    time.sleep(0.1)
                
                # 인증 코드 반환
                if OAuthHandler.auth_code:
                    self.auth_code = OAuthHandler.auth_code
                    return self.auth_code
                
        except Exception as e:
            print(f"❌ 서버 시작 실패: {e}")
            return None
    
    def _run_server(self):
        """서버 실행 (별도 스레드)"""
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"서버 실행 오류: {e}")
    
    def stop(self):
        """서버 중지"""
        if self.server:
            self.server.shutdown()
            print("🛑 OAuth 서버가 중지되었습니다.")

def get_oauth_auth_code(client_id: str, client_secret: str, scopes: list) -> dict:
    """OAuth 인증 코드를 가져오는 함수 - 시크릿 모드 자동 연결"""
    try:
        import requests
        
        print("🔐 Gmail 계정 인증을 시작합니다...")
        print("💡 시크릿 모드로 자동 연결하여 OAuth 2.0 플로우를 진행합니다 (포트 8081).")
        print()
        
        # 포트 8081 사용
        redirect_port = 8081
        redirect_uri = f'http://localhost:{redirect_port}'
        
        # 간단한 인증 URL 생성 (복잡한 파라미터 제거)
        auth_params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(scopes),
            'access_type': 'offline'
        }
        
        auth_url = "https://accounts.google.com/o/oauth2/auth?" + "&".join([
            f"{k}={requests.utils.quote(v)}" for k, v in auth_params.items()
        ])
        
        print(f"🔗 인증 링크: {auth_url}")
        print()
        print("💡 시크릿 모드로 브라우저가 자동으로 열립니다.")
        print("🔒 시크릿 모드에서 Gmail 계정으로 로그인하고 권한을 승인해주세요.")
        print(f"🔧 리디렉션 URI: {redirect_uri}")
        print("⚠️  만약 브라우저가 열리지 않으면, 위 링크를 수동으로 복사해서 시크릿 모드에서 열어주세요.")
        
        # 시크릿 모드로 브라우저 열기 시도 (다양한 방법)
        browser_opened = False
        print("🔍 브라우저 자동 열기 시도 중...")
        
        try:
            # 방법 1: 강제로 새 Chrome 시크릿 모드 창 열기
            import os
            try:
                print("🔄 방법 1: 강제 새 Chrome 시크릿 모드 창 열기...")
                # 기존 Chrome 프로세스 종료 후 새로 시작
                os.system('pkill -f "Google Chrome" 2>/dev/null')
                time.sleep(1)  # 프로세스 종료 대기
                
                chrome_cmd = f'open -a "Google Chrome" --args --incognito --new-window --start-maximized "{auth_url}"'
                result = os.system(chrome_cmd)
                if result == 0:
                    browser_opened = True
                    print("✅ Chrome 시크릿 모드로 새 브라우저 창 열기 성공")
                else:
                    print(f"⚠️  Chrome 시크릿 모드 실패: {result}")
            except Exception as e:
                print(f"⚠️  Chrome 실행 오류: {e}")
            
            # 방법 2: AppleScript를 사용한 강제 새 창 열기
            if not browser_opened:
                try:
                    print("🔄 방법 2: AppleScript로 Chrome 시크릿 모드 강제 열기...")
                    apple_script = f'''
                    tell application "Google Chrome"
                        activate
                        make new window with properties {{mode:"incognito"}}
                        set URL of active tab of front window to "{auth_url}"
                    end tell
                    '''
                    
                    apple_script_cmd = f'osascript -e \'{apple_script}\''
                    result = os.system(apple_script_cmd)
                    if result == 0:
                        browser_opened = True
                        print("✅ AppleScript로 Chrome 시크릿 모드 열기 성공")
                    else:
                        print(f"⚠️  AppleScript Chrome 실행 실패: {result}")
                except Exception as e:
                    print(f"⚠️  AppleScript 실행 오류: {e}")
            
            # 방법 3: Safari 강제 새 시크릿 모드 창 열기
            if not browser_opened:
                try:
                    print("🔄 방법 3: Safari 시크릿 모드 강제 열기...")
                    os.system('pkill -f "Safari" 2>/dev/null')
                    time.sleep(1)
                    
                    safari_cmd = f'open -a Safari --args --private "{auth_url}"'
                    result = os.system(safari_cmd)
                    if result == 0:
                        browser_opened = True
                        print("✅ Safari 시크릿 모드로 새 브라우저 창 열기 성공")
                    else:
                        print(f"⚠️  Safari 시크릿 모드 실패: {result}")
                except Exception as e:
                    print(f"⚠️  Safari 실행 오류: {e}")
            
            # 방법 4: 기본 브라우저로 강제 열기
            if not browser_opened:
                try:
                    print("🔄 방법 4: 기본 브라우저 강제 열기...")
                    # 기본 브라우저 프로세스 종료 후 새로 시작
                    os.system('pkill -f "Safari" 2>/dev/null')
                    os.system('pkill -f "Google Chrome" 2>/dev/null')
                    time.sleep(1)
                    
                    webbrowser.open(auth_url)
                    browser_opened = True
                    print("✅ 기본 브라우저로 새 창 열기 성공")
                except Exception as e:
                    print(f"⚠️  기본 브라우저 열기 실패: {e}")
            
            # 결과 안내
            if browser_opened:
                print("💡 브라우저가 열렸습니다!")
                print("🔒 시크릿 모드에서 Gmail 계정으로 로그인하고 권한을 승인해주세요.")
                print("⚠️  만약 일반 모드로 열렸다면, 수동으로 시크릿 모드로 전환해주세요.")
            else:
                print("❌ 모든 브라우저 열기 시도 실패")
                print("💡 아래 링크를 수동으로 복사해서 시크릿 모드에서 열어주세요:")
                print(f"🔗 {auth_url}")
                print("📋 링크 복사 방법:")
                print("   1. 위 링크를 마우스로 드래그하여 선택")
                print("   2. Cmd+C로 복사")
                print("   3. 브라우저에서 Cmd+Shift+N (Chrome) 또는 Cmd+Shift+P (Safari)")
                print("   4. Cmd+V로 붙여넣기")
                
        except Exception as e:
            print(f"❌ 브라우저 자동 열기 중 예외 발생: {e}")
            print("💡 위 링크를 수동으로 복사해서 시크릿 모드에서 열어주세요.")
        
        # 로컬 서버 시작하여 리디렉션 처리
        oauth_server = OAuthLocalServer(port=redirect_port)
        auth_code = oauth_server.start()
        
        if auth_code:
            print(f"✅ 인증 코드 획득: {auth_code}")
            
            # 토큰 교환 (PKCE 없이)
            print("🔄 토큰 교환 중...")
            token_response = exchange_code_for_tokens_simple(
                client_id, client_secret, auth_code, redirect_uri
            )
            
            if token_response:
                print("✅ 토큰 교환 성공!")
                print("💾 이제 메인 앱에서 자동으로 .env 파일이 업데이트됩니다.")
                
                # .env 파일 즉시 업데이트 확인
                _verify_env_update(token_response.get('refresh_token'))
                
                return token_response
            else:
                print("❌ 토큰 교환 실패")
                return None
        else:
            print("❌ 인증 코드를 가져올 수 없습니다.")
            return None
            
    except Exception as e:
        print(f"❌ OAuth 인증 실패: {e}")
        return None

def exchange_code_for_tokens_simple(client_id: str, client_secret: str, auth_code: str, redirect_uri: str) -> dict:
    """인증 코드를 액세스 토큰으로 교환 (간단한 방식)"""
    try:
        import requests
        
        print(f"🔄 토큰 교환 시작...")
        print(f"   클라이언트 ID: {client_id[:20]}...")
        print(f"   인증 코드: {auth_code[:20]}...")
        print(f"   리디렉션 URI: {redirect_uri}")
        
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': auth_code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        print(f"📤 토큰 교환 요청 전송 중...")
        response = requests.post(token_url, data=token_data)
        
        print(f"📥 응답 수신: {response.status_code}")
        
        if response.status_code == 200:
            token_info = response.json()
            print("✅ 토큰 교환 성공!")
            print(f"   액세스 토큰: {token_info.get('access_token', 'N/A')[:20]}...")
            print(f"   리프레시 토큰: {token_info.get('refresh_token', 'N/A')[:20]}...")
            print(f"   만료 시간: {token_info.get('expires_in', 'N/A')}초")
            print(f"   토큰 타입: {token_info.get('token_type', 'N/A')}")
            return token_info
        else:
            print(f"❌ 토큰 교환 실패: {response.status_code}")
            print(f"   오류 응답: {response.text}")
            print(f"   요청 헤더: {dict(response.request.headers)}")
            print(f"   요청 데이터: {token_data}")
            return None
            
    except Exception as e:
        print(f"❌ 토큰 교환 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def _verify_env_update(refresh_token: str) -> None:
        """환경 변수 업데이트 확인 및 안내"""
        try:
            import os
            import time
            
            print("🔍 .env 파일 업데이트 확인 중...")
            
            # 잠시 대기 후 .env 파일 확인
            time.sleep(2)
            
            if os.path.exists('.env'):
                try:
                    with open('.env', 'r', encoding='utf-8') as f:
                        env_content = f.read()
                    
                    if f'GMAIL_REFRESH_TOKEN={refresh_token}' in env_content:
                        print("✅ .env 파일에 새로운 리프레시 토큰이 성공적으로 저장되었습니다!")
                        print("🔄 이제 메인 앱을 다시 실행하면 새로운 토큰을 사용할 수 있습니다.")
                        print("💡 앱 재시작 방법:")
                        print("   1. 현재 앱 종료")
                        print("   2. 터미널에서 'python [앱파일명].py' 실행")
                        print("   3. 새로운 토큰으로 Gmail API 사용")
                    else:
                        print("⚠️  .env 파일에 새로운 리프레시 토큰이 저장되지 않았습니다.")
                        print("💡 수동으로 .env 파일을 확인해주세요.")
                        
                except Exception as e:
                    print(f"⚠️  .env 파일 읽기 실패: {e}")
            else:
                print("⚠️  .env 파일이 존재하지 않습니다.")
                
        except Exception as e:
            print(f"⚠️  .env 업데이트 확인 실패: {e}")

if __name__ == "__main__":
    # 테스트
    print("🚀 OAuth 로컬 서버 테스트 (포트 8081) - 시크릿 모드 자동 연결")
    
    # 환경변수에서 Gmail 설정 가져오기
    import os
    from setup_gmail_env import load_env_file
    
    load_env_file()
    
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    
    if client_id and client_secret:
        scopes = ['https://www.googleapis.com/auth/gmail.readonly']
        token_info = get_oauth_auth_code(client_id, client_secret, scopes)
        
        if token_info:
            print(f"🎉 인증 성공! 액세스 토큰: {token_info.get('access_token', 'N/A')[:20]}...")
            print(f"🔄 리프레시 토큰: {token_info.get('refresh_token', 'N/A')[:20]}...")
        else:
            print("❌ 인증 실패")
    else:
        print("❌ Gmail 환경변수가 설정되지 않았습니다.")
