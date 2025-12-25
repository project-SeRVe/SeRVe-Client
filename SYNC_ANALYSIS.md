# SeRVe 증분 동기화 로직 분석

## 📋 현재 구현 상태

### 백엔드 (Spring Boot)

#### 1. VectorChunk 엔티티 (VectorChunk.java)
```java
@Entity
@Table(name = "vector_chunks", indexes = {
    @Index(name = "idx_team_version", columnList = "team_id, version")
})
public class VectorChunk {
    @Id
    private String chunkId;

    private String documentId;
    private String teamId;
    private int chunkIndex;

    @Lob
    private byte[] encryptedBlob;

    @Version  // JPA가 자동으로 버전 관리
    private int version;

    private boolean isDeleted;

    // 업데이트/삭제 시 version 자동 증가
    public void updateContent(byte[] newBlob) { ... }
    public void markAsDeleted() { ... }
}
```

**주요 특징**:
- `@Version` 어노테이션으로 JPA가 자동으로 버전 관리
- UPDATE/DELETE 시 version이 자동으로 1씩 증가
- `team_id, version` 복합 인덱스로 동기화 쿼리 최적화
- `isDeleted` 플래그로 논리적 삭제 지원

#### 2. 동기화 API 엔드포인트

**ChunkController.java:69-78**
```java
/**
 * E. 팀별 증분 동기화
 * GET /api/sync/chunks?teamId={id}&lastVersion={n}
 */
@GetMapping("/api/sync/chunks")
public ResponseEntity<List<ChunkSyncResponse>> syncTeamChunks(
        @RequestParam String teamId,
        @RequestParam(defaultValue = "0") int lastVersion,
        @AuthenticationPrincipal User user) {

    List<ChunkSyncResponse> response = chunkService.syncTeamChunks(
            teamId, lastVersion, user.getUserId());
    return ResponseEntity.ok(response);
}
```

**ChunkService.java:162-183**
```java
@Transactional(readOnly = true)
public List<ChunkSyncResponse> syncTeamChunks(String teamId, int lastVersion, String userId) {
    // 1. Team 조회
    Team team = teamRepository.findByTeamId(teamId)...

    // 2. 팀 멤버십 체크 (ADMIN 또는 MEMBER 모두 허용)
    if (!memberRepository.existsByTeamAndUser(team, user)) {
        throw new SecurityException("팀 멤버가 아닙니다.");
    }

    // 3. 팀의 모든 문서에서 변경된 청크 조회
    List<VectorChunk> chunks = vectorChunkRepository
            .findByTeamIdAndVersionGreaterThanOrderByVersionAsc(teamId, lastVersion);

    return chunks.stream()
            .map(ChunkSyncResponse::from)
            .collect(Collectors.toList());
}
```

**응답 형식 (ChunkSyncResponse.java)**:
```json
[
  {
    "documentId": "doc-uuid",
    "chunkId": "chunk-uuid",
    "chunkIndex": 0,
    "encryptedBlob": [byte array],
    "version": 5,
    "isDeleted": false
  }
]
```

**권한**:
- ✅ ADMIN: 동기화 조회 가능
- ✅ MEMBER: 동기화 조회 가능
- ❌ 비멤버: 403 Forbidden

---

### 클라이언트 SDK (Python)

#### 1. API 클라이언트 (api_client.py:487-510)
```python
def sync_team_chunks(self, team_id: str, last_version: int,
                    access_token: str) -> Tuple[bool, Optional[List[Dict]]]:
    """
    팀 전체 증분 청크 동기화

    Returns:
        청크 형식: [{"documentId": str, "chunkId": str, "chunkIndex": int,
                    "encryptedBlob": bytes, "version": int, "isDeleted": bool}, ...]
    """
    resp = self.session.get(
        f"{self.server_url}/api/sync/chunks",
        params={"teamId": team_id, "lastVersion": last_version},
        headers=self._get_headers(access_token)
    )
    return self._handle_response(resp)
```

#### 2. 고수준 SDK (client.py:637-707)
```python
def sync_team_chunks(self, repo_id: str, last_version: int = 0) -> Tuple[Optional[Dict[str, List[Dict]]], str]:
    """
    팀 전체 증분 청크 동기화 (복호화 포함)

    Returns:
        형식: {
            "doc-id-1": [{"chunkIndex": int, "data": str, "version": int, "isDeleted": bool}, ...],
            "doc-id-2": [...]
        }
    """
    # 1. 서버에서 팀 전체 변경된 청크들 조회
    success, chunks = self.api.sync_team_chunks(repo_id, last_version, ...)

    # 2. 팀 키 가져오기
    team_key = self._ensure_team_key(repo_id)

    # 3. 문서별로 그룹핑하면서 복호화
    documents_chunks = {}
    for chunk in chunks:
        # 삭제되지 않은 청크만 복호화
        if not chunk["isDeleted"]:
            plaintext = self.crypto.decrypt_data(encrypted_blob, team_key)
            result_chunk["data"] = plaintext
        else:
            result_chunk["data"] = None

        # 문서별로 그룹핑
        documents_chunks[doc_id].append(result_chunk)

    return documents_chunks, f"{len(documents_chunks)}개 문서, 총 {total_chunks}개 청크 동기화 완료"
```

---

## 🔄 동기화 동작 방식

### 증분 동기화 시나리오

```
초기 상태:
- Edge A (ADMIN): lastVersion = 0
- Edge B (MEMBER): lastVersion = 0
- Cloud: version = 0 (청크 없음)

Step 1: Edge A가 청크 업로드
┌──────────┐
│ Edge A   │ POST /api/teams/{teamId}/chunks
│ (ADMIN)  │ → {"fileName": "doc1", "chunks": [{"chunkIndex": 0, "data": "..."}]}
└──────────┘
              ↓
         ┌─────────┐
         │ Cloud   │ INSERT vector_chunks (version = 0)
         └─────────┘

Step 2: Edge B가 동기화 요청
┌──────────┐
│ Edge B   │ GET /api/sync/chunks?teamId=xxx&lastVersion=0
│ (MEMBER) │
└──────────┘
              ↓
         ┌─────────┐
         │ Cloud   │ SELECT * WHERE team_id=xxx AND version > 0
         └─────────┘ → [{"documentId": "doc1", "chunkIndex": 0, "version": 0, ...}]
              ↓
┌──────────┐
│ Edge B   │ 복호화 후 로컬 벡터스토어에 저장
│          │ lastVersion = 0 (최신 버전 저장)
└──────────┘

Step 3: Edge A가 청크 업데이트
┌──────────┐
│ Edge A   │ POST /api/teams/{teamId}/chunks
│ (ADMIN)  │ → {"fileName": "doc1", "chunks": [{"chunkIndex": 0, "data": "updated"}]}
└──────────┘
              ↓
         ┌─────────┐
         │ Cloud   │ UPDATE vector_chunks SET encrypted_blob=..., version=1
         └─────────┘ (@Version으로 자동 증가)

Step 4: Edge B가 재동기화
┌──────────┐
│ Edge B   │ GET /api/sync/chunks?teamId=xxx&lastVersion=0
│ (MEMBER) │
└──────────┘
              ↓
         ┌─────────┐
         │ Cloud   │ SELECT * WHERE team_id=xxx AND version > 0
         └─────────┘ → [{"documentId": "doc1", "chunkIndex": 0, "version": 1, ...}]
              ↓
┌──────────┐
│ Edge B   │ 변경된 청크 감지 (version 1 > 0)
│          │ 로컬 벡터스토어 업데이트
│          │ lastVersion = 1
└──────────┘
```

---

## 🎯 권한 분리 및 보안

### 현재 권한 구조

| 작업 | ADMIN | MEMBER | 비멤버 |
|------|-------|--------|--------|
| 청크 업로드 (POST /api/teams/{teamId}/chunks) | ✅ | ❌ | ❌ |
| 청크 다운로드 (GET /api/teams/{teamId}/chunks) | ✅ | ✅ | ❌ |
| 청크 삭제 (DELETE /api/teams/{teamId}/chunks/{index}) | ✅ | ❌ | ❌ |
| 증분 동기화 (GET /api/sync/chunks) | ✅ | ✅ | ❌ |

**ChunkService.java 권한 체크**:
```java
// 업로드/삭제: ADMIN 전용
if (member.getRole() != Role.ADMIN) {
    throw new SecurityException("청크 업로드는 ADMIN 권한이 필요합니다.");
}

// 다운로드/동기화: ADMIN + MEMBER
if (!memberRepository.existsByTeamAndUser(team, user)) {
    throw new SecurityException("팀 멤버가 아닙니다.");
}
```

---

## 🏗️ 현재 아키텍처에서의 동기화 전략

### 방식 1: Pull 기반 Polling (현재 구현 완료)

```
┌─────────────┐                    ┌─────────────┐
│  Edge A     │                    │  Edge B     │
│  (ADMIN)    │                    │  (MEMBER)   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ 1. 센서 데이터 업로드             │
       │ POST /api/teams/{id}/chunks     │
       ├──────────────────────────────────┤
       │                                  │
       │                                  │ 2. 주기적 동기화 (예: 30초마다)
       │                                  │ GET /api/sync/chunks?lastVersion=N
       │                                  ├─────────────────────────►
       │                                  │
       │                                  │ 3. 변경사항 수신 (암호화)
       │                                  │◄─────────────────────────
       │                                  │
       │                                  │ 4. 복호화 후 로컬 벡터스토어 업데이트
       │                                  │ vision_engine.add_to_vector_store()
       └──────────────────────────────────┘
```

**장점**:
- ✅ 구현이 간단 (이미 완료됨)
- ✅ HTTP/REST만으로 동작
- ✅ 방화벽/NAT 문제 없음
- ✅ 서버 부하 예측 가능

**단점**:
- ❌ 실시간성 떨어짐 (polling 주기에 따라 지연)
- ❌ 불필요한 네트워크 요청 (변경 없어도 polling)
- ❌ 다수의 Edge 노드 시 서버 부하 증가

**구현 예시** (main.py에 추가):
```python
import asyncio

async def sync_worker():
    """백그라운드 동기화 워커"""
    last_version = 0

    while True:
        try:
            # 30초마다 동기화
            await asyncio.sleep(30)

            documents_chunks, msg = serve_client.sync_team_chunks(TEAM_ID, last_version)

            if not documents_chunks:
                logger.info("동기화: 변경사항 없음")
                continue

            logger.info(f"동기화: {msg}")

            # 각 문서의 청크를 로컬 벡터스토어에 반영
            for doc_id, chunks in documents_chunks.items():
                for chunk in chunks:
                    if chunk['isDeleted']:
                        # TODO: 로컬에서 청크 삭제 로직
                        pass
                    else:
                        # 로컬 벡터스토어에 추가/업데이트
                        vision_engine.add_to_vector_store(
                            local_vectorstore,
                            chunk['data'],
                            document_name=f"{doc_id}_chunk_{chunk['chunkIndex']}"
                        )

                    # 최신 버전 업데이트
                    if chunk['version'] > last_version:
                        last_version = chunk['version']

        except Exception as e:
            logger.error(f"동기화 오류: {e}")

@app.on_event("startup")
async def startup_event():
    # 기존 초기화...

    # 동기화 워커 시작
    asyncio.create_task(sync_worker())
```

---

### 방식 2: Push 기반 WebSocket/SSE (미구현, 향후 고려)

```
┌─────────────┐                    ┌─────────────┐
│  Edge A     │                    │  Edge B     │
│  (ADMIN)    │                    │  (MEMBER)   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │                                  │ 1. WebSocket 연결 유지
       │                                  │ WS /api/sync/stream
       │                                  ├─────────────────────────►
       │                                  │
       │ 2. 센서 데이터 업로드             │
       │ POST /api/teams/{id}/chunks     │
       ├──────────────────────────────────┤
       │                                  │
       │                                  │ 3. 서버가 실시간 알림 전송
       │                                  │◄═════════════════════════
       │                                  │ {"event": "chunk_updated", "version": N}
       │                                  │
       │                                  │ 4. 알림 받으면 즉시 동기화
       │                                  │ GET /api/sync/chunks?lastVersion=N-1
       │                                  ├─────────────────────────►
       └──────────────────────────────────┘
```

**장점**:
- ✅ 실시간 동기화
- ✅ 불필요한 polling 제거
- ✅ 네트워크 효율적

**단점**:
- ❌ 구현 복잡도 증가 (WebSocket 서버, 연결 관리)
- ❌ 방화벽/NAT 환경에서 연결 유지 어려움
- ❌ Edge 노드 재시작 시 재연결 로직 필요

**필요한 작업**:
1. Spring Boot에 WebSocket 설정 추가
2. 청크 업로드 시 WebSocket으로 알림 broadcast
3. Python 클라이언트에 WebSocket 연결 로직 추가

---

### 방식 3: Hybrid (추천)

**Pull + 조건부 Push**:
- 기본: 주기적 polling (예: 5분마다)
- 추가: ADMIN Edge가 업로드 시 HTTP POST로 MEMBER Edge에 알림 (optional)

```
┌─────────────┐                    ┌─────────────┐
│  Edge A     │                    │  Edge B     │
│  (ADMIN)    │                    │  (MEMBER)   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ 1. 센서 데이터 업로드             │ 기본: 5분 polling
       │ POST /api/teams/{id}/chunks     │ GET /api/sync/chunks
       ├──────────────────────────────────┤
       │                                  │
       │ 2. (Optional) MEMBER에 알림       │
       │ HTTP POST http://edge-b:9001/sync│
       ├──────────────────────────────────►
       │                                  │
       │                                  │ 3. 알림 받으면 즉시 동기화
       │                                  │ GET /api/sync/chunks
       │                                  ├─────────────────────────►
       └──────────────────────────────────┘
```

**장점**:
- ✅ 실시간성 + 안정성 균형
- ✅ 알림 실패해도 polling으로 복구
- ✅ 구현 난이도 낮음

**단점**:
- ❌ ADMIN이 MEMBER의 IP/Port를 알아야 함
- ❌ NAT 환경에서 직접 연결 어려움

---

## 💡 권장 구현 방안

### 현재 아키텍처 (WSL + Docker) 고려사항

1. **Edge 서버들이 같은 네트워크에 있는가?**
   - YES → Pull 기반 Polling으로 충분
   - NO → WebSocket 또는 Cloud를 통한 간접 알림 필요

2. **동기화 빈도 요구사항**
   - 실시간 (< 1초) → WebSocket 필요
   - 준실시간 (< 30초) → Polling으로 충분
   - 배치 (분 단위) → Polling으로 충분

3. **Edge 노드 수**
   - 소규모 (< 10대) → Polling으로 충분
   - 대규모 (> 100대) → WebSocket 고려

### Phase 1: Pull 기반 Polling (즉시 구현 가능)

**main.py에 동기화 워커 추가**:
```python
# src/main.py에 추가

import asyncio
from typing import Optional

# 전역 변수
last_sync_version = 0

async def background_sync_worker():
    """백그라운드 청크 동기화 워커"""
    global last_sync_version, local_vectorstore

    SYNC_INTERVAL = 30  # 30초마다 동기화

    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL)

            if not serve_client or not serve_client.session.is_authenticated():
                logger.warning("클라우드 미연결, 동기화 건너뜀")
                continue

            if not TEAM_ID:
                continue

            # 증분 동기화 실행
            documents_chunks, msg = serve_client.sync_team_chunks(TEAM_ID, last_sync_version)

            if not documents_chunks:
                logger.debug("동기화: 변경사항 없음")
                continue

            logger.info(f"📥 동기화: {msg}")

            # 로컬 벡터스토어에 반영
            for doc_id, chunks in documents_chunks.items():
                for chunk in chunks:
                    chunk_version = chunk['version']

                    if chunk['isDeleted']:
                        logger.info(f"   삭제된 청크: doc={doc_id[:8]}... chunk={chunk['chunkIndex']}")
                        # TODO: 로컬 벡터스토어에서 삭제 (현재 ChromaDB는 문서 단위 삭제만 지원)
                    else:
                        # 로컬 벡터스토어에 추가/업데이트
                        data = chunk['data']
                        doc_name = f"{doc_id}_chunk_{chunk['chunkIndex']}"

                        if vision_engine and local_vectorstore:
                            vision_engine.add_to_vector_store(
                                local_vectorstore,
                                data,
                                document_name=doc_name
                            )
                            logger.info(f"   청크 동기화: {doc_name} (v{chunk_version})")

                    # 최신 버전 업데이트
                    if chunk_version > last_sync_version:
                        last_sync_version = chunk_version

            logger.info(f"   최신 버전: {last_sync_version}")

        except Exception as e:
            logger.error(f"동기화 워커 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())

@app.on_event("startup")
async def startup_event():
    # ... 기존 초기화 코드 ...

    # 동기화 워커 시작
    logger.info("백그라운드 동기화 워커 시작...")
    asyncio.create_task(background_sync_worker())
```

### Phase 2: 수동 동기화 트리거 (추가 엔드포인트)

**main.py에 수동 동기화 API 추가**:
```python
@app.post("/api/trigger-sync")
async def trigger_sync():
    """수동 동기화 트리거 (ADMIN Edge가 호출 가능)"""
    global last_sync_version

    try:
        documents_chunks, msg = serve_client.sync_team_chunks(TEAM_ID, last_sync_version)

        if not documents_chunks:
            return {"status": "no_changes", "message": "변경사항 없음"}

        # 동기화 로직 실행 (background_sync_worker와 동일)
        # ...

        return {
            "status": "success",
            "message": msg,
            "latest_version": last_sync_version
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🔐 보안 고려사항

1. **팀 키 캐싱**:
   - 현재 SDK는 팀 키를 메모리에 캐시 (`_team_keys_cache`)
   - Edge 서버 재시작 시 재다운로드 필요
   - 안전하게 디스크에 암호화 저장 고려 (향후)

2. **버전 롤백 방지**:
   - 클라이언트는 `lastVersion`을 로컬에 저장
   - 서버는 항상 `version > lastVersion`만 반환
   - 악의적인 `lastVersion=0` 요청 시 모든 청크 재전송 (성능 이슈)

3. **삭제된 청크 처리**:
   - `isDeleted=true`인 청크도 `version` 증가
   - 클라이언트는 삭제 플래그 확인 필수
   - 로컬 벡터스토어에서 삭제 로직 구현 필요

---

## 📊 성능 최적화

### 데이터베이스 인덱스

**VectorChunk.java:8-11**:
```java
@Index(name = "idx_team_version", columnList = "team_id, version")
```

**쿼리 성능**:
```sql
-- 효율적 (인덱스 사용)
SELECT * FROM vector_chunks
WHERE team_id = ? AND version > ?
ORDER BY version ASC;
```

### 페이징 (대량 청크 처리)

**현재**: 모든 변경 청크를 한 번에 반환
**문제**: 변경사항이 많으면 메모리/네트워크 부담
**해결**: 페이징 추가 고려

```java
// 향후 개선안
@GetMapping("/api/sync/chunks")
public ResponseEntity<List<ChunkSyncResponse>> syncTeamChunks(
        @RequestParam String teamId,
        @RequestParam(defaultValue = "0") int lastVersion,
        @RequestParam(defaultValue = "100") int limit,  // 추가
        @AuthenticationPrincipal User user) {
    // ...
}
```

---

## 🧪 테스트 시나리오

### 시나리오 1: ADMIN → MEMBER 동기화

```bash
# 1. ADMIN Edge (Edge A)에서 데이터 업로드
docker exec serve-edge-server python /app/robot_simulator.py

# 2. MEMBER Edge (Edge B)에서 동기화 확인
# test/test_sync.py 실행
python test/test_sync.py
```

### 시나리오 2: 충돌 해결

```
Edge A (v0) → 업로드 → Cloud (v1)
Edge B (v0) → 동기화 → Edge B (v1)

Edge A (v1) → 업데이트 → Cloud (v2)
Edge B (v1) → 동기화 → Edge B (v2)  ✅ 정상 동기화

Edge B (v0) → 동기화 → Cloud (v > 0) → Edge B (v0, v1, v2 모두 수신)
```

---

## 📝 TODO: 구현 체크리스트

### 즉시 구현 (Phase 1)
- [ ] main.py에 `background_sync_worker()` 추가
- [ ] `last_sync_version` 저장/로드 로직 (파일 또는 DB)
- [ ] 동기화 로그 개선 (Prometheus metrics 추가 고려)
- [ ] test/test_sync.py 작성 (동기화 시나리오 테스트)

### 향후 개선 (Phase 2)
- [ ] 로컬 벡터스토어 청크 삭제 로직
- [ ] WebSocket 기반 실시간 동기화 (필요시)
- [ ] 동기화 페이징 (대량 청크 처리)
- [ ] 팀 키 안전한 디스크 저장
- [ ] 동기화 실패 시 재시도 로직
- [ ] 동기화 통계/모니터링 대시보드

---

## 🎯 결론 및 권장사항

**현재 WSL + Docker 환경에서 권장 방안**:

1. **Pull 기반 Polling 방식 채택** (30초 간격)
   - 이미 백엔드/SDK 구현 완료
   - main.py에 동기화 워커만 추가하면 즉시 동작
   - 소규모 Edge 노드(< 10대)에서 충분히 효율적

2. **권한 분리 유지**:
   - ADMIN Edge: 업로드 + 동기화
   - MEMBER Edge: 동기화만 (읽기 전용)

3. **단계적 구현**:
   - Step 1: 백그라운드 polling 워커 (30초)
   - Step 2: 수동 동기화 트리거 API
   - Step 3 (선택): WebSocket 실시간 알림 (필요 시)

4. **보안 강화**:
   - 팀 키 안전한 저장
   - 삭제된 청크 로컬 반영
   - 버전 롤백 방지 검증

**다음 작업**: `test/test_sync.py` 작성 후 동기화 워커 구현
