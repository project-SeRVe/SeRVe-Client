# SeRVe-Client
Python script for Robot Client (Physical AI)

# 세팅 (Conda 환경 기준)

WSL 및 Linux 환경에서의 클라이언트 세팅 방법입니다.
(패키지 관리를 위해 Conda 사용을 권장합니다.)

## 0. Miniconda 설치 (없을 경우)

Conda 명령어를 사용하기 위해 Miniconda 설치가 필요합니다. 이미 설치되어 있다면 건너뛰세요.

```bash
# 1. 설치 파일 다운로드 및 디렉토리 생성
mkdir -p ~/miniconda3
wget [https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh](https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh) -O ~/miniconda3/miniconda.sh

# 2. 설치 스크립트 실행
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3

# 3. 설치 파일 삭제
rm -rf ~/miniconda3/miniconda.sh

# 4. Conda 초기화 및 쉘 재시작 (명령어 인식 활성화)
~/miniconda3/bin/conda init bash
source ~/.bashrc
```

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
