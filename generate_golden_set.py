#!/usr/bin/env python3
"""
RAG 시스템 성능 평가를 위한 Golden Set 생성 스크립트
Jira 티켓 데이터를 기반으로 예상 질문을 생성하고 RAG 검색 결과를 기록합니다.
"""

import os
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Azure OpenAI 설정
load_dotenv()

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ==================== 설정 상수 ====================
JIRA_CSV_FILE_PATH = "sample_jira_tickets.csv"  # Jira CSV 파일 경로
OUTPUT_LOG_FILE = f"golden_set_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"  # 로그 파일명
QUESTIONS_PER_TICKET = 1  # 티켓당 생성할 질문 개수
MAX_TICKETS_TO_PROCESS = 10  # 처리할 최대 티켓 수 (테스트용)

# Azure OpenAI 설정
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# ==================== Azure OpenAI 클라이언트 초기화 ====================
def initialize_azure_openai():
    """Azure OpenAI 클라이언트 초기화"""
    if not OPENAI_AVAILABLE:
        raise ImportError("openai 라이브러리가 설치되지 않았습니다. pip install openai를 실행하세요.")
    
    if not all([AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME]):
        raise ValueError("Azure OpenAI 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    print("✅ Azure OpenAI 클라이언트 초기화 완료")
    return client

# ==================== LLM으로 예상 질문 생성 ====================
def generate_question_for_ticket(ticket: Dict[str, Any], llm_client) -> str:
    """
    Jira 티켓을 기반으로 사용자가 검색할 만한 자연스러운 질문을 생성합니다.
    
    Args:
        ticket: Jira 티켓 딕셔너리 (Summary, Description 등 포함)
        llm_client: Azure OpenAI 클라이언트
    
    Returns:
        str: 생성된 질문
    """
    try:
        # 티켓 정보 추출
        ticket_id = ticket.get('Key', 'Unknown')
        summary = ticket.get('Summary', '')
        description = ticket.get('Description', '')
        issue_type = ticket.get('Issue Type', '')
        priority = ticket.get('Priority', '')
        
        # 프롬프트 구성
        prompt = f"""당신은 IT 지원 시스템 사용자입니다. 아래 Jira 티켓 내용을 보고, 이 티켓을 찾기 위해 검색창에 입력할 만한 현실적인 질문을 한 문장으로 만들어주세요.

티켓 정보:
- ID: {ticket_id}
- 제목: {summary}
- 설명: {description}
- 유형: {issue_type}
- 우선순위: {priority}

요구사항:
1. 사용자가 실제로 검색창에 입력할 만한 자연스러운 질문이어야 합니다.
2. 한 문장으로 간결하게 작성하세요.
3. 티켓의 핵심 내용을 반영하되, 너무 구체적이지 않게 하세요.
4. 질문만 답변하고 다른 설명은 하지 마세요.

질문:"""

        # Azure OpenAI API 호출
        response = llm_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 IT 지원 시스템 사용자입니다. Jira 티켓을 기반으로 검색 질문을 생성하는 전문가입니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        question = response.choices[0].message.content.strip()
        
        # 질문이 너무 길거나 부적절한 경우 기본 질문 생성
        if len(question) > 200 or not question.endswith('?'):
            question = f"{summary} 관련 문제가 있는데 도움이 필요합니다."
        
        return question
        
    except Exception as e:
        print(f"❌ 질문 생성 실패 (티켓 {ticket.get('Key', 'Unknown')}): {str(e)}")
        # 기본 질문 생성
        return f"{ticket.get('Summary', '문제')} 관련 문의입니다."

# ==================== RAG 검색 함수 (Placeholder) ====================
def search_rag(query: str) -> List[Dict[str, Any]]:
    """
    RAG 시스템에서 검색을 수행하는 함수 (Placeholder)
    실제 구현에서는 사용자의 RAG 검색 로직으로 교체해야 합니다.
    
    Args:
        query: 검색 쿼리
    
    Returns:
        List[Dict]: 검색 결과 리스트 (id, content, score 포함)
    """
    # TODO: 실제 RAG 검색 로직으로 교체
    # 예시 구현
    mock_results = [
        {
            "id": "MOCK-001",
            "content": f"'{query}'에 대한 검색 결과 1입니다.",
            "score": 0.95
        },
        {
            "id": "MOCK-002", 
            "content": f"'{query}'에 대한 검색 결과 2입니다.",
            "score": 0.82
        },
        {
            "id": "MOCK-003",
            "content": f"'{query}'에 대한 검색 결과 3입니다.",
            "score": 0.75
        }
    ]
    
    print(f"🔍 RAG 검색 실행: '{query}' -> {len(mock_results)}개 결과")
    return mock_results

# ==================== 로그 파일에 결과 기록 ====================
def log_test_case(log_file, test_case_num: int, ticket: Dict[str, Any], question: str, rag_results: List[Dict[str, Any]]):
    """
    테스트 케이스 결과를 로그 파일에 기록합니다.
    
    Args:
        log_file: 로그 파일 객체
        test_case_num: 테스트 케이스 번호
        ticket: 원본 티켓 정보
        question: 생성된 질문
        rag_results: RAG 검색 결과
    """
    ticket_id = ticket.get('Key', 'Unknown')
    ticket_summary = ticket.get('Summary', 'No Summary')
    ticket_description = ticket.get('Description', 'No Description')
    
    log_file.write(f"\n--- [Test Case #{test_case_num}] ---\n")
    log_file.write(f"🎯 정답 티켓: {ticket_id} ({ticket_summary})\n")
    log_file.write(f"📝 티켓 설명: {ticket_description}\n")
    log_file.write(f"🧠 생성된 질문: {question}\n")
    log_file.write(f"🔍 RAG 검색 결과 (Top {len(rag_results)}) - 질문과의 유사도 기준 (0.0=완전다름, 1.0=완전동일):\n")
    
    for i, result in enumerate(rag_results, 1):
        result_id = result.get('id', 'Unknown')
        result_content = result.get('content', 'No Content')
        result_score = result.get('score', 0.0)
        raw_score = result.get('raw_score', result_score)
        
        # 원본 점수와 정규화된 유사도 모두 표시
        if raw_score != result_score:
            log_file.write(f"\n   {i}. ID: {result_id} (질문과의 유사도: {result_score:.3f}, 원본점수: {raw_score:.3f})\n")
        else:
            log_file.write(f"\n   {i}. ID: {result_id} (질문과의 유사도: {result_score:.3f})\n")
        log_file.write(f"      내용:\n")
        
        # 내용을 여러 줄로 나누어 표시
        content_lines = result_content.split('\n')
        for line in content_lines:
            log_file.write(f"      {line}\n")
        
        log_file.write(f"      {'-' * 60}\n")
    
    log_file.write("\n" + "="*80 + "\n")

# ==================== 메인 실행 로직 ====================
def main():
    """메인 실행 함수"""
    print("🚀 RAG Golden Set 생성 스크립트 시작")
    
    try:
        # Azure OpenAI 클라이언트 초기화
        llm_client = initialize_azure_openai()
        
        # CSV 파일 존재 확인
        if not os.path.exists(JIRA_CSV_FILE_PATH):
            raise FileNotFoundError(f"Jira CSV 파일을 찾을 수 없습니다: {JIRA_CSV_FILE_PATH}")
        
        # CSV 파일 읽기
        print(f"📖 CSV 파일 읽기: {JIRA_CSV_FILE_PATH}")
        df = pd.read_csv(JIRA_CSV_FILE_PATH)
        print(f"✅ {len(df)}개의 티켓을 발견했습니다.")
        
        # 처리할 티켓 수 제한
        if len(df) > MAX_TICKETS_TO_PROCESS:
            df = df.head(MAX_TICKETS_TO_PROCESS)
            print(f"⚠️ 테스트를 위해 {MAX_TICKETS_TO_PROCESS}개 티켓만 처리합니다.")
        
        # 로그 파일 열기
        with open(OUTPUT_LOG_FILE, 'w', encoding='utf-8') as log_file:
            # 헤더 정보 기록
            log_file.write("="*80 + "\n")
            log_file.write("RAG 시스템 Golden Set 생성 결과\n")
            log_file.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"처리된 티켓 수: {len(df)}\n")
            log_file.write(f"티켓당 질문 수: {QUESTIONS_PER_TICKET}\n")
            log_file.write("="*80 + "\n")
            
            # 각 티켓 처리
            for index, row in df.iterrows():
                test_case_num = index + 1
                ticket = row.to_dict()
                
                print(f"\n📝 테스트 케이스 #{test_case_num} 처리 중...")
                print(f"   티켓 ID: {ticket.get('Key', 'Unknown')}")
                
                try:
                    # 질문 생성
                    question = generate_question_for_ticket(ticket, llm_client)
                    print(f"   생성된 질문: {question}")
                    
                    # RAG 검색 실행
                    rag_results = search_rag(question)
                    
                    # 결과 로그에 기록
                    log_test_case(log_file, test_case_num, ticket, question, rag_results)
                    
                    print(f"   ✅ 테스트 케이스 #{test_case_num} 완료")
                    
                except Exception as e:
                    print(f"   ❌ 테스트 케이스 #{test_case_num} 실패: {str(e)}")
                    log_file.write(f"\n--- [Test Case #{test_case_num}] ---\n")
                    log_file.write(f"❌ 오류 발생: {str(e)}\n")
                    log_file.write("="*80 + "\n")
                    continue
        
        print(f"\n🎉 Golden Set 생성 완료!")
        print(f"📄 결과 파일: {OUTPUT_LOG_FILE}")
        print(f"📊 처리된 테스트 케이스: {len(df)}개")
        
    except Exception as e:
        print(f"❌ 스크립트 실행 실패: {str(e)}")
        return 1
    
    return 0

# ==================== 스크립트 실행 ====================
if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
