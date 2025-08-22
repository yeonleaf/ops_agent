#!/usr/bin/env python3
"""
메일 주소 도메인 분류기
내부/외부 메일을 구분하여 내부 메일은 티켓 생성 대상에서 제외
"""

import re
from typing import List, Dict, Optional, Tuple
from enum import Enum


class EmailType(Enum):
    """메일 유형"""
    INTERNAL = "internal"      # 내부 메일
    EXTERNAL = "external"      # 외부 메일
    UNKNOWN = "unknown"        # 미분류 (사용자 입력 필요)


class EmailDomainClassifier:
    """메일 도메인 분류기"""
    
    def __init__(self, internal_domains: List[str] = None, external_domains: List[str] = None):
        """
        초기화
        
        Args:
            internal_domains: 내부 도메인 리스트 (예: ["@skcc.com", "@sk.com"])
            external_domains: 외부 도메인 리스트 (예: ["@gmail.com", "@naver.com"])
        """
        self.internal_domains = internal_domains or []
        self.external_domains = external_domains or []
        self.unknown_domains_cache = {}  # 미분류 도메인 캐시
        
    def extract_domain_from_email(self, email: str) -> Optional[str]:
        """이메일 주소에서 도메인 추출"""
        if not email:
            return None
            
        # 이메일 주소에서 도메인 부분 추출
        email_pattern = r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        match = re.search(email_pattern, email)
        
        if match:
            return f"@{match.group(2).lower()}"
        return None
    
    def classify_email_domain(self, domain: str) -> EmailType:
        """도메인을 내부/외부/미분류로 분류"""
        if not domain:
            return EmailType.UNKNOWN
            
        domain = domain.lower()
        
        # 내부 도메인 확인
        for internal_domain in self.internal_domains:
            if domain == internal_domain.lower() or domain.endswith(internal_domain.lower()):
                return EmailType.INTERNAL
        
        # 외부 도메인 확인
        for external_domain in self.external_domains:
            if domain == external_domain.lower() or domain.endswith(external_domain.lower()):
                return EmailType.EXTERNAL
        
        # 캐시에서 확인
        if domain in self.unknown_domains_cache:
            return self.unknown_domains_cache[domain]
        
        return EmailType.UNKNOWN
    
    def classify_email(self, email: str, interactive: bool = True) -> Tuple[EmailType, str]:
        """
        이메일 주소를 분류
        
        Args:
            email: 이메일 주소
            interactive: 미분류 도메인에 대해 사용자 입력을 받을지 여부
            
        Returns:
            (EmailType, 도메인) 튜플
        """
        domain = self.extract_domain_from_email(email)
        if not domain:
            return EmailType.UNKNOWN, ""
        
        email_type = self.classify_email_domain(domain)
        
        # 미분류이고 interactive 모드인 경우 사용자에게 문의
        if email_type == EmailType.UNKNOWN and interactive:
            email_type = self._ask_user_for_classification(domain, email)
            
        return email_type, domain
    
    def _ask_user_for_classification(self, domain: str, email: str) -> EmailType:
        """사용자에게 도메인 분류를 요청"""
        print(f"\n⚠️  알 수 없는 도메인이 발견되었습니다!")
        print(f"📧 이메일: {email}")
        print(f"🌐 도메인: {domain}")
        print(f"이 도메인을 어떻게 분류하시겠습니까?")
        print(f"1. 내부 메일 (티켓 생성 제외)")
        print(f"2. 외부 메일 (티켓 생성 대상)")
        
        while True:
            try:
                choice = input("선택하세요 (1 또는 2): ").strip()
                if choice == "1":
                    self.unknown_domains_cache[domain] = EmailType.INTERNAL
                    print(f"✅ {domain}을 내부 도메인으로 분류했습니다.")
                    return EmailType.INTERNAL
                elif choice == "2":
                    self.unknown_domains_cache[domain] = EmailType.EXTERNAL
                    print(f"✅ {domain}을 외부 도메인으로 분류했습니다.")
                    return EmailType.EXTERNAL
                else:
                    print("❌ 1 또는 2를 입력해주세요.")
            except (EOFError, KeyboardInterrupt):
                print(f"\n⏭️  입력을 건너뛰고 {domain}을 외부 도메인으로 처리합니다.")
                self.unknown_domains_cache[domain] = EmailType.EXTERNAL
                return EmailType.EXTERNAL
    
    def add_internal_domain(self, domain: str):
        """내부 도메인 추가"""
        if domain not in self.internal_domains:
            self.internal_domains.append(domain)
    
    def add_external_domain(self, domain: str):
        """외부 도메인 추가"""
        if domain not in self.external_domains:
            self.external_domains.append(domain)
    
    def should_create_ticket(self, email: str, interactive: bool = True) -> Tuple[bool, str, str]:
        """
        해당 이메일이 티켓 생성 대상인지 판단
        
        Args:
            email: 이메일 주소
            interactive: 미분류 도메인에 대해 사용자 입력을 받을지 여부
            
        Returns:
            (티켓생성여부, 이메일타입, 도메인) 튜플
        """
        email_type, domain = self.classify_email(email, interactive)
        
        # 내부 메일은 티켓 생성 대상이 아님
        should_create = email_type != EmailType.INTERNAL
        
        return should_create, email_type.value, domain
    
    def get_classification_stats(self) -> Dict[str, int]:
        """분류 통계 반환"""
        stats = {
            "total_internal_domains": len(self.internal_domains),
            "total_external_domains": len(self.external_domains),
            "cached_unknown_domains": len(self.unknown_domains_cache)
        }
        return stats
    
    def print_domain_lists(self):
        """현재 도메인 리스트 출력"""
        print("\n📋 도메인 분류 현황")
        print("=" * 50)
        
        print(f"🏢 내부 도메인 ({len(self.internal_domains)}개):")
        for domain in self.internal_domains:
            print(f"   - {domain}")
        
        print(f"\n🌍 외부 도메인 ({len(self.external_domains)}개):")
        for domain in self.external_domains:
            print(f"   - {domain}")
        
        if self.unknown_domains_cache:
            print(f"\n❓ 학습된 미분류 도메인 ({len(self.unknown_domains_cache)}개):")
            for domain, email_type in self.unknown_domains_cache.items():
                print(f"   - {domain} → {email_type.value}")


# 테스트 함수
def test_email_classifier():
    """이메일 분류기 테스트"""
    print("🧪 이메일 도메인 분류기 테스트")
    print("=" * 50)
    
    # 분류기 초기화
    classifier = EmailDomainClassifier(
        internal_domains=["@skcc.com", "@sk.com"],
        external_domains=["@gmail.com", "@naver.com"]
    )
    
    # 테스트 이메일들
    test_emails = [
        "user@skcc.com",
        "test@sk.com", 
        "external@gmail.com",
        "someone@naver.com",
        "unknown@example.com",
        "jira@skbroadband.com",
        "invalid-email"
    ]
    
    print("\n📧 이메일 분류 테스트:")
    for email in test_emails:
        should_create, email_type, domain = classifier.should_create_ticket(email, interactive=False)
        print(f"   {email:25} → {email_type:8} {domain:20} 티켓생성: {'✅' if should_create else '❌'}")
    
    # 통계 출력
    print(f"\n📊 분류 통계:")
    stats = classifier.get_classification_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    classifier.print_domain_lists()


if __name__ == "__main__":
    test_email_classifier()