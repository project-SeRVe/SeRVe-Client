"""
멤버 관련 기능 테스트
- 멤버 초대
- 멤버 목록 조회
- 멤버 강퇴
- 권한 변경
"""
import pytest
from serve_connector import ServeConnector


class TestMember:
    """멤버 관련 테스트"""

    @pytest.fixture
    def connector_with_repo(self):
        """로그인 및 저장소 생성된 커넥터"""
        connector = ServeConnector()
        import uuid
        test_email = f"member_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        connector.signup(
            test_email, "password123",
            f"pub_key_{test_email}",
            f"enc_priv_key_{test_email}"
        )
        connector.login(test_email, "password123")

        # 저장소 생성
        repo_id, _ = connector.create_repository(
            "Test Repo for Members",
            "Member testing",
            "team_key_members"
        )

        connector.test_repo_id = repo_id
        return connector

    def test_invite_member(self, connector_with_repo):
        """멤버 초대 테스트"""
        import uuid
        invite_email = f"invited_{uuid.uuid4()}@example.com"

        # 먼저 초대할 사용자를 회원가입시킴
        temp_connector = ServeConnector()
        temp_connector.signup(
            invite_email, "password123",
            f"pub_key_{invite_email}",
            f"enc_priv_key_{invite_email}"
        )

        # 멤버 초대
        success, msg = connector_with_repo.invite_member(
            connector_with_repo.test_repo_id,
            invite_email,
            "encrypted_team_key_for_" + invite_email
        )

        print(f"Invite member result: {success}, {msg}")

    def test_get_members(self, connector_with_repo):
        """멤버 목록 조회 테스트"""
        members, msg = connector_with_repo.get_members(
            connector_with_repo.test_repo_id
        )

        print(f"Get members result: {msg}")
        if members:
            print(f"Found {len(members)} members:")
            for member in members:
                print(f"  - {member['email']} ({member['role']})")

    def test_kick_member(self, connector_with_repo):
        """멤버 강퇴 테스트"""
        import uuid

        # 1. 멤버 초대
        invite_email = f"to_kick_{uuid.uuid4()}@example.com"
        temp_connector = ServeConnector()
        temp_connector.signup(
            invite_email, "password123",
            f"pub_key_{invite_email}",
            f"enc_priv_key_{invite_email}"
        )

        connector_with_repo.invite_member(
            connector_with_repo.test_repo_id,
            invite_email,
            "key_for_" + invite_email
        )

        # 2. 멤버 목록 조회하여 user_id 찾기
        members, _ = connector_with_repo.get_members(connector_with_repo.test_repo_id)

        if members:
            target_member = next((m for m in members if m['email'] == invite_email), None)

            if target_member:
                # 3. 멤버 강퇴
                success, msg = connector_with_repo.kick_member(
                    connector_with_repo.test_repo_id,
                    target_member['userId'],
                    connector_with_repo.user_id  # 자신의 ID를 admin ID로 사용
                )

                print(f"Kick member result: {success}, {msg}")

    def test_update_member_role(self, connector_with_repo):
        """멤버 권한 변경 테스트"""
        import uuid

        # 1. 멤버 초대
        invite_email = f"role_change_{uuid.uuid4()}@example.com"
        temp_connector = ServeConnector()
        temp_connector.signup(
            invite_email, "password123",
            f"pub_key_{invite_email}",
            f"enc_priv_key_{invite_email}"
        )

        connector_with_repo.invite_member(
            connector_with_repo.test_repo_id,
            invite_email,
            "key_for_" + invite_email
        )

        # 2. 멤버 목록 조회
        members, _ = connector_with_repo.get_members(connector_with_repo.test_repo_id)

        if members:
            target_member = next((m for m in members if m['email'] == invite_email), None)

            if target_member:
                # 3. 권한 변경 (MEMBER -> ADMIN)
                success, msg = connector_with_repo.update_member_role(
                    connector_with_repo.test_repo_id,
                    target_member['userId'],
                    connector_with_repo.user_id,  # 자신의 ID를 admin ID로 사용
                    "ADMIN"
                )

                print(f"Update member role result: {success}, {msg}")


if __name__ == "__main__":
    print("=== Member Tests ===\n")

    # Admin 커넥터
    admin = ServeConnector()
    admin_email = "admin_manual_test@example.com"

    print("1. Setting up admin (signup, login, create repo)...")
    try:
        admin.signup(admin_email, "password123", "pub_key_admin", "enc_priv_key_admin")
        admin.login(admin_email, "password123")
        repo_id, _ = admin.create_repository("Member Test Repo", "For testing members", "team_key")
        print(f"   Admin ready. Repo ID: {repo_id}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")
        repo_id = 1  # fallback

    # Member 커넥터
    member = ServeConnector()
    member_email = "member_manual_test@example.com"

    print("2. Creating member account...")
    try:
        member.signup(member_email, "password123", "pub_key_member", "enc_priv_key_member")
        print(f"   Member account created: {member_email}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Inviting member to repository...")
    try:
        success, msg = admin.invite_member(
            repo_id,
            member_email,
            "encrypted_team_key_for_member"
        )
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
