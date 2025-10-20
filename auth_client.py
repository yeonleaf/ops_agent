#!/usr/bin/env python3
"""
Streamlit 앱에서 사용할 인증 클라이언트
인증 API 서버와의 통신을 담당
"""

import requests
import streamlit as st
from typing import Optional, Dict, Any
import json

class AuthClient:
    """인증 클라이언트"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def _get_cookies(self) -> Dict[str, str]:
        """현재 세션의 쿠키 반환"""
        cookies = {}
        if 'session_id' in st.session_state:
            cookies['session_id'] = st.session_state.session_id
        return cookies
    
    def signup(self, email: str, password: str) -> Dict[str, Any]:
        """회원가입"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/signup",
                json={"email": email, "password": password}
            )
            
            # 응답 상태 코드 확인
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"success": False, "message": f"서버 응답 파싱 실패: {response.text}"}
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}
                    
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "인증 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요."}
        except Exception as e:
            return {"success": False, "message": f"회원가입 요청 실패: {str(e)}"}
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """로그인"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            )
            
            # 응답 상태 코드 확인
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("success"):
                        # 쿠키에서 세션 ID 추출
                        cookies = response.cookies
                        if 'session_id' in cookies:
                            st.session_state.session_id = cookies['session_id']
                            st.session_state.is_logged_in = True
                            st.session_state.user_email = email
                    
                    return result
                except json.JSONDecodeError:
                    return {"success": False, "message": f"서버 응답 파싱 실패: {response.text}"}
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}
                    
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "인증 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요."}
        except Exception as e:
            return {"success": False, "message": f"로그인 요청 실패: {str(e)}"}
    
    def logout(self) -> Dict[str, Any]:
        """로그아웃"""
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/auth/logout",
                cookies=cookies
            )
            
            # 세션 상태 초기화
            if 'session_id' in st.session_state:
                del st.session_state.session_id
            if 'is_logged_in' in st.session_state:
                del st.session_state.is_logged_in
            if 'user_email' in st.session_state:
                del st.session_state.user_email
            
            return response.json()
        except Exception as e:
            return {"success": False, "message": f"로그아웃 요청 실패: {str(e)}"}
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        print(f"🍪 auth_client에서 사용자 정보 조회 시도")
        """현재 사용자 정보 조회"""
        try:
            cookies = self._get_cookies()

            # 세션 ID가 없으면 사용자 정보 조회하지 않음
            if not cookies.get('session_id'):
                print(f"🍪 session_id가 없어서 사용자 정보 조회 건너뜀")
                return None

            response = self.session.get(
                f"{self.base_url}/auth/me",
                cookies=cookies
            )

            if response.status_code == 200:
                user_info = response.json()
                print(f"🍪 auth_client에서 사용자 정보 조회: {user_info}")
                # 사용자 이메일을 세션에 저장
                if user_info and 'email' in user_info:
                    st.session_state['user_email'] = user_info['email']
                    print(f"🍪 auth_client에서 사용자 이메일 세션에 저장: {user_info['email']}")
                return user_info
            else:
                return None
        except Exception as e:
            print(f"사용자 정보 조회 실패: {str(e)}")
            return None
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """사용자 정보 조회 (get_current_user의 별칭)"""
        return self.get_current_user()
    
    def update_jira_integration(self, jira_endpoint: str, jira_api_token: str) -> Dict[str, Any]:
        """Jira 연동 정보 저장"""
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/user/integrations/jira",
                json={
                    "jira_endpoint": jira_endpoint,
                    "jira_api_token": jira_api_token
                },
                cookies=cookies
            )
            return response.json()
        except Exception as e:
            return {"success": False, "message": f"Jira 연동 정보 저장 실패: {str(e)}"}
    
    def get_jira_integration(self) -> Dict[str, Any]:
        """Jira 연동 정보 조회"""
        try:
            print("🔍 Jira 연동 상태 확인 요청 시작")
            cookies = self._get_cookies()
            print(f"🍪 요청 쿠키: {cookies}")
            
            response = self.session.get(
                f"{self.base_url}/user/integrations/jira",
                cookies=cookies
            )
            
            print(f"📡 Jira 연동 상태 응답: {response.status_code}")
            result = response.json()
            print(f"📋 Jira 연동 상태 결과: {result}")
            
            return result
        except Exception as e:
            print(f"❌ Jira 연동 상태 확인 오류: {str(e)}")
            return {"success": False, "message": f"Jira 연동 정보 조회 실패: {str(e)}"}
    
    def get_google_integration(self) -> Dict[str, Any]:
        """Google 연동 정보 조회"""
        try:
            print("🔍 Google 연동 상태 확인 요청 시작")
            cookies = self._get_cookies()
            print(f"🍪 요청 쿠키: {cookies}")
            
            response = self.session.get(
                f"{self.base_url}/user/integrations/google",
                cookies=cookies
            )
            
            print(f"📡 Google 연동 상태 응답: {response.status_code}")
            result = response.json()
            print(f"📋 Google 연동 상태 결과: {result}")
            
            return result
        except Exception as e:
            print(f"❌ Google 연동 상태 확인 오류: {str(e)}")
            return {"success": False, "message": f"Google 연동 정보 조회 실패: {str(e)}"}
    
    def update_google_integration(self, refresh_token: str) -> Dict[str, Any]:
        """Google 연동 정보 업데이트 (refresh_token 저장)"""
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/user/integrations/google",
                json={"email": "", "refresh_token": refresh_token},  # email은 빈 문자열로 전달
                cookies=cookies
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}
                    
        except Exception as e:
            return {"success": False, "message": f"Google 연동 정보 업데이트 실패: {str(e)}"}
    
    def get_kakao_integration(self) -> Dict[str, Any]:
        """카카오 연동 정보 조회"""
        try:
            print("🔍 카카오 연동 상태 확인 요청 시작")
            cookies = self._get_cookies()
            print(f"🍪 요청 쿠키: {cookies}")

            response = self.session.get(
                f"{self.base_url}/user/integrations/kakao",
                cookies=cookies
            )

            print(f"📡 카카오 연동 상태 응답: {response.status_code}")
            result = response.json()
            print(f"📋 카카오 연동 상태 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 카카오 연동 상태 확인 오류: {str(e)}")
            return {"success": False, "message": f"카카오 연동 정보 조회 실패: {str(e)}", "linked": False}

    def get_kakao_callback_data(self, code: str) -> Dict[str, Any]:
        """카카오 OAuth 콜백 데이터 가져오기 (Access Token + 이메일) - 사용 안 함"""
        try:
            print(f"🔍 카카오 콜백 데이터 요청: code={code[:10]}...")

            response = self.session.get(
                f"{self.base_url}/auth/kakao/link/callback/data",
                params={"code": code}
            )

            print(f"📡 카카오 콜백 데이터 응답: {response.status_code}")
            result = response.json()
            print(f"📋 카카오 콜백 데이터 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 카카오 콜백 데이터 조회 오류: {str(e)}")
            return {"success": False, "message": f"카카오 콜백 데이터 조회 실패: {str(e)}"}

    def get_kakao_temp_data(self, kakao_session_id: str) -> Dict[str, Any]:
        """임시 저장소에서 카카오 인증 정보 가져오기"""
        try:
            print(f"🔍 카카오 임시 데이터 조회: session_id={kakao_session_id[:8]}...")

            response = self.session.get(
                f"{self.base_url}/auth/kakao/temp",
                params={"kakao_session_id": kakao_session_id}
            )

            print(f"📡 카카오 임시 데이터 응답: {response.status_code}")
            result = response.json()
            print(f"📋 카카오 임시 데이터 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 카카오 임시 데이터 조회 오류: {str(e)}")
            return {"success": False, "message": f"카카오 임시 데이터 조회 실패: {str(e)}"}

    def delete_kakao_temp_data(self, kakao_session_id: str) -> Dict[str, Any]:
        """임시 저장소에서 카카오 인증 정보 삭제"""
        try:
            print(f"🗑️  카카오 임시 데이터 삭제: session_id={kakao_session_id[:8]}...")

            response = self.session.delete(
                f"{self.base_url}/auth/kakao/temp",
                params={"kakao_session_id": kakao_session_id}
            )

            print(f"📡 카카오 임시 데이터 삭제 응답: {response.status_code}")
            result = response.json()
            print(f"📋 카카오 임시 데이터 삭제 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 카카오 임시 데이터 삭제 오류: {str(e)}")
            return {"success": False, "message": f"카카오 임시 데이터 삭제 실패: {str(e)}"}

    def save_kakao_integration(self, kakao_id: str) -> Dict[str, Any]:
        """카카오 연동 정보 저장 (카카오 ID만 저장)"""
        try:
            print(f"🔍 카카오 연동 저장 요청: kakao_id={kakao_id}")
            cookies = self._get_cookies()
            print(f"🍪 요청 쿠키: {cookies}")

            response = self.session.post(
                f"{self.base_url}/user/integrations/kakao",
                json={
                    "kakao_id": kakao_id
                },
                cookies=cookies
            )

            print(f"📡 카카오 연동 저장 응답: {response.status_code}")
            result = response.json()
            print(f"📋 카카오 연동 저장 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 카카오 연동 저장 오류: {str(e)}")
            return {"success": False, "message": f"카카오 연동 정보 저장 실패: {str(e)}"}

    def get_slack_integration(self) -> Dict[str, Any]:
        """슬랙 연동 정보 조회"""
        try:
            print("🔍 슬랙 연동 상태 확인 요청 시작")
            cookies = self._get_cookies()
            print(f"🍪 요청 쿠키: {cookies}")

            response = self.session.get(
                f"{self.base_url}/user/integrations/slack",
                cookies=cookies
            )

            print(f"📡 슬랙 연동 상태 응답: {response.status_code}")
            result = response.json()
            print(f"📋 슬랙 연동 상태 결과: {result}")

            return result
        except Exception as e:
            print(f"❌ 슬랙 연동 상태 확인 오류: {str(e)}")
            return {"success": False, "message": f"슬랙 연동 정보 조회 실패: {str(e)}", "linked": False}

    def is_logged_in(self) -> bool:
        """로그인 상태 확인"""
        print(f"🍪 auth_client.is_logged_in() 호출됨")
        print(f"🍪 현재 세션 상태: is_logged_in={st.session_state.get('is_logged_in', False)}")

        # 서버에서 사용자 정보 확인 (세션 상태와 관계없이)
        print(f"🍪 get_current_user() 호출 전")
        user_info = self.get_current_user()
        print(f"🍪 get_current_user() 호출 후: {user_info}")

        if user_info is None:
            # 세션이 만료되었거나 유효하지 않음
            st.session_state.is_logged_in = False
            print(f"🍪 사용자 정보 없음 - 로그인되지 않음")
            return False

        # 사용자 정보가 있으면 로그인 상태로 설정
        st.session_state.is_logged_in = True
        print(f"🍪 사용자 정보 있음 - 로그인됨")
        return True

    # === Jira 온보딩 API 메서드 ===

    def validate_jira_credentials(self, jira_endpoint: str, jira_api_token: str) -> Dict[str, Any]:
        """
        Jira 인증 정보 검증 (/myself API 호출)

        Args:
            jira_endpoint: Jira 엔드포인트 URL
            jira_api_token: Jira API 토큰

        Returns:
            검증 결과 (성공 여부, 사용자 정보 등)
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/validate",
                json={
                    "jira_endpoint": jira_endpoint,
                    "jira_api_token": jira_api_token
                },
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 인증 검증 실패: {str(e)}"}

    def save_jira_credentials(self, jira_endpoint: str, jira_api_token: str) -> Dict[str, Any]:
        """
        Jira 인증 정보 저장 (endpoint, token)

        Args:
            jira_endpoint: Jira 엔드포인트 URL
            jira_api_token: Jira API 토큰

        Returns:
            저장 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/credentials",
                json={
                    "jira_endpoint": jira_endpoint,
                    "jira_api_token": jira_api_token
                },
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 인증 정보 저장 실패: {str(e)}"}

    def get_jira_projects(self) -> Dict[str, Any]:
        """
        Jira 프로젝트 목록 조회 (/project API 호출)

        Returns:
            프로젝트 목록 (성공 여부, 프로젝트 리스트 등)
        """
        try:
            cookies = self._get_cookies()
            response = self.session.get(
                f"{self.base_url}/jira/projects",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 프로젝트 조회 실패: {str(e)}"}

    def save_jira_projects(self, projects: list) -> Dict[str, Any]:
        """
        선택한 Jira 프로젝트 저장

        Args:
            projects: 선택한 프로젝트 키 리스트

        Returns:
            저장 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/projects",
                json={"projects": projects},
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 프로젝트 저장 실패: {str(e)}"}

    def validate_jira_labels(self, project_key: str, labels: list) -> Dict[str, Any]:
        """
        프로젝트와 레이블 조합으로 JQL 쿼리 검증

        Args:
            project_key: Jira 프로젝트 키
            labels: 필터링할 레이블 리스트

        Returns:
            검증 결과 (성공 여부, 이슈 개수 등)
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/validate-labels",
                json={
                    "project_key": project_key,
                    "labels": labels
                },
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"JQL 쿼리 검증 실패: {str(e)}"}

    def save_jira_labels(self, labels_config: dict) -> Dict[str, Any]:
        """
        프로젝트별 레이블 설정 저장

        Args:
            labels_config: {'project_key': ['label1', 'label2']} 형태의 딕셔너리

        Returns:
            저장 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/labels",
                json={"labels_config": labels_config},
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 레이블 저장 실패: {str(e)}"}

    def reset_jira_integration(self) -> Dict[str, Any]:
        """
        Jira 연동 정보 전체 삭제 (재설정용)

        Returns:
            삭제 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.delete(
                f"{self.base_url}/jira/integration",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Jira 연동 정보 삭제 실패: {str(e)}"}

# 전역 인스턴스
auth_client = AuthClient()
