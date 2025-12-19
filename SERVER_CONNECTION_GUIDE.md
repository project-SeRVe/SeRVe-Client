# 서버 연결 기능 가이드

## 개요

SeRVe 클라이언트는 이제 **서버 연결 없이도 실행**되며, UI에서 **동적으로 서버 주소를 변경**할 수 있습니다.

## 주요 기능

### 1. 서버 연결 화면
첫 실행 시 서버 연결 화면이 나타납니다.

- **서버 URL 입력**: 연결할 서버 주소 입력 (예: `http://localhost:8080`)
- **서버 연결 버튼**: 입력한 주소로 서버 연결 테스트
- **데모 모드**: 서버 없이 UI만 확인 가능

### 2. 서버 연결 테스트
연결 버튼 클릭 시:
1. `/actuator/health` 엔드포인트로 헬스 체크 시도
2. 실패 시 루트 경로(`/`)로 재시도
3. 응답이 있으면 연결 성공으로 간주

### 3. 동적 서버 URL 변경
- 로그인 전/후 모든 화면에서 서버 주소 변경 가능
- 사이드바의 "서버 연결 변경" 버튼 클릭
- 새로운 서버 주소 입력 후 재연결

## 사용 방법

### 서버 연결 모드 (권장)

```bash
# 1. SeRVe 서버 실행
cd SeRVe
./gradlew bootRun

# 2. 클라이언트 실행
cd SeRVe-Client
streamlit run app.py

# 3. 브라우저에서 http://localhost:8501 접속
# 4. 서버 URL 입력: http://localhost:8080
# 5. '서버 연결' 버튼 클릭
```

### 데모 모드 (서버 없이)

```bash
# 1. 클라이언트만 실행
cd SeRVe-Client
streamlit run app.py

# 2. 브라우저에서 접속
# 3. "서버 연결 없이 데모 모드로 실행" 체크
# 4. "데모 모드로 계속" 버튼 클릭
```

**주의**: 데모 모드에서는 서버 통신이 필요한 기능이 오류를 발생시킵니다.

## 기술적 세부사항

### ServeConnector 수정

```python
class ServeConnector:
    def __init__(self, server_url=None):
        # 서버 URL을 동적으로 설정 가능
        self.server_url = server_url if server_url else config.SERVER_URL

    def _get_server_url(self):
        """현재 서버 URL 반환 (config 모듈에서 최신 값 가져오기)"""
        return config.SERVER_URL if hasattr(config, 'SERVER_URL') else self.server_url
```

모든 API 호출 시 `self._get_server_url()`로 최신 서버 URL을 가져옵니다.

### Streamlit UI 수정

**세션 상태 추가**:
```python
st.session_state.server_connected = False  # 서버 연결 상태
st.session_state.server_url = SERVER_URL   # 현재 서버 URL
```

**3단계 화면 구조**:
1. 서버 연결 화면 (`not server_connected`)
2. 로그인/회원가입 화면 (`server_connected and not logged_in`)
3. 메인 애플리케이션 (`server_connected and logged_in`)

### 에러 처리

모든 서버 통신 메서드에 try-catch 블록 추가:

```python
try:
    success, msg = st.session_state.serve_conn.login(email, password)
    # ...
except Exception as e:
    st.error(f"로그인 중 오류 발생: {str(e)}")
    st.info("서버 연결을 확인해주세요.")
```

## 서버 연결 상태 표시

### 사이드바 (모든 화면)
- ✅ 연결됨: `http://localhost:8080`
- 서버 연결 변경 버튼

## 다양한 서버 주소 예시

### 로컬 개발
```
http://localhost:8080
```

### WSL 환경
```
http://172.28.160.1:8080
```

### 원격 서버
```
http://192.168.1.100:8080
https://serve.example.com
```

## 문제 해결

### 연결 실패 시
1. 서버가 실행 중인지 확인
2. 포트 번호가 정확한지 확인
3. 방화벽 설정 확인
4. 서버 로그 확인

### 데모 모드에서 기능 테스트
- UI 레이아웃 확인 가능
- 버튼 및 탭 구조 확인 가능
- 실제 데이터 처리는 불가능

## 이점

1. **오프라인 개발**: UI 개발 시 서버 없이 작업 가능
2. **유연한 연결**: 여러 서버 환경 간 쉬운 전환
3. **에러 복원력**: 서버 오류 시 명확한 메시지 표시
4. **사용자 경험**: 서버 문제와 클라이언트 문제 구분 가능
