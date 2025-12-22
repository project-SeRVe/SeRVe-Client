"""
통합 시나리오 테스트

실제 사용 흐름을 시뮬레이션하여 전체 Zero-Trust 아키텍처 검증:
1. 회원가입 → 로그인
2. 저장소 생성 → 팀 키 관리
3. 문서 업로드 → 다운로드
4. 멤버 초대 → 키 공유

주의: 실제 서버 없이 로컬에서만 동작 (모의 테스트)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from serve_sdk.security.crypto_utils import CryptoUtils
from serve_sdk.security.key_manager import KeyManager
from serve_sdk.session import Session


class TestEndToEndFlow(unittest.TestCase):
    """End-to-End 시나리오 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.crypto = CryptoUtils()
        self.key_manager = KeyManager(self.crypto)

    def test_signup_and_login_flow(self):
        """회원가입 → 로그인 전체 플로우"""
        print("\n[테스트] 회원가입 → 로그인")

        # === 1. 회원가입 (클라이언트) ===
        email = "alice@example.com"
        password = "alice_password_123"

        signup_keys = self.key_manager.prepare_signup_keys(password)
        self.assertIn("publicKey", signup_keys, "공개키 누락")
        self.assertIn("encryptedPrivateKey", signup_keys, "암호화된 개인키 누락")

        print(f"✓ 회원가입 키 생성 완료")
        print(f"  - 공개키 길이: {len(signup_keys['publicKey'])}")
        print(f"  - 암호화된 개인키 길이: {len(signup_keys['encryptedPrivateKey'])}")

        # (서버에 전송했다고 가정 → 서버는 이 값들을 저장만 함)

        # === 2. 로그인 (클라이언트) ===
        # 서버에서 encryptedPrivateKey를 받아왔다고 가정
        encrypted_private_key = signup_keys["encryptedPrivateKey"]

        # 개인키 복구
        private_key, public_key = self.key_manager.recover_user_keys(encrypted_private_key, password)
        self.assertIsNotNone(private_key, "개인키 복구 실패")
        self.assertIsNotNone(public_key, "공개키 파생 실패")

        print(f"✓ 로그인 성공 (개인키 복구 완료)")

        # === 3. 키 무결성 검증 ===
        is_valid = self.key_manager.verify_key_integrity(private_key, public_key)
        self.assertTrue(is_valid, "키 쌍 무결성 검증 실패")
        print(f"✓ 키 쌍 무결성 검증 통과")

    def test_repository_creation_and_document_flow(self):
        """저장소 생성 → 문서 업로드/다운로드 플로우"""
        print("\n[테스트] 저장소 생성 → 문서 암복호화")

        # === 1. 사용자 키 생성 (로그인했다고 가정) ===
        password = "user123"
        signup_keys = self.key_manager.prepare_signup_keys(password)
        private_key, public_key = self.key_manager.recover_user_keys(
            signup_keys["encryptedPrivateKey"], password
        )

        # === 2. 저장소 생성 ===
        team_key, encrypted_team_key = self.key_manager.prepare_new_repository_key(public_key)
        self.assertIsNotNone(team_key, "팀 키 생성 실패")
        self.assertIsNotNone(encrypted_team_key, "팀 키 래핑 실패")

        print(f"✓ 저장소 생성 완료")
        print(f"  - 암호화된 팀 키 길이: {len(encrypted_team_key)}")

        # (서버에 저장소 정보와 encrypted_team_key 전송)

        # === 3. 문서 업로드 ===
        original_content = "이것은 기밀 문서입니다. Top Secret! 🔒"
        encrypted_content = self.key_manager.encrypt_document(original_content, team_key)
        self.assertNotEqual(original_content, encrypted_content, "암호화 실패 (평문과 동일)")

        print(f"✓ 문서 암호화 완료")
        print(f"  - 원본 길이: {len(original_content)}")
        print(f"  - 암호문 길이: {len(encrypted_content)}")

        # (서버에 encrypted_content 전송)

        # === 4. 프로그램 재시작 시뮬레이션 (팀 키 캐시 손실) ===
        # 서버에서 encrypted_team_key를 다시 받아와서 복구
        recovered_team_key = self.key_manager.recover_team_key(encrypted_team_key, private_key)

        # === 5. 문서 다운로드 및 복호화 ===
        decrypted_content = self.key_manager.decrypt_document(encrypted_content, recovered_team_key)
        self.assertEqual(original_content, decrypted_content, "복호화 결과가 원본과 다름")

        print(f"✓ 문서 복호화 성공")
        print(f"  - 복호화된 내용: {decrypted_content}")

    def test_member_invitation_flow(self):
        """멤버 초대 → 키 공유 플로우"""
        print("\n[테스트] 멤버 초대 → 키 공유")

        # === 1. Alice (소유자) 설정 ===
        alice_password = "alice123"
        alice_signup = self.key_manager.prepare_signup_keys(alice_password)
        alice_private, alice_public = self.key_manager.recover_user_keys(
            alice_signup["encryptedPrivateKey"], alice_password
        )

        # === 2. Alice가 저장소 생성 ===
        team_key, alice_encrypted_team_key = self.key_manager.prepare_new_repository_key(alice_public)

        print(f"✓ Alice가 저장소 생성")

        # === 3. Bob (초대받을 사람) 설정 ===
        bob_password = "bob456"
        bob_signup = self.key_manager.prepare_signup_keys(bob_password)
        bob_private, bob_public = self.key_manager.recover_user_keys(
            bob_signup["encryptedPrivateKey"], bob_password
        )

        # === 4. Alice가 Bob을 초대 (팀 키를 Bob의 공개키로 래핑) ===
        bob_public_json = bob_signup["publicKey"]
        bob_encrypted_team_key = self.key_manager.prepare_member_invitation_key(
            team_key, bob_public_json
        )

        print(f"✓ Alice가 Bob 초대 완료")
        print(f"  - Bob용 암호화된 팀 키 길이: {len(bob_encrypted_team_key)}")

        # (서버에 Bob의 멤버십과 bob_encrypted_team_key 저장)

        # === 5. Bob이 서버에서 자신의 팀 키 조회 및 복구 ===
        bob_team_key = self.key_manager.recover_team_key(bob_encrypted_team_key, bob_private)

        # === 6. Alice와 Bob이 같은 문서를 공유할 수 있는지 확인 ===
        shared_document = "Alice와 Bob의 공유 문서입니다."

        # Alice가 문서 암호화
        encrypted_by_alice = self.key_manager.encrypt_document(shared_document, team_key)

        # Bob이 복호화
        decrypted_by_bob = self.key_manager.decrypt_document(encrypted_by_alice, bob_team_key)

        self.assertEqual(shared_document, decrypted_by_bob, "Bob이 Alice의 문서를 복호화 실패")

        print(f"✓ 키 공유 검증 성공")
        print(f"  - Alice가 암호화한 문서를 Bob이 복호화: {decrypted_by_bob}")

    def test_multi_user_collaboration(self):
        """다중 사용자 협업 시나리오"""
        print("\n[테스트] 3명의 사용자가 하나의 저장소 공유")

        # === 1. 3명의 사용자 생성 ===
        users = {}
        for name in ["Alice", "Bob", "Charlie"]:
            password = f"{name.lower()}123"
            signup = self.key_manager.prepare_signup_keys(password)
            private_key, public_key = self.key_manager.recover_user_keys(
                signup["encryptedPrivateKey"], password
            )
            users[name] = {
                "password": password,
                "private_key": private_key,
                "public_key": public_key,
                "public_key_json": signup["publicKey"]
            }

        # === 2. Alice가 저장소 생성 ===
        alice = users["Alice"]
        team_key, alice_encrypted_team_key = self.key_manager.prepare_new_repository_key(
            alice["public_key"]
        )

        print(f"✓ Alice가 저장소 생성")

        # === 3. Alice가 Bob과 Charlie 초대 ===
        for name in ["Bob", "Charlie"]:
            user = users[name]
            encrypted_team_key = self.key_manager.prepare_member_invitation_key(
                team_key, user["public_key_json"]
            )
            # 각 사용자가 자신의 팀 키 복구
            user["team_key"] = self.key_manager.recover_team_key(
                encrypted_team_key, user["private_key"]
            )
            print(f"✓ {name} 초대 완료")

        # Alice도 자신의 팀 키 보유
        users["Alice"]["team_key"] = team_key

        # === 4. 순차적 문서 편집 시뮬레이션 ===
        documents = []

        # Alice가 문서 작성
        doc1 = "Alice: 프로젝트 시작!"
        encrypted1 = self.key_manager.encrypt_document(doc1, users["Alice"]["team_key"])
        documents.append(encrypted1)

        # Bob이 문서 읽고 추가 작성
        decrypted_by_bob = self.key_manager.decrypt_document(encrypted1, users["Bob"]["team_key"])
        self.assertEqual(doc1, decrypted_by_bob, "Bob이 Alice의 문서를 읽지 못함")
        doc2 = decrypted_by_bob + "\nBob: 좋은 아이디어네요!"
        encrypted2 = self.key_manager.encrypt_document(doc2, users["Bob"]["team_key"])
        documents.append(encrypted2)

        # Charlie가 문서 읽고 추가 작성
        decrypted_by_charlie = self.key_manager.decrypt_document(encrypted2, users["Charlie"]["team_key"])
        self.assertIn("Bob:", decrypted_by_charlie, "Charlie가 Bob의 문서를 읽지 못함")
        doc3 = decrypted_by_charlie + "\nCharlie: 저도 참여하겠습니다!"
        encrypted3 = self.key_manager.encrypt_document(doc3, users["Charlie"]["team_key"])
        documents.append(encrypted3)

        # Alice가 최종 문서 확인
        final_doc = self.key_manager.decrypt_document(encrypted3, users["Alice"]["team_key"])
        self.assertIn("Alice:", final_doc, "최종 문서에 Alice 내용 누락")
        self.assertIn("Bob:", final_doc, "최종 문서에 Bob 내용 누락")
        self.assertIn("Charlie:", final_doc, "최종 문서에 Charlie 내용 누락")

        print(f"✓ 협업 성공!")
        print(f"\n[최종 문서 내용]")
        print(final_doc)

    def test_session_management(self):
        """Session 객체를 사용한 상태 관리 테스트"""
        print("\n[테스트] Session 상태 관리")

        # === 1. Session 초기화 ===
        session = Session()
        self.assertFalse(session.is_authenticated(), "초기 상태는 미인증이어야 함")
        self.assertFalse(session.has_private_key(), "초기 상태는 키 없음이어야 함")

        # === 2. 로그인 시뮬레이션 ===
        password = "user123"
        signup = self.key_manager.prepare_signup_keys(password)
        private_key, public_key = self.key_manager.recover_user_keys(
            signup["encryptedPrivateKey"], password
        )

        session.set_user_credentials("fake_jwt_token", 1, "user@example.com")
        session.set_key_pair(private_key, public_key)

        self.assertTrue(session.is_authenticated(), "로그인 후 인증되어야 함")
        self.assertTrue(session.has_private_key(), "로그인 후 키가 있어야 함")

        print(f"✓ 로그인 상태 설정 완료")
        print(f"  - {session}")

        # === 3. 팀 키 캐싱 ===
        team_key, _ = self.key_manager.prepare_new_repository_key(public_key)
        session.cache_team_key(repo_id=1, aes_handle=team_key)

        cached_key = session.get_cached_team_key(1)
        self.assertIsNotNone(cached_key, "캐시된 팀 키 조회 실패")

        print(f"✓ 팀 키 캐싱 성공 (repo_id=1)")

        # === 4. 로그아웃 ===
        session.clear()
        self.assertFalse(session.is_authenticated(), "로그아웃 후 미인증이어야 함")
        self.assertIsNone(session.get_cached_team_key(1), "로그아웃 후 캐시 비워져야 함")

        print(f"✓ 로그아웃 완료 (모든 상태 초기화)")

    def test_password_validation(self):
        """비밀번호 강도 검증 테스트"""
        print("\n[테스트] 비밀번호 강도 검증")

        test_cases = [
            ("short", False, "너무 짧음"),
            ("onlyletters", False, "문자만"),
            ("12345678", False, "숫자만"),
            ("valid123", True, "유효함"),
            ("Strong@Pass1", True, "유효함"),
        ]

        for password, expected_valid, description in test_cases:
            is_valid, msg = self.key_manager.verify_password_strength(password)
            self.assertEqual(is_valid, expected_valid, f"'{password}' 검증 오류")
            print(f"  - '{password}': {msg}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
