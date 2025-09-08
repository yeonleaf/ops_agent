# RAG 시스템 Golden Set 생성 도구

RAG 시스템의 성능을 평가하기 위한 Golden Set을 반자동으로 생성하는 Python 스크립트입니다.

## 📁 파일 구성

- `generate_golden_set.py`: 기본 스크립트 (Mock RAG 검색)
- `generate_golden_set_with_rag.py`: 실제 RAG 검색 연결 버전
- `sample_jira_tickets.csv`: 샘플 Jira 티켓 데이터
- `GOLDEN_SET_README.md`: 사용법 가이드

## 🚀 사용법

### 1. 환경 설정

```bash
# 필요한 라이브러리 설치
pip install pandas openai python-dotenv

# .env 파일에 Azure OpenAI 설정 추가
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
```

### 2. Jira CSV 파일 준비

CSV 파일은 다음 컬럼을 포함해야 합니다:
- `Key`: 티켓 ID (예: T-001)
- `Summary`: 티켓 제목
- `Description`: 티켓 설명
- `Issue Type`: 이슈 유형
- `Priority`: 우선순위
- `Status`: 상태
- `Assignee`: 담당자
- `Reporter`: 보고자
- `Created`: 생성일
- `Updated`: 수정일

### 3. 스크립트 실행

#### 기본 버전 (Mock RAG 검색)
```bash
python generate_golden_set.py
```

#### 실제 RAG 검색 연결 버전
```bash
python generate_golden_set_with_rag.py
```

### 4. 설정 변경

스크립트 상단의 상수들을 수정하여 설정을 변경할 수 있습니다:

```python
JIRA_CSV_FILE_PATH = "your_jira_tickets.csv"  # Jira CSV 파일 경로
MAX_TICKETS_TO_PROCESS = 20  # 처리할 최대 티켓 수
QUESTIONS_PER_TICKET = 1  # 티켓당 생성할 질문 개수
```

## 📊 출력 형식

생성된 로그 파일은 다음과 같은 형식으로 결과를 기록합니다:

```
--- [Test Case #1] ---
🎯 정답 티켓: T-001 (서버 접속 불가 문제)
🧠 생성된 질문: 우리 메인 서버가 다운된 것 같은데, 상태 좀 확인해주세요.
🔍 RAG 검색 결과 (Top 3):
   1. ID: T-001, 내용: 서버 장애 보고..., 점수: 0.95
   2. ID: DOC-A, 내용: 서버 점검 매뉴얼..., 점수: 0.82
   3. ID: T-456, 내용: 신규 서버 추가 요청..., 점수: 0.75
```

## 🔧 커스터마이징

### RAG 검색 함수 교체

`generate_golden_set.py`의 `search_rag()` 함수를 실제 RAG 검색 로직으로 교체하세요:

```python
def search_rag(query: str) -> List[Dict[str, Any]]:
    # 여기에 실제 RAG 검색 로직 구현
    # 반환 형식: [{"id": "ID", "content": "내용", "score": 0.95}, ...]
    pass
```

### 질문 생성 프롬프트 수정

`generate_question_for_ticket()` 함수의 프롬프트를 수정하여 질문 생성 방식을 조정할 수 있습니다.

## 📈 성능 평가 방법

1. **정확도 측정**: 각 테스트 케이스에서 정답 티켓이 상위 3개 결과에 포함되는지 확인
2. **순위 평가**: 정답 티켓이 몇 번째 순위에 나타나는지 기록
3. **관련성 평가**: 검색된 결과가 질문과 얼마나 관련성이 있는지 수동 평가

## ⚠️ 주의사항

- Azure OpenAI API 사용량에 따라 비용이 발생할 수 있습니다
- 대량의 티켓을 처리할 때는 API 제한을 고려하세요
- 생성된 질문의 품질을 수동으로 검토하는 것을 권장합니다

## 🐛 문제 해결

### CSV 파일 읽기 오류
- 파일 경로가 올바른지 확인
- CSV 파일의 인코딩이 UTF-8인지 확인
- 필수 컬럼이 모두 존재하는지 확인

### Azure OpenAI 연결 오류
- .env 파일의 환경변수가 올바르게 설정되었는지 확인
- API 키와 엔드포인트가 유효한지 확인
- 네트워크 연결 상태 확인

### RAG 검색 오류
- VectorDB가 올바르게 초기화되었는지 확인
- 검색 함수의 반환 형식이 올바른지 확인
