# MultiQueryRetriever 구현 가이드

## 개요

MultiQueryRetriever는 사용자의 단일 질문을 LLM을 이용해 여러 개의 다른 관점을 가진 질문으로 확장하여, 더 관련성 높은 문서를 찾아내는 RAG 검색 개선 모듈입니다.

## 구현된 기능

### 1. 핵심 컴포넌트

**MultiQueryRetrieverWrapper**
- LangChain의 MultiQueryRetriever를 래핑한 클래스
- 기본 검색기와 LLM을 결합하여 다중 질문 생성 및 검색 수행
- 폴백 메커니즘으로 기본 검색기 사용 가능

**ChromaDBRetriever**
- ChromaDB를 위한 BaseRetriever 구현
- 메일, 파일 청크, 구조적 청크 컬렉션 지원
- LangChain 호환 인터페이스 제공

**AzureChatOpenAIManager**
- AzureChatOpenAI LLM 관리
- 환경 변수 기반 자동 설정
- temperature=0으로 일관된 질문 생성

**MultiQuerySearchManager**
- 통합 검색 관리자
- 각 컬렉션별 MultiQueryRetriever 설정
- 필터링 및 결과 변환 기능

### 2. 검색 파이프라인

```
사용자 질문 → MultiQueryRetriever → LLM 질문 확장 → 다중 검색 → 결과 통합
```

**예시:**
- 입력: "서버 문제 해결 방법"
- LLM이 생성하는 질문들:
  - "서버 접속 불가 시 대처 방안은 무엇인가?"
  - "서버 장애 관련 최근 Jira 티켓"
  - "서버 성능 저하 원인 분석 문서"
- 각 질문으로 벡터 검색 수행
- 모든 결과를 종합하여 중복 제거 후 반환

## 파일 구조

```
multi_query_retriever.py          # MultiQueryRetriever 핵심 구현
ticket_ai_recommender.py          # 기존 검색 로직에 MultiQuery 통합
MULTI_QUERY_RETRIEVER_GUIDE.md   # 이 가이드 문서
```

## 사용 방법

### 1. 기본 사용

```python
from multi_query_retriever import create_multi_query_search_manager
from vector_db_models import VectorDBManager

# Vector DB 매니저 초기화
vector_db = VectorDBManager()

# MultiQuery 검색 관리자 생성
search_manager = create_multi_query_search_manager(vector_db)

# 검색 수행
results = search_manager.search_mails("서버 접속 문제", k=5)
```

### 2. TicketAIRecommender 통합

```python
from ticket_ai_recommender import TicketAIRecommender

# 인스턴스 생성 (자동으로 MultiQuery 초기화)
recommender = TicketAIRecommender()

# MultiQuery가 적용된 검색
mail_results = recommender.get_similar_emails("서버 문제", limit=5)
chunk_results = recommender.get_similar_file_chunks("서버 문제", limit=3)
```

### 3. 개별 컬렉션 검색

```python
# 메일 검색
mail_results = search_manager.search_mails(query, k=5)

# 파일 청크 검색
chunk_results = search_manager.search_file_chunks(query, k=5)

# 구조적 청크 검색 (필터 포함)
structured_results = search_manager.search_structured_chunks(
    query, k=5, 
    chunk_types=['header'], 
    priority_filter=2
)
```

## 환경 설정

### 1. 필요한 환경 변수

```bash
# Azure OpenAI 설정
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

### 2. 필요한 패키지

```bash
pip install langchain
pip install langchain-openai
pip install langchain-community
pip install python-dotenv
```

## 폴백 메커니즘

MultiQueryRetriever가 사용 불가능한 경우 자동으로 기본 검색으로 폴백됩니다:

1. **LangChain 미설치**: 기본 VectorDBManager 검색 사용
2. **Azure OpenAI 미설정**: 기본 VectorDBManager 검색 사용
3. **LLM 초기화 실패**: 기본 VectorDBManager 검색 사용
4. **MultiQuery 검색 실패**: 기본 검색기로 폴백

## 로깅

MultiQueryRetriever의 동작을 확인하기 위한 로깅이 구현되어 있습니다:

```python
import logging

# LangChain 로깅 활성화
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

# 생성된 질문들 확인
# INFO:langchain.retrievers.multi_query:Generated queries: ['질문1', '질문2', '질문3']
```

## 성능 개선 효과

### 1. 검색 정확도 향상
- 단일 질문 → 다중 관점 질문으로 검색 범위 확장
- 다양한 표현 방식으로 같은 내용 검색 가능
- 놓치기 쉬운 관련 문서 발견

### 2. 검색 일관성 향상
- LLM이 생성하는 질문으로 일관된 검색 패턴
- 사용자 질문의 의도 파악 개선
- 컨텍스트 이해도 향상

### 3. 결과 다양성 증가
- 단일 검색으로는 찾기 어려운 관련 문서 발견
- 다양한 관점에서의 관련 정보 수집
- 종합적인 검색 결과 제공

## 통합된 검색 파이프라인

```
사용자 질문
    ↓
텍스트 전처리 (노이즈 제거)
    ↓
MultiQueryRetriever (질문 확장)
    ↓
다중 벡터 검색
    ↓
Cohere Re-ranking (정확도 향상)
    ↓
최종 검색 결과
```

## 테스트

### 1. 기본 테스트

```python
python3 multi_query_retriever.py
```

### 2. 통합 테스트

```python
from ticket_ai_recommender import TicketAIRecommender

recommender = TicketAIRecommender()
results = recommender.get_similar_emails("테스트 쿼리", limit=3)
print(f"검색 결과: {len(results)}개")
```

## 주의사항

1. **LLM 비용**: MultiQueryRetriever는 LLM을 사용하므로 API 호출 비용이 발생합니다.
2. **응답 시간**: 질문 확장 과정으로 인해 기본 검색보다 시간이 더 걸릴 수 있습니다.
3. **환경 의존성**: Azure OpenAI 설정이 필요하며, 설정이 없으면 폴백 모드로 동작합니다.

## 향후 개선 방향

1. **캐싱**: 생성된 질문들을 캐싱하여 반복 검색 시 성능 향상
2. **질문 품질 개선**: 더 효과적인 질문 생성을 위한 프롬프트 최적화
3. **결과 랭킹**: 다중 검색 결과의 통합 랭킹 알고리즘 개선
4. **모니터링**: 검색 성능 및 질문 생성 품질 모니터링 시스템

## 결론

MultiQueryRetriever를 통해 RAG 시스템의 검색 성능이 크게 향상되었습니다. 사용자의 단일 질문을 다양한 관점으로 확장하여 더 관련성 높은 문서를 찾아내는 혁신적인 접근 방식을 구현했습니다.
