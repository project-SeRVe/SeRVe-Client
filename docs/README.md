# SeRVe-Client

> **Se**cure **R**obotics **V**alidation **e**nvironment
> Zero-Trust 암호화 기반 로봇 학습 데이터 관리 플랫폼

## 개요

SeRVe는 로봇 학습 데이터의 수집부터 추론까지 전체 생명주기를 Zero-Trust 암호화로 관리하는 CLI 플랫폼입니다.

### 핵심 특징

- 🔒 **Zero-Trust 암호화**: 서버는 평문 데이터를 볼 수 없음 (ECC P-256 + AES-256-GCM)
- 🤖 **End-to-End 파이프라인**: 데이터 수집 → 전처리 → 검증 → 암호화 업로드 → RAG 추론
- 🎯 **RAG 기반 Few-Shot Learning**: 유사 데모 검색 후 VLA 모델에 컨텍스트 제공
- 👥 **팀 협업**: 멤버 초대/강퇴, 자동 키 로테이션
- 📦 **시나리오 관리**: 같은 태스크의 여러 데모를 묶어서 관리

---

## 설치

### 요구사항

- Python 3.8+
- CUDA (선택, DINOv2 GPU 가속)

### 설치 방법

```bash
git clone https://github.com/project-SeRVe/SeRVe-Client.git
cd SeRVe-Client
pip install -e .

# 설치 확인
serve --help
```

---

## 빠른 시작

### 1. 사용자 인증

```bash
# 회원가입 (ECC 키 쌍 자동 생성)
serve auth signup

# 로그인
serve auth login
```

### 2. 팀 생성 및 관리

```bash
# 저장소(팀) 생성
serve repo create my-robot-team --description "Franka demos"

# 팀 멤버 초대
serve repo invite <team-id> colleague@example.com

# 저장소 목록
serve repo list
```

### 3. 데이터 전처리

```bash
# 디렉토리 구조:
# raw-demos/
#   ├── demo_0/
#   │   ├── traj.h5
#   │   └── recordings/frames/hand_camera/*.jpg
#   └── demo_1/...

# H5 → NPZ 변환 + DINOv2 임베딩
serve data preprocess ./raw-demos --prompt "pick up red cube"
```

### 4. 검증 및 업로드

```bash
# 포맷 검증
serve data validate ./raw-demos

# 수동 리뷰
serve data review --pending-root ./raw-demos

# 시나리오 단위 암호화 업로드
# 승인된 데모 암호화 업로드
```

### 5. 추론

```bash
# 로컬 벡터 DB 빌드
serve data build-index <team-id>

# Few-Shot 추론
serve reasoning few-shot <team-id> franka "pick up the red cube" --k 5
```

---

## 주요 명령어

### 인증 & 저장소

| 명령어 | 설명 |
|--------|------|
| `serve auth signup` | 회원가입 |
| `serve auth login` | 로그인 |
| `serve repo create <name>` | 저장소 생성 |
| `serve repo invite <team-id> <email>` | 멤버 초대 |
| `serve repo kick <team-id> <user-id>` | 멤버 강퇴 |
| `serve repo list` | 저장소 목록 |

### 데이터 파이프라인

| 명령어 | 설명 |
|--------|------|
| `serve data preprocess <dir>` | H5 → NPZ 변환 + 임베딩 |
| `serve data validate <dir>` | NPZ 포맷 검증 |
| `serve data review` | 인터랙티브 리뷰 |
| `serve data build-index <team-id>` | 벡터 DB 구축 |

### 추론

| 명령어 | 설명 |
|--------|------|
| `serve reasoning few-shot <team-id> <robot> <prompt>` | RAG 기반 추론 |
| `serve reasoning db-info <team-id>` | 벡터 DB 통계 |

---

## 아키텍처

### 프로젝트 구조

```
SeRVe-Client/
├── src/cli/              # CLI 명령어
│   ├── auth.py          # 인증 (signup/login)
│   ├── repo.py          # 저장소 관리
│   ├── data.py          # 데이터 업로드/다운로드
│   ├── preprocess.py    # H5 → NPZ 변환
│   ├── reasoning.py     # RAG 추론
│   └── dinov2_utils.py  # DINOv2 임베딩
├── serve_sdk/           # 핵심 SDK
│   ├── client.py        # 고수준 API
│   ├── api_client.py    # HTTP 통신
│   ├── session.py       # 세션/키 관리
│   └── security/        # 암호화
└── docs/                # 상세 문서
```

### 데이터 포맷

**NPZ 파일 구조** (Canonical Format):

```python
{
    'state': np.ndarray,         # (T, 8) - Joint pos + gripper
    'actions': np.ndarray,       # (T, 7) - Joint vel + gripper
    'base_image': np.ndarray,    # (T, 224, 224, 3)
    'wrist_image': np.ndarray,   # (T, 224, 224, 3)
    'base_image_embeddings': np.ndarray,   # (T, 49152) - DINOv2
    'wrist_image_embeddings': np.ndarray,  # (T, 49152)
    'prompt': str                # Task description
}
```

### 보안 모델

**Zero-Trust 원칙**: 서버는 평문 데이터와 복호화 키를 절대 보지 못합니다.

```
사용자 비밀번호 (Client)
    ↓ SHA-256
Password-Derived Key
    ↓ AES-GCM
개인키 (ECC P-256)
    ↓ ECIES
팀 키 (AES-256-GCM)
    ↓ Envelope Encryption
DEK (Data Encryption Key)
    ↓ AES-GCM
평문 데이터
```

**Envelope Encryption**: 시나리오 단위로 하나의 DEK를 공유하여 효율적인 키 관리

**자동 키 로테이션**: 멤버 강퇴 시 새 팀 키 생성 및 DEK 재래핑

---

## 워크플로우

### 데이터 업로드

```
로봇 데이터 수집
    ↓
전처리 (H5 → NPZ + DINOv2)
    ↓
검증 (포맷 체크)
    ↓
수동 리뷰 (O/X)
    ↓
암호화 업로드 (Envelope Encryption)
    ↓
서버 저장 (암호화 상태)
```

### RAG 추론

```
로컬 벡터 DB 구축
    ↓
사용자 쿼리
    ↓
유사 데모 검색 (Qdrant)
    ↓
Few-Shot 컨텍스트 생성
    ↓
VLA 모델 추론
```

---

## 문제 해결

### DINOv2 GPU 메모리 부족

```bash
# Placeholder 임베딩 (테스트용)
serve data preprocess ./demos --placeholder-embeddings

# CPU 모드 (자동 감지)
# CUDA 없으면 자동으로 CPU 사용
```

### 세션 파일 보안

```bash
# 권한 설정
chmod 600 ~/.serve/session.json

# 로그아웃
rm ~/.serve/session.json
```

---

## 상세 문서

- [전처리 가이드](docs/PREPROCESS.md)
- [보안 모델](docs/SECURITY.md) (예정)
- [API 레퍼런스](docs/API.md) (예정)

---

**Built with ❤️ for the Robotics Community**
