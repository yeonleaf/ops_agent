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
from multi_vector_cross_encoder_rag import MultiVectorCrossEncoderRAG

# ==================== 포괄적 테스트 케이스 정의 ====================

# 1. 정답이 없는 질문 테스트 (Zero-shot & Negative Test)
NEGATIVE_TEST_QUESTIONS = [
    "화성 탐사선 관련 티켓이 있나요?",
    "인공지능 로봇 개발 프로젝트는 어떻게 진행되고 있나요?",
    "블록체인 기술을 활용한 결제 시스템은 언제 출시되나요?",
    "우주 정거장 건설 계획에 대한 최신 상황을 알려주세요",
    "양자컴퓨팅 연구 프로젝트의 진행 상황은 어떤가요?",
    "가상현실 헤드셋 관련 기술 이슈가 있나요?",
    "자율주행 자동차 소프트웨어 개발 현황은?",
    "해양 심층 탐사 로봇 프로젝트는 언제 완료되나요?",
    "인공위성 통신 시스템 오류가 발생했나요?",
    "핵융합 발전소 건설 관련 기술 문제가 있나요?"
]

# 2. 다양성 및 난이도 테스트 질문
DIVERSITY_TEST_QUESTIONS = [
    # 요약형 질문
    "서버 관련 모든 이슈를 요약해서 알려주세요",
    "데이터베이스 문제들의 공통점과 해결 방안을 정리해주세요",
    "배치 작업 실패 사례들의 패턴을 분석해주세요",
    
    # 비교/대조형 질문
    "서버 접속 문제와 DB 연결 문제의 차이점은 무엇인가요?",
    "STG 환경과 PROD 환경에서 발생한 이슈들을 비교해주세요",
    "배치 작업과 실시간 작업의 성능 차이는 어떻게 되나요?",
    
    # 시간순 질문
    "가장 최근에 처리된 보안 관련 티켓은 무엇인가요?",
    "이번 주에 발생한 모든 이슈를 시간순으로 정리해주세요",
    "오래된 미해결 티켓 중 우선순위가 높은 것은?",
    
    # 복합 추론 질문
    "성능 저하의 원인이 될 수 있는 모든 요소들을 찾아주세요",
    "사용자 경험에 영향을 줄 수 있는 시스템 이슈들을 분석해주세요",
    "비즈니스 연속성에 위험을 초래할 수 있는 문제들을 식별해주세요"
]

# 3. 스트레스 테스트 질문
STRESS_TEST_QUESTIONS = [
    # 중의적 표현
    "배포가 '안 된' 이슈 좀 찾아줘",
    "서버가 '안 되는' 문제가 있나요?",
    "DB가 '안 돌아가는' 상황을 확인해주세요",
    
    # 오타 포함
    "서버 '졉속'이 안돼",
    "데이터베이스 '연결' 오류가 발생했어요",
    "배치 '작업'이 실패했나요?",
    "로그인 '에러'가 계속 발생해요",
    
    # 매우 짧은 질문
    "서버",
    "DB",
    "배치",
    "오류",
    "문제",
    
    # 매우 긴 질문 (장황한 상황 설명)
    "안녕하세요. 저는 개발팀에서 일하고 있는데, 어제부터 계속 서버에 접속이 안 되고 있어요. 처음에는 간헐적으로 발생했는데, 오늘 아침부터는 아예 접속이 안 되네요. 다른 팀원들도 같은 문제를 겪고 있고, 고객사에서도 문의가 들어오고 있어서 급한 상황입니다. 혹시 관련된 이슈나 해결 방법이 있는지 확인해주실 수 있나요?",
    
    "우리 회사에서 사용하는 데이터베이스 시스템에 문제가 생긴 것 같아요. 어제 오후부터 쿼리 실행 시간이 평소보다 10배 이상 느려졌고, 간헐적으로 타임아웃이 발생하고 있어요. 특히 배치 작업이 실행되는 시간대에 더 심하게 나타나는 것 같습니다. 이전에 비슷한 문제가 있었는지, 그리고 어떤 해결책이 있었는지 알고 싶어요.",
    
    # 복잡한 조건부 질문
    "서버 접속 문제가 있는데, 단순한 네트워크 문제가 아니라 애플리케이션 레벨에서 발생하는 문제인 것 같아요. 로그를 확인해보니 특정 시간대에만 발생하고 있고, 특히 사용자가 많을 때 더 자주 발생하는 것 같습니다. 이런 패턴의 이슈가 이전에 있었는지 확인해주세요.",
    
    # 모호한 질문
    "뭔가 이상해요",
    "문제가 있어요",
    "도움이 필요해요",
    "확인해주세요"
]

# ==================== 실제 RAG 검색 함수 ====================
def search_rag(query: str) -> List[Dict[str, Any]]:
    """
    Multi-Vector + Cross-Encoder RAG 시스템에서 검색을 수행하는 함수
    
    Args:
        query: 검색 쿼리
    
    Returns:
        List[Dict]: 검색 결과 리스트 (id, content, score 포함)
    """
    try:
        # Multi-Vector Cross-Encoder RAG 시스템 초기화
        rag = MultiVectorCrossEncoderRAG()
        
        # 검색 실행
        similar_content = rag.search(
            query=query,
            n_candidates=50,  # 1단계 후보 수
            top_k=10         # 최종 결과 수
        )
        
        # 결과를 표준 형식으로 변환
        results = []
        for i, item in enumerate(similar_content):
            # Cross-Encoder 점수 사용
            raw_score = item.get('similarity_score', 0.0)
            
            # Cross-Encoder 점수는 이미 0~1 범위로 정규화됨
            similarity_score = max(0.0, min(1.0, raw_score))
            
            result = {
                "id": item.get("id", f"ITEM-{i}"),
                "content": item.get("content", ""),
                "score": similarity_score,
                "raw_score": raw_score,  # 원본 점수도 보관
                "similarity_to_query": similarity_score  # 질문과의 유사도 명시
            }
            
            # Multi-Vector Cross-Encoder 검색 결과인 경우
            if item.get("source") == "multi_vector_cross_encoder":
                content = item.get('content', 'No Content')
                metadata = item.get('metadata', {})
                ticket_id = item.get('id', 'Unknown')
                
                # 내용이 길면 적절히 잘라서 표시
                if len(content) > 200:
                    content_preview = content[:200] + "..."
                else:
                    content_preview = content
                
                # Multi-Vector Cross-Encoder 검색 결과 표시
                result["content"] = f"[Multi-Vector Cross-Encoder] 티켓: {ticket_id}\n내용: {content_preview}"
            
            # 기타 결과인 경우 (file_chunk, mail 등)
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

# ==================== 포괄적 테스트 함수들 ====================

def run_negative_test():
    """정답이 없는 질문 테스트 (Zero-shot & Negative Test)"""
    print("\n" + "="*80)
    print("🔍 정답이 없는 질문 테스트 (Zero-shot & Negative Test)")
    print("="*80)
    
    results = []
    for i, question in enumerate(NEGATIVE_TEST_QUESTIONS, 1):
        print(f"\n📝 테스트 {i}: {question}")
        print("-" * 60)
        
        # RAG 검색 실행
        search_results = search_rag(question)
        
        # 결과 분석
        if not search_results:
            print("✅ 올바른 응답: 관련 정보를 찾을 수 없습니다")
            result_status = "CORRECT_NO_RESULTS"
        else:
            # 결과가 있지만 관련성이 낮은지 확인
            max_score = max([r.get('score', 0) for r in search_results]) if search_results else 0
            if max_score < 0.3:  # 임계값 설정
                print(f"✅ 올바른 응답: 관련성이 낮은 결과 (최고 점수: {max_score:.3f})")
                result_status = "CORRECT_LOW_RELEVANCE"
            else:
                print(f"⚠️ 의심스러운 응답: 관련성 있는 결과 반환 (최고 점수: {max_score:.3f})")
                result_status = "SUSPICIOUS_HIGH_RELEVANCE"
                
                # 상위 3개 결과 출력
                for j, result in enumerate(search_results[:3], 1):
                    print(f"  {j}. {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
                    print(f"     {result.get('content', 'No content')[:100]}...")
        
        results.append({
            'question': question,
            'status': result_status,
            'result_count': len(search_results),
            'max_score': max_score if search_results else 0
        })
    
    return results

def run_diversity_test():
    """다양성 및 난이도 테스트"""
    print("\n" + "="*80)
    print("🎯 다양성 및 난이도 테스트")
    print("="*80)
    
    results = []
    for i, question in enumerate(DIVERSITY_TEST_QUESTIONS, 1):
        print(f"\n📝 테스트 {i}: {question}")
        print("-" * 60)
        
        # RAG 검색 실행
        search_results = search_rag(question)
        
        if search_results:
            print(f"✅ {len(search_results)}개 결과 반환")
            max_score = max([r.get('score', 0) for r in search_results])
            print(f"   최고 점수: {max_score:.3f}")
            
            # 상위 3개 결과 출력
            for j, result in enumerate(search_results[:3], 1):
                print(f"  {j}. {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
                print(f"     {result.get('content', 'No content')[:100]}...")
        else:
            print("❌ 결과 없음")
        
        results.append({
            'question': question,
            'result_count': len(search_results),
            'max_score': max([r.get('score', 0) for r in search_results]) if search_results else 0
        })
    
    return results

def run_stress_test():
    """스트레스 테스트 (중의적 표현, 오타, 길이 변형)"""
    print("\n" + "="*80)
    print("💪 스트레스 테스트 (중의적 표현, 오타, 길이 변형)")
    print("="*80)
    
    results = []
    for i, question in enumerate(STRESS_TEST_QUESTIONS, 1):
        print(f"\n📝 테스트 {i}: {question[:50]}{'...' if len(question) > 50 else ''}")
        print("-" * 60)
        
        # RAG 검색 실행
        search_results = search_rag(question)
        
        if search_results:
            print(f"✅ {len(search_results)}개 결과 반환")
            max_score = max([r.get('score', 0) for r in search_results])
            print(f"   최고 점수: {max_score:.3f}")
            
            # 상위 2개 결과만 간단히 출력
            for j, result in enumerate(search_results[:2], 1):
                print(f"  {j}. {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
        else:
            print("❌ 결과 없음")
        
        results.append({
            'question': question,
            'result_count': len(search_results),
            'max_score': max([r.get('score', 0) for r in search_results]) if search_results else 0
        })
    
    return results

def analyze_test_results(negative_results, diversity_results, stress_results):
    """테스트 결과 종합 분석"""
    print("\n" + "="*80)
    print("📊 테스트 결과 종합 분석")
    print("="*80)
    
    # 1. 정답이 없는 질문 테스트 분석
    print("\n🔍 정답이 없는 질문 테스트 분석:")
    correct_no_results = sum(1 for r in negative_results if r['status'] == 'CORRECT_NO_RESULTS')
    correct_low_relevance = sum(1 for r in negative_results if r['status'] == 'CORRECT_LOW_RELEVANCE')
    suspicious_high_relevance = sum(1 for r in negative_results if r['status'] == 'SUSPICIOUS_HIGH_RELEVANCE')
    
    print(f"  - 올바른 응답 (결과 없음): {correct_no_results}/{len(negative_results)} ({correct_no_results/len(negative_results)*100:.1f}%)")
    print(f"  - 올바른 응답 (낮은 관련성): {correct_low_relevance}/{len(negative_results)} ({correct_low_relevance/len(negative_results)*100:.1f}%)")
    print(f"  - 의심스러운 응답 (높은 관련성): {suspicious_high_relevance}/{len(negative_results)} ({suspicious_high_relevance/len(negative_results)*100:.1f}%)")
    
    # 2. 다양성 테스트 분석
    print("\n🎯 다양성 및 난이도 테스트 분석:")
    diversity_with_results = sum(1 for r in diversity_results if r['result_count'] > 0)
    avg_diversity_score = sum(r['max_score'] for r in diversity_results) / len(diversity_results)
    print(f"  - 결과 반환 비율: {diversity_with_results}/{len(diversity_results)} ({diversity_with_results/len(diversity_results)*100:.1f}%)")
    print(f"  - 평균 최고 점수: {avg_diversity_score:.3f}")
    
    # 3. 스트레스 테스트 분석
    print("\n💪 스트레스 테스트 분석:")
    stress_with_results = sum(1 for r in stress_results if r['result_count'] > 0)
    avg_stress_score = sum(r['max_score'] for r in stress_results) / len(stress_results)
    print(f"  - 결과 반환 비율: {stress_with_results}/{len(stress_results)} ({stress_with_results/len(stress_results)*100:.1f}%)")
    print(f"  - 평균 최고 점수: {avg_stress_score:.3f}")
    
    # 4. 전체 시스템 강건성 평가
    print("\n🏆 전체 시스템 강건성 평가:")
    total_tests = len(negative_results) + len(diversity_results) + len(stress_results)
    total_with_results = diversity_with_results + stress_with_results
    overall_success_rate = total_with_results / total_tests * 100
    
    print(f"  - 전체 테스트 수: {total_tests}")
    print(f"  - 성공적인 응답 비율: {overall_success_rate:.1f}%")
    
    if suspicious_high_relevance == 0:
        print("  - ✅ 환각(Hallucination) 없음: 정답이 없는 질문에 대해 적절히 대응")
    else:
        print(f"  - ⚠️ 환각 가능성: {suspicious_high_relevance}개 질문에서 의심스러운 높은 관련성")
    
    if avg_diversity_score > 0.7:
        print("  - ✅ 높은 검색 품질: 복잡한 질문에 대해 높은 관련성 점수")
    elif avg_diversity_score > 0.5:
        print("  - ⚠️ 보통 검색 품질: 복잡한 질문에 대해 중간 수준 관련성")
    else:
        print("  - ❌ 낮은 검색 품질: 복잡한 질문에 대해 낮은 관련성")

# ==================== 메인 실행 로직 ====================
def run_comprehensive_test():
    """포괄적인 RAG 시스템 테스트 실행"""
    print("🚀 포괄적인 RAG 시스템 테스트 시작")
    print("="*80)
    
    try:
        # 1. 정답이 없는 질문 테스트
        negative_results = run_negative_test()
        
        # 2. 다양성 및 난이도 테스트
        diversity_results = run_diversity_test()
        
        # 3. 스트레스 테스트
        stress_results = run_stress_test()
        
        # 4. 결과 종합 분석
        analyze_test_results(negative_results, diversity_results, stress_results)
        
        # 5. 결과를 JSON 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"comprehensive_test_results_{timestamp}.json"
        
        comprehensive_results = {
            'timestamp': timestamp,
            'negative_test': negative_results,
            'diversity_test': diversity_results,
            'stress_test': stress_results,
            'summary': {
                'total_negative_tests': len(negative_results),
                'total_diversity_tests': len(diversity_results),
                'total_stress_tests': len(stress_results),
                'total_tests': len(negative_results) + len(diversity_results) + len(stress_results)
            }
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 테스트 결과가 저장되었습니다: {results_file}")
        print("🎉 포괄적인 RAG 시스템 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 포괄적인 테스트 실행 중 오류 발생: {e}")
        raise e

def main():
    """메인 실행 함수"""
    print("🚀 RAG Golden Set 생성 스크립트 시작 (실제 RAG 검색 연결)")
    
    # 사용자에게 테스트 유형 선택 요청
    print("\n📋 테스트 유형을 선택하세요:")
    print("1. 기존 Golden Set 생성 (정답이 있는 질문)")
    print("2. 포괄적인 시스템 테스트 (정답 없는 질문, 다양성, 스트레스)")
    print("3. 둘 다 실행")
    
    choice = input("\n선택 (1/2/3): ").strip()
    
    if choice == "1":
        run_original_golden_set()
    elif choice == "2":
        run_comprehensive_test()
    elif choice == "3":
        run_original_golden_set()
        print("\n" + "="*80)
        run_comprehensive_test()
    else:
        print("❌ 잘못된 선택입니다. 기본값으로 포괄적인 테스트를 실행합니다.")
        run_comprehensive_test()

def run_original_golden_set():
    """기존 Golden Set 생성 로직"""
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
