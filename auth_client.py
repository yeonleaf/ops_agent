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
    
    def signup(self, email: str, password: str, user_name: str, system_name: str = None) -> Dict[str, Any]:
        """회원가입"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/signup",
                json={
                    "email": email,
                    "password": password,
                    "user_name": user_name,
                    "system_name": system_name
                }
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

                            # 서버 응답에서 user_id 추출 및 저장
                            if 'user_id' in result:
                                st.session_state.user_id = result['user_id']
                                print(f"✅ 로그인 성공: user_id={result['user_id']}, email={email}")
                            else:
                                # Fallback: DB에서 직접 조회
                                print(f"⚠️ 서버 응답에 user_id가 없습니다. DB에서 직접 조회합니다.")
                                user_id = self._get_user_id_from_db(email)
                                if user_id:
                                    st.session_state.user_id = user_id
                                    print(f"✅ DB에서 user_id 조회 성공: user_id={user_id}, email={email}")
                                else:
                                    print(f"❌ DB에서 user_id 조회 실패: email={email}")

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

    def _get_user_id_from_db(self, email: str) -> Optional[int]:
        """DB에서 이메일로 user_id 조회 (fallback)"""
        try:
            import sqlite3
            conn = sqlite3.connect("tickets.db")
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return row[0]
            else:
                return None
        except Exception as e:
            print(f"❌ DB에서 user_id 조회 실패: {e}")
            return None
    
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
            if 'user_id' in st.session_state:
                del st.session_state.user_id

            return response.json()
        except Exception as e:
            return {"success": False, "message": f"로그아웃 요청 실패: {str(e)}"}
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """현재 사용자 정보 조회 (session_state에서)"""
        print(f"🍪 auth_client.get_current_user() 호출")

        # session_state에서 로그인 상태 확인
        if not st.session_state.get('is_logged_in', False):
            print(f"🍪 로그인되지 않음")
            return None

        # session_state에서 사용자 정보 가져오기
        user_id = st.session_state.get('user_id')
        user_email = st.session_state.get('user_email')

        if user_id and user_email:
            user_info = {
                'id': user_id,
                'email': user_email
            }
            print(f"🍪 session_state에서 사용자 정보 조회: {user_info}")
            return user_info
        else:
            print(f"🍪 session_state에 user_id 또는 user_email이 없음")
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
        """로그인 상태 확인 (session_state에서)"""
        print(f"🍪 auth_client.is_logged_in() 호출됨")

        # session_state에서 로그인 상태 확인
        is_logged_in = st.session_state.get('is_logged_in', False)
        user_id = st.session_state.get('user_id')
        user_email = st.session_state.get('user_email')

        # is_logged_in이 True이고, user_id와 user_email이 있으면 로그인된 것으로 판단
        if is_logged_in and user_id and user_email:
            print(f"🍪 로그인됨: user_id={user_id}, email={user_email}")
            return True
        else:
            print(f"🍪 로그인되지 않음")
            return False

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

    def validate_jira_jql(self, jql: str) -> Dict[str, Any]:
        """
        사용자가 입력한 JQL 쿼리를 검증

        Args:
            jql: 검증할 JQL 쿼리

        Returns:
            검증 결과 (성공 여부, 이슈 개수, 샘플 이슈 등)
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/validate-jql",
                json={"jql": jql},
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
            return {"success": False, "message": f"JQL 검증 실패: {str(e)}"}

    def save_jira_jql(self, jql: str) -> Dict[str, Any]:
        """
        JQL 쿼리를 저장 (신규 방식)

        Args:
            jql: 저장할 JQL 쿼리

        Returns:
            저장 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/jql",
                json={"jql": jql},
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
            return {"success": False, "message": f"JQL 저장 실패: {str(e)}"}

    def trigger_jira_sync(self, force_full_sync: bool = False) -> Dict[str, Any]:
        """
        수동으로 Jira 동기화 시작

        Args:
            force_full_sync: True이면 전체 재동기화

        Returns:
            트리거 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.post(
                f"{self.base_url}/jira/sync/trigger",
                json={"force_full_sync": force_full_sync},
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
            return {"success": False, "message": f"Jira 동기화 트리거 실패: {str(e)}"}

    def get_jira_sync_status(self) -> Dict[str, Any]:
        """
        Jira 동기화 상태 조회

        Returns:
            동기화 상태 정보
        """
        try:
            cookies = self._get_cookies()
            response = self.session.get(
                f"{self.base_url}/jira/sync/status",
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
            return {"success": False, "message": f"동기화 상태 조회 실패: {str(e)}"}

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

    # ============================================
    # 그룹 협업 API
    # ============================================

    def get_groups(self) -> Dict[str, Any]:
        """
        사용자의 그룹 목록 조회

        Returns:
            그룹 목록
        """
        try:
            cookies = self._get_cookies()
            response = self.session.get(
                f"{self.base_url}/api/v2/groups",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 목록 조회 실패: {str(e)}"}

    def create_group(self, name: str, description: str = None) -> Dict[str, Any]:
        """
        그룹 생성

        Args:
            name: 그룹 이름
            description: 그룹 설명 (선택)

        Returns:
            생성된 그룹 정보
        """
        try:
            cookies = self._get_cookies()
            data = {"name": name}
            if description:
                data["description"] = description

            response = self.session.post(
                f"{self.base_url}/api/v2/groups",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 생성 실패: {str(e)}"}

    def get_group_detail(self, group_id: int) -> Dict[str, Any]:
        """
        그룹 상세 정보 조회

        Args:
            group_id: 그룹 ID

        Returns:
            그룹 상세 정보 (멤버, 프롬프트 포함)
        """
        try:
            cookies = self._get_cookies()
            response = self.session.get(
                f"{self.base_url}/api/v2/groups/{group_id}",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 상세 조회 실패: {str(e)}"}

    def add_group_member(self, group_id: int, user_id: int, system: str = None) -> Dict[str, Any]:
        """
        그룹에 멤버 추가

        Args:
            group_id: 그룹 ID
            user_id: 추가할 사용자 ID
            system: 담당 시스템 (예: NCMS, EUXP)

        Returns:
            추가 결과
        """
        try:
            cookies = self._get_cookies()
            data = {"user_id": user_id}
            if system:
                data["system"] = system

            response = self.session.post(
                f"{self.base_url}/api/v2/groups/{group_id}/members",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"멤버 추가 실패: {str(e)}"}

    def remove_group_member(self, group_id: int, user_id: int) -> Dict[str, Any]:
        """
        그룹에서 멤버 제거

        Args:
            group_id: 그룹 ID
            user_id: 제거할 사용자 ID

        Returns:
            제거 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.delete(
                f"{self.base_url}/api/v2/groups/{group_id}/members/{user_id}",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"멤버 제거 실패: {str(e)}"}

    def update_group(self, group_id: int, name: str = None, description: str = None) -> Dict[str, Any]:
        """
        그룹 정보 수정

        Args:
            group_id: 그룹 ID
            name: 그룹 이름 (선택)
            description: 그룹 설명 (선택)

        Returns:
            수정 결과
        """
        try:
            cookies = self._get_cookies()
            data = {}
            if name:
                data["name"] = name
            if description is not None:
                data["description"] = description

            response = self.session.put(
                f"{self.base_url}/api/v2/groups/{group_id}",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 수정 실패: {str(e)}"}

    def delete_group(self, group_id: int) -> Dict[str, Any]:
        """
        그룹 삭제

        Args:
            group_id: 그룹 ID

        Returns:
            삭제 결과
        """
        try:
            cookies = self._get_cookies()
            response = self.session.delete(
                f"{self.base_url}/api/v2/groups/{group_id}",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 삭제 실패: {str(e)}"}

    def generate_group_report(self, group_id: int, title: str, prompt_ids: list,
                            include_toc: bool = True, save: bool = True) -> Dict[str, Any]:
        """
        그룹 보고서 생성

        Args:
            group_id: 그룹 ID
            title: 보고서 제목
            prompt_ids: 실행할 프롬프트 ID 목록
            include_toc: 목차 포함 여부
            save: 히스토리 저장 여부

        Returns:
            생성된 보고서
        """
        try:
            cookies = self._get_cookies()
            data = {
                "title": title,
                "prompt_ids": prompt_ids,
                "include_toc": include_toc,
                "save": save
            }

            response = self.session.post(
                f"{self.base_url}/api/v2/groups/{group_id}/reports/generate",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"그룹 보고서 생성 실패: {str(e)}"}

    # ==================== 카테고리 관리 API ====================

    def get_group_categories(self, group_id: int) -> Dict[str, Any]:
        """
        그룹 카테고리 목록 조회

        Args:
            group_id: 그룹 ID

        Returns:
            {"success": True/False, "categories": [...]}
        """
        try:
            cookies = self._get_cookies()
            response = self.session.get(
                f"{self.base_url}/api/v2/groups/{group_id}/categories",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"카테고리 조회 실패: {str(e)}"}

    def add_group_category(self, group_id: int, name: str, description: str = None, order_index: int = 999) -> Dict[str, Any]:
        """
        그룹 카테고리 추가 (owner만)

        Args:
            group_id: 그룹 ID
            name: 카테고리명
            description: 설명
            order_index: 순서

        Returns:
            {"success": True/False, "category": {...}}
        """
        try:
            cookies = self._get_cookies()
            data = {
                "name": name,
                "description": description,
                "order_index": order_index
            }

            response = self.session.post(
                f"{self.base_url}/api/v2/groups/{group_id}/categories",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"카테고리 추가 실패: {str(e)}"}

    def update_group_category(self, group_id: int, category_id: int, name: str = None, description: str = None) -> Dict[str, Any]:
        """
        그룹 카테고리 수정 (owner만)

        Args:
            group_id: 그룹 ID
            category_id: 카테고리 ID
            name: 새 카테고리명
            description: 새 설명

        Returns:
            {"success": True/False, "category": {...}}
        """
        try:
            cookies = self._get_cookies()
            data = {}
            if name:
                data["name"] = name
            if description is not None:
                data["description"] = description

            response = self.session.put(
                f"{self.base_url}/api/v2/groups/{group_id}/categories/{category_id}",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"카테고리 수정 실패: {str(e)}"}

    def delete_group_category(self, group_id: int, category_id: int) -> Dict[str, Any]:
        """
        그룹 카테고리 삭제 (owner만)

        Args:
            group_id: 그룹 ID
            category_id: 카테고리 ID

        Returns:
            {"success": True/False, "message": "..."}
        """
        try:
            cookies = self._get_cookies()
            response = self.session.delete(
                f"{self.base_url}/api/v2/groups/{group_id}/categories/{category_id}",
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"카테고리 삭제 실패: {str(e)}"}

    def reorder_group_categories(self, group_id: int, category_orders: list) -> Dict[str, Any]:
        """
        그룹 카테고리 순서 변경 (owner만)

        Args:
            group_id: 그룹 ID
            category_orders: [{"id": 1, "order_index": 0}, ...]

        Returns:
            {"success": True/False, "categories": [...]}
        """
        try:
            cookies = self._get_cookies()
            data = {"category_orders": category_orders}

            response = self.session.put(
                f"{self.base_url}/api/v2/groups/{group_id}/categories/reorder",
                json=data,
                cookies=cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_data = response.json()
                    return {"success": False, "message": error_data.get("detail", f"HTTP {response.status_code} 오류")}
                except json.JSONDecodeError:
                    return {"success": False, "message": f"HTTP {response.status_code} 오류"}

        except Exception as e:
            return {"success": False, "message": f"카테고리 순서 변경 실패: {str(e)}"}

# 전역 인스턴스
auth_client = AuthClient()
