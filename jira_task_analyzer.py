#!/usr/bin/env python3
"""
JIRA 일감 생성 적합성 판단 시스템
텍스트를 분석하여 해당 내용이 JIRA 티켓으로 생성할 만한 작업인지 판단
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Azure OpenAI 사용시 (기존 시스템과 연동)
try:
    from module.image_to_text import AzureOpenAIImageProcessor
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


class TaskType(Enum):
    """작업 유형"""
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    IMPROVEMENT = "improvement"
    TASK = "task"
    STORY = "story"
    EPIC = "epic"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    NOT_APPLICABLE = "not_applicable"


class Priority(Enum):
    """우선순위"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNDEFINED = "undefined"


class JiraEligibility(Enum):
    """JIRA 적합성"""
    HIGHLY_SUITABLE = "highly_suitable"      # 매우 적합
    SUITABLE = "suitable"                    # 적합
    PARTIALLY_SUITABLE = "partially_suitable"  # 부분적으로 적합
    NOT_SUITABLE = "not_suitable"           # 부적합


@dataclass
class TaskAnalysisResult:
    """작업 분석 결과"""
    text: str
    eligibility: JiraEligibility
    confidence: float  # 0.0 ~ 1.0
    task_type: TaskType
    priority: Priority
    reasoning: List[str] = field(default_factory=list)
    suggested_title: Optional[str] = None
    suggested_description: Optional[str] = None
    estimated_effort: Optional[str] = None  # "1h", "1d", "1w" 등
    tags: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)  # 작업 진행을 막는 요소들
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class JiraTaskAnalyzer:
    """JIRA 일감 생성 적합성 분석기"""
    
    def __init__(self, use_llm: bool = True, azure_processor: Optional[AzureOpenAIImageProcessor] = None):
        """
        Args:
            use_llm: LLM을 사용한 고도화된 분석 여부
            azure_processor: Azure OpenAI 프로세서 (선택사항)
        """
        self.use_llm = use_llm and AZURE_AVAILABLE
        self.azure_processor = azure_processor
        
        # 키워드 패턴 정의
        self._init_patterns()
        
        # 작업 유형별 가중치
        self.type_weights = {
            TaskType.BUG_FIX: 0.9,        # 버그는 높은 우선순위
            TaskType.FEATURE: 0.8,        # 기능 개발
            TaskType.IMPROVEMENT: 0.7,    # 개선사항
            TaskType.TASK: 0.6,          # 일반 작업
            TaskType.STORY: 0.8,         # 사용자 스토리
            TaskType.RESEARCH: 0.5,      # 조사/연구
            TaskType.DOCUMENTATION: 0.4, # 문서화
        }
    
    def _init_patterns(self):
        """키워드 패턴 초기화"""
        self.patterns = {
            "bug_keywords": [
                r"버그", r"오류", r"에러", r"bug", r"error", r"issue", r"문제",
                r"안\s*됨", r"작동하지\s*않", r"실패", r"깨짐", r"crash", r"exception"
            ],
            "feature_keywords": [
                r"기능", r"추가", r"개발", r"구현", r"feature", r"add", r"create", r"build",
                r"새로운", r"신규", r"만들", r"생성"
            ],
            "improvement_keywords": [
                r"개선", r"향상", r"최적화", r"리팩토링", r"upgrade", r"optimize", r"improve",
                r"성능", r"속도", r"효율", r"사용성", r"UX", r"UI"
            ],
            "task_keywords": [
                r"작업", r"설정", r"설치", r"배포", r"설정", r"config", r"setup", r"install",
                r"deploy", r"migration", r"update"
            ],
            "story_keywords": [
                r"사용자", r"고객", r"user", r"customer", r"~로서", r"~을\s*위해",
                r"story", r"requirement", r"요구사항"
            ],
            "research_keywords": [
                r"조사", r"연구", r"분석", r"검토", r"research", r"investigate", r"analyze",
                r"study", r"review", r"evaluate"
            ],
            "documentation_keywords": [
                r"문서", r"메뉴얼", r"가이드", r"설명서", r"docs", r"documentation", r"manual",
                r"guide", r"readme", r"wiki"
            ],
            "priority_high": [
                r"긴급", r"중요", r"critical", r"urgent", r"high", r"asap", r"빨리",
                r"즉시", r"우선순위"
            ],
            "priority_low": [
                r"나중에", r"여유\s*있을\s*때", r"low", r"minor", r"nice\s*to\s*have",
                r"추후", r"향후"
            ],
            "actionable": [
                r"해야\s*한다", r"해주세요", r"필요하다", r"요청", r"부탁", r"~하자",
                r"should", r"need", r"must", r"require", r"please", r"let's",
                r"고쳐", r"수정", r"개선", r"추가", r"구현", r"개발", r"만들",
                r"fix", r"add", r"create", r"build", r"implement", r"develop"
            ],
            "vague": [
                r"좀", r"약간", r"조금", r"가끔", r"maybe", r"perhaps", r"might",
                r"생각해보", r"고민", r"어떨까", r"괜찮을까"
            ],
            "jira_notifications": [
                r"업데이트", r"update", r"댓글", r"comment", r"수정", r"modified",
                r"변경", r"changed", r"assigned", r"mention", r"참조", r"watched",
                r"resolved", r"closed", r"reopened", r"진행", r"완료", r"해결",
                r"상태 변경", r"status.*changed", r"due date", r"마감일"
            ],
            "jira_creation": [
                r"생성", r"created", r"신규", r"new", r"등록", r"요청", r"request",
                r"문의", r"inquiry", r"버그 리포트", r"bug report", r"개발 요청"
            ],
            "effort_indicators": [
                r"(\d+)\s*(시간|hour|h)", r"(\d+)\s*(일|day|d)", r"(\d+)\s*(주|week|w)",
                r"(\d+)\s*(개월|month|m)", r"간단한", r"복잡한", r"어려운", r"쉬운"
            ]
        }
    
    def analyze_text(self, text: str) -> TaskAnalysisResult:
        """텍스트를 분석하여 JIRA 일감 적합성 판단"""
        try:
            # 1. 기본 분석 (키워드 기반)
            basic_result = self._basic_analysis(text)
            
            # 2. LLM 기반 고도화된 분석 (사용 가능시)
            if self.use_llm and self.azure_processor:
                enhanced_result = self._llm_enhanced_analysis(text, basic_result)
                return enhanced_result
            else:
                return basic_result
                
        except Exception as e:
            print(f"분석 오류: {e}")
            return TaskAnalysisResult(
                text=text,
                eligibility=JiraEligibility.NOT_SUITABLE,
                confidence=0.1,
                task_type=TaskType.NOT_APPLICABLE,
                priority=Priority.UNDEFINED,
                reasoning=[f"분석 오류: {str(e)}"]
            )
    
    def _basic_analysis(self, text: str) -> TaskAnalysisResult:
        """기본 키워드 기반 분석"""
        text_lower = text.lower()
        
        # JIRA 알림/업데이트 메일 사전 필터링
        if self._is_jira_notification(text_lower):
            return TaskAnalysisResult(
                text=text,
                eligibility=JiraEligibility.NOT_SUITABLE,
                confidence=0.9,  # 높은 신뢰도로 부적합 판정
                task_type=TaskType.NOT_APPLICABLE,
                priority=Priority.UNDEFINED,
                reasoning=["JIRA 알림/업데이트 메일로 감지됨", "신규 일감이 아닌 기존 티켓 진행사항"],
                suggested_title="[알림] " + text.split('\n')[0][:50] + "...",
                estimated_effort="0h"
            )
        
        # 작업 유형 판별
        task_type = self._detect_task_type(text_lower)
        
        # 우선순위 판별
        priority = self._detect_priority(text_lower)
        
        # 실행 가능성 점수 계산
        actionability_score = self._calculate_actionability(text_lower)
        
        # 명확성 점수 계산
        clarity_score = self._calculate_clarity(text_lower)
        
        # JIRA 적합성 계산
        eligibility, confidence = self._calculate_eligibility(
            task_type, actionability_score, clarity_score, len(text)
        )
        
        # 추천 제목 생성
        suggested_title = self._generate_title(text, task_type)
        
        # 노력 추정
        estimated_effort = self._estimate_effort(text_lower)
        
        # 태그 추출
        tags = self._extract_tags(text_lower, task_type)
        
        # 블로커 식별
        blockers = self._identify_blockers(text_lower)
        
        # 분석 근거 생성
        reasoning = self._generate_reasoning(
            task_type, actionability_score, clarity_score, len(text)
        )
        
        return TaskAnalysisResult(
            text=text,
            eligibility=eligibility,
            confidence=confidence,
            task_type=task_type,
            priority=priority,
            reasoning=reasoning,
            suggested_title=suggested_title,
            suggested_description=self._generate_description(text),
            estimated_effort=estimated_effort,
            tags=tags,
            blockers=blockers
        )
    
    def _detect_task_type(self, text: str) -> TaskType:
        """작업 유형 감지"""
        scores = {}
        
        for task_type, patterns in [
            (TaskType.BUG_FIX, self.patterns["bug_keywords"]),
            (TaskType.FEATURE, self.patterns["feature_keywords"]),
            (TaskType.IMPROVEMENT, self.patterns["improvement_keywords"]),
            (TaskType.TASK, self.patterns["task_keywords"]),
            (TaskType.STORY, self.patterns["story_keywords"]),
            (TaskType.RESEARCH, self.patterns["research_keywords"]),
            (TaskType.DOCUMENTATION, self.patterns["documentation_keywords"])
        ]:
            score = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)
            scores[task_type] = score
        
        if not any(scores.values()):
            return TaskType.NOT_APPLICABLE
        
        return max(scores, key=scores.get)
    
    def _detect_priority(self, text: str) -> Priority:
        """우선순위 감지"""
        high_score = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                        for pattern in self.patterns["priority_high"])
        low_score = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                       for pattern in self.patterns["priority_low"])
        
        if high_score > low_score:
            return Priority.HIGH
        elif low_score > 0:
            return Priority.LOW
        else:
            return Priority.MEDIUM
    
    def _calculate_actionability(self, text: str) -> float:
        """실행 가능성 점수 계산"""
        actionable_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                             for pattern in self.patterns["actionable"])
        vague_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                         for pattern in self.patterns["vague"])
        
        # 명확한 액션이 있으면 높은 점수, 모호한 표현이 있으면 감점
        score = min(actionable_count * 0.3 - vague_count * 0.2, 1.0)
        return max(score, 0.0)
    
    def _calculate_clarity(self, text: str) -> float:
        """명확성 점수 계산"""
        # 문장 길이, 구체성, 기술적 용어 등을 고려
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        
        # 적절한 문장 길이 (5-20 단어)
        length_score = 1.0 - abs(avg_sentence_length - 12.5) / 12.5
        length_score = max(0.0, min(1.0, length_score))
        
        # 구체적인 용어가 있는지 확인
        specific_terms = len(re.findall(r'[A-Z]{2,}|[a-z]+\.[a-z]+|\d+', text))
        specificity_score = min(specific_terms * 0.1, 1.0)
        
        return (length_score + specificity_score) / 2
    
    def _calculate_eligibility(self, task_type: TaskType, actionability: float, 
                              clarity: float, text_length: int) -> Tuple[JiraEligibility, float]:
        """JIRA 적합성 계산"""
        # 작업 유형별 기본 점수
        base_score = self.type_weights.get(task_type, 0.3)
        
        # NOT_APPLICABLE이 아닌 경우 기본 점수 상향 조정
        if task_type != TaskType.NOT_APPLICABLE:
            base_score = max(base_score, 0.5)
        
        # 실행 가능성과 명확성 반영
        score = base_score * 0.5 + actionability * 0.25 + clarity * 0.25
        
        # 텍스트 길이 고려 (너무 짧거나 길면 감점)
        if text_length < 10:
            score *= 0.5  # 너무 짧음
        elif text_length > 1000:
            score *= 0.8  # 너무 김
        
        # 적합성 등급 결정
        if score >= 0.8:
            eligibility = JiraEligibility.HIGHLY_SUITABLE
        elif score >= 0.6:
            eligibility = JiraEligibility.SUITABLE
        elif score >= 0.4:
            eligibility = JiraEligibility.PARTIALLY_SUITABLE
        else:
            eligibility = JiraEligibility.NOT_SUITABLE
        
        confidence = min(score, 0.95)  # 최대 95% 신뢰도
        
        return eligibility, confidence
    
    def _generate_title(self, text: str, task_type: TaskType) -> str:
        """제목 생성"""
        # 첫 문장이나 핵심 키워드를 바탕으로 제목 생성
        first_sentence = text.split('.')[0].strip()
        if len(first_sentence) > 50:
            first_sentence = first_sentence[:47] + "..."
        
        type_prefix = {
            TaskType.BUG_FIX: "[버그수정]",
            TaskType.FEATURE: "[기능개발]",
            TaskType.IMPROVEMENT: "[개선]",
            TaskType.TASK: "[작업]",
            TaskType.STORY: "[스토리]",
            TaskType.RESEARCH: "[조사]",
            TaskType.DOCUMENTATION: "[문서화]"
        }.get(task_type, "[작업]")
        
        return f"{type_prefix} {first_sentence}"
    
    def _generate_description(self, text: str) -> str:
        """설명 생성"""
        if len(text) <= 200:
            return text
        
        # 긴 텍스트의 경우 요약 형태로 구성
        sentences = text.split('.')
        key_sentences = sentences[:3]  # 처음 3문장
        
        description = "## 요청사항\n"
        description += '. '.join(key_sentences) + "\n\n"
        
        if len(sentences) > 3:
            description += "## 상세내용\n"
            description += '. '.join(sentences[3:])
        
        return description
    
    def _estimate_effort(self, text: str) -> Optional[str]:
        """작업 노력 추정"""
        for pattern in self.patterns["effort_indicators"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # 키워드 기반 추정
        if any(keyword in text for keyword in ["간단", "쉬운", "simple", "easy"]):
            return "1-2h"
        elif any(keyword in text for keyword in ["복잡", "어려운", "complex", "difficult"]):
            return "1-2w"
        else:
            return "2-3d"  # 기본값
    
    def _extract_tags(self, text: str, task_type: TaskType) -> List[str]:
        """태그 추출"""
        tags = [task_type.value]
        
        # 기술 스택 관련 태그
        tech_patterns = {
            "frontend": r"프론트엔드|frontend|react|vue|angular|javascript|html|css",
            "backend": r"백엔드|backend|api|server|java|python|node",
            "database": r"데이터베이스|database|db|sql|mysql|postgresql|mongodb",
            "mobile": r"모바일|mobile|ios|android|app",
            "devops": r"배포|deploy|ci/cd|docker|kubernetes|aws|azure"
        }
        
        for tag, pattern in tech_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                tags.append(tag)
        
        return tags
    
    def _identify_blockers(self, text: str) -> List[str]:
        """작업 블로커 식별"""
        blockers = []
        
        blocker_patterns = {
            "의존성": r"의존|depend|require|필요",
            "권한": r"권한|permission|access|승인",
            "리소스": r"리소스|resource|인력|시간|예산",
            "기술부채": r"기술부채|legacy|오래된|outdated"
        }
        
        for blocker_type, pattern in blocker_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                blockers.append(blocker_type)
        
        return blockers
    
    def _generate_reasoning(self, task_type: TaskType, actionability: float, 
                           clarity: float, text_length: int) -> List[str]:
        """분석 근거 생성"""
        reasoning = []
        
        reasoning.append(f"작업 유형: {task_type.value}")
        reasoning.append(f"실행가능성: {actionability:.2f}")
        reasoning.append(f"명확성: {clarity:.2f}")
        reasoning.append(f"텍스트 길이: {text_length}자")
        
        if actionability > 0.7:
            reasoning.append("명확한 액션 아이템 포함")
        elif actionability < 0.3:
            reasoning.append("모호한 표현으로 액션 불명확")
        
        if clarity > 0.7:
            reasoning.append("구체적이고 명확한 요구사항")
        elif clarity < 0.3:
            reasoning.append("요구사항이 불명확함")
        
        return reasoning
    
    def _is_jira_notification(self, text: str) -> bool:
        """JIRA 알림/업데이트 메일인지 판별"""
        # 제목/첫 줄에서 JIRA 알림 패턴 확인
        first_lines = text.split('\n')[:3]  # 처음 3줄 확인
        first_text = '\n'.join(first_lines).lower()
        
        # 1. JIRA 티켓 번호 + 업데이트 패턴
        jira_ticket_pattern = r'(jira|btvo|btvdb|bpm|testbed|ncms)[-_]?\d+.*업데이트'
        if re.search(jira_ticket_pattern, first_text, re.IGNORECASE):
            return True
        
        # 2. 일반적인 JIRA 알림 키워드
        notification_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                               for pattern in self.patterns["jira_notifications"])
        
        # 3. 새로운 생성 키워드 (이건 제외)
        creation_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                           for pattern in self.patterns["jira_creation"])
        
        # 알림 키워드가 많고 생성 키워드가 적으면 알림으로 판단
        if notification_count >= 2 and creation_count <= 1:
            return True
            
        # 4. 발신자가 JIRA 시스템인지 확인
        if re.search(r'jira@.*\.com|noreply.*jira', text, re.IGNORECASE):
            return True
        
        return False
    
    def _llm_enhanced_analysis(self, text: str, basic_result: TaskAnalysisResult) -> TaskAnalysisResult:
        """LLM을 사용한 고도화된 분석"""
        if not self.azure_processor:
            return basic_result
        
        try:
            # LLM에게 전달할 프롬프트 구성
            prompt = self._create_llm_prompt(text, basic_result)
            
            # 직접 Azure OpenAI client 사용하여 텍스트 분석
            llm_response = self._call_azure_openai_text(prompt)
            
            # LLM 응답을 파싱하여 결과 개선
            enhanced_result = self._parse_llm_response(llm_response, basic_result)
            
            return enhanced_result
            
        except Exception as e:
            print(f"LLM 분석 오류: {e}")
            # LLM 분석 실패시 기본 분석 결과 반환
            basic_result.reasoning.append(f"LLM 분석 실패: {str(e)}")
            return basic_result
    
    def _call_azure_openai_text(self, prompt: str) -> str:
        """Azure OpenAI를 통한 텍스트 분석"""
        try:
            response = self.azure_processor.client.chat.completions.create(
                model=self.azure_processor.deployment_name,
                messages=[
                    {"role": "system", "content": "당신은 JIRA 일감 분석 전문가입니다. 텍스트를 분석하여 JIRA 티켓 생성 적합성을 판단해주세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Azure OpenAI 텍스트 분석 오류: {str(e)}")
    
    def _create_llm_prompt(self, text: str, basic_result: TaskAnalysisResult) -> str:
        """LLM 분석용 프롬프트 생성"""
        prompt = f"""
        다음 텍스트가 JIRA 일감(티켓)으로 생성하기에 적합한지 분석해주세요:

        ==== 분석 대상 텍스트 ====
        {text}

        ==== 기본 분석 결과 ====
        - 작업 유형: {basic_result.task_type.value}
        - 우선순위: {basic_result.priority.value}
        - 적합성: {basic_result.eligibility.value}
        - 신뢰도: {basic_result.confidence:.2f}

        ==== 분석 요청사항 ====
        1. 이 텍스트가 실제 개발/작업이 필요한 구체적인 요구사항인가?
        2. JIRA 티켓으로 만들기에 충분히 명확한가?
        3. 우선순위와 작업 유형이 적절한가?
        4. 개선된 제목과 설명을 제안해주세요.
        5. 예상 작업 시간을 추정해주세요.

        JSON 형식으로 응답해주세요:
        {{
            "is_suitable": true/false,
            "confidence": 0.0-1.0,
            "task_type": "bug_fix|feature|improvement|task|story|research|documentation",
            "priority": "critical|high|medium|low",
            "improved_title": "개선된 제목",
            "improved_description": "개선된 설명",
            "estimated_hours": "예상 시간",
            "reasoning": ["분석 근거1", "분석 근거2", ...]
        }}
        """
        return prompt
    
    def _parse_llm_response(self, llm_response: str, basic_result: TaskAnalysisResult) -> TaskAnalysisResult:
        """LLM 응답 파싱 및 결과 개선"""
        try:
            # JSON 응답 파싱 시도
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                llm_data = json.loads(json_match.group())
                
                # LLM 결과로 기본 분석 결과 개선
                if "is_suitable" in llm_data:
                    if llm_data["is_suitable"]:
                        if basic_result.eligibility == JiraEligibility.NOT_SUITABLE:
                            basic_result.eligibility = JiraEligibility.PARTIALLY_SUITABLE
                    else:
                        basic_result.eligibility = JiraEligibility.NOT_SUITABLE
                
                if "confidence" in llm_data:
                    # 기본 분석과 LLM 분석의 평균
                    basic_result.confidence = (basic_result.confidence + llm_data["confidence"]) / 2
                
                if "improved_title" in llm_data:
                    basic_result.suggested_title = llm_data["improved_title"]
                
                if "improved_description" in llm_data:
                    basic_result.suggested_description = llm_data["improved_description"]
                
                if "estimated_hours" in llm_data:
                    basic_result.estimated_effort = llm_data["estimated_hours"]
                
                if "reasoning" in llm_data:
                    basic_result.reasoning.extend(llm_data["reasoning"])
            
            basic_result.reasoning.append("LLM 고도화 분석 완료")
            
        except Exception as e:
            basic_result.reasoning.append(f"LLM 응답 파싱 오류: {str(e)}")
        
        return basic_result


def analyze_jira_eligibility(text: str, use_llm: bool = False, 
                            azure_processor: Optional[AzureOpenAIImageProcessor] = None) -> TaskAnalysisResult:
    """
    편의 함수: 텍스트의 JIRA 일감 적합성 분석
    
    Args:
        text: 분석할 텍스트
        use_llm: LLM 사용 여부
        azure_processor: Azure OpenAI 프로세서
    
    Returns:
        TaskAnalysisResult: 분석 결과
    """
    analyzer = JiraTaskAnalyzer(use_llm=use_llm, azure_processor=azure_processor)
    return analyzer.analyze_text(text)


if __name__ == "__main__":
    # 테스트 예제
    test_texts = [
        "로그인 버튼이 안 눌러져요. 고쳐주세요.",
        "사용자가 프로필 사진을 업로드할 수 있는 기능을 추가해주세요.",
        "성능이 좀 느린 것 같아요. 뭔가 개선할 방법이 있을까요?",
        "점심 뭐 먹을까요?",
        "API 응답 시간을 2초에서 500ms로 개선해야 합니다. 캐싱 로직 추가 검토 필요.",
        "새로운 결제 시스템 연동을 위한 기술 조사가 필요합니다. PG사 3곳 비교 분석 후 보고서 작성."
    ]
    
    print("🎯 JIRA 일감 적합성 분석 테스트")
    print("=" * 60)
    
    analyzer = JiraTaskAnalyzer(use_llm=False)  # 기본 분석만 사용
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n📝 테스트 {i}: {text}")
        result = analyzer.analyze_text(text)
        
        print(f"   🎯 적합성: {result.eligibility.value} (신뢰도: {result.confidence:.2f})")
        print(f"   📋 작업 유형: {result.task_type.value}")
        print(f"   ⚡ 우선순위: {result.priority.value}")
        print(f"   💡 제안 제목: {result.suggested_title}")
        print(f"   ⏱️  예상 작업시간: {result.estimated_effort}")
        print(f"   🏷️  태그: {', '.join(result.tags)}")
        if result.blockers:
            print(f"   🚫 블로커: {', '.join(result.blockers)}")
        print(f"   📊 분석 근거: {', '.join(result.reasoning[:3])}")