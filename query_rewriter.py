#!/usr/bin/env python3
"""
Query Rewriter - 도메인 용어 사전 기반 쿼리 재작성

glossary.csv를 활용하여 쿼리의 도메인 용어를 확장하고 개선합니다.
"""

import csv
import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DomainGlossary:
    """도메인 용어 사전"""

    def __init__(self, glossary_path: str = "glossary.csv"):
        """
        도메인 용어 사전 초기화

        Args:
            glossary_path: glossary.csv 파일 경로
        """
        self.glossary_path = glossary_path
        self.terms = {}  # {term: {type, synonyms, expand_to}}
        self.load_glossary()

    def load_glossary(self):
        """glossary.csv 로드"""
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    term = row['term'].strip()
                    if not term:
                        continue

                    # 동의어 파싱 (쉼표로 구분)
                    synonyms = [s.strip() for s in row['synonyms'].split(',') if s.strip()]

                    self.terms[term] = {
                        'type': row['type'].strip(),
                        'synonyms': synonyms,
                        'expand_to': row['expand_to'].strip()
                    }

            logger.info(f"✅ 도메인 용어 사전 로드 완료: {len(self.terms)}개 용어")

        except Exception as e:
            logger.error(f"❌ 도메인 용어 사전 로드 실패: {e}")
            self.terms = {}

    def find_terms_in_query(self, query: str) -> List[Dict[str, Any]]:
        """
        쿼리에서 도메인 용어 찾기 (한국어 조사 고려)

        Args:
            query: 검색 쿼리

        Returns:
            발견된 용어 리스트 [{term, type, synonyms, expand_to, position}, ...]
        """
        found_terms = []

        for term, info in self.terms.items():
            # 원본 용어와 동의어 모두 검색
            search_terms = [term] + info['synonyms']

            for search_term in search_terms:
                # 한국어는 단어 경계가 명확하지 않으므로
                # 앞뒤에 공백/문장부호/시작/끝이 있는지만 확인
                # 또는 한국어 조사(은/는/이/가/을/를/에/에서/로/와/과)가 붙을 수 있음
                pattern = re.compile(
                    r'(?:^|[\s\(])' +  # 시작 또는 공백/괄호
                    re.escape(search_term) +
                    r'(?:[\s\)\?,\.!]|은|는|이|가|을|를|에|에서|로|와|과|의|도|만|$)',  # 끝 또는 조사
                    re.IGNORECASE
                )

                matches = pattern.finditer(query)

                for match in matches:
                    # 실제 매칭된 용어만 추출 (조사 제외)
                    matched_text = match.group().strip()
                    # 조사 제거
                    for josa in ['은', '는', '이', '가', '을', '를', '에', '에서', '로', '와', '과', '의', '도', '만']:
                        if matched_text.endswith(josa):
                            matched_text = matched_text[:-len(josa)]
                            break

                    found_terms.append({
                        'term': term,  # 원본 용어 (glossary의 키)
                        'matched_text': matched_text.strip(),
                        'position': match.start(),
                        'type': info['type'],
                        'synonyms': info['synonyms'],
                        'expand_to': info['expand_to']
                    })

        # 위치 순으로 정렬, 중복 제거
        seen = set()
        unique_terms = []
        for ft in sorted(found_terms, key=lambda x: x['position']):
            key = (ft['position'], ft['term'])
            if key not in seen:
                unique_terms.append(ft)
                seen.add(key)

        return unique_terms


class QueryRewriter:
    """쿼리 재작성기"""

    def __init__(self, glossary: DomainGlossary):
        """
        쿼리 재작성기 초기화

        Args:
            glossary: 도메인 용어 사전
        """
        self.glossary = glossary

    def rewrite_with_synonyms(self, query: str) -> str:
        """
        동의어 추가 방식 (Strategy 1)

        예: "EUXP 오류" → "EUXP 전시시스템 전시편성시스템 오류"

        Args:
            query: 원본 쿼리

        Returns:
            동의어가 추가된 쿼리
        """
        found_terms = self.glossary.find_terms_in_query(query)

        if not found_terms:
            return query

        # 각 용어에 동의어 추가
        result = query
        offset = 0

        for term_info in found_terms:
            term = term_info['matched_text']
            position = term_info['position'] + offset
            synonyms = term_info['synonyms']

            if synonyms:
                # "EUXP" → "EUXP 전시시스템 전시편성시스템"
                expanded = f"{term} {' '.join(synonyms)}"
                result = result[:position] + expanded + result[position + len(term):]
                offset += len(expanded) - len(term)

        logger.debug(f"동의어 확장: '{query}' → '{result}'")
        return result

    def rewrite_with_context(self, query: str) -> str:
        """
        맥락 추가 방식 (Strategy 2)

        예: "EUXP 오류" → "EUXP 오류 (EUXP는 B tv 전시/편성 시스템이다)"

        Args:
            query: 원본 쿼리

        Returns:
            맥락이 추가된 쿼리
        """
        found_terms = self.glossary.find_terms_in_query(query)

        if not found_terms:
            return query

        # 맥락 추가
        contexts = []
        for term_info in found_terms:
            expand_to = term_info['expand_to']
            if expand_to:
                contexts.append(expand_to)

        if contexts:
            result = f"{query} ({' '.join(contexts)})"
            logger.debug(f"맥락 추가: '{query}' → '{result}'")
            return result

        return query

    def rewrite_hybrid(self, query: str) -> str:
        """
        하이브리드 방식 (Strategy 3)

        동의어와 맥락을 모두 활용

        Args:
            query: 원본 쿼리

        Returns:
            확장된 쿼리
        """
        # 1단계: 동의어 추가
        with_synonyms = self.rewrite_with_synonyms(query)

        # 2단계: 맥락 추가
        found_terms = self.glossary.find_terms_in_query(query)

        if not found_terms:
            return with_synonyms

        contexts = []
        for term_info in found_terms:
            expand_to = term_info['expand_to']
            if expand_to:
                contexts.append(expand_to)

        if contexts:
            result = f"{with_synonyms} ({' '.join(contexts)})"
            logger.debug(f"하이브리드 확장: '{query}' → '{result}'")
            return result

        return with_synonyms

    def generate_variants(self, query: str, strategy: str = "synonyms") -> List[str]:
        """
        쿼리 변형 생성 (Multi-Query에 활용)

        Args:
            query: 원본 쿼리
            strategy: 재작성 전략 (synonyms, context, hybrid, all)

        Returns:
            쿼리 변형 리스트 (원본 포함)
        """
        variants = [query]  # 원본 항상 포함

        if strategy == "synonyms":
            variants.append(self.rewrite_with_synonyms(query))
        elif strategy == "context":
            variants.append(self.rewrite_with_context(query))
        elif strategy == "hybrid":
            variants.append(self.rewrite_hybrid(query))
        elif strategy == "all":
            variants.append(self.rewrite_with_synonyms(query))
            variants.append(self.rewrite_with_context(query))
            variants.append(self.rewrite_hybrid(query))

        # 중복 제거
        unique_variants = []
        seen = set()
        for v in variants:
            if v not in seen:
                unique_variants.append(v)
                seen.add(v)

        logger.info(f"쿼리 변형 생성: {len(unique_variants)}개 (전략: {strategy})")
        for i, v in enumerate(unique_variants):
            logger.debug(f"  {i+1}. {v}")

        return unique_variants


def test_query_rewriter():
    """Query Rewriter 테스트"""
    print("\n" + "="*80)
    print("🔧 Query Rewriter 테스트")
    print("="*80 + "\n")

    # Glossary 로드
    glossary = DomainGlossary("glossary.csv")

    # Rewriter 초기화
    rewriter = QueryRewriter(glossary)

    # 테스트 쿼리
    test_queries = [
        "EUXP에서 발생한 오류로 확인 문의가 들어온 적이 있어?",
        "PrePRD 환경에서 인프라 문제로 앱이 다운된 적이 있어?",
        "sequence number가 맞지 않을 때 우리 시스템에서는 어떤 조치를 했지?",
        "이미지 다운로드를 할 때 오류가 발생한 케이스를 찾아줘",
        "큐 발송에 이상이 생겨서 상용 배치가 종료되지 않은 적이 있어?",
    ]

    for query in test_queries:
        print(f"\n{'─'*80}")
        print(f"📝 원본 쿼리:")
        print(f"  {query}\n")

        # Strategy 1: Synonyms
        with_synonyms = rewriter.rewrite_with_synonyms(query)
        print(f"📌 Strategy 1 (동의어):")
        print(f"  {with_synonyms}\n")

        # Strategy 2: Context
        with_context = rewriter.rewrite_with_context(query)
        print(f"📌 Strategy 2 (맥락):")
        print(f"  {with_context}\n")

        # Strategy 3: Hybrid
        hybrid = rewriter.rewrite_hybrid(query)
        print(f"📌 Strategy 3 (하이브리드):")
        print(f"  {hybrid}\n")

    print("="*80)
    print("✅ 테스트 완료\n")


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )

    test_query_rewriter()
