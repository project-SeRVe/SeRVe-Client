"""
멤버 관련 기능 테스트
- 멤버 초대
- 멤버 목록 조회
- 멤버 강퇴
- 권한 변경
"""
import pytest
from serve_sdk import ServeClient
from config import SERVER_URL


class TestMember:
    """멤버 관련 테스트"""

    @pytest.fixture
    def client_with_repo(self):
        """로그인 및 저장소 생성된 클라이언트"""
        client = ServeClient(SERVER_URL)
        import uuid
        test_email = f"member_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        client.signup(test_email, "password123")
        client.login(test_email, "password123")

        # 저장소 생성
        repo_id, _ = client.create_repository(
            "Test Repo for Members",
            "Member testing"
        )

        client.test_repo_id = repo_id
        return client

    def test_invite_member(self, client_with_repo):
        """멤버 초대 테스트"""
        import uuid
        invite_email = f"invited_{uuid.uuid4()}@example.com"

        # 먼저 초대할 사용자를 회원가입시킴
        temp_client = ServeClient(SERVER_URL)
        temp_client.signup(invite_email, "password123")

        # 멤버 초대
        success, msg = client_with_repo.invite_member(
            client_with_repo.test_repo_id,
            invite_email
        )

        print(f"Invite member result: {success}, {msg}")

    def test_get_members(self, client_with_repo):
        """멤버 목록 조회 테스트"""
        members, msg = client_with_repo.get_members(
            client_with_repo.test_repo_id
        )

        print(f"Get members result: {msg}")
        if members:
            print(f"Found {len(members)} members:")
            for member in members:
                print(f"  - {member['email']} ({member['role']})")

    def test_kick_member(self, client_with_repo):
        """멤버 강퇴 테스트"""
        import uuid

        # 1. 멤버 초대
        invite_email = f"to_kick_{uuid.uuid4()}@example.com"
        temp_client = ServeClient(SERVER_URL)
        temp_client.signup(invite_email, "password123")

        client_with_repo.invite_member(
            client_with_repo.test_repo_id,
            invite_email
        )

        # 2. 멤버 목록 조회하여 user_id 찾기
        members, _ = client_with_repo.get_members(client_with_repo.test_repo_id)

        if members:
            target_member = next((m for m in members if m['email'] == invite_email), None)

            if target_member:
                # 3. 멤버 강퇴
                success, msg = client_with_repo.kick_member(
                    client_with_repo.test_repo_id,
                    target_member['userId']
                )

                print(f"Kick member result: {success}, {msg}")

    def test_update_member_role(self, client_with_repo):
        """멤버 권한 변경 테스트"""
        import uuid

        # 1. 멤버 초대
        invite_email = f"role_change_{uuid.uuid4()}@example.com"
        temp_client = ServeClient(SERVER_URL)
        temp_client.signup(invite_email, "password123")

        client_with_repo.invite_member(
            client_with_repo.test_repo_id,
            invite_email
        )

        # 2. 멤버 목록 조회
        members, _ = client_with_repo.get_members(client_with_repo.test_repo_id)

        if members:
            target_member = next((m for m in members if m['email'] == invite_email), None)

            if target_member:
                # 3. 권한 변경 (MEMBER -> ADMIN)
                success, msg = client_with_repo.update_member_role(
                    client_with_repo.test_repo_id,
                    target_member['userId'],
                    "ADMIN"
                )

                print(f"Update member role result: {success}, {msg}")


if __name__ == "__main__":
    print("=== Member Tests ===\n")

    # Admin 클라이언트
    admin = ServeClient(SERVER_URL)
    admin_email = "admin_manual_test@example.com"

    print("1. Setting up admin (signup, login, create repo)...")
    try:
        admin.signup(admin_email, "password123")
        admin.login(admin_email, "password123")
        repo_id, _ = admin.create_repository("Member Test Repo", "For testing members")
        print(f"   Admin ready. Repo ID: {repo_id}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")
        repo_id = 1  # fallback

    # Member 클라이언트
    member = ServeClient(SERVER_URL)
    member_email = "member_manual_test@example.com"

    print("2. Creating member account...")
    try:
        member.signup(member_email, "password123")
        print(f"   Member account created: {member_email}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Inviting member to repository...")
    try:
        success, msg = admin.invite_member(repo_id, member_email)
        print(f"   Result: {success}, {msg}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("4. Getting member list...")
    try:
        members, msg = admin.get_members(repo_id)
        print(f"   Result: {msg}")
        if members:
            for m in members:
                print(f"   - {m['email']} ({m['role']})")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
