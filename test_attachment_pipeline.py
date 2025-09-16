#!/usr/bin/env python3
"""
첨부파일 처리 파이프라인 테스트 스크립트
"""

import os
import base64
import json
from datetime import datetime
from typing import Dict, Any

from ticket_with_attachments import TicketAttachmentProcessor
from attachment_processor import AttachmentProcessor
from email_attachment_extractor import EmailAttachmentExtractor
from module.logging_config import setup_session_logging, get_logger


class AttachmentPipelineTest:
    """첨부파일 처리 파이프라인 테스트 클래스"""

    def __init__(self):
        # 세션별 로깅 설정
        session_id = setup_session_logging(level="INFO", console_output=True)
        self.logger = get_logger(__name__)
        self.logger.info(f"첨부파일 파이프라인 테스트 시작 - 세션: {session_id}")

        # 프로세서 초기화
        self.ticket_processor = TicketAttachmentProcessor()
        self.attachment_processor = AttachmentProcessor()
        self.email_extractor = EmailAttachmentExtractor()

    def create_test_data(self) -> Dict[str, Any]:
        """테스트용 이메일 데이터 생성"""
        try:
            # 간단한 텍스트 파일을 base64로 인코딩
            test_content = """
서버 에러 로그 분석 보고서

1. 발생 시간: 2025-01-15 14:30:00
2. 에러 내용: Database connection timeout
3. 영향 범위: 전체 사용자
4. 해결 방법:
   - 데이터베이스 연결 풀 크기 증가
   - 타임아웃 설정 조정
   - 모니터링 강화

추가 분석이 필요한 부분:
- 메모리 사용량 패턴
- 네트워크 지연 시간
- 백업 시스템 상태
"""

            # base64 인코딩
            test_base64 = base64.b64encode(test_content.encode('utf-8')).decode('utf-8')

            # 테스트 이메일 데이터
            test_email = {
                'id': 'test_email_001',
                'subject': '서버 장애 분석 보고서',
                'body': f'서버에서 발생한 장애를 분석했습니다. 상세 내용은 첨부 파일을 확인해주세요.\n\n첨부파일 데이터:\n{test_base64}',
                'sender': 'admin@company.com',
                'received_time': datetime.now().isoformat(),
                'has_attachments': True,
                'hasAttachments': True,
                'payload': {
                    'parts': [
                        {
                            'filename': 'server_error_analysis.txt',
                            'mimeType': 'text/plain',
                            'body': {
                                'data': test_base64,
                                'size': len(test_content)
                            }
                        }
                    ]
                }
            }

            self.logger.info("테스트 이메일 데이터 생성 완료")
            return test_email

        except Exception as e:
            self.logger.error(f"테스트 데이터 생성 실패: {e}")
            return {}

    def test_email_attachment_extraction(self) -> bool:
        """이메일 첨부파일 추출 테스트"""
        try:
            self.logger.info("=== 이메일 첨부파일 추출 테스트 시작 ===")

            test_email = self.create_test_data()
            if not test_email:
                self.logger.error("테스트 데이터 생성 실패")
                return False

            # 첨부파일 추출
            extracted_attachments = self.email_extractor.extract_attachments_from_mail_data(test_email)

            self.logger.info(f"추출된 첨부파일 수: {len(extracted_attachments)}")

            for i, attachment in enumerate(extracted_attachments):
                self.logger.info(f"첨부파일 {i+1}:")
                self.logger.info(f"  - 파일명: {attachment.get('filename', 'N/A')}")
                self.logger.info(f"  - 타입: {attachment.get('mime_type', 'N/A')}")
                self.logger.info(f"  - 크기: {attachment.get('size', 0)} bytes")

            return len(extracted_attachments) > 0

        except Exception as e:
            self.logger.error(f"첨부파일 추출 테스트 실패: {e}")
            return False

    def test_attachment_processing(self) -> bool:
        """첨부파일 처리 테스트"""
        try:
            self.logger.info("=== 첨부파일 처리 테스트 시작 ===")

            # 테스트용 base64 데이터 생성
            test_content = "서버 장애 보고서\n\n1. 발생 시간: 2025-01-15\n2. 원인: 메모리 부족"
            test_base64 = base64.b64encode(test_content.encode('utf-8')).decode('utf-8')

            # 첨부파일 처리
            processed = self.attachment_processor.process_attachment_from_base64(
                base64_data=test_base64,
                filename="test_report.txt",
                mime_type="text/plain",
                ticket_id="test_ticket_001"
            )

            if processed:
                self.logger.info("첨부파일 처리 성공:")
                self.logger.info(f"  - 파일 ID: {processed.metadata.file_id}")
                self.logger.info(f"  - 파일명: {processed.metadata.original_filename}")
                self.logger.info(f"  - 크기: {processed.metadata.file_size} bytes")
                self.logger.info(f"  - Vector DB IDs: {len(processed.vector_db_ids)}개")

                if processed.analysis_result:
                    self.logger.info("  - LLM 분석 결과:")
                    for key, value in processed.analysis_result.items():
                        self.logger.info(f"    {key}: {value}")

                return True
            else:
                self.logger.error("첨부파일 처리 실패")
                return False

        except Exception as e:
            self.logger.error(f"첨부파일 처리 테스트 실패: {e}")
            return False

    def test_ticket_creation_with_attachments(self) -> bool:
        """첨부파일 포함 티켓 생성 테스트"""
        try:
            self.logger.info("=== 첨부파일 포함 티켓 생성 테스트 시작 ===")

            test_email = self.create_test_data()
            if not test_email:
                self.logger.error("테스트 데이터 생성 실패")
                return False

            # 첨부파일 포함 티켓 생성
            result = self.ticket_processor.create_ticket_with_attachments(
                email_data=test_email,
                user_email="test@company.com"
            )

            if result:
                self.logger.info("첨부파일 포함 티켓 생성 성공:")
                self.logger.info(f"  - 티켓 ID: {result.ticket_id}")
                self.logger.info(f"  - 첨부파일 수: {len(result.attachments)}")

                if result.attachment_summary:
                    self.logger.info("  - 첨부파일 요약:")
                    self.logger.info(f"    {result.attachment_summary[:200]}...")

                return True
            else:
                self.logger.error("첨부파일 포함 티켓 생성 실패")
                return False

        except Exception as e:
            self.logger.error(f"첨부파일 포함 티켓 생성 테스트 실패: {e}")
            return False

    def test_attachment_search(self) -> bool:
        """첨부파일 검색 테스트"""
        try:
            self.logger.info("=== 첨부파일 검색 테스트 시작 ===")

            # 검색 쿼리
            test_queries = [
                "서버 장애",
                "데이터베이스 연결",
                "에러 분석",
                "메모리 사용량"
            ]

            for query in test_queries:
                self.logger.info(f"검색 쿼리: '{query}'")

                # 첨부파일 포함 검색
                results = self.ticket_processor.search_tickets_with_attachments(
                    query=query,
                    include_attachments=True,
                    n_results=3
                )

                self.logger.info(f"  검색 결과: {len(results)}개")

                for i, result in enumerate(results[:2]):  # 상위 2개만 로그
                    self.logger.info(f"  결과 {i+1}:")
                    self.logger.info(f"    - 소스: {result['source']}")
                    self.logger.info(f"    - 티켓 ID: {result.get('ticket_id', 'N/A')}")
                    self.logger.info(f"    - 유사도: {result.get('similarity_score', 0.0):.3f}")
                    self.logger.info(f"    - 내용: {result.get('content', '')[:100]}...")

            return True

        except Exception as e:
            self.logger.error(f"첨부파일 검색 테스트 실패: {e}")
            return False

    def test_attachment_statistics(self) -> bool:
        """첨부파일 통계 테스트"""
        try:
            self.logger.info("=== 첨부파일 통계 테스트 시작 ===")

            stats = self.ticket_processor.get_attachment_statistics()

            if stats:
                self.logger.info("첨부파일 통계:")
                self.logger.info(f"  - 총 청크 수: {stats.get('total_chunks', 0)}")
                self.logger.info(f"  - 총 파일 수: {stats.get('total_files', 0)}")

                file_types = stats.get('file_types', {})
                self.logger.info(f"  - 파일 형식: {len(file_types)}개")
                for file_type, count in list(file_types.items())[:3]:
                    self.logger.info(f"    {file_type}: {count}개")

                categories = stats.get('file_categories', {})
                if categories:
                    self.logger.info(f"  - 카테고리:")
                    for category, count in categories.items():
                        self.logger.info(f"    {category}: {count}개")

                return True
            else:
                self.logger.warning("첨부파일 통계가 비어있음")
                return True  # 데이터가 없어도 정상적인 상황

        except Exception as e:
            self.logger.error(f"첨부파일 통계 테스트 실패: {e}")
            return False

    def run_all_tests(self) -> Dict[str, bool]:
        """모든 테스트 실행"""
        try:
            self.logger.info("📋 첨부파일 처리 파이프라인 전체 테스트 시작")
            self.logger.info("="*60)

            test_results = {}

            # 1. 첨부파일 추출 테스트
            test_results['attachment_extraction'] = self.test_email_attachment_extraction()

            # 2. 첨부파일 처리 테스트
            test_results['attachment_processing'] = self.test_attachment_processing()

            # 3. 티켓 생성 테스트
            test_results['ticket_creation'] = self.test_ticket_creation_with_attachments()

            # 4. 첨부파일 검색 테스트
            test_results['attachment_search'] = self.test_attachment_search()

            # 5. 통계 테스트
            test_results['attachment_statistics'] = self.test_attachment_statistics()

            # 결과 요약
            self.logger.info("="*60)
            self.logger.info("📊 테스트 결과 요약")
            self.logger.info("="*60)

            passed_tests = sum(1 for result in test_results.values() if result)
            total_tests = len(test_results)

            for test_name, result in test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                self.logger.info(f"{test_name}: {status}")

            self.logger.info(f"\n총 테스트: {total_tests}개")
            self.logger.info(f"성공: {passed_tests}개")
            self.logger.info(f"실패: {total_tests - passed_tests}개")
            self.logger.info(f"성공률: {(passed_tests/total_tests)*100:.1f}%")

            if passed_tests == total_tests:
                self.logger.info("🎉 모든 테스트 통과!")
            else:
                self.logger.warning("⚠️ 일부 테스트 실패")

            return test_results

        except Exception as e:
            self.logger.error(f"전체 테스트 실행 실패: {e}")
            return {}


def main():
    """메인 함수"""
    try:
        # 환경 변수 확인
        required_env_vars = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_OPENAI_API_VERSION"
        ]

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            print(f"❌ 필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
            print("테스트를 실행하기 전에 .env 파일을 확인하세요.")
            return

        # 테스트 실행
        tester = AttachmentPipelineTest()
        results = tester.run_all_tests()

        # 종료 코드 설정
        if all(results.values()):
            exit(0)  # 성공
        else:
            exit(1)  # 실패

    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        exit(1)


if __name__ == "__main__":
    main()