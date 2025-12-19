"""
문서 관련 기능 테스트
- 핸드셰이크
- 문서 업로드 (암호화)
- 문서 다운로드 (복호화)
"""
import pytest
from serve_connector import ServeConnector


class TestDocument:
    """문서 관련 테스트"""

    @pytest.fixture
    def connector_with_repo(self):
        """로그인 및 저장소 생성된 커넥터"""
        connector = ServeConnector()
        import uuid
        test_email = f"doc_test_{uuid.uuid4()}@example.com"

        # 회원가입 및 로그인
        connector.signup(
            test_email, "password123",
            f"pub_key_{test_email}",
            f"enc_priv_key_{test_email}"
        )
        connector.login(test_email, "password123")

        # 저장소 생성
        repo_id, _ = connector.create_repository(
            "Test Repo for Documents",
            "Document testing",
            "team_key_docs"
        )

        connector.test_repo_id = repo_id
        return connector

    def test_handshake(self, connector_with_repo):
        """핸드셰이크 테스트"""
        success, msg = connector_with_repo.perform_handshake()

        print(f"Handshake result: {success}, {msg}")

        if success:
            assert connector_with_repo.aes_handle is not None

    def test_upload_document(self, connector_with_repo):
        """문서 업로드 테스트"""
        # 1. 핸드셰이크
        connector_with_repo.perform_handshake()

        # 2. 문서 업로드
        test_content = "This is a test document with sensitive information."

        doc_id, msg = connector_with_repo.upload_secure_document(
            test_content,
            connector_with_repo.test_repo_id
        )

        print(f"Upload document result: {msg}")
        if doc_id:
            print(f"Document ID: {doc_id}")
            connector_with_repo.test_doc_id = doc_id

    def test_download_document(self, connector_with_repo):
        """문서 다운로드 및 복호화 테스트"""
        # 1. 핸드셰이크 및 업로드
        connector_with_repo.perform_handshake()

        test_content = "Confidential: Pressure limit 500bar"
        doc_id, _ = connector_with_repo.upload_secure_document(
            test_content,
            connector_with_repo.test_repo_id
        )

        if doc_id:
            # 2. 다운로드 및 복호화
            decrypted_content, msg = connector_with_repo.get_secure_document(doc_id)

            print(f"Download document result: {msg}")
            if decrypted_content:
                print(f"Decrypted content: {decrypted_content}")
                assert decrypted_content == test_content

    def test_upload_without_handshake(self, connector_with_repo):
        """핸드셰이크 없이 문서 업로드 시도"""
        # 핸드셰이크 하지 않음

        doc_id, msg = connector_with_repo.upload_secure_document(
            "This should fail",
            connector_with_repo.test_repo_id
        )

        # 실패해야 함
        assert doc_id is None
        assert "핸드셰이크" in msg
        print(f"Upload without handshake: {msg}")

    def test_download_without_handshake(self, connector_with_repo):
        """핸드셰이크 없이 문서 다운로드 시도"""
        content, msg = connector_with_repo.get_secure_document(1)

        # 실패해야 함
        assert content is None
        assert "핸드셰이크" in msg
        print(f"Download without handshake: {msg}")

    def test_encrypt_decrypt_roundtrip(self, connector_with_repo):
        """암호화-복호화 왕복 테스트"""
        # 1. 핸드셰이크
        connector_with_repo.perform_handshake()

        # 2. 여러 문서 업로드 및 다운로드
        test_documents = [
            "Document 1: Sensitive data A",
            "Document 2: Confidential information B",
            "Document 3: Secret details C"
        ]

        for i, content in enumerate(test_documents):
            # 업로드
            doc_id, upload_msg = connector_with_repo.upload_secure_document(
                content,
                connector_with_repo.test_repo_id
            )

            print(f"Test {i+1}: {upload_msg}")

            if doc_id:
                # 다운로드
                decrypted, download_msg = connector_with_repo.get_secure_document(doc_id)

                if decrypted:
                    assert decrypted == content
                    print(f"  ✓ Roundtrip successful: {content[:30]}...")


if __name__ == "__main__":
    print("=== Document Tests ===\n")

    connector = ServeConnector()
    test_email = "doc_manual_test@example.com"

    print("1. Setting up (signup, login, create repo)...")
    try:
        connector.signup(test_email, "password123", "pub_key", "enc_priv_key")
        connector.login(test_email, "password123")
        repo_id, _ = connector.create_repository("Test Repo", "For docs", "key")
        print(f"   Ready. Repo ID: {repo_id}\n")
    except Exception as e:
        print(f"   Setup error: {e}\n")
        repo_id = 1  # fallback

    print("2. Performing handshake...")
    try:
        success, msg = connector.perform_handshake()
        print(f"   Result: {success}, {msg}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("3. Uploading document...")
    try:
        doc_id, msg = connector.upload_secure_document(
            "This is a test document with secret data.",
            repo_id
        )
        print(f"   Result: {msg}")
        if doc_id:
            print(f"   Document ID: {doc_id}\n")

            print("4. Downloading document...")
            content, msg2 = connector.get_secure_document(doc_id)
            print(f"   Result: {msg2}")
            if content:
                print(f"   Content: {content}\n")
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Note: 서버가 실행 중이 아니면 연결 오류가 발생합니다.")
