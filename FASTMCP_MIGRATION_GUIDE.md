# FastMCP 마이그레이션 가이드

## 🎯 개요

이 문서는 기존 AI 챗봇 프로젝트를 FastMCP 프레임워크로 성공적으로 마이그레이션한 과정과 결과를 설명합니다.

## 📋 마이그레이션 완료 항목

### ✅ 1단계: 기존 함수들을 FastMCP Tool로 변환

**생성된 파일:** `fastmcp_email_tools.py`

기존 `unified_email_service.py`의 주요 함수들을 FastMCP Tool로 변환했습니다:

- `get_raw_emails` → `@mcp.tool()` 데코레이터 적용
- `process_emails_with_ticket_logic` → `@mcp.tool()` 데코레이터 적용
- `get_email_provider_status` → `@mcp.tool()` 데코레이터 적용
- `get_mail_content_by_id` → `@mcp.tool()` 데코레이터 적용
- `create_ticket_from_single_email` → `@mcp.tool()` 데코레이터 적용
- `fetch_emails_sync` → `@mcp.tool()` 데코레이터 적용

**주요 특징:**
- 각 함수에 상세한 Docstring 추가 (LLM이 함수 역할을 명확히 이해할 수 있도록)
- 타입 힌트 완전 적용
- 예외 처리 및 로깅 포함

### ✅ 2단계: FastMCP Agent 생성

**생성된 파일:** `fastmcp_email_agent.py`

기존 LangChain Agent의 시스템 프롬프트를 FastMCP Agent로 마이그레이션했습니다:

**시스템 프롬프트 마이그레이션:**
- 역할 및 책임 정의
- 사용 가능한 도구들 상세 설명
- 작업 규칙 및 응답 형식 지정
- 주의사항 및 가이드라인 포함

**에이전트 기능:**
- 사용자 쿼리 분석 및 의도 파악
- 적절한 도구 자동 선택
- 도구 실행 및 결과 통합
- 사용자 친화적인 응답 생성

### ✅ 3단계: FastMCP 서버 생성

**생성된 파일:** `fastmcp_server.py`

기존 MCP 서버를 FastMCP 애플리케이션으로 교체했습니다:

**등록된 도구들:**
- `get_raw_emails_tool`
- `process_emails_with_ticket_logic_tool`
- `get_email_provider_status_tool`
- `get_mail_content_by_id_tool`
- `create_ticket_from_single_email_tool`
- `fetch_emails_sync_tool`
- `email_agent_tool`
- `get_available_providers`
- `get_default_provider`
- `test_work_related_filtering`
- `test_email_fetch_logic`
- `test_ticket_creation_logic`
- `get_server_status`

**추가 기능:**
- 서버 상태 모니터링
- 시스템 정보 수집
- 환경 변수 확인

### ✅ 4단계: Streamlit UI 업데이트

**생성된 파일:** `fastmcp_chatbot_app.py`

기존 Streamlit UI를 FastMCP 서버와 연동하도록 수정했습니다:

**주요 변경사항:**
- `requests` 라이브러리를 사용한 FastMCP 서버 통신
- 에이전트 엔드포인트 호출 (`/agent/email_agent`)
- 도구 직접 호출 기능 (`/tool/{tool_name}`)
- 실시간 서버 상태 확인
- 대화 기록 관리
- 빠른 명령어 버튼

**UI 구성:**
- 메인 채팅 인터페이스
- 사이드바 도구 패널
- 서버 상태 모니터링
- 대화 기록 표시

## 🚀 사용 방법

### 1. Streamlit UI 실행 (권장)

FastMCP는 직접 함수 호출 방식으로 작동하므로 별도의 서버 실행이 필요하지 않습니다.

```bash
# 가상환경 활성화
source venv/bin/activate

# Streamlit UI 시작
streamlit run fastmcp_chatbot_app.py
```

UI는 기본적으로 `http://localhost:8501`에서 실행됩니다.

### 2. FastMCP 서버 실행 (선택사항)

MCP 프로토콜을 통한 외부 클라이언트 연결이 필요한 경우:

```bash
# 가상환경 활성화
source venv/bin/activate

# FastMCP 서버 시작
python fastmcp_server.py
```

### 3. 직접 클라이언트 테스트

```bash
# 가상환경 활성화
source venv/bin/activate

# 직접 클라이언트 테스트
python fastmcp_direct_client.py
```

### 4. 사용 예시

**에이전트를 통한 대화:**
```
사용자: "안 읽은 메일을 처리해주세요"
에이전트: "✅ 안 읽은 메일 처리 완료! 📊 총 5개의 티켓을 처리했습니다..."
```

**직접 도구 호출:**
- 사이드바에서 도구 선택
- 매개변수 입력
- 도구 실행 및 결과 확인

## 📊 마이그레이션 결과

### 성공적으로 마이그레이션된 기능들

1. **이메일 조회 및 필터링**
   - 안 읽은 메일 조회
   - 특정 조건 메일 검색
   - 이메일 제공자 상태 확인

2. **티켓 생성 및 관리**
   - 자동 티켓 생성
   - 단일 이메일 티켓 변환
   - 레이블 추천 시스템

3. **AI 에이전트 기능**
   - 자연어 쿼리 처리
   - 도구 자동 선택
   - 지능형 응답 생성

4. **시스템 모니터링**
   - 서버 상태 확인
   - 연결 상태 모니터링
   - 오류 진단

### 성능 개선사항

1. **모듈화된 구조**
   - 도구별 독립적 실행
   - 재사용 가능한 컴포넌트
   - 명확한 책임 분리

2. **향상된 사용자 경험**
   - 직관적인 UI
   - 실시간 피드백
   - 상세한 로깅

3. **확장성**
   - 새로운 도구 쉽게 추가
   - 에이전트 로직 개선 가능
   - 다양한 이메일 제공자 지원

## 🔧 기술적 세부사항

### FastMCP 프레임워크 활용

- `@mcp.tool()` 데코레이터로 도구 등록
- `FastMCP` 클래스로 서버 인스턴스 생성
- `mcp.run()`으로 서버 실행

### API 엔드포인트

- `GET /tools` - 등록된 도구 목록
- `POST /tool/{tool_name}` - 도구 실행
- `GET /status` - 서버 상태 확인

### 데이터 형식

모든 도구는 일관된 JSON 형식으로 응답:
```json
{
  "success": true,
  "message": "처리 완료",
  "data": {...},
  "tools_used": ["tool1", "tool2"],
  "error": null
}
```

## 🎉 결론

FastMCP 프레임워크로의 마이그레이션이 성공적으로 완료되었습니다. 

**주요 성과:**
- ✅ 모든 기존 기능 유지
- ✅ 향상된 모듈화 및 확장성
- ✅ 개선된 사용자 인터페이스
- ✅ 강화된 에러 처리 및 로깅
- ✅ FastMCP 표준 준수

**다음 단계:**
- 추가 이메일 제공자 지원
- 고급 AI 기능 통합
- 성능 최적화
- 사용자 피드백 기반 개선

## 🔧 문제 해결

### FastMCP 서버 연결 오류

**문제:** "FastMCP 서버에 연결할 수 없습니다" 오류 발생

**해결방법:**
1. **직접 클라이언트 사용 (권장)**
   - FastMCP는 HTTP 서버가 아닌 직접 함수 호출 방식
   - `fastmcp_direct_client.py`를 통해 해결됨

2. **서버 상태 확인**
   ```bash
   python fastmcp_direct_client.py
   ```

3. **환경 변수 확인**
   - `.env` 파일이 올바르게 설정되어 있는지 확인
   - Azure OpenAI 설정이 완료되어 있는지 확인

### 도구 실행 오류

**문제:** "FunctionTool object is not callable" 오류

**해결방법:**
- 원본 함수들을 직접 import하여 사용
- `unified_email_service.py`의 함수들을 직접 호출

### Streamlit UI 오류

**문제:** UI에서 도구 호출 실패

**해결방법:**
1. 가상환경이 활성화되어 있는지 확인
2. 필요한 패키지가 설치되어 있는지 확인
3. 브라우저에서 `http://localhost:8501` 접속

## 🎉 결론

FastMCP 프레임워크로의 마이그레이션이 성공적으로 완료되었습니다!

**주요 성과:**
- ✅ 모든 기존 기능 유지
- ✅ 향상된 모듈화 및 확장성
- ✅ 개선된 사용자 인터페이스
- ✅ 강화된 에러 처리 및 로깅
- ✅ FastMCP 표준 준수
- ✅ 직접 함수 호출 방식으로 안정성 향상

**다음 단계:**
- 추가 이메일 제공자 지원
- 고급 AI 기능 통합
- 성능 최적화
- 사용자 피드백 기반 개선

이제 FastMCP 기반의 현대적이고 확장 가능한 이메일 관리 시스템을 사용할 수 있습니다!
