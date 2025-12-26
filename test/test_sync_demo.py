#!/usr/bin/env python3
"""
증분 동기화 시연 스크립트
변경사항 있을 때 / 없을 때를 명확히 보여주는 데모
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from serve_sdk import ServeClient
import json
import time
from datetime import datetime

# 설정
CLOUD_URL = "http://172.18.0.1:8080"
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
TEAM_ID = "b67b09a2-62ea-4b1e-a181-cfad8ed3517c"

# 테스트용 고정 파일명 (user_id는 로그인 후 동적으로 설정)
TEST_FILE_NAME = None  # 로그인 후 설정됨

def print_header(title):
    """헤더 출력"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_step(step_num, desc):
    """단계 출력"""
    print(f"\n[Step {step_num}] {desc}")
    print("-" * 70)

def get_current_version(client):
    """현재 최신 버전 조회"""
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, 0)

    max_version = 0
    if documents_chunks:
        for doc_id, chunks in documents_chunks.items():
            for chunk in chunks:
                if chunk['version'] > max_version:
                    max_version = chunk['version']

    return max_version

def upload_test_chunk(client, data_value, update_count):
    """테스트 청크 업로드"""
    sensor_data = {
        "robot_id": "DEMO-001",
        "temperature": data_value,
        "update_count": update_count,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "test": "sync_demo"
        }
    }

    chunks_data = [{
        "chunkIndex": 0,
        "data": json.dumps(sensor_data, ensure_ascii=False)
    }]

    success, msg = client.upload_chunks_to_document(
        file_name=TEST_FILE_NAME,
        repo_id=TEAM_ID,
        chunks_data=chunks_data
    )

    return success, msg

def sync_and_show(client, last_version):
    """동기화 실행 및 결과 표시"""
    documents_chunks, msg = client.sync_team_chunks(TEAM_ID, last_version)

    if not documents_chunks:
        print(f"  ⚪ 변경사항 없음 (lastVersion={last_version})")
        print(f"     메시지: {msg}")
        return last_version, False

    print(f"  ✅ 변경사항 감지! (lastVersion={last_version})")
    print(f"     {msg}")

    max_version = last_version
    for doc_id, chunks in documents_chunks.items():
        for chunk in chunks:
            version = chunk['version']
            chunk_index = chunk['chunkIndex']
            is_deleted = chunk['isDeleted']

            if not is_deleted:
                data = chunk['data']
                json_data = json.loads(data)

                print(f"\n     📦 청크 정보:")
                print(f"        - 버전: {version}")
                print(f"        - temperature: {json_data.get('temperature')}")
                print(f"        - update_count: {json_data.get('update_count')}")

            if version > max_version:
                max_version = version

    return max_version, True

def main():
    """메인 데모 실행"""
    print_header("SeRVe 증분 동기화 시연")
    print("\n이 스크립트는 다음을 시연합니다:")
    print("  1. 최초 업로드 시 version=0으로 생성")
    print("  2. 동일 파일명으로 재업로드 시 version 증가")
    print("  3. 증분 동기화로 변경사항만 조회")
    print("  4. 변경사항 없을 때 동기화 결과")

    # 클라이언트 초기화
    client = ServeClient(server_url=CLOUD_URL)
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"\n✗ 로그인 실패: {msg}")
        return

    print(f"\n✓ 로그인 성공: {EDGE_EMAIL}")

    # 테스트용 파일명 설정 (user_id 포함으로 충돌 방지)
    global TEST_FILE_NAME
    user_id_short = client.session.user_id[:8] if client.session.user_id else "unknown"
    TEST_FILE_NAME = f"DEMO_FIXED_FILE_{user_id_short}"
    print(f"  테스트 파일명: {TEST_FILE_NAME}")

    # ========================================
    # Part 1: 최초 업로드
    # ========================================
    print_header("Part 1: 최초 업로드 (version=0)")

    print_step(1, f"'{TEST_FILE_NAME}' 파일을 최초로 업로드")
    success, msg = upload_test_chunk(client, 25.0, 1)

    if success:
        print(f"  ✓ 업로드 성공")
    else:
        print(f"  ✗ 업로드 실패: {msg}")
        return

    time.sleep(2)

    print_step(2, "동기화 실행 (lastVersion=0)")
    last_version = 0
    last_version, has_changes = sync_and_show(client, last_version)

    if not has_changes:
        print("\n  ℹ️  변경사항이 없습니다. 이는 새 청크가 version=0으로 생성되었기 때문입니다.")
        print("     lastVersion=0으로 조회하면 version > 0인 청크만 조회됩니다.")
        print("     따라서 새로 생성된 청크는 조회되지 않습니다.")

    # ========================================
    # Part 2: 동일 파일 업데이트 (version 증가)
    # ========================================
    print_header("Part 2: 동일 파일 업데이트 (version 증가)")

    print_step(1, f"'{TEST_FILE_NAME}' 파일을 다시 업로드 (UPDATE)")
    success, msg = upload_test_chunk(client, 26.0, 2)

    if success:
        print(f"  ✓ 업로드 성공 (기존 청크 UPDATE → version 자동 증가)")
    else:
        print(f"  ✗ 업로드 실패: {msg}")
        return

    time.sleep(2)

    print_step(2, f"동기화 실행 (lastVersion={last_version})")
    last_version, has_changes = sync_and_show(client, last_version)

    if has_changes:
        print(f"\n  🎉 성공! version이 {last_version}로 증가했습니다.")

    # ========================================
    # Part 3: 한 번 더 업데이트
    # ========================================
    print_header("Part 3: 한 번 더 업데이트")

    print_step(1, f"'{TEST_FILE_NAME}' 파일을 또 업로드")
    success, msg = upload_test_chunk(client, 27.0, 3)

    if success:
        print(f"  ✓ 업로드 성공")
    else:
        print(f"  ✗ 업로드 실패: {msg}")
        return

    time.sleep(2)

    print_step(2, f"동기화 실행 (lastVersion={last_version})")
    last_version, has_changes = sync_and_show(client, last_version)

    if has_changes:
        print(f"\n  🎉 성공! version이 {last_version}로 증가했습니다.")

    # ========================================
    # Part 4: 변경사항 없을 때
    # ========================================
    print_header("Part 4: 변경사항 없을 때")

    print_step(1, "새로운 업로드 없이 바로 동기화 시도")
    print(f"  (lastVersion={last_version} 유지)")

    time.sleep(1)

    print_step(2, f"동기화 실행 (lastVersion={last_version})")
    _, has_changes = sync_and_show(client, last_version)

    if not has_changes:
        print("\n  ✅ 예상대로 변경사항이 없습니다!")

    # ========================================
    # 완료
    # ========================================
    print_header("시연 완료")
    print(f"\n최종 동기화 버전: {last_version}")
    print(f"\n✅ 증분 동기화가 정상적으로 작동합니다!")
    print(f"   - 새 청크 INSERT: version=0")
    print(f"   - 기존 청크 UPDATE: version 자동 증가")
    print(f"   - 증분 동기화: version > lastVersion인 청크만 조회")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
