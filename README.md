# 🤖 AI 메일 조회 챗봇 (통합 이메일 서비스)

Azure OpenAI와 LangChain을 사용한 지능형 메일 관리 시스템으로, Gmail과 Microsoft Graph API를 선택적으로 사용할 수 있습니다.

## ✨ 주요 기능

### 🔄 **유연한 이메일 제공자 선택**
- **Gmail API**: Google Gmail 연동
- **Microsoft Graph API**: Outlook/Office 365 연동
- **동적 전환**: 설정 파일 하나만 변경하면 즉시 전환 가능
- **자동 감지**: 환경변수에 따라 사용 가능한 제공자 자동 감지

### 🎯 **통일된 데이터 모델**
- Gmail과 Graph API의 데이터를 동일한 형식으로 변환
- 기존 티켓 UI와 완벽 호환
- 타입 안전성을 위한 Pydantic 모델 사용

### 🧠 **AI 기반 메일 관리**
- LangChain을 사용한 지능형 메일 분석
- 자연어로 메일 검색 및 분류
- 티켓 형태로 메일 관리

### 🎨 **직관적인 사용자 인터페이스**
- Streamlit 기반의 현대적인 웹 UI
- 메일 제목을 클릭 가능한 버튼으로 표시
- 우측 사이드바에 상세 메일 내용 표시
- 실시간 상태 모니터링

### 🆕 **향상된 티켓 처리 시스템 (NEW!)**
- **이중 분류 시스템**: AI가 '업무용'과 '업무용이 아님'으로 메일을 분류
- **사용자 정정 기능**: AI 분류 결과를 사용자가 직접 수정 가능
- **실시간 티켓 변환**: '정정' 버튼 클릭 한 번으로 즉시 티켓 생성
- **스마트 분류**: 메일 내용과 사용자 요청을 종합하여 정확한 분류 수행

## 🏗️ 아키텍처

### **추상화 계층**
```
EmailProvider (ABC)
├── GmailProvider
└── GraphApiProvider
```

### **데이터 흐름**
```
API Response → EmailMessage (통일된 모델) → AI 분류 → Tickets + Non-work Emails → UI
```

### **Factory 패턴**
- `create_provider()`: 제공자 인스턴스 생성
- `get_available_providers()`: 사용 가능한 제공자 목록
- `get_default_provider()`: 기본 제공자 자동 감지

### **향상된 티켓 처리 아키텍처**
```
메일 수신 → AI 분류기 → 분류 결과
    ↓
├── 업무용 메일 → 티켓 생성 → SQLite + VectorDB 저장
└── 업무용이 아닌 메일 → non_work_emails 목록 → 사용자 정정 대기
    ↓
사용자 정정 → create_ticket_from_single_email() → 즉시 티켓 생성
```

## 🚀 설치 및 설정

### **1. 저장소 클론**
```bash
git clone <repository-url>
cd ops_agent
```

### **2. 가상환경 생성 및 활성화**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### **3. 의존성 설치**
```bash
pip install -r requirements.txt
```

### **4. 환경변수 설정 (.env 파일)**
```bash
# Azure OpenAI 설정
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1

# Gmail API 설정 (선택사항)
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token

# Microsoft Graph API 설정 (선택사항)
GRAPH_CLIENT_ID=your_graph_client_id
GRAPH_CLIENT_SECRET=your_graph_client_secret
GRAPH_REFRESH_TOKEN=your_graph_refresh_token
GRAPH_TENANT_ID=your_tenant_id

# 기본 이메일 제공자 설정 (선택사항)
EMAIL_PROVIDER=gmail  # 또는 'graph'
```

## 🔧 사용법

### **1. 기본 실행**
```bash
streamlit run langchain_chatbot_app.py
```

### **2. 제공자 선택**
- 사이드바에서 "이메일 제공자 선택" 드롭다운 사용

### **3. 향상된 티켓 처리 시스템 사용법**

#### **자동 메일 분류**
사용자가 "오늘 처리해야 할 티켓 보여줘"라고 요청하면:
1. AI가 모든 메일을 분석하여 '업무용'과 '업무용이 아님'으로 분류
2. '업무용' 메일은 자동으로 티켓으로 생성
3. '업무용이 아님' 메일은 별도 섹션에 표시

#### **사용자 정정 기능**
1. **업무용이 아닌 메일 확인**: 하단 섹션에서 AI 분류 결과 확인
2. **정정 버튼 클릭**: 티켓으로 변환이 필요한 메일의 "정정" 버튼 클릭
3. **자동 티켓 생성**: 백엔드에서 즉시 티켓 생성 프로세스 실행
4. **실시간 업데이트**: 화면 새로고침으로 새 티켓이 상단 목록에 표시

#### **정정 버튼 동작 과정**
```
정정 버튼 클릭 → st.spinner("티켓 생성 중...") → 
create_ticket_from_single_email() 호출 → 
티켓 생성 및 DB 저장 → 
st.success("✅ 티켓이 성공적으로 생성되었습니다!") → 
st.rerun()으로 화면 새로고침
```

### **4. 고급 기능**
- **메일 필터링**: 읽음/안읽음, 발신자, 날짜 등으로 메일 필터링
- **티켓 상태 관리**: 생성된 티켓의 상태를 pending → approved → rejected로 변경
- **VectorDB 연동**: 메일 내용을 벡터화하여 유사도 검색 지원

## 📁 프로젝트 구조

```
ops_agent/
├── 📄 email_models.py          # 통일된 이메일 데이터 모델
├── 📄 email_provider.py        # 추상화 계층 및 Factory
├── 📄 gmail_provider.py        # Gmail API 구현
├── 📄 graph_provider.py        # Microsoft Graph API 구현
├── 📄 unified_email_service.py # 통합 이메일 서비스
├── 📄 langchain_chatbot_app.py # 메인 애플리케이션
├── 📄 enhanced_ticket_ui.py    # 티켓 UI 컴포넌트
├── 📄 requirements.txt         # 의존성 목록
└── 📄 README.md               # 프로젝트 문서
```

## 🔌 API 연동 가이드

### **Gmail API 설정**
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Gmail API 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. Refresh Token 획득

### **Microsoft Graph API 설정**
1. [Azure Portal](https://portal.azure.com/)에서 앱 등록
2. Microsoft Graph API 권한 추가
3. 클라이언트 시크릿 생성
4. 테넌트 ID 확인

## 🧪 테스트

### **개별 제공자 테스트**
```bash
# Gmail 제공자 테스트
python3 -c "from gmail_provider import GmailProvider; print('Gmail Provider OK')"

# Graph API 제공자 테스트
python3 -c "from graph_provider import GraphApiProvider; print('Graph Provider OK')"
```

### **통합 서비스 테스트**
```bash
# 통합 이메일 서비스 테스트
python3 -c "from unified_email_service import UnifiedEmailService; print('Unified Service OK')"
```

## 🔄 마이그레이션 가이드

### **기존 Gmail 전용 코드에서**
```python
# 기존 코드
from gmail_integration import fetch_gmail_tickets_sync

# 새로운 코드
from unified_email_service import fetch_emails_sync
# 또는
from unified_email_service import fetch_gmail_tickets_sync  # 호환성 유지
```

### **제공자 전환**
```python
# Gmail 사용
tickets = fetch_emails_sync('gmail')

# Microsoft Graph 사용
tickets = fetch_emails_sync('graph')

# 기본 제공자 사용
tickets = fetch_emails_sync()
```

## 🚧 제한사항

- **Gmail API**: 일일 할당량 제한 (1,000,000,000 quota units)
- **Microsoft Graph API**: 요청당 최대 999개 메시지
- **인증**: Refresh Token 만료 시 재인증 필요

## 🔮 향후 계획

- [ ] **추가 이메일 제공자**: Yahoo Mail, IMAP 등
- [ ] **배치 처리**: 대량 메일 처리 최적화
- [ ] **실시간 동기화**: 웹훅 기반 실시간 업데이트
- [ ] **고급 검색**: AI 기반 스마트 검색
- [ ] **메일 분류**: 자동 라벨링 및 카테고리화

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📞 지원

문제가 발생하거나 질문이 있으시면:
1. [Issues](../../issues) 페이지에서 버그 리포트
2. [Discussions](../../discussions) 페이지에서 질문
3. 프로젝트 문서 확인

---

**⭐ 이 프로젝트가 도움이 되었다면 Star를 눌러주세요!**