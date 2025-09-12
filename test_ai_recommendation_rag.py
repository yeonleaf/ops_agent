#!/usr/bin/env python3
"""
AI 추천 시스템 RAG 통합 테스트
Multi-Vector + Cross-Encoder RAG 시스템이 제대로 작동하는지 확인
"""

import os
import sys
from typing import Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ticket_ai_recommender import TicketAIRecommender

def test_rag_integration():
    """RAG 통합 테스트"""
    print("🧪 AI 추천 시스템 RAG 통합 테스트")
    print("="*60)
    
    try:
        # AI 추천 시스템 초기화
        recommender = TicketAIRecommender()
        
        # RAG 시스템 상태 확인
        if recommender.multi_vector_rag:
            print("✅ Multi-Vector + Cross-Encoder RAG 시스템 활성화")
        else:
            print("❌ Multi-Vector RAG 시스템 비활성화")
            return
        
        # 테스트 쿼리들
        test_queries = [
            "서버 접속 문제",
            "데이터베이스 오류",
            "배치 작업 실패",
            "로그인 오류",
            "성능 최적화"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 테스트 {i}: '{query}'")
            print("-" * 40)
            
            # RAG 검색 테스트
            try:
                results = recommender.get_similar_tickets_with_rag(query, limit=3)
                
                if results:
                    print(f"✅ RAG 검색 성공: {len(results)}개 결과")
                    for j, result in enumerate(results, 1):
                        print(f"  {j}. 티켓: {result.get('ticket_id', 'N/A')}")
                        print(f"     점수: {result.get('similarity_score', 0.0):.4f}")
                        print(f"     Cross-Encoder: {result.get('cross_encoder_score', 0.0):.4f}")
                        print(f"     내용: {result.get('content', '')[:100]}...")
                        print()
                else:
                    print("⚠️ RAG 검색 결과 없음")
                    
            except Exception as e:
                print(f"❌ RAG 검색 실패: {str(e)}")
        
        # 통합 검색 테스트
        print(f"\n🔍 통합 검색 테스트: '서버 문제'")
        print("-" * 40)
        
        try:
            integrated_results = recommender.get_integrated_similar_content("서버 문제", email_limit=2, chunk_limit=1)
            
            if integrated_results:
                print(f"✅ 통합 검색 성공: {len(integrated_results)}개 결과")
                for j, result in enumerate(integrated_results, 1):
                    print(f"  {j}. 소스: {result.get('source', 'N/A')}")
                    print(f"     점수: {result.get('similarity_score', 0.0):.4f}")
                    print(f"     내용: {result.get('content', '')[:100]}...")
                    print()
            else:
                print("⚠️ 통합 검색 결과 없음")
                
        except Exception as e:
            print(f"❌ 통합 검색 실패: {str(e)}")
        
        print("\n🎉 RAG 통합 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_integration()

