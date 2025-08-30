# MemoryBasedTicketProcessorTool 

## 개요

**장기 기억(Long-term Memory)을 활용한 HITL(Human-in-the-Loop) 티켓 생성 도구**

사용자의 피드백을 기억하고 다음 결정에 활용하는 스스로 학습하는 AI 티켓 생성 시스템입니다.

## 🎯 주요 특징

- **4단계 워크플로우**: 검색 → 추론 → 실행 → 기억 저장
- **장기 기억**: AI 결정과 사용자 피드백을 Vector DB에 저장하여 지속적 학습
- **지능적 결정**: 과거 기억을 바탕으로 티켓 생성 여부와 레이블을 추천
- **사용자 피드백 학습**: 사용자의 수정 사항을 기억하여 미래 결정에 반영

## 📋 4단계 워크플로우

### 1단계: 검색 (Retrieval)
- **1a. 유사 메일 검색**: Vector DB의 `mail_collection`에서 의미적으로 유사한 과거 이메일 검색
- **1b. 과거 티켓 조회**: 유사 메일들의 ID로 RDB에서 관련 티켓 조회
- **1c. 사용자 피드백 조회**: Vector DB의 `user_action` 컬렉션에서 관련 피드백 기억 수집

### 2단계: 추론 (Reasoning)
- **2a. 티켓 생성 여부 판단**: AI가 과거 기억을 바탕으로 티켓 생성 필요성 결정
- **2b. 최적 레이블 추천**: 생성 결정시 가장 적합한 레이블 목록 추천

### 3단계: 실행 (Action)
- AI 결정에 따라 실제 Jira 티켓 생성 또는 생성하지 않음

### 4단계: 통합된 기억 저장 (Unified Memorization)
- AI 결정을 표준화된 '기억' 문장으로 변환하여 Vector DB에 저장
- 향후 유사한 상황에서 참고할 수 있도록 지속적 학습

## 🔧 설치 및 설정

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일에 다음 설정을 추가하세요:

```env
# Azure OpenAI 설정 (필수)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-10-21

# Jira 설정 (선택사항)
JIRA_API_ENDPOINT=https://your-domain.atlassian.net/rest/api/2/
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-token
```

### 3. 데이터베이스 초기화
처음 실행시 SQLite 데이터베이스와 ChromaDB 컬렉션이 자동으로 생성됩니다.

## 🚀 사용 방법

### 기본 사용법

```python
from memory_based_ticket_processor import MemoryBasedTicketProcessorTool

# 도구 인스턴스 생성
tool = MemoryBasedTicketProcessorTool()

# 이메일 처리
result = tool._run(
    email_content="서버가 응답하지 않습니다. 긴급히 확인 부탁드립니다.",
    email_subject="[긴급] 웹 서버 장애",
    email_sender="user@company.com",
    message_id="message_123"
)

print(result)
```

### LangChain Agent와 함께 사용

```python
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from langchain_openai import AzureChatOpenAI
from memory_based_ticket_processor import create_memory_based_ticket_processor

# LLM 설정
llm = AzureChatOpenAI(
    azure_endpoint="your-endpoint",
    deployment_name="your-deployment",
    openai_api_key="your-key",
    openai_api_version="2024-10-21"
)

# 도구 목록
tools = [create_memory_based_ticket_processor()]

# Agent 초기화
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Agent 실행
response = agent.run(
    "이메일 내용을 분석하여 티켓 생성이 필요한지 판단하고 처리해주세요: "
    "제목: [긴급] 로그인 오류, 내용: 사용자들이 로그인할 수 없습니다."
)
```

### 사용자 피드백 기록

```python
from memory_based_ticket_processor import record_user_correction

# 사용자가 티켓 레이블을 수정했을 때
success = record_user_correction(
    ticket_id=123,
    old_label="auto-generated",
    new_label="urgent-bug",
    user_id="admin"
)

if success:
    print("사용자 피드백이 장기 기억에 저장되었습니다.")
```

## 📊 응답 형식

### 성공 응답
```json
{
  "success": true,
  "decision": {
    "ticket_creation_decision": {
      "decision": "approve-suggested",
      "reason": "서버 장애는 긴급한 문제로 즉시 티켓 생성이 필요함",
      "confidence": 0.9
    },
    "recommended_labels": ["urgent", "bug", "backend"]
  },
  "action": {
    "action_taken": "ticket_created",
    "ticket_id": 123,
    "labels": ["urgent", "bug", "backend"],
    "priority": "Highest",
    "ticket_type": "Bug"
  },
  "memory_context": {
    "similar_mails": [...],
    "past_tickets": [...],
    "user_feedback_memories": [...]
  },
  "workflow_completed": true
}
```

### 실패 응답
```json
{
  "success": false,
  "error": "오류 메시지",
  "workflow_completed": false
}
```

## 🧪 테스트

테스트 스크립트를 실행하여 기능을 확인할 수 있습니다:

```bash
python test_memory_based_processor.py
```

테스트는 다음 항목들을 검증합니다:
- 기본 기능 동작
- 티켓 생성 및 거부 시나리오
- 사용자 피드백 기록
- 장기 기억 검색

## 💾 데이터 구조

### RDB 테이블
- `tickets`: 생성된 티켓 정보
- `ticket_events`: 티켓 이벤트 로그
- `user_actions`: 사용자 액션 및 AI 결정 기록

### Vector DB 컬렉션
- `mail_collection`: 이메일 임베딩 저장
- `user_action`: AI 결정 및 사용자 피드백 기억 저장

## 🔄 학습 과정

1. **초기 실행**: 기본 규칙으로 티켓 생성 결정
2. **사용자 피드백**: 사용자가 AI 결정을 수정
3. **기억 저장**: 피드백이 Vector DB에 저장
4. **학습 적용**: 다음 유사한 상황에서 과거 피드백 참고
5. **지속적 개선**: 시간이 지날수록 더 정확한 결정

## 🎯 기억 문장 예시

### AI 행동 기록
```
AI Action: 제목 '[서버 장애]' 이메일에 대해 '긴급', '버그' 레이블로 티켓 T-124를 생성함.
```

### 사용자 피드백 기록
```
User Correction: 티켓 T-101의 레이블을 '문의'에서 '기능 요청'으로 수정함.
```

## ⚙️ 고급 설정

### 메모리 검색 결과 수 조정
```python
# 유사 메일 검색 결과 수 (기본값: 5)
similar_mails = self.vector_db.search_similar_mails(query, n_results=10)

# 유사 액션 검색 결과 수 (기본값: 10)  
similar_actions = self.user_action_vector_db.search_similar_actions(query, n_results=20)
```

### LLM 온도 조정
```python
self.llm = AzureChatOpenAI(
    # 더 보수적인 결정을 위해서는 낮은 값
    temperature=0.1,  # 기본값: 0.3
    # 기타 설정...
)
```

## 🚨 주의사항

1. **환경 변수**: Azure OpenAI 설정이 반드시 필요합니다.
2. **디스크 공간**: ChromaDB는 로컬 디스크에 저장되므로 충분한 공간이 필요합니다.
3. **API 비용**: LLM 호출로 인한 Azure OpenAI API 비용이 발생할 수 있습니다.
4. **데이터 보안**: 민감한 이메일 내용이 Vector DB에 저장되므로 보안에 주의하세요.

## 🤝 기여

버그 신고나 기능 요청은 이슈를 통해 알려주세요.

## 📄 라이센스

이 프로젝트는 MIT 라이센스하에 제공됩니다.
