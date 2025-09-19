#!/usr/bin/env python3
"""
TicketingAgent 중복 호출 수정 테스트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ticketing_agent_prompt():
    """TicketingAgent의 시스템 프롬프트가 올바르게 수정되었는지 테스트"""
    try:
        from specialist_agents import TicketingAgent
        from langchain_openai import AzureChatOpenAI

        # 더미 LLM 클라이언트 생성
        llm = AzureChatOpenAI(
            azure_deployment="gpt-4.1",
            api_version="2024-10-21",
            temperature=0.7
        )

        # TicketingAgent 인스턴스 생성
        ticketing_agent = TicketingAgent(llm)

        # 시스템 프롬프트 확인
        prompt = ticketing_agent.system_prompt

        print("🔍 TicketingAgent 시스템 프롬프트 검사:")
        print("=" * 50)

        # 중복 호출 방지 관련 내용이 포함되어 있는지 확인
        checks = [
            ("중복 메일 조회 방지", "중복 메일 조회 방지" in prompt),
            ("RouterAgent에서", "RouterAgent에서" in prompt),
            ("read_emails_tool을 사용하지 말고", "read_emails_tool을 사용하지 말고" in prompt),
            ("바로 process_tickets_tool을 사용", "바로 process_tickets_tool을 사용" in prompt),
        ]

        all_passed = True
        for check_name, result in checks:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {check_name}")
            if not result:
                all_passed = False

        print("=" * 50)

        # read_emails_tool 설명 확인
        read_tool = None
        for tool in ticketing_agent.tools:
            if tool.name == "read_emails_tool":
                read_tool = tool
                break

        if read_tool:
            tool_desc = read_tool.description
            print("🔍 read_emails_tool 설명 검사:")
            print("=" * 50)

            tool_checks = [
                ("주의 문구 포함", "주의:" in tool_desc),
                ("RouterAgent 중복 방지", "RouterAgent에서 이미" in tool_desc),
                ("사용하지 마세요", "사용하지 마세요" in tool_desc),
            ]

            for check_name, result in tool_checks:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} {check_name}")
                if not result:
                    all_passed = False
        else:
            print("❌ read_emails_tool을 찾을 수 없습니다")
            all_passed = False

        print("=" * 50)

        if all_passed:
            print("🎉 모든 수정사항이 올바르게 적용되었습니다!")
            return True
        else:
            print("❌ 일부 수정사항이 누락되었습니다.")
            return False

    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 TicketingAgent 중복 호출 수정 테스트 시작")
    print()

    success = test_ticketing_agent_prompt()

    print()
    if success:
        print("✅ 테스트 완료: 수정사항이 성공적으로 적용되었습니다!")
        sys.exit(0)
    else:
        print("❌ 테스트 실패: 추가 수정이 필요합니다.")
        sys.exit(1)