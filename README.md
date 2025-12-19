# SeRVe-Client
Python script for Robot Client (Physical AI)

# 세팅 (Conda 환경 기준)

WSL 및 Linux 환경에서의 클라이언트 세팅 방법입니다.
(Windows 파일 시스템 접근 속도 이슈로 인해 Conda 사용을 권장합니다.)

## 1. 실행 환경설정

```bash
# 1. Conda 가상환경 생성 (Python 3.10)
conda create -n serve-client python=3.10 -y

# 2. 가상환경 활성화
conda activate serve-client

# 3. 의존성 패키지 설치
pip install -r requirements.txt
```

## 2. Ollama 설치 및 사용 (Vision AI)

실제로 추론을 수행하려면 로컬에 Ollama가 설치되어 있고, LLaVA 모델이 실행 가능한 상태여야 합니다.

* [Ollama Quickstart 가이드](https://docs.ollama.com/quickstart)
* 모델 다운로드 예시: `ollama pull llava`

## 3. Client 실행하는 법

### GUI 대시보드 (웹 인터페이스)
```bash
# 가상환경 활성화
conda activate serve-client

# 앱 실행
streamlit run app.py
```

### CLI 시뮬레이션 (자동화 테스트)
```bash
python main.py
```
