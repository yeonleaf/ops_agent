#!/usr/bin/env python3
"""
첨부파일을 포함한 티켓 처리 모듈
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from attachment_processor import AttachmentProcessor, ProcessedAttachment
from email_attachment_extractor import EmailAttachmentExtractor
from sqlite_ticket_models import SQLiteTicketManager
from vector_db_models import VectorDBManager
from module.logging_config import get_logger


@dataclass
class TicketWithAttachments:
    """첨부파일이 포함된 티켓 정보"""
    ticket_id: str
    email_data: Dict[str, Any]
    attachments: List[ProcessedAttachment]
    attachment_summary: str


class TicketAttachmentProcessor:
    """티켓 생성 시 첨부파일 처리를 담당하는 클래스"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.attachment_processor = AttachmentProcessor()
        self.email_extractor = EmailAttachmentExtractor()
        self.ticket_manager = SQLiteTicketManager()
        self.vector_db = VectorDBManager()

    def create_ticket_with_attachments(self, email_data: Dict[str, Any],
                                     user_email: str = "unknown@example.com") -> Optional[TicketWithAttachments]:
        """이메일과 첨부파일을 포함한 티켓 생성"""
        try:
            # 1. 기본 티켓 생성
            ticket = self.ticket_manager.create_ticket_from_mail(email_data, user_email)
            if not ticket:
                self.logger.error("기본 티켓 생성 실패")
                return None

            ticket_id = str(ticket.id)
            self.logger.info(f"기본 티켓 생성 완료: {ticket_id}")

            # 2. 이메일에서 첨부파일 추출
            extracted_attachments = self.email_extractor.extract_attachments_from_mail_data(email_data)

            # 3. 첨부파일 처리
            processed_attachments = []
            for attachment_data in extracted_attachments:
                try:
                    # Base64 데이터에서 첨부파일 처리
                    processed = self.attachment_processor.process_attachment_from_base64(
                        base64_data=attachment_data.get('base64_data', ''),
                        filename=attachment_data.get('filename', f'attachment_{len(processed_attachments)}.bin'),
                        mime_type=attachment_data.get('mime_type', 'application/octet-stream'),
                        ticket_id=ticket_id
                    )

                    if processed:
                        processed_attachments.append(processed)
                        self.logger.info(f"첨부파일 처리 완료: {processed.metadata.original_filename}")
                    else:
                        self.logger.warning(f"첨부파일 처리 실패: {attachment_data.get('filename')}")

                except Exception as e:
                    self.logger.error(f"첨부파일 처리 중 오류: {e}")
                    continue

            # 4. 티켓에 첨부파일 정보 업데이트
            if processed_attachments:
                attachment_summary = self._generate_attachment_summary(processed_attachments)
                updated_description = self._update_ticket_description_with_attachments(
                    ticket.description, attachment_summary
                )

                # 티켓 설명 업데이트
                success = self.ticket_manager.update_ticket_description(ticket.id, updated_description)
                if success:
                    self.logger.info(f"티켓 {ticket_id} 설명에 첨부파일 정보 추가 완료")
                else:
                    self.logger.warning(f"티켓 {ticket_id} 설명 업데이트 실패")

            # 5. 결과 반환
            return TicketWithAttachments(
                ticket_id=ticket_id,
                email_data=email_data,
                attachments=processed_attachments,
                attachment_summary=attachment_summary if processed_attachments else ""
            )

        except Exception as e:
            self.logger.error(f"첨부파일 포함 티켓 생성 실패: {e}")
            return None

    def _generate_attachment_summary(self, attachments: List[ProcessedAttachment]) -> str:
        """첨부파일 요약 생성"""
        try:
            if not attachments:
                return ""

            summary_parts = [f"\n📎 **첨부파일 ({len(attachments)}개)**"]

            for i, attachment in enumerate(attachments, 1):
                metadata = attachment.metadata
                analysis = attachment.analysis_result

                # 파일 기본 정보
                file_info = f"{i}. **{metadata.original_filename}**"
                file_info += f" ({self._format_file_size(metadata.file_size)}, {metadata.mime_type})"

                summary_parts.append(file_info)

                # LLM 분석 결과
                if analysis.get("summary"):
                    summary_parts.append(f"   - 내용: {analysis['summary']}")

                if analysis.get("category"):
                    summary_parts.append(f"   - 유형: {analysis['category']}")

                if analysis.get("business_relevance"):
                    summary_parts.append(f"   - 업무 관련성: {analysis['business_relevance']}")

                if analysis.get("keywords"):
                    keywords = ", ".join(analysis["keywords"][:5])  # 상위 5개 키워드만
                    summary_parts.append(f"   - 주요 키워드: {keywords}")

                if analysis.get("key_points"):
                    for point in analysis["key_points"][:3]:  # 상위 3개 포인트만
                        summary_parts.append(f"   • {point}")

                summary_parts.append("")  # 파일 간 구분

            return "\n".join(summary_parts)

        except Exception as e:
            self.logger.error(f"첨부파일 요약 생성 실패: {e}")
            return f"\n📎 **첨부파일 ({len(attachments)}개)** - 분석 중 오류 발생"

    def _format_file_size(self, size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _update_ticket_description_with_attachments(self, original_description: str,
                                                  attachment_summary: str) -> str:
        """원본 티켓 설명에 첨부파일 정보 추가"""
        if not attachment_summary:
            return original_description

        # 첨부파일 정보를 원본 설명 뒤에 추가
        updated_description = original_description

        if not updated_description.endswith('\n'):
            updated_description += '\n'

        updated_description += '\n' + '='*50 + '\n'
        updated_description += attachment_summary

        return updated_description

    def search_tickets_with_attachments(self, query: str, include_attachments: bool = True,
                                      n_results: int = 5) -> List[Dict[str, Any]]:
        """첨부파일을 포함한 티켓 검색"""
        try:
            results = []

            # 1. 기본 메일 검색
            mail_results = self.vector_db.search_similar_mails(query, n_results)
            for mail_result in mail_results:
                ticket_info = {
                    'source': 'email',
                    'ticket_id': mail_result.ticket_id,
                    'content': f"제목: {mail_result.subject}\n내용: {mail_result.body[:200]}...",
                    'similarity_score': getattr(mail_result, 'similarity_score', 0.0),
                    'attachments': []
                }

                # 해당 티켓의 첨부파일 정보 추가
                if include_attachments and mail_result.ticket_id:
                    ticket_attachments = self.vector_db.get_attachments_by_ticket(mail_result.ticket_id)
                    ticket_info['attachments'] = ticket_attachments

                results.append(ticket_info)

            # 2. 첨부파일 검색
            if include_attachments:
                attachment_results = self.vector_db.search_attachment_chunks(query, n_results=n_results)
                for attachment_result in attachment_results:
                    metadata = attachment_result['metadata']
                    ticket_info = {
                        'source': 'attachment',
                        'ticket_id': metadata['ticket_id'],
                        'content': f"첨부파일: {metadata['original_filename']}\n내용: {attachment_result['content'][:200]}...",
                        'similarity_score': attachment_result['similarity_score'],
                        'file_info': {
                            'filename': metadata['original_filename'],
                            'mime_type': metadata['mime_type'],
                            'file_category': metadata['file_category'],
                            'analysis_summary': metadata['analysis_summary']
                        }
                    }
                    results.append(ticket_info)

            # 3. 유사도 순으로 정렬
            results.sort(key=lambda x: x['similarity_score'], reverse=True)

            self.logger.info(f"첨부파일 포함 검색 완료: {len(results)}개 결과")
            return results[:n_results]

        except Exception as e:
            self.logger.error(f"첨부파일 포함 검색 실패: {e}")
            return []

    def get_ticket_attachments(self, ticket_id: str) -> Dict[str, Any]:
        """특정 티켓의 첨부파일 상세 정보 조회"""
        try:
            # Vector DB에서 첨부파일 정보 조회
            attachments = self.vector_db.get_attachments_by_ticket(ticket_id)

            # 통계 정보 생성
            stats = {
                'total_files': len(attachments),
                'total_size': sum(att['file_size'] for att in attachments),
                'file_types': {},
                'categories': {}
            }

            for attachment in attachments:
                # 파일 타입별 통계
                mime_type = attachment['mime_type']
                stats['file_types'][mime_type] = stats['file_types'].get(mime_type, 0) + 1

                # 카테고리별 통계
                category = attachment.get('file_category', 'unknown')
                stats['categories'][category] = stats['categories'].get(category, 0) + 1

            return {
                'ticket_id': ticket_id,
                'attachments': attachments,
                'statistics': stats
            }

        except Exception as e:
            self.logger.error(f"티켓 첨부파일 조회 실패: {e}")
            return {'ticket_id': ticket_id, 'attachments': [], 'statistics': {}}

    def get_attachment_statistics(self) -> Dict[str, Any]:
        """전체 첨부파일 통계 조회"""
        try:
            return self.vector_db.get_attachment_statistics()
        except Exception as e:
            self.logger.error(f"첨부파일 통계 조회 실패: {e}")
            return {}


# 사용 예제
if __name__ == "__main__":
    processor = TicketAttachmentProcessor()

    # 테스트용 이메일 데이터
    test_email = {
        'subject': '서버 에러 보고서',
        'body': '서버에서 오류가 발생했습니다. 로그 파일을 첨부합니다.',
        'sender': 'admin@example.com',
        'received_time': datetime.now().isoformat(),
        'has_attachments': True
    }

    # 첨부파일 포함 티켓 생성
    result = processor.create_ticket_with_attachments(test_email)
    if result:
        print(f"티켓 생성 완료: {result.ticket_id}")
        print(f"첨부파일 수: {len(result.attachments)}")
        print(f"첨부파일 요약:\n{result.attachment_summary}")
    else:
        print("티켓 생성 실패")