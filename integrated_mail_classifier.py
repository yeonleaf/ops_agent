#!/usr/bin/env python3
"""
통합 메일 분류기
4개의 기존 분류기를 조합하고 LM이 최종 판단을 내리는 시스템
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import streamlit as st

# 기존 분류기들 임포트
from email_domain_classifier import EmailDomainClassifier, EmailType
from enhanced_content_extractor import EnhancedContentExtractor
from simple_mail_processor import SimpleMailProcessor

# LangChain 임포트
try:
    from langchain.schema import HumanMessage, SystemMessage
    from langchain_openai import AzureChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    st.warning("LangChain을 사용할 수 없습니다. 기본 분류 로직만 사용됩니다.")

class MailCategory(str, Enum):
    """메일 카테고리"""
    WORK_URGENT = "work_urgent"      # 긴급 업무
    WORK_NORMAL = "work_normal"       # 일반 업무
    WORK_LOW = "work_low"            # 낮은 우선순위 업무
    PERSONAL = "personal"             # 개인 메일
    NOTIFICATION = "notification"     # 알림/공지
    SPAM = "spam"                    # 스팸
    UNKNOWN = "unknown"              # 미분류

class MailPriority(str, Enum):
    """메일 우선순위"""
    CRITICAL = "critical"            # 긴급
    HIGH = "high"                    # 높음
    MEDIUM = "medium"                # 보통
    LOW = "low"                      # 낮음

class TicketCreationStatus(str, Enum):
    """티켓 생성 상태"""
    SHOULD_CREATE = "should_create"      # 티켓 생성해야 함
    ALREADY_EXISTS = "already_exists"    # 이미 티켓이 존재함
    NO_TICKET_NEEDED = "no_ticket_needed"  # 티켓 생성 불필요

class IntegratedMailClassifier:
    """통합 메일 분류기"""
    
    def __init__(self, use_lm: bool = True):
        """초기화"""
        self.use_lm = use_lm and LANGCHAIN_AVAILABLE
        
        # 기존 분류기들 초기화
        self.domain_classifier = EmailDomainClassifier(
            internal_domains=["@skcc.com", "@sk.com", "@skbroadband.com"],
            external_domains=["@gmail.com", "@naver.com", "@daum.net"]
        )
        self.content_extractor = EnhancedContentExtractor()
        self.mail_processor = SimpleMailProcessor()
        
        # LM 모델 초기화 (사용 가능한 경우)
        self.llm = None
        if self.use_lm:
            self._initialize_llm()
        
        # 분류 결과 캐시
        self.classification_cache = {}
    
    def _initialize_llm(self):
        """LLM 모델 초기화"""
        try:
            # Azure OpenAI 설정 확인
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
            
            # 디버깅 정보 표시
            st.error(f"🔧 Azure OpenAI 설정 확인:")
            st.error(f"   - Endpoint: {azure_endpoint}")
            st.error(f"   - API Key: {'설정됨' if azure_api_key else '설정 안됨'}")
            st.error(f"   - Deployment: {azure_deployment}")
            st.error(f"   - API Version: {azure_api_version}")
            
            if all([azure_endpoint, azure_api_key, azure_deployment]):
                # 환경 변수 설정 (LangChain이 자동으로 읽도록)
                os.environ["OPENAI_API_KEY"] = azure_api_key
                os.environ["OPENAI_API_BASE"] = azure_endpoint
                os.environ["OPENAI_API_VERSION"] = azure_api_version
                
                # Azure OpenAI 전용 환경 변수도 설정
                os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
                os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
                os.environ["AZURE_OPENAI_API_VERSION"] = azure_api_version
                
                st.error(f"   🔧 환경 변수 설정 완료:")
                st.error(f"      - OPENAI_API_KEY: {'설정됨' if os.getenv('OPENAI_API_KEY') else '설정 안됨'}")
                st.error(f"      - OPENAI_API_BASE: {'설정됨' if os.getenv('OPENAI_API_BASE') else '설정 안됨'}")
                st.error(f"      - OPENAI_API_VERSION: {'설정됨' if os.getenv('OPENAI_API_VERSION') else '설정 안됨'}")
                
                # URL 구성 확인
                st.error(f"   🌐 URL 구성 확인:")
                st.error(f"      - 원본 Endpoint: {azure_endpoint}")
                st.error(f"      - Deployment: {azure_deployment}")
                st.error(f"      - 예상 API URL: {azure_endpoint}/openai/deployments/{azure_deployment}/chat/completions?api-version={azure_api_version}")
                
                # URL 정리 (trailing slash 제거)
                clean_endpoint = azure_endpoint.rstrip('/')
                st.error(f"      - 정리된 Endpoint: {clean_endpoint}")
                st.error(f"      - 정리된 API URL: {clean_endpoint}/openai/deployments/{azure_deployment}/chat/completions?api-version={azure_api_version}")
                
                try:
                    # AzureChatOpenAI 사용 (Azure OpenAI API에 최적화)
                    clean_endpoint = azure_endpoint.rstrip('/')
                    self.llm = AzureChatOpenAI(
                        deployment_name=azure_deployment,
                        azure_endpoint=clean_endpoint,
                        api_key=azure_api_key,
                        api_version=azure_api_version,
                        temperature=0.1
                    )
                    st.success("✅ LLM 모델 초기화 완료 (AzureChatOpenAI)")
                    self.use_lm = True
                except Exception as e:
                    st.error(f"❌ LLM 모델 초기화 실패: {str(e)}")
                    st.error("💡 해결 방법:")
                    st.error("   1. Azure OpenAI 리소스가 활성화되어 있는지 확인")
                    st.error("   2. Deployment 이름이 정확한지 확인")
                    st.error("   3. Endpoint URL이 올바른지 확인")
                    st.error("   4. API 키가 유효한지 확인")
                    self.use_lm = False
                    self.llm = None
            else:
                st.warning("⚠️ Azure OpenAI 설정이 불완전하여 LLM을 사용할 수 없습니다.")
                self.use_lm = False
                self.llm = None
                
        except Exception as e:
            st.error(f"❌ LLM 초기화 실패: {str(e)}")
            self.use_lm = False
            self.llm = None
    
    def is_llm_available(self) -> bool:
        """LLM 사용 가능 여부 확인"""
        return self.use_lm and self.llm is not None
    
    def get_llm_status(self) -> Dict[str, Any]:
        """LLM 상태 정보 반환"""
        return {
            'use_lm': self.use_lm,
            'llm_available': self.llm is not None,
            'llm_type': type(self.llm).__name__ if self.llm else None
        }
    
    def should_create_ticket(self, email_data: Dict[str, Any], user_query: str = "") -> Tuple[TicketCreationStatus, str, Dict[str, Any]]:
        """
        LM을 사용하여 해당 메일이 티켓 생성 대상인지 판단
        
        Args:
            email_data: 메일 데이터
            user_query: 사용자 쿼리
            
        Returns:
            (티켓생성상태, 이유, 추가정보) 튜플
        """
        if not self.is_llm_available():
            st.error("❌ LM을 사용할 수 없습니다. Azure OpenAI 설정을 확인해주세요.")
            # LLM을 사용할 수 없는 경우 기본 규칙 적용
            return self._should_create_ticket_fallback(email_data, user_query)
        
        try:
            st.info(f"🧠 LM 기반 티켓 생성 판단 시작:")
            st.info(f"   - 사용자 쿼리: '{user_query}'")
            st.info(f"   - 메일 제목: '{email_data.get('subject', '')}'")
            
            # LM 프롬프트 구성 (개별 메일 내용 기반 판단)
            system_prompt = """당신은 메일 관리 시스템의 티켓 생성 판단 전문가입니다.

개별 메일의 내용을 분석하여 업무 관련 티켓 생성이 필요한지 판단해주세요.

티켓 생성이 필요한 메일:
- 업무 관련 요청이나 지시사항
- 프로젝트 관련 이슈나 작업 요청
- 버그 리포트나 기술적 문제
- 승인이 필요한 업무 프로세스
- 회의 요청이나 일정 조율
- 고객 지원 요청
- 시스템 장애나 문제 보고
- 업무 협업이나 리뷰 요청

티켓 생성이 불필요한 메일:
- 개인적인 안부나 인사
- 단순 정보 공유 (뉴스레터, 공지사항)
- 스팸이나 광고 메일
- 자동 알림 메일 (단순 확인용)
- 개인적인 대화나 잡담

판단 기준:
1. 메일 내용이 업무와 관련이 있는가?
2. 액션이나 응답이 필요한 내용인가?
3. 추적하고 관리해야 할 작업인가?

사용자가 "티켓 목록", "업무 메일" 등을 요청했다면, 업무 관련 메일은 티켓으로 생성해야 합니다.

JSON 형식으로만 응답해주세요:
{
    "should_create_ticket": true/false,
    "reasoning": "판단 근거를 간단히 설명",
    "confidence": 0.0-1.0,
    "detected_intent": "ticket_creation|mail_query|information_request|other",
    "ticket_type": "jira|general|project|issue|other"
}"""

            user_prompt = f"""메일 정보:
제목: {email_data.get('subject', '')}
발신자: {email_data.get('sender', '')}
내용: {email_data.get('body', '')[:500]}...

사용자 요청: "{user_query}"

이 메일 내용이 업무 관련이고 티켓 생성이 필요한 내용인가요?
사용자가 티켓/업무 관련 요청을 했고, 이 메일이 업무 관련이라면 티켓을 생성해야 합니다."""
            
            # LLM 호출
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # 스트리밍 처리
            current_response = ""
            final_response = None
            
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content'):
                    current_response += chunk.content
                    final_response = chunk
            
            response_content = final_response.content if final_response else ""
            
            # JSON 파싱
            import json
            try:
                lm_result = json.loads(response_content)
                
                should_create = lm_result.get('should_create_ticket', False)
                reasoning = lm_result.get('reasoning', '')
                confidence = lm_result.get('confidence', 0.5)
                detected_intent = lm_result.get('detected_intent', 'other')
                ticket_type = lm_result.get('ticket_type', 'general')
                
                st.success(f"   🧠 LM 판단 결과:")
                st.success(f"      - 티켓 생성 필요: {should_create}")
                st.success(f"      - 판단 근거: {reasoning}")
                st.success(f"      - 신뢰도: {confidence}")
                st.success(f"      - 감지된 의도: {detected_intent}")
                st.success(f"      - 티켓 타입: {ticket_type}")
                
                if should_create:
                    # 🎯 LLM이 "티켓 생성 필요"라고 판단한 경우, LLM 판단을 절대적으로 우선시
                    # 키워드 검증은 보조 정보로만 사용 (판단 기준이 아님)
                    email_has_ticket_keywords = self._check_ticket_keywords_in_email(email_data)
                    
                    # Vector DB 확인 (중복 티켓 방지용)
                    email_id_exists = self._check_email_id_in_vector_db(email_data.get('id', ''))
                    
                    if email_id_exists:
                        return TicketCreationStatus.ALREADY_EXISTS, f"LM 판단: {reasoning} (이미 Vector DB에 존재)", {
                            'lm_reasoning': reasoning,
                            'confidence': confidence,
                            'detected_intent': detected_intent,
                            'ticket_type': ticket_type,
                            'email_keywords': email_has_ticket_keywords,
                            'vector_db_status': 'exists'
                        }
                    else:
                        # ✅ LLM 판단을 신뢰하고 티켓 생성 (키워드 검증 결과와 무관)
                        return TicketCreationStatus.SHOULD_CREATE, f"LM 판단: {reasoning}", {
                            'lm_reasoning': reasoning,
                            'confidence': confidence,
                            'detected_intent': detected_intent,
                            'ticket_type': ticket_type,
                            'email_keywords': email_has_ticket_keywords,  # 보조 정보
                            'vector_db_status': 'not_found'
                        }
                else:
                    return TicketCreationStatus.NO_TICKET_NEEDED, f"LM 판단: {reasoning}", {
                        'lm_reasoning': reasoning,
                        'confidence': confidence,
                        'detected_intent': detected_intent,
                        'ticket_type': ticket_type
                    }
                
            except json.JSONDecodeError:
                st.error(f"   ❌ LM 응답 JSON 파싱 실패")
                return self._should_create_ticket_fallback(email_data, user_query)
                
        except Exception as e:
            st.error(f"   ❌ LM 호출 실패: {str(e)}")
            return self._should_create_ticket_fallback(email_data, user_query)
    
    def _should_create_ticket_fallback(self, email_data: Dict[str, Any], user_query: str = "") -> Tuple[TicketCreationStatus, str, Dict[str, Any]]:
        """LLM을 사용할 수 없을 때의 fallback 로직"""
        # 경고 메시지는 한 번만 표시 (첫 번째 호출 시에만)
        if not hasattr(self, '_fallback_warning_shown'):
            st.warning("⚠️ LM을 사용할 수 없어 기본 규칙을 적용합니다.")
            self._fallback_warning_shown = True
        
        # 1단계: 사용자 쿼리에서 명시적 티켓 생성 의도 확인
        query_lower = user_query.lower()
        explicit_ticket_keywords = ['티켓', '일감', '작업', '할일', '일정', '스케줄', '프로젝트', '이슈', '버그']
        
        has_explicit_intent = any(keyword in query_lower for keyword in explicit_ticket_keywords)
        
        if not has_explicit_intent:
            # 정보 메시지도 한 번만 표시
            if not hasattr(self, '_no_intent_info_shown'):
                st.info("ℹ️ 사용자 쿼리에 명시적 티켓 생성 의도가 없습니다.")
                self._no_intent_info_shown = True
                
            return TicketCreationStatus.NO_TICKET_NEEDED, "기본 규칙: 명시적 티켓 생성 의도 없음", {
                'fallback_reason': 'LM 사용 불가 + 명시적 의도 없음',
                'query_analysis': '단순 메일 조회로 판단'
            }
        
        # 2단계: 사용자가 명시적 티켓 생성 의도를 보였다면, 키워드 검증과 무관하게 티켓 생성
        # (LLM 우선시 원칙과 일치)
        email_has_keywords = self._check_ticket_keywords_in_email(email_data)
        
        # 사용자가 명시적 의도를 보였다면, 키워드 검증 결과와 무관하게 티켓 생성
        return TicketCreationStatus.SHOULD_CREATE, "기본 규칙: 명시적 티켓 생성 의도 발견 (LLM 우선시 원칙)", {
            'fallback_reason': 'LM 사용 불가 + 명시적 의도',
            'explicit_intent': True,
            'email_keywords': email_has_keywords,  # 보조 정보
            'llm_priority_principle': '사용자 의도 우선시'
        }
    
    def _check_ticket_keywords_in_email(self, email_data: Dict[str, Any]) -> List[str]:
        """메일 내용에서 티켓 키워드 확인 (LM 판단을 위한 보조 정보)"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        
        found_keywords = []
        content_lower = (subject + " " + body).lower()
        
        # 간단한 키워드 매칭 (LM 판단을 위한 참고용)
        simple_keywords = [
            # 영어 키워드
            'urgent', 'important', 'deadline', 'meeting', 'project', 'task',
            'issue', 'bug', 'error', 'request', 'approve', 'review', 'feedback',
            'action', 'required', 'schedule', 'appointment', 'conference', 'call',
            'report', 'document', 'proposal', 'contract', 'invoice', 'payment',
            'support', 'help', 'problem', 'solution', 'update', 'status',
            
            # 한국어 키워드 (보조 정보용)
            '서버', '접속', '불가', '기능', '제안', '자료', '요청', '프로젝트',
            '문제', '오류', '버그', '개발', '작업', '일정', '회의', '승인',
            '검토', '피드백', '지원', '도움', '해결', '업데이트', '상태',
            '시스템', '장애', '복구', '설정', '변경', '수정', '개선',
            '테스트', '배포', '운영', '모니터링', '로그', '백업', '보안'
        ]
        
        for keyword in simple_keywords:
            if keyword in content_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _generate_labels_for_ticket(self, email_data: Dict[str, Any], classification: Dict[str, Any]) -> List[str]:
        """티켓용 레이블 생성"""
        try:
            labels = []
            
            # 1. 메일 내용에서 키워드 기반 레이블
            subject = email_data.get('subject', '').lower()
            body = email_data.get('body', '').lower()
            content = f"{subject} {body}"
            
            # 우선순위별 레이블 매핑
            priority_labels = {
                'urgent': ['긴급', '긴급사항'],
                'high': ['높음', '중요'],
                'medium': ['보통', '일반'],
                'low': ['낮음', '낮은우선순위']
            }
            
            # 우선순위 레이블 추가
            priority = classification.get('priority', 'medium').lower()
            if priority in priority_labels:
                labels.extend(priority_labels[priority])
            
            # 2. 메일 타입별 레이블
            ticket_type = classification.get('ticket_type', 'general')
            type_labels = {
                'bug_fix': ['버그', '오류', '수정'],
                'feature': ['기능', '개발', '신규'],
                'improvement': ['개선', '향상'],
                'task': ['작업', '일반'],
                'issue': ['이슈', '문제'],
                'project': ['프로젝트', '계획']
            }
            
            if ticket_type in type_labels:
                labels.extend(type_labels[ticket_type])
            
            # 3. 콘텐츠 기반 레이블
            content_keywords = {
                '서버': ['서버', '시스템'],
                '접속': ['접속', '연결', '네트워크'],
                '불가': ['장애', '오류', '문제'],
                '기능': ['기능', '개발', '요청'],
                '제안': ['제안', '아이디어', '개선'],
                '자료': ['자료', '문서', '정보'],
                '요청': ['요청', '요구사항', '필요'],
                '프로젝트': ['프로젝트', '계획', '일정'],
                '회의': ['회의', '미팅', '일정'],
                '승인': ['승인', '검토', '결재'],
                '지원': ['지원', '도움', '문의']
            }
            
            for keyword, label_list in content_keywords.items():
                if keyword in content:
                    labels.extend(label_list)
                    break  # 첫 번째 매칭만 사용
            
            # 4. 도메인 기반 레이블
            domain_type = classification.get('domain_type', 'external')
            if domain_type == 'internal':
                labels.append('내부')
            else:
                labels.append('외부')
            
            # 5. 중복 제거 및 정리
            unique_labels = list(set(labels))
            
            # 6. 기본 레이블이 없으면 추가
            if not unique_labels:
                unique_labels = ['일반', '업무']
            
            return unique_labels[:5]  # 최대 5개 레이블
            
        except Exception as e:
            st.warning(f"레이블 생성 중 오류: {str(e)}")
            return ['일반', '업무']  # 기본값
    
    def _check_email_id_in_vector_db(self, email_id: str) -> bool:
        """Vector DB에서 메일 ID 존재 여부 확인"""
        try:
            # Vector DB 연결 및 검색 로직
            # 현재는 간단한 구현으로 대체
            # TODO: 실제 Vector DB 연동 구현
            
            # 임시로 항상 False 반환 (Vector DB에 없다고 가정)
            return False
            
        except Exception as e:
            st.warning(f"Vector DB 확인 중 오류: {str(e)}")
            return False
    
    def create_ticket_from_email(self, email_data: Dict[str, Any], user_query: str = "") -> Dict[str, Any]:
        """
        메일을 티켓으로 변환 (변환 → 임베딩 → 티켓 생성)
        
        Args:
            email_data: 메일 데이터
            user_query: 사용자 쿼리
            
        Returns:
            티켓 데이터
        """
        try:
            # 1단계: 메일 분류
            classification = self.classify_email(email_data)
            
            # 2단계: 임베딩 생성
            embedding = self._create_embedding(email_data, classification)
            
            # 3단계: VectorDB에 메일 저장 (pending 상태)
            try:
                from vector_db_models import VectorDBManager, Mail
                vector_db = VectorDBManager()
                
                mail = Mail(
                    message_id=email_data.get('id', ''),
                    original_content=email_data.get('body', ''),
                    refined_content=email_data.get('body', '')[:500],
                    sender=email_data.get('sender', ''),
                    status='pending',  # 티켓 생성 시 pending 상태
                    subject=email_data.get('subject', ''),
                    received_datetime=email_data.get('received_date', datetime.now()).isoformat() if hasattr(email_data.get('received_date', datetime.now()), 'isoformat') else datetime.now().isoformat(),
                    content_type='text',
                    has_attachment=False,
                    extraction_method='ticket_creation',
                    content_summary=email_data.get('body', '')[:200],
                    key_points=[],
                    created_at=datetime.now().isoformat()
                )
                
                vector_db.save_mail(mail)
                st.success(f"✅ VectorDB에 메일 저장 완료 (상태: pending)")
                
            except Exception as e:
                st.error(f"VectorDB 저장 실패: {str(e)}")
            
            # 4단계: 티켓 생성
            ticket = self._create_ticket_data(email_data, classification, embedding, user_query)
            
            return ticket
            
        except Exception as e:
            st.error(f"티켓 생성 실패: {str(e)}")
            return {}
    
    def _create_embedding(self, email_data: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
        """메일 내용을 임베딩으로 변환"""
        try:
            # 메일 내용을 임베딩 벡터로 변환
            # 현재는 간단한 구현으로 대체
            # TODO: 실제 임베딩 모델 연동 구현
            
            content = f"{email_data.get('subject', '')} {email_data.get('body', '')}"
            
            # 간단한 해시 기반 임베딩 (실제로는 OpenAI Embedding API 등 사용)
            import hashlib
            embedding_hash = hashlib.md5(content.encode()).hexdigest()
            
            return {
                'content': content,
                'embedding_hash': embedding_hash,
                'vector_dimension': 128,  # 임시 값
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            st.error(f"임베딩 생성 실패: {str(e)}")
            return {}
    
    def _create_ticket_data(self, email_data: Dict[str, Any], classification: Dict[str, Any], embedding: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """티켓 데이터 생성"""
        try:
            # 기본 티켓 정보
            ticket = {
                'ticket_id': f"T{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'original_message_id': email_data.get('id', ''),  # 메일 ID 추가
                'title': email_data.get('subject', '제목 없음'),
                'description': email_data.get('body', '내용 없음'),
                'status': 'pending',
                'priority': classification.get('priority', 'medium'),
                'type': 'email_ticket',
                'reporter': email_data.get('sender', '알 수 없음'),
                'labels': self._generate_labels_for_ticket(email_data, classification),  # 레이블 생성
                'created_at': datetime.now().isoformat(),
                'email_data': {
                    'id': email_data.get('id'),
                    'sender': email_data.get('sender'),
                    'subject': email_data.get('subject'),
                    'received_date': email_data.get('received_date'),
                    'message_id': email_data.get('message_id')
                },
                'classification': classification,
                'embedding': embedding,
                'user_query': user_query,
                'ticket_creation_method': 'ai_classifier_workflow'
            }
            
            return ticket
            
        except Exception as e:
            st.error(f"티켓 데이터 생성 실패: {str(e)}")
            return {}
    
    def classify_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        메일을 통합 분류
        
        Args:
            email_data: 메일 데이터 (EmailMessage 형식)
            
        Returns:
            분류 결과 딕셔너리
        """
        # 캐시 확인
        email_id = email_data.get('id', '')
        if email_id in self.classification_cache:
            return self.classification_cache[email_id]
        
        # 1단계: 도메인 분류
        domain_result = self._classify_by_domain(email_data)
        
        # 2단계: 콘텐츠 분석
        content_result = self._analyze_content(email_data)
        
        # 3단계: 메타데이터 분석
        metadata_result = self._analyze_metadata(email_data)
        
        # 4단계: 통합 분석
        combined_result = self._combine_classifications(
            domain_result, content_result, metadata_result
        )
        
        # 5단계: LM 최종 판단 (사용 가능한 경우)
        if self.use_lm and self.is_llm_available():
            final_result = self._get_lm_final_decision(
                email_data, combined_result
            )
        else:
            if self.use_lm:
                st.warning("⚠️ LM을 사용할 수 없어 기본 분류 결과를 사용합니다.")
            final_result = combined_result
        
        # 결과 캐시에 저장
        self.classification_cache[email_id] = final_result
        
        return final_result
    
    def _classify_by_domain(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """도메인 기반 분류"""
        sender = email_data.get('sender', '')
        
        try:
            should_create, email_type, domain = self.domain_classifier.should_create_ticket(
                sender, interactive=False
            )
            
            return {
                'domain_type': email_type,
                'domain': domain,
                'should_create_ticket': should_create,
                'is_internal': email_type == 'internal',
                'confidence': 0.9 if domain else 0.5
            }
        except Exception as e:
            return {
                'domain_type': 'unknown',
                'domain': '',
                'should_create_ticket': True,
                'is_internal': False,
                'confidence': 0.3
            }
    
    def _analyze_content(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """콘텐츠 분석"""
        body = email_data.get('body', '')
        subject = email_data.get('subject', '')
        
        try:
            # 콘텐츠 추출
            if body:
                extracted = self.content_extractor.extract_clean_content(body, 'text')
                key_points = extracted.get('key_points', [])
                summary = extracted.get('summary', '')
            else:
                key_points = []
                summary = ''
            
            # 업무 관련 키워드 분석
            work_keywords = self._detect_work_keywords(subject + " " + summary)
            
            # 긴급성 분석
            urgency_score = self._analyze_urgency(subject + " " + summary)
            
            return {
                'key_points': key_points,
                'summary': summary,
                'work_keywords': work_keywords,
                'urgency_score': urgency_score,
                'has_work_content': len(work_keywords) > 0,
                'confidence': 0.8
            }
        except Exception as e:
            return {
                'key_points': [],
                'summary': '',
                'work_keywords': [],
                'urgency_score': 0.0,
                'has_work_content': False,
                'confidence': 0.3
            }
    
    def _analyze_metadata(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """메타데이터 분석"""
        try:
            # 중요도 분석
            priority = email_data.get('priority', 'normal')
            priority_map = {
                'high': 0.8,
                'normal': 0.5,
                'low': 0.2
            }
            priority_score = priority_map.get(priority, 0.5)
            
            # 첨부파일 분석
            has_attachments = email_data.get('has_attachments', False)
            attachment_count = email_data.get('attachment_count', 0)
            
            # 읽음 상태
            is_read = email_data.get('is_read', False)
            
            # 날짜 분석
            received_date = email_data.get('received_date')
            if received_date:
                if isinstance(received_date, str):
                    try:
                        received_date = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                    except:
                        received_date = datetime.now()
                
                # 최근 메일인지 확인 (24시간 이내)
                time_diff = datetime.now() - received_date
                is_recent = time_diff.total_seconds() < 24 * 3600
            else:
                is_recent = False
            
            return {
                'priority_score': priority_score,
                'has_attachments': has_attachments,
                'attachment_count': attachment_count,
                'is_read': is_read,
                'is_recent': is_recent,
                'confidence': 0.9
            }
        except Exception as e:
            return {
                'priority_score': 0.5,
                'has_attachments': False,
                'attachment_count': 0,
                'is_read': False,
                'is_recent': False,
                'confidence': 0.3
            }
    
    def _combine_classifications(self, domain_result: Dict, content_result: Dict, metadata_result: Dict) -> Dict[str, Any]:
        """분류 결과 통합"""
        try:
            # 기본 카테고리 결정
            if domain_result.get('is_internal', False):
                category = MailCategory.PERSONAL
                priority = MailPriority.LOW
            elif content_result.get('has_work_content', False):
                urgency = content_result.get('urgency_score', 0.0)
                if urgency > 0.7:
                    category = MailCategory.WORK_URGENT
                    priority = MailPriority.CRITICAL
                elif urgency > 0.4:
                    category = MailCategory.WORK_NORMAL
                    priority = MailPriority.HIGH
                else:
                    category = MailCategory.WORK_LOW
                    priority = MailPriority.MEDIUM
            else:
                category = MailCategory.NOTIFICATION
                priority = MailPriority.LOW
            
            # 신뢰도 계산
            confidence = (
                domain_result.get('confidence', 0.5) * 0.3 +
                content_result.get('confidence', 0.5) * 0.4 +
                metadata_result.get('confidence', 0.5) * 0.3
            )
            
            return {
                'category': category.value,
                'priority': priority.value,
                'confidence': confidence,
                'domain_result': domain_result,
                'content_result': content_result,
                'metadata_result': metadata_result,
                'classification_method': 'rule_based'
            }
        except Exception as e:
            return {
                'category': MailCategory.UNKNOWN.value,
                'priority': MailPriority.MEDIUM.value,
                'confidence': 0.3,
                'classification_method': 'fallback',
                'error': str(e)
            }
    
    def _get_lm_final_decision(self, email_data: Dict[str, Any], combined_result: Dict[str, Any]) -> Dict[str, Any]:
        """LM을 사용한 최종 판단"""
        try:
            # LLM 사용 가능 여부 확인
            if not self.llm:
                st.warning("⚠️ LLM을 사용할 수 없어 기본 분류 결과를 사용합니다.")
                combined_result['classification_method'] = 'lm_unavailable'
                return combined_result
            
            # 프롬프트 구성
            system_prompt = """당신은 메일 분류 전문가입니다. 
다음 정보를 바탕으로 메일의 최종 카테고리와 우선순위를 결정해주세요.

메일 정보:
- 제목: {subject}
- 발신자: {sender}
- 도메인 분류: {domain_type} ({domain})
- 업무 키워드: {work_keywords}
- 긴급성 점수: {urgency_score}
- 중요도: {priority}
- 첨부파일: {has_attachments}

현재 분류 결과:
- 카테고리: {current_category}
- 우선순위: {current_priority}
- 신뢰도: {confidence}

다음 JSON 형식으로 응답해주세요:
{{
    "category": "work_urgent|work_normal|work_low|personal|notification|spam|unknown",
    "priority": "critical|high|medium|low",
    "reasoning": "분류 이유를 간단히 설명",
    "confidence": 0.0-1.0,
    "requires_action": true/false,
    "estimated_response_time": "1시간|1일|1주일|무시"
}}"""

            user_prompt = system_prompt.format(
                subject=email_data.get('subject', ''),
                sender=email_data.get('sender', ''),
                domain_type=combined_result.get('domain_result', {}).get('domain_type', ''),
                domain=combined_result.get('domain_result', {}).get('domain', ''),
                work_keywords=', '.join(combined_result.get('content_result', {}).get('work_keywords', [])),
                urgency_score=combined_result.get('content_result', {}).get('urgency_score', 0.0),
                priority=combined_result.get('priority', ''),
                has_attachments=combined_result.get('metadata_result', {}).get('has_attachments', False),
                current_category=combined_result.get('category', ''),
                current_priority=combined_result.get('priority', ''),
                confidence=combined_result.get('confidence', 0.0)
            )
            
            # LLM 호출
            messages = [
                SystemMessage(content="당신은 메일 분류 전문가입니다. JSON 형식으로만 응답하세요."),
                HumanMessage(content=user_prompt)
            ]
            
            # 스트리밍 처리
            current_response = ""
            final_response = None
            
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content'):
                    current_response += chunk.content
                    final_response = chunk
            
            response_content = final_response.content if final_response else ""
            
            # JSON 파싱
            import json
            try:
                lm_result = json.loads(response_content)
                
                # 결과 통합
                final_result = combined_result.copy()
                final_result.update({
                    'category': lm_result.get('category', combined_result.get('category')),
                    'priority': lm_result.get('priority', combined_result.get('priority')),
                    'confidence': lm_result.get('confidence', combined_result.get('confidence')),
                    'reasoning': lm_result.get('reasoning', ''),
                    'requires_action': lm_result.get('requires_action', False),
                    'estimated_response_time': lm_result.get('estimated_response_time', ''),
                    'classification_method': 'lm_enhanced'
                })
                
                return final_result
                
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기존 결과 반환
                combined_result['classification_method'] = 'lm_failed'
                return combined_result
                
        except Exception as e:
            # LLM 호출 실패 시 기존 결과 반환
            st.warning(f"⚠️ LM 분류 실패: {str(e)}")
            combined_result['classification_method'] = 'lm_error'
            combined_result['error'] = str(e)
            return combined_result
    
    def _detect_work_keywords(self, text: str) -> List[str]:
        """업무 관련 키워드 감지"""
        work_keywords = [
            'urgent', 'important', 'deadline', 'meeting', 'project', 'task',
            'issue', 'bug', 'error', 'request', 'approve', 'review', 'feedback',
            'action', 'required', 'schedule', 'appointment', 'conference', 'call',
            'report', 'document', 'proposal', 'contract', 'invoice', 'payment',
            'support', 'help', 'problem', 'solution', 'update', 'status'
        ]
        
        detected = []
        text_lower = text.lower()
        for keyword in work_keywords:
            if keyword in text_lower:
                detected.append(keyword)
        
        return detected
    
    def _analyze_urgency(self, text: str) -> float:
        """긴급성 점수 계산"""
        urgency_keywords = {
            'urgent': 0.9,
            'asap': 0.8,
            'immediate': 0.8,
            'critical': 0.9,
            'emergency': 1.0,
            'deadline': 0.7,
            'today': 0.6,
            'now': 0.7,
            'quick': 0.5,
            'fast': 0.5
        }
        
        text_lower = text.lower()
        max_score = 0.0
        
        for keyword, score in urgency_keywords.items():
            if keyword in text_lower:
                max_score = max(max_score, score)
        
        return max_score
    
    def classify_multiple_emails(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """여러 메일을 일괄 분류"""
        results = []
        for email in emails:
            result = self.classify_email(email)
            results.append(result)
        return results
    
    def get_classification_summary(self, classifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """분류 결과 요약"""
        if not classifications:
            return {}
        
        category_counts = {}
        priority_counts = {}
        total_confidence = 0.0
        
        for classification in classifications:
            category = classification.get('category', 'unknown')
            priority = classification.get('priority', 'medium')
            confidence = classification.get('confidence', 0.0)
            
            category_counts[category] = category_counts.get(category, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            total_confidence += confidence
        
        avg_confidence = total_confidence / len(classifications) if classifications else 0.0
        
        return {
            'total_emails': len(classifications),
            'category_distribution': category_counts,
            'priority_distribution': priority_counts,
            'average_confidence': avg_confidence,
            'work_emails': category_counts.get('work_urgent', 0) + category_counts.get('work_normal', 0) + category_counts.get('work_low', 0),
            'personal_emails': category_counts.get('personal', 0),
            'urgent_emails': priority_counts.get('critical', 0) + priority_counts.get('high', 0)
        } 