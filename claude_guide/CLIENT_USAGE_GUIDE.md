# SeRVe Client 사용 가이드

SeRVe 서버의 모든 API 기능을 활용하는 클라이언트 구현 가이드입니다.

## 구현된 기능

### 1. 인증 관련 (Authentication)
- **회원가입** (`signup`)
- **로그인** (`login`)
- **로그아웃** (`logout`)
- **비밀번호 재설정** (`reset_password`)
- **회원 탈퇴** (`withdraw`)

### 2. 보안 관련 (Security)
- **핸드셰이크** (`perform_handshake`) - AES 키 교환

### 3. 저장소 관리 (Repository)
- **저장소 생성** (`create_repository`)
- **저장소 목록 조회** (`get_my_repositories`)
- **팀 키 조회** (`get_team_key`)
- **저장소 삭제** (`delete_repository`)

### 4. 문서 관리 (Document)
- **문서 업로드** (`upload_secure_document`) - 암호화 후 업로드
- **문서 다운로드** (`get_secure_document`) - 다운로드 후 복호화

### 5. 멤버 관리 (Member)
- **멤버 초대** (`invite_member`)
- **멤버 목록 조회** (`get_members`)
- **멤버 강퇴** (`kick_member`)
- **권한 변경** (`update_member_role`)

## 서버 API 엔드포인트

### 인증 (AuthController)
```
POST   /auth/signup           - 회원가입
POST   /auth/login            - 로그인
POST   /auth/reset-password   - 비밀번호 재설정
DELETE /auth/me               - 회원 탈퇴
```

### 보안 (SecurityController)
```
POST   /api/security/handshake - 핸드셰이크 (AES 키 교환)
```

### 저장소 (RepoController)
```
POST   /api/repositories                    - 저장소 생성
GET    /api/repositories?userId={userId}    - 저장소 목록 조회
GET    /api/repositories/{repoId}/keys?userId={userId} - 팀 키 조회
DELETE /api/repositories/{repoId}?userId={userId}      - 저장소 삭제
```

### 문서 (DocumentController)
```
POST   /api/documents              - 문서 업로드
GET    /api/documents/{documentId} - 문서 다운로드
```

### 멤버 (MemberController)
```
POST   /repositories/{repoId}/members                              - 멤버 초대
GET    /repositories/{repoId}/members                              - 멤버 목록 조회
DELETE /repositories/{repoId}/members/{userId}?adminId={adminId}  - 멤버 강퇴
PUT    /repositories/{repoId}/members/{userId}?adminId={adminId}  - 권한 변경
```

## 사용 방법

### 1. Streamlit UI 실행

```bash
cd SeRVe-Client
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

**서버 연결 없이 실행 가능**: 클라이언트는 서버 연결 없이도 실행됩니다. 처음 실행하면 서버 연결 화면이 나타납니다.

#### 서버 연결 모드
1. **정상 모드**: 서버 URL을 입력하고 '서버 연결' 버튼 클릭
   - 서버가 실행 중이면 자동으로 연결됩니다
   - 모든 기능을 사용할 수 있습니다

2. **데모 모드**: 서버 연결 없이 실행
   - '서버 연결 없이 데모 모드로 실행' 체크박스 선택
   - UI는 정상적으로 동작하지만 서버 통신이 필요한 기능은 오류가 발생합니다

### 2. 프로그래밍 방식 사용

```python
from serve_connector import ServeConnector

# 커넥터 생성
conn = ServeConnector()

# 1. 회원가입
success, msg = conn.signup(
    email="user@example.com",
    password="password123",
    public_key="demo_public_key",
    encrypted_private_key="demo_encrypted_private_key"
)

# 2. 로그인
success, msg = conn.login("user@example.com", "password123")

# 3. 저장소 생성
repo_id, msg = conn.create_repository(
    name="My Repository",
    description="Test repository",
    encrypted_team_key="demo_team_key"
)

# 4. 핸드셰이크
success, msg = conn.perform_handshake()

# 5. 문서 업로드
doc_id, msg = conn.upload_secure_document(
    plaintext="Confidential data",
    repo_id=repo_id
)

# 6. 문서 다운로드
content, msg = conn.get_secure_document(doc_id)

# 7. 로그아웃
success, msg = conn.logout()
```

## 테스트 실행

각 기능별 테스트 파일이 제공됩니다:

### 개별 테스트 실행

```bash
# 인증 테스트
python test_auth.py

# 저장소 테스트
python test_repository.py

# 문서 테스트
python test_document.py

# 멤버 테스트
python test_member.py

# 통합 테스트
python test_integration.py
```

### pytest로 모든 테스트 실행

```bash
# pytest 설치
pip install pytest

# 모든 테스트 실행
pytest test_*.py -v

# 특정 테스트만 실행
pytest test_auth.py -v
```

## Streamlit UI 구조

### 서버 연결 화면 (처음 실행 시)
- 서버 URL 입력
- 서버 연결 버튼
- 데모 모드 옵션

### 로그인 전
- **사이드바**: 서버 연결 상태 표시, 서버 변경 버튼
- 로그인 탭
- 회원가입 탭

### 로그인 후
- **사이드바**
  - 서버 연결 상태 (URL 표시)
  - 서버 연결 변경 버튼
  - 사용자 정보 (이메일, User ID)
  - 로그아웃 버튼
  - 보안 핸드셰이크 버튼
  - Virtual Camera (이미지 선택)

- **메인 탭**
  1. **저장소 관리**
     - 저장소 목록 조회
     - 저장소 생성
     - 저장소 선택
     - 저장소 삭제

  2. **문서 관리**
     - 문서 업로드 (암호화)
     - 문서 다운로드 (복호화)

  3. **멤버 관리**
     - 멤버 목록 조회
     - 멤버 초대
     - 멤버 강퇴
     - 권한 변경

  4. **Vision AI 분석**
     - 일반 추론 (컨텍스트 없음)
     - 보안 RAG 추론 (SeRVe 연동)

## 주요 워크플로우

### 기본 사용 흐름
1. 회원가입 → 로그인
2. 저장소 생성
3. 핸드셰이크 (AES 키 교환)
4. 문서 업로드/다운로드

### 팀 협업 흐름
1. 관리자: 회원가입 → 로그인 → 저장소 생성
2. 멤버들: 회원가입
3. 관리자: 멤버 초대
4. 멤버들: 로그인 → 저장소 접근
5. 모두: 문서 업로드/다운로드

### Vision AI 분석 흐름
1. 로그인 → 저장소 선택
2. 핸드셰이크
3. 보안 컨텍스트 업로드 (문서)
4. 이미지 선택
5. 보안 RAG 추론 실행

## 설정 파일

`config.py`:
```python
SERVER_URL = "http://localhost:8080"
ROBOT_ID = "agv-robot-01"
```

**주의**: 서버 URL은 UI에서 동적으로 변경할 수 있으므로, `config.py`는 기본값으로만 사용됩니다.
- UI에서 입력한 서버 URL이 우선순위를 가집니다
- 서버 연결 화면에서 언제든지 서버 주소를 변경할 수 있습니다

## 주의사항

1. **서버 연결**:
   - 서버 없이도 클라이언트는 실행됩니다
   - 실제 기능을 사용하려면 SeRVe 서버가 실행 중이어야 합니다
   - 서버 연결 상태는 UI 상단에 표시됩니다

2. **API 경로**:
   - 보안 API: `/api/security/*`
   - 저장소 API: `/api/repositories/*`
   - 문서 API: `/api/documents/*`
   - 멤버 API: `/repositories/*` (api prefix 없음)
   - 인증 API: `/auth/*`

3. **데모 키**: 현재 구현은 데모용 임시 키를 사용합니다. 실제 환경에서는 적절한 암호화 키 관리가 필요합니다.

4. **핸드셰이크 필수**: 문서 업로드/다운로드 전에 반드시 핸드셰이크를 수행해야 합니다.

5. **로그인 필수**: 인증이 필요한 API는 로그인 후 Authorization 헤더에 토큰을 포함하여 요청합니다.

## 파일 구조

```
SeRVe-Client/
├── app.py                    # Streamlit UI 메인 앱
├── serve_connector.py        # 서버 API 클라이언트
├── vision_engine.py          # Vision AI 엔진 (Ollama)
├── config.py                 # 설정 파일
├── security/
│   └── crypto_manager.py     # 암호화 관리
├── test_auth.py              # 인증 테스트
├── test_repository.py        # 저장소 테스트
├── test_document.py          # 문서 테스트
├── test_member.py            # 멤버 테스트
├── test_integration.py       # 통합 테스트
└── CLIENT_USAGE_GUIDE.md     # 이 파일
```

## 문제 해결

### 연결 오류
- 서버가 실행 중인지 확인
- `config.py`의 `SERVER_URL`이 올바른지 확인

### 핸드셰이크 실패
- 서버의 보안 모듈이 활성화되어 있는지 확인
- 클라이언트와 서버의 암호화 라이브러리 버전 일치 확인

### 로그인 실패
- 이메일/비밀번호 확인
- 서버의 인증 모듈이 구현되어 있는지 확인

## 참고

- 서버 저장소: `SeRVe/`
- 클라이언트 저장소: `SeRVe-Client/`
- 서버 브랜치: `repo-member` (모든 기능 포함)
