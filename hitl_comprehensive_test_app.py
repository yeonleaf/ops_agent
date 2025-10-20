#!/usr/bin/env python3
"""
Human-in-the-Loop (HITL) 종합 테스트 앱

기능:
1. JSONL 파일 업로드 및 파싱
2. IntegratedMailClassifier를 통한 자동 분류 수행
3. 정답과 비교하여 성공률 계산
4. 사용자 정정 기능 (mem0에 학습 데이터 저장)
5. 정정 후 재분류를 통한 개선도 측정
6. Few-shot Learning 효과 검증
"""

import streamlit as st
import json
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import logging
from pathlib import Path
import traceback
import uuid

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 분류기 관련 import
try:
    from integrated_mail_classifier import IntegratedMailClassifier, TicketCreationStatus
    from mem0_memory_adapter import create_mem0_memory, add_ticket_event
    CLASSIFIER_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ 분류기 모듈 임포트 실패: {e}")
    CLASSIFIER_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="HITL 종합 테스트 앱",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

class HITLComprehensiveTestApp:
    """Human-in-the-Loop 종합 테스트 애플리케이션"""

    def __init__(self):
        """초기화"""
        self.classifier = None
        self.mem0_memory = None

        # 세션 상태 초기화
        if 'test_data' not in st.session_state:
            st.session_state.test_data = []
        if 'classification_results' not in st.session_state:
            st.session_state.classification_results = []
        if 'correction_history' not in st.session_state:
            st.session_state.correction_history = []
        if 'classifier_initialized' not in st.session_state:
            st.session_state.classifier_initialized = False
        if 'baseline_accuracy' not in st.session_state:
            st.session_state.baseline_accuracy = None
        if 'improved_accuracy' not in st.session_state:
            st.session_state.improved_accuracy = None

        # 세션에 분류기 저장 (지속성 확보)
        if 'classifier_instance' not in st.session_state:
            st.session_state.classifier_instance = None

    def initialize_classifier(self) -> bool:
        """분류기 및 메모리 시스템 초기화"""
        if not CLASSIFIER_AVAILABLE:
            st.error("❌ 분류기 모듈을 사용할 수 없습니다.")
            return False

        # 세션에서 기존 분류기 가져오기
        if st.session_state.classifier_initialized and st.session_state.classifier_instance:
            self.classifier = st.session_state.classifier_instance
            if hasattr(st.session_state, 'mem0_instance'):
                self.mem0_memory = st.session_state.mem0_instance
            return True

        try:
            with st.spinner("🤖 IntegratedMailClassifier 초기화 중..."):
                # IntegratedMailClassifier 초기화
                self.classifier = IntegratedMailClassifier(use_lm=True)

                # 분류기가 정상 초기화되었는지 확인
                if self.classifier is None:
                    raise Exception("IntegratedMailClassifier 초기화 실패")

                # 세션에 분류기 저장
                st.session_state.classifier_instance = self.classifier

                # LLM 상태 확인
                try:
                    llm_status = self.classifier.get_llm_status()
                    if llm_status['llm_available']:
                        st.success(f"✅ LLM 사용 가능: {llm_status['llm_type']}")
                    else:
                        st.warning("⚠️ LLM을 사용할 수 없습니다. 기본 규칙 기반 분류를 사용합니다.")
                except Exception as llm_e:
                    st.warning(f"⚠️ LLM 상태 확인 실패: {llm_e}")

                # Mem0 메모리 초기화
                try:
                    self.mem0_memory = create_mem0_memory("hitl_comprehensive_test")
                    st.session_state.mem0_instance = self.mem0_memory
                    st.success("✅ Mem0 메모리 시스템 초기화 완료")
                except Exception as mem_e:
                    st.warning(f"⚠️ Mem0 초기화 실패: {mem_e}")
                    self.mem0_memory = None
                    st.session_state.mem0_instance = None

                st.session_state.classifier_initialized = True
                st.success("🎉 분류기 초기화 완료!")
                return True

        except Exception as e:
            st.error(f"❌ 분류기 초기화 실패: {str(e)}")
            with st.expander("상세 오류 정보"):
                st.text(traceback.format_exc())
            # 초기화 실패시 세션 상태 리셋
            st.session_state.classifier_initialized = False
            st.session_state.classifier_instance = None
            return False

    def load_jsonl_file(self, uploaded_file) -> List[Dict[str, Any]]:
        """JSONL 파일을 로드하여 테스트 데이터 반환"""
        try:
            content = uploaded_file.read().decode('utf-8')
            test_data = []

            for line_num, line in enumerate(content.strip().split('\n'), 1):
                if line.strip():
                    try:
                        data = json.loads(line)
                        test_data.append(data)
                    except json.JSONDecodeError as e:
                        st.warning(f"라인 {line_num}: JSON 파싱 오류 - {str(e)}")

            st.info(f"📊 로드된 데이터 통계:")

            # 데이터 분포 분석
            business_count = sum(1 for item in test_data if item.get('evaluation_group') == 'business')
            non_business_count = len(test_data) - business_count

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("전체", len(test_data))
            with col2:
                st.metric("업무용", business_count)
            with col3:
                st.metric("비업무용", non_business_count)

            return test_data

        except Exception as e:
            st.error(f"❌ 파일 읽기 오류: {str(e)}")
            return []

    def extract_email_data(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """JSONL 데이터에서 분류기가 사용할 이메일 데이터 추출"""
        return {
            'id': json_data.get('message_id', ''),
            'message_id': json_data.get('message_id', ''),
            'subject': json_data.get('subject', ''),
            'body': json_data.get('body_text', ''),
            'sender': json_data.get('from', {}).get('email', ''),
            'received_date': json_data.get('received_at', ''),
            'priority': json_data.get('headers', {}).get('X-Priority', 'normal'),
            'has_attachments': len(json_data.get('attachments', [])) > 0,
            'attachment_count': len(json_data.get('attachments', [])),
            'is_read': False  # 기본값
        }

    def extract_gold_labels(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """정답 레이블 추출"""
        gold_labels = json_data.get('gold_labels', {})
        evaluation_group = json_data.get('evaluation_group', 'unknown')

        # business/non_business를 boolean으로 변환
        is_business = evaluation_group == 'business'

        return {
            'is_business': is_business,
            'priority': gold_labels.get('priority', 'Medium'),
            'ticket_type': gold_labels.get('ticket_type', 'None'),
            'labels': gold_labels.get('labels', []),
            'status': gold_labels.get('status', 'pending'),
            'evaluation_group': evaluation_group
        }

    def run_classification(self, email_data: Dict[str, Any], user_query: str = "업무 관련 메일을 티켓으로 생성해주세요") -> Dict[str, Any]:
        """분류기를 통한 메일 분류 수행"""
        try:
            # 분류기 유효성 확인
            if self.classifier is None:
                # 세션에서 분류기 복구 시도
                if st.session_state.classifier_instance:
                    self.classifier = st.session_state.classifier_instance
                else:
                    raise Exception("분류기가 초기화되지 않았습니다. 분류기 초기화를 다시 수행해주세요.")

            # Few-shot 예시 수집 (correction_history에서)
            few_shot_examples = self.get_few_shot_examples()

            # 티켓 생성 판단
            ticket_status, reason, details = self.classifier.should_create_ticket(
                email_data,
                user_query,
                few_shot_examples
            )

            # 분류 결과
            classification = self.classifier.classify_email(email_data)

            # 결과 통합
            result = {
                'ticket_status': ticket_status,
                'reason': reason,
                'details': details,
                'classification': classification,
                'predicted_is_business': ticket_status == TicketCreationStatus.SHOULD_CREATE,
                'confidence': details.get('confidence', 0.5) if isinstance(details, dict) else 0.5,
                'user_query': user_query,
                'few_shot_count': len(few_shot_examples.get('accept', [])) + len(few_shot_examples.get('reject', []))
            }

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"분류 실행 중 오류: {error_msg}")

            # 상세한 오류 정보 로깅
            if "NoneType" in error_msg:
                logger.error("분류기(self.classifier)가 None입니다. 초기화가 제대로 되지 않았습니다.")
                st.error("❌ 분류기가 초기화되지 않았습니다. 페이지를 새로고침하고 분류기를 다시 초기화해주세요.")

            return {
                'ticket_status': TicketCreationStatus.NO_TICKET_NEEDED,
                'reason': f'분류 오류: {error_msg}',
                'details': {},
                'classification': {},
                'predicted_is_business': False,
                'confidence': 0.0,
                'error': error_msg,
                'few_shot_count': 0
            }

    def get_few_shot_examples(self) -> Dict[str, List[Dict[str, Any]]]:
        """correction_history에서 few-shot 예시 생성"""
        examples = {'accept': [], 'reject': []}

        for correction in st.session_state.correction_history:
            example = {
                'subject': correction['subject'],
                'reason': correction['reason']
            }

            if correction['corrected_to_business']:
                examples['accept'].append(example)
            else:
                examples['reject'].append(example)

        return examples

    def calculate_accuracy_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """정확도 및 성능 메트릭 계산"""
        if not results:
            return {'total': 0, 'correct': 0, 'accuracy': 0.0}

        total = len(results)
        correct = 0
        business_tp = business_fp = business_tn = business_fn = 0

        for result in results:
            predicted = result['predicted_is_business']
            actual = result['gold_labels']['is_business']

            if predicted == actual:
                correct += 1

            # Confusion Matrix
            if actual and predicted:
                business_tp += 1
            elif not actual and predicted:
                business_fp += 1
            elif not actual and not predicted:
                business_tn += 1
            elif actual and not predicted:
                business_fn += 1

        accuracy = correct / total if total > 0 else 0.0

        # Precision, Recall, F1 계산
        precision = business_tp / (business_tp + business_fp) if (business_tp + business_fp) > 0 else 0.0
        recall = business_tp / (business_tp + business_fn) if (business_tp + business_fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'confusion_matrix': {
                'tp': business_tp, 'fp': business_fp,
                'tn': business_tn, 'fn': business_fn
            }
        }

    def save_correction_to_memory(self, email_data: Dict[str, Any], original_prediction: bool, corrected_prediction: bool, reason: str) -> bool:
        """정정 내용을 mem0에 저장"""
        try:
            if self.mem0_memory:
                event_description = f"""
메일 분류 정정 사례:
- 제목: {email_data.get('subject', '')}
- 발신자: {email_data.get('sender', '')}
- AI 원래 판단: {'업무용' if original_prediction else '업무용 아님'}
- 사용자 정정: {'업무용' if corrected_prediction else '업무용 아님'}
- 정정 이유: {reason}
- 메일 내용 요약: {email_data.get('body', '')[:200]}...
"""

                add_ticket_event(
                    self.mem0_memory,
                    'user_correction',
                    event_description,
                    email_data.get('id', '')
                )

                logger.info(f"메모리에 정정 사례 저장: {email_data.get('subject', '')}")
                return True
            else:
                logger.warning("mem0_memory가 초기화되지 않았습니다.")
                return False

        except Exception as e:
            logger.error(f"메모리 저장 실패: {str(e)}")
            return False

    def display_accuracy_comparison(self):
        """정확도 비교 표시"""
        if st.session_state.baseline_accuracy and st.session_state.improved_accuracy:
            st.subheader("📈 성능 개선 비교")

            col1, col2, col3 = st.columns(3)

            baseline = st.session_state.baseline_accuracy
            improved = st.session_state.improved_accuracy

            with col1:
                st.metric(
                    "베이스라인 정확도",
                    f"{baseline['accuracy']:.2%}",
                    help="정정 전 초기 분류 성능"
                )
                st.metric(
                    "베이스라인 F1 스코어",
                    f"{baseline['f1']:.3f}"
                )

            with col2:
                improvement = improved['accuracy'] - baseline['accuracy']
                st.metric(
                    "개선된 정확도",
                    f"{improved['accuracy']:.2%}",
                    delta=f"{improvement:.2%}",
                    help="정정 후 향상된 분류 성능"
                )
                f1_improvement = improved['f1'] - baseline['f1']
                st.metric(
                    "개선된 F1 스코어",
                    f"{improved['f1']:.3f}",
                    delta=f"{f1_improvement:.3f}"
                )

            with col3:
                correction_count = len(st.session_state.correction_history)
                st.metric("적용된 정정 사례", correction_count)

                if correction_count > 0:
                    avg_improvement_per_correction = improvement / correction_count
                    st.metric(
                        "정정당 평균 개선",
                        f"{avg_improvement_per_correction:.3%}"
                    )

            # 성능 개선 시각화
            comparison_df = pd.DataFrame({
                'Metric': ['Accuracy', 'Precision', 'Recall', 'F1 Score'],
                'Baseline': [baseline['accuracy'], baseline['precision'], baseline['recall'], baseline['f1']],
                'Improved': [improved['accuracy'], improved['precision'], improved['recall'], improved['f1']]
            })

            st.bar_chart(comparison_df.set_index('Metric'))

    def display_classification_results(self, results: List[Dict[str, Any]], title: str = "📋 분류 결과"):
        """분류 결과 표시"""
        if not results:
            st.info("분류 결과가 없습니다.")
            return

        # 정확도 계산
        accuracy_metrics = self.calculate_accuracy_metrics(results)

        st.subheader(title)

        # 메트릭 표시
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("전체 정확도", f"{accuracy_metrics['accuracy']:.2%}")
        with col2:
            st.metric("정밀도", f"{accuracy_metrics['precision']:.2%}")
        with col3:
            st.metric("재현율", f"{accuracy_metrics['recall']:.2%}")
        with col4:
            st.metric("F1 스코어", f"{accuracy_metrics['f1']:.3f}")

        # Confusion Matrix
        cm = accuracy_metrics['confusion_matrix']
        st.write("**📊 Confusion Matrix:**")
        confusion_df = pd.DataFrame({
            'Predicted Business': [cm['tp'], cm['fp']],
            'Predicted Non-Business': [cm['fn'], cm['tn']]
        }, index=['Actual Business', 'Actual Non-Business'])
        st.dataframe(confusion_df)

        # 상세 결과 테이블
        display_data = []
        for i, result in enumerate(results):
            display_data.append({
                'Index': i + 1,
                'Subject': result['email_data']['subject'][:50] + '...' if len(result['email_data']['subject']) > 50 else result['email_data']['subject'],
                'Predicted': '✅ Business' if result['predicted_is_business'] else '❌ Non-Business',
                'Actual': '✅ Business' if result['gold_labels']['is_business'] else '❌ Non-Business',
                'Correct': '✅' if result['predicted_is_business'] == result['gold_labels']['is_business'] else '❌',
                'Confidence': f"{result['confidence']:.2f}",
                'Few-shot': result.get('few_shot_count', 0),
                'Reason': result['reason'][:100] + '...' if len(result['reason']) > 100 else result['reason']
            })

        df = pd.DataFrame(display_data)

        # 필터링 옵션
        col1, col2, col3 = st.columns(3)
        with col1:
            show_incorrect_only = st.checkbox("❌ 틀린 결과만 표시", key=f"show_incorrect_{title}")
        with col2:
            show_details = st.checkbox("📝 상세 정보 표시", key=f"show_details_{title}")
        with col3:
            show_correction_ui = st.checkbox("🔧 정정 인터페이스 표시", key=f"show_correction_{title}", help="틀린 결과를 정정할 수 있는 UI를 표시합니다")

        # 전체 결과 또는 필터된 결과 표시
        if show_incorrect_only:
            filtered_df = df[df['Correct'] == '❌']
            st.dataframe(filtered_df, use_container_width=True)

            # 틀린 결과 개수 표시
            st.info(f"📊 틀린 결과: {len(filtered_df)}개 / 전체 {len(df)}개")
        else:
            if show_details:
                st.dataframe(df, use_container_width=True)
            else:
                st.dataframe(df[['Index', 'Subject', 'Predicted', 'Actual', 'Correct', 'Confidence', 'Few-shot']], use_container_width=True)

        # 정정 인터페이스 표시 (독립적으로 작동)
        if show_correction_ui and not title.startswith("📈"):  # 개선된 결과가 아닌 경우만
            incorrect_df = df[df['Correct'] == '❌']
            if len(incorrect_df) > 0:
                st.markdown("---")
                st.subheader("🔧 메일 분류 정정")
                st.info(f"💡 {len(incorrect_df)}개의 틀린 결과를 정정하여 AI 학습에 도움을 줄 수 있습니다.")

                # 간단한 정정 옵션 먼저 제공
                st.write("### 📝 정정 방법 선택:")
                correction_mode = st.radio(
                    "정정 방식을 선택하세요:",
                    options=["간편 정정", "상세 정정"],
                    key=f"correction_mode_{title}",
                    help="간편 정정: 빠른 정정, 상세 정정: 자세한 정정 인터페이스"
                )

                if correction_mode == "간편 정정":
                    self.display_simple_correction_interface(results, incorrect_df, title)
                else:
                    self.display_correction_interface(results, incorrect_df, title)
            else:
                if show_correction_ui:
                    st.success("🎉 모든 분류가 정확합니다! 정정할 항목이 없습니다.")

        return accuracy_metrics

    def display_simple_correction_interface(self, results: List[Dict[str, Any]], incorrect_df: pd.DataFrame, section_title: str):
        """간편 정정 인터페이스"""
        st.write("### 🚀 간편 정정")

        # 틀린 결과를 테이블로 표시하고 바로 정정 가능하게
        for _, row in incorrect_df.iterrows():
            idx = row['Index'] - 1
            result = results[idx]

            with st.container():
                st.write(f"**#{idx + 1}. {result['email_data']['subject']}**")

                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.write(f"📧 **발신자:** {result['email_data']['sender']}")
                    st.write(f"🤖 **AI 판단:** {'업무용' if result['predicted_is_business'] else '업무용 아님'}")
                    st.write(f"✅ **정답:** {'업무용' if result['gold_labels']['is_business'] else '업무용 아님'}")

                with col2:
                    # 빠른 정정 이유 선택
                    quick_reasons = {
                        "개인적 내용": "개인적인 안부나 잡담입니다",
                        "단순 공지": "업무 요청이 없는 공지사항입니다",
                        "광고성": "광고나 마케팅 메일입니다",
                        "업무 요청": "명확한 업무 요청이 있습니다",
                        "기타": ""
                    }

                    reason_key = st.selectbox(
                        "정정 이유:",
                        options=list(quick_reasons.keys()),
                        key=f"quick_reason_{section_title}_{idx}"
                    )

                with col3:
                    if st.button(f"🔧 정정", key=f"quick_save_{section_title}_{idx}", type="secondary"):
                        correct_classification = result['gold_labels']['is_business']  # 정답으로 정정
                        reason = quick_reasons[reason_key] if reason_key != "기타" else "기타 이유로 정정"

                        correction_record = {
                            'timestamp': datetime.now().isoformat(),
                            'email_id': result['email_data']['id'],
                            'subject': result['email_data']['subject'],
                            'sender': result['email_data']['sender'],
                            'original_prediction': result['predicted_is_business'],
                            'corrected_to_business': correct_classification,
                            'reason': reason,
                            'confidence': result['confidence'],
                            'correction_id': str(uuid.uuid4())
                        }

                        st.session_state.correction_history.append(correction_record)

                        # mem0에 저장
                        mem_saved = self.save_correction_to_memory(
                            result['email_data'],
                            result['predicted_is_business'],
                            correct_classification,
                            reason
                        )

                        if mem_saved:
                            st.success("✅ 간편 정정 완료!")
                        else:
                            st.warning("⚠️ 세션에 저장됨")

                        st.rerun()

                st.markdown("---")

        # 전체 정정 완료 버튼
        if len(incorrect_df) > 1:
            st.write("### 📦 일괄 정정")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ 모두 정답으로 정정", key=f"batch_correct_{section_title}"):
                    for _, row in incorrect_df.iterrows():
                        idx = row['Index'] - 1
                        result = results[idx]

                        correction_record = {
                            'timestamp': datetime.now().isoformat(),
                            'email_id': result['email_data']['id'],
                            'subject': result['email_data']['subject'],
                            'sender': result['email_data']['sender'],
                            'original_prediction': result['predicted_is_business'],
                            'corrected_to_business': result['gold_labels']['is_business'],
                            'reason': "일괄 정정: 정답으로 수정",
                            'confidence': result['confidence'],
                            'correction_id': str(uuid.uuid4())
                        }

                        st.session_state.correction_history.append(correction_record)

                        self.save_correction_to_memory(
                            result['email_data'],
                            result['predicted_is_business'],
                            result['gold_labels']['is_business'],
                            "일괄 정정: 정답으로 수정"
                        )

                    st.success(f"✅ {len(incorrect_df)}개 항목 일괄 정정 완료!")
                    st.rerun()

            with col2:
                st.info(f"📊 현재 정정 사례: {len(st.session_state.correction_history)}개")

    def display_correction_interface(self, results: List[Dict[str, Any]], incorrect_df: pd.DataFrame, section_title: str):
        """정정 인터페이스 표시"""
        st.subheader("🔧 분류 정정")
        st.write("잘못 분류된 결과를 정정하여 AI 학습에 도움을 줄 수 있습니다:")

        for _, row in incorrect_df.iterrows():
            idx = row['Index'] - 1
            result = results[idx]

            correction_key = f"correction_{section_title}_{idx}"

            with st.expander(f"📧 정정 #{idx + 1}: {row['Subject']} ({row['Predicted']} ➡️ {row['Actual']})"):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**📧 제목:** {result['email_data']['subject']}")
                    st.write(f"**👤 발신자:** {result['email_data']['sender']}")
                    st.write(f"**📄 내용:**")
                    st.text(result['email_data']['body'][:500] + ('...' if len(result['email_data']['body']) > 500 else ''))
                    st.write(f"**🤖 AI 판단 근거:** {result['reason']}")

                with col2:
                    st.write(f"**🎯 AI 예측:** {'업무용' if result['predicted_is_business'] else '업무용 아님'}")
                    st.write(f"**✅ 정답:** {'업무용' if result['gold_labels']['is_business'] else '업무용 아님'}")
                    st.write(f"**📊 신뢰도:** {result['confidence']:.2f}")
                    st.write(f"**📚 Few-shot:** {result.get('few_shot_count', 0)}개")

                # 정정 UI
                correct_classification = st.radio(
                    "올바른 분류를 선택해주세요:",
                    options=[True, False],
                    format_func=lambda x: "✅ 업무용" if x else "❌ 업무용 아님",
                    index=0 if result['gold_labels']['is_business'] else 1,
                    key=f"radio_{correction_key}"
                )

                reason = st.text_area(
                    "정정 이유를 입력해주세요:",
                    placeholder="예: 이 메일은 업무 요청이 아닌 일반적인 공지사항입니다.",
                    key=f"reason_{correction_key}",
                    height=100
                )

                if st.button(f"💾 정정 내용 저장", key=f"save_{correction_key}"):
                    if reason.strip():
                        correction_record = {
                            'timestamp': datetime.now().isoformat(),
                            'email_id': result['email_data']['id'],
                            'subject': result['email_data']['subject'],
                            'sender': result['email_data']['sender'],
                            'original_prediction': result['predicted_is_business'],
                            'corrected_to_business': correct_classification,
                            'reason': reason,
                            'confidence': result['confidence'],
                            'correction_id': str(uuid.uuid4())
                        }

                        st.session_state.correction_history.append(correction_record)

                        # mem0에 저장
                        mem_saved = self.save_correction_to_memory(
                            result['email_data'],
                            result['predicted_is_business'],
                            correct_classification,
                            reason
                        )

                        if mem_saved:
                            st.success(f"✅ 정정 내용이 mem0에 저장되었습니다!")
                        else:
                            st.warning("⚠️ mem0 저장 실패, 세션에만 저장되었습니다.")

                        st.info(f"📚 총 {len(st.session_state.correction_history)}개의 정정 사례가 누적되었습니다.")
                        st.info("🔄 '재분류 실행' 버튼을 클릭하여 개선 효과를 확인해보세요!")

                    else:
                        st.error("정정 이유를 입력해주세요.")

    def run_classification_batch(self, use_corrections: bool = False) -> List[Dict[str, Any]]:
        """배치 분류 실행"""
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 분류기 유효성 사전 확인
        if self.classifier is None:
            if st.session_state.classifier_instance:
                self.classifier = st.session_state.classifier_instance
            else:
                st.error("❌ 분류기가 초기화되지 않았습니다. 페이지를 새로고침하고 다시 시도해주세요.")
                return []

        correction_info = ""
        if use_corrections:
            few_shot_examples = self.get_few_shot_examples()
            accept_count = len(few_shot_examples.get('accept', []))
            reject_count = len(few_shot_examples.get('reject', []))
            correction_info = f" (Few-shot: Accept {accept_count}개, Reject {reject_count}개)"

        for i, test_item in enumerate(st.session_state.test_data):
            status_text.text(f"🤖 분류 중... {i+1}/{len(st.session_state.test_data)}{correction_info}")

            # 이메일 데이터 추출
            email_data = self.extract_email_data(test_item)
            gold_labels = self.extract_gold_labels(test_item)

            # 분류 실행
            classification_result = self.run_classification(email_data)

            # 오류 발생시 처리
            if 'error' in classification_result:
                st.error(f"❌ 분류 실패 (항목 {i+1}): {classification_result['error']}")
                # 오류가 발생해도 계속 진행
                pass

            # 결과 저장
            result = {
                'email_data': email_data,
                'gold_labels': gold_labels,
                **classification_result
            }
            results.append(result)

            # 진행률 업데이트
            progress_bar.progress((i + 1) / len(st.session_state.test_data))

        status_text.text("✅ 분류 완료!")
        return results

    def run_app(self):
        """메인 앱 실행"""
        st.title("🧪 Human-in-the-Loop (HITL) 종합 테스트 앱")
        st.markdown("---")
        st.markdown("""
        이 앱은 메일 분류기의 성능을 테스트하고 사용자 피드백을 통해 개선하는 도구입니다.

        **주요 기능:**
        - 📂 JSONL 테스트 파일 업로드
        - 🤖 IntegratedMailClassifier 기반 자동 분류
        - 📊 성능 메트릭 계산 (정확도, 정밀도, 재현율, F1)
        - 🔧 사용자 정정 기능 (mem0 연동)
        - 📈 Few-shot Learning 효과 검증
        """)

        # 사용법 가이드
        with st.expander("📖 사용법 가이드", expanded=False):
            st.markdown("""
            ### 🚀 HITL 테스트 진행 순서

            1. **파일 업로드**
               - `output_results/HITL_converted.jsonl` 파일을 업로드하세요

            2. **초기 분류 실행**
               - "🚀 초기 분류 실행" 버튼을 클릭하여 베이스라인 성능을 측정하세요

            3. **결과 확인**
               - 분류 정확도와 틀린 결과를 확인하세요

            4. **정정 수행**
               - "🔧 정정 인터페이스 표시" 체크박스를 체크하세요
               - **간편 정정**: 빠른 정정 (추천)
               - **상세 정정**: 자세한 정정 및 이유 입력

            5. **재분류 실행**
               - 정정 후 "🔄 재분류 실행" 버튼을 클릭하여 개선 효과를 확인하세요

            6. **성능 비교**
               - 베이스라인 vs 개선된 성능을 비교 분석하세요

            ### 💡 팁
            - **간편 정정**으로 여러 항목을 빠르게 정정할 수 있습니다
            - **일괄 정정** 기능으로 모든 틀린 결과를 한번에 정답으로 정정할 수 있습니다
            - 사이드바에서 정정 히스토리를 실시간으로 확인할 수 있습니다
            """)

        st.markdown("---")

        # 사이드바 - 정정 히스토리 및 통계
        with st.sidebar:
            st.header("📚 정정 히스토리")

            if st.session_state.correction_history:
                st.metric("정정 사례 수", len(st.session_state.correction_history))

                # 정정 통계
                accept_corrections = sum(1 for c in st.session_state.correction_history if c['corrected_to_business'])
                reject_corrections = len(st.session_state.correction_history) - accept_corrections

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("업무용 정정", accept_corrections)
                with col2:
                    st.metric("비업무용 정정", reject_corrections)

                # 최근 정정 사례 표시
                st.write("**최근 정정 사례:**")
                for i, correction in enumerate(st.session_state.correction_history[-3:], 1):
                    with st.expander(f"정정 #{len(st.session_state.correction_history) - 3 + i}"):
                        st.write(f"**제목:** {correction['subject'][:30]}...")
                        original = "업무용" if correction['original_prediction'] else "비업무용"
                        corrected = "업무용" if correction['corrected_to_business'] else "비업무용"
                        st.write(f"**정정:** {original} ➡️ {corrected}")
                        st.write(f"**이유:** {correction['reason'][:50]}...")

                if st.button("🗑️ 정정 히스토리 초기화"):
                    st.session_state.correction_history = []
                    st.session_state.baseline_accuracy = None
                    st.session_state.improved_accuracy = None
                    st.success("정정 히스토리가 초기화되었습니다.")
                    st.rerun()
            else:
                st.info("아직 정정 사례가 없습니다.")

        # 메인 영역
        # 1단계: 분류기 초기화
        st.header("1️⃣ 분류기 초기화")

        # 분류기 상태 표시
        with st.expander("🔧 분류기 상태 정보", expanded=False):
            st.write(f"**세션 초기화 상태:** {st.session_state.classifier_initialized}")
            st.write(f"**분류기 인스턴스 존재:** {st.session_state.classifier_instance is not None}")
            st.write(f"**현재 분류기 상태:** {self.classifier is not None}")

        if not self.initialize_classifier():
            st.error("❌ 분류기 초기화에 실패했습니다. 다음을 확인해주세요:")
            st.markdown("""
            - Azure OpenAI API 키와 엔드포인트 설정
            - IntegratedMailClassifier 모듈 가용성
            - 환경 변수 (.env) 파일 설정
            """)
            if st.button("🔄 분류기 강제 재초기화"):
                st.session_state.classifier_initialized = False
                st.session_state.classifier_instance = None
                st.rerun()
            st.stop()

        # 초기화 성공시 상태 확인
        if self.classifier is not None:
            st.success(f"✅ 분류기 준비 완료! (타입: {type(self.classifier).__name__})")
        else:
            st.warning("⚠️ 분류기 객체가 None입니다. 재초기화가 필요할 수 있습니다.")

        # 2단계: 테스트 파일 업로드
        st.header("2️⃣ 테스트 파일 업로드")
        uploaded_file = st.file_uploader(
            "HITL_converted.jsonl 파일을 업로드하세요",
            type=['jsonl'],
            help="JSON Lines 형식의 테스트 데이터 파일 (48개 테스트 케이스)"
        )

        if uploaded_file:
            with st.spinner("파일 로딩 중..."):
                test_data = self.load_jsonl_file(uploaded_file)
                st.session_state.test_data = test_data

            # 데이터 미리보기
            if st.checkbox("📋 데이터 미리보기 (처음 5개)"):
                preview_data = []
                for item in test_data[:5]:
                    preview_data.append({
                        'Subject': item['subject'][:60] + '...' if len(item['subject']) > 60 else item['subject'],
                        'From': item['from']['email'],
                        'Gold Label': item['evaluation_group'],
                        'Body Preview': item['body_text'][:100] + '...' if len(item['body_text']) > 100 else item['body_text']
                    })
                preview_df = pd.DataFrame(preview_data)
                st.dataframe(preview_df, use_container_width=True)

        # 3단계: 분류 실행
        if st.session_state.test_data:
            st.header("3️⃣ 분류 실행")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("🚀 초기 분류 실행", type="primary", help="정정 사례 없이 기본 분류 수행"):
                    with st.spinner("분류 실행 중..."):
                        results = self.run_classification_batch(use_corrections=False)
                        st.session_state.classification_results = results

                        # 베이스라인 정확도 저장
                        baseline_metrics = self.calculate_accuracy_metrics(results)
                        st.session_state.baseline_accuracy = baseline_metrics

                        st.success(f"✅ 초기 분류 완료! 정확도: {baseline_metrics['accuracy']:.2%}")

            with col2:
                correction_count = len(st.session_state.correction_history)
                if correction_count > 0:
                    if st.button(f"🔄 재분류 실행 ({correction_count}개 정정 반영)",
                               type="secondary",
                               help="사용자 정정 사례를 Few-shot Learning으로 반영하여 재분류"):
                        with st.spinner(f"재분류 실행 중 (정정 사례 {correction_count}개 반영)..."):
                            improved_results = self.run_classification_batch(use_corrections=True)

                            # 개선된 정확도 저장
                            improved_metrics = self.calculate_accuracy_metrics(improved_results)
                            st.session_state.improved_accuracy = improved_metrics

                            st.success(f"✅ 재분류 완료! 개선된 정확도: {improved_metrics['accuracy']:.2%}")

                            # 개선 결과 표시
                            if st.session_state.baseline_accuracy:
                                improvement = improved_metrics['accuracy'] - st.session_state.baseline_accuracy['accuracy']
                                if improvement > 0:
                                    st.success(f"🎉 정확도가 {improvement:.2%} 향상되었습니다!")
                                elif improvement < 0:
                                    st.warning(f"⚠️ 정확도가 {abs(improvement):.2%} 하락했습니다.")
                                else:
                                    st.info("정확도 변화가 없습니다.")

                            # 결과 저장 (개선된 결과로 업데이트)
                            st.session_state.classification_results = improved_results
                else:
                    st.info("재분류를 하려면 먼저 정정 사례를 추가해주세요.")

        # 4단계: 성능 개선 비교
        if st.session_state.baseline_accuracy and st.session_state.improved_accuracy:
            st.header("4️⃣ 성능 개선 분석")
            self.display_accuracy_comparison()

        # 5단계: 분류 결과 표시
        if st.session_state.classification_results:
            st.header("5️⃣ 분류 결과 분석")
            accuracy_metrics = self.display_classification_results(
                st.session_state.classification_results,
                "📋 현재 분류 결과"
            )

        # 추가 분석
        if st.session_state.classification_results and st.checkbox("📊 고급 분석 표시"):
            st.subheader("🔍 고급 분석")

            results = st.session_state.classification_results

            # 신뢰도별 성능 분석
            high_conf_results = [r for r in results if r['confidence'] > 0.7]
            low_conf_results = [r for r in results if r['confidence'] <= 0.7]

            col1, col2 = st.columns(2)
            with col1:
                st.write("**고신뢰도 (>0.7) 결과:**")
                if high_conf_results:
                    high_conf_metrics = self.calculate_accuracy_metrics(high_conf_results)
                    st.metric("정확도", f"{high_conf_metrics['accuracy']:.2%}")
                    st.metric("케이스 수", len(high_conf_results))
                else:
                    st.info("고신뢰도 결과가 없습니다.")

            with col2:
                st.write("**저신뢰도 (≤0.7) 결과:**")
                if low_conf_results:
                    low_conf_metrics = self.calculate_accuracy_metrics(low_conf_results)
                    st.metric("정확도", f"{low_conf_metrics['accuracy']:.2%}")
                    st.metric("케이스 수", len(low_conf_results))
                else:
                    st.info("저신뢰도 결과가 없습니다.")

if __name__ == "__main__":
    if CLASSIFIER_AVAILABLE:
        app = HITLComprehensiveTestApp()
        app.run_app()
    else:
        st.error("❌ 필수 모듈을 가져올 수 없습니다. 프로젝트 환경을 확인해주세요.")