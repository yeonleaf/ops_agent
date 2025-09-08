#!/usr/bin/env python3
"""
RAG 시스템 성능 평가를 위한 Golden Set 생성 스크립트 (실제 RAG 검색 연결)
기존 generate_golden_set.py를 기반으로 실제 RAG 검색 함수를 연결한 버전입니다.
"""

import os
import sys
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 기존 모듈들 import
from generate_golden_set import (
    initialize_azure_openai, 
    generate_question_for_ticket, 
    log_test_case,
    JIRA_CSV_FILE_PATH,
    OUTPUT_LOG_FILE,
    QUESTIONS_PER_TICKET,
    MAX_TICKETS_TO_PROCESS
)

# RAG 관련 모듈들 import
from vector_db_models import VectorDBManager
from ticket_ai_recommender import TicketAIRecommender

# ==================== 실제 RAG 검색 함수 ====================
def search_rag(query: str) -> List[Dict[str, Any]]:
    """
    실제 RAG 시스템에서 검색을 수행하는 함수
    
    Args:
        query: 검색 쿼리
    
    Returns:
        List[Dict]: 검색 결과 리스트 (id, content, score 포함)
    """
    try:
        # VectorDBManager 초기화
        vector_db = VectorDBManager()
        
        # 통합 검색 실행 (메일 + 파일 청크)
        recommender = TicketAIRecommender()
        similar_content = recommender.get_integrated_similar_content(
            query, 
            email_limit=2, 
            chunk_limit=1
        )
        
        # 결과를 표준 형식으로 변환
        results = []
        for i, item in enumerate(similar_content):
            # Retrieve then Re-rank 결과인 경우 rerank_score 사용, 그 외에는 similarity_score 사용
            if item.get("source") == "retrieve_rerank_whoosh":
                metadata = item.get('metadata', {})
                score = metadata.get('rerank_score', item.get('similarity_score', 0.0))
            else:
                score = item.get('similarity_score', 0.0)
            
            result = {
                "id": item.get("message_id", item.get("chunk_id", f"ITEM-{i}")),
                "content": "",
                "score": score
            }
            
            # Retrieve then Re-rank 검색 결과인 경우 (Vector + Whoosh + CohereRerank)
            if item.get("source") == "retrieve_rerank_whoosh":
                content = item.get('content', 'No Content')
                metadata = item.get('metadata', {})
                source_type = metadata.get('source_type', 'unknown')
                extracted_keywords = item.get('extracted_keywords', [])
                
                # 내용이 길면 적절히 잘라서 표시
                if len(content) > 200:
                    content_preview = content[:200] + "..."
                else:
                    content_preview = content
                
                # 추출된 키워드 정보 추가
                keyword_info = f" (키워드: {', '.join(extracted_keywords)})" if extracted_keywords else ""
                
                # Retrieve then Re-rank 검색 결과 표시
                result["content"] = f"[Retrieve then Re-rank Whoosh] {source_type}{keyword_info}\n내용: {content_preview}"
            
            # QueryExpansion 결과인 경우 (file_chunk, mail 등)
            elif item.get("source") in ["file_chunk", "mail", "structured_chunk"]:
                content = item.get('content', 'No Content')
                metadata = item.get('metadata', {})
                source = item.get('source', 'unknown')
                
                # 내용이 길면 적절히 잘라서 표시
                if len(content) > 200:
                    content_preview = content[:200] + "..."
                else:
                    content_preview = content
                
                # 소스 타입에 따라 다른 표시 형식
                if source == "file_chunk":
                    file_name = metadata.get('file_name', 'Unknown File')
                    result["content"] = f"[파일 청크] {file_name}\n내용: {content_preview}"
                elif source == "mail":
                    subject = metadata.get('subject', 'No Subject')
                    sender = metadata.get('sender', 'Unknown Sender')
                    result["content"] = f"[메일] {subject}\n발신자: {sender}\n내용: {content_preview}"
                elif source == "structured_chunk":
                    ticket_id = metadata.get('ticket_id', 'Unknown')
                    chunk_type = metadata.get('chunk_type', 'unknown')
                    field_name = metadata.get('field_name', 'unknown')
                    priority = metadata.get('priority', 3)
                    commenter = metadata.get('commenter', '')
                    
                    # 청크 타입에 따라 다른 표시 형식
                    if chunk_type == 'header':
                        result["content"] = f"[헤더 청크] {ticket_id} (우선순위: {priority})\n내용: {content_preview}"
                    elif chunk_type == 'comment':
                        commenter_info = f" (작성자: {commenter})" if commenter else ""
                        result["content"] = f"[댓글 청크] {ticket_id}{commenter_info} (우선순위: {priority})\n내용: {content_preview}"
                    else:
                        result["content"] = f"[구조적 청크] {ticket_id} - {field_name} (우선순위: {priority})\n타입: {chunk_type}\n내용: {content_preview}"
                else:
                    # 기타 소스 타입
                    result["content"] = f"[{source}] {content_preview}"
            
            # 구조적 청킹 결과인 경우 (기존 코드 유지)
            elif item.get("source") == "structured_chunk":
                content = item.get('content', 'No Content')
                metadata = item.get('metadata', {})
                ticket_id = metadata.get('ticket_id', 'Unknown')
                chunk_type = metadata.get('chunk_type', 'unknown')
                field_name = metadata.get('field_name', 'unknown')
                priority = metadata.get('priority', 3)
                commenter = metadata.get('commenter', '')
                
                # 내용이 길면 적절히 잘라서 표시
                if len(content) > 200:
                    content_preview = content[:200] + "..."
                else:
                    content_preview = content
                
                # 청크 타입에 따라 다른 표시 형식
                if chunk_type == 'header':
                    result["content"] = f"[헤더 청크] {ticket_id} (우선순위: {priority})\n내용: {content_preview}"
                elif chunk_type == 'comment':
                    commenter_info = f" (작성자: {commenter})" if commenter else ""
                    result["content"] = f"[댓글 청크] {ticket_id}{commenter_info} (우선순위: {priority})\n내용: {content_preview}"
                else:
                    result["content"] = f"[구조적 청크] {ticket_id} - {field_name} (우선순위: {priority})\n타입: {chunk_type}\n내용: {content_preview}"
            
            # Cohere Re-ranking 결과인 경우
            elif item.get("source") == "cohere_rerank":
                content = item.get('content', 'No Content')
                metadata = item.get('metadata', {})
                source_type = metadata.get('source', 'unknown')
                
                if source_type == "mail":
                    subject = metadata.get('subject', 'No Subject')
                    sender = metadata.get('sender', 'Unknown Sender')
                    result["content"] = f"[메일] {subject}\n발신자: {sender}\n내용: {content[:200]}..."
                elif source_type == "file_chunk":
                    file_name = metadata.get('file_name', 'Unknown')
                    file_type = metadata.get('file_type', 'Unknown')
                    result["content"] = f"[문서] {file_name} ({file_type})\n내용: {content[:200]}..."
                else:
                    result["content"] = content[:200] + "..." if len(content) > 200 else content
            
            # 기존 메일인 경우 - 더 자세한 정보 포함
            elif item.get("source_type") == "email":
                subject = item.get('subject', 'No Subject')
                sender = item.get('sender', 'Unknown Sender')
                summary = item.get('content_summary', 'No Summary')
                refined_content = item.get('refined_content', '')
                
                # 내용이 길면 적절히 잘라서 표시
                if len(refined_content) > 200:
                    content_preview = refined_content[:200] + "..."
                else:
                    content_preview = refined_content
                
                result["content"] = f"[메일] {subject}\n발신자: {sender}\n요약: {summary}\n내용: {content_preview}"
            
            # 기존 파일 청크인 경우 - 더 자세한 정보 포함
            elif item.get("source_type") == "file_chunk":
                file_name = item.get('file_name', 'Unknown')
                file_type = item.get('file_type', 'Unknown')
                page_number = item.get('page_number', 1)
                element_type = item.get('element_type', 'text')
                content = item.get("content", "")
                
                # 내용이 길면 적절히 잘라서 표시
                if len(content) > 300:
                    content_preview = content[:300] + "..."
                else:
                    content_preview = content
                
                result["content"] = f"[문서] {file_name} ({file_type})\n페이지: {page_number}, 요소: {element_type}\n내용: {content_preview}"
            
            results.append(result)
        
        print(f"🔍 RAG 검색 실행: '{query}' -> {len(results)}개 결과")
        return results
        
    except Exception as e:
        print(f"❌ RAG 검색 실패: {str(e)}")
        # 오류 발생 시 빈 결과 반환
        return []

# ==================== 메인 실행 로직 ====================
def main():
    """메인 실행 함수"""
    print("🚀 RAG Golden Set 생성 스크립트 시작 (실제 RAG 검색 연결)")
    
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
        
        # 로그 파일명에 실제 RAG 표시 추가
        output_file = f"golden_set_results_with_rag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # 로그 파일 열기
        with open(output_file, 'w', encoding='utf-8') as log_file:
            # 헤더 정보 기록
            log_file.write("="*80 + "\n")
            log_file.write("RAG 시스템 Golden Set 생성 결과 (실제 RAG 검색 연결)\n")
            log_file.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"처리된 티켓 수: {len(df)}\n")
            log_file.write(f"티켓당 질문 수: {QUESTIONS_PER_TICKET}\n")
            log_file.write("\n📊 성능 평가 가이드:\n")
            log_file.write("- 정확도: 정답 티켓이 상위 3개 결과에 포함되는지 확인\n")
            log_file.write("- 순위: 정답 티켓이 몇 번째 순위에 나타나는지 기록\n")
            log_file.write("- 관련성: 검색된 결과가 질문과 얼마나 관련성이 있는지 평가\n")
            log_file.write("- 유사도 점수: 0.8 이상이면 높은 관련성, 0.5-0.8 중간, 0.5 미만 낮음\n")
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
                    
                    # 실제 RAG 검색 실행
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
        print(f"📄 결과 파일: {output_file}")
        print(f"📊 처리된 테스트 케이스: {len(df)}개")
        print(f"\n📋 성능 평가 방법:")
        print(f"1. 로그 파일을 열어서 각 테스트 케이스를 검토하세요")
        print(f"2. 정답 티켓이 상위 3개 결과에 포함되는지 확인하세요")
        print(f"3. 유사도 점수가 0.8 이상인 결과의 관련성을 평가하세요")
        print(f"4. 전체적인 검색 품질을 종합적으로 판단하세요")
        
    except Exception as e:
        print(f"❌ 스크립트 실행 실패: {str(e)}")
        return 1
    
    return 0

# ==================== 스크립트 실행 ====================
if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
