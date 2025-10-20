#!/usr/bin/env python3
"""
HITL (Human in the Loop) 테스트 앱
HITL_converted.jsonl 파일을 업로드하여 업무용 메일 여부를 판단하고 정정할 수 있는 앱
"""

import streamlit as st
import json
import os
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 모듈 임포트
try:
    from email_domain_classifier import EmailDomainClassifier, EmailType
    from database_models import DatabaseManager, UserAction
    CLASSIFIER_AVAILABLE = True
except ImportError as e:
    st.error(f"분류기 임포트 실패: {e}")
    CLASSIFIER_AVAILABLE = False

# mem0 임포트 (정정 내용 저장용)
try:
    from mem0 import MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    st.warning("mem0를 사용할 수 없습니다. 정정 내용이 로컬에만 저장됩니다.")

# 페이지 설정
st.set_page_config(
    page_title="HITL 테스트 앱 - 업무용 메일 판단",
    page_icon="🧪",
    layout="wide"
)

class HITLTestApp:
    """HITL 테스트 앱 클래스 - 업무용 메일 판단용"""
    
    def __init__(self):
        self.domain_classifier = None
        self.db_manager = None
        self.mem0_client = None
        self.initialize_components()
    
    def initialize_components(self):
        """컴포넌트 초기화"""
        if CLASSIFIER_AVAILABLE:
            try:
                # 도메인 분류기 초기화 (실제 티켓 생성 여부 판단용)
                self.domain_classifier = EmailDomainClassifier(
                    internal_domains=["@skcc.com", "@sk.com", "@skbroadband.com"],
                    external_domains=["@gmail.com", "@naver.com", "@daum.net"]
                )
                st.success("✅ 도메인 분류기 초기화 완료")
            except Exception as e:
                st.error(f"❌ 분류기 초기화 실패: {e}")
                self.domain_classifier = None
        
        try:
            self.db_manager = DatabaseManager()
            st.success("✅ 데이터베이스 매니저 초기화 완료")
        except Exception as e:
            st.error(f"❌ 데이터베이스 초기화 실패: {e}")
            self.db_manager = None
        
        if MEM0_AVAILABLE:
            try:
                # .env 파일에서 mem0 API 키 읽기
                mem0_api_key = os.getenv("MEM0_API_KEY")
                if mem0_api_key:
                    self.mem0_client = MemoryClient(api_key=mem0_api_key)
                    st.success("✅ mem0 클라이언트 초기화 완료 (API 키 사용)")
                else:
                    self.mem0_client = None
                    st.info("ℹ️ MEM0_API_KEY가 .env 파일에 설정되지 않았습니다. 정정 내용은 로컬 DB와 파일에만 저장됩니다.")
            except Exception as e:
                st.warning(f"⚠️ mem0 초기화 실패: {e}")
                self.mem0_client = None
    
    def load_jsonl_file(self, uploaded_file) -> List[Dict[str, Any]]:
        """JSONL 파일 로드"""
        try:
            emails = []
            for line in uploaded_file:
                line = line.decode('utf-8').strip()
                if line:
                    email_data = json.loads(line)
                    emails.append(email_data)
            return emails
        except Exception as e:
            st.error(f"파일 로드 실패: {e}")
            return []
    
    def classify_business_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """업무용 메일 여부 판단"""
        if not self.domain_classifier:
            return {'error': '분류기가 초기화되지 않았습니다.'}
        
        try:
            sender_email = email_data.get('from', {}).get('email', '')
            subject = email_data.get('subject', '')
            body_text = email_data.get('body_text', '')
            
            # 1. 도메인 기반 판단
            should_create_ticket, email_type, domain = self.domain_classifier.should_create_ticket(
                sender_email, interactive=False
            )
            
            # 2. 콘텐츠 기반 업무 키워드 분석
            business_keywords = self._detect_business_keywords(subject + " " + body_text)
            
            # 3. 최종 판단
            is_business = should_create_ticket and (email_type != 'internal')
            
            # 4. 신뢰도 계산
            confidence = 0.8 if should_create_ticket else 0.6
            if business_keywords:
                confidence += 0.1
            
            return {
                'is_business': is_business,
                'should_create_ticket': should_create_ticket,
                'email_type': email_type,
                'domain': domain,
                'business_keywords': business_keywords,
                'confidence': min(confidence, 1.0),
                'classification_method': 'domain_and_content_analysis'
            }
            
        except Exception as e:
            return {
                'is_business': False,
                'should_create_ticket': False,
                'error': str(e),
                'confidence': 0.0
            }
    
    def _detect_business_keywords(self, text: str) -> List[str]:
        """업무 관련 키워드 감지"""
        business_keywords = [
            '문제', '오류', '에러', '장애', '이슈', '버그', '수정', '개선',
            '요청', '문의', '도움', '지원', '처리', '해결', '확인',
            '데이터', '파일', '업로드', '다운로드', '전송', '수신',
            '시스템', '서버', 'DB', 'API', '로그', '모니터링',
            '긴급', '우선', '중요', '즉시', '빠른', '시급',
            '회의', '미팅', '프로젝트', '작업', '업무', '일정'
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in business_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def classify_emails(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """이메일 분류"""
        if not self.domain_classifier:
            st.error("분류기가 초기화되지 않았습니다.")
            return []
        
        results = []
        progress_bar = st.progress(0)
        
        for i, email_data in enumerate(emails):
            try:
                # 업무용 메일 여부 판단
                classification_result = self.classify_business_email(email_data)
                
                # 결과 저장
                result = {
                    'original_email': email_data,
                    'classification': classification_result,
                    'gold_labels': email_data.get('gold_labels', {}),
                    'gold_ticket': email_data.get('gold_ticket', {}),
                    'evaluation_group': email_data.get('evaluation_group', ''),
                    'is_corrected': False,
                    'correction': None
                }
                results.append(result)
                
                # 진행률 업데이트
                progress_bar.progress((i + 1) / len(emails))
                
            except Exception as e:
                st.error(f"이메일 {i+1} 분류 실패: {e}")
                results.append({
                    'original_email': email_data,
                    'classification': {'error': str(e)},
                    'gold_labels': email_data.get('gold_labels', {}),
                    'gold_ticket': email_data.get('gold_ticket', {}),
                    'evaluation_group': email_data.get('evaluation_group', ''),
                    'is_corrected': False,
                    'correction': None
                })
        
        progress_bar.empty()
        return results
    
    def save_correction_to_mem0(self, email_id: str, original_classification: Dict, corrected_classification: Dict, user_feedback: str):
        """정정 내용을 mem0에 저장"""
        if not self.mem0_client:
            return False
        
        try:
            correction_data = {
                'email_id': email_id,
                'original_classification': original_classification,
                'corrected_classification': corrected_classification,
                'user_feedback': user_feedback,
                'timestamp': datetime.now().isoformat(),
                'correction_id': str(uuid.uuid4())
            }
            
            # mem0에 저장 (API 변경에 대비한 fallback)
            try:
                # 새로운 API 시도
                self.mem0_client.add(
                    f"email_classification_correction_{email_id}",
                    correction_data
                )
            except AttributeError:
                # 구 API 시도
                self.mem0_client.store(
                    f"email_classification_correction_{email_id}",
                    correction_data
                )
            except Exception as api_error:
                st.warning(f"mem0 API 오류: {api_error}")
                return False
            
            return True
        except Exception as e:
            st.error(f"mem0 저장 실패: {e}")
            return False
    
    def save_correction_to_db(self, email_id: str, original_classification: Dict, corrected_classification: Dict, user_feedback: str):
        """정정 내용을 데이터베이스에 저장"""
        if not self.db_manager:
            return False
        
        try:
            user_action = UserAction(
                action_id=None,
                ticket_id=None,
                message_id=email_id,
                action_type='business_email_correction',
                action_description=f'HITL 업무용 메일 판단 정정: {user_feedback}',
                old_value=json.dumps(original_classification, ensure_ascii=False),
                new_value=json.dumps(corrected_classification, ensure_ascii=False),
                context=f'HITL 테스트 앱에서 업무용 메일 판단 정정',
                created_at=datetime.now().isoformat(),
                user_id='hitl_tester'
            )
            
            self.db_manager.add_user_action(user_action)
            return True
        except Exception as e:
            st.error(f"데이터베이스 저장 실패: {e}")
            return False
    
    def save_correction_to_file(self, email_id: str, original_classification: Dict, corrected_classification: Dict, user_feedback: str):
        """정정 내용을 로컬 파일에 저장"""
        try:
            correction_data = {
                'email_id': email_id,
                'original_classification': original_classification,
                'corrected_classification': corrected_classification,
                'user_feedback': user_feedback,
                'timestamp': datetime.now().isoformat(),
                'correction_id': str(uuid.uuid4())
            }
            
            # 로컬 파일에 저장
            corrections_file = "output_results/hitl_business_corrections.jsonl"
            os.makedirs(os.path.dirname(corrections_file), exist_ok=True)
            
            with open(corrections_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(correction_data, ensure_ascii=False) + '\n')
            
            return True
        except Exception as e:
            st.error(f"파일 저장 실패: {e}")
            return False
    
    def calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """정확도, 정밀도, 재현율 계산"""
        if not results:
            return {}
        
        total = len(results)
        correct = 0
        business_correct = 0
        non_business_correct = 0
        business_total = 0
        non_business_total = 0
        business_predicted = 0
        non_business_predicted = 0
        
        for result in results:
            gold_labels = result.get('gold_labels', {})
            classification = result.get('classification', {})
            
            # 골든 라벨에서 비즈니스 여부 판단
            is_business_gold = 'business' in gold_labels.get('labels', [])
            
            # 예측 결과에서 비즈니스 여부 판단
            is_business_pred = classification.get('is_business', False)
            
            # 정확도 계산
            if is_business_gold == is_business_pred:
                correct += 1
            
            # 비즈니스 관련 계산
            if is_business_gold:
                business_total += 1
                if is_business_pred:
                    business_correct += 1
            
            if is_business_pred:
                business_predicted += 1
            
            # 논비즈니스 관련 계산
            if not is_business_gold:
                non_business_total += 1
                if not is_business_pred:
                    non_business_correct += 1
            
            if not is_business_pred:
                non_business_predicted += 1
        
        # 메트릭 계산
        accuracy = correct / total if total > 0 else 0
        business_precision = business_correct / business_predicted if business_predicted > 0 else 0
        business_recall = business_correct / business_total if business_total > 0 else 0
        non_business_precision = non_business_correct / non_business_predicted if non_business_predicted > 0 else 0
        non_business_recall = non_business_correct / non_business_total if non_business_total > 0 else 0
        
        return {
            'accuracy': accuracy,
            'business_precision': business_precision,
            'business_recall': business_recall,
            'non_business_precision': non_business_precision,
            'non_business_recall': non_business_recall,
            'total': total,
            'correct': correct,
            'business_total': business_total,
            'non_business_total': non_business_total
        }

def main():
    """메인 앱"""
    st.title("🧪 HITL 테스트 앱 - 업무용 메일 판단")
    st.markdown("Human in the Loop 테스트를 위한 업무용 메일 여부 판단 정확도 측정 도구")
    
    # 앱 초기화
    if 'hitl_app' not in st.session_state:
        st.session_state.hitl_app = HITLTestApp()
    
    hitl_app = st.session_state.hitl_app
    
    # 사이드바
    with st.sidebar:
        st.header("📊 테스트 설정")
        
        if not CLASSIFIER_AVAILABLE:
            st.error("❌ 분류기를 사용할 수 없습니다.")
            st.stop()
        
        if not hitl_app.domain_classifier:
            st.error("❌ 도메인 분류기가 초기화되지 않았습니다.")
            st.stop()
        
        st.success("✅ 모든 컴포넌트 준비 완료")
        
        # 분류기 통계 표시
        stats = hitl_app.domain_classifier.get_classification_stats()
        st.subheader("📋 분류기 통계")
        st.write(f"내부 도메인: {stats['total_internal_domains']}개")
        st.write(f"외부 도메인: {stats['total_external_domains']}개")
        st.write(f"학습된 미분류: {stats['cached_unknown_domains']}개")
    
    # 메인 컨텐츠
    tab1, tab2, tab3 = st.tabs(["📁 파일 업로드", "🔍 분류 결과", "📈 성능 분석"])
    
    with tab1:
        st.header("📁 테스트 파일 업로드")
        
        uploaded_file = st.file_uploader(
            "HITL_converted.jsonl 파일을 업로드하세요",
            type=['jsonl'],
            help="JSONL 형식의 테스트 데이터 파일"
        )
        
        if uploaded_file is not None:
            if st.button("🚀 분류 시작", type="primary"):
                with st.spinner("파일을 로드하고 분류 중..."):
                    # 파일 로드
                    emails = hitl_app.load_jsonl_file(uploaded_file)
                    
                    if emails:
                        st.success(f"✅ {len(emails)}개의 이메일을 로드했습니다.")
                        
                        # 분류 실행
                        results = hitl_app.classify_emails(emails)
                        
                        # 세션에 저장
                        st.session_state.classification_results = results
                        st.session_state.emails_loaded = True
                        
                        st.success("✅ 분류 완료!")
                        st.rerun()
                    else:
                        st.error("❌ 파일을 로드할 수 없습니다.")
    
    with tab2:
        st.header("🔍 분류 결과")
        
        if 'classification_results' not in st.session_state:
            st.info("먼저 파일을 업로드하고 분류를 실행해주세요.")
        else:
            results = st.session_state.classification_results
            
            # 필터링 옵션
            col1, col2 = st.columns(2)
            with col1:
                show_corrected = st.checkbox("정정된 항목만 보기", value=False)
            with col2:
                evaluation_group = st.selectbox(
                    "평가 그룹 필터",
                    ["전체"] + list(set(r.get('evaluation_group', '') for r in results if r.get('evaluation_group')))
                )
            
            # 결과 표시
            for i, result in enumerate(results):
                if show_corrected and not result.get('is_corrected', False):
                    continue
                
                if evaluation_group != "전체" and result.get('evaluation_group', '') != evaluation_group:
                    continue
                
                with st.expander(f"이메일 {i+1}: {result['original_email'].get('subject', '제목 없음')}"):
                    # 원본 이메일 정보
                    email_data = result['original_email']
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📧 원본 이메일")
                        st.write(f"**발신자:** {email_data.get('from', {}).get('email', '')}")
                        st.write(f"**제목:** {email_data.get('subject', '')}")
                        st.write(f"**본문:** {email_data.get('body_text', '')[:200]}...")
                        st.write(f"**골든 라벨:** {email_data.get('gold_labels', {})}")
                    
                    with col2:
                        st.subheader("🤖 분류 결과")
                        classification = result.get('classification', {})
                        st.write(f"**업무용 메일:** {'✅ 예' if classification.get('is_business') else '❌ 아니오'}")
                        st.write(f"**티켓 생성 필요:** {'✅ 예' if classification.get('should_create_ticket') else '❌ 아니오'}")
                        st.write(f"**이메일 타입:** {classification.get('email_type', 'N/A')}")
                        st.write(f"**도메인:** {classification.get('domain', 'N/A')}")
                        st.write(f"**업무 키워드:** {', '.join(classification.get('business_keywords', []))}")
                        st.write(f"**신뢰도:** {classification.get('confidence', 0):.2f}")
                    
                    # 정정 버튼
                    if not result.get('is_corrected', False):
                        st.subheader("✏️ 분류 정정")
                        
                        with st.form(f"correction_form_{i}"):
                            corrected_is_business = st.selectbox(
                                "수정된 업무용 메일 여부",
                                [True, False],
                                format_func=lambda x: "✅ 업무용 메일" if x else "❌ 개인 메일",
                                key=f"business_{i}"
                            )
                            user_feedback = st.text_area(
                                "정정 이유",
                                placeholder="왜 이 분류가 틀렸다고 생각하시나요?",
                                key=f"feedback_{i}"
                            )
                            
                            if st.form_submit_button("💾 정정 저장"):
                                if user_feedback:
                                    # 정정 내용 저장
                                    corrected_classification = {
                                        'is_business': corrected_is_business,
                                        'should_create_ticket': corrected_is_business,
                                        'confidence': 1.0,  # 사용자 정정은 100% 신뢰도
                                        'classification_method': 'human_correction'
                                    }
                                    
                                    # mem0에 저장 (API 키 필요로 인해 비활성화)
                                    mem0_success = hitl_app.save_correction_to_mem0(
                                        email_data.get('message_id', ''),
                                        classification,
                                        corrected_classification,
                                        user_feedback
                                    )
                                    
                                    # 데이터베이스에 저장
                                    db_success = hitl_app.save_correction_to_db(
                                        email_data.get('message_id', ''),
                                        classification,
                                        corrected_classification,
                                        user_feedback
                                    )
                                    
                                    # 로컬 파일에 저장
                                    file_success = hitl_app.save_correction_to_file(
                                        email_data.get('message_id', ''),
                                        classification,
                                        corrected_classification,
                                        user_feedback
                                    )
                                    
                                    if mem0_success or db_success or file_success:
                                        # 결과 업데이트
                                        result['is_corrected'] = True
                                        result['correction'] = {
                                            'corrected_classification': corrected_classification,
                                            'user_feedback': user_feedback,
                                            'timestamp': datetime.now().isoformat()
                                        }
                                        
                                        st.success("✅ 정정 내용이 저장되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error("❌ 정정 내용 저장에 실패했습니다.")
                                else:
                                    st.error("정정 이유를 입력해주세요.")
                    else:
                        st.success("✅ 이미 정정된 항목입니다.")
                        correction = result.get('correction', {})
                        corrected_classification = correction.get('corrected_classification', {})
                        st.write(f"**정정된 업무용 메일 여부:** {'✅ 예' if corrected_classification.get('is_business') else '❌ 아니오'}")
                        st.write(f"**정정 이유:** {correction.get('user_feedback', 'N/A')}")
    
    with tab3:
        st.header("📈 성능 분석")
        
        if 'classification_results' not in st.session_state:
            st.info("먼저 파일을 업로드하고 분류를 실행해주세요.")
        else:
            results = st.session_state.classification_results
            
            # 메트릭 계산
            metrics = hitl_app.calculate_metrics(results)
            
            if metrics:
                st.subheader("📊 전체 성능 지표")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("정확도", f"{metrics['accuracy']:.2%}")
                
                with col2:
                    st.metric("업무용 메일 정밀도", f"{metrics['business_precision']:.2%}")
                
                with col3:
                    st.metric("업무용 메일 재현율", f"{metrics['business_recall']:.2%}")
                
                with col4:
                    st.metric("총 이메일 수", metrics['total'])
                
                # 상세 분석
                st.subheader("📋 상세 분석")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**업무용 메일 분석**")
                    st.write(f"- 총 업무용 메일: {metrics['business_total']}개")
                    st.write(f"- 정밀도: {metrics['business_precision']:.2%}")
                    st.write(f"- 재현율: {metrics['business_recall']:.2%}")
                
                with col2:
                    st.write("**개인 메일 분석**")
                    st.write(f"- 총 개인 메일: {metrics['non_business_total']}개")
                    st.write(f"- 정밀도: {metrics['non_business_precision']:.2%}")
                    st.write(f"- 재현율: {metrics['non_business_recall']:.2%}")
                
                # 정정 통계
                corrected_count = sum(1 for r in results if r.get('is_corrected', False))
                st.subheader("✏️ 정정 통계")
                st.write(f"- 정정된 항목: {corrected_count}개")
                st.write(f"- 정정률: {corrected_count / len(results):.2%}")
                
                # CSV 다운로드
                if st.button("📥 결과 CSV 다운로드"):
                    # 결과를 DataFrame으로 변환
                    df_data = []
                    for i, result in enumerate(results):
                        email_data = result['original_email']
                        classification = result.get('classification', {})
                        gold_labels = result.get('gold_labels', {})
                        
                        df_data.append({
                            'email_id': i + 1,
                            'subject': email_data.get('subject', ''),
                            'sender': email_data.get('from', {}).get('email', ''),
                            'predicted_is_business': classification.get('is_business', False),
                            'predicted_should_create_ticket': classification.get('should_create_ticket', False),
                            'predicted_confidence': classification.get('confidence', 0),
                            'business_keywords': ', '.join(classification.get('business_keywords', [])),
                            'gold_labels': str(gold_labels),
                            'evaluation_group': result.get('evaluation_group', ''),
                            'is_corrected': result.get('is_corrected', False),
                            'correction_feedback': result.get('correction', {}).get('user_feedback', '') if result.get('is_corrected') else ''
                        })
                    
                    df = pd.DataFrame(df_data)
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    
                    st.download_button(
                        label="CSV 파일 다운로드",
                        data=csv,
                        file_name=f"hitl_business_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

if __name__ == "__main__":
    main()

