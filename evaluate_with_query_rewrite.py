#!/usr/bin/env python3
"""
Query Rewrite 적용 RAG 평가 스크립트

glossary.csv 기반 Query Rewrite를 적용하여 RAG 성능을 평가합니다.
"""

import csv
import os
import sys
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rrf_fusion_rag_system import RRFRAGSystem, RRFConfig
from query_rewriter import DomainGlossary, QueryRewriter

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rag_evaluation_query_rewrite.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RAGEvaluatorWithRewrite:
    """Query Rewrite 적용 RAG 평가기"""

    def __init__(self, rag_system: RRFRAGSystem, query_rewriter: QueryRewriter,
                 rewrite_strategy: str = "synonyms"):
        """
        Args:
            rag_system: RAG 시스템
            query_rewriter: 쿼리 재작성기
            rewrite_strategy: 재작성 전략 (none, synonyms, context, hybrid)
        """
        self.rag_system = rag_system
        self.query_rewriter = query_rewriter
        self.rewrite_strategy = rewrite_strategy
        self.results = []

    def load_test_data(self, csv_path: str) -> List[Dict[str, str]]:
        """테스트 데이터 로드"""
        test_cases = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    test_cases.append({
                        'query': row['query'],
                        'answer_ticket_id': row['answer_ticket_id']
                    })
            logger.info(f"✅ 테스트 데이터 로드 완료: {len(test_cases)}개 케이스")
            return test_cases
        except Exception as e:
            logger.error(f"❌ 테스트 데이터 로드 실패: {e}")
            raise e

    def extract_ticket_id(self, metadata: Dict[str, Any]) -> str:
        """메타데이터에서 티켓 ID 추출"""
        possible_keys = ['ticket_id', 'ticket_key', 'jira_key', 'issue_key', 'key', 'id']
        for key in possible_keys:
            if key in metadata:
                ticket_id = metadata[key]
                if isinstance(ticket_id, str):
                    return ticket_id
        return None

    def find_answer_rank(self, search_results: List[Dict[str, Any]],
                        answer_ticket_id: str) -> Tuple[int, bool]:
        """검색 결과에서 정답의 순위 찾기"""
        for rank, result in enumerate(search_results, start=1):
            metadata = result.get('metadata', {})
            ticket_id = self.extract_ticket_id(metadata)
            if ticket_id and ticket_id == answer_ticket_id:
                return rank, True
        return -1, False

    def rewrite_query(self, query: str) -> str:
        """쿼리 재작성"""
        if self.rewrite_strategy == "none":
            return query
        elif self.rewrite_strategy == "synonyms":
            return self.query_rewriter.rewrite_with_synonyms(query)
        elif self.rewrite_strategy == "context":
            return self.query_rewriter.rewrite_with_context(query)
        elif self.rewrite_strategy == "hybrid":
            return self.query_rewriter.rewrite_hybrid(query)
        else:
            return query

    def evaluate_single_query(self, query: str, answer_ticket_id: str) -> Dict[str, Any]:
        """단일 쿼리 평가"""
        try:
            # 쿼리 재작성
            rewritten_query = self.rewrite_query(query)

            if rewritten_query != query:
                logger.info(f"🔄 쿼리 재작성:")
                logger.info(f"  원본: {query}")
                logger.info(f"  재작성: {rewritten_query}")

            logger.info(f"🔍 평가 중: '{query}' (정답: {answer_ticket_id})")

            # RAG 검색 실행
            search_results = self.rag_system.rrf_search(rewritten_query)

            if not search_results:
                logger.warning(f"⚠️ 검색 결과 없음: '{query}'")
                return {
                    'query': query,
                    'rewritten_query': rewritten_query,
                    'answer_ticket_id': answer_ticket_id,
                    'rank': -1,
                    'found': False,
                    'reciprocal_rank': 0.0,
                    'top_results': []
                }

            # 정답 순위 찾기
            rank, found = self.find_answer_rank(search_results, answer_ticket_id)

            # 상위 5개 결과
            top_results = []
            for i, result in enumerate(search_results[:5], start=1):
                metadata = result.get('metadata', {})
                ticket_id = self.extract_ticket_id(metadata)
                top_results.append({
                    'rank': i,
                    'ticket_id': ticket_id,
                    'score': result.get('score', 0.0),
                    'rrf_score': metadata.get('rrf_score', 0.0)
                })

            # Reciprocal Rank 계산
            reciprocal_rank = 1.0 / rank if found else 0.0

            result = {
                'query': query,
                'rewritten_query': rewritten_query,
                'answer_ticket_id': answer_ticket_id,
                'rank': rank,
                'found': found,
                'reciprocal_rank': reciprocal_rank,
                'top_results': top_results
            }

            if found:
                logger.info(f"✅ 정답 발견: 순위 {rank}")
            else:
                logger.warning(f"❌ 정답 미발견: {answer_ticket_id}")

            return result

        except Exception as e:
            logger.error(f"❌ 쿼리 평가 실패: {e}")
            return {
                'query': query,
                'rewritten_query': query,
                'answer_ticket_id': answer_ticket_id,
                'rank': -1,
                'found': False,
                'reciprocal_rank': 0.0,
                'error': str(e),
                'top_results': []
            }

    def evaluate_all(self, test_cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """모든 테스트 케이스 평가"""
        results = []
        logger.info(f"🚀 전체 평가 시작: {len(test_cases)}개 케이스")
        logger.info(f"📝 Query Rewrite 전략: {self.rewrite_strategy}")

        for i, test_case in enumerate(test_cases, start=1):
            logger.info(f"\n{'='*60}")
            logger.info(f"진행률: {i}/{len(test_cases)}")

            result = self.evaluate_single_query(
                test_case['query'],
                test_case['answer_ticket_id']
            )
            results.append(result)

        logger.info(f"\n{'='*60}")
        logger.info("✅ 전체 평가 완료")

        self.results = results
        return results

    def calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """평가 메트릭 계산"""
        total = len(results)
        if total == 0:
            return {}

        mrr = sum(r['reciprocal_rank'] for r in results) / total

        def hit_at_k(k: int) -> float:
            hits = sum(1 for r in results if r['found'] and r['rank'] <= k and r['rank'] > 0)
            return hits / total

        hit_at_1 = hit_at_k(1)
        hit_at_3 = hit_at_k(3)
        hit_at_5 = hit_at_k(5)
        hit_at_10 = hit_at_k(10)

        found_rate = sum(1 for r in results if r['found']) / total
        found_results = [r for r in results if r['found']]
        avg_rank = sum(r['rank'] for r in found_results) / len(found_results) if found_results else 0.0

        metrics = {
            'total_queries': total,
            'mrr': mrr,
            'hit@1': hit_at_1,
            'hit@3': hit_at_3,
            'hit@5': hit_at_5,
            'hit@10': hit_at_10,
            'top1_accuracy': hit_at_1,
            'found_rate': found_rate,
            'avg_rank': avg_rank,
            'found_count': len(found_results)
        }

        return metrics

    def print_metrics(self, metrics: Dict[str, float], title: str = "평가 결과"):
        """메트릭 출력"""
        print("\n" + "="*60)
        print(f"📊 {title}")
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
                    output_path: str, config_info: Dict[str, Any]):
        """평가 결과 저장"""
        try:
            output_data = {
                'timestamp': datetime.now().isoformat(),
                'config': config_info,
                'metrics': metrics,
                'results': results
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 평가 결과 저장: {output_path}")

        except Exception as e:
            logger.error(f"❌ 결과 저장 실패: {e}")


def compare_rewrite_strategies():
    """여러 Query Rewrite 전략 비교"""
    try:
        os.makedirs('logs', exist_ok=True)

        # Query Rewriter 초기화
        glossary = DomainGlossary("glossary.csv")
        query_rewriter = QueryRewriter(glossary)

        strategies = ['none', 'synonyms', 'context', 'hybrid']
        all_results = {}

        for strategy in strategies:
            logger.info(f"\n{'#'*80}")
            logger.info(f"# Query Rewrite 전략: {strategy}")
            logger.info(f"{'#'*80}\n")

            # RAG 시스템 초기화
            rrf_config = RRFConfig(
                deduplicate_tickets=True,
                deduplication_strategy='all_scores'
            )
            rag_system = RRFRAGSystem("jira_chunks", rrf_config)

            # 평가기 초기화
            evaluator = RAGEvaluatorWithRewrite(rag_system, query_rewriter, strategy)

            # 테스트 데이터 로드
            test_cases = evaluator.load_test_data("test_data.csv")

            # 평가 실행
            results = evaluator.evaluate_all(test_cases)

            # 메트릭 계산
            metrics = evaluator.calculate_metrics(results)

            # 결과 출력
            evaluator.print_metrics(metrics, title=f"평가 결과 (전략: {strategy})")

            # 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"rag_evaluation_rewrite_{strategy}_{timestamp}.json"
            config_info = {
                'rewrite_strategy': strategy,
                'deduplicate_tickets': True,
                'deduplication_strategy': 'all_scores'
            }
            evaluator.save_results(results, metrics, output_path, config_info)

            all_results[strategy] = metrics

        # 전략 비교 출력
        print("\n" + "="*80)
        print("📊 Query Rewrite 전략 비교")
        print("="*80)
        print(f"{'전략':<15} {'MRR':<10} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'Hit@10':<10} {'발견율':<10}")
        print("-"*80)
        for strategy, metrics in all_results.items():
            print(f"{strategy:<15} {metrics['mrr']:<10.4f} {metrics['hit@1']:<10.2%} {metrics['hit@3']:<10.2%} "
                  f"{metrics['hit@5']:<10.2%} {metrics['hit@10']:<10.2%} {metrics['found_rate']:<10.2%}")
        print("="*80)

        # 최고 성능 전략
        best_strategy = max(all_results.items(), key=lambda x: x[1]['mrr'])
        print(f"\n🏆 최고 성능 전략: {best_strategy[0]} (MRR: {best_strategy[1]['mrr']:.4f})")

        # 개선율 계산
        baseline_mrr = all_results['none']['mrr']
        for strategy, metrics in all_results.items():
            if strategy != 'none':
                improvement = (metrics['mrr'] - baseline_mrr) / baseline_mrr * 100
                print(f"  {strategy}: MRR {metrics['mrr']:.4f} ({improvement:+.1f}%)")

        logger.info("✅ 전체 비교 완료")

    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        raise e


if __name__ == "__main__":
    compare_rewrite_strategies()
