# SeRVe Edge Server

**Zero-Trust Edge Computing Platform for Physical AI**

엣지 서버는 로봇(Physical AI)과 클라우드 사이의 보안 게이트웨이 역할을 수행합니다.

## 아키텍처

```
로봇(평문) → 엣지 서버(IDS + 암호화 + 로컬처리) → 클라우드(암호문 저장)
             ↓
         [Suricata IDS] → 공격 탐지
         [FastAPI Proxy] → 데이터 수신 및 암호화
         [VisionEngine] → 로컬 벡터DB 처리
         [Streamlit] → 관리 대시보드
```

## 주요 기능

### 1. Suricata IDS
- 포트 9000으로 들어오는 트래픽 감시
- SQL Injection, XSS 등 공격 패턴 탐지
- 미러 모드 (탐지만, 차단 없음)
- 로그: `/var/log/suricata/fast.log`

### 2. FastAPI Proxy
- **POST /api/sensor-data**: 로봇 센서 데이터 수신
- **GET /api/status**: 엣지 서버 상태 확인
- 데이터 흐름:
  1. 로봇 → JSON 데이터 수신
  2. vision_engine으로 로컬 처리 및 벡터DB 저장
  3. serve_sdk로 로그인 및 암호화
  4. 클라우드에 청크로 업로드

### 3. Streamlit Dashboard
- 포트 8501에서 접근
- 저장소/문서/멤버 관리
- 로컬 벡터DB 관리
- Vision AI 분석

## 설치 및 실행

### 사전 요구사항

1. **클라우드 서버 실행** (SeRVe-Backend)
   ```bash
   cd ../SeRVe-Backend
   ./gradlew bootRun
   ```

2. **사용자 계정 생성**
   - 웹 브라우저: `http://localhost:8080`
   - 또는 Streamlit: `http://localhost:8501`
   - 엣지 계정 생성: `edge@serve.local` / `edge123`

3. **저장소(Team) 생성**
   - Streamlit 대시보드에서 저장소 생성
   - 생성된 저장소의 **Team ID** 복사

### 설정

1. `.env` 파일 생성
   ```bash
   cd edge-server
   cp .env.example .env
   ```

2. `.env` 파일 수정
   ```bash
   CLOUD_URL=http://localhost:8080
   EDGE_EMAIL=edge@serve.local
   EDGE_PASSWORD=edge123
   TEAM_ID=your-team-id-here  # 저장소 ID 입력
   ```

### 실행

```bash
# Docker Compose로 실행
docker-compose up --build

# 또는 백그라운드 실행
docker-compose up -d --build
```

### 접속

- **Streamlit Dashboard**: http://localhost:8501
- **FastAPI Proxy**: http://localhost:9000
- **API 문서**: http://localhost:9001/docs (컨테이너 내부)

## 시연 시나리오

### 터미널 4개 준비

#### 터미널 1: 엣지 서버 실행
```bash
cd edge-server
docker-compose up
```

출력:
```
✓ Suricata IDS 시작
✓ FastAPI Proxy 시작 (포트 9001)
✓ Nginx 프록시 시작 (포트 9000)
✓ Streamlit 대시보드 시작 (포트 8501)
```

#### 터미널 2: 정상 데이터 전송
```bash
cd edge-server
python robot_simulator.py
```

출력:
```
[NORMAL MODE] Sending data at 14:30:15
Robot ID: AGV-001
✓ Response: 200
  {'status': 'success', 'message': 'Data encrypted and uploaded to cloud'}
```

#### 터미널 3: Suricata 로그 모니터링
```bash
# 로컬 로그 (호스트)
tail -f edge-server/logs/suricata/fast.log

# 또는 컨테이너 내부
docker exec -it serve-edge-server tail -f /var/log/suricata/fast.log
```

정상 상태:
```
(로그 없음 - 정상 트래픽)
```

#### 터미널 4: 공격 데이터 전송
```bash
cd edge-server
python robot_simulator.py --attack
```

출력:
```
[ATTACK MODE] Sending data at 14:32:10
Robot ID: AGV-001'; DROP TABLE users;--
⚠️  ATTACK PAYLOAD DETECTED:
{
  "robot_id": "AGV-001'; DROP TABLE users;--",
  "temperature": 25.3,
  "pressure": 101.2,
  "timestamp": "2024-12-24T14:32:10"
}
✓ Response: 200
```

**Suricata 로그 (터미널 3):**
```
12/24/2024-14:32:10.123456 [**] [1:1000001:1] SQL Injection - DROP TABLE [**]
12/24/2024-14:32:10.123457 [**] [1:1000004:1] SQL Injection - Comment Markers [**]
```

### 예상 결과

1. **정상 모드**:
   - 로봇 → 센서 데이터 전송
   - 엣지 서버 → 로컬 벡터DB 저장 + 암호화 후 클라우드 업로드
   - Suricata → 로그 없음

2. **공격 모드**:
   - 로봇 → SQL Injection 페이로드 전송
   - 엣지 서버 → 데이터 수신 및 처리 (정상 동작)
   - **Suricata → 공격 탐지 및 로그 기록**

## 로봇 시뮬레이터 사용법

### 기본 사용
```bash
python robot_simulator.py
```

### 옵션
```bash
# 공격 모드
python robot_simulator.py --attack

# 전송 간격 변경 (5초)
python robot_simulator.py --interval 5

# 10회만 전송 후 종료
python robot_simulator.py --count 10

# 모든 옵션 조합
python robot_simulator.py --attack --interval 2 --count 5
```

### 커스텀 설정
```bash
# 다른 로봇 ID 사용
python robot_simulator.py --robot-id AGV-002

# 다른 엣지 서버 주소
python robot_simulator.py --url http://remote-edge:9000/api/sensor-data
```

## 로그 확인

### Suricata IDS 로그
```bash
# 실시간 모니터링
tail -f logs/suricata/fast.log

# 최근 50줄
tail -n 50 logs/suricata/fast.log

# SQL Injection 탐지만 필터링
grep "SQL Injection" logs/suricata/fast.log
```

### FastAPI 로그
```bash
tail -f logs/supervisor/fastapi.log
```

### Streamlit 로그
```bash
tail -f logs/supervisor/streamlit.log
```

### 모든 로그
```bash
tail -f logs/supervisor/*.log
```

## 문제 해결

### 1. 엣지 서버가 클라우드에 연결되지 않음
```bash
# .env 파일 확인
cat .env

# 클라우드 서버 실행 확인
curl http://localhost:8080/actuator/health

# 로그 확인
docker-compose logs edge-server | grep "Cloud login"
```

### 2. Suricata가 트래픽을 탐지하지 않음
```bash
# Suricata 실행 확인
docker exec -it serve-edge-server ps aux | grep suricata

# Suricata 로그 확인
docker exec -it serve-edge-server tail /var/log/suricata/suricata.log

# 네트워크 인터페이스 확인
docker exec -it serve-edge-server ip addr
```

### 3. 로봇 시뮬레이터 연결 실패
```bash
# 엣지 서버 상태 확인
curl http://localhost:9000/api/status

# 포트 확인
netstat -an | grep 9000

# Docker 컨테이너 상태 확인
docker ps
```

### 4. TEAM_ID 찾기
```bash
# Streamlit 대시보드에서 저장소 목록 확인
# 또는 클라우드 서버 로그 확인
cd ../SeRVe-Backend
./gradlew bootRun | grep "Created repository"
```

## 디렉토리 구조

```
edge-server/
├── Dockerfile              # All-in-one 이미지
├── docker-compose.yml      # 컨테이너 실행 설정
├── supervisord.conf        # 멀티 프로세스 관리
├── nginx.conf              # 트래픽 프록시 설정
├── .env                    # 환경변수 (생성 필요)
├── .env.example            # 환경변수 예제
├── robot_simulator.py      # 로봇 시뮬레이터
├── src/
│   └── main.py             # FastAPI 앱
├── suricata/
│   └── custom.rules        # Suricata 커스텀 룰
└── logs/                   # 로그 디렉토리 (자동 생성)
    ├── edge-server/
    ├── suricata/
    ├── supervisor/
    └── nginx/
```

## 보안 고려사항

1. **Zero-Trust 아키텍처**
   - 모든 데이터는 엣지에서 암호화
   - 클라우드는 암호문만 저장
   - 개인키는 절대 서버에 전송하지 않음

2. **IDS (Intrusion Detection System)**
   - Suricata는 미러 모드로 동작 (탐지만, 차단 없음)
   - 실제 차단은 FastAPI에서 구현 가능 (향후 확장)

3. **로컬 처리**
   - 민감한 데이터는 로컬 벡터DB에서 처리
   - 클라우드 전송은 최소화

## 라이센스

MIT License

## 기여

Pull requests are welcome!

## 문의

Issues: https://github.com/your-repo/SeRVe-Project/issues
