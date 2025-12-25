#!/usr/bin/env python3
"""
간단한 청크 다운로드 테스트
특정 파일명으로 청크 다운로드 및 복호화 확인
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from serve_sdk import ServeClient
import json

# 설정
CLOUD_URL = "http://172.18.0.1:8080"  # WSL 환경: Docker 컨테이너에서 호스트 접근
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
TEAM_ID = "b67b09a2-62ea-4b1e-a181-cfad8ed3517c"

# 테스트할 파일명 (최근 업로드된 파일)
TEST_FILE_NAME = "AGV-001_20251225_122604"

def main():
    print("=" * 60)
    print(f"청크 다운로드 테스트: {TEST_FILE_NAME}")
    print("=" * 60)

    # 1. 클라이언트 생성 및 로그인
    client = ServeClient(server_url=CLOUD_URL)
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"✗ 로그인 실패: {msg}")
        return

    print(f"✓ 로그인 성공: {EDGE_EMAIL}")

    # 2. 청크 다운로드 및 복호화
    print(f"\n파일명으로 청크 다운로드 시도: {TEST_FILE_NAME}")
    chunks, msg = client.download_chunks_from_document(TEST_FILE_NAME, TEAM_ID)

    if chunks is None:
        print(f"✗ 청크 다운로드 실패: {msg}")
        return

    print(f"✓ {len(chunks)}개 청크 다운로드 및 복호화 성공")

    # 3. 청크 내용 출력
    for chunk in chunks:
        chunk_idx = chunk.get('chunkIndex')
        data = chunk.get('data')
        version = chunk.get('version')

        print(f"\n청크 #{chunk_idx} (버전: {version})")
        print(f"데이터 크기: {len(data)} bytes")

        # JSON 파싱 시도
        try:
            json_data = json.loads(data)
            print(f"JSON 내용:")
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"원시 데이터: {data[:200]}...")

    print("\n" + "=" * 60)
    print("테스트 완료 - 다운로드 및 복호화 성공!")
    print("=" * 60)

if __name__ == "__main__":
    main()
