import tink
from tink import aead
from tink import hybrid
from tink import cleartext_keyset_handle
from tink import JsonKeysetReader, JsonKeysetWriter
import base64
import io

class CryptoManager:
    def __init__(self):
        try:
            aead.register()
            hybrid.register()
        except Exception as e:
            print(f"Tink 초기화 중 오류: {e}")

    # [키 교환] 클라이언트용 RSA(ECIES) 키 쌍 생성
    def generate_client_key_pair(self):
        template = hybrid.hybrid_key_templates.ECIES_P256_HKDF_HMAC_SHA256_AES128_GCM
        return tink.new_keyset_handle(template)

    # [키 교환] 공개키 추출 (JSON String)
    def get_public_key_json(self, private_handle):
        public_handle = private_handle.public_keyset_handle()
        buffer = io.StringIO()
        cleartext_keyset_handle.write(JsonKeysetWriter(buffer), public_handle)
        return buffer.getvalue()

    # [키 교환] 서버가 준 암호화된 AES 키 복구 (Unwrap)
    def unwrap_aes_key(self, encrypted_aes_key_b64, private_handle):
        # 1. Base64 디코딩
        encrypted_bytes = base64.b64decode(encrypted_aes_key_b64)
        
        # 2. 복호화
        hybrid_decrypt = private_handle.primitive(hybrid.HybridDecrypt)
        decrypted_keyset_bytes = hybrid_decrypt.decrypt(encrypted_bytes, b'')
        
        # 3. AES 핸들로 변환
        reader = JsonKeysetReader(decrypted_keyset_bytes.decode('utf-8'))
        return cleartext_keyset_handle.read(reader)

    # [데이터] 암호화 (AES-GCM) -> Base64 String 반환
    def encrypt_data(self, plaintext, aes_handle):
        env_aead = aes_handle.primitive(aead.Aead)
        ciphertext = env_aead.encrypt(plaintext.encode('utf-8'), b'')
        return base64.b64encode(ciphertext).decode('utf-8')

    # [데이터] 복호화 -> String 반환
    def decrypt_data(self, ciphertext_b64, aes_handle):
        env_aead = aes_handle.primitive(aead.Aead)
        ciphertext = base64.b64decode(ciphertext_b64)
        decrypted = env_aead.decrypt(ciphertext, b'')
        return decrypted.decode('utf-8')
