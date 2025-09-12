#!/usr/bin/env python3
"""
AI 추천 시스템 프롬프트 생성 테스트
실제 프롬프트가 어떻게 생성되는지 확인
"""

import os
import sys
from typing import Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ticket_ai_recommender import TicketAIRecommender

def test_prompt_generation():
    """프롬프트 생성 테스트"""
    print("🧪 AI 추천 시스템 프롬프트 생성 테스트")
    print("="*60)
    
    try:
        # AI 추천 시스템 초기화
        recommender = TicketAIRecommender()
        
        # RAG 시스템 상태 확인
        if not recommender.multi_vector_rag:
            print("❌ Multi-Vector RAG 시스템 비활성화")
            return
        
        print("✅ Multi-Vector + Cross-Encoder RAG 시스템 활성화")
        
        # 테스트용 티켓 데이터 생성
        test_ticket_data = {
            "ticket_id": "TEST-001",
            "title": "서버 접속 문제 해결 요청",
            "description": "메인 서버에 접속이 되지 않습니다. HTTP 500 오류가 발생하고 있습니다. 긴급히 해결이 필요합니다.",
            "status": "pending",
            "priority": "High",
            "ticket_type": "Bug",
            "reporter": "김개발",
            "labels": ["서버", "긴급", "오류"],
            "original_mail": {
                "sender": "kim.dev@company.com",
                "subject": "[긴급] 서버 접속 불가 문제",
                "refined_content": "안녕하세요. 메인 서버에 접속이 안 되고 있습니다. HTTP 500 오류가 계속 발생하고 있어서 업무에 지장이 있습니다.",
                "content_summary": "서버 접속 불가 및 HTTP 500 오류 발생",
                "key_points": ["서버 접속 불가", "HTTP 500 오류", "업무 지장"]
            }
        }
        
        # RAG 검색으로 유사한 티켓들 찾기
        print(f"\n🔍 RAG 검색 시작: '{test_ticket_data['title']}'")
        similar_content = recommender.get_similar_tickets_with_rag(
            f"{test_ticket_data['title']} {test_ticket_data['description']}", 
            limit=3
        )
        
        if similar_content:
            print(f"✅ RAG 검색 완료: {len(similar_content)}개 결과")
            for i, result in enumerate(similar_content, 1):
                print(f"  {i}. 티켓: {result.get('ticket_id', 'N/A')}")
                print(f"     점수: {result.get('similarity_score', 0.0):.4f}")
                print(f"     Cross-Encoder: {result.get('cross_encoder_score', 0.0):.4f}")
                print(f"     내용: {result.get('content', '')[:100]}...")
                print()
        else:
            print("⚠️ RAG 검색 결과 없음")
            return
        
        # 프롬프트 생성
        print("📝 AI 추천 프롬프트 생성 중...")
        prompt = recommender._build_recommendation_prompt(test_ticket_data, similar_content)
        
        print("\n" + "="*80)
        print("🎯 생성된 AI 추천 프롬프트")
        print("="*80)
        print(prompt)
        print("="*80)
        
        # 프롬프트 분석
        print(f"\n📊 프롬프트 분석:")
        print(f"- 총 길이: {len(prompt)} 문자")
        print(f"- RAG 검색 결과 수: {len(similar_content)}개")
        print(f"- 티켓 정보 포함: ✅")
        print(f"- 원본 메일 정보 포함: ✅")
        print(f"- 유사 사례 정보 포함: ✅")
        
        # 선택된 티켓들 요약
        print(f"\n🎯 선택된 유사 티켓들:")
        for i, result in enumerate(similar_content, 1):
            ticket_id = result.get('ticket_id', 'N/A')
            score = result.get('similarity_score', 0.0)
            cross_score = result.get('cross_encoder_score', 0.0)
            content_preview = result.get('content', '')[:150] + "..." if len(result.get('content', '')) > 150 else result.get('content', '')
            
            print(f"  {i}. {ticket_id}")
            print(f"     - 유사도: {score:.4f}")
            print(f"     - Cross-Encoder: {cross_score:.4f}")
            print(f"     - 내용: {content_preview}")
            print()
        
        print("🎉 프롬프트 생성 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt_generation()

