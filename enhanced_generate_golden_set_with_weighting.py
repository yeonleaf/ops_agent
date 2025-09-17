#!/usr/bin/env python3
"""
지능형 청크 가중치가 적용된 RAG Golden Set 생성 스크립트
기존 generate_golden_set_with_rag.py에 지능형 가중치 시스템을 통합
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
    QUESTIONS_PER_TICKET,
    MAX_TICKETS_TO_PROCESS
)

# RAG 관련 모듈들 import
from multi_vector_cross_encoder_rag import MultiVectorCrossEncoderRAG
from intelligent_chunk_weighting import IntelligentChunkWeighting

class EnhancedRAGWithWeighting:
    """지능형 가중치가 적용된 RAG 시스템"""

    def __init__(self):
        """초기화"""
        self.base_rag = MultiVectorCrossEncoderRAG()
        self.weighting_system = IntelligentChunkWeighting()

    def search_with_intelligent_weighting(self, query: str, n_candidates: int = 50,
                                        top_k: int = 10) -> List[Dict[str, Any]]:
        """
        지능형 가중치가 적용된 검색

        Args:
            query: 검색 쿼리
            n_candidates: 1단계 후보 수
            top_k: 최종 결과 수

        Returns:
            가중치가 적용된 검색 결과
        """
        try:
            # 1. 기본 RAG 검색 수행
            base_results = self.base_rag.search(query, n_candidates, top_k)

            # 2. 검색 결과를 가중치 시스템 형식으로 변환
            enhanced_results = []
            for result in base_results:
                # chunk_type 추출 (실제 메타데이터에서)
                metadata = result.get('metadata', {})

                # 실제 chunk_type 정보 복원 시도
                chunk_type = self._extract_real_chunk_type(result)

                enhanced_result = {
                    'id': result.get('id', ''),
                    'content': result.get('content', ''),
                    'chunk_type': chunk_type,
                    'cosine_score': result.get('similarity_score', 0.0),
                    'embedding': [],  # 임베딩은 재계산하지 않음
                    'metadata': {
                        **metadata,
                        'original_score': result.get('similarity_score', 0.0),
                        'search_method': 'enhanced_rag_with_weighting'
                    }
                }
                enhanced_results.append(enhanced_result)

            # 3. Mock 쿼리 임베딩 (실제로는 검색 시 사용된 임베딩 활용)
            import numpy as np
            mock_query_embedding = np.random.normal(0, 1, 768).tolist()

            # 4. 가중치 적용
            weighted_results = self.weighting_system.apply_weighted_scoring(
                enhanced_results, mock_query_embedding
            )

            # 5. 결과를 원래 형식으로 변환
            final_results = []
            for weighted_result in weighted_results:
                final_result = {
                    "id": weighted_result.id,
                    "content": weighted_result.content,
                    "similarity_score": weighted_result.weighted_score,  # 가중치 적용된 점수
                    "source": "enhanced_rag_with_weighting",
                    "metadata": {
                        **weighted_result.metadata,
                        'chunk_type': weighted_result.chunk_type,
                        'weight': weighted_result.weight,
                        'original_cosine_score': weighted_result.cosine_score,
                        'weighted_score': weighted_result.weighted_score,
                        'weight_applied': True
                    }
                }
                final_results.append(final_result)

            return final_results

        except Exception as e:
            print(f"❌ 가중치 적용 검색 실패: {e}")
            # 실패 시 기본 RAG 결과 반환
            return self.base_rag.search(query, n_candidates, top_k)

    def _extract_real_chunk_type(self, result: Dict[str, Any]) -> str:
        """
        실제 chunk_type 추출 (content 기반 휴리스틱)

        Args:
            result: 검색 결과

        Returns:
            추출된 chunk_type
        """
        content = result.get('content', '').lower()
        metadata = result.get('metadata', {})

        # 메타데이터에서 chunk_type 확인
        if 'chunk_type' in metadata and metadata['chunk_type'] != 'multi_vector':
            return metadata['chunk_type']

        # content 기반 휴리스틱 분류
        if any(keyword in content for keyword in ['제목:', '타이틀:', 'title:']):
            return 'title'
        elif any(keyword in content for keyword in ['요약:', 'summary:', '개요:']):
            return 'summary'
        elif any(keyword in content for keyword in ['설명:', 'description:', '상세:']):
            return 'description'
        elif any(keyword in content for keyword in ['댓글:', 'comment:', '의견:']):
            return 'comment'
        elif any(keyword in content for keyword in ['헤더:', 'header:']):
            return 'header'
        elif len(content) < 100:  # 짧은 텍스트는 제목으로 추정
            return 'title'
        elif len(content) > 500:  # 긴 텍스트는 본문으로 추정
            return 'body'
        else:
            return 'description'  # 중간 길이는 설명으로 추정

def search_rag_with_weighting(query: str) -> List[Dict[str, Any]]:
    """
    가중치가 적용된 RAG 검색 함수 (generate_golden_set_with_rag.py 호환)

    Args:
        query: 검색 쿼리

    Returns:
        가중치가 적용된 검색 결과 리스트
    """
    try:
        # 가중치 적용 RAG 시스템 초기화
        enhanced_rag = EnhancedRAGWithWeighting()

        # 가중치 적용 검색 실행
        results = enhanced_rag.search_with_intelligent_weighting(
            query=query,
            n_candidates=50,  # 1단계 후보 수
            top_k=10         # 최종 결과 수
        )

        # 결과를 기존 형식으로 변환
        formatted_results = []
        for i, item in enumerate(results):
            # 가중치 정보 포함하여 결과 포맷팅
            result = {
                "id": item.get("id", f"ITEM-{i}"),
                "content": item.get("content", ""),
                "score": item.get("similarity_score", 0.0),
                "raw_score": item.get("metadata", {}).get("original_cosine_score", item.get("similarity_score", 0.0)),
                "similarity_to_query": item.get("similarity_score", 0.0),
                "source": "enhanced_rag_with_weighting"
            }

            # 가중치 적용 결과인 경우 상세 정보 추가
            metadata = item.get('metadata', {})
            if metadata.get('weight_applied'):
                chunk_type = metadata.get('chunk_type', 'unknown')
                weight = metadata.get('weight', 1.0)
                weighted_score = metadata.get('weighted_score', 0.0)
                original_score = metadata.get('original_cosine_score', 0.0)

                # 내용 미리보기
                content = item.get('content', 'No Content')
                if len(content) > 200:
                    content_preview = content[:200] + "..."
                else:
                    content_preview = content

                # 가중치 정보를 포함한 상세 내용
                result["content"] = f"[가중치 적용] {chunk_type.upper()} (weight: {weight:.1f})\n" \
                                  f"원본 점수: {original_score:.4f} → 가중치 점수: {weighted_score:.4f}\n" \
                                  f"내용: {content_preview}"

            formatted_results.append(result)

        print(f"🔍 가중치 적용 RAG 검색 실행: '{query}' -> {len(formatted_results)}개 결과")

        # 가중치 효과 요약 출력
        if formatted_results:
            weighted_items = [r for r in results if r.get('metadata', {}).get('weight_applied')]
            if weighted_items:
                print(f"   ⚖️ 가중치 적용된 결과: {len(weighted_items)}개")
                for item in weighted_items[:3]:  # 상위 3개만 표시
                    metadata = item.get('metadata', {})
                    chunk_type = metadata.get('chunk_type', 'unknown')
                    weight = metadata.get('weight', 1.0)
                    improvement = metadata.get('weighted_score', 0) - metadata.get('original_cosine_score', 0)
                    print(f"      - {chunk_type}: 가중치 {weight:.1f}, 점수 향상 {improvement:+.4f}")

        return formatted_results

    except Exception as e:
        print(f"❌ 가중치 적용 RAG 검색 실패: {str(e)}")
        # 실패 시 빈 결과 반환
        return []

def create_enhanced_test_questions() -> List[str]:
    """가중치 테스트에 특화된 질문들 생성"""
    return [
        # title 우선 질문 (title chunk가 높은 점수를 받을 것으로 예상)
        "서버 접속 문제 해결 방법",
        "데이터베이스 연결 오류",
        "로그인 시스템 장애",

        # description 우선 질문 (description chunk가 높은 점수를 받을 것으로 예상)
        "메인 서버에 접속할 수 없을 때 확인해야 할 사항들을 알고 싶습니다",
        "데이터베이스 연결이 끊어지는 문제의 원인과 해결책을 설명해주세요",
        "사용자 인터페이스 개선 방안에 대한 자세한 설명이 필요합니다",

        # comment 우선 질문 (comment chunk는 낮은 점수를 받을 것으로 예상)
        "다른 사용자들의 경험담이나 의견을 알고 싶어요",
        "이 문제에 대한 커뮤니티 피드백은 어떤가요",
        "비슷한 경험을 한 사람들의 해결 방법을 참고하고 싶습니다"
    ]

def run_enhanced_weighting_test():
    """가중치 효과를 확인하는 전용 테스트"""
    print("="*80)
    print("🎯 지능형 가중치 효과 검증 테스트")
    print("="*80)

    test_questions = create_enhanced_test_questions()

    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 테스트 {i}: {question}")
        print("-" * 60)

        # 가중치 적용 검색
        results = search_rag_with_weighting(question)

        if results:
            print(f"✅ {len(results)}개 결과 (가중치 적용)")

            # 상위 3개 결과의 가중치 효과 분석
            for j, result in enumerate(results[:3], 1):
                score = result.get('score', 0)
                print(f"  {j}. ID: {result.get('id', 'Unknown')} (점수: {score:.4f})")

                # 가중치 정보 추출
                content = result.get('content', '')
                if '[가중치 적용]' in content:
                    lines = content.split('\n')
                    if len(lines) > 1:
                        print(f"     {lines[1]}")  # 점수 변화 정보 출력
        else:
            print("❌ 결과 없음")

def main():
    """메인 실행 함수"""
    print("🚀 지능형 가중치 적용 RAG Golden Set 생성 스크립트")

    # 사용자에게 테스트 유형 선택 요청
    print("\n📋 테스트 유형을 선택하세요:")
    print("1. 기존 Golden Set 생성 (가중치 적용)")
    print("2. 가중치 효과 검증 전용 테스트")
    print("3. 둘 다 실행")

    choice = input("\n선택 (1/2/3): ").strip()

    if choice == "1":
        run_original_golden_set_with_weighting()
    elif choice == "2":
        run_enhanced_weighting_test()
    elif choice == "3":
        run_original_golden_set_with_weighting()
        print("\n" + "="*80)
        run_enhanced_weighting_test()
    else:
        print("❌ 잘못된 선택입니다. 가중치 효과 검증 테스트를 실행합니다.")
        run_enhanced_weighting_test()

def run_original_golden_set_with_weighting():
    """기존 Golden Set 생성 로직 (가중치 적용 버전)"""
    try:
        # Azure OpenAI 클라이언트 초기화
        llm_client = initialize_azure_openai()

        # CSV 파일 존재 확인
        if not os.path.exists(JIRA_CSV_FILE_PATH):
            print(f"⚠️ Jira CSV 파일을 찾을 수 없습니다: {JIRA_CSV_FILE_PATH}")
            print("가중치 효과 검증 테스트만 실행합니다.")
            run_enhanced_weighting_test()
            return

        # CSV 파일 읽기
        print(f"📖 CSV 파일 읽기: {JIRA_CSV_FILE_PATH}")
        df = pd.read_csv(JIRA_CSV_FILE_PATH)
        print(f"✅ {len(df)}개의 티켓을 발견했습니다.")

        # 처리할 티켓 수 제한
        if len(df) > MAX_TICKETS_TO_PROCESS:
            df = df.head(MAX_TICKETS_TO_PROCESS)
            print(f"⚠️ 테스트를 위해 {MAX_TICKETS_TO_PROCESS}개 티켓만 처리합니다.")

        # 로그 파일명에 가중치 표시 추가
        output_file = f"golden_set_results_with_intelligent_weighting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # 로그 파일 열기
        with open(output_file, 'w', encoding='utf-8') as log_file:
            # 헤더 정보 기록
            log_file.write("="*80 + "\n")
            log_file.write("RAG 시스템 Golden Set 생성 결과 (지능형 가중치 적용)\n")
            log_file.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"처리된 티켓 수: {len(df)}\n")
            log_file.write(f"티켓당 질문 수: {QUESTIONS_PER_TICKET}\n")
            log_file.write("\n🎯 가중치 시스템 정보:\n")
            log_file.write("- title: 1.5배, summary: 1.3배, description: 1.2배\n")
            log_file.write("- body: 1.0배 (기본), comment: 0.8배, attachment: 0.6배\n")
            log_file.write("- 가중치 적용된 점수 = 원본 코사인 유사도 × chunk_type 가중치\n")
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

                    # 가중치 적용 RAG 검색 실행
                    rag_results = search_rag_with_weighting(question)

                    # 결과 로그에 기록
                    log_test_case(log_file, test_case_num, ticket, question, rag_results)

                    print(f"   ✅ 테스트 케이스 #{test_case_num} 완료")

                except Exception as e:
                    print(f"   ❌ 테스트 케이스 #{test_case_num} 실패: {str(e)}")
                    log_file.write(f"\n--- [Test Case #{test_case_num}] ---\n")
                    log_file.write(f"❌ 오류 발생: {str(e)}\n")
                    log_file.write("="*80 + "\n")
                    continue

        print(f"\n🎉 지능형 가중치 적용 Golden Set 생성 완료!")
        print(f"📄 결과 파일: {output_file}")
        print(f"📊 처리된 테스트 케이스: {len(df)}개")

    except Exception as e:
        print(f"❌ 스크립트 실행 실패: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    # 전역 search_rag 함수를 가중치 버전으로 교체
    import sys
    current_module = sys.modules[__name__]
    current_module.search_rag = search_rag_with_weighting

    exit_code = main()
    exit(exit_code)