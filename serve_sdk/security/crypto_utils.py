"""
CryptoUtils - Zero-Trust 암호화 유틸리티

Google Tink 라이브러리를 사용한 암호화/복호화 기본 기능 제공:
1. 키 쌍 생성 (ECIES - Elliptic Curve Integrated Encryption Scheme)
2. AES 키 생성 (AES-256-GCM)
3. 키 래핑/언래핑 (Hybrid Encryption)
4. 데이터 암복호화
5. 개인키 보호 (비밀번호 기반 암호화)
"""

import tink
from tink import aead
from tink import hybrid
from tink import cleartext_keyset_handle
from tink import JsonKeysetReader, JsonKeysetWriter
import base64
import io
import hashlib


class CryptoUtils:
    """
    Tink 라이브러리 래퍼 - Zero-Trust 암호화 프리미티브 제공
    """

    def __init__(self):
        """Tink 라이브러리 초기화"""
        try:
            aead.register()
            hybrid.register()
        except Exception as e:
            # 이미 등록된 경우 무시 (멀티 인스턴스 환경 대응)
            pass

    # ==================== 키 생성 ====================

    def generate_key_pair(self):
        """
        ECIES 키 쌍 생성 (타원곡선 암호화)

        Returns:
            KeysetHandle: 개인키 핸들 (public_keyset_handle()로 공개키 추출 가능)
        """
        template = hybrid.hybrid_key_templates.ECIES_P256_HKDF_HMAC_SHA256_AES128_GCM
        return tink.new_keyset_handle(template)

    def generate_aes_key(self):
        """
        새로운 AES-256-GCM 키 생성 (팀 키용)

        Returns:
            KeysetHandle: AES 키 핸들
        """
        template = aead.aead_key_templates.AES256_GCM
        return tink.new_keyset_handle(template)

    # ==================== 키 직렬화/역직렬화 ====================

    def get_public_key_json(self, private_handle) -> str:
        """
        개인키 핸들에서 공개키를 JSON 문자열로 추출

        Args:
            private_handle: 개인키 KeysetHandle

        Returns:
            str: JSON 형식의 공개키
        """
        public_handle = private_handle.public_keyset_handle()
        buffer = io.StringIO()
        cleartext_keyset_handle.write(JsonKeysetWriter(buffer), public_handle)
        return buffer.getvalue()

    def parse_public_key_json(self, json_str: str):
        """
        JSON 문자열을 공개키 KeysetHandle로 변환

        Args:
            json_str: JSON 형식의 공개키

        Returns:
            KeysetHandle: 공개키 핸들
        """
        reader = JsonKeysetReader(json_str)
        return cleartext_keyset_handle.read(reader)

    def serialize_aes_key(self, aes_handle) -> str:
        """
        AES 키를 JSON 문자열로 직렬화 (내부 사용)

        Args:
            aes_handle: AES KeysetHandle

        Returns:
            str: JSON 형식의 AES 키
        """
        buffer = io.StringIO()
        cleartext_keyset_handle.write(JsonKeysetWriter(buffer), aes_handle)
        return buffer.getvalue()

    def parse_aes_key_json(self, json_str: str):
        """
        JSON 문자열을 AES KeysetHandle로 변환

        Args:
            json_str: JSON 형식의 AES 키

        Returns:
            KeysetHandle: AES 키 핸들
        """
        reader = JsonKeysetReader(json_str)
        return cleartext_keyset_handle.read(reader)

    # ==================== 키 래핑/언래핑 ====================

    def wrap_aes_key(self, aes_handle, recipient_public_key_handle) -> str:
        """
        AES 키를 수신자의 공개키로 래핑 (암호화)

        Zero-Trust 핵심 로직:
        - 팀 키를 다른 사람의 공개키로 암호화하여 전달
        - 서버는 이 값을 해독할 수 없음 (수신자만 자신의 개인키로 복호화 가능)

        Args:
            aes_handle: 래핑할 AES 키
            recipient_public_key_handle: 수신자의 공개키

        Returns:
            str: Base64로 인코딩된 암호화된 AES 키
        """
        # 1. AES 키를 JSON으로 직렬화
        aes_json = self.serialize_aes_key(aes_handle)

        # 2. 수신자의 공개키로 암호화
        hybrid_encrypt = recipient_public_key_handle.primitive(hybrid.HybridEncrypt)
        encrypted_bytes = hybrid_encrypt.encrypt(aes_json.encode('utf-8'), b'')

        # 3. Base64 인코딩 (전송용)
        return base64.b64encode(encrypted_bytes).decode('utf-8')

    def unwrap_aes_key(self, encrypted_aes_key_b64: str, private_handle):
        """
        암호화된 AES 키를 내 개인키로 언래핑 (복호화)

        Args:
            encrypted_aes_key_b64: Base64로 인코딩된 암호화된 AES 키
            private_handle: 내 개인키

        Returns:
            KeysetHandle: 복호화된 AES 키 핸들
        """
        # 1. Base64 디코딩
        encrypted_bytes = base64.b64decode(encrypted_aes_key_b64)

        # 2. 내 개인키로 복호화
        hybrid_decrypt = private_handle.primitive(hybrid.HybridDecrypt)
        decrypted_json = hybrid_decrypt.decrypt(encrypted_bytes, b'')

        # 3. JSON을 AES 핸들로 변환
        return self.parse_aes_key_json(decrypted_json.decode('utf-8'))

    # ==================== 데이터 암복호화 ====================

    def encrypt_data(self, plaintext: str, aes_handle) -> str:
        """
        데이터를 AES-GCM으로 암호화

        Args:
            plaintext: 평문 문자열
            aes_handle: AES 키 핸들

        Returns:
            str: Base64로 인코딩된 암호문
        """
        env_aead = aes_handle.primitive(aead.Aead)
        ciphertext = env_aead.encrypt(plaintext.encode('utf-8'), b'')
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt_data(self, ciphertext_b64: str, aes_handle) -> str:
        """
        AES-GCM으로 암호화된 데이터를 복호화

        Args:
            ciphertext_b64: Base64로 인코딩된 암호문
            aes_handle: AES 키 핸들

        Returns:
            str: 복호화된 평문
        """
        env_aead = aes_handle.primitive(aead.Aead)
        ciphertext = base64.b64decode(ciphertext_b64)
        decrypted = env_aead.decrypt(ciphertext, b'')
        return decrypted.decode('utf-8')

    # ==================== 개인키 보호 (비밀번호 기반) ====================

    def _derive_key_from_password(self, password: str) -> bytes:
        """
        비밀번호에서 AES 키 유도 (PBKDF2 대신 간단한 해시 사용)

        실제 프로덕션에서는 PBKDF2, Argon2 등 사용 권장

        Args:
            password: 사용자 비밀번호

        Returns:
            bytes: 32바이트 키
        """
        # SHA-256으로 비밀번호 해싱 (32바이트)
        return hashlib.sha256(password.encode('utf-8')).digest()

    def encrypt_private_key(self, private_handle, password: str) -> str:
        """
        개인키를 비밀번호로 암호화 (회원가입 시 사용)

        Zero-Trust 핵심: 서버는 사용자의 개인키를 알아서는 안 됨
        - 클라이언트에서 비밀번호로 암호화한 후 서버에 저장
        - 서버는 암호화된 블랍만 보관 (복호화 불가능)

        Args:
            private_handle: 개인키 핸들
            password: 사용자 비밀번호

        Returns:
            str: Base64로 인코딩된 암호화된 개인키
        """
        # 1. 개인키를 JSON으로 직렬화
        buffer = io.StringIO()
        cleartext_keyset_handle.write(JsonKeysetWriter(buffer), private_handle)
        private_key_json = buffer.getvalue()

        # 2. 비밀번호에서 AES 키 유도
        password_key = self._derive_key_from_password(password)

        # 3. Tink AEAD로 암호화 (간단한 방법: XOR + HMAC 대신 AES-GCM 직접 사용)
        # 실제로는 Tink의 KMS 통합 사용 권장
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(password_key)
        nonce = b'0' * 12  # 실제로는 랜덤 생성 필요! (데모용 고정값)
        encrypted_bytes = aesgcm.encrypt(nonce, private_key_json.encode('utf-8'), None)

        # 4. Base64 인코딩
        return base64.b64encode(nonce + encrypted_bytes).decode('utf-8')

    def recover_private_key(self, encrypted_private_key_b64: str, password: str):
        """
        암호화된 개인키를 비밀번호로 복호화 (로그인 시 사용)

        Zero-Trust 핵심: 서버에서 받은 암호화된 개인키를 클라이언트에서만 복호화

        Args:
            encrypted_private_key_b64: Base64로 인코딩된 암호화된 개인키
            password: 사용자 비밀번호

        Returns:
            KeysetHandle: 복호화된 개인키 핸들

        Raises:
            Exception: 비밀번호가 틀렸거나 데이터가 손상된 경우
        """
        try:
            # 1. Base64 디코딩
            encrypted_data = base64.b64decode(encrypted_private_key_b64)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # 2. 비밀번호에서 AES 키 유도
            password_key = self._derive_key_from_password(password)

            # 3. 복호화
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(password_key)
            decrypted_json = aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')

            # 4. JSON을 KeysetHandle로 변환
            reader = JsonKeysetReader(decrypted_json)
            return cleartext_keyset_handle.read(reader)

        except Exception as e:
            raise Exception(f"개인키 복구 실패 (비밀번호 오류 또는 데이터 손상): {e}")
