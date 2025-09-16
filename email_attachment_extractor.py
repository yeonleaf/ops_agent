#!/usr/bin/env python3
"""
이메일에서 첨부파일을 추출하는 유틸리티
"""

import base64
import re
import email
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from module.logging_config import get_logger


@dataclass
class ExtractedAttachment:
    """추출된 첨부파일 정보"""
    filename: str
    mime_type: str
    content: bytes
    size: int
    content_id: Optional[str] = None  # 인라인 이미지용
    is_inline: bool = False


class EmailAttachmentExtractor:
    """이메일 첨부파일 추출기"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def extract_attachments_from_raw_email(self, raw_email: str) -> List[ExtractedAttachment]:
        """원시 이메일 데이터에서 첨부파일 추출"""
        try:
            # 이메일 파싱
            msg = email.message_from_string(raw_email)
            return self.extract_attachments_from_message(msg)

        except Exception as e:
            self.logger.error(f"원시 이메일에서 첨부파일 추출 실패: {e}")
            return []

    def extract_attachments_from_message(self, msg: email.message.Message) -> List[ExtractedAttachment]:
        """이메일 메시지 객체에서 첨부파일 추출"""
        attachments = []

        try:
            if msg.is_multipart():
                for part in msg.walk():
                    attachment = self._process_email_part(part)
                    if attachment:
                        attachments.append(attachment)
            else:
                # 단일 파트 메시지
                attachment = self._process_email_part(msg)
                if attachment:
                    attachments.append(attachment)

            self.logger.info(f"이메일에서 {len(attachments)}개 첨부파일 추출")
            return attachments

        except Exception as e:
            self.logger.error(f"이메일 메시지에서 첨부파일 추출 실패: {e}")
            return []

    def _process_email_part(self, part: email.message.Message) -> Optional[ExtractedAttachment]:
        """이메일 파트 처리"""
        try:
            # Content-Disposition 헤더 확인
            disposition = part.get('Content-Disposition', '')
            content_type = part.get_content_type()

            # 첨부파일인지 확인
            if 'attachment' in disposition or 'inline' in disposition:
                filename = self._get_filename_from_part(part)
                if not filename:
                    filename = f"attachment_{hash(part.get_payload())}.dat"

                # 콘텐츠 추출
                payload = part.get_payload(decode=True)
                if payload is None:
                    return None

                # Content-ID 확인 (인라인 이미지)
                content_id = part.get('Content-ID')
                is_inline = 'inline' in disposition

                return ExtractedAttachment(
                    filename=filename,
                    mime_type=content_type,
                    content=payload,
                    size=len(payload),
                    content_id=content_id,
                    is_inline=is_inline
                )

            return None

        except Exception as e:
            self.logger.error(f"이메일 파트 처리 실패: {e}")
            return None

    def _get_filename_from_part(self, part: email.message.Message) -> Optional[str]:
        """이메일 파트에서 파일명 추출"""
        try:
            # Content-Disposition에서 filename 추출
            disposition = part.get('Content-Disposition', '')
            if disposition:
                filename = part.get_filename()
                if filename:
                    return filename

            # Content-Type에서 name 파라미터 추출
            content_type = part.get('Content-Type', '')
            name_match = re.search(r'name="?([^"]+)"?', content_type)
            if name_match:
                return name_match.group(1)

            return None

        except Exception as e:
            self.logger.error(f"파일명 추출 실패: {e}")
            return None

    def extract_base64_attachments_from_text(self, text: str) -> List[Dict[str, str]]:
        """텍스트에서 base64로 인코딩된 첨부파일 데이터 추출"""
        try:
            # base64 패턴 찾기 (긴 base64 문자열)
            base64_pattern = r'[A-Za-z0-9+/]{100,}={0,2}'
            matches = re.findall(base64_pattern, text)

            base64_attachments = []
            for i, match in enumerate(matches):
                try:
                    # base64 디코딩 시도
                    decoded = base64.b64decode(match)

                    # 파일 시그니처로 타입 추정
                    file_type = self._guess_file_type_from_content(decoded)

                    base64_attachments.append({
                        'base64_data': match,
                        'estimated_type': file_type,
                        'size': len(decoded),
                        'filename': f'extracted_attachment_{i}.{file_type.split("/")[-1] if "/" in file_type else "bin"}'
                    })

                except Exception:
                    # 유효하지 않은 base64는 건너뛰기
                    continue

            self.logger.info(f"텍스트에서 {len(base64_attachments)}개 base64 첨부파일 발견")
            return base64_attachments

        except Exception as e:
            self.logger.error(f"base64 첨부파일 추출 실패: {e}")
            return []

    def _guess_file_type_from_content(self, content: bytes) -> str:
        """파일 내용에서 MIME 타입 추정"""
        try:
            # 파일 시그니처 확인
            if content.startswith(b'\x89PNG'):
                return 'image/png'
            elif content.startswith(b'\xFF\xD8\xFF'):
                return 'image/jpeg'
            elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
                return 'image/gif'
            elif content.startswith(b'%PDF'):
                return 'application/pdf'
            elif content.startswith(b'PK\x03\x04'):
                # ZIP 계열 파일 (Office 문서 포함)
                if b'word/' in content[:1000]:
                    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                elif b'xl/' in content[:1000]:
                    return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif b'ppt/' in content[:1000]:
                    return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                else:
                    return 'application/zip'
            elif content.startswith(b'\xD0\xCF\x11\xE0'):
                return 'application/msword'  # 레거시 Office 문서
            else:
                # 텍스트 파일인지 확인
                try:
                    content.decode('utf-8')
                    return 'text/plain'
                except UnicodeDecodeError:
                    return 'application/octet-stream'

        except Exception as e:
            self.logger.error(f"파일 타입 추정 실패: {e}")
            return 'application/octet-stream'

    def extract_attachments_from_mail_data(self, mail_data: Dict) -> List[Dict[str, str]]:
        """메일 데이터에서 첨부파일 정보 추출"""
        try:
            attachments = []

            # Gmail API 형태의 메일 데이터에서 첨부파일 추출
            if 'payload' in mail_data:
                payload = mail_data['payload']
                attachments.extend(self._extract_from_gmail_payload(payload))

            # Outlook/Graph API 형태의 메일 데이터
            elif 'attachments' in mail_data:
                for attachment in mail_data['attachments']:
                    if 'contentBytes' in attachment:
                        attachments.append({
                            'base64_data': attachment['contentBytes'],
                            'filename': attachment.get('name', 'attachment'),
                            'mime_type': attachment.get('contentType', 'application/octet-stream'),
                            'size': attachment.get('size', 0)
                        })

            # 메일 본문에서 base64 데이터 추출
            body = mail_data.get('body', '')
            if isinstance(body, dict):
                body = body.get('content', '') or body.get('data', '')

            if body:
                base64_attachments = self.extract_base64_attachments_from_text(body)
                attachments.extend(base64_attachments)

            self.logger.info(f"메일 데이터에서 {len(attachments)}개 첨부파일 추출")
            return attachments

        except Exception as e:
            self.logger.error(f"메일 데이터에서 첨부파일 추출 실패: {e}")
            return []

    def _extract_from_gmail_payload(self, payload: Dict) -> List[Dict[str, str]]:
        """Gmail payload에서 첨부파일 추출"""
        attachments = []

        try:
            # 멀티파트 메시지
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('filename') and 'data' in part.get('body', {}):
                        attachments.append({
                            'base64_data': part['body']['data'],
                            'filename': part['filename'],
                            'mime_type': part.get('mimeType', 'application/octet-stream'),
                            'size': part['body'].get('size', 0)
                        })
                    elif 'parts' in part:
                        # 중첩된 파트 처리
                        attachments.extend(self._extract_from_gmail_payload(part))

            # 단일 파트에 첨부파일이 있는 경우
            elif payload.get('filename') and 'data' in payload.get('body', {}):
                attachments.append({
                    'base64_data': payload['body']['data'],
                    'filename': payload['filename'],
                    'mime_type': payload.get('mimeType', 'application/octet-stream'),
                    'size': payload['body'].get('size', 0)
                })

        except Exception as e:
            self.logger.error(f"Gmail payload 처리 실패: {e}")

        return attachments


# 사용 예제
if __name__ == "__main__":
    extractor = EmailAttachmentExtractor()

    # 테스트용 메일 데이터
    test_mail = {
        'body': 'SGVsbG8gV29ybGQhIFRoaXMgaXMgYSB0ZXN0IGZpbGUgY29udGVudC4='  # "Hello World! This is a test file content."
    }

    attachments = extractor.extract_attachments_from_mail_data(test_mail)
    print(f"추출된 첨부파일: {len(attachments)}개")
    for attachment in attachments:
        print(f"- {attachment['filename']} ({attachment['estimated_type']}, {attachment['size']} bytes)")