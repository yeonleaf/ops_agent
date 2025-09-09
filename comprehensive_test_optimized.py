#!/usr/bin/env python3
"""
메모리 최적화된 포괄적 RAG 시스템 테스트
MPS 메모리 부족 문제를 해결하기 위해 강력한 메모리 관리 전략을 적용
"""

import os
import sys
import gc
import torch
import json
from datetime import datetime
from typing import Dict, List, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# RAG 관련 모듈들 import
from multi_vector_cross_encoder_rag import MultiVectorCrossEncoderRAG

# ==================== 포괄적 테스트 케이스 정의 ====================

# 1. 정답이 없는 질문 테스트 (Zero-shot & Negative Test)
NEGATIVE_TEST_QUESTIONS = [
    "화성 탐사선 관련 티켓이 있나요?",
    "인공지능 로봇 개발 프로젝트는 어떻게 진행되고 있나요?",
    "블록체인 기술을 활용한 결제 시스템은 언제 출시되나요?",
    "우주 정거장 건설 계획에 대한 최신 상황을 알려주세요",
    "양자컴퓨팅 연구 프로젝트의 진행 상황은 어떤가요?"
]

# 2. 다양성 및 난이도 테스트 질문 (간소화)
DIVERSITY_TEST_QUESTIONS = [
    # 요약형 질문
    "서버 관련 모든 이슈를 요약해서 알려주세요",
    "데이터베이스 문제들의 공통점과 해결 방안을 정리해주세요",
    
    # 비교/대조형 질문
    "서버 접속 문제와 DB 연결 문제의 차이점은 무엇인가요?",
    "STG 환경과 PROD 환경에서 발생한 이슈들을 비교해주세요",
    
    # 시간순 질문
    "가장 최근에 처리된 보안 관련 티켓은 무엇인가요?",
    "이번 주에 발생한 모든 이슈를 시간순으로 정리해주세요"
]

# 3. 스트레스 테스트 질문 (간소화)
STRESS_TEST_QUESTIONS = [
    # 중의적 표현
    "배포가 '안 된' 이슈 좀 찾아줘",
    "서버가 '안 되는' 문제가 있나요?",
    
    # 오타 포함
    "서버 '졉속'이 안돼",
    "데이터베이스 '연결' 오류가 발생했어요",
    
    # 매우 짧은 질문
    "서버",
    "DB",
    "배치"
]

# ==================== 메모리 관리 클래스 ====================

class MemoryManager:
    """강력한 메모리 관리 클래스"""
    
    @staticmethod
    def cleanup_memory():
        """포괄적인 메모리 정리"""
        try:
            # Python 가비지 컬렉션
            gc.collect()
            
            # PyTorch 캐시 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
                torch.mps.synchronize()
            
            # 추가 가비지 컬렉션
            gc.collect()
            
            print("🧹 메모리 정리 완료")
        except Exception as e:
            print(f"⚠️ 메모리 정리 중 오류: {e}")
    
    @staticmethod
    def force_cleanup():
        """강제 메모리 정리 (더 적극적)"""
        try:
            # 여러 번 가비지 컬렉션
            for _ in range(3):
                gc.collect()
            
            # PyTorch 캐시 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
                torch.mps.synchronize()
            
            # 최종 가비지 컬렉션
            gc.collect()
            
            print("🧹 강제 메모리 정리 완료")
        except Exception as e:
            print(f"⚠️ 강제 메모리 정리 중 오류: {e}")

# ==================== 메모리 최적화된 RAG 검색 함수 ====================

def search_rag_with_memory_management(query: str) -> List[Dict[str, Any]]:
    """
    메모리 관리를 포함한 RAG 검색 함수
    각 검색 후 메모리를 정리하여 누적을 방지
    """
    rag = None
    try:
        print(f"🔍 RAG 검색 시작: '{query}'")
        
        # RAG 시스템 초기화
        rag = MultiVectorCrossEncoderRAG()
        
        # 검색 실행
        similar_content = rag.search(
            query=query,
            n_candidates=30,  # 후보 수 줄임
            top_k=5  # 결과 수 줄임
        )
        
        # 결과 처리
        results = []
        for i, content in enumerate(similar_content):
            result = {
                "id": f"result_{i+1}",
                "content": content.get('text', 'No content'),
                "score": content.get('score', 0.0)
            }
            results.append(result)
        
        print(f"✅ RAG 검색 완료: {len(results)}개 결과")
        return results
        
    except Exception as e:
        print(f"❌ RAG 검색 실패: {e}")
        return []
    finally:
        # RAG 객체 정리
        if rag:
            del rag
        
        # 메모리 정리
        MemoryManager.cleanup_memory()

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
        search_results = search_rag_with_memory_management(question)
        
        # 결과 분석
        if not search_results:
            print("✅ 올바른 응답: 관련 정보를 찾을 수 없습니다")
            result_status = "CORRECT_NO_RESULTS"
            max_score = 0.0
        else:
            # 결과가 있지만 관련성이 낮은지 확인
            max_score = max([r.get('score', 0) for r in search_results]) if search_results else 0
            if max_score < 0.3:  # 임계값 설정
                print(f"✅ 올바른 응답: 관련성이 낮은 결과 (최고 점수: {max_score:.3f})")
                result_status = "CORRECT_LOW_RELEVANCE"
            else:
                print(f"⚠️ 의심스러운 응답: 관련성 있는 결과 반환 (최고 점수: {max_score:.3f})")
                result_status = "SUSPICIOUS_HIGH_RELEVANCE"
                
                # 상위 2개 결과만 출력
                for j, result in enumerate(search_results[:2], 1):
                    print(f"  {j}. {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
                    print(f"     {result.get('content', 'No content')[:80]}...")
        
        results.append({
            'question': question,
            'status': result_status,
            'result_count': len(search_results),
            'max_score': max_score
        })
        
        # 각 테스트 후 강제 메모리 정리
        MemoryManager.force_cleanup()
    
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
        search_results = search_rag_with_memory_management(question)
        
        if search_results:
            print(f"✅ {len(search_results)}개 결과 반환")
            max_score = max([r.get('score', 0) for r in search_results])
            print(f"   최고 점수: {max_score:.3f}")
            
            # 상위 2개 결과만 출력
            for j, result in enumerate(search_results[:2], 1):
                print(f"  {j}. {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
                print(f"     {result.get('content', 'No content')[:80]}...")
        else:
            print("❌ 결과 없음")
        
        results.append({
            'question': question,
            'result_count': len(search_results),
            'max_score': max([r.get('score', 0) for r in search_results]) if search_results else 0
        })
        
        # 각 테스트 후 강제 메모리 정리
        MemoryManager.force_cleanup()
    
    return results

def run_stress_test():
    """스트레스 테스트 (중의적 표현, 오타, 길이 변형)"""
    print("\n" + "="*80)
    print("💪 스트레스 테스트 (중의적 표현, 오타, 길이 변형)")
    print("="*80)
    
    results = []
    for i, question in enumerate(STRESS_TEST_QUESTIONS, 1):
        print(f"\n📝 테스트 {i}: {question[:30]}{'...' if len(question) > 30 else ''}")
        print("-" * 60)
        
        # RAG 검색 실행
        search_results = search_rag_with_memory_management(question)
        
        if search_results:
            print(f"✅ {len(search_results)}개 결과 반환")
            max_score = max([r.get('score', 0) for r in search_results])
            print(f"   최고 점수: {max_score:.3f}")
            
            # 상위 1개 결과만 간단히 출력
            if search_results:
                result = search_results[0]
                print(f"  {result.get('id', 'Unknown')} (점수: {result.get('score', 0):.3f})")
        else:
            print("❌ 결과 없음")
        
        results.append({
            'question': question,
            'result_count': len(search_results),
            'max_score': max([r.get('score', 0) for r in search_results]) if search_results else 0
        })
        
        # 각 테스트 후 강제 메모리 정리
        MemoryManager.force_cleanup()
    
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

# ==================== 메인 실행 함수 ====================

def main():
    """메모리 최적화된 포괄적 테스트 실행"""
    print("🚀 메모리 최적화된 포괄적 RAG 시스템 테스트 시작")
    print("="*80)
    
    try:
        # 초기 메모리 정리
        MemoryManager.force_cleanup()
        
        # 1. 정답이 없는 질문 테스트
        print("\n🔍 1단계: 정답이 없는 질문 테스트")
        negative_results = run_negative_test()
        
        # 중간 메모리 정리
        MemoryManager.force_cleanup()
        
        # 2. 다양성 및 난이도 테스트
        print("\n🎯 2단계: 다양성 및 난이도 테스트")
        diversity_results = run_diversity_test()
        
        # 중간 메모리 정리
        MemoryManager.force_cleanup()
        
        # 3. 스트레스 테스트
        print("\n💪 3단계: 스트레스 테스트")
        stress_results = run_stress_test()
        
        # 4. 결과 종합 분석
        analyze_test_results(negative_results, diversity_results, stress_results)
        
        # 5. 결과를 JSON 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"comprehensive_test_results_optimized_{timestamp}.json"
        
        comprehensive_results = {
            'timestamp': timestamp,
            'test_type': 'memory_optimized',
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
        print("🎉 메모리 최적화된 포괄적 RAG 시스템 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {e}")
        # 최종 메모리 정리
        MemoryManager.force_cleanup()
        raise e
    finally:
        # 최종 메모리 정리
        MemoryManager.force_cleanup()

if __name__ == "__main__":
    main()
