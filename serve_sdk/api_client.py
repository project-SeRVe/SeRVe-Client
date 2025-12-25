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

    def __init__(self, server_url: str):
        """
        Args:
            server_url: 서버 기본 URL (예: http://localhost:8080)
        """
        self.server_url = server_url.rstrip('/')
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

    def reset_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        """비밀번호 재설정"""
        try:
            resp = self.session.post(
                f"{self.server_url}/auth/reset-password",
                json={"email": email, "newPassword": new_password}
            )
            success, _ = self._handle_response(resp)
            return success, "비밀번호 재설정 성공" if success else "비밀번호 재설정 실패"
        except Exception as e:
            return False, f"비밀번호 재설정 오류: {str(e)}"

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
                f"{self.server_url}/api/repositories",
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
                f"{self.server_url}/api/repositories",
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
                f"{self.server_url}/api/repositories/{repo_id}/keys",
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
                f"{self.server_url}/api/repositories/{repo_id}",
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
                f"{self.server_url}/api/teams/{repo_id}/members",
                json={
                    "email": email,
                    "encryptedTeamKey": encrypted_team_key
                },
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "멤버 초대 성공" if success else "멤버 초대 실패"
        except Exception as e:
            return False, f"멤버 초대 오류: {str(e)}"

    def get_members(self, repo_id: str, access_token: str) -> Tuple[bool, Optional[List]]:
        """멤버 목록 조회"""
        try:
            resp = self.session.get(
                f"{self.server_url}/api/teams/{repo_id}/members",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"멤버 목록 조회 오류: {str(e)}"

    def kick_member(self, repo_id: str, target_user_id: str, admin_id: str,
                   access_token: str) -> Tuple[bool, str]:
        """멤버 강퇴"""
        try:
            resp = self.session.delete(
                f"{self.server_url}/api/teams/{repo_id}/members/{target_user_id}",
                params={"adminId": admin_id},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "멤버 강퇴 성공" if success else "멤버 강퇴 실패"
        except Exception as e:
            return False, f"멤버 강퇴 오류: {str(e)}"

    def update_member_role(self, repo_id: str, target_user_id: str, admin_id: str,
                          new_role: str, access_token: str) -> Tuple[bool, str]:
        """멤버 권한 변경"""
        try:
            resp = self.session.put(
                f"{self.server_url}/api/teams/{repo_id}/members/{target_user_id}",
                params={"adminId": admin_id},
                json={"role": new_role},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "권한 변경 성공" if success else "권한 변경 실패"
        except Exception as e:
            return False, f"권한 변경 오류: {str(e)}"

    # ==================== 문서 API ====================

    def upload_document(self, encrypted_content: str, repo_id: str,
                       access_token: str, file_name: str = "document.txt",
                       file_type: str = "text/plain") -> Tuple[bool, Any]:
        """
        암호화된 문서 업로드

        Args:
            encrypted_content: 이미 팀 키로 암호화된 내용 (Base64)
            repo_id: 저장소 ID (UUID 문자열)
            file_name: 파일명 (기본값: document.txt)
            file_type: 파일 타입 (기본값: text/plain)

        Returns:
            (성공 여부, 문서 ID 또는 에러 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.server_url}/api/teams/{repo_id}/documents",
                json={
                    "fileName": file_name,
                    "fileType": file_type,
                    "encryptedBlob": encrypted_content
                },
                headers=self._get_headers(access_token)
            )
            success, data = self._handle_response(resp)
            if success:
                # 서버는 void를 반환하므로 데이터가 없거나 빈 응답일 수 있음
                # 성공 시 응답에서 doc_id를 추출할 수 없으므로 성공 메시지만 반환
                return True, "문서 업로드 성공"
            return False, data
        except Exception as e:
            return False, f"문서 업로드 오류: {str(e)}"

    def get_document(self, doc_id: str, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        문서 다운로드

        Args:
            doc_id: 문서 ID (UUID 문자열)

        Returns:
            (성공 여부, {content: 암호화된 내용, ...} 또는 에러 메시지)
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/documents/{doc_id}/data",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"문서 다운로드 오류: {str(e)}"

    def get_documents(self, repo_id: str, access_token: str) -> Tuple[bool, Optional[List]]:
        """
        문서 목록 조회

        Args:
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            (성공 여부, 문서 목록 또는 에러 메시지)
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/teams/{repo_id}/documents",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"문서 목록 조회 오류: {str(e)}"

    def delete_document(self, repo_id: str, doc_id: str, access_token: str) -> Tuple[bool, str]:
        """
        문서 삭제

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            doc_id: 문서 ID

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.delete(
                f"{self.server_url}/api/teams/{repo_id}/documents/{doc_id}",
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "문서 삭제 성공" if success else "문서 삭제 실패"
        except Exception as e:
            return False, f"문서 삭제 오류: {str(e)}"

    # ==================== 벡터 청크 API ====================

    def upload_chunks(self, doc_id: str, chunks: List[Dict[str, Any]],
                     access_token: str) -> Tuple[bool, str]:
        """
        벡터 청크 배치 업로드

        Args:
            doc_id: 문서 ID (UUID 문자열)
            chunks: 청크 목록 [{"chunkIndex": int, "encryptedBlob": str (Base64)}, ...]
            access_token: 인증 토큰

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.post(
                f"{self.server_url}/api/documents/{doc_id}/chunks",
                json={"chunks": chunks},
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "청크 업로드 성공" if success else "청크 업로드 실패"
        except Exception as e:
            return False, f"청크 업로드 오류: {str(e)}"

    def download_chunks(self, doc_id: str, access_token: str) -> Tuple[bool, Optional[List[Dict]]]:
        """
        문서의 모든 청크 다운로드

        Args:
            doc_id: 문서 ID (UUID 문자열)
            access_token: 인증 토큰

        Returns:
            (성공 여부, 청크 목록 또는 에러 메시지)
            청크 형식: [{"chunkId": str, "chunkIndex": int, "encryptedBlob": bytes, "version": int}, ...]
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/documents/{doc_id}/chunks",
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"청크 다운로드 오류: {str(e)}"

    def delete_chunk(self, doc_id: str, chunk_index: int, access_token: str) -> Tuple[bool, str]:
        """
        특정 청크 삭제 (논리적 삭제)

        Args:
            doc_id: 문서 ID (UUID 문자열)
            chunk_index: 청크 인덱스
            access_token: 인증 토큰

        Returns:
            (성공 여부, 메시지)
        """
        try:
            resp = self.session.delete(
                f"{self.server_url}/api/documents/{doc_id}/chunks/{chunk_index}",
                headers=self._get_headers(access_token)
            )
            success, _ = self._handle_response(resp)
            return success, "청크 삭제 성공" if success else "청크 삭제 실패"
        except Exception as e:
            return False, f"청크 삭제 오류: {str(e)}"

    def sync_document_chunks(self, doc_id: str, last_version: int,
                            access_token: str) -> Tuple[bool, Optional[List[Dict]]]:
        """
        문서별 증분 청크 동기화

        Args:
            doc_id: 문서 ID (UUID 문자열)
            last_version: 마지막으로 알려진 버전 번호
            access_token: 인증 토큰

        Returns:
            (성공 여부, 변경된 청크 목록 또는 에러 메시지)
            청크 형식: [{"documentId": str, "chunkId": str, "chunkIndex": int,
                        "encryptedBlob": bytes, "version": int, "isDeleted": bool}, ...]
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/documents/{doc_id}/chunks/sync",
                params={"lastVersion": last_version},
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"청크 동기화 오류: {str(e)}"

    def sync_team_chunks(self, team_id: str, last_version: int,
                        access_token: str) -> Tuple[bool, Optional[List[Dict]]]:
        """
        팀 전체 증분 청크 동기화

        Args:
            team_id: 팀/저장소 ID (UUID 문자열)
            last_version: 마지막으로 알려진 버전 번호
            access_token: 인증 토큰

        Returns:
            (성공 여부, 변경된 청크 목록 또는 에러 메시지)
            청크 형식: [{"documentId": str, "chunkId": str, "chunkIndex": int,
                        "encryptedBlob": bytes, "version": int, "isDeleted": bool}, ...]
        """
        try:
            resp = self.session.get(
                f"{self.server_url}/api/sync/chunks",
                params={"teamId": team_id, "lastVersion": last_version},
                headers=self._get_headers(access_token)
            )
            return self._handle_response(resp)
        except Exception as e:
            return False, f"팀 청크 동기화 오류: {str(e)}"

