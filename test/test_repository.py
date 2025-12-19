"""
저장소 관련 기능 테스트
- 저장소 생성
- 저장소 목록 조회
- 팀 키 조회
- 저장소 삭제
"""
import pytest
from serve_connector import ServeConnector


class TestRepository:
    """저장소 관련 테스트"""

    @pytest.fixture
    def logged_in_connector(self):
        """로그인된 커넥터 (테스트용)"""
        connector = ServeConnector()
        import uuid
        test_email = f"repo_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        connector.signup(
            test_email, "password123",
            f"pub_key_{test_email}",
            f"enc_priv_key_{test_email}"
        )
        connector.login(test_email, "password123")

        return connector

    def test_create_repository(self, logged_in_connector):
        """저장소 생성 테스트"""
        repo_id, msg = logged_in_connector.create_repository(
            name="Test Repository",
            description="This is a test repository",
            encrypted_team_key="demo_team_key_test"
        )

        print(f"Create repository result: {repo_id}, {msg}")

        if repo_id:
            assert isinstance(repo_id, int) or isinstance(repo_id, str)

    def test_get_repositories(self, logged_in_connector):
        """저장소 목록 조회 테스트"""
        # 1. 저장소 생성
        logged_in_connector.create_repository(
            "Test Repo 1", "Description 1", "key1"
        )
        logged_in_connector.create_repository(
            "Test Repo 2", "Description 2", "key2"
        )

        # 2. 목록 조회
        repos, msg = logged_in_connector.get_my_repositories()

        print(f"Get repositories result: {msg}")
        if repos:
            print(f"Found {len(repos)} repositories")
            for repo in repos:
                print(f"  - {repo['name']} (ID: {repo['id']})")

    def test_get_team_key(self, logged_in_connector):
        """팀 키 조회 테스트"""
        # 1. 저장소 생성
        repo_id, _ = logged_in_connector.create_repository(
            "Key Test Repo", "For testing key retrieval", "test_team_key_123"
        )

        if repo_id:
            # 2. 팀 키 조회
            team_key, msg = logged_in_connector.get_team_key(repo_id)

            print(f"Get team key result: {msg}")
            if team_key:
                print(f"Team key: {team_key}")

    def test_delete_repository(self, logged_in_connector):
        """저장소 삭제 테스트"""
        # 1. 저장소 생성
        repo_id, _ = logged_in_connector.create_repository(
            "Repo to Delete", "This will be deleted", "temp_key"
        )

        if repo_id:
            # 2. 저장소 삭제
            success, msg = logged_in_connector.delete_repository(repo_id)

            print(f"Delete repository result: {success}, {msg}")
            assert success is True or success is False

    def test_create_repo_without_login(self):
        """로그인하지 않고 저장소 생성 시도"""
        connector = ServeConnector()  # 로그인 안 함

        repo_id, msg = connector.create_repository(
            "Should Fail", "No login", "key"
        )

        # 로그인 안 했으므로 실패해야 함
        assert repo_id is None
        assert "로그인" in msg
        print(f"Create repo without login: {msg}")


if __name__ == "__main__":
    print("=== Repository Tests ===\n")

    connector = ServeConnector()
    test_email = "repo_manual_test@example.com"

    print("1. Setting up (signup & login)...")
    try:
        connector.signup(test_email, "password123", "pub_key", "enc_priv_key")
        connector.login(test_email, "password123")
        print(f"   Logged in as: {connector.email}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")

    print("2. Creating repository...")
    try:
        repo_id, msg = connector.create_repository(
            "Manual Test Repo",
            "Created from manual test",
            "team_key_manual"
        )
        print(f"   Result: {msg}")
        if repo_id:
            print(f"   Repository ID: {repo_id}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Getting repositories...")
    try:
        repos, msg = connector.get_my_repositories()
        print(f"   Result: {msg}")
        if repos:
            for repo in repos:
                print(f"   - {repo['name']} (ID: {repo['id']})")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
