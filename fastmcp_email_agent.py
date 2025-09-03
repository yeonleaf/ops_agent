#!/usr/bin/env python3
"""
FastMCP 기반 이메일 에이전트
기존 LangChain Agent의 시스템 프롬프트를 FastMCP Agent로 마이그레이션
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# FastMCP import
from fastmcp import FastMCP

# LangChain imports for LLM
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("EmailAgent")

# 사용 가능한 도구들의 상세 정보
AVAILABLE_TOOLS = {
    "get_raw_emails": {
        "name": "get_raw_emails",
        "description": "사용자의 특정 조건에 맞는 순수 이메일 목록을 반환합니다. 필터 조건에는 읽음 상태, 발신자, 제목, 첨부파일 여부, 날짜 범위 등이 포함될 수 있습니다.",
        "use_cases": [
            "특정 조건의 이메일을 조회하고 싶을 때",
            "읽은/안 읽은 메일을 필터링하고 싶을 때", 
            "특정 발신자의 메일을 찾고 싶을 때",
            "제목이나 내용으로 메일을 검색하고 싶을 때",
            "단순히 이메일 목록만 보고 싶을 때"
        ],
        "parameters": {
            "provider_name": "이메일 제공자 이름 (gmail, outlook)",
            "filters": "필터 조건 (읽음 상태, 발신자, 제목 등)"
        }
    },
    "process_emails_with_ticket_logic": {
        "name": "process_emails_with_ticket_logic", 
        "description": "안 읽은 메일을 가져와서 업무용 메일만 필터링하고, 유사 메일 검색을 통해 레이블을 생성한 후 티켓을 생성합니다. LLM 기반 업무용 메일 필터링과 Memory-Based 레이블 추천을 포함합니다.",
        "use_cases": [
            "안 읽은 메일을 처리하고 티켓을 생성하고 싶을 때",
            "업무용 메일만 필터링하고 싶을 때",
            "자동으로 티켓을 생성하고 싶을 때",
            "메일을 분석하여 적절한 레이블을 추천받고 싶을 때"
        ],
        "parameters": {
            "provider_name": "이메일 제공자 이름 (gmail, outlook)",
            "user_query": "사용자 쿼리 (티켓 생성 시 참고용)"
        }
    },
    "get_email_provider_status": {
        "name": "get_email_provider_status",
        "description": "이메일 제공자의 연결 상태와 설정 정보를 확인합니다. 연결 상태, 인증 상태, 사용 가능한 기능 등을 점검합니다.",
        "use_cases": [
            "이메일 제공자 연결 상태를 확인하고 싶을 때",
            "시스템 상태를 점검하고 싶을 때",
            "인증 문제를 해결하고 싶을 때",
            "Gmail이나 Outlook 연결을 확인하고 싶을 때"
        ],
        "parameters": {
            "provider_name": "확인할 이메일 제공자 이름 (선택사항)"
        }
    },
    "get_mail_content_by_id": {
        "name": "get_mail_content_by_id",
        "description": "VectorDB에서 message_id로 메일 상세 내용을 조회합니다. 메일의 원본 내용, 정제된 내용, 요약, 핵심 포인트 등의 정보를 제공합니다.",
        "use_cases": [
            "특정 메일의 상세 내용을 보고 싶을 때",
            "메일의 요약이나 핵심 포인트를 확인하고 싶을 때",
            "메일 ID로 특정 메일을 찾고 싶을 때"
        ],
        "parameters": {
            "message_id": "조회할 메일의 고유 ID"
        }
    },
    "create_ticket_from_single_email": {
        "name": "create_ticket_from_single_email",
        "description": "단일 이메일을 티켓으로 변환합니다. Memory-Based 학습 시스템을 사용하여 이메일의 내용을 분석하고, 적절한 우선순위, 레이블, 티켓 타입을 자동으로 결정합니다.",
        "use_cases": [
            "특정 이메일 하나를 티켓으로 만들고 싶을 때",
            "단일 메일을 분석하여 티켓을 생성하고 싶을 때"
        ],
        "parameters": {
            "email_data": "이메일 데이터 (ID, 제목, 발신자, 내용 등)"
        }
    },
    "fetch_emails_sync": {
        "name": "fetch_emails_sync",
        "description": "동기적으로 이메일을 가져와서 티켓 형태로 변환하여 반환합니다. 분류기 사용 여부를 선택할 수 있으며, 최대 결과 수를 제한할 수 있습니다.",
        "use_cases": [
            "이메일을 티켓 형태로 조회하고 싶을 때",
            "분류기를 사용하여 이메일을 처리하고 싶을 때",
            "제한된 수의 이메일만 가져오고 싶을 때"
        ],
        "parameters": {
            "provider_name": "이메일 제공자 이름",
            "use_classifier": "분류기 사용 여부",
            "max_results": "최대 결과 수"
        }
    }
}

# LLM 기반 도구 선택을 위한 프롬프트
TOOL_SELECTION_PROMPT = """당신은 이메일 관리 시스템의 도구 선택 전문가입니다.

사용자의 요청을 분석하여 가장 적절한 도구를 선택해야 합니다.

## 사용 가능한 도구들:

{available_tools}

## 사용자 요청:
{user_query}

## 지침:
1. 사용자의 요청을 정확히 이해하세요
2. 각 도구의 설명과 사용 사례를 고려하세요
3. 가장 적절한 도구를 하나만 선택하세요
4. 선택한 도구의 매개변수도 함께 결정하세요

## 응답 형식:
다음 JSON 형식으로만 응답하세요:
{{
    "selected_tool": "도구_이름",
    "reasoning": "선택 이유",
    "parameters": {{
        "매개변수_이름": "매개변수_값"
    }}
}}

중요: JSON 형식만 사용하고 다른 설명은 추가하지 마세요."""

def select_tool_with_llm(user_query: str) -> Dict[str, Any]:
    """
    LLM을 사용하여 사용자 쿼리에 가장 적절한 도구를 선택합니다.
    
    Args:
        user_query (str): 사용자의 요청
        
    Returns:
        Dict[str, Any]: 선택된 도구 정보
            - selected_tool (str): 선택된 도구 이름
            - reasoning (str): 선택 이유
            - parameters (Dict): 도구 매개변수
    """
    try:
        # Azure OpenAI 설정
        llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # 도구 정보를 문자열로 변환
        tools_info = ""
        for tool_name, tool_info in AVAILABLE_TOOLS.items():
            tools_info += f"\n### {tool_name}\n"
            tools_info += f"**설명**: {tool_info['description']}\n"
            tools_info += f"**사용 사례**:\n"
            for use_case in tool_info['use_cases']:
                tools_info += f"- {use_case}\n"
            tools_info += f"**매개변수**: {tool_info['parameters']}\n"
        
        # 프롬프트 생성
        prompt = ChatPromptTemplate.from_template(TOOL_SELECTION_PROMPT)
        chain = prompt | llm | StrOutputParser()
        
        # LLM 호출
        response = chain.invoke({
            "available_tools": tools_info,
            "user_query": user_query
        })
        
        # JSON 파싱
        try:
            result = json.loads(response)
            logging.info(f"🧠 LLM 도구 선택 결과: {result['selected_tool']} - {result['reasoning']}")
            return result
        except json.JSONDecodeError:
            logging.error(f"❌ LLM 응답 JSON 파싱 실패: {response}")
            # 기본값 반환
            return {
                "selected_tool": "get_raw_emails",
                "reasoning": "JSON 파싱 실패로 기본 도구 선택",
                "parameters": {"provider_name": "gmail", "filters": {}}
            }
            
    except Exception as e:
        logging.error(f"❌ LLM 도구 선택 실패: {str(e)}")
        # 기본값 반환
        return {
            "selected_tool": "get_raw_emails", 
            "reasoning": f"LLM 호출 실패: {str(e)}",
            "parameters": {"provider_name": "gmail", "filters": {}}
        }

def execute_selected_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    선택된 도구를 실행합니다.
    
    Args:
        tool_name (str): 실행할 도구 이름
        parameters (Dict[str, Any]): 도구 매개변수
        
    Returns:
        Dict[str, Any]: 도구 실행 결과
    """
    try:
        # 도구별 실행 로직
        if tool_name == "get_raw_emails":
            from unified_email_service import get_raw_emails
            result = get_raw_emails(
                parameters.get("provider_name", "gmail"),
                parameters.get("filters", {})
            )
            
        elif tool_name == "process_emails_with_ticket_logic":
            from unified_email_service import process_emails_with_ticket_logic
            result = process_emails_with_ticket_logic(
                parameters.get("provider_name", "gmail"),
                parameters.get("user_query", "")
            )
            
        elif tool_name == "get_email_provider_status":
            from unified_email_service import get_email_provider_status
            result = get_email_provider_status(
                parameters.get("provider_name")
            )
            
        elif tool_name == "get_mail_content_by_id":
            from unified_email_service import get_mail_content_by_id
            result = get_mail_content_by_id(
                parameters.get("message_id")
            )
            
        elif tool_name == "create_ticket_from_single_email":
            from unified_email_service import create_ticket_from_single_email
            result = create_ticket_from_single_email(
                parameters.get("email_data")
            )
            
        elif tool_name == "fetch_emails_sync":
            from unified_email_service import fetch_emails_sync
            result = fetch_emails_sync(
                parameters.get("provider_name", "gmail"),
                parameters.get("use_classifier", False),
                parameters.get("max_results", 50)
            )
            
        else:
            raise ValueError(f"알 수 없는 도구: {tool_name}")
        
        logging.info(f"✅ 도구 '{tool_name}' 실행 완료")
        return result
        
    except Exception as e:
        logging.error(f"❌ 도구 '{tool_name}' 실행 실패: {str(e)}")
        return {
            "error": str(e),
            "tool_name": tool_name,
            "parameters": parameters
        }

# 시스템 프롬프트 (기존 LangChain Agent에서 마이그레이션)
SYSTEM_PROMPT = """당신은 이메일 관리 및 티켓 생성 전문 AI 어시스턴트입니다.

## 역할 및 책임
- 사용자의 이메일 관련 요청을 이해하고 적절한 도구를 선택하여 실행합니다
- 이메일 조회, 필터링, 티켓 생성 등의 작업을 수행합니다
- 사용자에게 명확하고 유용한 정보를 제공합니다

## 사용 가능한 도구들

### 1. get_raw_emails
- **목적**: 특정 조건에 맞는 순수 이메일 목록 조회
- **사용 시기**: 사용자가 특정 조건의 이메일을 요청할 때
- **매개변수**: provider_name (이메일 제공자), filters (필터 조건)

### 2. process_emails_with_ticket_logic
- **목적**: 안 읽은 메일을 업무용으로 필터링하고 티켓 생성
- **사용 시기**: 사용자가 "안 읽은 메일 처리", "티켓 생성" 등을 요청할 때
- **매개변수**: provider_name (이메일 제공자), user_query (사용자 쿼리)

### 3. get_email_provider_status
- **목적**: 이메일 제공자의 연결 상태 확인
- **사용 시기**: 시스템 상태 점검이나 연결 문제 해결 시
- **매개변수**: provider_name (이메일 제공자, 선택사항)

### 4. get_mail_content_by_id
- **목적**: 특정 메일의 상세 내용 조회
- **사용 시기**: 사용자가 특정 메일의 자세한 내용을 요청할 때
- **매개변수**: message_id (메일 ID)

### 5. create_ticket_from_single_email
- **목적**: 단일 이메일을 티켓으로 변환
- **사용 시기**: 사용자가 특정 이메일을 티켓으로 만들고 싶을 때
- **매개변수**: email_data (이메일 데이터)

### 6. fetch_emails_sync
- **목적**: 동기적으로 이메일을 가져와서 티켓 형태로 변환
- **사용 시기**: 사용자가 이메일을 티켓 형태로 조회하고 싶을 때
- **매개변수**: provider_name, use_classifier, max_results

## 작업 규칙

### 이메일 조회 관련
1. **안 읽은 메일 요청**: `process_emails_with_ticket_logic` 사용
2. **특정 조건 메일**: `get_raw_emails` 사용
3. **메일 상세 내용**: `get_mail_content_by_id` 사용
4. **티켓 형태 조회**: `fetch_emails_sync` 사용

### 티켓 생성 관련
1. **자동 티켓 생성**: `process_emails_with_ticket_logic` 사용
2. **단일 메일 티켓**: `create_ticket_from_single_email` 사용

### 시스템 상태 관련
1. **연결 상태 확인**: `get_email_provider_status` 사용

## 응답 형식
- 도구 실행 결과를 사용자에게 명확하게 설명
- 오류 발생 시 구체적인 오류 메시지와 해결 방안 제시
- 한국어로 친근하고 전문적인 톤으로 응답

## 주의사항
- 사용자의 요청을 정확히 파악한 후 적절한 도구 선택
- 도구 실행 전 필요한 매개변수가 모두 있는지 확인
- 민감한 정보는 적절히 마스킹하여 표시
- 오류 발생 시 사용자에게 도움이 되는 정보 제공
"""

def email_agent_logic(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    이메일 관리 및 티켓 생성 전문 AI 어시스턴트 (LLM 기반 도구 선택)
    
    LLM을 사용하여 사용자의 이메일 관련 요청을 이해하고 적절한 도구를 선택하여 실행합니다.
    
    Args:
        user_query (str): 사용자의 요청 또는 질문
        context (Optional[Dict[str, Any]]): 추가 컨텍스트 정보
    
    Returns:
        Dict[str, Any]: 처리 결과
            - success (bool): 처리 성공 여부
            - message (str): 응답 메시지
            - data (Any): 처리된 데이터
            - tools_used (List[str]): 사용된 도구 목록
            - tool_selection (Dict): 도구 선택 정보
            - error (str, optional): 오류 메시지
    """
    try:
        logging.info(f"🤖 이메일 에이전트 요청 처리 시작: {user_query}")
        
        # 1단계: LLM을 사용하여 적절한 도구 선택
        logging.info("🧠 LLM 기반 도구 선택 시작...")
        tool_selection = select_tool_with_llm(user_query)
        selected_tool = tool_selection.get("selected_tool")
        reasoning = tool_selection.get("reasoning", "")
        parameters = tool_selection.get("parameters", {})
        
        logging.info(f"🎯 선택된 도구: {selected_tool}")
        logging.info(f"💭 선택 이유: {reasoning}")
        
        # 2단계: 선택된 도구 실행
        logging.info(f"⚙️ 도구 '{selected_tool}' 실행 시작...")
        result_data = execute_selected_tool(selected_tool, parameters)
        
        # 3단계: 결과 처리 및 응답 메시지 생성
        response_message = generate_response_message(selected_tool, result_data, reasoning)
        
        logging.info(f"✅ 이메일 에이전트 요청 처리 완료: {selected_tool} 도구 사용")
        
        return {
            "success": True,
            "message": response_message,
            "data": result_data,
            "tools_used": [selected_tool],
            "tool_selection": tool_selection,
            "query": user_query
        }
        
    except Exception as e:
        logging.error(f"❌ 이메일 에이전트 오류: {str(e)}")
        return {
            "success": False,
            "message": f"요청 처리 중 오류가 발생했습니다: {str(e)}",
            "data": None,
            "tools_used": [],
            "tool_selection": {},
            "error": str(e),
            "query": user_query
        }

def generate_response_message(tool_name: str, result_data: Any, reasoning: str) -> str:
    """
    도구 실행 결과를 바탕으로 사용자에게 보여줄 응답 메시지를 생성합니다.
    
    Args:
        tool_name (str): 사용된 도구 이름
        result_data (Any): 도구 실행 결과
        reasoning (str): 도구 선택 이유
        
    Returns:
        str: 사용자에게 보여줄 응답 메시지
    """
    try:
        response_message = f"🧠 **AI 분석**: {reasoning}\n\n"
        
        if tool_name == "get_raw_emails":
            if isinstance(result_data, list) and result_data:
                response_message += f"✅ {len(result_data)}개의 이메일을 찾았습니다.\n\n"
                for i, email in enumerate(result_data[:5], 1):  # 최대 5개만 표시
                    # EmailMessage 객체인 경우 딕셔너리로 변환
                    if hasattr(email, 'model_dump'):
                        email_dict = email.model_dump()
                    elif hasattr(email, '__dict__'):
                        email_dict = email.__dict__
                    else:
                        email_dict = email
                    
                    response_message += f"{i}. {email_dict.get('subject', '제목 없음')}\n"
                    response_message += f"   발신자: {email_dict.get('sender', 'N/A')}\n"
                    response_message += f"   읽음 상태: {'읽음' if email_dict.get('is_read') else '안 읽음'}\n\n"
                
                if len(result_data) > 5:
                    response_message += f"... 외 {len(result_data) - 5}개 더\n"
            else:
                response_message += "조건에 맞는 이메일을 찾을 수 없습니다."
                
        elif tool_name == "process_emails_with_ticket_logic":
            if result_data.get('display_mode') == 'tickets':
                tickets = result_data.get('tickets', [])
                new_tickets = result_data.get('new_tickets_created', 0)
                existing_tickets = result_data.get('existing_tickets_found', 0)
                
                response_message += f"✅ 안 읽은 메일 처리 완료!\n"
                response_message += f"📊 총 {len(tickets)}개의 티켓을 처리했습니다.\n"
                response_message += f"🆕 새로 생성된 티켓: {new_tickets}개\n"
                response_message += f"📋 기존 티켓: {existing_tickets}개\n\n"
                
                if tickets:
                    response_message += "📋 처리된 티켓 목록:\n"
                    for i, ticket in enumerate(tickets[:5], 1):  # 최대 5개만 표시
                        response_message += f"{i}. {ticket.get('title', '제목 없음')} (상태: {ticket.get('status', 'N/A')})\n"
                    
                    if len(tickets) > 5:
                        response_message += f"... 외 {len(tickets) - 5}개 더\n"
            else:
                response_message += result_data.get('message', '처리 결과를 가져올 수 없습니다.')
                
        elif tool_name == "get_email_provider_status":
            if result_data.get('is_connected'):
                response_message += f"✅ {result_data.get('provider_name', '이메일 제공자')} 연결 상태: 정상\n"
                response_message += f"🔐 인증 상태: {'인증됨' if result_data.get('is_authenticated') else '인증 필요'}\n"
                response_message += f"🛠️ 사용 가능한 기능: {', '.join(result_data.get('available_features', []))}\n"
            else:
                response_message += f"❌ {result_data.get('provider_name', '이메일 제공자')} 연결 상태: 오류\n"
                response_message += f"오류 메시지: {result_data.get('error_message', '알 수 없는 오류')}\n"
                
        elif tool_name == "get_mail_content_by_id":
            if result_data:
                response_message += f"✅ 메일 상세 내용 조회 완료\n\n"
                response_message += f"**제목**: {result_data.get('subject', 'N/A')}\n"
                response_message += f"**발신자**: {result_data.get('sender', 'N/A')}\n"
                response_message += f"**수신 시간**: {result_data.get('received_datetime', 'N/A')}\n"
                response_message += f"**요약**: {result_data.get('content_summary', 'N/A')}\n"
                if result_data.get('key_points'):
                    response_message += f"**핵심 포인트**: {', '.join(result_data.get('key_points', []))}\n"
            else:
                response_message += "해당 메일을 찾을 수 없습니다."
                
        elif tool_name == "create_ticket_from_single_email":
            if result_data.get('ticket_id'):
                response_message += f"✅ 티켓 생성 완료!\n\n"
                response_message += f"**티켓 ID**: {result_data.get('ticket_id')}\n"
                response_message += f"**제목**: {result_data.get('title', 'N/A')}\n"
                response_message += f"**상태**: {result_data.get('status', 'N/A')}\n"
                response_message += f"**우선순위**: {result_data.get('priority', 'N/A')}\n"
                response_message += f"**타입**: {result_data.get('type', 'N/A')}\n"
                if result_data.get('labels'):
                    response_message += f"**레이블**: {', '.join(result_data.get('labels', []))}\n"
            else:
                response_message += f"❌ 티켓 생성 실패: {result_data.get('error_message', '알 수 없는 오류')}"
                
        elif tool_name == "fetch_emails_sync":
            if result_data.get('tickets'):
                tickets = result_data.get('tickets', [])
                response_message += f"✅ {len(tickets)}개의 이메일을 티켓 형태로 조회했습니다.\n\n"
                for i, ticket in enumerate(tickets[:5], 1):
                    response_message += f"{i}. {ticket.get('title', '제목 없음')}\n"
                    response_message += f"   발신자: {ticket.get('reporter', 'N/A')}\n"
                    response_message += f"   상태: {ticket.get('status', 'N/A')}\n\n"
                
                if len(tickets) > 5:
                    response_message += f"... 외 {len(tickets) - 5}개 더\n"
            else:
                response_message += "조회된 이메일이 없습니다."
        
        else:
            response_message += f"도구 '{tool_name}' 실행 완료"
            
        return response_message
        
    except Exception as e:
        logging.error(f"❌ 응답 메시지 생성 실패: {str(e)}")
        return f"처리 완료되었지만 응답 메시지 생성 중 오류가 발생했습니다: {str(e)}"

# FastMCP 도구로도 등록
@mcp.tool()
def email_agent(user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """이메일 관리 및 티켓 생성 전문 AI 어시스턴트 (FastMCP 도구)"""
    return email_agent_logic(user_query, context)

# FastMCP 앱 실행을 위한 메인 함수
def run_fastmcp_agent():
    """FastMCP 에이전트 실행"""
    mcp.run()

if __name__ == "__main__":
    run_fastmcp_agent()
