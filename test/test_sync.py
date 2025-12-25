#!/usr/bin/env python3
"""
증분 동기화 테스트 스크립트
변경사항 있을 때/없을 때를 구분하여 시연
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from serve_sdk import ServeClient
import json
import time
from datetime import datetime

# 설정
CLOUD_URL = "http://172.18.0.1:8080"  # WSL 환경
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
TEAM_ID = "b67b09a2-62ea-4b1e-a181-cfad8ed3517c"

def print_separator(title=""):
    """구분선 출력"""
    if title:
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
    else:
        print("=" * 60)

def test_sync_with_changes():
    """시나리오 1: 변경사항이 있을 때 동기화"""
    print_separator("시나리오 1: 변경사항 있을 때 동기화")

    # 1. 클라이언트 생성 및 로그인
    client = ServeClient(server_url=CLOUD_URL)
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"✗ 로그인 실패: {msg}")
        return

    print(f"✓ 로그인 성공: {EDGE_EMAIL}")

    # 2. 현재 동기화 상태 확인 (초기 동기화)
    print("\n[Step 1] 초기 동기화 상태 확인...")
    last_version = 0
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, last_version)

    if documents_chunks:
        print(f"✓ {msg}")
        # 최신 버전 찾기
        for doc_id, chunks in documents_chunks.items():
            for chunk in chunks:
                if chunk['version'] > last_version:
                    last_version = chunk['version']
        print(f"  현재 최신 버전: {last_version}")
    else:
        print(f"  변경사항 없음 (lastVersion={last_version})")

    # 3. 새로운 데이터 업로드 (ADMIN이 업로드한다고 가정)
    print("\n[Step 2] 새로운 센서 데이터 업로드 중...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"TEST_SYNC_{timestamp}"

    sensor_data = {
        "robot_id": "TEST-SYNC-001",
        "temperature": 25.5,
        "pressure": 101.3,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "location": "Test Lab",
            "status": "sync_test"
        }
    }

    chunks_data = [{
        "chunkIndex": 0,
        "data": json.dumps(sensor_data, ensure_ascii=False)
    }]

    success, msg = client.upload_chunks_to_document(
        file_name=file_name,
        repo_id=TEAM_ID,
        chunks_data=chunks_data
    )

    if success:
        print(f"✓ 청크 업로드 성공: {file_name}")
    else:
        print(f"✗ 청크 업로드 실패: {msg}")
        return

    # 4. 잠시 대기 (데이터베이스 반영 대기)
    print("\n[Step 3] 데이터베이스 반영 대기 중... (2초)")
    time.sleep(2)

    # 5. 증분 동기화 실행
    print(f"\n[Step 4] 증분 동기화 실행 (lastVersion={last_version})...")
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, last_version)

    if not documents_chunks:
        print("✗ 변경사항이 감지되지 않았습니다!")
        print(f"  메시지: {msg}")
    else:
        print(f"✓ {msg}")
        print("\n변경된 청크 상세:")

        for doc_id, chunks in documents_chunks.items():
            print(f"\n  문서 ID: {doc_id[:16]}...")
            for chunk in chunks:
                chunk_idx = chunk['chunkIndex']
                version = chunk['version']
                is_deleted = chunk['isDeleted']

                if is_deleted:
                    print(f"    - 청크 #{chunk_idx} (버전: {version}) - 삭제됨")
                else:
                    data = chunk['data']
                    print(f"    - 청크 #{chunk_idx} (버전: {version})")
                    print(f"      데이터 크기: {len(data)} bytes")

                    try:
                        json_data = json.loads(data)
                        print(f"      내용: {json.dumps(json_data, indent=10, ensure_ascii=False)[:200]}...")
                    except:
                        print(f"      내용: {data[:100]}...")

                # 버전 업데이트
                if version > last_version:
                    last_version = version

        print(f"\n  업데이트된 최신 버전: {last_version}")

    print_separator()

def test_sync_without_changes():
    """시나리오 2: 변경사항이 없을 때 동기화"""
    print_separator("시나리오 2: 변경사항 없을 때 동기화")

    # 1. 클라이언트 생성 및 로그인
    client = ServeClient(server_url=CLOUD_URL)
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"✗ 로그인 실패: {msg}")
        return

    print(f"✓ 로그인 성공: {EDGE_EMAIL}")

    # 2. 현재 최신 버전 확인
    print("\n[Step 1] 현재 최신 버전 확인...")
    last_version = 0
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, last_version)

    if documents_chunks:
        print(f"✓ {msg}")
        # 최신 버전 찾기
        for doc_id, chunks in documents_chunks.items():
            for chunk in chunks:
                if chunk['version'] > last_version:
                    last_version = chunk['version']
        print(f"  현재 최신 버전: {last_version}")
    else:
        print("  초기 상태 (청크 없음)")

    # 3. 같은 버전으로 재동기화 (변경사항 없음)
    print(f"\n[Step 2] 동일 버전으로 재동기화 시도 (lastVersion={last_version})...")
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, last_version)

    if not documents_chunks:
        print(f"✓ 예상대로 변경사항 없음")
        print(f"  메시지: {msg}")
    else:
        print(f"⚠ 예상과 다름: {msg}")
        print(f"  변경된 청크 수: {sum(len(chunks) for chunks in documents_chunks.values())}")

    # 4. 이전 버전으로 동기화 (모든 변경사항 조회)
    if last_version > 0:
        old_version = max(0, last_version - 5)
        print(f"\n[Step 3] 이전 버전으로 동기화 시도 (lastVersion={old_version})...")
        documents_chunks, msg = client.sync_team_chunks(TEAM_ID, old_version)

        if documents_chunks:
            print(f"✓ {msg}")
            total_chunks = sum(len(chunks) for chunks in documents_chunks.values())
            print(f"  조회된 청크 수: {total_chunks}개")
            print(f"  버전 범위: {old_version + 1} ~ {last_version}")
        else:
            print(f"  변경사항 없음")

    print_separator()

def main():
    """메인 테스트 실행"""
    print_separator("SeRVe 증분 동기화 테스트")
    print("이 스크립트는 두 가지 시나리오를 테스트합니다:")
    print("  1. 변경사항이 있을 때 동기화")
    print("  2. 변경사항이 없을 때 동기화")
    print_separator()

    print("\n테스트 시작...")

    # 시나리오 1: 변경사항 있을 때
    test_sync_with_changes()

    print("\n\n")
    time.sleep(2)

    # 시나리오 2: 변경사항 없을 때
    test_sync_without_changes()

    print("\n")
    print_separator("모든 테스트 완료")

if __name__ == "__main__":
    main()
