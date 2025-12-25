"""
Key Manager - 복합 키 관리 로직

CryptoUtils의 기본 프리미티브를 조합하여 고수준 키 관리 작업 수행:
- 회원가입 시 전체 키 생성 플로우
- 로그인 시 키 복구 플로우
- 팀 키 생성 및 배포
- 멤버 간 키 공유

이 클래스는 Session과 CryptoUtils를 연결하는 중간 레이어 역할
"""

from typing import Tuple, Dict, Any
from .crypto_utils import CryptoUtils


class KeyManager:
    """
    고수준 키 관리 작업 수행

    CryptoUtils는 "암호화 도구"
    KeyManager는 "암호화 레시피" (여러 도구를 조합한 워크플로우)
    """

    def __init__(self, crypto: CryptoUtils):
        """
        Args:
            crypto: CryptoUtils 인스턴스
        """
        self.crypto = crypto

    # ==================== 회원가입 플로우 ====================

    def prepare_signup_keys(self, password: str) -> Dict[str, str]:
        """
        회원가입을 위한 키 생성 및 암호화

        플로우:
        1. 새로운 키 쌍 생성
        2. 개인키를 비밀번호로 암호화
        3. 공개키 JSON 추출

        Args:
            password: 사용자 비밀번호

        Returns:
            {
                "publicKey": "공개키 JSON",
                "encryptedPrivateKey": "암호화된 개인키"
            }
        """
        # 1. 키 쌍 생성
        key_pair = self.crypto.generate_key_pair()

        # 2. 개인키를 비밀번호로 암호화
        encrypted_private_key = self.crypto.encrypt_private_key(key_pair, password)

        # 3. 공개키 추출
        public_key_json = self.crypto.get_public_key_json(key_pair)

        return {
            "publicKey": public_key_json,
            "encryptedPrivateKey": encrypted_private_key
        }

    # ==================== 로그인 플로우 ====================

    def recover_user_keys(self, encrypted_private_key: str, password: str) -> Tuple[Any, Any]:
        """
        로그인 시 암호화된 개인키 복구

        플로우:
        1. 암호화된 개인키를 비밀번호로 복호화
        2. 개인키에서 공개키 파생

        Args:
            encrypted_private_key: 서버에서 받은 암호화된 개인키
            password: 사용자 비밀번호

        Returns:
            (private_key_handle, public_key_handle)

        Raises:
            Exception: 비밀번호 오류 또는 데이터 손상
        """
        # 1. 개인키 복구
        private_key = self.crypto.recover_private_key(encrypted_private_key, password)

        # 2. 공개키 파생
        public_key = private_key.public_keyset_handle()

        return private_key, public_key

    # ==================== 저장소 생성 플로우 ====================

    def prepare_new_repository_key(self, owner_public_key_handle) -> Tuple[Any, str]:
        """
        새 저장소를 위한 팀 키 생성 및 래핑

        플로우:
        1. 새로운 AES 팀 키 생성
        2. 소유자의 공개키로 팀 키 래핑

        Args:
            owner_public_key_handle: 소유자의 공개키

        Returns:
            (원본 팀 키 핸들, 래핑된 팀 키 Base64)
        """
        # 1. 팀 키 생성
        team_key = self.crypto.generate_aes_key()

        # 2. 소유자의 공개키로 래핑
        encrypted_team_key = self.crypto.wrap_aes_key(team_key, owner_public_key_handle)

        return team_key, encrypted_team_key

    # ==================== 멤버 초대 플로우 ====================

    def prepare_member_invitation_key(self, team_key_handle, recipient_public_key_json: str) -> str:
        """
        멤버 초대를 위한 팀 키 래핑

        플로우:
        1. 수신자의 공개키 JSON 파싱
        2. 팀 키를 수신자의 공개키로 래핑

        Args:
            team_key_handle: 현재 저장소의 팀 키
            recipient_public_key_json: 초대할 사람의 공개키 JSON

        Returns:
            래핑된 팀 키 Base64
        """
        # 1. 공개키 JSON → KeysetHandle 변환
        recipient_public_key = self.crypto.parse_public_key_json(recipient_public_key_json)

        # 2. 팀 키 래핑
        encrypted_team_key = self.crypto.wrap_aes_key(team_key_handle, recipient_public_key)

        return encrypted_team_key

    # ==================== 팀 키 복구 플로우 ====================

    def recover_team_key(self, encrypted_team_key: str, private_key_handle) -> Any:
        """
        서버에서 받은 암호화된 팀 키를 복구

        플로우:
        1. 내 개인키로 팀 키 언래핑

        Args:
            encrypted_team_key: 서버에서 받은 래핑된 팀 키
            private_key_handle: 내 개인키

        Returns:
            복호화된 팀 키 핸들
        """
        return self.crypto.unwrap_aes_key(encrypted_team_key, private_key_handle)

    # ==================== 문서 암복호화 플로우 ====================

    def encrypt_document(self, plaintext: str, team_key_handle) -> str:
        """
        문서를 팀 키로 암호화

        Args:
            plaintext: 평문 내용
            team_key_handle: 팀 키

        Returns:
            Base64 암호문
        """
        return self.crypto.encrypt_data(plaintext, team_key_handle)

    def decrypt_document(self, ciphertext: str, team_key_handle) -> str:
        """
        암호화된 문서를 팀 키로 복호화

        Args:
            ciphertext: Base64 암호문
            team_key_handle: 팀 키

        Returns:
            평문 내용
        """
        return self.crypto.decrypt_data(ciphertext, team_key_handle)

    # ==================== 검증 유틸 ====================

    def verify_password_strength(self, password: str) -> Tuple[bool, str]:
        """
        비밀번호 강도 검증 (간단한 버전)

        프로덕션에서는 더 강력한 검증 필요:
        - 최소 길이
        - 대소문자, 숫자, 특수문자 조합
        - 일반적인 비밀번호 사전 체크

        Args:
            password: 검증할 비밀번호

        Returns:
            (유효 여부, 메시지)
        """
        if len(password) < 8:
            return False, "비밀번호는 최소 8자 이상이어야 합니다"

        if password.isalpha() or password.isdigit():
            return False, "비밀번호는 문자와 숫자를 조합해야 합니다"

        return True, "유효한 비밀번호입니다"

    def verify_key_integrity(self, private_key_handle, public_key_handle) -> bool:
        """
        개인키-공개키 쌍이 유효한지 검증

        테스트 방법:
        - 공개키로 더미 데이터를 래핑
        - 개인키로 언래핑
        - 성공하면 유효한 쌍

        Args:
            private_key_handle: 개인키
            public_key_handle: 공개키

        Returns:
            유효 여부
        """
        try:
            # 더미 팀 키 생성
            dummy_key = self.crypto.generate_aes_key()

            # 공개키로 래핑
            wrapped = self.crypto.wrap_aes_key(dummy_key, public_key_handle)

            # 개인키로 언래핑
            unwrapped = self.crypto.unwrap_aes_key(wrapped, private_key_handle)

            # 원본과 언래핑된 키로 같은 데이터 암호화 시 결과 동일해야 함
            test_data = "integrity check"
            encrypted1 = self.crypto.encrypt_data(test_data, dummy_key)
            decrypted = self.crypto.decrypt_data(encrypted1, unwrapped)

            return decrypted == test_data

        except Exception:
            return False
