"""
ServeClient - Zero-Trust SDK 메인 클래스

사용자가 직접 사용하는 고수준 API 제공.
내부적으로 Session, CryptoUtils, ApiClient를 조율하여
End-to-End 암호화를 구현.

핵심 기능:
1. Lazy Loading: 필요할 때만 서버에서 암호화된 키를 받아와 복호화
2. 자동 키 관리: 사용자는 암호화를 의식하지 않고 API만 호출
3. Zero-Trust: 서버는 평문 데이터나 원본 키를 절대 보지 못함
"""

from typing import Optional, Tuple, List, Dict, Any
from .session import Session
from .security.crypto_utils import CryptoUtils
from .api_client import ApiClient


class ServeClient:
    """
    Zero-Trust 문서 공유 플랫폼 클라이언트 SDK

    사용법:
        client = ServeClient(server_url="http://localhost:8080")
        client.login("user@example.com", "password")
        client.create_repository("MyRepo", "Description")
        client.upload_document("secret content", repo_id=1)
    """

    def __init__(self, server_url: str = "http://localhost:8080"):
        """
        Args:
            server_url: 서버 URL
        """
        self.api = ApiClient(server_url)
        self.crypto = CryptoUtils()
        self.session = Session()

    # ==================== 내부 헬퍼 메서드 ====================

    def _ensure_authenticated(self):
        """인증 상태 확인 (내부용)"""
        if not self.session.is_authenticated():
            raise RuntimeError("로그인이 필요합니다.")

    def _ensure_team_key(self, repo_id: str):
        """
        팀 키 Lazy Loading (핵심 로직!)

        Session에 팀 키가 없으면:
        1. 서버에서 암호화된 팀 키 조회
        2. 내 개인키로 복호화
        3. Session에 캐싱

        Args:
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            KeysetHandle: 복호화된 팀 키

        Raises:
            RuntimeError: 팀 키 조회/복호화 실패 시
        """
        # 1. 캐시 확인
        cached_key = self.session.get_cached_team_key(repo_id)
        if cached_key:
            return cached_key

        # 2. 서버에서 암호화된 팀 키 받아오기
        self._ensure_authenticated()
        success, encrypted_key = self.api.get_team_key(
            repo_id,
            self.session.user_id,
            self.session.access_token
        )

        if not success:
            raise RuntimeError(f"팀 키 조회 실패: {encrypted_key}")

        # 3. 내 개인키로 복호화
        try:
            private_key = self.session.get_private_key()
            team_key = self.crypto.unwrap_aes_key(encrypted_key, private_key)
        except Exception as e:
            raise RuntimeError(f"팀 키 복호화 실패: {e}")

        # 4. 캐시에 저장
        self.session.cache_team_key(repo_id, team_key)
        return team_key

    # ==================== 인증 API ====================

    def signup(self, email: str, password: str) -> Tuple[bool, str]:
        """
        회원가입

        내부 동작:
        1. 새로운 키 쌍 생성
        2. 개인키를 비밀번호로 암호화
        3. 공개키와 암호화된 개인키를 서버에 전송

        Args:
            email: 이메일
            password: 비밀번호

        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 키 쌍 생성
            key_pair = self.crypto.generate_key_pair()
            public_key_json = self.crypto.get_public_key_json(key_pair)

            # 2. 개인키를 비밀번호로 암호화
            encrypted_private_key = self.crypto.encrypt_private_key(key_pair, password)

            # 3. 서버에 전송
            return self.api.signup(email, password, public_key_json, encrypted_private_key)

        except Exception as e:
            return False, f"회원가입 처리 오류: {str(e)}"

    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """
        로그인

        내부 동작:
        1. 서버에 로그인 요청
        2. 받은 encryptedPrivateKey를 비밀번호로 복호화
        3. 개인키를 Session에 저장

        Args:
            email: 이메일
            password: 비밀번호

        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 서버 로그인
            success, data = self.api.login(email, password)
            if not success:
                return False, data

            # 2. 세션에 사용자 정보 저장
            self.session.set_user_credentials(
                data['accessToken'],
                data['userId'],
                data['email']
            )

            # 3. 암호화된 개인키 복구 (Zero-Trust 핵심!)
            try:
                encrypted_priv_key = data['encryptedPrivateKey']
                private_key = self.crypto.recover_private_key(encrypted_priv_key, password)
                public_key = private_key.public_keyset_handle()

                # 4. Session에 저장
                self.session.set_key_pair(private_key, public_key)

                return True, "로그인 성공"

            except Exception as e:
                # 개인키 복구 실패 (비밀번호 오류 가능성)
                self.session.clear()
                return False, f"개인키 복구 실패: {e}"

        except Exception as e:
            return False, f"로그인 오류: {str(e)}"

    def logout(self) -> Tuple[bool, str]:
        """로그아웃 (메모리 초기화)"""
        self.session.clear()
        return True, "로그아웃 성공"

    def reset_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        """비밀번호 재설정"""
        return self.api.reset_password(email, new_password)

    def withdraw(self) -> Tuple[bool, str]:
        """회원 탈퇴"""
        self._ensure_authenticated()
        success, msg = self.api.withdraw(self.session.access_token)
        if success:
            self.session.clear()
        return success, msg

    # ==================== 저장소 API ====================

    def create_repository(self, name: str, description: str = "") -> Tuple[Optional[str], str]:
        """
        저장소 생성

        내부 동작:
        1. 새로운 AES 팀 키 생성
        2. 내 공개키로 팀 키 래핑
        3. 서버에 전송
        4. 원본 팀 키를 Session에 캐싱

        Args:
            name: 저장소 이름
            description: 설명

        Returns:
            (저장소 ID (UUID 문자열), 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 새로운 팀 키 생성
            team_key = self.crypto.generate_aes_key()

            # 2. 내 공개키로 래핑
            my_public_key = self.session.get_public_key()
            encrypted_team_key = self.crypto.wrap_aes_key(team_key, my_public_key)

            # 3. 서버에 전송
            success, data = self.api.create_repository(
                name,
                description,
                self.session.user_id,
                encrypted_team_key,
                self.session.access_token
            )

            if not success:
                return None, data

            # 4. 응답에서 repo_id 추출 (UUID 문자열)
            repo_id = str(data) if isinstance(data, str) else data.get('id')

            # 5. 원본 팀 키를 Session에 캐싱
            self.session.cache_team_key(repo_id, team_key)

            return repo_id, f"저장소 생성 성공 (ID: {repo_id})"

        except Exception as e:
            return None, f"저장소 생성 오류: {str(e)}"

    def get_my_repositories(self) -> Tuple[Optional[List], str]:
        """내 저장소 목록 조회"""
        self._ensure_authenticated()
        success, data = self.api.get_my_repositories(
            self.session.user_id,
            self.session.access_token
        )
        return (data, "조회 성공") if success else (None, data)

    def delete_repository(self, repo_id: str) -> Tuple[bool, str]:
        """저장소 삭제"""
        self._ensure_authenticated()
        success, msg = self.api.delete_repository(
            repo_id,
            self.session.user_id,
            self.session.access_token
        )
        # 캐시에서도 제거
        if success and repo_id in self.session.team_keys:
            del self.session.team_keys[repo_id]
        return success, msg

    # ==================== 멤버 관리 API ====================

    def invite_member(self, repo_id: str, email: str) -> Tuple[bool, str]:
        """
        멤버 초대

        내부 동작:
        1. 초대할 사람의 공개키 조회
        2. 현재 저장소의 팀 키를 상대방 공개키로 래핑
        3. 서버에 전송

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            email: 초대할 사람의 이메일

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 상대방 공개키 조회
            success, public_key_json = self.api.get_user_public_key(
                email,
                self.session.access_token
            )

            if not success:
                return False, f"사용자 공개키 조회 실패: {public_key_json}"

            # 2. JSON → KeysetHandle 변환
            recipient_public_key = self.crypto.parse_public_key_json(public_key_json)

            # 3. 팀 키 가져오기 (lazy loading)
            team_key = self._ensure_team_key(repo_id)

            # 4. 상대방 공개키로 팀 키 래핑
            encrypted_team_key = self.crypto.wrap_aes_key(team_key, recipient_public_key)

            # 5. 서버에 전송
            return self.api.invite_member(
                repo_id,
                email,
                encrypted_team_key,
                self.session.access_token
            )

        except Exception as e:
            return False, f"멤버 초대 오류: {str(e)}"

    def get_members(self, repo_id: str) -> Tuple[Optional[List], str]:
        """멤버 목록 조회"""
        self._ensure_authenticated()
        success, data = self.api.get_members(repo_id, self.session.access_token)
        return (data, "조회 성공") if success else (None, data)

    def kick_member(self, repo_id: str, target_user_id: str) -> Tuple[bool, str]:
        """멤버 강퇴"""
        self._ensure_authenticated()
        return self.api.kick_member(
            repo_id,
            target_user_id,
            self.session.user_id,
            self.session.access_token
        )

    def update_member_role(self, repo_id: str, target_user_id: str, new_role: str) -> Tuple[bool, str]:
        """멤버 권한 변경"""
        self._ensure_authenticated()
        return self.api.update_member_role(
            repo_id,
            target_user_id,
            self.session.user_id,
            new_role,
            self.session.access_token
        )

    # ==================== 문서 API ====================

    def upload_document(self, plaintext: str, repo_id: str) -> Tuple[Optional[str], str]:
        """
        문서 업로드

        내부 동작:
        1. 팀 키 가져오기 (lazy loading)
        2. 평문을 팀 키로 암호화
        3. 암호문을 서버에 전송

        Args:
            plaintext: 평문 내용
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            (문서 ID, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 팀 키 가져오기 (lazy loading)
            team_key = self._ensure_team_key(repo_id)

            # 2. 암호화
            encrypted_content = self.crypto.encrypt_data(plaintext, team_key)

            # 3. 업로드
            success, data = self.api.upload_document(
                encrypted_content,
                repo_id,
                self.session.access_token
            )

            return (data, "업로드 성공") if success else (None, data)

        except Exception as e:
            return None, f"업로드 오류: {str(e)}"

    def download_document(self, doc_id: int, repo_id: str) -> Tuple[Optional[str], str]:
        """
        문서 다운로드

        내부 동작:
        1. 서버에서 암호문 다운로드
        2. 팀 키 가져오기 (lazy loading)
        3. 암호문을 팀 키로 복호화

        Args:
            doc_id: 문서 ID
            repo_id: 저장소 ID (UUID 문자열, 팀 키 조회용)

        Returns:
            (평문 내용, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 다운로드
            success, data = self.api.get_document(doc_id, self.session.access_token)

            if not success:
                return None, data

            # 2. 암호문 추출
            encrypted_content = data.get('content')
            if not encrypted_content:
                return None, "암호문이 없습니다"

            # 3. 팀 키 가져오기 (lazy loading)
            team_key = self._ensure_team_key(repo_id)

            # 4. 복호화
            plaintext = self.crypto.decrypt_data(encrypted_content, team_key)

            return plaintext, "복호화 성공"

        except Exception as e:
            return None, f"다운로드 오류: {str(e)}"

    def get_documents(self, repo_id: str) -> Tuple[Optional[List], str]:
        """
        문서 목록 조회

        Args:
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            (문서 목록, 메시지)
        """
        self._ensure_authenticated()
        success, data = self.api.get_documents(repo_id, self.session.access_token)
        return (data, "조회 성공") if success else (None, data)

    def delete_document(self, repo_id: str, doc_id: str) -> Tuple[bool, str]:
        """
        문서 삭제

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            doc_id: 문서 ID

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()
        return self.api.delete_document(repo_id, doc_id, self.session.access_token)

    # ==================== 레거시 호환 (선택적) ====================

    def perform_handshake(self) -> Tuple[bool, str]:
        """
        서버와 세션 키 교환 (레거시)

        주의: Zero-Trust 모드에서는 팀 키만 사용하므로 이 메서드는 사용하지 않음.
        기존 코드 호환성을 위해 유지.
        """
        try:
            # 임시 키 쌍 생성
            temp_key_pair = self.crypto.generate_key_pair()
            public_key_json = self.crypto.get_public_key_json(temp_key_pair)

            # 핸드셰이크
            success, encrypted_aes_key = self.api.handshake(public_key_json)

            if not success:
                return False, encrypted_aes_key

            # AES 키 복호화 (사용하지 않지만 검증용)
            _ = self.crypto.unwrap_aes_key(encrypted_aes_key, temp_key_pair)

            return True, "핸드셰이크 성공 (레거시)"

        except Exception as e:
            return False, f"핸드셰이크 오류: {str(e)}"

    # ==================== 디버그 유틸 ====================

    def get_session_info(self) -> Dict[str, Any]:
        """세션 정보 조회 (디버깅용)"""
        return {
            "authenticated": self.session.is_authenticated(),
            "user_id": self.session.user_id,
            "email": self.session.email,
            "has_private_key": self.session.has_private_key(),
            "cached_repositories": list(self.session.team_keys.keys())
        }
