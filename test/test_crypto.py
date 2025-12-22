"""
암호화 기본 기능 단위 테스트

CryptoUtils의 모든 메서드가 정상 동작하는지 검증
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from serve_sdk.security.crypto_utils import CryptoUtils


class TestCryptoUtils(unittest.TestCase):
    """CryptoUtils 단위 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.crypto = CryptoUtils()

    def test_key_pair_generation(self):
        """키 쌍 생성 테스트"""
        key_pair = self.crypto.generate_key_pair()
        self.assertIsNotNone(key_pair, "키 쌍 생성 실패")

        # 공개키 추출
        public_key_json = self.crypto.get_public_key_json(key_pair)
        self.assertIsNotNone(public_key_json, "공개키 추출 실패")
        self.assertIn("primaryKeyId", public_key_json, "공개키 JSON 형식 오류")

    def test_aes_key_generation(self):
        """AES 키 생성 테스트"""
        aes_key = self.crypto.generate_aes_key()
        self.assertIsNotNone(aes_key, "AES 키 생성 실패")

    def test_public_key_parsing(self):
        """공개키 JSON 파싱 테스트"""
        # 1. 키 쌍 생성
        key_pair = self.crypto.generate_key_pair()
        public_key_json = self.crypto.get_public_key_json(key_pair)

        # 2. JSON → KeysetHandle 변환
        parsed_key = self.crypto.parse_public_key_json(public_key_json)
        self.assertIsNotNone(parsed_key, "공개키 파싱 실패")

    def test_aes_key_wrapping_and_unwrapping(self):
        """AES 키 래핑/언래핑 테스트"""
        # 1. Alice 키 쌍 생성
        alice_key_pair = self.crypto.generate_key_pair()
        alice_public_key = alice_key_pair.public_keyset_handle()

        # 2. 팀 키 생성
        team_key = self.crypto.generate_aes_key()

        # 3. Alice 공개키로 팀 키 래핑
        wrapped_key = self.crypto.wrap_aes_key(team_key, alice_public_key)
        self.assertIsNotNone(wrapped_key, "키 래핑 실패")
        self.assertIsInstance(wrapped_key, str, "래핑된 키는 문자열이어야 함")

        # 4. Alice 개인키로 팀 키 언래핑
        unwrapped_key = self.crypto.unwrap_aes_key(wrapped_key, alice_key_pair)
        self.assertIsNotNone(unwrapped_key, "키 언래핑 실패")

        # 5. 원본 키와 언래핑된 키로 같은 데이터 암호화 시 복호화 가능한지 확인
        plaintext = "Test message"
        encrypted_with_original = self.crypto.encrypt_data(plaintext, team_key)
        decrypted_with_unwrapped = self.crypto.decrypt_data(encrypted_with_original, unwrapped_key)
        self.assertEqual(plaintext, decrypted_with_unwrapped, "언래핑된 키가 원본과 다름")

    def test_data_encryption_and_decryption(self):
        """데이터 암복호화 테스트"""
        # 1. AES 키 생성
        aes_key = self.crypto.generate_aes_key()

        # 2. 암호화
        plaintext = "This is a secret message! 한글도 되나요?"
        ciphertext = self.crypto.encrypt_data(plaintext, aes_key)
        self.assertIsNotNone(ciphertext, "암호화 실패")
        self.assertNotEqual(plaintext, ciphertext, "암호문이 평문과 같음")

        # 3. 복호화
        decrypted = self.crypto.decrypt_data(ciphertext, aes_key)
        self.assertEqual(plaintext, decrypted, "복호화 결과가 원본과 다름")

    def test_private_key_encryption_and_recovery(self):
        """개인키 암호화/복구 테스트 (회원가입/로그인)"""
        # 1. 키 쌍 생성
        original_key_pair = self.crypto.generate_key_pair()
        password = "user_password_123"

        # 2. 개인키를 비밀번호로 암호화 (회원가입)
        encrypted_private_key = self.crypto.encrypt_private_key(original_key_pair, password)
        self.assertIsNotNone(encrypted_private_key, "개인키 암호화 실패")

        # 3. 암호화된 개인키를 비밀번호로 복구 (로그인)
        recovered_key_pair = self.crypto.recover_private_key(encrypted_private_key, password)
        self.assertIsNotNone(recovered_key_pair, "개인키 복구 실패")

        # 4. 원본 키와 복구된 키가 동일한지 검증
        # (같은 팀 키를 둘 다로 암호화했을 때 서로 복호화 가능한지 확인)
        team_key = self.crypto.generate_aes_key()
        original_public = original_key_pair.public_keyset_handle()
        recovered_public = recovered_key_pair.public_keyset_handle()

        wrapped_with_original = self.crypto.wrap_aes_key(team_key, original_public)
        unwrapped_with_recovered = self.crypto.unwrap_aes_key(wrapped_with_original, recovered_key_pair)

        test_data = "Key recovery test"
        encrypted = self.crypto.encrypt_data(test_data, team_key)
        decrypted = self.crypto.decrypt_data(encrypted, unwrapped_with_recovered)
        self.assertEqual(test_data, decrypted, "복구된 키가 원본과 다름")

    def test_wrong_password_recovery_fails(self):
        """잘못된 비밀번호로 개인키 복구 시 실패하는지 테스트"""
        key_pair = self.crypto.generate_key_pair()
        correct_password = "correct123"
        wrong_password = "wrong456"

        encrypted_private_key = self.crypto.encrypt_private_key(key_pair, correct_password)

        # 잘못된 비밀번호로 복구 시도 → 예외 발생 기대
        with self.assertRaises(Exception):
            self.crypto.recover_private_key(encrypted_private_key, wrong_password)

    def test_cross_user_key_wrapping(self):
        """서로 다른 사용자 간 키 래핑 시나리오"""
        # 1. Alice와 Bob 키 쌍 생성
        alice_key_pair = self.crypto.generate_key_pair()
        bob_key_pair = self.crypto.generate_key_pair()

        # 2. Alice가 팀 키 생성
        team_key = self.crypto.generate_aes_key()

        # 3. Alice가 Bob의 공개키로 팀 키 래핑
        bob_public_key = bob_key_pair.public_keyset_handle()
        wrapped_for_bob = self.crypto.wrap_aes_key(team_key, bob_public_key)

        # 4. Bob이 자신의 개인키로 팀 키 언래핑
        bob_team_key = self.crypto.unwrap_aes_key(wrapped_for_bob, bob_key_pair)

        # 5. 둘 다 같은 문서를 암복호화할 수 있는지 확인
        secret = "Shared secret document"
        encrypted_by_alice = self.crypto.encrypt_data(secret, team_key)
        decrypted_by_bob = self.crypto.decrypt_data(encrypted_by_alice, bob_team_key)
        self.assertEqual(secret, decrypted_by_bob, "Bob이 Alice의 암호문을 복호화 실패")

    def test_multiple_wrappings_same_key(self):
        """같은 팀 키를 여러 사람에게 각각 래핑"""
        # 1. 팀원 3명의 키 쌍 생성
        users = {
            "alice": self.crypto.generate_key_pair(),
            "bob": self.crypto.generate_key_pair(),
            "charlie": self.crypto.generate_key_pair()
        }

        # 2. 하나의 팀 키 생성
        team_key = self.crypto.generate_aes_key()

        # 3. 각 사람의 공개키로 팀 키 래핑
        wrapped_keys = {}
        for name, key_pair in users.items():
            public_key = key_pair.public_keyset_handle()
            wrapped_keys[name] = self.crypto.wrap_aes_key(team_key, public_key)

        # 4. 각자가 자신의 래핑된 키를 언래핑할 수 있는지 확인
        secret = "Team document"
        encrypted = self.crypto.encrypt_data(secret, team_key)

        for name, key_pair in users.items():
            unwrapped = self.crypto.unwrap_aes_key(wrapped_keys[name], key_pair)
            decrypted = self.crypto.decrypt_data(encrypted, unwrapped)
            self.assertEqual(secret, decrypted, f"{name}이 문서 복호화 실패")


if __name__ == '__main__':
    unittest.main(verbosity=2)
