#!/usr/bin/env python3
"""
file_chunks 데이터를 활용한 가중치 적용 Golden Set 테스트
jira_multi_vector_chunks 대신 기존 file_chunks 활용
"""

import os
import sys
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 기존 모듈들 import
from generate_golden_set import (
    initialize_azure_openai,
    generate_question_for_ticket,
    JIRA_CSV_FILE_PATH,
    QUESTIONS_PER_TICKET,
    MAX_TICKETS_TO_PROCESS
)

from intelligent_chunk_weighting import IntelligentChunkWeighting
import numpy as np

class FileChunksRAGWithWeighting:
    """file_chunks 데이터를 활용한 가중치 적용 RAG 시스템"""

    def __init__(self):
        """초기화"""
        self.client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        self.collection = self.client.get_collection("file_chunks")
        self.weighting_system = IntelligentChunkWeighting()
        print(f"📊 file_chunks 컬렉션 연결: {self.collection.count()}개 문서")

    def search_with_weighting(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        file_chunks에서 가중치 적용 검색

        Args:
            query: 검색 쿼리
            n_results: 결과 수

        Returns:
            가중치가 적용된 검색 결과
        """
        try:
            # 1. 기본 벡터 검색 (기존 임베딩 함수 사용)
            basic_results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )

            if not basic_results['ids'][0]:
                return []

            # 2. 검색 결과를 가중치 시스템 형식으로 변환
            search_results = []
            for i in range(len(basic_results['ids'][0])):
                metadata = basic_results['metadatas'][0][i] if basic_results['metadatas'][0] else {}
                content = basic_results['documents'][0][i] if basic_results['documents'][0] else ""
                distance = basic_results['distances'][0][i] if basic_results['distances'][0] else 1.0

                # 코사인 유사도로 변환
                cosine_score = max(0.0, 1.0 - distance)

                # chunk_type 추정
                chunk_type = self._estimate_chunk_type(metadata, content)

                search_result = {
                    'id': basic_results['ids'][0][i],
                    'content': content,
                    'chunk_type': chunk_type,
                    'cosine_score': cosine_score,
                    'embedding': [],
                    'metadata': {
                        **metadata,
                        'estimated_chunk_type': chunk_type,
                        'original_distance': distance
                    }
                }
                search_results.append(search_result)

            # 3. 가중치 적용 (Mock 쿼리 임베딩 사용 - 384차원)
            mock_query_embedding = np.random.normal(0, 1, 384).tolist()
            weighted_results = self.weighting_system.apply_weighted_scoring(
                search_results, mock_query_embedding
            )

            # 4. 결과를 표준 형식으로 변환
            final_results = []
            for weighted_result in weighted_results:
                result = {
                    "id": weighted_result.id,
                    "content": weighted_result.content,
                    "score": weighted_result.weighted_score,
                    "raw_score": weighted_result.cosine_score,
                    "similarity_to_query": weighted_result.weighted_score,
                    "source": "file_chunks_with_weighting"
                }

                # 가중치 정보 포함한 상세 내용
                chunk_type = weighted_result.chunk_type
                weight = weighted_result.weight
                content_preview = weighted_result.content[:200].replace('\n', ' ') + "..."

                result["content"] = f"[가중치 적용] {chunk_type.upper()} (weight: {weight:.1f})\n" \
                                  f"원본 점수: {weighted_result.cosine_score:.4f} → 가중치 점수: {weighted_result.weighted_score:.4f}\n" \
                                  f"내용: {content_preview}"

                final_results.append(result)

            return final_results

        except Exception as e:
            print(f"❌ file_chunks 검색 실패: {e}")
            return []

    def _estimate_chunk_type(self, metadata: Dict[str, Any], content: str) -> str:
        """메타데이터와 내용을 기반으로 chunk_type 추정"""
        content_lower = content.lower()

        # 1. 구조적 패턴 분석
        if any(pattern in content_lower for pattern in ['제목:', 'title:', '이슈 키:', 'issue key:']):
            return 'title'
        elif any(pattern in content_lower for pattern in ['요약:', 'summary:', '개요:']):
            return 'summary'
        elif any(pattern in content_lower for pattern in ['설명:', 'description:', '상세:', '내용:']):
            return 'description'
        elif any(pattern in content_lower for pattern in ['댓글:', 'comment:', '의견:', '피드백:']):
            return 'comment'
        elif any(pattern in content_lower for pattern in ['헤더:', 'header:']):
            return 'header'

        # 2. 내용 길이 기반
        elif len(content.strip()) < 30:
            return 'title'
        elif len(content.strip()) < 100:
            return 'summary'
        elif len(content.strip()) > 1000:
            return 'body'
        else:
            return 'description'

def search_rag_with_file_chunks(query: str) -> List[Dict[str, Any]]:
    """
    file_chunks를 활용한 가중치 적용 RAG 검색

    Args:
        query: 검색 쿼리

    Returns:
        가중치가 적용된 검색 결과 리스트
    """
    try:
        # file_chunks 기반 RAG 시스템 초기화
        rag_system = FileChunksRAGWithWeighting()

        # 검색 실행
        results = rag_system.search_with_weighting(query, n_results=10)

        print(f"🔍 file_chunks 가중치 적용 검색: '{query}' -> {len(results)}개 결과")

        # 가중치 효과 요약
        if results:
            weighted_items = [r for r in results if '[가중치 적용]' in r.get('content', '')]
            if weighted_items:
                print(f"   ⚖️ 가중치 적용된 결과: {len(weighted_items)}개")

                # chunk_type별 통계
                chunk_types = {}
                for item in weighted_items[:5]:
                    content = item.get('content', '')
                    if '[가중치 적용]' in content:
                        # chunk_type 추출
                        lines = content.split('\n')
                        if len(lines) > 0:
                            first_line = lines[0]
                            if '(' in first_line and ')' in first_line:
                                chunk_type = first_line.split('[가중치 적용]')[1].split('(')[0].strip()
                                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

                for chunk_type, count in chunk_types.items():
                    print(f"      - {chunk_type}: {count}개")

        return results

    except Exception as e:
        print(f"❌ file_chunks 가중치 검색 실패: {str(e)}")
        return []

def log_test_case_with_weighting(log_file, test_case_num: int, ticket: Dict[str, Any],
                                question: str, rag_results: List[Dict[str, Any]]):
    """
    가중치 정보를 포함한 테스트 케이스 로깅

    Args:
        log_file: 로그 파일 객체
        test_case_num: 테스트 케이스 번호
        ticket: 원본 티켓 정보
        question: 생성된 질문
        rag_results: 가중치 적용된 RAG 검색 결과
    """
    ticket_id = ticket.get('Key', 'Unknown')
    ticket_summary = ticket.get('Summary', 'No Summary')
    ticket_description = ticket.get('Description', 'No Description')

    log_file.write(f"\n--- [Test Case #{test_case_num}] ---\n")
    log_file.write(f"🎯 정답 티켓: {ticket_id} ({ticket_summary})\n")
    log_file.write(f"📝 티켓 설명: {ticket_description}\n")
    log_file.write(f"🧠 생성된 질문: {question}\n")
    log_file.write(f"🔍 file_chunks 가중치 적용 검색 결과 (Top {len(rag_results)}):\n")

    for i, result in enumerate(rag_results, 1):
        result_id = result.get('id', 'Unknown')
        result_content = result.get('content', 'No Content')
        result_score = result.get('score', 0.0)
        raw_score = result.get('raw_score', result_score)

        log_file.write(f"\n   {i}. ID: {result_id} (가중치 점수: {result_score:.4f}, 원본: {raw_score:.4f})\n")
        log_file.write(f"      내용:\n")

        # 내용을 여러 줄로 나누어 표시
        content_lines = result_content.split('\n')
        for line in content_lines:
            log_file.write(f"      {line}\n")

        log_file.write(f"      {'-' * 60}\n")

    log_file.write("\n" + "="*80 + "\n")

def create_weighted_test_questions() -> List[str]:
    """가중치 테스트에 특화된 질문들"""
    return [
        # 다양한 chunk_type을 테스트할 수 있는 질문들
        "시스템 제목이나 헤더에 관련된 정보",  # title 우선
        "프로젝트 요약이나 개요 정보",        # summary 우선
        "상세한 설명이나 구현 방법",          # description 우선
        "사용자 피드백이나 댓글 내용",        # comment 우선
        "전체적인 시스템 구조나 본문"         # body 우선
    ]

def run_weighted_test_only():
    """가중치 효과만 확인하는 전용 테스트"""
    print("="*80)
    print("🎯 file_chunks 가중치 효과 검증 테스트")
    print("="*80)

    test_questions = create_weighted_test_questions()

    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 테스트 {i}: {question}")
        print("-" * 60)

        # 가중치 적용 검색
        results = search_rag_with_file_chunks(question)

        if results:
            print(f"✅ {len(results)}개 결과")

            # 상위 3개 결과의 가중치 효과 표시
            for j, result in enumerate(results[:3], 1):
                score = result.get('score', 0)
                raw_score = result.get('raw_score', 0)
                improvement = score - raw_score
                print(f"  {j}. ID: {result.get('id', 'Unknown')[:12]}...")
                print(f"     가중치 효과: {raw_score:.4f} → {score:.4f} ({improvement:+.4f})")

                # chunk_type 정보 추출
                content = result.get('content', '')
                if '[가중치 적용]' in content:
                    lines = content.split('\n')
                    if len(lines) > 0:
                        print(f"     {lines[0]}")  # chunk_type과 weight 정보
        else:
            print("❌ 결과 없음")

def main():
    """메인 실행 함수"""
    print("🚀 file_chunks 기반 가중치 적용 Golden Set 테스트")

    # 테스트 유형 선택
    print("\n📋 테스트 유형을 선택하세요:")
    print("1. 기존 Golden Set 생성 (file_chunks + 가중치)")
    print("2. 가중치 효과 검증 전용 테스트")

    choice = input("\n선택 (1/2): ").strip()

    if choice == "1":
        run_golden_set_with_file_chunks()
    else:
        run_weighted_test_only()

def run_golden_set_with_file_chunks():
    """기존 Golden Set 생성 (file_chunks 버전)"""
    try:
        # CSV 파일 확인
        if not os.path.exists(JIRA_CSV_FILE_PATH):
            print(f"⚠️ Jira CSV 파일을 찾을 수 없습니다: {JIRA_CSV_FILE_PATH}")
            print("가중치 효과 검증 테스트만 실행합니다.")
            run_weighted_test_only()
            return

        # Azure OpenAI 클라이언트 초기화
        llm_client = initialize_azure_openai()

        # CSV 파일 읽기
        print(f"📖 CSV 파일 읽기: {JIRA_CSV_FILE_PATH}")
        df = pd.read_csv(JIRA_CSV_FILE_PATH)
        print(f"✅ {len(df)}개의 티켓을 발견했습니다.")

        # 처리할 티켓 수 제한
        if len(df) > MAX_TICKETS_TO_PROCESS:
            df = df.head(MAX_TICKETS_TO_PROCESS)
            print(f"⚠️ 테스트를 위해 {MAX_TICKETS_TO_PROCESS}개 티켓만 처리합니다.")

        # 로그 파일명
        output_file = f"file_chunks_weighted_golden_set_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # 로그 파일 생성
        with open(output_file, 'w', encoding='utf-8') as log_file:
            # 헤더 정보
            log_file.write("="*80 + "\n")
            log_file.write("file_chunks 기반 가중치 적용 Golden Set 결과\n")
            log_file.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"처리된 티켓 수: {len(df)}\n")
            log_file.write(f"데이터 소스: file_chunks (1517개 문서)\n")
            log_file.write("\n🎯 가중치 시스템:\n")
            log_file.write("- title: 1.5배, summary: 1.3배, description: 1.2배\n")
            log_file.write("- body: 1.0배, comment: 0.8배, attachment: 0.6배\n")
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

                    # file_chunks 가중치 검색 실행
                    rag_results = search_rag_with_file_chunks(question)

                    # 결과 로그에 기록
                    log_test_case_with_weighting(log_file, test_case_num, ticket, question, rag_results)

                    print(f"   ✅ 테스트 케이스 #{test_case_num} 완료")

                except Exception as e:
                    print(f"   ❌ 테스트 케이스 #{test_case_num} 실패: {str(e)}")
                    log_file.write(f"\n--- [Test Case #{test_case_num}] ---\n")
                    log_file.write(f"❌ 오류 발생: {str(e)}\n")
                    log_file.write("="*80 + "\n")
                    continue

        print(f"\n🎉 file_chunks 가중치 적용 Golden Set 생성 완료!")
        print(f"📄 결과 파일: {output_file}")
        print(f"📊 처리된 테스트 케이스: {len(df)}개")

    except Exception as e:
        print(f"❌ 스크립트 실행 실패: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)