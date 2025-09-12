# OAuth2 인증 및 토큰 관리 시스템 설정 가이드

## 🎯 개요

이 시스템은 안전한 OAuth2 인증과 HttpOnly 쿠키 기반의 세션 관리를 제공합니다. 기존의 불안정한 .env 파일 기반 인증을 폐기하고, 표준적인 보안 메커니즘을 도입했습니다.

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   OAuth Server  │    │   MCP Server    │
│   (Streamlit)   │◄──►│   (Port 8000)   │◄──►│   (Port 8505)   │
│   (Port 8501)   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 설치 및 설정

### 1. 의존성 설치

```bash
pip install fastapi uvicorn requests streamlit python-multipart python-jose passlib
```

### 2. 환경 설정

```bash
# 설정 파일 복사
cp oauth_config.env .env

# .env 파일 편집
nano .env
```

`.env` 파일에 다음 정보를 입력하세요:

```env
# Google OAuth 설정
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft OAuth 설정
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_TENANT_ID=common

# 서버 설정
OAUTH_SERVER_PORT=8000
MCP_SERVER_PORT=8505
FRONTEND_URL=http://localhost:8501

# 보안 설정
SESSION_SECRET_KEY=your-super-secret-session-key-here
COOKIE_DOMAIN=localhost
SECURE_COOKIES=true
```

### 3. OAuth 앱 등록

#### Google OAuth 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" > "사용자 인증 정보" 이동
4. "사용자 인증 정보 만들기" > "OAuth 2.0 클라이언트 ID" 선택
5. 애플리케이션 유형: "웹 애플리케이션"
6. 승인된 리디렉션 URI 추가:
   - `http://localhost:8000/auth/callback`
7. 클라이언트 ID와 시크릿을 `.env` 파일에 입력

#### Microsoft OAuth 설정

1. [Azure Portal](https://portal.azure.com/) 접속
2. "Azure Active Directory" > "앱 등록" 이동
3. "새 등록" 클릭
4. 애플리케이션 이름 입력
5. 지원되는 계정 유형: "모든 조직 디렉터리의 계정"
6. 리디렉션 URI: `http://localhost:8000/auth/callback`
7. 클라이언트 ID, 시크릿, 테넌트 ID를 `.env` 파일에 입력

## 🚀 실행 방법

### 방법 1: 자동 실행 (권장)

```bash
python run_oauth_services.py
```

이 명령어는 다음을 자동으로 실행합니다:
- OAuth 서버 (포트 8000)
- MCP 서버 (포트 8505)
- Streamlit 앱 (포트 8501)

### 방법 2: 수동 실행

#### 터미널 1: OAuth 서버
```bash
python oauth_auth_server.py
```

#### 터미널 2: MCP 서버
```bash
python secure_mcp_server.py
```

#### 터미널 3: Streamlit 앱
```bash
streamlit run oauth_client_integration.py --server.port 8501
```

## 🧪 테스트

### 1. 엔드포인트 테스트

```bash
python test_oauth_endpoints.py
```

### 2. 수동 테스트

1. 브라우저에서 `http://localhost:8501` 접속
2. Gmail 또는 Outlook 로그인 클릭
3. OAuth 인증 완료
4. 이메일 서비스 사용

## 📋 API 엔드포인트

### OAuth 서버 (포트 8000)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 서버 상태 확인 |
| `/auth/login/{provider}` | GET | OAuth 로그인 시작 |
| `/auth/callback` | GET | OAuth 콜백 처리 |
| `/auth/refresh` | POST | 토큰 재발급 |
| `/auth/status` | GET | 인증 상태 확인 |
| `/auth/logout` | POST | 로그아웃 |

### MCP 서버 (포트 8505)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 서버 상태 확인 |
| `/health` | GET | 헬스 체크 |
| `/get_authenticated_emails` | GET | 인증된 이메일 조회 |
| `/create_authenticated_ticket` | POST | 인증된 티켓 생성 |
| `/refresh_authentication` | POST | 인증 토큰 재발급 |
| `/get_auth_status` | GET | 인증 상태 확인 |

## 🔒 보안 특징

### 1. HttpOnly 쿠키
- XSS 공격 방지
- JavaScript로 쿠키 접근 불가

### 2. SameSite=Strict
- CSRF 공격 방지
- 동일 사이트에서만 쿠키 전송

### 3. Secure 플래그
- HTTPS에서만 쿠키 전송
- 네트워크 스니핑 방지

### 4. 세션 관리
- 서버 사이드 세션 저장
- 자동 만료 처리
- 안전한 세션 ID 생성

## 🐛 문제 해결

### 1. OAuth 인증 실패

**문제**: "OAuth 설정이 완료되지 않았습니다"
**해결**: `.env` 파일의 OAuth 설정 확인

**문제**: "리디렉션 URI가 일치하지 않습니다"
**해결**: OAuth 앱 등록에서 리디렉션 URI 확인

### 2. 쿠키 문제

**문제**: 쿠키가 설정되지 않음
**해결**: 브라우저에서 쿠키 허용 확인

**문제**: "유효하지 않은 세션입니다"
**해결**: 로그아웃 후 재로그인

### 3. 서버 연결 실패

**문제**: "MCP 서버 연결 실패"
**해결**: MCP 서버가 실행 중인지 확인

**문제**: "인증 서버 연결 실패"
**해결**: OAuth 서버가 실행 중인지 확인

## 📚 추가 정보

### 개발 모드 실행

```bash
# 디버그 모드로 OAuth 서버 실행
uvicorn oauth_auth_server:app --host 0.0.0.0 --port 8000 --reload

# 디버그 모드로 MCP 서버 실행
uvicorn secure_mcp_server:app --host 0.0.0.0 --port 8505 --reload
```

### 로그 확인

```bash
# OAuth 서버 로그
tail -f oauth_server.log

# MCP 서버 로그
tail -f mcp_server.log
```

### 프로덕션 배포

1. HTTPS 인증서 설정
2. 도메인 설정
3. 환경 변수 보안 강화
4. 로드 밸런서 설정
5. 모니터링 도구 연동

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 라이선스

MIT License
