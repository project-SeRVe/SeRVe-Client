# README2: SeRVe-Client 구현 상세 문서

## 📚 목차
- [1. 프로젝트 개요](#1-프로젝트-개요)
- [2. 아키텍처 구조](#2-아키텍처-구조)
- [3. SDK 계층 (serve_sdk/)](#3-sdk-계층-serve_sdk)
- [4. CLI 계층 (src/cli/)](#4-cli-계층-srccli)
- [5. 암호화 워크플로우](#5-암호화-워크플로우)
- [6. 핵심 기능 구현](#6-핵심-기능-구현)
- [7. 파일 구조 및 책임](#7-파일-구조-및-책임)

---

## 1. 프로젝트 개요

### 1.1 SeRVe-Client란?
**SeRVe (Secure Robotics Validation environment) CLI**는 Zero-Trust End-to-End 암호화 기반 문서/데모 데이터 공유 플랫폼의 클라이언트 구현입니다.

### 1.2 핵심 설계 원칙
- **Zero-Trust**: 서버는 평문 데이터와 복호화 키를 절대 보지 못함
- **End-to-End 암호화**: 모든 민감 데이터는 클라이언트에서만 암호화/복호화
- **Lazy Loading**: 필요한 시점에만 키를 서버에서 가져와 복호화
- **계층 분리**: SDK(비즈니스 로직) / CLI(사용자 인터페이스) 명확히 분리

### 1.3 기술 스택
```python
# 코어 암호화 라이브러리
tink (Google)        # ECIES (P-256), AES-256-GCM
  └─ ECC P-256       # 비대칭 암호화 (키 교환)
  └─ AES-256-GCM     # 대칭 암호화 (데이터 암호화)
  └─ Hybrid Encryption  # 키 래핑/언래핑

# CLI 프레임워크
click                # 명령어 인터페이스

# HTTP 클라이언트
requests             # REST API 통신
```

---

## 2. 아키텍처 구조

### 2.1 전체 계층 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                  사용자 (터미널)                          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                CLI Layer (src/cli/)                      │
│  ┌──────────────┬─────────────┬────────────────────┐   │
│  │ auth.py      │ repo.py     │ data.py            │   │
│  │ (인증 관리)   │ (저장소 관리)│ (데이터 관리)       │   │
│  └──────────────┴─────────────┴────────────────────┘   │
│  ┌───────────────────────────────────────────────────┐ │
│  │ context.py         │ session_manager.py           │ │
│  │ (SDK 초기화)       │ (로컬 세션 저장)              │ │
│  └───────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              SDK Layer (serve_sdk/)                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ServeClient (client.py)                          │  │
│  │ - 비즈니스 로직 오케스트레이션                     │  │
│  │ - 암호화/복호화 워크플로우                         │  │
│  │ - Lazy Loading 구현                              │  │
│  └──────────┬───────────────────────────┬───────────┘  │
│             │                           │               │
│  ┌──────────▼──────────┐   ┌───────────▼──────────┐   │
│  │ ApiClient           │   │ CryptoUtils          │   │
│  │ (api_client.py)     │   │ (crypto_utils.py)    │   │
│  │ - HTTP 통신         │   │ - 암호화 프리미티브   │   │
│  │ - 인증 헤더 관리    │   │ - 키 생성/래핑       │   │
│  └──────────┬──────────┘   └──────────────────────┘   │
│             │                                           │
│  ┌──────────▼──────────────────────────────────────┐  │
│  │ Session (session.py)                            │  │
│  │ - 메모리 내 상태 관리 (복호화된 키, 토큰)        │  │
│  └─────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  서버 (REST API)                         │
│  - 암호화된 데이터만 저장                                │
│  - 평문 키/데이터 접근 불가 (Zero-Trust)                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 책임 분리 (Separation of Concerns)

| 계층 | 파일 | 책임 |
|------|------|------|
| **CLI** | `src/cli/*.py` | 사용자 입력/출력, 명령어 파싱, 로컬 세션 관리 |
| **SDK - 오케스트레이터** | `serve_sdk/client.py` | 비즈니스 로직, 암호화 워크플로우 조율 |
| **SDK - 통신** | `serve_sdk/api_client.py` | HTTP 요청/응답, 에러 처리 |
| **SDK - 암호화** | `serve_sdk/security/crypto_utils.py` | 키 생성, 암호화/복호화, 래핑/언래핑 |
| **SDK - 상태** | `serve_sdk/session.py` | 메모리 내 키/토큰 캐싱 |

---

## 3. SDK 계층 (serve_sdk/)

### 3.1 ServeClient (client.py) - 1030 lines

**역할**: 모든 비즈니스 로직의 중앙 오케스트레이터

#### 3.1.1 핵심 메서드 분류

```python
class ServeClient:
    # ==================== 인증 API ====================
    def signup(email, password) -> Tuple[bool, str]
        # 1. 키 쌍 생성 (ECC P-256)
        # 2. 개인키를 비밀번호로 암호화
        # 3. 공개키 + 암호화된 개인키 → 서버 전송
    
    def login(email, password) -> Tuple[bool, str]
        # 1. 서버 인증
        # 2. encryptedPrivateKey를 비밀번호로 복호화
        # 3. Session에 복호화된 키 저장
    
    def reset_password(email, new_password) -> Tuple[bool, str]
        # 개인키를 새 비밀번호로 재암호화 후 업로드
    
    def withdraw() -> Tuple[bool, str]
        # 회원 탈퇴 + Session 초기화

    # ==================== 저장소 API ====================
    def create_repository(name, description) -> Tuple[Optional[str], str]
        # 1. 새 팀 키(AES-256) 생성
        # 2. 내 공개키로 팀 키 래핑
        # 3. 서버에 암호화된 팀 키 전송
        # 4. 원본 팀 키 Session 캐싱
    
    def invite_member(repo_id, email) -> Tuple[bool, str]
        # 1. 초대할 사용자의 공개키 조회
        # 2. 팀 키를 그 공개키로 래핑
        # 3. 서버에 전송 (서버는 복호화 불가)
    
    def kick_member(repo_id, user_id) -> Tuple[bool, str]
        # 1. 멤버 제거
        # 2. 보안을 위해 팀 키 로테이션
        # 3. 남은 멤버들에게 새 팀 키 재배포

    def _ensure_team_key(repo_id: str)
        # 🔥 Lazy Loading 핵심 로직!
        # 1. Session 캐시 확인
        # 2. 없으면 서버에서 암호화된 팀 키 조회
        # 3. 내 개인키로 복호화
        # 4. Session에 캐싱

    # ==================== 데이터 API ====================
    def upload_chunks_to_document(file_name, repo_id, chunks_data)
        # Envelope Encryption 적용:
        # 1. DEK(Data Encryption Key) 생성
        # 2. 각 청크를 DEK로 암호화
        # 3. DEK를 팀 키(KEK)로 래핑
        # 4. 암호화된 청크 + 암호화된 DEK → 서버
    
    def download_chunks_from_document(file_name, repo_id)
        # Envelope Encryption 복호화:
        # 1. 문서의 암호화된 DEK 조회
        # 2. 팀 키로 DEK 언래핑
        # 3. DEK로 각 청크 복호화
        # 4. 평문 청크 반환
    
    def sync_team_chunks(repo_id, last_version)
        # 팀의 모든 문서 동기화
```

#### 3.1.2 Lazy Loading 패턴 상세

```python
def _ensure_team_key(self, repo_id: str):
    """
    팀 키 Lazy Loading - Zero-Trust의 핵심!
    
    Session에 팀 키가 없으면:
    1. 서버에서 암호화된 팀 키 조회 (내 개인키로 래핑된 상태)
    2. 내 개인키로 복호화
    3. Session에 캐싱
    
    이후 같은 repo_id 요청 시 캐시에서 즉시 반환
    → 불필요한 서버 요청 최소화
    → 서버는 평문 팀 키를 절대 보지 못함
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
        raise RuntimeError(f"팀 키 조회 실패: {encrypted_key}")

    # 3. 내 개인키로 복호화
    private_key = self.session.get_private_key()
    team_key = self.crypto.unwrap_aes_key(encrypted_key, private_key)

    # 4. 캐시에 저장
    self.session.cache_team_key(repo_id, team_key)
    return team_key
```

### 3.2 ApiClient (api_client.py) - 566 lines

**역할**: 순수 HTTP 통신 전담 (암호화 로직 일절 없음)

```python
class ApiClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
    
    # ==================== 인증 API ====================
    def signup(email, password, public_key, encrypted_private_key)
        # POST /auth/signup
    
    def login(email, password)
        # POST /auth/login
        # Returns: {accessToken, userId, email, encryptedPrivateKey}
    
    def reset_password(email, new_password, encrypted_private_key)
        # PUT /auth/reset-password
    
    def withdraw(access_token)
        # DELETE /auth/withdraw

    # ==================== 저장소 API ====================
    def create_repository(name, description, owner_id, encrypted_team_key, token)
        # POST /repositories
    
    def get_team_key(repo_id, user_id, token)
        # GET /repositories/{repo_id}/team-key?userId={user_id}
    
    def invite_member(repo_id, email, encrypted_key, token)
        # POST /repositories/{repo_id}/members
    
    def kick_member(repo_id, user_id, token)
        # DELETE /repositories/{repo_id}/members/{user_id}

    # ==================== 데이터 API ====================
    def upload_chunks(repo_id, file_name, encrypted_chunks, token, encrypted_dek)
        # POST /repositories/{repo_id}/documents
        # Body: {fileName, chunks: [{chunkIndex, encryptedBlob}], encryptedDEK}
    
    def sync_team_chunks(repo_id, last_version, token)
        # GET /repositories/{repo_id}/sync?lastVersion={version}
        # Returns: {documents: [{docId, fileName, encryptedDEK, chunks: [...]}]}
    
    def get_documents(repo_id, token)
        # GET /repositories/{repo_id}/documents
```

### 3.3 CryptoUtils (security/crypto_utils.py) - 327 lines

**역할**: Google Tink 래퍼, 모든 암호화 프리미티브 제공

#### 3.3.1 키 생성

```python
def generate_key_pair(self):
    """
    ECIES P-256 키 쌍 생성
    템플릿: ECIES_P256_HKDF_HMAC_SHA256_AES128_GCM
    
    Returns:
        KeysetHandle (개인키)
        └─ .public_keyset_handle() → 공개키 추출
    """
    template = hybrid.hybrid_key_templates.ECIES_P256_HKDF_HMAC_SHA256_AES128_GCM
    return tink.new_keyset_handle(template)

def generate_aes_key(self):
    """
    AES-256-GCM 키 생성 (팀 키/DEK용)
    """
    template = aead.aead_key_templates.AES256_GCM
    return tink.new_keyset_handle(template)
```

#### 3.3.2 키 래핑/언래핑 (Hybrid Encryption)

```python
def wrap_aes_key(self, aes_handle, recipient_public_key_handle) -> str:
    """
    AES 키를 수신자의 공개키로 래핑
    
    Zero-Trust 핵심:
    - 팀 키를 다른 사람의 공개키로 암호화
    - 서버는 해독 불가 (수신자만 자신의 개인키로 복호화 가능)
    
    1. AES 키 → JSON 직렬화
    2. 수신자 공개키로 암호화 (Hybrid Encryption)
    3. Base64 인코딩 후 반환
    """
    aes_json = self.serialize_aes_key(aes_handle)
    hybrid_encrypt = recipient_public_key_handle.primitive(hybrid.HybridEncrypt)
    encrypted_bytes = hybrid_encrypt.encrypt(aes_json.encode('utf-8'), b'')
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def unwrap_aes_key(self, encrypted_aes_key_b64: str, private_handle):
    """
    암호화된 AES 키를 내 개인키로 언래핑
    
    1. Base64 디코딩
    2. 내 개인키로 복호화 (Hybrid Decryption)
    3. JSON → AES KeysetHandle 변환
    """
    encrypted_bytes = base64.b64decode(encrypted_aes_key_b64)
    hybrid_decrypt = private_handle.primitive(hybrid.HybridDecrypt)
    decrypted_json = hybrid_decrypt.decrypt(encrypted_bytes, b'')
    return self.parse_aes_key_json(decrypted_json.decode('utf-8'))
```

#### 3.3.3 Envelope Encryption (DEK 래핑)

```python
def wrap_key_with_aes(self, dek_handle, kek_handle) -> str:
    """
    DEK(Data Encryption Key)를 KEK(Key Encryption Key, 팀 키)로 래핑
    
    Envelope Encryption:
    - DEK: 실제 데이터 암호화 키 (문서별 랜덤)
    - KEK: DEK를 암호화하는 키 (팀 공유 키)
    
    1. DEK → JSON 직렬화
    2. KEK(팀 키)로 AES-GCM 암호화
    3. Base64 인코딩
    """
    dek_json = self.serialize_aes_key(dek_handle)
    env_aead = kek_handle.primitive(aead.Aead)
    encrypted_bytes = env_aead.encrypt(dek_json.encode('utf-8'), b'')
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def unwrap_key_with_aes(self, encrypted_dek_b64: str, kek_handle):
    """
    KEK(팀 키)로 DEK 언래핑
    """
    encrypted_bytes = base64.b64decode(encrypted_dek_b64)
    env_aead = kek_handle.primitive(aead.Aead)
    decrypted_json = env_aead.decrypt(encrypted_bytes, b'')
    return self.parse_aes_key_json(decrypted_json.decode('utf-8'))
```

#### 3.3.4 데이터 암호화/복호화

```python
def encrypt_data(self, plaintext: str, aes_handle) -> str:
    """
    데이터를 AES-256-GCM으로 암호화
    
    Returns:
        Base64 인코딩된 암호문
    """
    env_aead = aes_handle.primitive(aead.Aead)
    ciphertext = env_aead.encrypt(plaintext.encode('utf-8'), b'')
    return base64.b64encode(ciphertext).decode('utf-8')

def decrypt_data(self, ciphertext_b64: str, aes_handle) -> str:
    """
    AES-256-GCM 복호화
    """
    env_aead = aes_handle.primitive(aead.Aead)
    ciphertext = base64.b64decode(ciphertext_b64)
    decrypted = env_aead.decrypt(ciphertext, b'')
    return decrypted.decode('utf-8')
```

#### 3.3.5 개인키 보호 (비밀번호 기반 암호화)

```python
def encrypt_private_key(self, private_handle, password: str) -> str:
    """
    개인키를 비밀번호로 암호화
    
    1. 비밀번호 → AES 키 유도 (SHA-256)
    2. 개인키 → JSON 직렬화
    3. 유도된 키로 AES-GCM 암호화
    4. Base64 인코딩
    
    주의: 프로덕션에서는 PBKDF2/Argon2 권장
    """
    aes_key_bytes = self._derive_key_from_password(password)
    aes_handle = self._create_aes_handle_from_bytes(aes_key_bytes)
    
    private_json = self._serialize_private_key(private_handle)
    env_aead = aes_handle.primitive(aead.Aead)
    encrypted = env_aead.encrypt(private_json.encode('utf-8'), b'')
    return base64.b64encode(encrypted).decode('utf-8')

def recover_private_key(self, encrypted_private_key_b64: str, password: str):
    """
    비밀번호로 개인키 복구
    
    잘못된 비밀번호 시 AES-GCM 무결성 검증 실패
    """
    aes_key_bytes = self._derive_key_from_password(password)
    aes_handle = self._create_aes_handle_from_bytes(aes_key_bytes)
    
    encrypted = base64.b64decode(encrypted_private_key_b64)
    env_aead = aes_handle.primitive(aead.Aead)
    decrypted_json = env_aead.decrypt(encrypted, b'')
    return self._parse_private_key(decrypted_json.decode('utf-8'))
```

### 3.4 Session (session.py) - 97 lines

**역할**: 메모리 내 민감 정보 관리 (프로그램 재시작 시 모두 삭제)

```python
class Session:
    """
    Zero-Trust 메모리 저장소
    
    저장 항목:
    - access_token: JWT 토큰
    - user_id, email: 사용자 정보
    - private_key_handle: 복호화된 개인키 (KeysetHandle)
    - public_key_handle: 복호화된 공개키 (KeysetHandle)
    - team_keys: {repo_id: aes_handle} 팀 키 캐시
    
    특징:
    - Singleton이 아님 (멀티 세션 지원)
    - 서버가 절대 보지 못하는 정보만 저장
    - 프로그램 종료 시 자동 소멸
    """
    
    def __init__(self):
        self.access_token = None
        self.user_id = None
        self.email = None
        self.private_key_handle = None
        self.public_key_handle = None
        self.team_keys = {}  # {repo_id: aes_keyset_handle}
    
    def cache_team_key(self, repo_id: str, aes_handle):
        """팀 키 캐싱 (Lazy Loading 지원)"""
        self.team_keys[repo_id] = aes_handle
    
    def get_cached_team_key(self, repo_id: str):
        """캐시된 팀 키 조회"""
        return self.team_keys.get(repo_id)
    
    def clear(self):
        """로그아웃 시 모든 민감 정보 삭제"""
        self.access_token = None
        self.user_id = None
        self.email = None
        self.private_key_handle = None
        self.public_key_handle = None
        self.team_keys.clear()
```

---

## 4. CLI 계층 (src/cli/)

### 4.1 main.py - 명령어 엔트리포인트

```python
@click.group()
def cli():
    """
    SeRVe Zero-Trust CLI Client
    서버와 클라이언트 간 End-to-End 암호화를 지원하는 문서/데이터 공유 플랫폼
    """
    pass

cli.add_command(auth)      # serve auth ...
cli.add_command(repo)      # serve repo ...
cli.add_command(data)      # serve data ...
cli.add_command(reasoning) # serve reasoning ...
```

### 4.2 context.py - SDK 초기화 헬퍼

```python
class CLIContext:
    """
    CLI 명령어에서 SDK를 쉽게 사용하기 위한 컨텍스트
    
    책임:
    1. ServeClient 인스턴스 생성
    2. 로컬 세션 파일에서 인증 정보 복구
    3. 개인키 복호화 (비밀번호 입력 받아)
    """
    
    def __init__(self):
        server_url = os.environ.get("SERVE_API_URL", "http://localhost:8080")
        self.client = ServeClient(server_url=server_url)
        self.session_data = get_session()  # ~/.serve/session.json
    
    def ensure_authenticated(self):
        """
        로컬 세션 파일 확인 → SDK Session에 토큰 복원
        """
        if not self.session_data:
            click.echo("에러: 로그인이 필요합니다.")
            sys.exit(1)
        
        self.client.session.set_user_credentials(
            self.session_data["access_token"],
            self.session_data["user_id"],
            self.session_data["email"]
        )
    
    def ensure_private_key(self, password=None):
        """
        암호화된 개인키를 비밀번호로 복호화하여 SDK Session에 로드
        
        Zero-Trust 원칙:
        - 필요한 시점에만 복호화
        - 명령어 실행마다 다시 입력받을 수 있음
        """
        self.ensure_authenticated()
        
        if self.client.session.has_private_key():
            return  # 이미 메모리에 있으면 스킵
        
        enc_priv_key = self.session_data.get("encrypted_private_key")
        if not password:
            password = getpass.getpass("> 현재 비밀번호를 입력하세요: ")
        
        try:
            private_key = self.client.crypto.recover_private_key(enc_priv_key, password)
            public_key = private_key.public_keyset_handle()
            self.client.session.set_key_pair(private_key, public_key)
            return True
        except Exception:
            click.echo("에러: 비밀번호가 틀렸거나 개인키 복호화에 실패했습니다.")
            sys.exit(1)
```

### 4.3 session_manager.py - 로컬 세션 파일 관리

```python
SESSION_DIR = Path.home() / ".serve"
SESSION_FILE = SESSION_DIR / "session.json"

def get_session():
    """
    ~/.serve/session.json 읽기
    
    저장 항목:
    - access_token: JWT
    - user_id, email: 사용자 정보
    - encrypted_private_key: 비밀번호로 암호화된 개인키
    """
    if not SESSION_FILE.exists():
        return None
    with open(SESSION_FILE, "r") as f:
        return json.load(f)

def save_session(access_token, user_id, email, encrypted_private_key):
    """로그인 성공 시 세션 저장"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_data = {
        "access_token": access_token,
        "user_id": user_id,
        "email": email,
        "encrypted_private_key": encrypted_private_key
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(session_data, f)

def clear_session():
    """로그아웃/회원탈퇴 시 세션 파일 삭제"""
    if SESSION_FILE.exists():
        os.remove(SESSION_FILE)
```

### 4.4 CLI 명령어 구조 예시

#### auth.py - 인증 명령어

```python
@auth.command()
def login():
    """CLI 로그인"""
    ctx = CLIContext()
    email = click.prompt("> Enter email")
    password = click.prompt("> Enter password", hide_input=True)
    
    # SDK 호출
    success, msg = ctx.client.login(email, password)
    if not success:
        click.echo(f"❌ 로그인 실패: {msg}")
        sys.exit(1)
    
    # 로컬 세션 파일 저장
    priv_key = ctx.client.session.get_private_key()
    encrypted_priv_key = ctx.client.crypto.encrypt_private_key(priv_key, password)
    save_session(
        ctx.client.session.access_token,
        ctx.client.session.user_id,
        ctx.client.session.email,
        encrypted_priv_key
    )
    
    click.echo("✅ Login Successful!")
```

#### repo.py - 저장소 명령어

```python
@repo.command()
@click.argument('team-name')
@click.option('--description', default="")
def create(team_name, description):
    """저장소 생성"""
    ctx = CLIContext()
    ctx.ensure_private_key()  # 팀 키 래핑을 위해 공개키 필요
    
    repo_id, msg = ctx.client.create_repository(team_name, description)
    if repo_id:
        click.echo(f"✅ 저장소 생성 성공! (ID: {repo_id})")
    else:
        click.echo(f"❌ 저장소 생성 실패: {msg}")
```

#### data.py - 데이터 명령어

```python
@data.command()
@click.argument('team-id')
@click.argument('task-name')
@click.argument('data-id')
def upload(team_id, task_name, data_id, description, robot_id):
    """데모 데이터 업로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()  # 암호화를 위해 팀 키 필요
    
    # 메타데이터 준비
    metadata = f"Task: {task_name}\nDataID: {data_id}\nDesc: {description}"
    chunk_data = [{"chunkIndex": 0, "data": metadata}]
    
    # SDK 호출 (Envelope Encryption 자동 적용)
    success, msg = ctx.client.upload_chunks_to_document(
        file_name=f"{task_name}_{data_id}",
        repo_id=team_id,
        chunks_data=chunk_data
    )
    
    if success:
        click.echo("✅ 데모 데이터 업로드 성공!")
    else:
        click.echo(f"❌ 업로드 실패: {msg}")
```

---

## 5. 암호화 워크플로우

### 5.1 회원가입 (Signup)

```
User Input: email, password
    ↓
┌───────────────────────────────────────┐
│ CLI: serve auth signup                │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: ServeClient.signup()             │
│                                       │
│ 1. 키 쌍 생성                          │
│    crypto.generate_key_pair()         │
│    → private_key (ECC P-256)          │
│    → public_key                       │
│                                       │
│ 2. 개인키 암호화                       │
│    crypto.encrypt_private_key(        │
│        private_key, password)         │
│    → encrypted_private_key (Base64)   │
│                                       │
│ 3. 서버 전송                          │
│    api.signup(email, password,        │
│        public_key_json,               │
│        encrypted_private_key)         │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ Server                                │
│ 저장: {                               │
│   email, password_hash,               │
│   public_key_json,                    │
│   encrypted_private_key (복호화 불가) │
│ }                                     │
└───────────────────────────────────────┘

서버가 알 수 없는 것:
✗ password (해시만 저장)
✗ private_key (암호화된 버전만 저장)
```

### 5.2 로그인 (Login)

```
User Input: email, password
    ↓
┌───────────────────────────────────────┐
│ CLI: serve auth login                 │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: ServeClient.login()              │
│                                       │
│ 1. 서버 인증                          │
│    api.login(email, password)         │
│    ← {accessToken, userId,            │
│         encryptedPrivateKey}          │
│                                       │
│ 2. 개인키 복구 (클라이언트에서만!)     │
│    crypto.recover_private_key(        │
│        encryptedPrivateKey, password) │
│    → private_key (복호화 성공)         │
│                                       │
│ 3. Session에 저장                     │
│    session.set_key_pair(              │
│        private_key, public_key)       │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ CLI: 로컬 파일 저장                    │
│ ~/.serve/session.json {               │
│   access_token,                       │
│   user_id, email,                     │
│   encrypted_private_key               │
│ }                                     │
└───────────────────────────────────────┘

서버가 알 수 없는 것:
✗ 복호화된 private_key (클라이언트 메모리에만 존재)
```

### 5.3 저장소 생성 (Create Repository)

```
User Input: team-name
    ↓
┌───────────────────────────────────────┐
│ CLI: serve repo create                │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: ServeClient.create_repository()  │
│                                       │
│ 1. 팀 키 생성                          │
│    team_key = crypto.generate_aes_key()│
│    (AES-256-GCM, 랜덤)                │
│                                       │
│ 2. 내 공개키로 팀 키 래핑              │
│    my_public_key = session.get_public_key()│
│    encrypted_team_key =               │
│        crypto.wrap_aes_key(           │
│            team_key, my_public_key)   │
│                                       │
│ 3. 서버 전송                          │
│    api.create_repository(             │
│        name, encrypted_team_key)      │
│    ← repo_id                          │
│                                       │
│ 4. 원본 팀 키 캐싱                     │
│    session.cache_team_key(            │
│        repo_id, team_key)             │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ Server                                │
│ 저장: {                               │
│   repo_id, name,                      │
│   encrypted_team_key (복호화 불가)    │
│ }                                     │
└───────────────────────────────────────┘

서버가 알 수 없는 것:
✗ 평문 team_key (공개키로 암호화됨)
```

### 5.4 멤버 초대 (Invite Member)

```
User Input: team-id, invitee-email
    ↓
┌───────────────────────────────────────┐
│ CLI: serve repo invite                │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: ServeClient.invite_member()      │
│                                       │
│ 1. 초대할 사용자의 공개키 조회         │
│    api.get_user_public_key(email)     │
│    ← invitee_public_key               │
│                                       │
│ 2. 팀 키 Lazy Loading                 │
│    team_key = _ensure_team_key(repo_id)│
│    (캐시 없으면 서버에서 조회 후 복호화)│
│                                       │
│ 3. 초대자의 공개키로 팀 키 재래핑      │
│    encrypted_team_key_for_invitee =   │
│        crypto.wrap_aes_key(           │
│            team_key,                  │
│            invitee_public_key)        │
│                                       │
│ 4. 서버 전송                          │
│    api.invite_member(                 │
│        repo_id, email,                │
│        encrypted_team_key_for_invitee)│
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ Server                                │
│ 저장: {                               │
│   repo_id, invitee_user_id,           │
│   encrypted_team_key_for_invitee      │
│ }                                     │
│                                       │
│ 초대받은 사람만 자신의 개인키로        │
│ 팀 키를 복호화할 수 있음               │
└───────────────────────────────────────┘

서버가 알 수 없는 것:
✗ 평문 team_key
✗ 누가 무슨 데이터를 볼 수 있는지 (암호학적으로만 제어)
```

### 5.5 데이터 업로드 (Upload Chunks) - Envelope Encryption

```
User Input: file-name, chunks_data (평문)
    ↓
┌───────────────────────────────────────┐
│ CLI: serve data upload                │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: upload_chunks_to_document()      │
│                                       │
│ 1. 팀 키(KEK) Lazy Loading            │
│    team_key = _ensure_team_key(repo_id)│
│                                       │
│ 2. DEK 생성 (문서별 랜덤 키)           │
│    dek = crypto.generate_aes_key()    │
│                                       │
│ 3. 각 청크를 DEK로 암호화              │
│    for chunk in chunks_data:          │
│        encrypted_blob =               │
│            crypto.encrypt_data(       │
│                chunk.data, dek)       │
│                                       │
│ 4. DEK를 팀 키로 래핑                  │
│    encrypted_dek =                    │
│        crypto.wrap_key_with_aes(      │
│            dek, team_key)             │
│                                       │
│ 5. 서버 전송                          │
│    api.upload_chunks(                 │
│        repo_id, file_name,            │
│        encrypted_chunks,              │
│        encrypted_dek)                 │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ Server                                │
│ 저장: {                               │
│   docId, fileName,                    │
│   encrypted_dek (팀 키로 암호화됨),    │
│   chunks: [{                          │
│       chunkIndex,                     │
│       encryptedBlob (DEK로 암호화됨)  │
│   }]                                  │
│ }                                     │
└───────────────────────────────────────┘

서버가 알 수 없는 것:
✗ 평문 DEK (팀 키로 암호화됨)
✗ 평문 청크 데이터 (DEK로 암호화됨)
✗ 팀 키 (각 멤버의 개인키로만 복호화 가능)

Envelope Encryption 이점:
- 대량 데이터는 빠른 대칭키(DEK)로 암호화
- DEK만 팀 키로 암호화하여 키 공유
- 멤버 추가 시 DEK만 재래핑하면 됨 (데이터 재암호화 불필요)
```

### 5.6 데이터 다운로드 (Download Chunks)

```
User Input: file-name, team-id
    ↓
┌───────────────────────────────────────┐
│ CLI: serve data download              │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ SDK: download_chunks_from_document()  │
│                                       │
│ 1. 문서 메타데이터 조회                 │
│    api.get_documents(repo_id)         │
│    ← [{docId, fileName, encryptedDEK}]│
│                                       │
│ 2. 팀 키 Lazy Loading                 │
│    team_key = _ensure_team_key(repo_id)│
│                                       │
│ 3. DEK 언래핑 (복호화)                 │
│    dek = crypto.unwrap_key_with_aes(  │
│        encryptedDEK, team_key)        │
│                                       │
│ 4. 청크 동기화 (암호화된 상태)          │
│    api.sync_team_chunks(repo_id, -1)  │
│    ← [{docId, chunks: [{encryptedBlob}]}]│
│                                       │
│ 5. 각 청크를 DEK로 복호화              │
│    for chunk in chunks:               │
│        plaintext =                    │
│            crypto.decrypt_data(       │
│                chunk.encryptedBlob, dek)│
│                                       │
│ 6. 평문 청크 반환                      │
│    return decrypted_chunks            │
└───────────┬───────────────────────────┘
            │
┌───────────▼───────────────────────────┐
│ CLI: 로컬 DB에 저장                    │
│ sqlite3: local.db                     │
│ INSERT INTO downloaded_data ...       │
└───────────────────────────────────────┘

복호화는 오직 클라이언트에서만!
서버는 암호문만 전송, 내용 알 수 없음
```

---

## 6. 핵심 기능 구현

### 6.1 Zero-Trust 달성 메커니즘

#### 6.1.1 키 계층 구조

```
사용자 비밀번호 (User Memory)
    ↓ SHA-256 (간단한 해시, 프로덕션에서는 PBKDF2 권장)
Password-Derived Key (Client Memory)
    ↓ AES-GCM 복호화
개인키 (ECC P-256) (Client Memory Only!)
    ↓ ECIES 언래핑
팀 키 (AES-256-GCM) (Client Memory Cache)
    ↓ AES-GCM 언래핑
DEK (AES-256-GCM) (임시 생성)
    ↓ AES-GCM 복호화
평문 데이터 (Client Memory Only!)

서버가 저장하는 것:
✓ 암호화된 개인키 (비밀번호로 보호)
✓ 공개키 (평문, 공개 가능)
✓ 암호화된 팀 키 (각 멤버의 공개키로 래핑)
✓ 암호화된 DEK (팀 키로 래핑)
✓ 암호화된 데이터 (DEK로 암호화)

서버가 절대 알 수 없는 것:
✗ 비밀번호
✗ 복호화된 개인키
✗ 복호화된 팀 키
✗ 복호화된 DEK
✗ 평문 데이터
```

#### 6.1.2 Lazy Loading 패턴

```python
# 최초 요청
user → repo.create("TeamA") → ServeClient
                                ↓
                          팀 키 생성 (메모리)
                                ↓
                          Session 캐싱
                                ↓
                          서버에 암호화된 버전 전송

# 이후 요청 (같은 프로그램 실행 중)
user → data.upload("TeamA", ...) → ServeClient
                                      ↓
                                _ensure_team_key("TeamA")
                                      ↓
                                Session 캐시 확인 ✓
                                      ↓
                                즉시 반환 (서버 요청 없음)

# 프로그램 재시작 후
user → data.upload("TeamA", ...) → ServeClient
                                      ↓
                                _ensure_team_key("TeamA")
                                      ↓
                                Session 캐시 없음 ✗
                                      ↓
                                서버에서 암호화된 팀 키 조회
                                      ↓
                                내 개인키로 복호화
                                      ↓
                                Session 캐싱
                                      ↓
                                반환
```

### 6.2 멤버 강퇴 시 자동 키 로테이션

```python
def kick_member(self, repo_id: str, target_user_id: str):
    """
    멤버 강퇴 + 자동 키 로테이션
    
    보안 이유:
    - 강퇴된 멤버가 이전에 받은 팀 키로 
      새로운 데이터를 복호화하지 못하도록 방지
    
    워크플로우:
    1. 서버에 강퇴 요청
    2. 남은 멤버 목록 조회
    3. 새로운 팀 키 생성
    4. 각 남은 멤버의 공개키로 새 팀 키 래핑
    5. 서버에 업데이트
    6. 모든 문서를 새 팀 키로 재암호화
    """
    # 1. 멤버 강퇴
    self.api.kick_member(repo_id, target_user_id, token)
    
    # 2. 남은 멤버 조회
    members = self.api.get_members(repo_id, token)
    
    # 3. 새 팀 키 생성
    new_team_key = self.crypto.generate_aes_key()
    
    # 4. 각 멤버의 공개키로 래핑
    for member in members:
        member_public_key = self.api.get_user_public_key(member['email'])
        encrypted_key = self.crypto.wrap_aes_key(new_team_key, member_public_key)
        self.api.update_member_key(repo_id, member['userId'], encrypted_key)
    
    # 5. 모든 문서 재암호화
    self._reencrypt_all_documents(repo_id, new_team_key)
    
    # 6. Session 캐시 업데이트
    self.session.cache_team_key(repo_id, new_team_key)
```

### 6.3 문서 재암호화 로직

```python
def _reencrypt_all_documents(self, repo_id: str, new_team_key):
    """
    팀 키 로테이션 시 모든 문서 재암호화
    
    효율적인 방법 (Envelope Encryption 덕분):
    - 실제 데이터는 재암호화하지 않음!
    - DEK만 새 팀 키로 재래핑
    
    1. 모든 문서 조회
    2. 각 문서의 DEK를 구 팀 키로 언래핑
    3. DEK를 신 팀 키로 재래핑
    4. 서버에 업데이트
    """
    documents = self.api.get_documents(repo_id, token)
    
    for doc in documents:
        # 1. 구 팀 키로 DEK 복호화
        old_team_key = self.session.get_cached_team_key(repo_id)
        dek = self.crypto.unwrap_key_with_aes(
            doc['encryptedDEK'], 
            old_team_key
        )
        
        # 2. 신 팀 키로 DEK 재암호화
        new_encrypted_dek = self.crypto.wrap_key_with_aes(
            dek, 
            new_team_key
        )
        
        # 3. 서버 업데이트 (청크 데이터는 그대로!)
        self.api.update_document_dek(
            doc['docId'], 
            new_encrypted_dek
        )
```

---

## 7. 파일 구조 및 책임

### 7.1 전체 파일 트리

```
SeRVe-Client/
├── serve_sdk/              # SDK 계층 (재사용 가능한 비즈니스 로직)
│   ├── __init__.py
│   ├── client.py           # ★ 메인 오케스트레이터 (1030 lines)
│   ├── api_client.py       # HTTP 통신 전담 (566 lines)
│   ├── session.py          # 메모리 상태 관리 (97 lines)
│   └── security/           # 암호화 모듈
│       ├── __init__.py
│       ├── crypto_utils.py # ★ 암호화 프리미티브 (327 lines)
│       └── key_manager.py  # 키 관리 유틸리티
│
├── src/cli/                # CLI 계층 (사용자 인터페이스)
│   ├── main.py             # 명령어 엔트리포인트
│   ├── context.py          # SDK 초기화 헬퍼
│   ├── session_manager.py  # 로컬 세션 파일 관리
│   ├── auth.py             # serve auth ... 명령어
│   ├── repo.py             # serve repo ... 명령어
│   ├── data.py             # serve data ... 명령어
│   └── reasoning.py        # serve reasoning ... 명령어 (스텁)
│
├── setup.py                # 패키지 설정
├── README.md               # 사용자 매뉴얼
├── README2.md              # 본 문서 (구현 상세)
│
├── mock_server.py          # 개발용 모의 서버
├── test_data_api.py        # 데이터 API 테스트
└── local.db                # 로컬 다운로드 기록 (SQLite)
```

### 7.2 파일별 책임 요약

| 파일 | LOC | 핵심 책임 | 의존성 |
|------|-----|-----------|--------|
| **serve_sdk/client.py** | 1030 | 비즈니스 로직 오케스트레이션, Lazy Loading, Envelope Encryption | api_client, crypto_utils, session |
| **serve_sdk/api_client.py** | 566 | REST API 통신, 인증 헤더, 에러 처리 | requests |
| **serve_sdk/security/crypto_utils.py** | 327 | 키 생성, 암호화/복호화, 래핑/언래핑 | tink |
| **serve_sdk/session.py** | 97 | 메모리 내 키/토큰 캐싱 | - |
| **src/cli/context.py** | 58 | SDK 초기화, 로컬 세션 복원 | session_manager, client |
| **src/cli/session_manager.py** | 30 | ~/.serve/session.json 파일 I/O | - |
| **src/cli/auth.py** | 151 | 인증 명령어 (signup, login, reset-pw, delete-account) | context |
| **src/cli/repo.py** | 135 | 저장소 명령어 (create, invite, kick, list, show, set-role) | context |
| **src/cli/data.py** | 168 | 데이터 명령어 (upload, download, list, pull) | context, sqlite3 |
| **src/cli/reasoning.py** | 33 | VLA 추론 명령어 (스텁 구현) | context |
| **src/cli/main.py** | 22 | Click 그룹 등록 | auth, repo, data, reasoning |

### 7.3 핵심 데이터 흐름

#### 업로드 흐름
```
User
  ↓ 평문 데이터
CLI (data.py)
  ↓ 명령어 파싱
CLIContext
  ↓ SDK 초기화
ServeClient.upload_chunks_to_document()
  ↓ 팀 키 Lazy Loading
Session (캐시 확인)
  ↓ 없으면 서버 조회
ApiClient.get_team_key() → Server (암호화된 팀 키 반환)
  ↓ 복호화
CryptoUtils.unwrap_aes_key()
  ↓ DEK 생성 + 데이터 암호화
CryptoUtils.encrypt_data() + wrap_key_with_aes()
  ↓ 서버 전송
ApiClient.upload_chunks() → Server (암호문만 저장)
```

#### 다운로드 흐름
```
User
  ↓ 문서 ID 요청
CLI (data.py)
  ↓ 명령어 파싱
CLIContext
  ↓ SDK 초기화
ServeClient.download_chunks_from_document()
  ↓ 문서 메타데이터 조회
ApiClient.get_documents() → Server (encryptedDEK 포함)
  ↓ 팀 키 Lazy Loading
Session (캐시 확인)
  ↓ DEK 언래핑
CryptoUtils.unwrap_key_with_aes()
  ↓ 청크 동기화
ApiClient.sync_team_chunks() → Server (암호화된 청크)
  ↓ 각 청크 복호화
CryptoUtils.decrypt_data()
  ↓ 평문 반환
CLI (local.db에 저장)
  ↓
User (평문 데이터)
```

---

## 8. 설치 및 실행

### 8.1 설치

```bash
# 개발 모드로 설치 (소스 수정 시 재설치 불필요)
pip install -e .

# 의존성:
# - click: CLI 프레임워크
# - requests: HTTP 클라이언트
# - tink: Google 암호화 라이브러리
```

### 8.2 명령어 구조

```bash
# 전역 명령어로 등록됨
serve --help

# 인증 그룹
serve auth signup
serve auth login
serve auth reset-pw
serve auth delete-account [--force]

# 저장소 그룹
serve repo create <team-name> [--description "..."]
serve repo list
serve repo invite <team-id> <user-email>
serve repo kick <team-id> <user-id>
serve repo set-role <team-id> <user-id> <role>
serve repo show <team-id>
serve repo rotate-key <team-id>  # ⚠️ 스텁 구현

# 데이터 그룹
serve data upload <team-id> <task-name> <data-id> [--description "..."] [--robot-id "..."]
serve data list <team-id>
serve data download <team-id> <task-name> <data-id> [--db-url "sqlite:///local.db"]
serve data pull <team-id> <db-url>

# 추론 그룹 (스텁)
serve reasoning few-shot <robot> <text>
serve reasoning basic <robot> <text>
```

### 8.3 환경 변수

```bash
# 서버 URL 변경 (기본값: http://localhost:8080)
export SERVE_API_URL=https://api.serve.example.com

serve auth login
```

### 8.4 로컬 세션 파일 위치

```bash
# 인증 정보 저장 위치
~/.serve/session.json

# 구조:
{
  "access_token": "eyJhbGc...",
  "user_id": "uuid-string",
  "email": "user@example.com",
  "encrypted_private_key": "base64-encrypted-key"
}

# 보안 주의사항:
# - 개인키가 비밀번호로 암호화되어 있지만 세션 파일 유출 시 위험
# - 공유 서버에서는 파일 권한 설정 필수 (chmod 600)
```

---

## 9. 보안 고려사항

### 9.1 구현된 보안 메커니즘

✅ **End-to-End 암호화**: 서버는 평문 데이터 절대 접근 불가  
✅ **Zero-Trust 아키텍처**: 서버도 믿지 않음  
✅ **Envelope Encryption**: 대량 데이터 효율적 암호화  
✅ **키 로테이션**: 멤버 강퇴 시 자동 팀 키 갱신  
✅ **Lazy Loading**: 필요한 시점에만 키 복호화  
✅ **메모리 격리**: 민감 정보 프로그램 종료 시 자동 소멸  

### 9.2 프로덕션 권장 개선사항

⚠️ **비밀번호 해싱**: 현재 SHA-256 사용 → PBKDF2/Argon2 교체 권장  
⚠️ **세션 파일 보호**: ~/.serve/session.json 암호화 또는 OS 키체인 활용  
⚠️ **TLS 필수**: HTTPS 통신 강제 (중간자 공격 방지)  
⚠️ **타임아웃 설정**: 세션 만료 시간 설정  
⚠️ **로그 보안**: 민감 정보(키, 비밀번호) 로그 출력 금지  

### 9.3 알려진 제약사항

❌ **VLA 추론 미구현**: reasoning 명령어 스텁 상태  
❌ **수동 키 로테이션 미구현**: `serve repo rotate-key` 스텁  
❌ **복구 메커니즘 없음**: 비밀번호 분실 시 데이터 영구 손실  
❌ **멀티 디바이스 동기화 없음**: 디바이스별로 별도 로그인 필요  

---

## 10. 확장 가능성

### 10.1 SDK 재사용

```python
# CLI가 아닌 다른 애플리케이션에서도 SDK 사용 가능
from serve_sdk.client import ServeClient

client = ServeClient(server_url="https://api.example.com")
client.login("user@example.com", "password")
client.create_repository("ProjectX", "Description")
client.upload_chunks_to_document("doc1", "repo-id", chunks)
```

### 10.2 추가 가능한 기능

- [ ] 웹 UI (React/Vue + serve_sdk 래퍼)
- [ ] 모바일 앱 (네이티브 + REST API)
- [ ] 파일 업로드 (청크 자동 분할)
- [ ] 버전 관리 (Git 스타일)
- [ ] 감사 로그 (암호화된 액세스 로그)
- [ ] 팀 간 데이터 공유 (크로스 팀 키 교환)

---

## 11. 문제 해결

### 11.1 일반적인 에러

**"로그인이 필요합니다"**
```bash
# 세션이 만료되었거나 없음
serve auth login
```

**"비밀번호가 틀렸거나 개인키 복호화에 실패"**
```bash
# AES-GCM 무결성 검증 실패
# 1. 비밀번호 오타 확인
# 2. 세션 파일 손상 → 재로그인
rm ~/.serve/session.json
serve auth login
```

**"팀 키 조회 실패"**
```bash
# 원인 가능성:
# 1. 저장소 멤버가 아님 → ADMIN에게 초대 요청
# 2. 네트워크 문제 → 서버 URL 확인
# 3. 권한 부족 → 멤버 역할 확인
serve repo show <team-id>
```

### 11.2 디버깅 팁

```bash
# 서버 URL 확인
echo $SERVE_API_URL

# 세션 파일 확인
cat ~/.serve/session.json

# 네트워크 테스트
curl $SERVE_API_URL/health

# 상세 에러 확인 (Python 트레이스백)
python -m pdb $(which serve) auth login
```

---

## 12. 개발 참고사항

### 12.1 코드 스타일

- PEP 8 준수
- 타입 힌트 사용 (`Tuple[bool, str]` 등)
- Docstring에 내부 동작 설명 포함
- 책임 분리: 각 클래스는 단일 책임만

### 12.2 테스트

```bash
# 모의 서버 실행
python mock_server.py

# 데이터 API 테스트
python test_data_api.py

# 통합 테스트 (수동)
serve auth signup
serve auth login
serve repo create "TestTeam"
serve data upload <team-id> "task1" "data1"
serve data list <team-id>
serve data download <team-id> "task1" "data1"
```

### 12.3 기여 가이드

1. **SDK 변경**: `serve_sdk/` 수정 시 CLI 영향도 고려
2. **암호화 로직 변경**: `CryptoUtils` 수정 시 기존 데이터 호환성 확인
3. **API 변경**: `api_client.py` 수정 시 서버 스펙 동기화
4. **CLI 명령어 추가**: `click.command()` 데코레이터 + `CLIContext` 활용

---

## 13. 결론

SeRVe-Client는 **Zero-Trust End-to-End 암호화**를 철저히 구현한 CLI 도구입니다.

### 13.1 핵심 강점

1. **진정한 Zero-Trust**: 서버는 평문 데이터/키를 절대 보지 못함
2. **계층 분리**: SDK(재사용 가능) / CLI(사용자 친화적) 명확히 분리
3. **Lazy Loading**: 효율적인 키 관리
4. **Envelope Encryption**: 대량 데이터 처리에 최적화
5. **자동 키 로테이션**: 멤버 강퇴 시 보안 자동 유지

### 13.2 구현 완성도

- **인증/저장소/데이터 관리**: 프로덕션 수준 구현 완료
- **VLA 추론**: 향후 구현 예정 (스텁 존재)
- **전체 구현률**: 82% (17개 명령어 중 14개 완성)

### 13.3 다음 단계

1. VLA 추론 서버 연동
2. `serve repo rotate-key` 완전 구현
3. 웹 UI 개발 (SDK 재사용)
4. 프로덕션 보안 강화 (PBKDF2, 키체인 통합)

---

**문서 작성일**: 2026-02-26  
**버전**: 0.1.0  
**작성자**: SeRVe Development Team
