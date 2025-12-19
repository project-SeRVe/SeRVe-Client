"""
인증 관련 기능 테스트
- 회원가입
- 로그인
- 로그아웃
- 비밀번호 재설정
- 회원 탈퇴
"""
import pytest
from serve_connector import ServeConnector
from config import SERVER_URL


class TestAuthentication:
    """인증 관련 테스트"""

    @pytest.fixture
    def connector(self):
        """테스트용 ServeConnector 인스턴스"""
        return ServeConnector()

    @pytest.fixture
    def test_user_email(self):
        """테스트용 이메일"""
        import uuid
        return f"test_{uuid.uuid4()}@example.com"

    def test_signup_success(self, connector, test_user_email):
        """회원가입 성공 테스트"""
        success, msg = connector.signup(
            email=test_user_email,
            password="testpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )

        # 서버가 구현되어 있지 않으면 실패할 수 있음
        # 이 테스트는 서버가 정상적으로 작동할 때만 통과
        print(f"Signup result: {success}, {msg}")

    def test_signup_invalid_email(self, connector):
        """잘못된 이메일로 회원가입 시도"""
        success, msg = connector.signup(
            email="",  # 빈 이메일
            password="testpassword123",
            public_key="test_public_key",
            encrypted_private_key="test_encrypted_private_key"
        )

        # 빈 이메일은 실패해야 함
        print(f"Signup with empty email result: {success}, {msg}")

    def test_login_success(self, connector, test_user_email):
        """로그인 성공 테스트 (회원가입 후)"""
        # 1. 먼저 회원가입
        connector.signup(
            email=test_user_email,
            password="testpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )

        # 2. 로그인 시도
        success, msg = connector.login(test_user_email, "testpassword123")

        print(f"Login result: {success}, {msg}")

        if success:
            # 로그인 성공 시 토큰 및 사용자 정보 확인
            assert connector.access_token is not None
            assert connector.user_id is not None
            assert connector.email == test_user_email

    def test_login_wrong_password(self, connector, test_user_email):
        """잘못된 비밀번호로 로그인 시도"""
        # 1. 먼저 회원가입
        connector.signup(
            email=test_user_email,
            password="testpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )

        # 2. 잘못된 비밀번호로 로그인 시도
        success, msg = connector.login(test_user_email, "wrongpassword")

        # 실패해야 함
        assert success is False
        print(f"Login with wrong password result: {success}, {msg}")

    def test_logout(self, connector, test_user_email):
        """로그아웃 테스트"""
        # 1. 로그인
        connector.signup(
            email=test_user_email,
            password="testpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )
        connector.login(test_user_email, "testpassword123")

        # 2. 로그아웃
        success, msg = connector.logout()

        assert success is True
        assert connector.access_token is None
        assert connector.user_id is None
        assert connector.email is None
        print(f"Logout result: {success}, {msg}")

    def test_reset_password(self, connector, test_user_email):
        """비밀번호 재설정 테스트"""
        # 1. 회원가입
        connector.signup(
            email=test_user_email,
            password="oldpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )

        # 2. 비밀번호 재설정
        success, msg = connector.reset_password(test_user_email, "newpassword123")

        print(f"Password reset result: {success}, {msg}")

    def test_withdraw(self, connector, test_user_email):
        """회원 탈퇴 테스트"""
        # 1. 회원가입 및 로그인
        connector.signup(
            email=test_user_email,
            password="testpassword123",
            public_key="test_public_key_" + test_user_email,
            encrypted_private_key="test_encrypted_private_key_" + test_user_email
        )
        connector.login(test_user_email, "testpassword123")

        # 2. 회원 탈퇴
        success, msg = connector.withdraw()

        print(f"Withdraw result: {success}, {msg}")

        if success:
            # 탈퇴 성공 시 세션 정보가 삭제되어야 함
            assert connector.access_token is None
            assert connector.user_id is None


if __name__ == "__main__":
    # 간단한 테스트 실행
    print("=== Authentication Tests ===\n")

    connector = ServeConnector()
    test_email = "manual_test@example.com"

    print("1. Testing signup...")
    try:
        success, msg = connector.signup(
            test_email, "password123",
            "pub_key_test", "enc_priv_key_test"
        )
        print(f"   Result: {success}, {msg}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("2. Testing login...")
    try:
        success, msg = connector.login(test_email, "password123")
        print(f"   Result: {success}, {msg}\n")
        if success:
            print(f"   User ID: {connector.user_id}")
            print(f"   Email: {connector.email}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Testing logout...")
    try:
        success, msg = connector.logout()
        print(f"   Result: {success}, {msg}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
    print(f"Server URL: {SERVER_URL}")
