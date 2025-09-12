#!/usr/bin/env python3
"""
ChromaDB 싱글톤 매니저
여러 모듈에서 동일한 ChromaDB 인스턴스를 공유하여 충돌 방지
"""

import os
import threading
from typing import Optional
import chromadb
from chromadb.config import Settings

class ChromaDBSingleton:
    """ChromaDB 싱글톤 클래스"""
    
    _instance: Optional['ChromaDBSingleton'] = None
    _lock = threading.Lock()
    _client: Optional[chromadb.PersistentClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ChromaDBSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._db_path = "./vector_db"
            self._client = None
    
    def get_client(self, force_reset: bool = False) -> chromadb.PersistentClient:
        """ChromaDB 클라이언트를 가져오거나 생성"""
        if self._client is None or force_reset:
            with self._lock:
                if self._client is None or force_reset:
                    self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> chromadb.PersistentClient:
        """새로운 ChromaDB 클라이언트 생성"""
        try:
            # 디렉토리 생성
            if not os.path.exists(self._db_path):
                os.makedirs(self._db_path, mode=0o755, exist_ok=True)
                print(f"✅ Vector DB 폴더 생성: {self._db_path}")
            
            # 클라이언트 생성
            client = chromadb.PersistentClient(
                path=self._db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 연결 테스트
            _ = client.list_collections()
            print("✅ ChromaDB 싱글톤 클라이언트 생성 성공")
            return client
            
        except Exception as e:
            print(f"❌ ChromaDB 클라이언트 생성 실패: {e}")
            raise e
    
    def reset_client(self):
        """클라이언트 강제 재설정"""
        with self._lock:
            if self._client:
                try:
                    del self._client
                except:
                    pass
                self._client = None
            
            # 디렉토리 완전 삭제 후 재생성
            import shutil
            if os.path.exists(self._db_path):
                shutil.rmtree(self._db_path)
            os.makedirs(self._db_path, mode=0o755, exist_ok=True)
            print(f"🔄 ChromaDB 디렉토리 재생성: {self._db_path}")
            
            # 새 클라이언트 생성
            self._client = self._create_client()
    
    def get_collection(self, name: str, create_if_not_exists: bool = True):
        """컬렉션 가져오기 또는 생성"""
        client = self.get_client()
        
        try:
            return client.get_collection(name)
        except Exception:
            if create_if_not_exists:
                return client.create_collection(
                    name=name,
                    metadata={
                        "description": f"Collection for {name}",
                        "created_at": str(os.path.getctime(self._db_path))
                    }
                )
            else:
                raise

# 전역 싱글톤 인스턴스
_chromadb_singleton = ChromaDBSingleton()

def get_chromadb_client(force_reset: bool = False) -> chromadb.PersistentClient:
    """전역 ChromaDB 클라이언트 가져오기"""
    return _chromadb_singleton.get_client(force_reset)

def get_chromadb_collection(name: str, create_if_not_exists: bool = True):
    """전역 ChromaDB 컬렉션 가져오기"""
    return _chromadb_singleton.get_collection(name, create_if_not_exists)

def reset_chromadb_singleton():
    """ChromaDB 싱글톤 강제 재설정"""
    _chromadb_singleton.reset_client()
