#!/usr/bin/env python3
"""
한국어 특화 RAG 데이터 관리자 모듈
ko-sroberta-multitask 모델을 사용한 임베딩 처리
"""

import os
import tempfile
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

# FileProcessor import
from module.file_processor import FileProcessor, DocumentType, FileTypeDetector

# Vector DB import
from vector_db_models import VectorDBManager, FileChunk, StructuredChunk

# 한국어 임베딩 함수 import
from setup_korean_embedding import KoreanEmbeddingFunction

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

class KoreanEmbeddingClient:
    """한국어 특화 임베딩 클라이언트"""
    
    def __init__(self):
        """한국어 임베딩 함수 초기화"""
        self.embedding_function = KoreanEmbeddingFunction()
        self.dimension = 768  # ko-sroberta-multitask 차원
    
    def embed_query(self, text: str) -> List[float]:
        """단일 텍스트 임베딩"""
        embeddings = self.embedding_function([text])
        return embeddings[0] if embeddings else [0.0] * self.dimension
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트 임베딩"""
        return self.embedding_function(texts)

class KoreanVectorDBManager:
    """한국어 특화 Vector DB 관리자"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """ChromaDB 클라이언트 초기화"""
        import chromadb
        from chromadb.config import Settings
        
        # Vector DB 폴더가 없으면 생성하고 권한 설정
        if not os.path.exists(db_path):
            os.makedirs(db_path, mode=0o755, exist_ok=True)
            print(f"✅ Vector DB 폴더 생성 및 권한 설정: {db_path}")
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 한국어 임베딩 함수 초기화
        self.korean_embedding_function = KoreanEmbeddingFunction()
        
        # 컬렉션 이름들
        self.collection_names = {
            'mail': 'mail_collection',
            'file': 'file_chunks', 
            'jira': 'jira_specialized_chunks'
        }
        
        # 컬렉션들 초기화
        self.collections = {}
        self._initialize_collections()
        
        print("✅ 한국어 특화 Vector DB 관리자 초기화 완료")
    
    def _initialize_collections(self):
        """컬렉션들 초기화"""
        for collection_type, collection_name in self.collection_names.items():
            try:
                # 기존 컬렉션 가져오기 시도
                collection = self.client.get_collection(name=collection_name)
                self.collections[collection_type] = collection
                print(f"✅ 기존 컬렉션 사용: {collection_name}")
            except Exception:
                # 컬렉션이 없으면 새로 생성
                collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.korean_embedding_function,
                    metadata={
                        "description": f"한국어 특화 임베딩 - {collection_name}",
                        "embedding_model": "jhgan/ko-sroberta-multitask",
                        "embedding_dimension": 768,
                        "language": "korean"
                    }
                )
                self.collections[collection_type] = collection
                print(f"✅ 새 컬렉션 생성: {collection_name}")
    
    def add_document(self, collection_type: str, document: str, metadata: Dict[str, Any], doc_id: str = None):
        """문서를 컬렉션에 추가"""
        if collection_type not in self.collections:
            raise ValueError(f"지원하지 않는 컬렉션 타입: {collection_type}")
        
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        
        collection = self.collections[collection_type]
        
        try:
            collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id]
            )
            print(f"✅ 문서 추가 완료: {doc_id}")
            return doc_id
        except Exception as e:
            print(f"❌ 문서 추가 실패: {e}")
            return None
    
    def search_similar(self, collection_type: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """유사한 문서 검색"""
        if collection_type not in self.collections:
            raise ValueError(f"지원하지 않는 컬렉션 타입: {collection_type}")
        
        collection = self.collections[collection_type]
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # 결과 포맷팅
            formatted_results = []
            for i in range(len(results['documents'][0])):
                result = {
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                    'similarity_score': 1.0 - (results['distances'][0][i] / 1000.0)  # 거리를 유사도로 변환
                }
                formatted_results.append(result)
            
            print(f"✅ 검색 완료: {len(formatted_results)}개 결과")
            return formatted_results
            
        except Exception as e:
            print(f"❌ 검색 실패: {e}")
            return []
    
    def get_collection_info(self, collection_type: str) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        if collection_type not in self.collections:
            return {}
        
        collection = self.collections[collection_type]
        count = collection.count()
        
        return {
            'name': collection.name,
            'count': count,
            'metadata': collection.metadata
        }

def create_korean_embedding_client():
    """한국어 임베딩 클라이언트 생성"""
    return KoreanEmbeddingClient()

def test_korean_rag_system():
    """한국어 RAG 시스템 테스트"""
    print("🧪 한국어 RAG 시스템 테스트 시작...")
    
    # Vector DB 관리자 초기화
    vector_manager = KoreanVectorDBManager()
    
    # 테스트 문서들
    test_documents = [
        {
            'content': '서버에 접속할 수 없는 문제가 발생했습니다. HTTP 500 오류가 지속적으로 나타나고 있습니다.',
            'metadata': {'type': 'server_issue', 'priority': 'high'},
            'id': 'doc_001'
        },
        {
            'content': '데이터베이스 연결 오류가 발생했습니다. 연결 풀이 고갈되어 새로운 연결을 생성할 수 없습니다.',
            'metadata': {'type': 'database_issue', 'priority': 'high'},
            'id': 'doc_002'
        },
        {
            'content': '사용자 인터페이스가 느리게 로드되는 문제가 있습니다. 페이지 로딩 시간이 평균 5초 이상 소요됩니다.',
            'metadata': {'type': 'ui_issue', 'priority': 'medium'},
            'id': 'doc_003'
        }
    ]
    
    # 문서들 추가
    print("\n📝 테스트 문서들 추가 중...")
    for doc in test_documents:
        vector_manager.add_document('mail', doc['content'], doc['metadata'], doc['id'])
    
    # 검색 테스트
    print("\n🔍 검색 테스트...")
    test_queries = [
        '서버 문제',
        '데이터베이스 오류',
        '느린 로딩',
        'HTTP 500'
    ]
    
    for query in test_queries:
        print(f"\n검색어: '{query}'")
        results = vector_manager.search_similar('mail', query, top_k=2)
        
        for i, result in enumerate(results, 1):
            print(f"  {i}. 유사도: {result['similarity_score']:.3f}")
            print(f"     내용: {result['content'][:80]}...")
            print(f"     메타데이터: {result['metadata']}")
    
    # 컬렉션 정보 출력
    print("\n📊 컬렉션 정보:")
    for collection_type in ['mail', 'file', 'jira']:
        info = vector_manager.get_collection_info(collection_type)
        if info:
            print(f"  {collection_type}: {info['count']}개 문서")
    
    print("\n✅ 한국어 RAG 시스템 테스트 완료!")

if __name__ == "__main__":
    test_korean_rag_system()
