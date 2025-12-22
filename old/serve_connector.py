import requests
import json
import base64
from security.crypto_manager import CryptoManager
import config

class ServeConnector:
    def __init__(self, server_url=None):
        self.crypto = CryptoManager()
        self.session = requests.Session()
        self.aes_handle = None
        self.access_token = None
        self.user_id = None
        self.email = None
        self.encrypted_private_key = None
        # 서버 URL을 동적으로 설정 가능하도록
        self.server_url = server_url if server_url else config.SERVER_URL

    def _get_server_url(self):
        """현재 서버 URL 반환 (config 모듈에서 최신 값 가져오기)"""
        return config.SERVER_URL if hasattr(config, 'SERVER_URL') else self.server_url

    def _get_auth_headers(self):
        """인증 헤더 반환"""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    # ==================== 인증 관련 API ====================

    def signup(self, email, password, public_key, encrypted_private_key):
        """회원가입"""
        try:
            server_url = self._get_server_url()
            resp = self.session.post(f"{server_url}/auth/signup", json={
                "email": email,
                "password": password,
                "publicKey": public_key,
                "encryptedPrivateKey": encrypted_private_key
            })

            if resp.status_code == 201:
                return True, "회원가입 성공"
            else:
                return False, f"회원가입 실패: {resp.text}"
        except Exception as e:
            return False, f"회원가입 오류: {str(e)}"

    def login(self, email, password):
        """로그인"""
        try:
            server_url = self._get_server_url()
            resp = self.session.post(f"{server_url}/auth/login", json={
                "email": email,
                "password": password
            })

            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data['accessToken']
                self.user_id = data['userId']
                self.email = data['email']
                self.encrypted_private_key = data['encryptedPrivateKey']
                return True, "로그인 성공"
            else:
                return False, f"로그인 실패: {resp.text}"
        except Exception as e:
            return False, f"로그인 오류: {str(e)}"

    def logout(self):
        """로그아웃 (클라이언트 측 토큰 제거)"""
        self.access_token = None
        self.user_id = None
        self.email = None
        self.encrypted_private_key = None
        return True, "로그아웃 성공"

    def reset_password(self, email, new_password):
        """비밀번호 재설정"""
        try:
            server_url = self._get_server_url()
            resp = self.session.post(f"{server_url}/auth/reset-password",
                                    json={"email": email, "newPassword": new_password})

            if resp.status_code == 200:
                return True, "비밀번호 재설정 성공"
            else:
                return False, f"비밀번호 재설정 실패: {resp.text}"
        except Exception as e:
            return False, f"비밀번호 재설정 오류: {str(e)}"

    def withdraw(self):
        """회원 탈퇴"""
        try:
            server_url = self._get_server_url()
            resp = self.session.delete(f"{server_url}/auth/me",
                                      headers=self._get_auth_headers())

            if resp.status_code == 200:
                self.logout()
                return True, "회원 탈퇴 성공"
            else:
                return False, f"회원 탈퇴 실패: {resp.text}"
        except Exception as e:
            return False, f"회원 탈퇴 오류: {str(e)}"

    # ==================== 보안 관련 API ====================

    def perform_handshake(self):
        """서버와 키 교환을 수행하고 AES 키를 획득합니다."""
        try:
            server_url = self._get_server_url()
            # 1. 내 키 생성
            my_key_pair = self.crypto.generate_client_key_pair()
            public_key_json = self.crypto.get_public_key_json(my_key_pair)

            # 2. 서버 요청 (경로 수정: /api/security/handshake)
            resp = self.session.post(f"{server_url}/api/security/handshake", json={
                "publicKeyJson": public_key_json
            })

            if resp.status_code != 200:
                raise Exception(f"Handshake failed: {resp.text}")

            # 3. AES 키 복구
            encrypted_key = resp.json()['encryptedAesKey']
            self.aes_handle = self.crypto.unwrap_aes_key(encrypted_key, my_key_pair)
            return True, "보안 핸드셰이크 성공 (AES Key Secured)"

        except Exception as e:
            return False, f"핸드셰이크 오류: {str(e)}"

    # ==================== 저장소 관련 API ====================

    def create_repository(self, name, description, encrypted_team_key):
        """저장소 생성 후 teamId를 반환"""
        if not self.user_id:
            return None, "먼저 로그인해주세요."

        try:
            server_url = self._get_server_url()
            resp = self.session.post(f"{server_url}/api/repositories",
                                    json={
                                        "name": name,
                                        "description": description,
                                        "ownerId": self.user_id,
                                        "encryptedTeamKey": encrypted_team_key
                                    },
                                    headers=self._get_auth_headers())

            if resp.status_code == 200:
                repo_long_id = resp.json()  # Long ID 받기

                # 생성된 저장소의 실제 teamId를 얻기 위해 목록 조회
                # 서버가 teamId를 생성하지 않으므로, Long ID를 String으로 사용
                # 참고: 서버 수정이 필요한 부분이지만, 일단 시도
                team_id = str(repo_long_id)

                return team_id, f"저장소 생성 성공 (ID: {repo_long_id})"
            else:
                return None, f"저장소 생성 실패: {resp.text}"
        except Exception as e:
            return None, f"저장소 생성 오류: {str(e)}"

    def get_my_repositories(self):
        """내 저장소 목록 조회"""
        if not self.user_id:
            return None, "먼저 로그인해주세요."

        try:
            server_url = self._get_server_url()
            resp = self.session.get(f"{server_url}/api/repositories",
                                   params={"userId": self.user_id},
                                   headers=self._get_auth_headers())

            if resp.status_code == 200:
                repos = resp.json()
                return repos, "저장소 목록 조회 성공"
            else:
                return None, f"저장소 목록 조회 실패: {resp.text}"
        except Exception as e:
            return None, f"저장소 목록 조회 오류: {str(e)}"

    def get_team_key(self, repo_id):
        """팀 키 조회"""
        if not self.user_id:
            return None, "먼저 로그인해주세요."

        try:
            server_url = self._get_server_url()
            resp = self.session.get(f"{server_url}/api/repositories/{repo_id}/keys",
                                   params={"userId": self.user_id},
                                   headers=self._get_auth_headers())

            if resp.status_code == 200:
                team_key = resp.text
                return team_key, "팀 키 조회 성공"
            else:
                return None, f"팀 키 조회 실패: {resp.text}"
        except Exception as e:
            return None, f"팀 키 조회 오류: {str(e)}"

    def delete_repository(self, repo_id):
        """저장소 삭제"""
        if not self.user_id:
            return False, "먼저 로그인해주세요."

        try:
            server_url = self._get_server_url()
            resp = self.session.delete(f"{server_url}/api/repositories/{repo_id}",
                                      params={"userId": self.user_id},
                                      headers=self._get_auth_headers())

            if resp.status_code == 200:
                return True, "저장소 삭제 성공"
            else:
                return False, f"저장소 삭제 실패: {resp.text}"
        except Exception as e:
            return False, f"저장소 삭제 오류: {str(e)}"

    # ==================== 멤버 관련 API ====================

    def invite_member(self, team_id, email, encrypted_team_key):
        """멤버 초대"""
        try:
            server_url = self._get_server_url()
            resp = self.session.post(f"{server_url}/api/teams/{team_id}/members",
                                    json={
                                        "email": email,
                                        "encryptedTeamKey": encrypted_team_key
                                    },
                                    headers=self._get_auth_headers())

            if resp.status_code == 200:
                return True, "멤버 초대 성공"
            else:
                return False, f"멤버 초대 실패: {resp.text}"
        except Exception as e:
            return False, f"멤버 초대 오류: {str(e)}"

    def get_members(self, team_id):
        """멤버 목록 조회"""
        try:
            server_url = self._get_server_url()
            resp = self.session.get(f"{server_url}/api/teams/{team_id}/members",
                                   headers=self._get_auth_headers())

            if resp.status_code == 200:
                members = resp.json()
                return members, "멤버 목록 조회 성공"
            else:
                return None, f"멤버 목록 조회 실패: {resp.text}"
        except Exception as e:
            return None, f"멤버 목록 조회 오류: {str(e)}"

    def kick_member(self, team_id, target_user_id, admin_id):
        """멤버 강퇴"""
        try:
            server_url = self._get_server_url()
            resp = self.session.delete(f"{server_url}/api/teams/{team_id}/members/{target_user_id}",
                                      params={"adminId": admin_id},
                                      headers=self._get_auth_headers())

            if resp.status_code == 200:
                return True, "멤버 강퇴 성공"
            else:
                return False, f"멤버 강퇴 실패: {resp.text}"
        except Exception as e:
            return False, f"멤버 강퇴 오류: {str(e)}"

    def update_member_role(self, team_id, target_user_id, admin_id, new_role):
        """멤버 권한 변경"""
        try:
            server_url = self._get_server_url()
            resp = self.session.put(f"{server_url}/api/teams/{team_id}/members/{target_user_id}",
                                   params={"adminId": admin_id},
                                   json={"role": new_role},
                                   headers=self._get_auth_headers())

            if resp.status_code == 200:
                return True, "권한 변경 성공"
            else:
                return False, f"권한 변경 실패: {resp.text}"
        except Exception as e:
            return False, f"권한 변경 오류: {str(e)}"

    # ==================== 문서 관련 API ====================

    def upload_secure_document(self, plaintext, repo_id=1, file_name="document.txt", file_type="text/plain"):
        """데이터를 암호화하여 서버에 업로드합니다."""
        if not self.aes_handle:
            return None, "먼저 핸드셰이크를 수행해야 합니다."

        try:
            server_url = self._get_server_url()
            # 1. 암호화
            encrypted_content = self.crypto.encrypt_data(plaintext, self.aes_handle)

            # 2. 업로드 (수정: /api/teams/{teamId}/documents)
            payload = {
                "fileName": file_name,
                "fileType": file_type,
                "encryptedBlob": encrypted_content
            }
            resp = self.session.post(f"{server_url}/api/teams/{repo_id}/documents",
                                    json=payload,
                                    headers=self._get_auth_headers())

            if resp.status_code != 200:
                error_detail = resp.text if resp.text else f"HTTP {resp.status_code}"
                return None, f"업로드 실패 (status={resp.status_code}): {error_detail}"

            return "success", "업로드 성공"

        except Exception as e:
            import traceback
            return None, f"업로드 오류: {str(e)}\n{traceback.format_exc()}"

    def get_documents(self, team_id):
        """팀의 문서 목록 조회"""
        try:
            server_url = self._get_server_url()
            resp = self.session.get(f"{server_url}/api/teams/{team_id}/documents",
                                   headers=self._get_auth_headers())

            if resp.status_code == 200:
                documents = resp.json()
                return documents, "문서 목록 조회 성공"
            else:
                error_detail = resp.text if resp.text else f"HTTP {resp.status_code}"
                return None, f"문서 목록 조회 실패 (status={resp.status_code}): {error_detail}"
        except Exception as e:
            import traceback
            return None, f"문서 목록 조회 오류: {str(e)}\n{traceback.format_exc()}"

    def get_secure_document(self, doc_id):
        """문서 ID로 암호문을 다운로드받아 복호화합니다."""
        if not self.aes_handle:
            return None, "먼저 핸드셰이크를 수행해야 합니다."

        try:
            server_url = self._get_server_url()
            # 1. 다운로드 (수정: /api/documents/{docId}/data)
            resp = self.session.get(f"{server_url}/api/documents/{doc_id}/data",
                                   headers=self._get_auth_headers())
            if resp.status_code != 200:
                return None, f"다운로드 실패: {resp.text}"

            # 2. 복호화
            encrypted_blob = resp.json()['encryptedBlob']
            decrypted_text = self.crypto.decrypt_data(encrypted_blob, self.aes_handle)

            return decrypted_text, "복호화 성공"
        except Exception as e:
            return None, f"문서 처리 오류: {str(e)}"

    def delete_document(self, team_id, doc_id):
        """문서 삭제"""
        try:
            server_url = self._get_server_url()
            resp = self.session.delete(f"{server_url}/api/teams/{team_id}/documents/{doc_id}",
                                      headers=self._get_auth_headers())

            if resp.status_code == 200:
                return True, "문서 삭제 성공"
            else:
                return False, f"문서 삭제 실패: {resp.text}"
        except Exception as e:
            return False, f"문서 삭제 오류: {str(e)}"