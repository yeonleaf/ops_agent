#!/usr/bin/env python3
"""
refresh_trigger 초기화 테스트
"""

import streamlit as st

def test_refresh_trigger():
    """refresh_trigger 초기화 테스트"""
    print("=== refresh_trigger 초기화 테스트 ===")
    
    # 세션 상태 초기화
    if 'refresh_trigger' not in st.session_state:
        st.session_state.refresh_trigger = 0
        print("✅ refresh_trigger 초기화 완료")
    else:
        print(f"✅ refresh_trigger 이미 존재: {st.session_state.refresh_trigger}")
    
    # 값 증가 테스트
    st.session_state.refresh_trigger += 1
    print(f"✅ refresh_trigger 값 증가: {st.session_state.refresh_trigger}")
    
    print("=== 테스트 완료 ===")

if __name__ == "__main__":
    test_refresh_trigger()
