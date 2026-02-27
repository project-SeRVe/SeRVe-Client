# SeRVe-Client

> **Secure Robotics Validation environment**: Zero-Trust E2E 암호화 기반 로봇 학습 데이터 관리 및 RAG 기반 VLA 추론 플랫폼

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [명령어 레퍼런스](#명령어-레퍼런스)
- [데이터 파이프라인](#데이터-파이프라인)
- [보안 모델](#보안-모델)
- [문제 해결](#문제-해결)

---

## 개요

SeRVe-Client는 로봇 학습 데이터의 **수집부터 추론까지** 전체 생명주기를 관리하는 CLI 기반 플랫폼입니다.

### 핵심 특징

- **Zero-Trust 암호화**: 서버는 평문 데이터를 절대 볼 수 없음
- **End-to-End 파이프라인**: 로봇 로그 → 전처리 → 검증 → 업로드 → 벡터 DB → VLA 추론
- **RAG 기반 추론**: 로컬 벡터 DB에서 유사 데모 검색 후 VLA 모델에 컨텍스트 제공
- **팀 협업**: 팀 단위 데이터 공유, 멤버 초대/강퇴, 자동 키 로테이션

---

## 주요 기능

### 1. 사용자 인증 & 저장소 관리

- **ECC P-256 키 쌍 기반 인증**: 비대칭 암호화로 사용자 신원 보장
- **팀 키(AES-256-GCM)**: 팀 단위 데이터 공유
- **Lazy Loading**: 필요한 시점에만 키를 복호화하여 메모리 효율 최적화

### 2. 로봇 데이터 전처리

- **H5 궤적 파일 → NPZ 변환**: state, actions, RGB 이미지, DINOv2 임베딩
- **DINOv2 ViT-B/14 임베딩**: 64PATCHES = 49,152D per timestep
- **검증 & 리뷰 워크플로우**: 수동 품질 관리 (O/X 승인)

### 3. 암호화 업로드

- **Envelope Encryption**: DEK(데이터 암호화 키) + KEK(키 암호화 키, 팀 키)
- **시나리오 단위 업로드**: 같은 태스크의 여러 데모를 묶어서 업로드

### 4. RAG 기반 VLA 추론

- **로컬 벡터 DB**: FAISS 인덱스 기반 유사도 검색
- **Few-Shot 추론**: 유사 데모 검색 → VLA 모델 컨텍스트 제공
- **엣지 서버 최적화**: 로컬 추론으로 레이턴시 최소화

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     SeRVe-Client Architecture                   │
│                (Zero-Trust + Robot Learning Data)               │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                            │
┌───────▼────────┐                      ┌───────────▼────────┐
│  Data Pipeline  │                      │ Inference Pipeline  │
│  (Robot → Server)│                      │ (Local RAG → VLA)  │
└────────────────┘                      └────────────────────┘

[Data Pipeline Flow]
로봇 궤적 수집 (H5 + 카메라)
    ↓
전처리 (preprocess) → NPZ + DINOv2 임베딩
    ↓
검증 (validate) → 포맷 검증
    ↓
수동 리뷰 (review) → O/X 승인
    ↓
시나리오 업로드 (upload-scenario) → Envelope Encryption
    ↓
서버 저장 (암호화된 상태로만 저장)

[Inference Pipeline Flow]
승인된 데모들 → 벡터 DB 구축 (build-index)
                   ↓
              ~/.serve/vector_db/<team>/
                   ↓
            Few-Shot 추론 (reasoning few-shot)
                   ↓
         유사 데모 검색 (FAISS L2)
                   ↓
         VLA 모델에 컨텍스트 제공
                   ↓
            액션 예측 (TODO)
```

### 계층 구조

| 계층 | 위치 | 책임 |
|------|------|------|
| **CLI** | `src/cli/` | 사용자 인터페이스, 명령어 파싱 |
| **SDK** | `serve_sdk/` | 비즈니스 로직, 암호화 워크플로우 |
| **Crypto** | `serve_sdk/security/` | Google Tink 래퍼 (ECC, AES-GCM) |
| **API Client** | `serve_sdk/api_client.py` | HTTP 통신 |
| **Session** | `serve_sdk/session.py` | 메모리 내 키/토큰 관리 |

---

## 설치

### 요구사항

- Python 3.8+
- CUDA (선택, DINOv2 GPU 가속용)

### 설치 명령어

```bash
# 저장소 클론
git clone https://github.com/project-SeRVe/SeRVe-Client.git
cd SeRVe-Client

# 개발 모드 설치 (소스 수정 시 재설치 불필요)
pip install -e .

# 의존성 자동 설치:
# - click: CLI 프레임워크
# - requests: HTTP 클라이언트
# - tink: Google 암호화 라이브러리
# - numpy, h5py: 데이터 처리
# - Pillow: 이미지 전처리
# - torch, torchvision: DINOv2 임베딩

# 설치 확인
serve --help
```

---

## 빠른 시작

### 1단계: 사용자 인증

```bash
# 회원가입 (ECC P-256 키 쌍 자동 생성)
serve auth signup

# 로그인
serve auth login
# → ~/.serve/session.json에 세션 저장 (암호화된 개인키 포함)
```

### 2단계: 팀 생성 및 멤버 초대

```bash
# 저장소(팀) 생성
serve repo create my-robot-team --description "Franka pick-and-place demos"
# → 출력: Team ID (예: team-abc123)

# 팀 멤버 초대 (팀 키를 멤버의 공개키로 래핑)
serve repo invite team-abc123 colleague@example.com

# 저장소 목록 조회
serve repo list

# 저장소 상세 조회 (멤버 리스트)
serve repo show team-abc123
```

### 3단계: 로봇 데이터 전처리

```bash
# 디렉토리 구조 예시:
# raw-demos/
#   ├── demo_0/
#   │   ├── traj.h5
#   │   └── recordings/frames/hand_camera/*.jpg
#   │                        /varied_camera_1/*.jpg
#   └── demo_1/...

# 전처리 (H5 → NPZ + DINOv2 임베딩)
serve data preprocess ./raw-demos --prompt "pick up red cube"
# → 각 demo_X/ 폴더에 processed_demo.npz 생성

# 재귀 모드 (여러 시나리오 한번에)
serve data preprocess ./scenarios --recursive --prompt "pick" --prompt "place"
```

### 4단계: 검증 및 리뷰

```bash
# NPZ 포맷 검증
serve data validate ./raw-demos

# 수동 리뷰 (인터랙티브 O/X)
serve data review --pending-root ./raw-demos
# → O: ~/.serve/approved/<team>/ 이동
# → X: ~/.serve/rejected/<team>/ 이동
```

### 5단계: 서버 업로드

```bash
# 시나리오 단위 암호화 업로드
serve data upload-scenario team-abc123 pick_cube ~/.serve/approved/team-abc123/pick_cube
# → 서버에 암호화된 상태로 저장 (Envelope Encryption)
```

### 6단계: 벡터 DB 구축 및 추론

```bash
# 로컬 벡터 DB 빌드 (승인된 데모들로부터)
serve data build-index team-abc123 --write-faiss
# → ~/.serve/vector_db/team-abc123/ 생성
#    - vectors.npz: 임베딩 벡터들
#    - episodes.json: 에피소드 메타데이터
#    - index.faiss: FAISS L2 인덱스

# 벡터 DB 정보 확인
serve reasoning db-info team-abc123

# Few-Shot 추론 (RAG 기반)
serve reasoning few-shot team-abc123 franka "pick up the red cube" --k 5
# → 유사 데모 5개 검색 → VLA 모델에 컨텍스트 제공 (TODO: VLA 통합)

# Basic 추론 (RAG 없이 모델만)
serve reasoning basic franka "pick up object"
```

---

## 명령어 레퍼런스

### 인증 (`serve auth`)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `signup` | 회원가입 (키 쌍 생성) | `serve auth signup` |
| `login` | 로그인 (세션 저장) | `serve auth login` |
| `reset-pw` | 비밀번호 재설정 | `serve auth reset-pw` |
| `delete-account` | 회원 탈퇴 | `serve auth delete-account --force` |

### 저장소 (`serve repo`)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `create` | 저장소 생성 | `serve repo create my-team` |
| `list` | 저장소 목록 | `serve repo list` |
| `show` | 저장소 상세 조회 | `serve repo show team-id` |
| `invite` | 멤버 초대 | `serve repo invite team-id user@example.com` |
| `kick` | 멤버 강퇴 (자동 키 로테이션) | `serve repo kick team-id user-id` |
| `set-role` | 권한 변경 | `serve repo set-role team-id user-id ADMIN` |

### 데이터 관리 (`serve data`)

#### 전처리 파이프라인

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `preprocess` | H5 → NPZ 변환 + 임베딩 | `serve data preprocess ./demos --prompt "pick"` |
| `validate` | NPZ 포맷 검증 | `serve data validate ./demos --verbose` |
| `review` | 수동 O/X 리뷰 | `serve data review --pending-root ./demos` |

#### 업로드/다운로드

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `upload-scenario` | 시나리오 단위 업로드 | `serve data upload-scenario team-id scenario-name ./approved/scenario` |
| `upload` | 단일 데모 업로드 | `serve data upload team-id task-name data-id` |
| `download` | 데모 다운로드 | `serve data download team-id task-name data-id` |
| `download-scenario` | 시나리오 단위 다운로드 | `serve data download-scenario team-id scenario-name --output-dir ./downloads` |
| `list` | 데모 목록 조회 | `serve data list team-id` |
| `pull` | 전체 동기화 | `serve data pull team-id sqlite:///local.db` |

#### 벡터 DB

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `build-index` | 벡터 DB 구축 | `serve data build-index team-id --write-faiss` |

### 추론 (`serve reasoning`)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `few-shot` | RAG 기반 추론 | `serve reasoning few-shot team-id robot "pick cube" --k 5` |
| `basic` | 모델 단독 추론 | `serve reasoning basic robot "pick cube"` |
| `db-info` | 벡터 DB 통계 | `serve reasoning db-info team-id` |

---

## 데이터 파이프라인

### NPZ 포맷 (Canonical)

전처리된 로봇 데모는 다음 구조의 NPZ 파일로 저장됩니다:

```python
{
    'state': np.ndarray,         # (T, 8) - Joint positions (7) + gripper (1)
    'actions': np.ndarray,       # (T, 7) - Joint velocities (6) + gripper (1)
    'base_image': np.ndarray,    # (T, 224, 224, 3) - RGB uint8
    'wrist_image': np.ndarray,   # (T, 224, 224, 3) - RGB uint8
    'base_image_embeddings': np.ndarray,   # (T, 49152) - DINOv2 64PATCHES
    'wrist_image_embeddings': np.ndarray,  # (T, 49152) - DINOv2 64PATCHES
    'prompt': str                # Task description
}
```

### DINOv2 임베딩 옵션

`src/cli/dinov2_utils.py`에서 `EMBEDDING_TYPE` 상수로 조절:

| 타입 | 차원 | 설명 |
|------|------|------|
| `64PATCHES` (기본) | 49,152D | 64 spatial regions × 768D |
| `CLS` | 768D | [CLS] token만 사용 (압축) |
| `AVG` | 768D | 모든 패치 평균 (압축) |
| `16PATCHES` | 12,288D | 16 spatial regions × 768D |

### 전처리 상세 옵션

```bash
serve data preprocess INPUT_DIR [OUTPUT_DIR] \
    --prompt "pick cube" \              # 태스크 설명 (여러 개 가능)
    --wrist-camera hand_camera \        # 손목 카메라 폴더명
    --base-camera varied_camera_1 \     # 베이스 카메라 폴더명
    --rotate-180 \                      # 이미지 180도 회전
    --placeholder-embeddings \          # GPU 없이 제로 임베딩 (테스트용)
    --recursive \                       # 하위 시나리오 모두 처리
    --overwrite                         # 기존 NPZ 덮어쓰기
```

자세한 내용은 [`docs/PREPROCESS.md`](docs/PREPROCESS.md) 참조.

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

#### 서버가 저장하는 것

- ✅ 암호화된 개인키 (비밀번호로 보호)
- ✅ 공개키 (평문)
- ✅ 암호화된 팀 키 (각 멤버의 공개키로 래핑)
- ✅ 암호화된 DEK (팀 키로 래핑)
- ✅ 암호화된 데이터 (DEK로 암호화)

#### 서버가 절대 알 수 없는 것

- ❌ 비밀번호
- ❌ 복호화된 개인키
- ❌ 복호화된 팀 키
- ❌ 복호화된 DEK
- ❌ 평문 데이터 (로봇 궤적, 이미지, 임베딩)

### Envelope Encryption (봉투 암호화)

```
[업로드 시]
1. DEK 생성 (AES-256-GCM, 랜덤)
   - 시나리오 단위 업로드: 하나의 DEK를 모든 에피소드가 공유
   - 단일 데모 업로드: 에피소드마다 개별 DEK 생성
2. 데이터를 DEK로 암호화
3. DEK를 팀 키(KEK)로 래핑
4. 서버에 전송: {encryptedData, encryptedDEK}

[다운로드 시]
1. 팀 키로 DEK 언래핑
2. DEK로 데이터 복호화
3. 평문 반환

장점:
- 대량 데이터는 빠른 대칭키(DEK)로 암호화
- 멤버 추가 시 DEK만 재래핑 (데이터 재암호화 불필요)
- 시나리오 단위 업로드: 같은 태스크의 모든 에피소드가 하나의 DEK 공유 → 효율적 관리

### Lazy Loading 패턴

```python
# _ensure_team_key() 구현 (serve_sdk/client.py)
def _ensure_team_key(repo_id):
    # 1. 메모리 캐시 확인
    if cached := session.get_cached_team_key(repo_id):
        return cached
    
    # 2. 서버에서 암호화된 팀 키 조회
    encrypted_key = api.get_team_key(repo_id, user_id, token)
    
    # 3. 내 개인키로 복호화 (클라이언트에서만!)
    team_key = crypto.unwrap_aes_key(encrypted_key, private_key)
    
    # 4. 메모리에 캐싱
    session.cache_team_key(repo_id, team_key)
    return team_key

# 같은 프로그램 실행 중에는 서버 요청 없이 캐시 사용
# → 불필요한 네트워크 트래픽 최소화
```

### 멤버 강퇴 시 자동 키 로테이션

```
1. 서버에 강퇴 요청
2. 새로운 팀 키 생성
3. 남은 멤버들의 공개키로 새 팀 키 재래핑
4. 모든 DEK를 새 팀 키로 재래핑 (데이터 자체는 재암호화 불필요)
5. 강퇴된 멤버는 더 이상 새 데이터 복호화 불가
```

---

## 문제 해결

### DINOv2 OOM (Out of Memory)

**증상**: 전처리 중 `CUDA out of memory` 에러

**해결책**:

```bash
# 방법 1: Placeholder 임베딩 사용 (테스트용)
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
# 세션 파일 위치
~/.serve/session.json

# 권한 설정 (다른 사용자가 읽지 못하도록)
chmod 600 ~/.serve/session.json

# 로그아웃 (세션 파일 삭제)
rm ~/.serve/session.json
```

### 벡터 DB 재구축

```bash
# 기존 벡터 DB 삭제
rm -rf ~/.serve/vector_db/<team-id>/

# 재구축
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
