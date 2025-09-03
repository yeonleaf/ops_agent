#!/usr/bin/env python3
"""
Mem0Memory 어댑터 클래스

mem0 라이브러리를 사용하여 AI 에이전트의 메모리 시스템을 단순화하는 어댑터
기존의 복잡한 Vector DB + RDB 조회 로직을 mem0의 단순한 API로 교체
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("⚠️ mem0 라이브러리가 설치되지 않았습니다. pip install mem0ai 명령으로 설치해주세요.")

class DummyMemory:
    """테스트용 더미 메모리 클래스"""
    
    def __init__(self):
        self.memories = []
        self.memory_id_counter = 1
    
    def add(self, messages, user_id=None, metadata=None):
        """더미 메모리 추가"""
        memory_id = f"dummy_{self.memory_id_counter}"
        self.memory_id_counter += 1
        
        # 메모리 저장
        memory_data = {
            "id": memory_id,
            "memory": messages[0]["content"] if messages else "",
            "metadata": metadata or {},
            "user_id": user_id,
            "created_at": datetime.now().isoformat()
        }
        self.memories.append(memory_data)
        
        return {"id": memory_id}
    
    def search(self, query, user_id=None, limit=5):
        """더미 메모리 검색"""
        # 간단한 키워드 매칭으로 검색
        results = []
        query_lower = query.lower()
        
        for memory in self.memories:
            if memory["user_id"] == user_id or user_id is None:
                memory_text = memory["memory"].lower()
                if any(word in memory_text for word in query_lower.split()):
                    results.append({
                        "memory": memory["memory"],
                        "score": 0.8,  # 더미 점수
                        "metadata": memory["metadata"],
                        "id": memory["id"]
                    })
        
        # 점수순으로 정렬하고 limit만큼 반환
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:limit]}
    
    def get_all(self, user_id=None, limit=100):
        """더미 메모리 전체 조회"""
        filtered_memories = []
        for memory in self.memories:
            if memory["user_id"] == user_id or user_id is None:
                filtered_memories.append({
                    "memory": memory["memory"],
                    "metadata": memory["metadata"],
                    "id": memory["id"],
                    "created_at": memory["created_at"]
                })
        
        return {"results": filtered_memories[:limit]}
    
    def delete(self, memory_id, user_id=None):
        """더미 메모리 삭제"""
        for i, memory in enumerate(self.memories):
            if memory["id"] == memory_id and (memory["user_id"] == user_id or user_id is None):
                del self.memories[i]
                return {"success": True}
        return {"success": False}

class Mem0Memory:
    """mem0 라이브러리를 사용한 메모리 어댑터 클래스"""
    
    def __init__(self, user_id: str = "default_user"):
        """
        Mem0Memory 초기화
        
        Args:
            user_id: 사용자 ID (기본값: "default_user")
        """
        if not MEM0_AVAILABLE:
            raise ImportError("mem0 라이브러리가 설치되지 않았습니다. pip install mem0ai 명령으로 설치해주세요.")
        
        self.user_id = user_id
        self.memory = None
        self._initialize_memory()
    
    def _initialize_memory(self):
        """mem0 클라이언트 초기화"""
        try:
            # Azure OpenAI 설정 (기존 시스템과 동일한 설정 사용)
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
            
            if not all([azure_endpoint, deployment_name, api_key]):
                print("⚠️ Azure OpenAI 환경 변수가 설정되지 않았습니다. 기본 LLM을 사용합니다.")
                # 기본 LLM 사용 (OpenAI GPT-4o-mini)
                self.memory = Memory()
            else:
                # Azure OpenAI 사용 - mem0의 올바른 설정 방법
                self.memory = Memory(
                    config={
                        "llm": {
                            "provider": "azure_openai",
                            "config": {
                                "azure_endpoint": azure_endpoint,
                                "api_key": api_key,
                                "api_version": api_version,
                                "deployment_name": deployment_name,
                                "temperature": 0.3
                            }
                        }
                    }
                )
            
            print(f"✅ Mem0Memory 초기화 완료 (사용자: {self.user_id})")
            
        except Exception as e:
            print(f"❌ Mem0Memory 초기화 실패: {e}")
            # 폴백: 기본 설정으로 초기화
            try:
                # OpenAI API 키가 있는지 확인
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if openai_api_key:
                    self.memory = Memory()
                    print("✅ Mem0Memory 기본 설정으로 초기화 완료")
                else:
                    # 테스트용 더미 메모리 클래스 생성
                    self.memory = DummyMemory()
                    print("⚠️ Mem0Memory 더미 모드로 초기화 (테스트용)")
            except Exception as fallback_error:
                print(f"❌ Mem0Memory 기본 초기화도 실패: {fallback_error}")
                # 최종 폴백: 더미 메모리
                self.memory = DummyMemory()
                print("⚠️ Mem0Memory 더미 모드로 초기화 (최종 폴백)")
    
    def add(self, event_text: str, metadata: Dict[str, Any] = None) -> str:
        """
        새로운 이벤트를 메모리에 추가
        
        Args:
            event_text: 이벤트 설명 텍스트 (예: "사용자가 티켓 #123의 라벨을 '버그'로 수정함")
            metadata: 추가 메타데이터 (티켓 ID, 메일 ID, 액션 타입 등)
            
        Returns:
            생성된 메모리 ID
        """
        try:
            if not self.memory:
                raise RuntimeError("Mem0Memory가 초기화되지 않았습니다.")
            
            # 메타데이터 준비
            memory_metadata = metadata or {}
            memory_metadata.update({
                "timestamp": datetime.now().isoformat(),
                "user_id": self.user_id
            })
            
            # mem0에 메모리 추가
            result = self.memory.add(
                messages=[{"role": "user", "content": event_text}],
                user_id=self.user_id,
                metadata=memory_metadata
            )
            
            # 결과에서 메모리 ID 추출
            memory_id = result.get("id", "unknown")
            
            print(f"✅ 메모리 추가 완료: {memory_id}")
            print(f"   이벤트: {event_text}")
            print(f"   메타데이터: {memory_metadata}")
            
            return memory_id
            
        except Exception as e:
            print(f"❌ 메모리 추가 실패: {e}")
            print(f"   이벤트: {event_text}")
            print(f"   메타데이터: {metadata}")
            raise e
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리와 관련된 과거 이벤트를 검색
        
        Args:
            query: 검색 쿼리 (예: 새 이메일의 내용)
            limit: 반환할 최대 결과 수
            
        Returns:
            관련된 과거 이벤트 목록
        """
        try:
            if not self.memory:
                raise RuntimeError("Mem0Memory가 초기화되지 않았습니다.")
            
            # mem0에서 관련 메모리 검색
            results = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit
            )
            
            # 결과를 표준화된 형식으로 변환
            formatted_results = []
            for result in results.get("results", []):
                formatted_result = {
                    "memory": result.get("memory", ""),
                    "score": result.get("score", 0.0),
                    "metadata": result.get("metadata", {}),
                    "id": result.get("id", "unknown")
                }
                formatted_results.append(formatted_result)
            
            print(f"✅ 메모리 검색 완료: {len(formatted_results)}개 결과")
            print(f"   쿼리: {query[:100]}...")
            print(f"   결과 수: {len(formatted_results)}")
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ 메모리 검색 실패: {e}")
            print(f"   쿼리: {query[:100]}...")
            return []
    
    def get_all_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        모든 메모리를 조회 (디버깅용)
        
        Args:
            limit: 반환할 최대 결과 수
            
        Returns:
            모든 메모리 목록
        """
        try:
            if not self.memory:
                raise RuntimeError("Mem0Memory가 초기화되지 않았습니다.")
            
            # mem0에서 모든 메모리 조회
            results = self.memory.get_all(user_id=self.user_id, limit=limit)
            
            # 결과를 표준화된 형식으로 변환
            formatted_results = []
            for result in results.get("results", []):
                formatted_result = {
                    "memory": result.get("memory", ""),
                    "metadata": result.get("metadata", {}),
                    "id": result.get("id", "unknown"),
                    "created_at": result.get("created_at", "")
                }
                formatted_results.append(formatted_result)
            
            print(f"✅ 전체 메모리 조회 완료: {len(formatted_results)}개")
            return formatted_results
            
        except Exception as e:
            print(f"❌ 전체 메모리 조회 실패: {e}")
            return []
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        특정 메모리 삭제
        
        Args:
            memory_id: 삭제할 메모리 ID
            
        Returns:
            삭제 성공 여부
        """
        try:
            if not self.memory:
                raise RuntimeError("Mem0Memory가 초기화되지 않았습니다.")
            
            # mem0에서 메모리 삭제
            result = self.memory.delete(memory_id=memory_id, user_id=self.user_id)
            
            success = result.get("success", False)
            if success:
                print(f"✅ 메모리 삭제 완료: {memory_id}")
            else:
                print(f"❌ 메모리 삭제 실패: {memory_id}")
            
            return success
            
        except Exception as e:
            print(f"❌ 메모리 삭제 실패: {e}")
            return False
    
    def clear_all_memories(self) -> bool:
        """
        모든 메모리 삭제 (주의: 모든 데이터가 삭제됩니다)
        
        Returns:
            삭제 성공 여부
        """
        try:
            if not self.memory:
                raise RuntimeError("Mem0Memory가 초기화되지 않았습니다.")
            
            # 모든 메모리 조회 후 삭제
            all_memories = self.get_all_memories()
            deleted_count = 0
            
            for memory in all_memories:
                memory_id = memory.get("id")
                if memory_id and self.delete_memory(memory_id):
                    deleted_count += 1
            
            print(f"✅ 전체 메모리 삭제 완료: {deleted_count}개 삭제")
            return True
            
        except Exception as e:
            print(f"❌ 전체 메모리 삭제 실패: {e}")
            return False
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        메모리 통계 정보 반환
        
        Returns:
            메모리 통계 딕셔너리
        """
        try:
            all_memories = self.get_all_memories()
            
            # 메타데이터별 통계 계산
            action_types = {}
            ticket_ids = set()
            message_ids = set()
            
            for memory in all_memories:
                metadata = memory.get("metadata", {})
                
                # 액션 타입별 개수
                action_type = metadata.get("action_type", "unknown")
                action_types[action_type] = action_types.get(action_type, 0) + 1
                
                # 티켓 ID 수집
                ticket_id = metadata.get("ticket_id")
                if ticket_id:
                    ticket_ids.add(ticket_id)
                
                # 메일 ID 수집
                message_id = metadata.get("message_id")
                if message_id:
                    message_ids.add(message_id)
            
            stats = {
                "total_memories": len(all_memories),
                "action_types": action_types,
                "unique_tickets": len(ticket_ids),
                "unique_messages": len(message_ids),
                "user_id": self.user_id
            }
            
            print(f"✅ 메모리 통계: {stats}")
            return stats
            
        except Exception as e:
            print(f"❌ 메모리 통계 조회 실패: {e}")
            return {"error": str(e)}


# 편의 함수들
def create_mem0_memory(user_id: str = "default_user") -> Mem0Memory:
    """Mem0Memory 인스턴스 생성 헬퍼 함수"""
    return Mem0Memory(user_id=user_id)


def add_ticket_event(memory: Mem0Memory, event_type: str, description: str, 
                    ticket_id: str = None, message_id: str = None, 
                    old_value: str = None, new_value: str = None, 
                    user_id: str = None) -> str:
    """
    티켓 관련 이벤트를 메모리에 추가하는 편의 함수
    
    Args:
        memory: Mem0Memory 인스턴스
        event_type: 이벤트 타입 (예: "label_updated", "status_changed")
        description: 이벤트 설명
        ticket_id: 관련 티켓 ID
        message_id: 관련 메일 ID
        old_value: 이전 값
        new_value: 새로운 값
        user_id: 사용자 ID (선택사항)
        
    Returns:
        생성된 메모리 ID
    """
    metadata = {
        "action_type": event_type,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "old_value": old_value,
        "new_value": new_value,
        "timestamp": datetime.now().isoformat()
    }
    
    # user_id가 제공된 경우 메타데이터에 추가
    if user_id:
        metadata["user_id"] = user_id
    
    return memory.add(description, metadata)


def search_related_memories(memory: Mem0Memory, email_content: str, 
                          limit: int = 5) -> List[Dict[str, Any]]:
    """
    이메일 내용과 관련된 과거 메모리를 검색하는 편의 함수
    
    Args:
        memory: Mem0Memory 인스턴스
        email_content: 이메일 내용
        limit: 반환할 최대 결과 수
        
    Returns:
        관련된 과거 메모리 목록
    """
    return memory.search(email_content, limit=limit)


if __name__ == "__main__":
    # 테스트 코드
    print("🧪 Mem0Memory 어댑터 테스트 시작")
    
    try:
        # Mem0Memory 인스턴스 생성
        mem0_memory = create_mem0_memory("test_user")
        
        # 테스트 이벤트 추가
        print("\n📝 테스트 이벤트 추가...")
        event_id1 = add_ticket_event(
            memory=mem0_memory,
            event_type="label_updated",
            description="사용자가 티켓 #123의 라벨을 '버그'에서 '개선사항'으로 수정함",
            ticket_id="123",
            old_value="버그",
            new_value="개선사항"
        )
        
        event_id2 = add_ticket_event(
            memory=mem0_memory,
            event_type="ticket_created",
            description="AI가 '서버 오류' 이메일로부터 티켓 #124를 생성함",
            ticket_id="124",
            message_id="msg_456"
        )
        
        # 메모리 검색 테스트
        print("\n🔍 메모리 검색 테스트...")
        search_results = search_related_memories(
            memory=mem0_memory,
            email_content="서버 접속 오류가 발생했습니다",
            limit=3
        )
        
        print(f"검색 결과: {len(search_results)}개")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. {result['memory']} (점수: {result['score']:.3f})")
        
        # 통계 조회
        print("\n📊 메모리 통계...")
        stats = mem0_memory.get_memory_stats()
        print(f"총 메모리 수: {stats['total_memories']}")
        print(f"액션 타입별: {stats['action_types']}")
        
        print("\n✅ Mem0Memory 어댑터 테스트 완료")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
