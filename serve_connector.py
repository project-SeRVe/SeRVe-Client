import requests
import json
import base64
from security.crypto_manager import CryptoManager
from config import SERVER_URL, ROBOT_ID

class ServeConnector:
    def __init__(self):
        self.crypto = CryptoManager()
        self.session = requests.Session()
        self.aes_handle = None 

    def perform_handshake(self):
        """서버와 키 교환을 수행하고 AES 키를 획득합니다."""
        try:
            # 1. 내 키 생성
            my_key_pair = self.crypto.generate_client_key_pair()
            public_key_json = self.crypto.get_public_key_json(my_key_pair)

            # 2. 서버 요청
            resp = self.session.post(f"{SERVER_URL}/security/handshake", json={
                "publicKeyJson": public_key_json
            })
            
            if resp.status_code != 200:
                raise Exception(f"Handshake failed: {resp.text}")

            # 3. AES 키 복구
            encrypted_key = resp.json()['encryptedAesKey']
            self.aes_handle = self.crypto.unwrap_aes_key(encrypted_key, my_key_pair)
            return True, "보안 핸드셰이크 성공 (AES Key Secured)"
            
        except Exception as e:
            return False, f"핸드셰이크 오류: {str(e)}"

    def upload_secure_document(self, plaintext, repo_id=1):
        """데이터를 암호화하여 서버에 업로드합니다."""
        if not self.aes_handle:
            return None, "먼저 핸드셰이크를 수행해야 합니다."

        try:
            # 1. 암호화
            encrypted_content = self.crypto.encrypt_data(plaintext, self.aes_handle)
            
            # 2. 업로드
            payload = {
                "content": encrypted_content,
                "repositoryId": repo_id
            }
            resp = self.session.post(f"{SERVER_URL}/documents", json=payload)
            
            if resp.status_code != 200:
                return None, f"업로드 실패: {resp.text}"
            
            # ID 추출 (숫자만)
            doc_id = ''.join(filter(str.isdigit, resp.text))
            return doc_id, "업로드 성공"
            
        except Exception as e:
            return None, f"업로드 오류: {str(e)}"

    def get_secure_document(self, doc_id):
        """문서 ID로 암호문을 다운로드받아 복호화합니다."""
        if not self.aes_handle:
            return None, "먼저 핸드셰이크를 수행해야 합니다."

        try:
            # 1. 다운로드
            resp = self.session.get(f"{SERVER_URL}/documents/{doc_id}")
            if resp.status_code != 200:
                return None, f"다운로드 실패: {resp.text}"

            # 2. 복호화
            encrypted_content = resp.json()['content']
            decrypted_text = self.crypto.decrypt_data(encrypted_content, self.aes_handle)
            
            return decrypted_text, "복호화 성공"
        except Exception as e:
            return None, f"문서 처리 오류: {str(e)}"