#!/usr/bin/env python3
"""
RAG 시스템 정확도 평가 스크립트

test_data.csv의 쿼리를 사용하여 RAG 시스템의 성능을 평가합니다.
- MRR (Mean Reciprocal Rank): 정답이 나타나는 위치의 역수 평균
- Hit@K: 상위 K개 결과에 정답이 포함되는 비율
- Top-1 Accuracy: 1위가 정답인 비율
"""

import csv
import os
import sys
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rrf_fusion_rag_system import RRFRAGSystem, RRFConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rag_evaluation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RAGEvaluator:
    """RAG 시스템 평가 클래스"""

    def __init__(self, rag_system: RRFRAGSystem):
        """
        RAG 평가기 초기화

        Args:
            rag_system: 평가할 RAG 시스템
        """
        self.rag_system = rag_system
        self.results = []

    def load_test_data(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        테스트 데이터 로드 (여러 정답 지원)

        Args:
            csv_path: CSV 파일 경로

        Returns:
            테스트 케이스 리스트 [{'query': '...', 'answer_ticket_ids': ['...', '...']}, ...]
        """
        test_cases = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 세미콜론(;)으로 구분된 여러 정답 처리
                    answer_ids = [id.strip() for id in row['answer_ticket_id'].split(';') if id.strip()]
                    # 중복 제거
                    answer_ids = list(dict.fromkeys(answer_ids))

                    test_cases.append({
                        'query': row['query'],
                        'answer_ticket_ids': answer_ids  # 리스트로 변경
                    })

            total_answers = sum(len(tc['answer_ticket_ids']) for tc in test_cases)
            logger.info(f"✅ 테스트 데이터 로드 완료: {len(test_cases)}개 케이스, {total_answers}개 정답")
            return test_cases
        except Exception as e:
            logger.error(f"❌ 테스트 데이터 로드 실패: {e}")
            raise e

    def extract_ticket_id(self, metadata: Dict[str, Any]) -> str:
        """
        메타데이터에서 티켓 ID 추출

        Args:
            metadata: 문서 메타데이터

        Returns:
            티켓 ID (예: "BTVO-61021")
        """
        # 가능한 키 목록
        possible_keys = ['ticket_id', 'ticket_key', 'jira_key', 'issue_key', 'key', 'id']

        for key in possible_keys:
            if key in metadata:
                ticket_id = metadata[key]
                # BTVO-숫자 형식으로 변환 (필요시)
                if isinstance(ticket_id, str):
                    return ticket_id

        # 메타데이터 전체 로깅 (디버그용)
        logger.debug(f"메타데이터에서 ticket_id를 찾을 수 없음: {metadata}")
        return None

    def find_best_answer_rank(self, search_results: List[Dict[str, Any]],
                              answer_ticket_ids: List[str]) -> Tuple[int, bool, str]:
        """
        검색 결과에서 여러 정답 중 가장 높은 순위 찾기

        Args:
            search_results: RAG 검색 결과
            answer_ticket_ids: 정답 티켓 ID 리스트

        Returns:
            (순위, 발견 여부, 발견된 티켓 ID) 튜플. 순위는 1부터 시작, 없으면 -1
        """
        best_rank = -1
        found_ticket = None

        for rank, result in enumerate(search_results, start=1):
            metadata = result.get('metadata', {})
            ticket_id = self.extract_ticket_id(metadata)

            if ticket_id and ticket_id in answer_ticket_ids:
                # 첫 번째 발견된 정답 (가장 높은 순위)
                best_rank = rank
                found_ticket = ticket_id
                break

        if best_rank > 0:
            return best_rank, True, found_ticket
        else:
            return -1, False, None

    def evaluate_single_query(self, query: str, answer_ticket_ids: List[str]) -> Dict[str, Any]:
        """
        단일 쿼리 평가 (여러 정답 지원)

        Args:
            query: 검색 쿼리
            answer_ticket_ids: 정답 티켓 ID 리스트

        Returns:
            평가 결과 딕셔너리
        """
        try:
            answer_str = ', '.join(answer_ticket_ids)
            logger.info(f"🔍 평가 중: '{query}' (정답: {answer_str})")

            # RAG 검색 실행
            search_results = self.rag_system.rrf_search(query)

            if not search_results:
                logger.warning(f"⚠️ 검색 결과 없음: '{query}'")
                return {
                    'query': query,
                    'answer_ticket_ids': answer_ticket_ids,
                    'rank': -1,
                    'found': False,
                    'found_ticket': None,
                    'reciprocal_rank': 0.0,
                    'top_results': []
                }

            # 여러 정답 중 가장 높은 순위 찾기
            rank, found, found_ticket = self.find_best_answer_rank(search_results, answer_ticket_ids)

            # 상위 10개 결과 (디버깅용 - 더 많이 표시)
            top_results = []
            for i, result in enumerate(search_results[:10], start=1):
                metadata = result.get('metadata', {})
                ticket_id = self.extract_ticket_id(metadata)
                is_answer = ticket_id in answer_ticket_ids if ticket_id else False
                top_results.append({
                    'rank': i,
                    'ticket_id': ticket_id,
                    'is_answer': is_answer,
                    'score': result.get('score', 0.0),
                    'rrf_score': metadata.get('rrf_score', 0.0)
                })

            # Reciprocal Rank 계산
            reciprocal_rank = 1.0 / rank if found else 0.0

            result = {
                'query': query,
                'answer_ticket_ids': answer_ticket_ids,
                'rank': rank,
                'found': found,
                'found_ticket': found_ticket,
                'reciprocal_rank': reciprocal_rank,
                'top_results': top_results
            }

            if found:
                logger.info(f"✅ 정답 발견: {found_ticket} (순위 {rank})")
            else:
                logger.warning(f"❌ 정답 미발견: {answer_str}")

            return result

        except Exception as e:
            logger.error(f"❌ 쿼리 평가 실패: {e}")
            return {
                'query': query,
                'answer_ticket_ids': answer_ticket_ids,
                'rank': -1,
                'found': False,
                'found_ticket': None,
                'reciprocal_rank': 0.0,
                'error': str(e),
                'top_results': []
            }

    def evaluate_all(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        모든 테스트 케이스 평가

        Args:
            test_cases: 테스트 케이스 리스트

        Returns:
            평가 결과 리스트
        """
        results = []

        logger.info(f"🚀 전체 평가 시작: {len(test_cases)}개 케이스")

        for i, test_case in enumerate(test_cases, start=1):
            logger.info(f"\n{'='*60}")
            logger.info(f"진행률: {i}/{len(test_cases)}")

            result = self.evaluate_single_query(
                test_case['query'],
                test_case['answer_ticket_ids']  # 리스트로 변경
            )
            results.append(result)

        logger.info(f"\n{'='*60}")
        logger.info("✅ 전체 평가 완료")

        self.results = results
        return results

    def calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        평가 메트릭 계산

        Args:
            results: 평가 결과 리스트

        Returns:
            메트릭 딕셔너리
        """
        total = len(results)

        if total == 0:
            return {}

        # MRR (Mean Reciprocal Rank)
        mrr = sum(r['reciprocal_rank'] for r in results) / total

        # Hit@K 계산
        def hit_at_k(k: int) -> float:
            hits = sum(1 for r in results if r['found'] and r['rank'] <= k and r['rank'] > 0)
            return hits / total

        hit_at_1 = hit_at_k(1)
        hit_at_3 = hit_at_k(3)
        hit_at_5 = hit_at_k(5)
        hit_at_10 = hit_at_k(10)

        # Top-1 Accuracy (=Hit@1)
        top1_accuracy = hit_at_1

        # 정답 발견율 (전체 결과에서)
        found_rate = sum(1 for r in results if r['found']) / total

        # 평균 순위 (정답이 발견된 경우만)
        found_results = [r for r in results if r['found']]
        avg_rank = sum(r['rank'] for r in found_results) / len(found_results) if found_results else 0.0

        metrics = {
            'total_queries': total,
            'mrr': mrr,
            'hit@1': hit_at_1,
            'hit@3': hit_at_3,
            'hit@5': hit_at_5,
            'hit@10': hit_at_10,
            'top1_accuracy': top1_accuracy,
            'found_rate': found_rate,
            'avg_rank': avg_rank,
            'found_count': len(found_results)
        }

        return metrics

    def print_metrics(self, metrics: Dict[str, float]):
        """메트릭 출력"""
        print("\n" + "="*60)
        print("📊 RAG 시스템 평가 결과")
        print("="*60)
        print(f"총 쿼리 수: {metrics['total_queries']}")
        print(f"정답 발견 수: {metrics['found_count']}")
        print(f"정답 발견율: {metrics['found_rate']:.2%}")
        print()
        print("📈 주요 메트릭:")
        print(f"  MRR (Mean Reciprocal Rank): {metrics['mrr']:.4f}")
        print(f"  Top-1 Accuracy (Hit@1):     {metrics['top1_accuracy']:.2%}")
        print(f"  Hit@3:                      {metrics['hit@3']:.2%}")
        print(f"  Hit@5:                      {metrics['hit@5']:.2%}")
        print(f"  Hit@10:                     {metrics['hit@10']:.2%}")
        print()
        print(f"평균 정답 순위 (발견된 경우): {metrics['avg_rank']:.2f}")
        print("="*60)

    def save_results(self, results: List[Dict[str, Any]], metrics: Dict[str, float],
                    output_path: str):
        """
        평가 결과 저장

        Args:
            results: 평가 결과 리스트
            metrics: 메트릭
            output_path: 출력 파일 경로
        """
        try:
            output_data = {
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'results': results
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 평가 결과 저장: {output_path}")

        except Exception as e:
            logger.error(f"❌ 결과 저장 실패: {e}")


def main():
    """메인 실행 함수"""
    try:
        # 로그 디렉토리 생성
        os.makedirs('logs', exist_ok=True)

        # RAG 시스템 초기화
        logger.info("🔧 RAG 시스템 초기화 중...")
        rrf_config = RRFConfig(
            rrf_k=60,
            multi_query_results=20,
            hyde_results=20,
            bm25_results=20,
            final_candidates=30,
            enable_bm25=True,
            bm25_tokenizer="korean"
        )

        rag_system = RRFRAGSystem(
            collection_name="jira_chunks",
            rrf_config=rrf_config
        )

        # 평가기 초기화
        evaluator = RAGEvaluator(rag_system)

        # 테스트 데이터 로드
        test_data_path = "test_data.csv"
        test_cases = evaluator.load_test_data(test_data_path)

        # 평가 실행
        results = evaluator.evaluate_all(test_cases)

        # 메트릭 계산
        metrics = evaluator.calculate_metrics(results)

        # 결과 출력
        evaluator.print_metrics(metrics)

        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"rag_evaluation_results_{timestamp}.json"
        evaluator.save_results(results, metrics, output_path)

        # 실패 케이스 분석
        failed_cases = [r for r in results if not r['found']]
        if failed_cases:
            print("\n❌ 정답을 찾지 못한 케이스:")
            for case in failed_cases[:5]:  # 상위 5개만 출력
                print(f"  - 쿼리: {case['query']}")
                answer_str = ', '.join(case['answer_ticket_ids'])
                print(f"    정답: {answer_str}")
                if case.get('top_results'):
                    print(f"    상위 결과: {[r['ticket_id'] for r in case['top_results'][:3]]}")

        logger.info("✅ 평가 완료")

    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        raise e


if __name__ == "__main__":
    main()
