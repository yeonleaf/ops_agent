#!/usr/bin/env python3
"""
ChromaDB에 Azure OpenAI 임베딩 함수를 설정하는 스크립트
"""

import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from openai import AzureOpenAI

def setup_azure_embedding():
    """ChromaDB에 Azure OpenAI 임베딩 함수 설정"""
    print("🔧 ChromaDB에 Azure OpenAI 임베딩 함수 설정 중...")
    
    # 환경 변수 로드
    load_dotenv()
    
    # Azure OpenAI 설정
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
    
    if not all([azure_endpoint, azure_api_key]):
        print("❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        print("   다음 환경 변수를 설정하세요:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_API_KEY")
        print("   - AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME (선택사항)")
        return False
    
    # Azure OpenAI 클라이언트 초기화
    openai_client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=azure_api_key,
        api_version="2024-02-15-preview"
    )
    
    # ChromaDB 클라이언트 초기화
    client = chromadb.PersistentClient(
        path="./vector_db",
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    
    # Azure OpenAI 임베딩 함수 정의
    def azure_embedding_function(texts):
        """Azure OpenAI 임베딩 함수"""
        try:
            response = openai_client.embeddings.create(
                input=texts,
                model=azure_deployment
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            print(f"❌ Azure OpenAI 임베딩 실패: {e}")
            return None
    
    # 기존 컬렉션들 확인
    collections = client.list_collections()
    print(f"📋 발견된 컬렉션: {[c.name for c in collections]}")
    
    # 각 컬렉션에 Azure OpenAI 임베딩 함수 설정
    for collection_info in collections:
        collection_name = collection_info.name
        print(f"\n🔧 컬렉션 '{collection_name}' 설정 중...")
        
        try:
            # 기존 컬렉션 삭제
            client.delete_collection(collection_name)
            print(f"   ✅ 기존 컬렉션 삭제: {collection_name}")
            
            # Azure OpenAI 임베딩 함수로 새 컬렉션 생성
            new_collection = client.create_collection(
                name=collection_name,
                embedding_function=azure_embedding_function,
                metadata={
                    "description": f"Azure OpenAI 임베딩 사용 - {collection_name}",
                    "embedding_model": azure_deployment,
                    "embedding_dimension": 1536
                }
            )
            print(f"   ✅ Azure OpenAI 임베딩 함수 설정 완료: {collection_name}")
            
        except Exception as e:
            print(f"   ❌ 컬렉션 설정 실패: {collection_name} - {e}")
    
    print("\n🎉 Azure OpenAI 임베딩 함수 설정 완료!")
    print("   이제 모든 컬렉션이 1536차원 Azure OpenAI 임베딩을 사용합니다.")
    
    return True

if __name__ == "__main__":
    setup_azure_embedding()
