#!/usr/bin/env python3
"""
HTML 텍스트 정제기
JIRA description의 HTML을 깨끗한 텍스트로 변환
"""

import re
import html
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import html2text


class JiraHTMLCleaner:
    """JIRA HTML 콘텐츠 정제기"""
    
    def __init__(self):
        """초기화"""
        # html2text 설정
        self.html2text_converter = html2text.HTML2Text()
        self.html2text_converter.ignore_links = True  # 링크 무시
        self.html2text_converter.ignore_images = True  # 이미지 무시
        self.html2text_converter.body_width = 0  # 줄바꿈 비활성화
        self.html2text_converter.unicode_snob = True  # 유니코드 처리
        self.html2text_converter.escape_all = False  # 이스케이프 비활성화
        
        # JIRA 특수 패턴들
        self.jira_patterns = [
            # JIRA 이미지 경로
            r'/plugins/servlet/jeditor_ck_provider\.jsp\?file=[^"\']*',
            # JIRA 사용자 멘션
            r'\[~[^\]]+\]',
            # JIRA 티켓 링크
            r'\[[A-Z]+-\d+\]',
            # 빈 셀들
            r'&nbsp;',
            # 연속된 공백
            r'\s+',
        ]
    
    def clean_html_to_text(self, html_content: str) -> str:
        """
        HTML을 깨끗한 텍스트로 변환
        
        Args:
            html_content: 원본 HTML 콘텐츠
            
        Returns:
            정제된 텍스트
        """
        if not html_content or not html_content.strip():
            return ""
        
        try:
            # 1단계: HTML 엔티티 디코딩
            decoded = html.unescape(html_content)
            
            # 2단계: BeautifulSoup으로 HTML 파싱 및 정제
            cleaned_html = self._clean_html_structure(decoded)
            
            # 3단계: html2text로 마크다운 변환
            markdown_text = self.html2text_converter.handle(cleaned_html)
            
            # 4단계: JIRA 특수 패턴 정제
            cleaned_text = self._clean_jira_patterns(markdown_text)
            
            # 5단계: 최종 텍스트 정리
            final_text = self._finalize_text(cleaned_text)
            
            return final_text
            
        except Exception as e:
            # HTML 파싱 실패 시 폴백: 간단한 태그 제거
            return self._fallback_clean(html_content)
    
    def _clean_html_structure(self, html_content: str) -> str:
        """HTML 구조 정제"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 이미지 태그 제거
            for img in soup.find_all('img'):
                img.decompose()
            
            # 스타일 태그와 스크립트 제거
            for tag in soup.find_all(['style', 'script']):
                tag.decompose()
            
            # 테이블을 읽기 쉬운 형태로 변환
            self._convert_tables(soup)
            
            # 리스트를 읽기 쉬운 형태로 변환
            self._convert_lists(soup)
            
            return str(soup)
            
        except Exception:
            return html_content
    
    def _convert_tables(self, soup: BeautifulSoup):
        """테이블을 읽기 쉬운 텍스트로 변환"""
        for table in soup.find_all('table'):
            # 테이블 헤더 추출
            headers = []
            header_row = table.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    text = th.get_text(strip=True)
                    if text and text != '&nbsp;':
                        headers.append(text)
            
            # 테이블 데이터 추출
            rows_data = []
            for row in table.find_all('tr')[1:]:  # 헤더 제외
                row_data = []
                for cell in row.find_all(['td', 'th']):
                    text = cell.get_text(strip=True)
                    if text and text != '&nbsp;':
                        row_data.append(text)
                
                # 의미있는 데이터가 있는 행만 추가
                if any(data.strip() for data in row_data if data != '&nbsp;'):
                    rows_data.append(row_data)
            
            # 테이블을 텍스트로 변환
            table_text = self._format_table_as_text(headers, rows_data)
            
            # 원본 테이블을 텍스트로 교체
            table.replace_with(soup.new_string(table_text))
    
    def _format_table_as_text(self, headers: List[str], rows: List[List[str]]) -> str:
        """테이블 데이터를 읽기 쉬운 텍스트로 포맷"""
        if not rows:
            return ""
        
        lines = []
        
        # 헤더가 있으면 추가
        if headers:
            lines.append("표:")
            lines.append(" | ".join(headers))
            lines.append("-" * 50)
        
        # 데이터 행 추가
        for row in rows:
            if row and any(cell.strip() for cell in row):
                # 빈 값 필터링
                filtered_row = [cell for cell in row if cell.strip() and cell != '&nbsp;']
                if filtered_row:
                    lines.append(" | ".join(filtered_row))
        
        return "\n".join(lines) + "\n"
    
    def _convert_lists(self, soup: BeautifulSoup):
        """리스트를 읽기 쉬운 형태로 변환"""
        # 순서없는 리스트
        for ul in soup.find_all('ul'):
            items = []
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    items.append(f"• {text}")
            
            if items:
                list_text = "\n".join(items) + "\n"
                ul.replace_with(soup.new_string(list_text))
        
        # 순서있는 리스트
        for ol in soup.find_all('ol'):
            items = []
            for i, li in enumerate(ol.find_all('li'), 1):
                text = li.get_text(strip=True)
                if text:
                    items.append(f"{i}. {text}")
            
            if items:
                list_text = "\n".join(items) + "\n"
                ol.replace_with(soup.new_string(list_text))
    
    def _clean_jira_patterns(self, text: str) -> str:
        """JIRA 특수 패턴 정제"""
        cleaned = text
        
        # JIRA 사용자 멘션을 읽기 쉽게 변환
        cleaned = re.sub(r'\[~([^\]]+)\]', r'@\1', cleaned)
        
        # JIRA 이미지 경로 제거
        cleaned = re.sub(r'/plugins/servlet/jeditor_ck_provider\.jsp\?[^"\'\s]*', '', cleaned)
        
        # 빈 링크나 이미지 태그 제거
        cleaned = re.sub(r'!\[\]\([^)]*\)', '', cleaned)  # 빈 이미지
        cleaned = re.sub(r'\[\]\([^)]*\)', '', cleaned)   # 빈 링크
        
        # &nbsp; 제거
        cleaned = re.sub(r'&nbsp;', ' ', cleaned)
        
        return cleaned
    
    def _finalize_text(self, text: str) -> str:
        """최종 텍스트 정리"""
        # 연속된 공백을 단일 공백으로
        text = re.sub(r'\s+', ' ', text)
        
        # 연속된 줄바꿈을 최대 2개로 제한
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 시작과 끝 공백 제거
        text = text.strip()
        
        # 너무 긴 텍스트는 제한 (임베딩 토큰 고려)
        if len(text) > 2000:
            text = text[:2000] + "..."
        
        return text
    
    def _fallback_clean(self, html_content: str) -> str:
        """HTML 파싱 실패 시 폴백 정제"""
        # 간단한 태그 제거
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        # 기본 정리
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        if len(text) > 2000:
            text = text[:2000] + "..."
        
        return text
    
    def extract_table_data(self, html_content: str) -> List[Dict[str, str]]:
        """
        테이블 데이터를 구조화된 형태로 추출
        (별도 분석이 필요한 경우 사용)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tables_data = []
            
            for table in soup.find_all('table'):
                # 헤더 추출
                headers = []
                header_row = table.find('tr')
                if header_row:
                    for th in header_row.find_all(['th', 'td']):
                        text = th.get_text(strip=True)
                        headers.append(text if text != '&nbsp;' else '')
                
                # 데이터 행 추출
                rows = []
                for row in table.find_all('tr')[1:]:
                    row_data = {}
                    cells = row.find_all(['td', 'th'])
                    
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        header = headers[i] if i < len(headers) else f'col_{i}'
                        row_data[header] = text if text != '&nbsp;' else ''
                    
                    if any(value.strip() for value in row_data.values()):
                        rows.append(row_data)
                
                if rows:
                    tables_data.append({
                        'headers': headers,
                        'rows': rows
                    })
            
            return tables_data
            
        except Exception:
            return []


# 테스트 함수
def test_html_cleaner():
    """HTML 정제기 테스트"""
    print("🧪 HTML 정제기 테스트")
    print("=" * 50)
    
    cleaner = JiraHTMLCleaner()
    
    # 실제 JIRA HTML 샘플 (저장된 파일에서 가져온 것)
    sample_html = '''<p dir="auto"><span style="display:inline; float:none"><img alt="Attention" height="24" src="/plugins/servlet/jeditor_ck_provider.jsp?file=plugins/smiley/images/exclamation.png" title="Attention" width="24">반드시 아래 양식에 맞게 입력 부탁드립니다.</span></p>

<table border="1" cellspacing="0" class="jeditorTable" style="border-collapse:collapse; border:1px solid">
    <tbody>
        <tr>
            <td dir="auto" rowspan="2" style="text-align:center">구분</td>
            <td dir="auto" rowspan="2" style="text-align:center">SKB 담당자</td>
            <td dir="auto" rowspan="2" style="text-align:center">사용자 소속</td>
            <td dir="auto" rowspan="2" style="text-align:center">사용자 이름</td>
            <td dir="auto" rowspan="2" style="text-align:center">VPN 계정</td>
            <td colspan="3" dir="auto" style="text-align:center">신청일자</td>
            <td colspan="2" dir="auto" style="text-align:center">사용시간</td>
            <td dir="auto" rowspan="2" style="text-align:center">접속사유</td>
        </tr>
        <tr>
            <td dir="auto">년</td>
            <td dir="auto">월</td>
            <td dir="auto">일</td>
            <td dir="auto">시작</td>
            <td dir="auto">종료</td>
        </tr>
        <tr>
            <td dir="auto">1</td>
            <td dir="auto">탁현종</td>
            <td dir="auto">SKAX</td>
            <td dir="auto">이경범</td>
            <td dir="auto">skb3069_04</td>
            <td dir="auto">2025</td>
            <td dir="auto">08</td>
            <td dir="auto">14</td>
            <td dir="auto">00</td>
            <td dir="auto">08</td>
            <td dir="auto">NCMS PM</td>
        </tr>
    </tbody>
</table>'''
    
    print("📝 원본 HTML:")
    print(sample_html[:200] + "...")
    print(f"길이: {len(sample_html)} 문자")
    
    print("\n🔧 정제 중...")
    cleaned_text = cleaner.clean_html_to_text(sample_html)
    
    print("\n✨ 정제된 텍스트:")
    print(cleaned_text)
    print(f"길이: {len(cleaned_text)} 문자")
    
    print(f"\n📊 압축률: {((len(sample_html) - len(cleaned_text)) / len(sample_html) * 100):.1f}%")
    
    # 테이블 데이터 추출 테스트
    print("\n📋 구조화된 테이블 데이터:")
    tables = cleaner.extract_table_data(sample_html)
    for i, table in enumerate(tables, 1):
        print(f"테이블 {i}:")
        print(f"  헤더: {table['headers']}")
        print(f"  행 수: {len(table['rows'])}")
        if table['rows']:
            print(f"  첫 번째 행: {table['rows'][0]}")


if __name__ == "__main__":
    test_html_cleaner()