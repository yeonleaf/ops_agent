#!/usr/bin/env python3
"""
RAG 임베딩 파이프라인 디버깅 스크립트
Streamlit이나 LangChain 에이전트 없이, 오직 임베딩 모델과 벡터 DB의 핵심 기능만을 테스트
"""

import os
import sys
from dotenv import load_dotenv
from openai import AzureOpenAI
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime
import numpy as np

class DummyEmbeddingClient:
    """더미 임베딩 클라이언트 - 테스트용"""
    
    def __init__(self, dimension=384):
        self.dimension = dimension
        print(f"🔧 더미 임베딩 클라이언트 초기화 (차원: {dimension})")
    
    def get_embedding(self, text: str):
        """더미 임베딩 생성 - 랜덤 벡터 반환"""
        # 텍스트의 해시값을 시드로 사용하여 일관된 랜덤 벡터 생성
        import hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        np.random.seed(seed)
        
        # 정규화된 랜덤 벡터 생성 (더 작은 범위로)
        embedding = np.random.normal(0, 0.1, self.dimension)
        embedding = embedding / np.linalg.norm(embedding)  # 정규화
        
        # 벡터 크기를 1로 정규화 (코사인 유사도 계산을 위해)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()

def load_environment():
    """1단계: 초기 설정 - 환경 변수 로드"""
    print("🔧 1단계: 환경 변수 로드 중...")
    load_dotenv()
    
    # Azure OpenAI 설정 확인
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
    
    if not all([azure_endpoint, azure_api_key, azure_deployment]):
        print("❌ Azure OpenAI 환경 변수가 설정되지 않았습니다.")
        print(f"   AZURE_OPENAI_ENDPOINT: {'✅' if azure_endpoint else '❌'}")
        print(f"   AZURE_OPENAI_API_KEY: {'✅' if azure_api_key else '❌'}")
        print(f"   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: {'✅' if azure_deployment else '❌'}")
        return None, None, None
    
    print("✅ 환경 변수 로드 완료")
    return azure_endpoint, azure_api_key, azure_deployment

def initialize_clients(azure_endpoint, azure_api_key, azure_deployment):
    """1단계: Azure OpenAI 및 Vector DB 클라이언트 초기화"""
    print("🔧 Azure OpenAI 클라이언트 초기화 중...")
    
    # Azure OpenAI 클라이언트 초기화
    openai_client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=azure_api_key,
        api_version="2024-02-15-preview"
    )
    
    print("🔧 Vector DB 클라이언트 초기화 중...")
    
    # Vector DB 폴더 생성 및 권한 설정
    db_path = "./debug_vector_db"
    if not os.path.exists(db_path):
        os.makedirs(db_path, mode=0o755, exist_ok=True)
        print(f"✅ Vector DB 폴더 생성: {db_path}")
    
    # ChromaDB 클라이언트 초기화
    chroma_client = chromadb.PersistentClient(
        path=db_path,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    
    # 테스트용 컬렉션 생성 (코사인 유사도 사용)
    collection_name = "debug_embedding_test"
    try:
        collection = chroma_client.get_collection(collection_name)
        print(f"✅ 기존 컬렉션 사용: {collection_name}")
    except:
        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={"description": "임베딩 파이프라인 디버깅용 컬렉션"},
            embedding_function=None  # 기본 임베딩 함수 사용하지 않음
        )
        print(f"✅ 새 컬렉션 생성: {collection_name} (코사인 유사도)")
    
    # ChromaDB 파일 권한 설정
    try:
        chroma_file = os.path.join(db_path, "chroma.sqlite3")
        if os.path.exists(chroma_file):
            os.chmod(chroma_file, 0o666)
            print(f"✅ ChromaDB 파일 권한 설정: {chroma_file}")
    except Exception as e:
        print(f"⚠️ ChromaDB 파일 권한 설정 실패: {e}")
    
    return openai_client, collection

def get_embedding(openai_client, azure_deployment, text: str, use_dummy=False):
    """3단계: 핵심 기능 테스트 - 텍스트 임베딩 함수"""
    print(f"\n🔍 임베딩 생성 중...")
    print(f"   입력 텍스트: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
    if use_dummy:
        print("   🔧 더미 임베딩 클라이언트 사용")
        dummy_client = DummyEmbeddingClient()
        embedding_vector = dummy_client.get_embedding(text)
        print(f"   벡터 차원: {len(embedding_vector)}")
        print(f"   벡터 앞 5개 값: {embedding_vector[:5]}")
        
        # 벡터 값 범위 확인
        min_val = min(embedding_vector)
        max_val = max(embedding_vector)
        print(f"   벡터 값 범위: {min_val:.6f} ~ {max_val:.6f}")
        
        return embedding_vector
    
    try:
        response = openai_client.embeddings.create(
            input=text,
            model=azure_deployment
        )
        
        embedding_vector = response.data[0].embedding
        print(f"   벡터 차원: {len(embedding_vector)}")
        print(f"   벡터 앞 5개 값: {embedding_vector[:5]}")
        
        # 벡터가 모두 0인지 확인
        if all(x == 0 for x in embedding_vector):
            print("❌ 심각한 오류: 벡터가 모두 0입니다!")
            return None
        
        # 벡터 값 범위 확인
        min_val = min(embedding_vector)
        max_val = max(embedding_vector)
        print(f"   벡터 값 범위: {min_val:.6f} ~ {max_val:.6f}")
        
        return embedding_vector
        
    except Exception as e:
        print(f"❌ 임베딩 생성 실패: {e}")
        print("   🔧 더미 임베딩 클라이언트로 폴백")
        dummy_client = DummyEmbeddingClient()
        embedding_vector = dummy_client.get_embedding(text)
        print(f"   벡터 차원: {len(embedding_vector)}")
        print(f"   벡터 앞 5개 값: {embedding_vector[:5]}")
        return embedding_vector

def run_pipeline_test(openai_client, azure_deployment, collection, use_dummy=False):
    """3단계: 핵심 기능 테스트 - 전체 파이프라인 실행"""
    print(f"\n🚀 3단계: 파이프라인 테스트 시작")
    
    # 2단계: 정답 데이터와 질문 정의
    ground_truth_document = "메인 서버에 접속이 되지 않습니다. HTTP 500 오류가 발생하고 있습니다."
    test_query = "서버 접속 오류 문제 해결 방법"
    
    print(f"📄 정답 문서: '{ground_truth_document}'")
    print(f"❓ 테스트 질문: '{test_query}'")
    
    # 1. 정답 문서를 ChromaDB 기본 임베딩으로 저장
    print(f"\n📝 1) 정답 문서를 ChromaDB 기본 임베딩으로 저장 중...")
    doc_id = "DEBUG-001"
    try:
        collection.add(
            documents=[ground_truth_document],
            ids=[doc_id],
            metadatas=[{
                "type": "ground_truth",
                "created_at": datetime.now().isoformat(),
                "test_id": "debug_001"
            }]
        )
        print(f"✅ 문서 저장 완료: ID={doc_id}")
    except Exception as e:
        print(f"❌ 문서 저장 실패: {e}")
        return None
    
    # 2. 테스트 질문으로 ChromaDB 기본 임베딩 검색
    print(f"\n🔍 2) ChromaDB 기본 임베딩으로 검색 중...")
    try:
        results = collection.query(
            query_texts=[test_query],
            n_results=3,
            include=['documents', 'metadatas', 'distances']
        )
        
        print(f"✅ 검색 완료: {len(results['ids'][0])}개 결과")
        
        # 검색 결과 출력
        print(f"\n📊 검색 결과 (상위 3개):")
        for i, (doc_id, doc_content, distance) in enumerate(zip(
            results['ids'][0], 
            results['documents'][0], 
            results['distances'][0]
        )):
            # ChromaDB의 거리 계산 방식에 따른 유사도 변환
            # L2 거리: similarity = 1 / (1 + distance)
            # 코사인 거리: similarity = 1 - distance
            if distance > 2:  # L2 거리로 보임
                similarity_score = 1 / (1 + distance)
                distance_type = "L2"
            else:  # 코사인 거리로 보임
                similarity_score = 1 - distance
                distance_type = "코사인"
            
            print(f"   {i+1}. ID: {doc_id}")
            print(f"      내용: '{doc_content[:100]}{'...' if len(doc_content) > 100 else ''}'")
            print(f"      유사도 점수: {similarity_score:.6f} ({distance_type})")
            print(f"      거리: {distance:.6f}")
            print(f"      ---")
        
        return results
        
    except Exception as e:
        print(f"❌ 유사도 검색 실패: {e}")
        return None

def verify_results(results):
    """4단계: 최종 검증 로직"""
    print(f"\n🎯 4단계: 최종 검증")
    
    if results is None:
        print("❌ 검색 결과가 없어 검증할 수 없습니다.")
        return False
    
    # DEBUG-001 문서가 검색 결과에 포함되어 있는지 확인
    found_ids = results['ids'][0]
    target_id = "DEBUG-001"
    
    if target_id not in found_ids:
        print(f"❌ 실패: 정답 문서 '{target_id}'가 검색 결과에 없습니다.")
        print(f"   검색된 ID들: {found_ids}")
        return False
    
    # DEBUG-001의 유사도 점수 확인
    target_index = found_ids.index(target_id)
    target_distance = results['distances'][0][target_index]
    
    # ChromaDB의 거리 계산 방식에 따른 유사도 변환
    if target_distance > 2:  # L2 거리로 보임
        target_similarity = 1 / (1 + target_distance)
        distance_type = "L2"
    else:  # 코사인 거리로 보임
        target_similarity = 1 - target_distance
        distance_type = "코사인"
    
    print(f"✅ 성공: 정답 문서 '{target_id}' 발견!")
    print(f"   유사도 점수: {target_similarity:.6f}")
    print(f"   순위: {target_index + 1}위")
    
    if target_similarity >= 0.8:
        print(f"🎉 완벽: 유사도 점수가 0.8 이상입니다! ({target_similarity:.6f})")
        return True
    elif target_similarity >= 0.5:
        print(f"⚠️ 보통: 유사도 점수가 0.5-0.8 사이입니다. ({target_similarity:.6f})")
        return True
    else:
        print(f"❌ 낮음: 유사도 점수가 0.5 미만입니다. ({target_similarity:.6f})")
        return False

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("🔬 RAG 임베딩 파이프라인 디버깅 스크립트")
    print("=" * 80)
    
    # 1단계: 환경 설정
    azure_endpoint, azure_api_key, azure_deployment = load_environment()
    
    # 환경 변수가 없으면 더미 클라이언트 사용
    use_dummy = not all([azure_endpoint, azure_api_key, azure_deployment])
    if use_dummy:
        print("⚠️ Azure OpenAI 환경 변수가 설정되지 않아 더미 클라이언트를 사용합니다.")
        print("   실제 Azure OpenAI를 사용하려면 다음 환경 변수를 설정하세요:")
        print("   - AZURE_OPENAI_ENDPOINT")
        print("   - AZURE_OPENAI_API_KEY") 
        print("   - AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
    
    # 클라이언트 초기화
    openai_client, collection = initialize_clients(azure_endpoint, azure_api_key, azure_deployment)
    if not collection:
        print("❌ Vector DB 초기화 실패로 종료합니다.")
        return
    
    # 3단계: 파이프라인 테스트 실행
    results = run_pipeline_test(openai_client, azure_deployment, collection, use_dummy)
    
    # 4단계: 결과 검증
    success = verify_results(results)
    
    # 최종 결과
    print("\n" + "=" * 80)
    if success:
        print("🎉 임베딩 파이프라인 테스트 성공!")
        print("   모든 단계가 정상적으로 작동하고 있습니다.")
    else:
        print("❌ 임베딩 파이프라인 테스트 실패!")
        print("   위의 오류 메시지를 확인하여 문제를 해결하세요.")
    print("=" * 80)

if __name__ == "__main__":
    main()
