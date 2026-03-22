# Data Pipeline Guide

SeRVe-Client의 데이터 파이프라인 완전 가이드입니다. 로봇 데이터 수집부터 암호화 업로드, RAG 기반 추론까지 전체 워크플로우를 다룹니다.

---

## 목차

1. [워크플로우 개요](#워크플로우-개요)
2. [전처리 (Preprocess)](#전처리-preprocess)
3. [검증 (Validate)](#검증-validate)
4. [수동 리뷰 (Review)](#수동-리뷰-review)
5. [업로드 (Upload)](#업로드-upload)
6. [다운로드 (Download)](#다운로드-download)
7. [벡터 DB 구축 (Build Index)](#벡터-db-구축-build-index)
8. [데이터 포맷](#데이터-포맷)
9. [문제 해결](#문제-해결)

---

## 워크플로우 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    SeRVe Data Pipeline                          │
└─────────────────────────────────────────────────────────────────┘

1. 로봇 데이터 수집
   ├── trajectory.h5 (joint positions, velocities, gripper)
   └── recordings/frames/camera_name/*.jpg

                        ↓

2. 전처리 (preprocess)
   ├── H5 → NPZ 변환
   ├── 이미지 리사이즈 (224x224)
   ├── DINOv2 임베딩 추출 (GPU/CPU)
   └── 출력: processed_demo.npz

                        ↓

3. 검증 (validate)
   ├── NPZ 포맷 체크
   ├── 필수 키 확인
   ├── Shape 검증
   └── 시간 차원 일관성 체크
   
                        ↓

4. 수동 리뷰 (review)
   ├── 인터랙티브 O/X 승인
   ├── pending/ → approved/ or rejected/
   └── 리뷰 로그 기록 (JSONL)

                        ↓

5. 데모 업로드 (upload)
   ├── 단일 NPZ 파일
   ├── 개별 DEK 생성
   ├── Envelope Encryption
   └── 서버 저장 (암호화 상태)

                       ↓

6. 데모 다운로드 (download)
   ├── 단일 NPZ 다운로드
   ├── 자동 복호화
   └── 로컬 DB 기록

                        ↓

7. 벡터 DB 구축 (build-index)
   ├── approved/ 디렉토리에서 로드
   ├── 임베딩 + 메타데이터 추출
   └── Qdrant 컬렉션 생성 및 업로드


                        ↓

8. RAG 기반 추론 (reasoning few-shot)
   ├── Qdrant COSINE 유사도 검색
   ├── Top-K 데모 검색
   ├── Few-Shot 컨텍스트 생성
   └── VLA 모델 추론
```

---

## 전처리 (Preprocess)

로봇 로그 (H5 + 이미지)를 canonical NPZ 포맷으로 변환하고 DINOv2 임베딩을 추출합니다.

### 기본 사용법

```bash
serve data preprocess <input-dir> --prompt "task description"
```

### 입력 디렉토리 구조

```
raw-demos/
├── demo_0/
│   ├── trajectory.h5         # 또는 traj.h5
│   └── recordings/frames/
│       ├── hand_camera/       # wrist camera (필수)
│       │   ├── 000000.jpg
│       │   ├── 000001.jpg
│       │   └── ...
│       └── varied_camera_1/   # base camera (필수)
│           ├── 000000.jpg
│           └── ...
├── demo_1/
│   └── ...
└── demo_2/
    └── ...
```

### 출력 구조

```
raw-demos/
├── demo_0/
│   ├── trajectory.h5
│   ├── recordings/
│   ├── processed_demo.npz     ← 생성됨
│   └── episode_meta.json      ← 생성됨
└── ...
```

### 주요 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--prompt` | 태스크 설명 (필수) | - |
| `--wrist-camera` | 손목 카메라 이름 | `hand_camera` |
| `--base-camera` | 베이스 카메라 이름 | `varied_camera_1` |
| `--rotate-180` | 손목 카메라 이미지 180도 회전 | False |
| `--placeholder-embeddings` | GPU 없이 테스트용 더미 임베딩 | False |
| `--recursive` | 하위 디렉토리 모두 처리 | False |
| `--overwrite` | 기존 파일 덮어쓰기 | False |

### 예제

**기본 전처리 (GPU 사용)**
```bash
serve data preprocess ./raw-demos \
    --prompt "pick up the red cube and place it in the basket"
```

**커스텀 카메라 이름**
```bash
serve data preprocess ./raw-demos \
    --prompt "open the drawer" \
    --wrist-camera cam_hand \
    --base-camera cam_static
```

**손목 카메라 회전 + 재귀 처리**
```bash
serve data preprocess ./all-tasks \
    --prompt "various manipulation tasks" \
    --rotate-180 \
    --recursive \
    --overwrite
```

**테스트용 (GPU 없이)**
```bash
serve data preprocess ./test-demos \
    --prompt "test task" \
    --placeholder-embeddings
```

### DINOv2 임베딩 설정

임베딩 타입을 변경하려면 `src/cli/dinov2_utils.py`의 `EMBEDDING_TYPE` 상수를 수정하세요:

```python
EMBEDDING_TYPE = '64PATCHES'  # Options: 'CLS', 'AVG', '16PATCHES', '64PATCHES'
```

| 타입 | 차원 | 설명 | 권장 용도 |
|------|------|------|-----------|
| `64PATCHES` (기본) | 49,152 | 64 spatial regions × 768D | 상세한 공간 정보 필요 시 |
| `CLS` | 768 | [CLS] token만 | 빠른 프로토타이핑, 디스크 절약 |
| `AVG` | 768 | 패치 평균 | 전역 의미론적 정보만 필요 시 |
| `16PATCHES` | 12,288 | 16 regions × 768D | 중간 수준 공간 해상도 |

### 프롬프트 우선순위

프롬프트는 다음 순서로 결정됩니다:

1. **CLI `--prompt` 옵션** (최우선)
2. **meta.json 파일** (`demo_dir/meta.json`)
3. **디렉토리 이름** (예: `2024-01-15_pick_cube` → "pick cube")

### 메타데이터 파일 (episode_meta.json)

전처리 후 각 데모 디렉토리에 생성됩니다:

```json
{
  "processed_demo_path": "/path/to/demo_0/processed_demo.npz",
  "task_description": "pick up the red cube",
  "num_steps": 150,
  "wrist_camera_name": "hand_camera",
  "base_camera_name": "varied_camera_1",
  "rotate_wrist_180": false,
  "embedding_type": "64PATCHES",
  "embedding_dim": 49152,
  "processed_at_utc": "2026-03-10T12:34:56.789012+00:00"
}
```

---

## 검증 (Validate)

전처리된 NPZ 파일이 canonical 포맷을 따르는지 검증합니다.

### 기본 사용법

```bash
serve data validate <path>
```

### 검증 항목

#### 1. 필수 키 존재 여부
- `state`
- `actions`
- `base_image`
- `wrist_image`
- `base_image_embeddings`
- `wrist_image_embeddings`
- `prompt`

#### 2. Shape 검증
- `state`: `(T, 8)` - Joint positions (7) + gripper (1)
- `actions`: `(T, 7)` - Joint velocities (7)
- `base_image`: `(T, 224, 224, 3)` - RGB base camera
- `wrist_image`: `(T, 224, 224, 3)` - RGB wrist camera
- `base_image_embeddings`: `(T, D)` - DINOv2 embeddings
- `wrist_image_embeddings`: `(T, D)` - DINOv2 embeddings

#### 3. 시간 차원 일관성
모든 배열의 첫 번째 차원 (T)이 동일해야 합니다.

#### 4. 프롬프트 유효성
빈 문자열이 아니어야 합니다.

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--embed-dim` | 예상 임베딩 차원 (검증 강화) |
| `--report-json` | 검증 결과를 JSON 파일로 저장 |
| `--allow-fail` | 실패해도 exit code 0 반환 |
| `--verbose` | 통과한 파일도 모두 표시 |

### 예제

**단일 파일 검증**
```bash
serve data validate ./demo_0/processed_demo.npz
```

**디렉토리 전체 검증**
```bash
serve data validate ./raw-demos
```

**임베딩 차원 검증 포함**
```bash
serve data validate ./raw-demos --embed-dim 49152
```

**JSON 리포트 생성**
```bash
serve data validate ./all-scenarios \
    --report-json validation_report.json \
    --verbose
```

### 출력 예시

```
Found 15 processed_demo.npz file(s) in /path/to/raw-demos

Validating demos: 100%|████████████████| 15/15

============================================================
Validation Summary: 14 passed, 1 failed
============================================================

Failed validations:
✗ /path/to/demo_5/processed_demo.npz
  - time_length_mismatch: [150, 150, 150, 150, 148, 148]
  - wrist_image has 148 steps but state has 150 steps
```

---

## 수동 리뷰 (Review)

전처리된 데모를 인터랙티브하게 승인/거부합니다.

### 기본 사용법

```bash
serve data review --pending-root ./runtime_demos/pending
```

### 디렉토리 구조

```
runtime_demos/
├── pending/          # 리뷰 대기 중인 데모
├── approved/         # 승인된 데모 (업로드 또는 벡터 DB 구축용)
├── rejected/         # 거부된 데모
└── review_log.jsonl  # 리뷰 결정 로그
```

### 인터랙티브 UI

```
Found 5 pending episode(s) in /path/to/pending

Decision keys: [o] approve, [x] reject, [s] skip, [q] quit
Reviewer: user123

[1/5] pick_cube/demo_0
  Steps: 150
  Prompt: pick up the red cube
  NPZ size: 12.45 MB
Decision (o=approve, x=reject, s=skip, q=quit) [s]: o
Reason (optional): clean trajectory, good lighting
  ✓ Moved → approved: /path/to/approved/pick_cube/demo_0

[2/5] pick_cube/demo_1
  Steps: 145
  Prompt: pick up the red cube
  NPZ size: 11.98 MB
Decision (o=approve, x=reject, s=skip, q=quit) [s]: x
Reason (optional): robot collision at step 80
  ✓ Moved → rejected: /path/to/rejected/pick_cube/demo_1

[3/5] open_drawer/demo_0
  ...
```

### 주요 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--pending-root` | 대기 중인 데모 디렉토리 | `runtime_demos/pending` |
| `--approved-root` | 승인된 데모 디렉토리 | `runtime_demos/approved` |
| `--rejected-root` | 거부된 데모 디렉토리 | `runtime_demos/rejected` |
| `--log-path` | 리뷰 로그 파일 경로 | `runtime_demos/review_log.jsonl` |
| `--reviewer` | 리뷰어 이름 | `$USER` |
| `--reason-required` | 모든 결정에 이유 필수 | False |
| `--overwrite` | 기존 파일 덮어쓰기 | False |
| `--dry-run` | 실제 이동 없이 미리보기 | False |
| `--limit` | 최대 리뷰 개수 제한 | None |

### 리뷰 로그 포맷

`review_log.jsonl` 파일에 각 결정이 한 줄씩 기록됩니다:

```jsonl
{"timestamp_utc": "2026-03-10T12:00:00.000000+00:00", "reviewer": "user123", "decision": "approved", "reason": "clean trajectory", "source": "/path/to/pending/demo_0", "target": "/path/to/approved/demo_0", "relative_episode_path": "pick_cube/demo_0", "episode_meta": {"num_steps": 150, "prompt": "pick up the red cube"}}
{"timestamp_utc": "2026-03-10T12:01:30.000000+00:00", "reviewer": "user123", "decision": "rejected", "reason": "robot collision", "source": "/path/to/pending/demo_1", "target": "/path/to/rejected/demo_1", "relative_episode_path": "pick_cube/demo_1", "episode_meta": {"num_steps": 145, "prompt": "pick up the red cube"}}
```

### 예제

**기본 리뷰**
```bash
serve data review
```

**커스텀 디렉토리 + 이유 필수**
```bash
serve data review \
    --pending-root ./my-demos/pending \
    --approved-root ./my-demos/approved \
    --reason-required
```

**Dry run (미리보기)**
```bash
serve data review --dry-run --limit 10
```

---

## 업로드 (Upload)

승인된 데모를 암호화하여 서버에 업로드합니다.

### 데모 업로드

개별 NPZ 파일을 업로드합니다. 각 데모마다 별도의 DEK가 생성됩니다.

```bash
serve data upload <team-id> <task-name> <data-id> --file <npz-file>
```

#### 예제

```bash
serve data upload team-abc123 pick_cube demo_0 \
    --file ./demo_0/processed_demo.npz \
    --description "clean trajectory" \
    --robot-id "franka_001"
```

#### 옵션

| 옵션 | 설명 |
|------|------|
| `--file` | NPZ 파일 경로 (필수) |
| `--description` | 데모 설명 |
| `--robot-id` | 로봇 ID |

### 5-2. 단일 데모 업로드

개별 NPZ 파일을 업로드합니다. 각 데모마다 별도의 DEK가 생성됩니다.

```bash
serve data upload <team-id> <task-name> <data-id> --file <npz-file>
```

#### 예제

```bash
serve data upload team-abc123 pick_cube demo_0 \
    --file ./demo_0/processed_demo.npz \
    --description "clean trajectory" \
    --robot-id "franka_001"
```

#### 옵션

| 옵션 | 설명 |
|------|------|
| `--file` | NPZ 파일 경로 (필수) |
| `--description` | 데모 설명 |
| `--robot-id` | 로봇 ID |

### 업로드 목록 조회

```bash
serve data list <team-id>
```

출력 예시:
```
[+] Fetching task list for repository team-abc123...

--- Task List ---
  [task-001] pick_cube
  [task-002] open_drawer
  [task-003] push_button
```

---

## 다운로드 (Download)

서버에서 암호화된 데모를 다운로드하고 자동 복호화합니다.

### 데모 다운로드

개별 NPZ 파일을 다운로드합니다.

```bash
serve data download <team-id> <task-name> <data-id> --output <file>
```

#### 예제

```bash
serve data download team-abc123 pick_cube demo_0 \
    --output ./demo_0.npz \
    --db-url sqlite:///my-local.db
```

#### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--output` | 출력 파일 경로 (필수) | - |
| `--db-url` | 로컬 DB 연결 URL | `sqlite:///local.db` |

다운로드 후 `local.db`에 메타데이터가 기록됩니다:

```sql
CREATE TABLE downloaded_data (
    team_id TEXT,
    task_name TEXT,
    data_id TEXT,
    output_file TEXT,
    download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, data_id)
);
```

### 6-2. 단일 데모 다운로드

개별 NPZ 파일을 다운로드합니다.

```bash
serve data download <team-id> <task-name> <data-id> --output <file>
```

#### 예제

```bash
serve data download team-abc123 pick_cube demo_0 \
    --output ./demo_0.npz \
    --db-url sqlite:///my-local.db

### 6-3. 전체 동기화

팀의 모든 암호화된 청크를 로컬로 동기화합니다.

```bash
serve data pull <team-id> <db-url>
```

#### 예제

```bash
serve data pull team-abc123 sqlite:///sync.db
```

---

## 벡터 DB 구축 (Build Index)

승인된 데모에서 벡터 DB를 구축하여 RAG 기반 추론에 사용합니다.

### 기본 사용법

```bash
serve data build-index <team-id>
```

### 입력/출력 구조

**입력** (approved 디렉토리):
```
~/.serve/approved/team-abc123/
├── pick_cube/
│   ├── demo_0/processed_demo.npz
│   ├── demo_1/processed_demo.npz
│   └── demo_2/processed_demo.npz
└── open_drawer/
    ├── demo_0/processed_demo.npz
    └── demo_1/processed_demo.npz
```

**출력** (Qdrant 디렉토리):
```
~/.serve/qdrant/
└── collections/
    └── team_<team-id>/  # Qdrant 컬렉션 데이터
                         # - 768D 임베딩 벡터 (COSINE distance)
                         # - Payload: episode_id, step_index, prompt, paths, dimensions
```




### 주요 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--approved-root` | 승인된 데모 디렉토리 | `~/.serve/approved/<team-id>` |
| `--output-root` | 벡터 DB 출력 디렉토리 | `~/.serve/vector_db` |
| `--overwrite` | 기존 벡터 DB 덮어쓰기 | False |

| `--embedding-key` | 사용할 임베딩 키 | `base_image_embeddings` |

### 예제

**기본 벡터 DB 구축**
```bash
serve data build-index team-abc123
```

**Qdrant 벡터 DB 구축**
```bash
serve data build-index team-abc123
```

**커스텀 디렉토리 + 손목 카메라 임베딩 사용**
```bash
serve data build-index team-abc123 \
    --approved-root ./my-approved-demos \
    --embedding-key wrist_image_embeddings \
    --overwrite
```

**기존 벡터 DB 재구축**
```bash
serve data build-index team-abc123 --overwrite
```

### 실행 과정

```
Building Qdrant vector DB from 5 approved episode(s)...
Approved root: /home/user/.serve/approved/team-abc123
Output: /home/user/.serve/vector_db/team-abc123
Embedding key: base_image_embeddings

Processing episodes: 100%|████████████| 5/5

Collected 750 vectors from 5 episodes
Embedding dimension: 49152

Saving vectors.npz...
Saving episodes.json...
Creating Qdrant collection...
Uploading points to Qdrant (batch size: 100)...
Saving summary.json...

✓ Qdrant vector DB built successfully!
Location: ~/.serve/qdrant/
Collection: team_team-abc123
Episodes: 5
Embedding dim: 49152
Distance metric: COSINE
```

### episodes.json 포맷

```json
[
  {
    "episode_id": 0,
    "relative_path": "pick_cube/demo_0",
    "processed_demo_path": "/path/to/approved/pick_cube/demo_0/processed_demo.npz",
    "num_steps": 150,
    "state_dim": 8,
    "action_dim": 7,
    "prompt": "pick up the red cube"
  },
  ...
]
```

### summary.json 포맷 (Deprecated)

Qdrant는 메타데이터를 컬렉션 내부에 저장하므로 별도의 summary.json이 필요하지 않습니다.
`serve reasoning db-info <team-id>` 명령으로 Qdrant 컬렉션 정보를 조회할 수 있습니다.












### 벡터 DB 정보 조회

```bash
serve reasoning db-info <team-id>
```

---

## 데이터 포맷

### NPZ 파일 구조 (Canonical Format)

```python
{
    # 로봇 상태
    'state': np.ndarray,         # (T, 8) - float32
                                  # Joint positions (7) + gripper position (1)
    
    # 액션 (속도 제어)
    'actions': np.ndarray,       # (T, 7) - float32
                                  # Joint velocities (7)
    
    # 베이스 카메라 이미지
    'base_image': np.ndarray,    # (T, 224, 224, 3) - uint8
                                  # RGB images, padded and resized
    
    # 손목 카메라 이미지
    'wrist_image': np.ndarray,   # (T, 224, 224, 3) - uint8
                                  # RGB images, padded and resized
    
    # DINOv2 임베딩
    'base_image_embeddings': np.ndarray,   # (T, D) - float32
                                            # D = 768 (CLS/AVG)
                                            #   = 12,288 (16PATCHES)
                                            #   = 49,152 (64PATCHES)
    
    'wrist_image_embeddings': np.ndarray,  # (T, D) - float32
    
    # 태스크 설명
    'prompt': str                # Task description (non-empty string)
}
```

### H5 파일 구조 (입력)

```python
{
    # 로봇 궤적
    'robot0_joint_pos': np.ndarray,       # (T, N) - Joint positions
    'robot0_joint_vel': np.ndarray,       # (T, N) - Joint velocities
    'robot0_gripper_qpos': np.ndarray,    # (T, 2) - Gripper position
    'robot0_gripper_qvel': np.ndarray,    # (T, 2) - Gripper velocity
    'robot0_eef_pos': np.ndarray,         # (T, 3) - End-effector position
    'robot0_eef_quat': np.ndarray,        # (T, 4) - End-effector quaternion
    
    # 타임스탬프
    'timestamps': np.ndarray,             # (T,) - Timestamps
}
```

---

## 문제 해결

### 1. DINOv2 GPU 메모리 부족

**증상**: `CUDA out of memory` 에러

**해결책**:
```bash
# 방법 1: Placeholder 임베딩 (테스트용)
serve data preprocess ./demos --placeholder-embeddings

# 방법 2: CPU 모드 (자동 감지)
# CUDA 없으면 자동으로 CPU 사용 (느리지만 안전)

# 방법 3: 배치 크기 조절
# src/cli/dinov2_utils.py에서 BATCH_SIZE 변경 (기본값: 256)
BATCH_SIZE = 128  # 또는 64
```

### 2. 카메라 프레임 수 불일치

**증상**: `time_length_mismatch` 검증 에러

**원인**: 카메라 프레임 수가 H5 타임스텝 수와 다름

**해결책**:
```bash
# 1. 프레임 수 확인
ls recordings/frames/hand_camera/ | wc -l
h5dump -d "/timestamps" trajectory.h5 | grep "DATA" | wc -l

# 2. 프레임이 적으면: 로봇 로그를 다시 수집
# 3. 프레임이 많으면: 전처리가 자동으로 H5 길이에 맞춰 잘라냄
```

### 3. 업로드 실패

**증상**: 데모 업로드 실패

**해결책**:
```bash
# 네트워크 연결 확인
# 인증 토큰 확인
serve auth login

# 파일 포맷 검증
serve data validate ./demos
```
### 4. 리뷰 시 파일 이미 존재

**증상**: `Destination already exists` 에러

**해결책**:
```bash
# --overwrite 옵션 사용
serve data review --overwrite
```

### 5. 벡터 DB 빌드 시 approved 디렉토리 없음

**증상**: `Approved root does not exist` 에러

**해결책**:
```bash
# 1. 리뷰를 통해 승인된 데모 생성
serve data review --pending-root ./pending --approved-root ~/.serve/approved/team-id

# 2. 또는 전처리된 데모를 수동으로 이동
mkdir -p ~/.serve/approved/team-id/scenario-name
cp -r ./processed-demos/* ~/.serve/approved/team-id/scenario-name/
```

### 6. Qdrant 연결 실패

**증상**: `Qdrant connection error` 또는 컬렉션 생성 실패

**해결책**:
```bash
# Qdrant 클라이언트 설치 확인
pip install qdrant-client

# Qdrant 디렉토리 권한 확인
ls -la ~/.serve/qdrant/


---

## 참고 자료

- [전처리 상세 가이드](PREPROCESS.md)
- [보안 모델](../README.md#보안-모델)
- [RAG 추론 가이드](REASONING.md) (예정)

---

**Built with ❤️ for the Robotics Community**
