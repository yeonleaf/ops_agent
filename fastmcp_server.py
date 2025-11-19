#!/usr/bin/env python3
"""
FastMCP 서버 - 이메일 연동 제거됨 (보안 정책)
Jira 연동 및 기타 기능만 제공
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from fastmcp import FastMCP

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastMCP 인스턴스 생성
mcp = FastMCP("OpsAgentServer")

# ============================================================
# 이메일 관련 기능은 보안 정책으로 제거되었습니다
# ============================================================

@mcp.tool()
def get_server_status() -> dict:
    """
    서버 상태를 확인합니다.
    
    Returns:
        dict: 서버 상태 정보
    """
    try:
        return {
            'status': 'healthy',
            'message': 'FastMCP 서버가 정상 작동 중입니다',
            'email_integration': 'disabled (보안 정책)',
            'jira_integration': 'available',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"서버 상태 확인 실패: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

@mcp.tool()
def simple_llm_call(prompt: str) -> str:
    """
    Azure OpenAI LLM을 호출합니다.
    
    Args:
        prompt: LLM에 전달할 프롬프트
        
    Returns:
        str: LLM의 응답 텍스트
    """
    try:
        from openai import AzureOpenAI
        
        azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4.1')
        azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-10-21')
        
        if not all([azure_endpoint, azure_api_key]):
            return "오류: Azure OpenAI 환경 변수가 설정되지 않았습니다."
        
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version
        )
        
        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logging.error(f"LLM 호출 실패: {e}")
        return f"오류: {str(e)}"

def run_fastmcp_server():
    """FastMCP 서버 실행"""
    logging.info("🚀 FastMCP 서버 시작")
    logging.info("📧 이메일 연동 기능: 제거됨 (보안 정책)")
    logging.info("🔧 등록된 도구들:")
    logging.info("  - get_server_status")
    logging.info("  - simple_llm_call")
    
    # FastMCP 서버 실행
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        log_level="info"
    )

if __name__ == "__main__":
    run_fastmcp_server()
