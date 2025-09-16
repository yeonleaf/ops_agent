#!/usr/bin/env python3
"""
첨부파일 관련 UI 컴포넌트
"""

import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime
import base64

from ticket_with_attachments import TicketAttachmentProcessor
from module.logging_config import get_logger


class AttachmentUIManager:
    """첨부파일 UI 관리 클래스"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.attachment_processor = TicketAttachmentProcessor()

    def display_attachment_summary(self, ticket_id: str) -> None:
        """티켓의 첨부파일 요약 표시"""
        try:
            attachment_info = self.attachment_processor.get_ticket_attachments(ticket_id)

            if not attachment_info['attachments']:
                st.info("📎 이 티켓에는 첨부파일이 없습니다.")
                return

            attachments = attachment_info['attachments']
            stats = attachment_info['statistics']

            # 첨부파일 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("첨부파일 수", stats['total_files'])
            with col2:
                st.metric("총 크기", self._format_file_size(stats['total_size']))
            with col3:
                file_types = list(stats['file_types'].keys())
                st.metric("파일 형식", f"{len(file_types)}개")

            # 첨부파일 목록
            st.subheader("📎 첨부파일 목록")

            for i, attachment in enumerate(attachments):
                with st.expander(f"📄 {attachment['original_filename']}", expanded=False):
                    # 파일 정보
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**파일 크기:** {self._format_file_size(attachment['file_size'])}")
                        st.write(f"**파일 형식:** {attachment['mime_type']}")
                        if attachment.get('file_category'):
                            st.write(f"**카테고리:** {attachment['file_category']}")

                    with col2:
                        if attachment.get('business_relevance'):
                            st.write(f"**업무 관련성:** {attachment['business_relevance']}")
                        if attachment.get('created_at'):
                            created_at = datetime.fromisoformat(attachment['created_at'].replace('Z', '+00:00'))
                            st.write(f"**처리 시간:** {created_at.strftime('%Y-%m-%d %H:%M:%S')}")

                    # LLM 분석 결과
                    if attachment.get('analysis_summary'):
                        st.write("**AI 분석 요약:**")
                        st.info(attachment['analysis_summary'])

                    # 키워드
                    if attachment.get('keywords'):
                        st.write("**주요 키워드:**")
                        keywords_html = " ".join([
                            f'<span style="background-color: #e1f5fe; padding: 2px 6px; border-radius: 3px; margin: 2px;">{keyword}</span>'
                            for keyword in attachment['keywords']
                        ])
                        st.markdown(keywords_html, unsafe_allow_html=True)

                    # 파일 내용 (청크별)
                    if attachment.get('chunks'):
                        st.write("**파일 내용:**")
                        content_preview = ""
                        for chunk in attachment['chunks'][:3]:  # 최대 3개 청크만 표시
                            content_preview += chunk['content'][:200] + "...\n\n"

                        if content_preview:
                            st.text_area(
                                "내용 미리보기",
                                value=content_preview,
                                height=150,
                                key=f"content_{ticket_id}_{i}"
                            )

                        if len(attachment['chunks']) > 3:
                            st.caption(f"({len(attachment['chunks'])-3}개 추가 청크 생략)")

        except Exception as e:
            self.logger.error(f"첨부파일 요약 표시 실패: {e}")
            st.error("첨부파일 정보를 불러올 수 없습니다.")

    def display_attachment_search_results(self, search_results: List[Dict[str, Any]]) -> None:
        """첨부파일 검색 결과 표시"""
        try:
            if not search_results:
                st.info("검색 결과가 없습니다.")
                return

            # 결과를 소스별로 분류
            email_results = [r for r in search_results if r['source'] == 'email']
            attachment_results = [r for r in search_results if r['source'] == 'attachment']

            # 탭으로 분리 표시
            tab1, tab2 = st.tabs([f"📧 이메일 결과 ({len(email_results)})", f"📎 첨부파일 결과 ({len(attachment_results)})"])

            with tab1:
                self._display_email_search_results(email_results)

            with tab2:
                self._display_attachment_search_results(attachment_results)

        except Exception as e:
            self.logger.error(f"검색 결과 표시 실패: {e}")
            st.error("검색 결과를 표시할 수 없습니다.")

    def _display_email_search_results(self, results: List[Dict[str, Any]]) -> None:
        """이메일 검색 결과 표시"""
        for i, result in enumerate(results):
            similarity_score = result.get('similarity_score', 0.0)

            with st.container():
                # 헤더
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.subheader(f"📧 티켓 ID: {result.get('ticket_id', 'N/A')}")
                with col2:
                    st.metric("유사도", f"{similarity_score:.3f}")

                # 내용
                st.write(result.get('content', ''))

                # 첨부파일 정보
                attachments = result.get('attachments', [])
                if attachments:
                    st.write(f"📎 **첨부파일:** {len(attachments)}개")
                    with st.expander("첨부파일 목록 보기"):
                        for attachment in attachments:
                            st.write(f"• {attachment['original_filename']} ({self._format_file_size(attachment['file_size'])})")

                st.divider()

    def _display_attachment_search_results(self, results: List[Dict[str, Any]]) -> None:
        """첨부파일 검색 결과 표시"""
        for i, result in enumerate(results):
            similarity_score = result.get('similarity_score', 0.0)
            file_info = result.get('file_info', {})

            with st.container():
                # 헤더
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.subheader(f"📎 {file_info.get('filename', 'Unknown File')}")
                    st.caption(f"티켓 ID: {result.get('ticket_id', 'N/A')}")
                with col2:
                    st.metric("유사도", f"{similarity_score:.3f}")

                # 파일 정보
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**파일 형식:** {file_info.get('mime_type', 'unknown')}")
                with col2:
                    st.write(f"**카테고리:** {file_info.get('file_category', 'unknown')}")

                # AI 분석 요약
                if file_info.get('analysis_summary'):
                    st.write("**AI 분석:**")
                    st.info(file_info['analysis_summary'])

                # 매칭된 내용
                st.write("**매칭된 내용:**")
                st.text_area(
                    "내용",
                    value=result.get('content', ''),
                    height=100,
                    key=f"attachment_content_{i}"
                )

                st.divider()

    def display_attachment_statistics(self) -> None:
        """전체 첨부파일 통계 대시보드"""
        try:
            stats = self.attachment_processor.get_attachment_statistics()

            if not stats:
                st.info("첨부파일 통계 정보가 없습니다.")
                return

            st.header("📊 첨부파일 통계")

            # 전체 통계
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("전체 청크", stats.get('total_chunks', 0))
            with col2:
                st.metric("전체 파일", stats.get('total_files', 0))
            with col3:
                avg_chunks = stats.get('total_chunks', 0) / max(stats.get('total_files', 1), 1)
                st.metric("평균 청크/파일", f"{avg_chunks:.1f}")
            with col4:
                st.metric("파일 형식", len(stats.get('file_types', {})))

            # 파일 형식별 통계
            st.subheader("📄 파일 형식별 분포")
            file_types = stats.get('file_types', {})
            if file_types:
                # 파이 차트 데이터 준비
                chart_data = [{'type': k, 'count': v} for k, v in file_types.items()]
                st.bar_chart({item['type']: item['count'] for item in chart_data})

            # 카테고리별 통계
            st.subheader("📂 카테고리별 분포")
            categories = stats.get('file_categories', {})
            if categories:
                col1, col2 = st.columns(2)
                with col1:
                    for category, count in categories.items():
                        st.write(f"**{category}:** {count}개")

            # 업무 관련성별 통계
            st.subheader("💼 업무 관련성별 분포")
            business_relevance = stats.get('business_relevance', {})
            if business_relevance:
                relevance_colors = {
                    '높음': '#4CAF50',
                    '보통': '#FF9800',
                    '낮음': '#F44336'
                }

                for relevance, count in business_relevance.items():
                    color = relevance_colors.get(relevance, '#9E9E9E')
                    st.write(f"<span style='color: {color}'>**{relevance}:**</span> {count}개",
                            unsafe_allow_html=True)

        except Exception as e:
            self.logger.error(f"첨부파일 통계 표시 실패: {e}")
            st.error("통계 정보를 불러올 수 없습니다.")

    def create_attachment_search_interface(self) -> Optional[List[Dict[str, Any]]]:
        """첨부파일 검색 인터페이스"""
        try:
            st.subheader("🔍 첨부파일 검색")

            with st.form("attachment_search_form"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    query = st.text_input(
                        "검색어",
                        placeholder="첨부파일에서 찾고 싶은 내용을 입력하세요...",
                        help="파일 내용, 파일명, 키워드 등으로 검색할 수 있습니다."
                    )

                with col2:
                    n_results = st.number_input("결과 수", min_value=1, max_value=20, value=5)

                # 검색 옵션
                col1, col2 = st.columns(2)
                with col1:
                    include_email = st.checkbox("이메일 내용 포함", value=True)
                with col2:
                    include_attachments = st.checkbox("첨부파일 내용 포함", value=True)

                submitted = st.form_submit_button("검색", use_container_width=True)

                if submitted and query:
                    with st.spinner("검색 중..."):
                        results = self.attachment_processor.search_tickets_with_attachments(
                            query=query,
                            include_attachments=include_attachments,
                            n_results=n_results
                        )

                        if results:
                            st.success(f"검색 완료: {len(results)}개 결과")
                            return results
                        else:
                            st.warning("검색 결과가 없습니다.")
                            return []

            return None

        except Exception as e:
            self.logger.error(f"첨부파일 검색 인터페이스 오류: {e}")
            st.error("검색 인터페이스 오류가 발생했습니다.")
            return None

    def _format_file_size(self, size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def display_file_download_button(self, file_path: str, filename: str) -> None:
        """파일 다운로드 버튼 표시 (향후 구현)"""
        try:
            # 실제 파일 다운로드 기능은 보안상 제한될 수 있음
            st.button(f"📥 다운로드: {filename}", disabled=True, help="파일 다운로드는 보안상 제한됩니다.")
        except Exception as e:
            self.logger.error(f"다운로드 버튼 표시 실패: {e}")


# 사용 예제
if __name__ == "__main__":
    # Streamlit 앱에서 사용하는 방법
    ui_manager = AttachmentUIManager()

    # 첨부파일 통계 대시보드
    if st.button("첨부파일 통계 보기"):
        ui_manager.display_attachment_statistics()

    # 첨부파일 검색
    st.header("첨부파일 검색")
    search_results = ui_manager.create_attachment_search_interface()
    if search_results:
        ui_manager.display_attachment_search_results(search_results)