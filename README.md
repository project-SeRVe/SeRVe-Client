# SeRVe-Client

> **Secure Robotics Validation environment**  
> Zero-Trust E2E 암호화 기반 로봇 학습 데이터 관리 및 RAG 기반 VLA 추론 플랫폼

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## 개요

SeRVe-Client는 로봇 학습 데이터의 **수집부터 추론까지** 전체 생명주기를 Zero-Trust 암호화로 관리하는 CLI 플랫폼입니다.

### 핵심 특징

| 특징 | 설명 |
|------|------|
| 🔒 **Zero-Trust 암호화** | 서버는 평문 데이터를 절대 볼 수 없음 (ECC P-256 + AES-256-GCM) |
| 🤖 **End-to-End 파이프라인** | 로봇 로그 → 전처리 → 검증 → 업로드 → 벡터 DB → VLA 추론 |
| 🎯 **RAG 기반 추론** | Few-Shot Learning - 유사 데모 검색 후 VLA 모델에 컨텍스트 제공 |
| 👥 **팀 협업** | 팀 단위 데이터 공유, 멤버 초대/강퇴, 자동 키 로테이션 |
| 📦 **시나리오 관리** | 같은 태스크의 여러 데모를 묶어서 업로드/다운로드 |

---

## 설치

### 요구사항

- **Python 3.8+**
- **CUDA** (선택, DINOv2 GPU 가속용)

### 설치 명령어

```bash
# 저장소 클론
git clone https://github.com/project-SeRVe/SeRVe-Client.git
cd SeRVe-Client

# 개발 모드 설치
pip install -e .

# 설치 확인
serve --help
```

**주요 의존성**: click, requests, tink (Google 암호화), numpy, h5py, Pillow, torch, torchvision

---

## 빠른 시작

### 1️⃣ 사용자 인증

```bash
# 회원가입 (ECC P-256 키 쌍 자동 생성)
serve auth signup

# 로그인
serve auth login
```

### 2️⃣ 팀 생성

```bash
# 저장소(팀) 생성
serve repo create my-robot-team --description "Franka pick-and-place demos"

# 팀 멤버 초대
serve repo invite <team-id> colleague@example.com

# 저장소 목록 조회
serve repo list
```

### 3️⃣ 데이터 전처리

```bash
# 디렉토리 구조:
# raw-demos/
#   ├── demo_0/
#   │   ├── traj.h5
#   │   └── recordings/frames/hand_camera/*.jpg
#   │                        /varied_camera_1/*.jpg
#   └── demo_1/...

# H5 → NPZ 변환 + DINOv2 임베딩
serve data preprocess ./raw-demos --prompt "pick up red cube"
```

### 4️⃣ 검증 및 업로드

```bash
# NPZ 포맷 검증
serve data validate ./raw-demos

# 수동 리뷰 (O/X)
serve data review --pending-root ./raw-demos

# 시나리오 단위 암호화 업로드
serve data upload-scenario <team-id> pick_cube ~/.serve/approved/<team-id>/pick_cube
```

### 5️⃣ 벡터 DB 구축 및 추론

```bash
# 로컬 벡터 DB 빌드
serve data build-index <team-id> --write-faiss

# Few-Shot 추론 (RAG)
serve reasoning few-shot <team-id> franka "pick up the red cube" --k 5
```

---

## 워크플로우

### 📤 데이터 업로드 워크플로우

```
로봇 데이터 수집
    ↓
전처리 (preprocess)
    ↓ NPZ + DINOv2 임베딩
검증 (validate)
    ↓ 포맷 체크
수동 리뷰 (review)
    ↓ O/X 승인
시나리오 업로드 (upload-scenario)
    ↓ Envelope Encryption (시나리오 단위 DEK 공유)
서버 저장 (암호화 상태)
```

**핵심**: 같은 시나리오의 모든 에피소드는 **하나의 DEK를 공유**하여 효율적으로 관리됩니다.

### 📥 데이터 다운로드 워크플로우

```bash
# 시나리오 단위 다운로드
serve data download-scenario <team-id> <scenario-name> --output-dir ./downloads

# 전체 동기화
serve data pull <team-id> sqlite:///local.db
```

### 🤖 추론 워크플로우

```
로컬 벡터 DB 구축
    ↓
사용자 쿼리 입력
    ↓
유사 데모 검색 (FAISS L2)
    ↓
Few-Shot 컨텍스트 생성
    ↓
VLA 모델 추론 (TODO)
    ↓
액션 예측
```

---

## 명령어 레퍼런스

### 🔐 인증 & 저장소 관리

| 명령어 | 설명 |
|--------|------|
| `serve auth signup` | 회원가입 (키 쌍 생성) |
| `serve auth login` | 로그인 |
| `serve auth reset-pw` | 비밀번호 재설정 |
| `serve repo create <name>` | 저장소 생성 |
| `serve repo invite <team-id> <email>` | 멤버 초대 |
| `serve repo kick <team-id> <user-id>` | 멤버 강퇴 (자동 키 로테이션) |
| `serve repo list` | 저장소 목록 |
| `serve repo show <team-id>` | 저장소 상세 (멤버 리스트) |

### 📦 데이터 파이프라인

#### 전처리

| 명령어 | 설명 |
|--------|------|
| `serve data preprocess <dir> --prompt <text>` | H5 → NPZ 변환 + DINOv2 임베딩 |
| `serve data validate <dir>` | NPZ 포맷 검증 |
| `serve data review --pending-root <dir>` | 인터랙티브 O/X 리뷰 |

**전처리 옵션**:
```bash
serve data preprocess <input> \
    --prompt "task description" \
    --wrist-camera hand_camera \
    --base-camera varied_camera_1 \
    --rotate-180 \
    --placeholder-embeddings \  # GPU 없이 테스트
    --recursive \                # 하위 디렉토리 모두 처리
    --overwrite
```

#### 업로드/다운로드

| 명령어 | 설명 |
|--------|------|
| `serve data upload-scenario <team-id> <name> <dir>` | 시나리오 단위 업로드 (DEK 공유) |
| `serve data download-scenario <team-id> <name>` | 시나리오 단위 다운로드 |
| `serve data upload <team-id> <task> <data-id>` | 단일 데모 업로드 |
| `serve data download <team-id> <task> <data-id>` | 단일 데모 다운로드 |
| `serve data pull <team-id> <db-path>` | 전체 동기화 |
| `serve data list <team-id>` | 데모 목록 조회 |

#### 벡터 DB

| 명령어 | 설명 |
|--------|------|
| `serve data build-index <team-id> --write-faiss` | 벡터 DB 구축 |
| `serve reasoning db-info <team-id>` | 벡터 DB 통계 |

### 🎯 추론

| 명령어 | 설명 |
|--------|------|
| `serve reasoning few-shot <team-id> <robot> <prompt> --k 5` | RAG 기반 Few-Shot 추론 |
| `serve reasoning basic <robot> <prompt>` | 모델 단독 추론 |

---

## 아키텍처

### 시스템 구조

```
┌─────────────────────────────────────────────────────┐
│                  SeRVe-Client                       │
│         (Zero-Trust + Robot Learning Data)          │
└──────────────┬─────────────────┬────────────────────┘
               │                 │
    ┌──────────▼───────┐  ┌──────▼────────┐
    │  Data Pipeline   │  │   Inference   │
    │  (Robot→Server)  │  │  (Local RAG)  │
    └──────────────────┘  └───────────────┘
```

### 계층 구조

| 계층 | 위치 | 책임 |
|------|------|------|
| **CLI** | `src/cli/` | 사용자 인터페이스 |
| **SDK** | `serve_sdk/` | 비즈니스 로직, 암호화 워크플로우 |
| **Crypto** | `serve_sdk/security/` | Google Tink 래퍼 (ECC P-256, AES-256-GCM) |
| **API** | `serve_sdk/api_client.py` | HTTP 통신 |
| **Session** | `serve_sdk/session.py` | 메모리 내 키/토큰 관리 |

### 데이터 포맷

**NPZ 파일 구조** (Canonical Format):
```python
{
    'state': np.ndarray,         # (T, 8) - Joint pos + gripper
    'actions': np.ndarray,       # (T, 7) - Joint vel + gripper
    'base_image': np.ndarray,    # (T, 224, 224, 3) - RGB
    'wrist_image': np.ndarray,   # (T, 224, 224, 3) - RGB
    'base_image_embeddings': np.ndarray,   # (T, 49152) - DINOv2
    'wrist_image_embeddings': np.ndarray,  # (T, 49152) - DINOv2
    'prompt': str                # Task description
}
```

**DINOv2 임베딩 타입** (`src/cli/dinov2_utils.py`의 `EMBEDDING_TYPE` 상수):

| 타입 | 차원 | 설명 |
|------|------|------|
| `64PATCHES` (기본) | 49,152D | 64 spatial regions × 768D (상세) |
| `CLS` | 768D | [CLS] token만 (압축) |
| `AVG` | 768D | 패치 평균 (압축) |
| `16PATCHES` | 12,288D | 16 regions × 768D (중간) |

> 자세한 전처리 가이드: [`docs/PREPROCESS.md`](docs/PREPROCESS.md)

---

## 보안 모델

### Zero-Trust 원칙

**서버는 평문 데이터와 복호화 키를 절대 보지 못합니다.**

#### 키 계층 구조

```
사용자 비밀번호 (User Memory)
    ↓ SHA-256
Password-Derived Key (Client Memory)
    ↓ AES-GCM 복호화
개인키 (ECC P-256) (Client Memory Only!)
    ↓ ECIES 언래핑
팀 키 (AES-256-GCM) (Client Memory Cache)
    ↓ AES-GCM 언래핑
DEK (Data Encryption Key) (임시 생성)
    ↓ AES-GCM 복호화
평문 데이터 (Client Memory Only!)
```

#### 서버가 알 수 있는 것 vs 알 수 없는 것

| 서버가 저장하는 것 | 서버가 절대 모르는 것 |
|-------------------|---------------------|
| ✅ 암호화된 개인키 (비밀번호로 보호) | ❌ 비밀번호 |
| ✅ 공개키 (평문) | ❌ 복호화된 개인키 |
| ✅ 암호화된 팀 키 (공개키로 래핑) | ❌ 복호화된 팀 키 |
| ✅ 암호화된 DEK (팀 키로 래핑) | ❌ 복호화된 DEK |
| ✅ 암호화된 데이터 | ❌ 평문 데이터 (궤적, 이미지) |

### Envelope Encryption (봉투 암호화)

**업로드 시**:
1. DEK 생성 (AES-256-GCM)
   - **시나리오 단위**: 하나의 DEK를 모든 에피소드가 공유
   - **단일 데모**: 에피소드마다 개별 DEK 생성
2. 데이터를 DEK로 암호화
3. DEK를 팀 키(KEK)로 래핑
4. 서버에 전송: `{encryptedData, encryptedDEK}`

**다운로드 시**:
1. 팀 키로 DEK 언래핑
2. DEK로 데이터 복호화
3. 평문 반환

**장점**:
- 대량 데이터를 빠른 대칭키(DEK)로 암호화
- 멤버 추가 시 DEK만 재래핑 (데이터 재암호화 불필요)
- 시나리오 단위 업로드 시 키 관리 효율화

### Lazy Loading

```python
# 팀 키 필요 시점에만 서버에서 가져옴
def _ensure_team_key(repo_id):
    if cached := session.get_cached_team_key(repo_id):
        return cached  # 캐시 히트
    
    encrypted_key = api.get_team_key(repo_id, user_id, token)
    team_key = crypto.unwrap_aes_key(encrypted_key, private_key)
    session.cache_team_key(repo_id, team_key)  # 메모리 캐싱
    return team_key
```

→ 같은 프로그램 실행 중에는 네트워크 요청 없이 캐시 사용

### 멤버 강퇴 시 자동 키 로테이션

1. 서버에 강퇴 요청
2. 새로운 팀 키 생성
3. 남은 멤버들의 공개키로 새 팀 키 재래핑
4. 모든 DEK를 새 팀 키로 재래핑 (데이터 자체는 재암호화 불필요)
5. 강퇴된 멤버는 더 이상 새 데이터 복호화 불가

---

## 문제 해결

### DINOv2 OOM (Out of Memory)

**증상**: 전처리 중 `CUDA out of memory` 에러

**해결책**:
```bash
# 방법 1: Placeholder 임베딩 (테스트용)
serve data preprocess ./demos --placeholder-embeddings

# 방법 2: CPU 모드 (자동 감지)
# CUDA 없으면 자동으로 CPU 사용 (느리지만 안전)

# 방법 3: 배치 크기 조절
# src/cli/dinov2_utils.py의 BATCH_SIZE 상수 수정 (기본값: 256)
```

### 비밀번호 분실

**현재 제약사항**: 복구 메커니즘 없음. 비밀번호 분실 시 **모든 데이터 영구 손실**.

**프로덕션 권장**:
- 하드웨어 키 백업 (Yubikey 등)
- 팀 내 다중 관리자 지정

### 세션 파일 보안

```bash
# 세션 파일 권한 설정 (다른 사용자 읽기 방지)
chmod 600 ~/.serve/session.json

# 로그아웃 (세션 파일 삭제)
rm ~/.serve/session.json
```

### 벡터 DB 재구축

```bash
# 기존 벡터 DB 삭제 후 재구축
rm -rf ~/.serve/vector_db/<team-id>/
serve data build-index <team-id> --write-faiss
```

---

## 향후 로드맵

### 단기 (v1.1)

- [ ] VLA 모델 통합 (Local/HTTP Backend)
- [ ] Sentence-Transformers 기반 의미 검색 (현재는 키워드 매칭)
- [ ] 수동 키 로테이션 명령어 구현
- [ ] PBKDF2/Argon2 비밀번호 해싱 (현재 SHA-256)

### 중기 (v1.2)

- [ ] ChromaDB/Qdrant 통합 (프로덕션 벡터 DB)
- [ ] 분산 벡터 DB 동기화 (엣지 서버 간)
- [ ] 실시간 추론 스트리밍
- [ ] 웹 UI (대시보드, 데모 시각화)

### 장기 (v2.0)

- [ ] Federated Learning 지원
- [ ] 다중 로봇 협업 시나리오
- [ ] 자동 품질 평가 (리뷰 자동화)
- [ ] 온디바이스 VLA 최적화 (양자화, 프루닝)

---

## 기여 및 라이선스

### 기여 방법

1. Fork this repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조.

---

## 연락처

- **프로젝트**: [project-SeRVe/SeRVe-Client](https://github.com/project-SeRVe/SeRVe-Client)
- **이슈 트래커**: [GitHub Issues](https://github.com/project-SeRVe/SeRVe-Client/issues)

---

**Built with ❤️ for the Robotics Community**
