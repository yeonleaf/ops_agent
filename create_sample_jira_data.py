#!/usr/bin/env python3
"""
테스트용 Jira 샘플 데이터 생성 스크립트
jira_multi_vector_chunks 컬렉션에 다양한 chunk_type의 샘플 데이터를 추가
"""

import chromadb
from chromadb.config import Settings
from setup_korean_embedding import KoreanEmbeddingFunction
import uuid
from datetime import datetime

def create_sample_jira_data():
    """테스트용 Jira 샘플 데이터 생성"""
    print("🚀 테스트용 Jira 샘플 데이터 생성")
    print("="*80)

    try:
        # ChromaDB 연결
        client = chromadb.PersistentClient(
            path='./vector_db',
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        # 한국어 임베딩 함수 초기화
        korean_embedding = KoreanEmbeddingFunction()

        # jira_multi_vector_chunks 컬렉션 가져오기 또는 생성
        try:
            collection = client.get_collection("jira_multi_vector_chunks")
            print(f"📊 기존 컬렉션 사용: {collection.count()}개 문서")
        except:
            collection = client.create_collection(
                name="jira_multi_vector_chunks",
                embedding_function=korean_embedding
            )
            print("📊 새 컬렉션 생성")

        # 샘플 Jira 티켓 데이터
        sample_tickets = [
            {
                "ticket_id": "PROJ-001",
                "chunks": [
                    {
                        "chunk_type": "title",
                        "content": "서버 접속 오류 해결 방법"
                    },
                    {
                        "chunk_type": "summary",
                        "content": "메인 서버에 접속할 수 없는 문제의 원인 분석 및 해결 방안 요약"
                    },
                    {
                        "chunk_type": "description",
                        "content": "사용자들이 메인 서버(192.168.1.100)에 접속을 시도할 때 연결 시간 초과 오류가 발생합니다. 네트워크 연결 상태는 정상이며, 다른 서비스는 정상 작동합니다. 로그 분석 결과 서버 포트 8080에서 응답이 없는 상태입니다."
                    },
                    {
                        "chunk_type": "comment",
                        "content": "저도 같은 문제가 있었는데 방화벽 설정을 확인해보니 포트가 차단되어 있었어요. 포트 8080을 열어주니까 해결되었습니다."
                    }
                ]
            },
            {
                "ticket_id": "PROJ-002",
                "chunks": [
                    {
                        "chunk_type": "title",
                        "content": "데이터베이스 연결 실패 문제"
                    },
                    {
                        "chunk_type": "summary",
                        "content": "MySQL 데이터베이스 연결이 간헐적으로 실패하는 현상 조사"
                    },
                    {
                        "chunk_type": "description",
                        "content": "애플리케이션에서 MySQL 데이터베이스에 연결을 시도할 때 간헐적으로 'Connection timeout' 오류가 발생합니다. 특히 피크 시간대(오전 9시-11시, 오후 2시-4시)에 빈번하게 발생하며, 연결 풀 설정과 관련된 것으로 추정됩니다."
                    },
                    {
                        "chunk_type": "comment",
                        "content": "연결 풀 최대 크기를 50에서 100으로 늘리고 타임아웃을 30초로 설정했더니 문제가 많이 줄어들었습니다."
                    }
                ]
            },
            {
                "ticket_id": "PROJ-003",
                "chunks": [
                    {
                        "chunk_type": "title",
                        "content": "사용자 인터페이스 개선 요청"
                    },
                    {
                        "chunk_type": "summary",
                        "content": "메인 대시보드의 사용성 개선 및 직관적 인터페이스 구현"
                    },
                    {
                        "chunk_type": "description",
                        "content": "현재 메인 대시보드가 복잡하고 직관적이지 않아 사용자들이 어려워합니다. 주요 기능들을 찾기 어렵고, 메뉴 구조가 깊어서 원하는 작업을 수행하기까지 시간이 많이 걸립니다. 사용자 경험을 개선하기 위해 인터페이스 재설계가 필요합니다."
                    },
                    {
                        "chunk_type": "comment",
                        "content": "특히 검색 기능이 너무 숨겨져 있어요. 검색 버튼을 더 눈에 띄는 곳에 배치하면 좋겠습니다."
                    }
                ]
            },
            {
                "ticket_id": "PROJ-004",
                "chunks": [
                    {
                        "chunk_type": "title",
                        "content": "API 응답 속도 최적화"
                    },
                    {
                        "chunk_type": "summary",
                        "content": "REST API 응답 시간이 3초 이상 걸리는 성능 이슈 해결"
                    },
                    {
                        "chunk_type": "description",
                        "content": "사용자 목록 조회 API(/api/users)의 응답 시간이 평균 3.5초로 매우 느립니다. 데이터베이스 쿼리 최적화, 인덱스 추가, 캐싱 전략 도입 등의 방법으로 응답 시간을 1초 이내로 단축해야 합니다."
                    },
                    {
                        "chunk_type": "comment",
                        "content": "Redis 캐시를 도입했더니 응답 시간이 0.8초로 줄어들었습니다. 인덱스도 추가로 최적화하면 더 빨라질 것 같아요."
                    }
                ]
            },
            {
                "ticket_id": "PROJ-005",
                "chunks": [
                    {
                        "chunk_type": "title",
                        "content": "로그인 시스템 보안 강화"
                    },
                    {
                        "chunk_type": "summary",
                        "content": "2단계 인증 및 비밀번호 정책 강화를 통한 보안 개선"
                    },
                    {
                        "chunk_type": "description",
                        "content": "현재 로그인 시스템의 보안이 취약합니다. 비밀번호 정책이 느슨하고, 2단계 인증이 없어서 보안 위험이 높습니다. 2FA 도입, 비밀번호 복잡도 강화, 계정 잠금 정책 등을 구현해야 합니다."
                    },
                    {
                        "chunk_type": "comment",
                        "content": "Google Authenticator와 연동하는 2FA를 구현했습니다. 사용자 반응이 좋네요."
                    }
                ]
            }
        ]

        # 데이터 추가
        all_ids = []
        all_documents = []
        all_metadatas = []

        for ticket in sample_tickets:
            ticket_id = ticket["ticket_id"]

            for chunk in ticket["chunks"]:
                chunk_id = f"{ticket_id}_{chunk['chunk_type']}_{uuid.uuid4().hex[:8]}"

                metadata = {
                    "ticket_id": ticket_id,
                    "chunk_type": chunk["chunk_type"],
                    "created_at": datetime.now().isoformat(),
                    "source": "sample_data"
                }

                all_ids.append(chunk_id)
                all_documents.append(chunk["content"])
                all_metadatas.append(metadata)

        # 컬렉션에 추가
        collection.add(
            ids=all_ids,
            documents=all_documents,
            metadatas=all_metadatas
        )

        print(f"✅ {len(all_ids)}개 샘플 데이터 추가 완료")
        print(f"📊 현재 컬렉션 문서 수: {collection.count()}")

        # chunk_type별 통계
        chunk_type_counts = {}
        for metadata in all_metadatas:
            chunk_type = metadata["chunk_type"]
            chunk_type_counts[chunk_type] = chunk_type_counts.get(chunk_type, 0) + 1

        print("\n📈 chunk_type별 분포:")
        for chunk_type, count in sorted(chunk_type_counts.items()):
            print(f"  - {chunk_type}: {count}개")

        return True

    except Exception as e:
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return False

if __name__ == "__main__":
    create_sample_jira_data()