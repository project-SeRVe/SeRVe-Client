"""
통합 테스트
- 전체 워크플로우 테스트
- 실제 사용 시나리오 테스트
"""
import pytest
from serve_sdk import ServeClient
from config import SERVER_URL


class TestIntegration:
    """통합 테스트"""

    def test_full_workflow(self):
        """
        전체 워크플로우 테스트
        1. 회원가입
        2. 로그인
        3. 저장소 생성
        4. 문서 업로드
        5. 문서 다운로드 및 복호화
        6. 멤버 초대
        7. 멤버 목록 조회
        8. 로그아웃
        """
        import uuid

        # 사용자 1 (Admin)
        admin = ServeClient(SERVER_URL)
        admin_email = f"admin_{uuid.uuid4()}@example.com"

        print("=== Full Workflow Test ===\n")

        # 1. 회원가입
        print("1. Admin signup...")
        success, msg = admin.signup(admin_email, "admin_pass")
        print(f"   {msg}\n")

        # 2. 로그인
        print("2. Admin login...")
        success, msg = admin.login(admin_email, "admin_pass")
        print(f"   {msg}")
        if success:
            print(f"   User ID: {admin.session.user_id}\n")

        # 3. 저장소 생성
        print("3. Create repository...")
        repo_id, msg = admin.create_repository(
            "Integration Test Repo",
            "Full workflow test repository"
        )
        print(f"   {msg}")
        if repo_id:
            print(f"   Repo ID: {repo_id}\n")

        # 4. 문서 업로드
        print("4. Upload document...")
        test_content = "Integration test: Confidential data about hydraulic system. Max pressure: 600bar."
        doc_id, msg = admin.upload_document(test_content, repo_id)
        print(f"   {msg}")
        if doc_id:
            print(f"   Document ID: {doc_id}\n")

            # 5. 문서 다운로드
            print("5. Download document...")
            decrypted_content, msg = admin.download_document(int(doc_id), repo_id)
            print(f"   {msg}")
            if decrypted_content:
                print(f"   Content matches: {decrypted_content == test_content}\n")

        # 6. 멤버 초대
        print("6. Invite member...")
        member_email = f"member_{uuid.uuid4()}@example.com"

        # 멤버 계정 생성
        member = ServeClient(SERVER_URL)
        member.signup(member_email, "member_pass")

        success, msg = admin.invite_member(repo_id, member_email)
        print(f"   {msg}\n")

        # 7. 멤버 목록 조회
        print("7. Get member list...")
        members, msg = admin.get_members(repo_id)
        print(f"   {msg}")
        if members:
            for m in members:
                print(f"   - {m['email']} ({m['role']})")
            print()

        # 8. 로그아웃
        print("8. Admin logout...")
        success, msg = admin.logout()
        print(f"   {msg}")
        print(f"   Token cleared: {admin.session.access_token is None}\n")

        print("=== Workflow Complete ===")

    def test_multiple_repos_scenario(self):
        """
        다중 저장소 시나리오
        - 사용자가 여러 저장소를 만들고 각각에 다른 문서 업로드
        """
        import uuid

        user = ServeClient(SERVER_URL)
        user_email = f"multi_repo_{uuid.uuid4()}@example.com"

        print("=== Multiple Repositories Scenario ===\n")

        # Setup
        print("Setup: Signup & Login...")
        user.signup(user_email, "password")
        user.login(user_email, "password")
        print("   Ready\n")

        # 여러 저장소 생성
        repos = []
        for i in range(3):
            print(f"Creating repository {i+1}...")
            repo_id, msg = user.create_repository(
                f"Repo {i+1}",
                f"Test repository number {i+1}"
            )
            if repo_id:
                repos.append(repo_id)
                print(f"   Created: ID {repo_id}\n")

                # 각 저장소에 문서 업로드
                print(f"   Uploading document to Repo {i+1}...")
                doc_id, msg = user.upload_document(
                    f"Document for Repo {i+1}: Secret data {i+1}",
                    repo_id
                )
                print(f"   {msg}\n")

        # 저장소 목록 조회
        print("Getting all repositories...")
        repo_list, msg = user.get_my_repositories()
        if repo_list:
            print(f"   Found {len(repo_list)} repositories:")
            for repo in repo_list:
                print(f"   - {repo['name']} (ID: {repo['teamid']})")

        print("\n=== Scenario Complete ===")

    def test_team_collaboration_scenario(self):
        """
        팀 협업 시나리오
        - 관리자가 저장소 생성
        - 여러 멤버 초대
        - 각 멤버가 문서 업로드 (같은 저장소에)
        """
        import uuid

        print("=== Team Collaboration Scenario ===\n")

        # Admin
        admin = ServeClient(SERVER_URL)
        admin_email = f"team_admin_{uuid.uuid4()}@example.com"

        print("1. Admin setup...")
        admin.signup(admin_email, "admin_pass")
        admin.login(admin_email, "admin_pass")

        repo_id, _ = admin.create_repository(
            "Team Project",
            "Collaborative repository"
        )
        print(f"   Repository created: ID {repo_id}\n")

        # Members
        members = []
        for i in range(3):
            member = ServeClient(SERVER_URL)
            member_email = f"team_member_{i}_{uuid.uuid4()}@example.com"

            print(f"2.{i+1} Member {i+1} setup...")
            member.signup(member_email, "member_pass")

            # Admin이 멤버 초대
            success, msg = admin.invite_member(repo_id, member_email)
            print(f"   Invited: {member_email} - {msg}\n")

            members.append((member, member_email))

        # Admin이 멤버 목록 확인
        print("3. Checking member list...")
        member_list, msg = admin.get_members(repo_id)
        if member_list:
            print(f"   Total members: {len(member_list)}")
            for m in member_list:
                print(f"   - {m['email']} ({m['role']})")

        print("\n=== Collaboration Scenario Complete ===")


if __name__ == "__main__":
    print("Running integration tests...\n")

    test = TestIntegration()

    try:
        test.test_full_workflow()
    except Exception as e:
        print(f"Full workflow test error: {e}\n")

    print("\n" + "="*50 + "\n")

    try:
        test.test_multiple_repos_scenario()
    except Exception as e:
        print(f"Multiple repos test error: {e}\n")

    print("\n" + "="*50 + "\n")

    try:
        test.test_team_collaboration_scenario()
    except Exception as e:
        print(f"Team collaboration test error: {e}\n")

    print("\nNote: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
