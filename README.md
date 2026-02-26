# SeRVe CLI 

SeRVe (Secure Robotics Validation environment) CLI는 **End-to-End 암호화(Zero-Trust)** 기반으로 설계된 문서 및 데모 데이터 공유 플랫폼의 콘솔 인터페이스입니다.
모든 데이터는 암호화되어 서버로 전송되며, 서버조차 원본 데이터를 확인할 수 없습니다.

## 🚀 설치 방법

프로젝트 디렉토리에서 아래 명령어를 실행하여 전역 CLI 명령어로 등록합니다.

```bash
pip install -e .
```

정상적으로 설치되었다면 터미널에서 `serve --help` 를 입력하여 전체 명령어 목록을 확인할 수 있습니다.

---

## 🛠 주요 기능 및 명령어 명세

### 1. 사용자 및 인증 (`auth`)

모든 암호화 키 생성 및 관리는 이 그룹에서 시작됩니다.

* **회원가입**: 새로운 암호화 키 쌍(ECC P-256)을 생성하고, 개인키를 비밀번호로 보호하여 서버에 등록합니다.
  ```bash
  serve auth signup
  ```
* **로그인**: 서버에 인증하고, 암호화된 개인키를 내려받아 메모리 세션에서 복호화합니다. CLI의 특성상 세션은 로컬 파일(`.serve/session.json`)에 임시 보관됩니다.
  ```bash
  serve auth login
  ```
* **비밀번호 재설정**: 현재 비밀번호로 개인키를 복호화한 후 새로운 비밀번호로 재암호화하여 서버에 업로드합니다.
  ```bash
  serve auth reset-pw
  ```
* **회원 탈퇴**: 로컬 인증 정보를 파기하고 서버에서 모든 계정 정보와 암호화 키를 영구 삭제합니다.
  ```bash
  serve auth delete-account [--force]
  ```

---

### 2. 저장소 관리 (`repo`)

팀 키(KEK, AES-GCM)를 사용하여 멤버 간 안전하게 데이터를 공유할 수 있는 워크스페이스를 관리합니다.

* **저장소 생성**: 새로운 팀 키를 발급하고 소유자의 공개키로 암호화하여 저장소를 생성합니다.
  ```bash
  serve repo create <team-name> [--description "설명"]
  ```
* **저장소 목록 조회**: 본인이 속한 모든 저장소의 목록, ID, 역할 등을 확인합니다.
  ```bash
  serve repo list
  ```
* **멤버 초대**: 초대받은 멤버의 공개키를 서버에서 조회하여, 팀 키를 해당 공개키로 래핑해 멤버에게 전달합니다.
  ```bash
  serve repo invite <team-id> <user-email>
  ```
* **멤버 강퇴**: 특정 유저를 팀에서 제거합니다 (내부적으로 남은 멤버들을 위해 팀 키를 재생성하는 로테이션 작업이 일어날 수 있습니다).
  ```bash
  serve repo kick <team-id> <user-email>
  ```
* **권한 변경**: 특정 멤버의 권한(MEMBER, ADMIN 등)을 변경합니다.
  ```bash
  serve repo set-role <team-id> <user-email> <role>
  ```
* **저장소 상세 조회**: 특정 팀의 메타데이터와 소속된 멤버 리스트를 조회합니다.
  ```bash
  serve repo show <team-id>
  ```
* **팀 키 로테이션**: 보안을 위해 팀 키를 수동으로 새로고침합니다.
  ```bash
  serve repo rotate-key <team-id>
  ```

---

### 3. 데모 데이터 관리 (`data`)

실제 콘텐츠(벡터 청크 등)를 데이터 암호화 키(DEK)로 암호화하여 팀 내에서만 복호화할 수 있도록 관리합니다.

* **데모 데이터 업로드**:
  ```bash
  serve data upload <team-id> <task-name> <data-id> [--description "..."] [--robot-id "..."]
  ```
* **목록 조회**:
  ```bash
  serve data list <team-id>
  ```
* **데모 데이터 다운로드**: 서버에서 암호화된 데이터를 내려받고, 세션의 팀 키로 복호화하여 저장합니다.
  ```bash
  serve data download <team-id> <task-name> <data-id> [--db-url "sqlite:///로컬/DB/파일.db"]
  ```
* **데모 데이터 동기화**:
  ```bash
  serve data pull <team-id> <db-url>
  ```

---

### 4. VLA 추론 (`reasoning`)

기존 데모 동영상을 기반으로 VLA 모델 추론 명령을 내립니다.

* **Few-Shot 추론**:
  ```bash
  serve reasoning few-shot <robot> <text>
  ```
* **Basic 추론**:
  ```bash
  serve reasoning basic <robot> <text>
  ```
