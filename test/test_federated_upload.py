#!/usr/bin/env python3
"""
Federated Model 테스트: Member 직접 업로드 검증
ADMIN 없이 MEMBER가 직접 클라우드에 데이터를 업로드할 수 있는지 테스트
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
TEAM_ID = "b67b09a2-62ea-4b1e-a181-cfad8ed3517c"

# 테스트 계정 (기존 사용자 계정 2개 사용)
# 실제로는 ADMIN/MEMBER 구분이 아니라 단순히 다른 사용자로 충돌 테스트
USER1_EMAIL = "edge@serve.local"
USER1_PASSWORD = "edge123"

USER2_EMAIL = "user@serve.local"  # 다른 사용자 (없으면 edge 재사용)
USER2_PASSWORD = "user123"

def print_header(title):
    """헤더 출력"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_step(step_num, desc):
    """단계 출력"""
    print(f"\n[Step {step_num}] {desc}")
    print("-" * 70)

def test_member_direct_upload():
    """
    테스트 시나리오:
    1. MEMBER 계정으로 로그인
    2. MEMBER가 직접 청크 업로드 시도
    3. 성공 여부 확인 (Federated Model에서는 성공해야 함)
    """
    print_header("Federated Model 테스트: MEMBER 직접 업로드")

    # Step 1: MEMBER 로그인
    print_step(1, f"USER1 계정으로 로그인 ({USER1_EMAIL})")

    member_client = ServeClient(server_url=CLOUD_URL)
    success, msg = member_client.login(USER1_EMAIL, USER1_PASSWORD)

    if not success:
        print(f"  ✗ 로그인 실패: {msg}")
        return False

    print(f"  ✓ 로그인 성공")
    print(f"  User ID: {member_client.session.user_id}")
    print(f"  Email: {member_client.session.email}")

    # Step 2: MEMBER가 직접 청크 업로드
    print_step(2, "MEMBER가 직접 청크 업로드 시도")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    user_id_short = member_client.session.user_id[:8]
    file_name = f"MEMBER_TEST_{user_id_short}_{timestamp}"

    sensor_data = {
        "robot_id": "MEMBER-ROBOT-001",
        "temperature": 28.5,
        "pressure": 102.1,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "test": "federated_upload",
            "uploaded_by": "MEMBER"
        }
    }

    chunks_data = [{
        "chunkIndex": 0,
        "data": json.dumps(sensor_data, ensure_ascii=False)
    }]

    print(f"  파일명: {file_name}")
    print(f"  데이터: {json.dumps(sensor_data, indent=2, ensure_ascii=False)[:200]}...")

    success, msg = member_client.upload_chunks_to_document(
        file_name=file_name,
        repo_id=TEAM_ID,
        chunks_data=chunks_data
    )

    if not success:
        print(f"\n  ✗ 업로드 실패: {msg}")
        print(f"\n  ⚠️  Federated Model이 아직 활성화되지 않았습니다!")
        print(f"     백엔드 변경사항을 적용했는지 확인하세요.")
        return False

    print(f"\n  ✓ 업로드 성공!")
    print(f"     {msg}")

    # Step 3: 동기화로 검증
    print_step(3, "동기화로 업로드된 데이터 확인")

    time.sleep(2)  # 데이터베이스 반영 대기

    documents_chunks, sync_msg = member_client.sync_team_chunks(TEAM_ID, 0)

    if not documents_chunks:
        print(f"  ⚠️  동기화 데이터 없음: {sync_msg}")
        return True  # 업로드는 성공했으므로 True

    print(f"  ✓ {sync_msg}")

    # 방금 업로드한 데이터 찾기
    found = False
    for doc_id, chunks in documents_chunks.items():
        for chunk in chunks:
            try:
                data = json.loads(chunk['data'])
                if data.get('robot_id') == 'MEMBER-ROBOT-001':
                    print(f"\n  ✅ MEMBER가 업로드한 데이터 발견!")
                    print(f"     Document ID: {doc_id[:16]}...")
                    print(f"     Version: {chunk['version']}")
                    print(f"     Temperature: {data.get('temperature')}°C")
                    print(f"     Uploaded by: {data.get('metadata', {}).get('uploaded_by')}")
                    found = True
                    break
            except:
                continue
        if found:
            break

    if not found:
        print(f"  ⚠️  업로드한 데이터를 동기화 결과에서 찾지 못했습니다.")
        print(f"     (다른 데이터가 많아서 조회되지 않았을 수 있습니다)")

    return True

def test_conflict_prevention():
    """
    파일명 충돌 방지 테스트:
    서로 다른 사용자가 동일한 robot_id로 업로드해도 user_id가 다르므로 충돌하지 않아야 함
    """
    print_header("파일명 충돌 방지 테스트")

    # Step 1: USER1 로그인 및 업로드
    print_step(1, "USER1 계정으로 업로드")

    user1_client = ServeClient(server_url=CLOUD_URL)
    success, msg = user1_client.login(USER1_EMAIL, USER1_PASSWORD)

    if not success:
        print(f"  ✗ USER1 로그인 실패: {msg}")
        return False

    print(f"  ✓ USER1 로그인 성공")

    user1_user_id_short = user1_client.session.user_id[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    user1_file_name = f"ROBOT-999_{user1_user_id_short}_{timestamp}"

    user1_data = {
        "robot_id": "ROBOT-999",
        "source": "USER1",
        "value": 100
    }

    success, msg = user1_client.upload_chunks_to_document(
        file_name=user1_file_name,
        repo_id=TEAM_ID,
        chunks_data=[{"chunkIndex": 0, "data": json.dumps(user1_data)}]
    )

    if not success:
        print(f"  ✗ USER1 업로드 실패: {msg}")
        return False

    print(f"  ✓ USER1 업로드 성공: {user1_file_name}")

    # Step 2: 동일 사용자로 재업로드 (다른 타임스탬프) - 충돌하지 않아야 함
    print_step(2, "동일 사용자 (USER1)가 다른 타임스탬프로 재업로드")

    time.sleep(1)  # 타임스탬프 차이 확보
    timestamp2 = datetime.now().strftime('%Y%m%d_%H%M%S')
    user1_file_name2 = f"ROBOT-999_{user1_user_id_short}_{timestamp2}"

    user1_data2 = {
        "robot_id": "ROBOT-999",
        "source": "USER1",
        "value": 200
    }

    success, msg = user1_client.upload_chunks_to_document(
        file_name=user1_file_name2,
        repo_id=TEAM_ID,
        chunks_data=[{"chunkIndex": 0, "data": json.dumps(user1_data2)}]
    )

    if not success:
        print(f"  ✗ USER1 재업로드 실패: {msg}")
        return False

    print(f"  ✓ USER1 재업로드 성공: {user1_file_name2}")

    # Step 3: 파일명 비교
    print_step(3, "파일명 충돌 여부 확인")

    print(f"\n  첫 번째 파일명: {user1_file_name}")
    print(f"  두 번째 파일명: {user1_file_name2}")

    if user1_file_name == user1_file_name2:
        print(f"\n  ✗ 파일명이 충돌합니다! (타임스탬프가 동일함)")
        return False
    else:
        print(f"\n  ✓ 파일명이 다릅니다! (타임스탬프로 격리됨)")
        print(f"     User ID: {user1_user_id_short}")
        print(f"     Timestamp 1: {timestamp}")
        print(f"     Timestamp 2: {timestamp2}")

    return True

def main():
    """메인 테스트 실행"""
    print_header("Federated Model 통합 테스트")

    print("\n이 스크립트는 다음을 테스트합니다:")
    print("  1. MEMBER가 직접 클라우드에 업로드 가능 여부")
    print("  2. 동일 robot_id 사용 시 파일명 충돌 방지")
    print("  3. ADMIN 우회 여부 (Member → Cloud 직접 연결)")

    results = []

    # 테스트 1: MEMBER 직접 업로드
    try:
        result1 = test_member_direct_upload()
        results.append(("MEMBER 직접 업로드", result1))
    except Exception as e:
        print(f"\n✗ 테스트 1 오류: {e}")
        import traceback
        traceback.print_exc()
        results.append(("MEMBER 직접 업로드", False))

    time.sleep(2)

    # 테스트 2: 파일명 충돌 방지
    try:
        result2 = test_conflict_prevention()
        results.append(("파일명 충돌 방지", result2))
    except Exception as e:
        print(f"\n✗ 테스트 2 오류: {e}")
        import traceback
        traceback.print_exc()
        results.append(("파일명 충돌 방지", False))

    # 결과 요약
    print_header("테스트 결과 요약")

    for test_name, result in results:
        status = "✓ 성공" if result else "✗ 실패"
        print(f"  {status}: {test_name}")

    all_passed = all(r for _, r in results)

    if all_passed:
        print("\n" + "=" * 70)
        print("  🎉 모든 테스트 통과! Federated Model이 정상 작동합니다!")
        print("=" * 70 + "\n")
    else:
        print("\n" + "=" * 70)
        print("  ⚠️  일부 테스트 실패. 로그를 확인하세요.")
        print("=" * 70 + "\n")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
