import os

# 백엔드 서버 주소 (환경 변수가 있으면 쓰고, 없으면 기본값 localhost 사용)
CLOUD_URL = os.getenv("CLOUD_URL", "http://localhost:8080")