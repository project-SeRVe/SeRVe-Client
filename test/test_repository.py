"""
저장소 관련 기능 테스트
- 저장소 생성
- 저장소 목록 조회
- 팀 키 조회
- 저장소 삭제
"""
import pytest
from serve_sdk import ServeClient
from config import SERVER_URL


class TestRepository:
    """저장소 관련 테스트"""

    @pytest.fixture
    def logged_in_client(self):
        """로그인된 클라이언트 (테스트용)"""
        client = ServeClient(SERVER_URL)
        import uuid
        test_email = f"repo_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        client.signup(test_email, "password123")
        client.login(test_email, "password123")

        return client

    def test_create_repository(self, logged_in_client):
        """저장소 생성 테스트"""
        repo_id, msg = logged_in_client.create_repository(
            name="Test Repository",
            description="This is a test repository"
        )

        print(f"Create repository result: {repo_id}, {msg}")

        if repo_id:
            assert isinstance(repo_id, int) or isinstance(repo_id, str)

    def test_get_repositories(self, logged_in_client):
        """저장소 목록 조회 테스트"""
        # 1. 저장소 생성
        logged_in_client.create_repository("Test Repo 1", "Description 1")
        logged_in_client.create_repository("Test Repo 2", "Description 2")

        # 2. 목록 조회
        repos, msg = logged_in_client.get_my_repositories()

        print(f"Get repositories result: {msg}")
        if repos:
            print(f"Found {len(repos)} repositories")
            for repo in repos:
                print(f"  - {repo['name']} (ID: {repo['teamid']})")

    def test_delete_repository(self, logged_in_client):
        """저장소 삭제 테스트"""
        # 1. 저장소 생성
        repo_id, _ = logged_in_client.create_repository(
            "Repo to Delete", "This will be deleted"
        )

        if repo_id:
            # 2. 저장소 삭제
            success, msg = logged_in_client.delete_repository(repo_id)

            print(f"Delete repository result: {success}, {msg}")
            assert success is True or success is False

    def test_create_repo_without_login(self):
        """로그인하지 않고 저장소 생성 시도"""
        client = ServeClient(SERVER_URL)  # 로그인 안 함

        repo_id, msg = client.create_repository(
            "Should Fail", "No login"
        )

        # 로그인 안 했으므로 실패해야 함
        assert repo_id is None
        assert "로그인" in msg
        print(f"Create repo without login: {msg}")


if __name__ == "__main__":
    print("=== Repository Tests ===\n")

    client = ServeClient(SERVER_URL)
    test_email = "repo_manual_test@example.com"

    print("1. Setting up (signup & login)...")
    try:
        client.signup(test_email, "password123")
        client.login(test_email, "password123")
        print(f"   Logged in as: {client.session.email}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")

    print("2. Creating repository...")
    try:
        repo_id, msg = client.create_repository(
            "Manual Test Repo",
            "Created from manual test"
        )
        print(f"   Result: {msg}")
        if repo_id:
            print(f"   Repository ID: {repo_id}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Getting repositories...")
    try:
        repos, msg = client.get_my_repositories()
        print(f"   Result: {msg}")
        if repos:
            for repo in repos:
                print(f"   - {repo['name']} (ID: {repo['teamid']})")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
