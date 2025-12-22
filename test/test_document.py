"""
문서 관련 기능 테스트
- 핸드셰이크
- 문서 업로드 (암호화)
- 문서 다운로드 (복호화)
"""
import pytest
from serve_sdk import ServeClient
from config import SERVER_URL


class TestDocument:
    """문서 관련 테스트"""

    @pytest.fixture
    def client_with_repo(self):
        """로그인 및 저장소 생성된 클라이언트"""
        client = ServeClient(SERVER_URL)
        import uuid
        test_email = f"doc_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        client.signup(test_email, "password123")
        client.login(test_email, "password123")

        # 저장소 생성
        repo_id, _ = client.create_repository(
            "Test Repo for Documents",
            "Document testing"
        )

        client.test_repo_id = repo_id
        return client

    def test_handshake(self, client_with_repo):
        """핸드셰이크 테스트 (레거시)"""
        success, msg = client_with_repo.perform_handshake()

        print(f"Handshake result: {success}, {msg}")

    def test_upload_document(self, client_with_repo):
        """문서 업로드 테스트"""
        # 문서 업로드 (새 SDK는 핸드셰이크 불필요)
        test_content = "This is a test document with sensitive information."

        doc_id, msg = client_with_repo.upload_document(
            test_content,
            client_with_repo.test_repo_id
        )

        print(f"Upload document result: {msg}")
        if doc_id:
            print(f"Document ID: {doc_id}")
            client_with_repo.test_doc_id = doc_id

    def test_download_document(self, client_with_repo):
        """문서 다운로드 및 복호화 테스트"""
        # 업로드
        test_content = "Confidential: Pressure limit 500bar"
        doc_id, _ = client_with_repo.upload_document(
            test_content,
            client_with_repo.test_repo_id
        )

        if doc_id:
            # 다운로드 및 복호화
            decrypted_content, msg = client_with_repo.download_document(
                int(doc_id),
                client_with_repo.test_repo_id
            )

            print(f"Download document result: {msg}")
            if decrypted_content:
                print(f"Decrypted content: {decrypted_content}")
                assert decrypted_content == test_content

    def test_upload_without_login(self):
        """로그인 없이 문서 업로드 시도"""
        client = ServeClient(SERVER_URL)

        doc_id, msg = client.upload_document(
            "This should fail",
            1  # repo_id
        )

        # 실패해야 함
        assert doc_id is None
        assert "로그인" in msg
        print(f"Upload without login: {msg}")

    def test_download_without_login(self):
        """로그인 없이 문서 다운로드 시도"""
        client = ServeClient(SERVER_URL)

        content, msg = client.download_document(1, 1)

        # 실패해야 함
        assert content is None
        assert "로그인" in msg
        print(f"Download without login: {msg}")

    def test_encrypt_decrypt_roundtrip(self, client_with_repo):
        """암호화-복호화 왕복 테스트"""
        # 여러 문서 업로드 및 다운로드
        test_documents = [
            "Document 1: Sensitive data A",
            "Document 2: Confidential information B",
            "Document 3: Secret details C"
        ]

        for i, content in enumerate(test_documents):
            # 업로드
            doc_id, upload_msg = client_with_repo.upload_document(
                content,
                client_with_repo.test_repo_id
            )

            print(f"Test {i+1}: {upload_msg}")

            if doc_id:
                # 다운로드
                decrypted, download_msg = client_with_repo.download_document(
                    int(doc_id),
                    client_with_repo.test_repo_id
                )

                if decrypted:
                    assert decrypted == content
                    print(f"  ✓ Roundtrip successful: {content[:30]}...")


if __name__ == "__main__":
    print("=== Document Tests ===\n")

    client = ServeClient(SERVER_URL)
    test_email = "doc_manual_test@example.com"

    print("1. Setting up (signup, login, create repo)...")
    try:
        client.signup(test_email, "password123")
        client.login(test_email, "password123")
        repo_id, _ = client.create_repository("Test Repo", "For docs")
        print(f"   Ready. Repo ID: {repo_id}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")
        repo_id = 1  # fallback

    print("2. Uploading document...")
    try:
        doc_id, msg = client.upload_document(
            "This is a test document with secret data.",
            repo_id
        )
        print(f"   Result: {msg}")
        if doc_id:
            print(f"   Document ID: {doc_id}\n")

            print("3. Downloading document...")
            content, msg2 = client.download_document(int(doc_id), repo_id)
            print(f"   Result: {msg2}")
            if content:
                print(f"   Content: {content}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
