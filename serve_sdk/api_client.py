"""
API Client - HTTP 통신 전담

순수 HTTP 요청/응답만 처리. 암호화 로직은 일절 모름.
Session에서 토큰을 받아와 인증 헤더에 사용.
"""

import json
import requests
from typing import Optional, Dict, Any, List, Tuple


class ApiClient:
    """
    서버와의 HTTP 통신을 담당하는 클라이언트

    책임:
    - REST API 호출
    - 인증 헤더 관리
    - 응답 파싱 및 에러 처리

    책임이 아닌 것:
    - 암호화/복호화 (CryptoUtils가 담당)
    - 상태 관리 (Session이 담당)
    - 비즈니스 로직 (ServeClient가 담당)
    """

    def __init__(self, server_url: str, team_service_url: Optional[str] = None, core_service_url: Optional[str] = None):
        """
        Args:
            server_url: Auth 서버 기본 URL (예: http://localhost:8080)
            team_service_url: Team 서버 URL (예: http://localhost:8082). 미지정 시 server_url 사용.
            core_service_url: Core 서버 URL (예: http://localhost:8083). 미지정 시 server_url 사용.
        """
        self.server_url = server_url.rstrip('/')
        self.team_service_url = (team_service_url or server_url).rstrip('/')
        self.core_service_url = (core_service_url or server_url).rstrip('/')
        self.session = requests.Session()

    def _get_headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        """인증 헤더 생성"""
        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _handle_response(self, response: requests.Response) -> Tuple[bool, Any]:
        """
        응답 처리 헬퍼

        Returns:
            (성공 여부, 데이터 또는 에러 메시지)
        """
        if response.status_code in [200, 201]:
            try:
                return True, response.json()
            except:
                # JSON 파싱 실패 시 텍스트 반환
                return True, response.text
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    # ==================== 인증 API ====================

    def signup(self, email: str, password: str, public_key: str,
               encrypted_private_key: str) -> Tuple[bool, str]:
        """
        회원가입

        Args:
            email: 사용자 이메일
            password: 비밀번호
            public_key: JSON 형식의 공개키
            encrypted_private_key: 비밀번호로 암호화된 개인키

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.server_url}/auth/signup",
                json={
                    "email": email,
                    "password": password,
                    "publicKey": public_key,
                    "encryptedPrivateKey": encrypted_private_key
                }
            )
            success, data = self._handle_response(resp)
            return success, "회원가입 성공" if success else data
        except Exception as e:
            return False, f"회원가입 오류: {str(e)}"

    def login(self, email: str, password: str) -> Tuple[bool, Optional[Dict]]:
        """
        로그인

        Returns:
            (성공 여부, 사용자 데이터 또는 에러 메시지)
            사용자 데이터: {accessToken, userId, email, encryptedPrivateKey}
        """
        try:
            resp = self.session.post(
                f"{self.server_url}/auth/login",
                json={"email": email, "password": password}
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"로그인 오류: {str(e)}"


    def withdraw(self, access_token: str) -> Tuple[bool, str]:
        """회원 탈퇴"""
        try:
            resp = self.session.delete(
                f"{self.server_url}/auth/me",
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "회원 탈퇴 성공" if success else "회원 탈퇴 실패"
        except Exception as e:
            return False, f"회원 탈퇴 오류: {str(e)}"

    # ==================== 사용자 정보 API ====================

    def get_user_public_key(self, email: str, access_token: str) -> Tuple[bool, Optional[str]]:
        """
        다른 사용자의 공개키 조회 (멤버 초대 시 사용)

        Args:
            email: 조회할 사용자 이메일
            access_token: 인증 토큰

        Returns:
            (성공 여부, JSON 형식의 공개키 또는 에러 메시지)
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/auth/public-key",
                params={"email": email},
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            if success and isinstance(data, dict):
                # dict를 JSON 문자열로 변환 (crypto_utils가 JSON 문자열을 기대함)
                return True, json.dumps(data)
            return success, data
        except Exception as e:
            return False, f"공개키 조회 오류: {str(e)}"

    # ==================== 저장소 API ====================

    def create_repository(self, name: str, description: str, owner_id: str,
                         encrypted_team_key: str, access_token: str) -> Tuple[bool, Any]:
        """
        저장소 생성

        Args:
            owner_id: 소유자 ID (UUID 문자열)
            encrypted_team_key: 내 공개키로 래핑된 팀 키
        """
        try:
            resp = self.session.post(
                f"{self.team_service_url}/api/repositories",
                json={
                    "name": name,
                    "description": description,
                    "ownerId": owner_id,
                    "encryptedTeamKey": encrypted_team_key
                },
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"저장소 생성 오류: {str(e)}"

    def get_my_repositories(self, user_id: str, access_token: str) -> Tuple[bool, Optional[List]]:
        """내 저장소 목록 조회"""
        try:
            resp = self.session.get(
                f"{self.team_service_url}/api/repositories",
                params={"userId": user_id},
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"저장소 목록 조회 오류: {str(e)}"

    def get_team_key(self, repo_id: str, user_id: str, access_token: str) -> Tuple[bool, Optional[str]]:
        """
        내가 가진 저장소의 암호화된 팀 키 조회

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            user_id: 사용자 ID (UUID 문자열)

        Returns:
            (성공 여부, Base64 암호화된 팀 키 또는 에러 메시지)
        """
        try:
            resp = self.session.get(
                f"{self.team_service_url}/api/repositories/{repo_id}/keys",
                params={"userId": user_id},
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"팀 키 조회 오류: {str(e)}"

    def delete_repository(self, repo_id: str, user_id: str, access_token: str) -> Tuple[bool, str]:
        """저장소 삭제"""
        try:
            resp = self.session.delete(
                f"{self.team_service_url}/api/repositories/{repo_id}",
                params={"userId": user_id},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "저장소 삭제 성공" if success else "저장소 삭제 실패"
        except Exception as e:
            return False, f"저장소 삭제 오류: {str(e)}"

    # ==================== 멤버 관리 API ====================

    def invite_member(self, repo_id: str, email: str, encrypted_team_key: str,
                     access_token: str) -> Tuple[bool, str]:
        """
        멤버 초대

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            encrypted_team_key: 초대할 사람의 공개키로 래핑된 팀 키
        """
        try:
            resp = self.session.post(
                f"{self.team_service_url}/api/teams/{repo_id}/members",
                json={
                    "email": email,
                    "encryptedTeamKey": encrypted_team_key
                },
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            if success:
                return True, "멤버 초대 성공"
            else:
                # 서버 에러 메시지 반환
                error_msg = data if isinstance(data, str) else str(data)
                return False, f"멤버 초대 실패: {error_msg}"
        except Exception as e:
            return False, f"멤버 초대 오류: {str(e)}"

    def get_members(self, repo_id: str, access_token: str) -> Tuple[bool, Optional[List]]:
        """멤버 목록 조회"""
        try:
            resp = self.session.get(
                f"{self.team_service_url}/api/teams/{repo_id}/members",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"멤버 목록 조회 오류: {str(e)}"

    def kick_member(self, repo_id: str, target_user_id: str, admin_id: str,
                   access_token: str) -> Tuple[bool, any]:
        """
        멤버 강퇴 (자동 키 로테이션 지원)

        Returns:
            (success, response_data)
            response_data 형식:
            {
                "success": true,
                "keyRotationRequired": true,
                "message": "...",
                "keyRotationReason": "...",
                "remainingMembers": [
                    {"userId": "...", "email": "...", "publicKey": "..."},
                    ...
                ]
            }
        """
        try:
            resp = self.session.delete(
                f"{self.team_service_url}/api/teams/{repo_id}/members/{target_user_id}",
                params={"adminId": admin_id},
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            return success, data  # 응답 데이터 그대로 반환
        except Exception as e:
            return False, f"멤버 강퇴 오류: {str(e)}"

    def update_member_role(self, repo_id: str, target_user_id: str, admin_id: str,
                          new_role: str, access_token: str) -> Tuple[bool, str]:
        """멤버 권한 변경"""
        try:
            resp = self.session.put(
                f"{self.team_service_url}/api/teams/{repo_id}/members/{target_user_id}",
                params={"adminId": admin_id},
                json={"role": new_role},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "권한 변경 성공" if success else "권한 변경 실패"
        except Exception as e:
            return False, f"권한 변경 오류: {str(e)}"

    def rotate_team_keys(self, repo_id: str, member_keys: list,
                        access_token: str) -> Tuple[bool, str]:
        """
        팀 키 로테이션 (일괄 업데이트)

        Args:
            repo_id: 팀 ID
            member_keys: [{"userId": "...", "encryptedTeamKey": "..."}, ...]
            access_token: JWT 토큰

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.team_service_url}/api/teams/{repo_id}/members/rotate-keys",
                json={"memberKeys": member_keys},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "키 로테이션 성공" if success else "키 로테이션 실패"
        except Exception as e:
            return False, f"키 로테이션 오류: {str(e)}"

    # ==================== Task API (SeRVe-Core) ====================

    def upload_task(self, team_id: str, file_name: str, file_type: str,
                   encrypted_blob: str, access_token: str) -> Tuple[bool, Any]:
        """
        암호화된 태스크 업로드

        Args:
            team_id: 팀 ID (UUID 문자열)
            file_name: 파일명
            file_type: 파일 타입
            encrypted_blob: 암호화된 내용 (Base64)
            access_token: 인증 토큰

        Returns:
            (성공 여부, 응답 데이터 또는 에러 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.core_service_url}/api/teams/{team_id}/tasks",
                f"{self.server_url}/api/teams/{team_id}/tasks",
                json={
                    "fileName": file_name,
                    "fileType": file_type,
                    "encryptedBlob": encrypted_blob
                },
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            return success, "태스크 업로드 성공" if success else data
        except Exception as e:
            return False, f"태스크 업로드 오류: {str(e)}"

    def get_tasks(self, team_id: str, access_token: str) -> Tuple[bool, Optional[List]]:
        """태스크 목록 조회"""
        try:
            resp = self.session.get(
                f"{self.core_service_url}/api/teams/{team_id}/tasks",
                f"{self.server_url}/api/teams/{team_id}/tasks",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"태스크 목록 조회 오류: {str(e)}"

    def download_task(self, task_id: int, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """태스크 데이터 다운로드"""
        try:
            resp = self.session.get(
                f"{self.core_service_url}/api/tasks/{task_id}/data",
                f"{self.server_url}/api/tasks/{task_id}/data",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"태스크 다운로드 오류: {str(e)}"

    def delete_task(self, team_id: str, task_id: str, access_token: str) -> Tuple[bool, str]:
        """태스크 삭제"""
        try:
            resp = self.session.delete(
                f"{self.core_service_url}/api/teams/{team_id}/tasks/{task_id}",
                f"{self.server_url}/api/teams/{team_id}/tasks/{task_id}",
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "태스크 삭제 성공" if success else "태스크 삭제 실패"
        except Exception as e:
            return False, f"태스크 삭제 오류: {str(e)}"

    # ==================== Demo API (SeRVe-Core) ====================

    def upload_demos(self, team_id: str, file_name: str, demos: List[Dict[str, Any]],
                    access_token: str) -> Tuple[bool, str]:
        """
        벡터 데모 배치 업로드

        Args:
            team_id: 팀 ID (UUID 문자열)
            file_name: 파일명 (시나리오 식별용)
            demos: 데모 목록 [{"demoIndex": int, "encryptedBlob": str (Base64)}, ...]
            access_token: 인증 토큰

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.core_service_url}/api/teams/{team_id}/demos",
                f"{self.server_url}/api/teams/{team_id}/demos",
                json={
                    "fileName": file_name,
                    "demos": demos
                },
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            return success, "데모 업로드 성공" if success else f"데모 업로드 실패: {data}"
        except Exception as e:
            return False, f"데모 업로드 오류: {str(e)}"

    def delete_demo(self, team_id: str, file_name: str, demo_index: int,
                   access_token: str) -> Tuple[bool, str]:
        """
        특정 데모 삭제

        Args:
            team_id: 팀 ID (UUID 문자열)
            file_name: 파일명
            demo_index: 데모 인덱스
            access_token: 인증 토큰

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.delete(
                f"{self.server_url}/api/teams/{team_id}/demos/{demo_index}",
                params={"fileName": file_name},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "데모 삭제 성공" if success else "데모 삭제 실패"
        except Exception as e:
            return False, f"데모 삭제 오류: {str(e)}"

    def sync_demos(self, team_id: str, last_version: int,
                  access_token: str) -> Tuple[bool, Optional[List[Dict]]]:
        """
        팀 데모 증분 동기화

        Args:
            team_id: 팀 ID (UUID 문자열)
            last_version: 마지막으로 알려진 버전 번호
            access_token: 인증 토큰

        Returns:
            (성공 여부, 변경된 데모 목록 또는 에러 메시지)
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/sync/demos",
                params={"teamId": team_id, "lastVersion": last_version},
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"데모 동기화 오류: {str(e)}"
