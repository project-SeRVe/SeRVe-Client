"""
ServeClient - Zero-Trust SDK 메인 클래스

사용자가 직접 사용하는 고수준 API 제공.
내부적으로 Session, CryptoUtils, ApiClient를 조율하여
End-to-End 암호화를 구현.

핵심 기능:
1. Lazy Loading: 필요할 때만 서버에서 암호화된 키를 받아와 복호화
2. 자동 키 관리: 사용자는 암호화를 의식하지 않고 API만 호출
3. Zero-Trust: 서버는 평문 데이터나 원본 키를 절대 보지 못함
"""

from typing import Optional, Tuple, List, Dict, Any
from .session import Session
from .security.crypto_utils import CryptoUtils
from .api_client import ApiClient


class ServeClient:
    """
    Zero-Trust 문서 공유 플랫폼 클라이언트 SDK

    사용법:
        client = ServeClient(server_url="http://localhost:8080")
        client.login("user@example.com", "password")
        client.create_repository("MyRepo", "Description")
        client.upload_document("secret content", repo_id=1)
    """

    def __init__(self, server_url: str = "http://localhost:8080"):
        """
        Args:
            server_url: 서버 URL
        """
        self.api = ApiClient(server_url)
        self.crypto = CryptoUtils()
        self.session = Session()

    # ==================== 내부 헬퍼 메서드 ====================

    def _ensure_authenticated(self):
        """인증 상태 확인 (내부용)"""
        if not self.session.is_authenticated():
            raise RuntimeError("로그인이 필요합니다.")

    def _ensure_team_key(self, repo_id: str):
        """
        팀 키 Lazy Loading (핵심 로직!)

        Session에 팀 키가 없으면:
        1. 서버에서 암호화된 팀 키 조회
        2. 내 개인키로 복호화
        3. Session에 캐싱

        Args:
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            KeysetHandle: 복호화된 팀 키

        Raises:
            RuntimeError: 팀 키 조회/복호화 실패 시
        """
        # 1. 캐시 확인
        cached_key = self.session.get_cached_team_key(repo_id)
        if cached_key:
            return cached_key

        # 2. 서버에서 암호화된 팀 키 받아오기
        self._ensure_authenticated()
        success, encrypted_key = self.api.get_team_key(
            repo_id,
            self.session.user_id,
            self.session.access_token
        )

        if not success:
            # ADMIN 중심 에러 메시지 표시
            error_msg = encrypted_key if isinstance(encrypted_key, str) else str(encrypted_key)
            raise RuntimeError(
                f"팀 키 조회 실패\n"
                f"{'=' * 60}\n"
                f"{error_msg}\n"
                f"{'=' * 60}\n"
                f"💡 해결 방법:\n"
                f"   1. 팀 멤버가 아닌 경우: 팀 ADMIN에게 초대를 요청하세요\n"
                f"   2. 팀 키 미설정: 팀 ADMIN에게 재초대를 요청하세요\n"
                f"   3. 위 메시지에서 ADMIN 이메일을 확인하세요"
            )

        # 3. 내 개인키로 복호화
        try:
            private_key = self.session.get_private_key()
            team_key = self.crypto.unwrap_aes_key(encrypted_key, private_key)
        except Exception as e:
            raise RuntimeError(f"팀 키 복호화 실패: {e}")

        # 4. 캐시에 저장
        self.session.cache_team_key(repo_id, team_key)
        return team_key

    # ==================== 인증 API ====================

    def signup(self, email: str, password: str) -> Tuple[bool, str]:
        """
        회원가입

        내부 동작:
        1. 새로운 키 쌍 생성
        2. 개인키를 비밀번호로 암호화
        3. 공개키와 암호화된 개인키를 서버에 전송

        Args:
            email: 이메일
            password: 비밀번호

        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 키 쌍 생성
            key_pair = self.crypto.generate_key_pair()
            public_key_json = self.crypto.get_public_key_json(key_pair)

            # 2. 개인키를 비밀번호로 암호화
            encrypted_private_key = self.crypto.encrypt_private_key(key_pair, password)

            # 3. 서버에 전송
            return self.api.signup(email, password, public_key_json, encrypted_private_key)

        except Exception as e:
            return False, f"회원가입 처리 오류: {str(e)}"

    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """
        로그인

        내부 동작:
        1. 서버에 로그인 요청
        2. 받은 encryptedPrivateKey를 비밀번호로 복호화
        3. 개인키를 Session에 저장

        Args:
            email: 이메일
            password: 비밀번호

        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 서버 로그인
            success, data = self.api.login(email, password)
            if not success:
                return False, data

            # 2. 세션에 사용자 정보 저장
            self.session.set_user_credentials(
                data['accessToken'],
                data['userId'],
                data['email']
            )

            # 3. 암호화된 개인키 복구 (Zero-Trust 핵심!)
            try:
                encrypted_priv_key = data['encryptedPrivateKey']
                private_key = self.crypto.recover_private_key(encrypted_priv_key, password)
                public_key = private_key.public_keyset_handle()

                # 4. Session에 저장
                self.session.set_key_pair(private_key, public_key)

                return True, "로그인 성공"

            except Exception as e:
                # 개인키 복구 실패 (비밀번호 오류 가능성)
                self.session.clear()
                return False, f"개인키 복구 실패: {e}"

        except Exception as e:
            return False, f"로그인 오류: {str(e)}"

    def logout(self) -> Tuple[bool, str]:
        """로그아웃 (메모리 초기화)"""
        self.session.clear()
        return True, "로그아웃 성공"

    def reset_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        """비밀번호 재설정"""
        return self.api.reset_password(email, new_password)

    def withdraw(self) -> Tuple[bool, str]:
        """회원 탈퇴"""
        self._ensure_authenticated()
        success, msg = self.api.withdraw(self.session.access_token)
        if success:
            self.session.clear()
        return success, msg

    # ==================== 저장소 API ====================

    def create_repository(self, name: str, description: str = "") -> Tuple[Optional[str], str]:
        """
        저장소 생성

        내부 동작:
        1. 새로운 AES 팀 키 생성
        2. 내 공개키로 팀 키 래핑
        3. 서버에 전송
        4. 원본 팀 키를 Session에 캐싱

        Args:
            name: 저장소 이름
            description: 설명

        Returns:
            (저장소 ID (UUID 문자열), 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 새로운 팀 키 생성
            team_key = self.crypto.generate_aes_key()

            # 2. 내 공개키로 래핑
            my_public_key = self.session.get_public_key()
            encrypted_team_key = self.crypto.wrap_aes_key(team_key, my_public_key)

            # 3. 서버에 전송
            success, data = self.api.create_repository(
                name,
                description,
                self.session.user_id,
                encrypted_team_key,
                self.session.access_token
            )

            if not success:
                return None, data

            # 4. 응답에서 repo_id 추출 (UUID 문자열)
            repo_id = str(data) if isinstance(data, str) else data.get('id')

            # 5. 원본 팀 키를 Session에 캐싱
            self.session.cache_team_key(repo_id, team_key)

            return repo_id, f"저장소 생성 성공 (ID: {repo_id})"

        except Exception as e:
            return None, f"저장소 생성 오류: {str(e)}"

    def get_my_repositories(self) -> Tuple[Optional[List], str]:
        """내 저장소 목록 조회"""
        self._ensure_authenticated()
        success, data = self.api.get_my_repositories(
            self.session.user_id,
            self.session.access_token
        )
        return (data, "조회 성공") if success else (None, data)

    def delete_repository(self, repo_id: str) -> Tuple[bool, str]:
        """저장소 삭제"""
        self._ensure_authenticated()
        success, msg = self.api.delete_repository(
            repo_id,
            self.session.user_id,
            self.session.access_token
        )
        # 캐시에서도 제거
        if success and repo_id in self.session.team_keys:
            del self.session.team_keys[repo_id]
        return success, msg

    # ==================== 멤버 관리 API ====================

    def invite_member(self, repo_id: str, email: str) -> Tuple[bool, str]:
        """
        멤버 초대

        내부 동작:
        1. 초대할 사람의 공개키 조회
        2. 현재 저장소의 팀 키를 상대방 공개키로 래핑
        3. 서버에 전송

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            email: 초대할 사람의 이메일

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 상대방 공개키 조회
            success, public_key_json = self.api.get_user_public_key(
                email,
                self.session.access_token
            )

            if not success:
                return False, f"사용자 공개키 조회 실패: {public_key_json}"

            # 2. JSON → KeysetHandle 변환
            recipient_public_key = self.crypto.parse_public_key_json(public_key_json)

            # 3. 팀 키 가져오기 (lazy loading)
            team_key = self._ensure_team_key(repo_id)

            # 4. 상대방 공개키로 팀 키 래핑
            encrypted_team_key = self.crypto.wrap_aes_key(team_key, recipient_public_key)

            # 5. 서버에 전송
            return self.api.invite_member(
                repo_id,
                email,
                encrypted_team_key,
                self.session.access_token
            )

        except Exception as e:
            return False, f"멤버 초대 오류: {str(e)}"

    def get_members(self, repo_id: str) -> Tuple[Optional[List], str]:
        """멤버 목록 조회"""
        self._ensure_authenticated()
        success, data = self.api.get_members(repo_id, self.session.access_token)
        return (data, "조회 성공") if success else (None, data)

    def kick_member(self, repo_id: str, target_user_id: str,
                    auto_rotate_keys: bool = True) -> Tuple[bool, str]:
        """
        멤버 강퇴 (자동 키 로테이션 지원)

        Args:
            repo_id: 팀 ID
            target_user_id: 강퇴할 사용자 ID
            auto_rotate_keys: 자동 키 로테이션 수행 여부 (기본값: True)

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()

        # 1. 멤버 강퇴 API 호출
        success, response = self.api.kick_member(
            repo_id,
            target_user_id,
            self.session.user_id,
            self.session.access_token
        )

        if not success:
            return False, f"멤버 강퇴 실패: {response}"

        # 2. 응답 확인
        if not isinstance(response, dict):
            return True, "멤버 강퇴 성공 (키 로테이션 정보 없음)"

        key_rotation_required = response.get("keyRotationRequired", False)
        remaining_members = response.get("remainingMembers", [])

        # 3. 자동 키 로테이션 수행
        if auto_rotate_keys and key_rotation_required and remaining_members:
            try:
                # 3-1. 새 팀 키 생성
                new_team_key = self.crypto.generate_aes_key()

                # 3-2. 각 멤버의 공개키로 새 팀 키 래핑
                member_keys = []
                for member in remaining_members:
                    user_id = member["userId"]
                    public_key_json = member["publicKey"]

                    # 공개키 파싱
                    public_key_handle = self.crypto.parse_public_key_json(public_key_json)

                    # 팀 키 래핑
                    encrypted_team_key = self.crypto.wrap_aes_key(new_team_key, public_key_handle)

                    member_keys.append({
                        "userId": user_id,
                        "encryptedTeamKey": encrypted_team_key
                    })

                # 3-3. 키 로테이션 API 호출
                rotate_success, rotate_msg = self.api.rotate_team_keys(
                    repo_id,
                    member_keys,
                    self.session.access_token
                )

                if not rotate_success:
                    return True, f"멤버 강퇴 성공, 하지만 키 로테이션 실패: {rotate_msg}"

                # 3-4. 기존 문서(청크)를 새 키로 재암호화
                try:
                    self._reencrypt_all_documents(repo_id, new_team_key)
                except Exception as e:
                    # 재암호화 실패해도 키 로테이션은 완료됨
                    return True, f"키 로테이션 완료, 하지만 문서 재암호화 실패: {str(e)}"

                # 3-5. 세션에서 팀 키 업데이트 (내 것만)
                self.session.cache_team_key(repo_id, new_team_key)

                return True, f"멤버 강퇴 성공 및 키 로테이션 완료 ({len(member_keys)}명)"

            except Exception as e:
                return True, f"멤버 강퇴 성공, 하지만 자동 키 로테이션 실패: {str(e)}"

        # 4. 키 로테이션 미수행
        if key_rotation_required and not auto_rotate_keys:
            return True, "멤버 강퇴 성공 (수동 키 로테이션 필요)"

        return True, response.get("message", "멤버 강퇴 성공")

    def update_member_role(self, repo_id: str, target_user_id: str, new_role: str) -> Tuple[bool, str]:
        """멤버 권한 변경"""
        self._ensure_authenticated()
        return self.api.update_member_role(
            repo_id,
            target_user_id,
            self.session.user_id,
            new_role,
            self.session.access_token
        )

    # ==================== 문서 API ====================

    def upload_document(self, plaintext: str, repo_id: str,
                       file_name: str = "document.txt",
                       file_type: str = "text/plain") -> Tuple[bool, str]:
        """
        문서 업로드

        내부 동작:
        1. 팀 키 가져오기 (lazy loading)
        2. 평문을 팀 키로 암호화
        3. 암호문을 서버에 전송

        Args:
            plaintext: 평문 내용
            repo_id: 저장소 ID (UUID 문자열)
            file_name: 파일명 (기본값: document.txt)
            file_type: 파일 타입 (기본값: text/plain)

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 팀 키 가져오기 (lazy loading)
            team_key = self._ensure_team_key(repo_id)

            # 2. 암호화
            encrypted_content = self.crypto.encrypt_data(plaintext, team_key)

            # 3. 업로드
            success, msg = self.api.upload_document(
                encrypted_content,
                repo_id,
                self.session.access_token,
                file_name,
                file_type
            )

            return success, msg

        except Exception as e:
            return False, f"업로드 오류: {str(e)}"

    def download_document(self, doc_id: str, repo_id: str) -> Tuple[Optional[str], str]:
        """
        [사용 중단] 문서 다운로드 (Federated Model에서 지원하지 않음)

        Federated Model에서는 다운로드 대신 동기화(sync_team_chunks)를 사용합니다.

        대신 사용:
        - sync_team_chunks(repo_id, last_version) - 팀 전체 증분 동기화
        - download_chunks_from_document(file_name, repo_id) - 특정 파일 동기화 (내부적으로 sync 사용)
        """
        return None, "다운로드 기능은 Federated Model에서 지원하지 않습니다. sync_team_chunks() 또는 download_chunks_from_document()를 사용하세요."

    def get_documents(self, repo_id: str) -> Tuple[Optional[List], str]:
        """
        문서 목록 조회

        Args:
            repo_id: 저장소 ID (UUID 문자열)

        Returns:
            (문서 목록, 메시지)
        """
        self._ensure_authenticated()
        success, data = self.api.get_documents(repo_id, self.session.access_token)
        return (data, "조회 성공") if success else (None, data)

    def delete_document(self, repo_id: str, doc_id: str) -> Tuple[bool, str]:
        """
        문서 삭제

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            doc_id: 문서 ID

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()
        return self.api.delete_document(repo_id, doc_id, self.session.access_token)

    # ==================== 벡터 청크 API ====================

    def upload_chunks_to_document(self, file_name: str, repo_id: str, chunks_data: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        벡터 청크 배치 업로드 (Envelope Encryption 적용)

        Envelope Encryption:
        1. DEK(Data Encryption Key) 생성 - 문서별 랜덤 키
        2. DEK로 청크 데이터 암호화
        3. 팀 키(KEK)로 DEK 래핑(암호화)
        4. 암호화된 DEK를 서버에 전송

        Args:
            file_name: 파일명 (문서 식별용)
            repo_id: 저장소 ID (팀 ID, 팀 키 조회용)
            chunks_data: 청크 데이터 목록 [{"chunkIndex": int, "data": str (평문)}, ...]

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()

        try:
            # 1. 팀 키 가져오기 (KEK - Key Encryption Key)
            team_key = self._ensure_team_key(repo_id)

            # 2. DEK(Data Encryption Key) 생성 - 문서별 랜덤 키
            dek = self.crypto.generate_aes_key()

            # 3. 각 청크를 DEK로 암호화
            encrypted_chunks = []
            for chunk in chunks_data:
                chunk_index = chunk["chunkIndex"]
                plaintext_data = chunk["data"]

                # DEK로 암호화 (팀 키가 아님!)
                encrypted_blob = self.crypto.encrypt_data(plaintext_data, dek)

                encrypted_chunks.append({
                    "chunkIndex": chunk_index,
                    "encryptedBlob": encrypted_blob
                })

            # 4. DEK를 팀 키로 래핑 (암호화) - Envelope Encryption
            encrypted_dek = self.crypto.wrap_key_with_aes(dek, team_key)

            # 5. 서버에 업로드 (암호화된 DEK 포함)
            return self.api.upload_chunks(
                repo_id,  # team_id
                file_name,
                encrypted_chunks,
                self.session.access_token,
                encrypted_dek  # Base64 인코딩된 암호화된 DEK
            )

        except Exception as e:
            return False, f"청크 업로드 오류: {str(e)}"

    def download_chunks_from_document(self, file_name: str, repo_id: str) -> Tuple[Optional[List[Dict]], str]:
        """
        [주의] 이름은 download이지만 내부적으로 동기화(sync) API를 사용합니다.
        Federated Model에서는 다운로드가 아닌 동기화만 지원하기 때문입니다.

        문서의 모든 청크 가져오기 (Envelope Encryption 적용, 동기화 API 사용, 복호화 포함)

        Envelope Encryption:
        1. 팀 키로 DEK를 언래핑(복호화)
        2. DEK로 청크 데이터 복호화

        Args:
            file_name: 파일명 (문서 식별용)
            repo_id: 저장소 ID (팀 ID, 팀 키 조회용)

        Returns:
            (청크 목록, 메시지)
            청크 형식: [{"chunkIndex": int, "data": str (복호화된 평문), "version": int}, ...]
        """
        self._ensure_authenticated()

        try:
            # 1. 문서 목록 조회하여 fileName → documentId + encryptedDEK 가져오기
            success, documents = self.api.get_documents(repo_id, self.session.access_token)
            if not success:
                return None, f"문서 목록 조회 실패: {documents}"

            # 2. fileName으로 documentId 및 encryptedDEK 찾기
            document_id = None
            encrypted_dek_bytes = None
            for doc in documents:
                if doc.get("fileName") == file_name:
                    document_id = doc.get("docId")
                    encrypted_dek_bytes = doc.get("encryptedDEK")  # byte[] 형식
                    break

            if not document_id:
                return None, f"문서를 찾을 수 없습니다: {file_name}"

            if not encrypted_dek_bytes:
                return None, f"문서에 암호화된 DEK가 없습니다: {file_name} (Envelope Encryption 미적용)"

            # 3. 동기화 API로 팀의 모든 청크 가져오기 (lastVersion=-1로 전체 조회, version > -1이므로 모든 청크 포함)
            success, all_chunks = self.api.sync_team_chunks(repo_id, -1, self.session.access_token)
            if not success:
                return None, f"청크 동기화 실패: {all_chunks}"

            # 4. 해당 문서의 청크만 필터링 (삭제되지 않은 것만)
            document_chunks = [
                chunk for chunk in all_chunks
                if chunk.get("documentId") == document_id and not chunk.get("isDeleted", False)
            ]

            if not document_chunks:
                return None, f"문서에 청크가 없습니다: {file_name}"

            # 5. 팀 키 가져오기 (KEK - Key Encryption Key)
            team_key = self._ensure_team_key(repo_id)

            # 6. Envelope Encryption: 팀 키로 DEK 언래핑(복호화)
            import base64
            if isinstance(encrypted_dek_bytes, list):
                # byte[] → Base64 변환
                encrypted_dek = base64.b64encode(bytes(encrypted_dek_bytes)).decode('utf-8')
            elif isinstance(encrypted_dek_bytes, bytes):
                encrypted_dek = base64.b64encode(encrypted_dek_bytes).decode('utf-8')
            else:
                encrypted_dek = encrypted_dek_bytes  # 이미 Base64 문자열

            dek = self.crypto.unwrap_key_with_aes(encrypted_dek, team_key)

            # 7. 각 청크를 DEK로 복호화 (팀 키가 아님!)
            decrypted_chunks = []
            for chunk in document_chunks:
                chunk_index = chunk["chunkIndex"]
                encrypted_blob = chunk["encryptedBlob"]
                version = chunk["version"]

                # byte[] → Base64 변환 (필요시)
                if isinstance(encrypted_blob, list):
                    encrypted_blob = base64.b64encode(bytes(encrypted_blob)).decode('utf-8')

                # DEK로 복호화 (팀 키가 아님!)
                plaintext = self.crypto.decrypt_data(encrypted_blob, dek)

                decrypted_chunks.append({
                    "chunkIndex": chunk_index,
                    "data": plaintext,
                    "version": version
                })

            # chunkIndex로 정렬
            decrypted_chunks.sort(key=lambda x: x["chunkIndex"])

            return decrypted_chunks, "청크 다운로드 및 복호화 성공"

        except Exception as e:
            return None, f"청크 다운로드 오류: {str(e)}"

    def delete_chunk_from_document(self, doc_id: str, chunk_index: int) -> Tuple[bool, str]:
        """
        특정 청크 삭제

        Args:
            doc_id: 문서 ID (UUID 문자열)
            chunk_index: 청크 인덱스

        Returns:
            (성공 여부, 메시지)
        """
        self._ensure_authenticated()
        return self.api.delete_chunk(doc_id, chunk_index, self.session.access_token)

    def sync_document_chunks(self, doc_id: str, repo_id: str, last_version: int = 0) -> Tuple[Optional[List[Dict]], str]:
        """
        문서별 증분 청크 동기화 (복호화 포함)

        Args:
            doc_id: 문서 ID (UUID 문자열)
            repo_id: 저장소 ID (팀 키 조회용)
            last_version: 마지막으로 알려진 버전 (기본값: 0)

        Returns:
            (변경된 청크 목록, 메시지)
            청크 형식: [{"chunkIndex": int, "data": str (복호화된 평문), "version": int, "isDeleted": bool}, ...]
        """
        self._ensure_authenticated()

        try:
            # 1. 서버에서 변경된 청크들 조회
            success, chunks = self.api.sync_document_chunks(
                doc_id, last_version, self.session.access_token
            )

            if not success:
                return None, chunks

            if not chunks:
                return [], "변경사항 없음"

            # 2. 팀 키 가져오기
            team_key = self._ensure_team_key(repo_id)

            # 3. 각 청크 복호화 (삭제되지 않은 경우에만)
            decrypted_chunks = []
            for chunk in chunks:
                chunk_index = chunk["chunkIndex"]
                version = chunk["version"]
                is_deleted = chunk.get("isDeleted", False)

                result_chunk = {
                    "chunkIndex": chunk_index,
                    "version": version,
                    "isDeleted": is_deleted
                }

                # 삭제되지 않은 청크만 복호화
                if not is_deleted:
                    encrypted_blob = chunk["encryptedBlob"]

                    # byte[] → Base64 변환 (필요시)
                    if isinstance(encrypted_blob, list):
                        import base64
                        encrypted_blob = base64.b64encode(bytes(encrypted_blob)).decode('utf-8')

                    # 복호화
                    plaintext = self.crypto.decrypt_data(encrypted_blob, team_key)
                    result_chunk["data"] = plaintext
                else:
                    result_chunk["data"] = None

                decrypted_chunks.append(result_chunk)

            return decrypted_chunks, f"{len(decrypted_chunks)}개 청크 동기화 완료"

        except Exception as e:
            return None, f"청크 동기화 오류: {str(e)}"

    def sync_team_chunks(self, repo_id: str, last_version: int = 0) -> Tuple[Optional[Dict[str, List[Dict]]], str]:
        """
        팀 전체 증분 청크 동기화 (복호화 포함)

        Args:
            repo_id: 저장소 ID (UUID 문자열)
            last_version: 마지막으로 알려진 버전 (기본값: 0)

        Returns:
            (문서별 청크 딕셔너리, 메시지)
            형식: {
                "doc-id-1": [{"chunkIndex": int, "data": str, "version": int, "isDeleted": bool}, ...],
                "doc-id-2": [...]
            }
        """
        self._ensure_authenticated()

        try:
            # 1. 서버에서 팀 전체 변경된 청크들 조회
            success, chunks = self.api.sync_team_chunks(
                repo_id, last_version, self.session.access_token
            )

            if not success:
                return None, chunks

            if not chunks:
                return {}, "변경사항 없음"

            # 2. 팀 키 가져오기
            team_key = self._ensure_team_key(repo_id)

            # 3. 문서별로 그룹핑하면서 복호화
            documents_chunks = {}
            for chunk in chunks:
                doc_id = chunk["documentId"]
                chunk_index = chunk["chunkIndex"]
                version = chunk["version"]
                is_deleted = chunk.get("isDeleted", False)

                result_chunk = {
                    "chunkIndex": chunk_index,
                    "version": version,
                    "isDeleted": is_deleted
                }

                # 삭제되지 않은 청크만 복호화
                if not is_deleted:
                    encrypted_blob = chunk["encryptedBlob"]

                    # byte[] → Base64 변환 (필요시)
                    if isinstance(encrypted_blob, list):
                        import base64
                        encrypted_blob = base64.b64encode(bytes(encrypted_blob)).decode('utf-8')

                    # 복호화
                    plaintext = self.crypto.decrypt_data(encrypted_blob, team_key)
                    result_chunk["data"] = plaintext
                else:
                    result_chunk["data"] = None

                # 문서별로 그룹핑
                if doc_id not in documents_chunks:
                    documents_chunks[doc_id] = []
                documents_chunks[doc_id].append(result_chunk)

            total_chunks = sum(len(chunks) for chunks in documents_chunks.values())
            return documents_chunks, f"{len(documents_chunks)}개 문서, 총 {total_chunks}개 청크 동기화 완료"

        except Exception as e:
            return None, f"팀 청크 동기화 오류: {str(e)}"

    # ==================== 내부 헬퍼 메서드 ====================

    def _reencrypt_all_documents(self, repo_id: str, new_team_key):
        """
        팀의 모든 문서 DEK를 새 팀 키로 재암호화 (Envelope Encryption)

        Envelope Encryption:
        - 청크 데이터는 변경하지 않음 (DEK로 이미 암호화됨)
        - DEK만 이전 팀 키로 언래핑 → 새 팀 키로 래핑
        - 작은 메타데이터만 업데이트 (대용량 데이터 재암호화 불필요)

        Args:
            repo_id: 팀 ID
            new_team_key: 새로 생성된 팀 키 (KeysetHandle)
        """
        import base64

        # 1. 현재 팀 키 백업 (이전 키)
        old_team_key = self.session.get_cached_team_key(repo_id)
        if not old_team_key:
            raise ValueError("이전 팀 키를 찾을 수 없습니다")

        # 2. 모든 문서 조회
        success, documents = self.api.get_documents(repo_id, self.session.access_token)
        if not success:
            raise RuntimeError(f"문서 목록 조회 실패: {documents}")

        # 3. 각 문서의 DEK 재암호화
        reencrypted_docs = []
        for doc in documents:
            doc_id = doc.get("docId")
            encrypted_dek_bytes = doc.get("encryptedDEK")

            if not encrypted_dek_bytes:
                # Envelope Encryption 미적용 문서는 스킵
                continue

            # 3-1. byte[] → Base64 변환 (필요시)
            if isinstance(encrypted_dek_bytes, list):
                encrypted_dek = base64.b64encode(bytes(encrypted_dek_bytes)).decode('utf-8')
            elif isinstance(encrypted_dek_bytes, bytes):
                encrypted_dek = base64.b64encode(encrypted_dek_bytes).decode('utf-8')
            else:
                encrypted_dek = encrypted_dek_bytes  # 이미 Base64 문자열

            # 3-2. 이전 팀 키로 DEK 언래핑(복호화)
            try:
                dek = self.crypto.unwrap_key_with_aes(encrypted_dek, old_team_key)
            except Exception as e:
                # 복호화 실패 시 스킵 (이미 새 키로 암호화되었거나 손상됨)
                print(f"경고: 문서 {doc_id} DEK 복호화 실패: {e}")
                continue

            # 3-3. 새 팀 키로 DEK 래핑(암호화)
            new_encrypted_dek = self.crypto.wrap_key_with_aes(dek, new_team_key)

            reencrypted_docs.append({
                "documentId": doc_id,
                "newEncryptedDEK": new_encrypted_dek  # Base64 문자열
            })

        # 4. 서버에 재암호화된 DEK 전송 (청크 데이터는 변경 없음!)
        if reencrypted_docs:
            success, msg = self.api.reencrypt_document_keys(
                repo_id,
                reencrypted_docs,
                self.session.access_token
            )
            if not success:
                raise RuntimeError(f"DEK 재암호화 실패: {msg}")

    # ==================== 디버그 유틸 ====================

    def get_session_info(self) -> Dict[str, Any]:
        """세션 정보 조회 (디버깅용)"""
        return {
            "authenticated": self.session.is_authenticated(),
            "user_id": self.session.user_id,
            "email": self.session.email,
            "has_private_key": self.session.has_private_key(),
            "cached_repositories": list(self.session.team_keys.keys())
        }
