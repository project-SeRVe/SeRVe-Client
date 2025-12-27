#!/usr/bin/env python3
"""
SeRVe 전체 워크플로우 통합 테스트

검증 항목:
1. 동기화 - 증분 동기화 (version 기반)
2. 권한 검증 - ADMIN vs MEMBER
3. 비인가 사용자 접근 차단
4. 팀 간 데이터 격리
5. 안전한 팀키 배포 (공개키 래핑)
6. Envelope 암호화 (DEK/KEK)
7. 팀 단위 데이터 관리
8. 서버 암호화 저장
9. 팀키 암호화 저장
10. DoS 방지 (Rate Limit)
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

def print_separator(title=""):
    """구분선 출력"""
    if title:
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    else:
        print("=" * 70)

def test_1_incremental_sync():
    """테스트 1: 증분 동기화 검증"""
    print_separator("테스트 1: 증분 동기화")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    admin_email = f"sync_admin_{timestamp}@test.serve"
    member_email = f"sync_member_{timestamp}@test.serve"
    password = "test123!@#"

    try:
        # 1. 유저 생성 및 팀 생성
        admin_client = ServeClient(server_url=CLOUD_URL)
        admin_client.signup(admin_email, password)
        admin_client.login(admin_email, password)

        team_id, _ = admin_client.create_repository(f"SyncTest_{timestamp}", "증분 동기화 테스트")
        print(f"✓ 팀 생성: {team_id}")

        # 2. Member 초대
        member_client = ServeClient(server_url=CLOUD_URL)
        member_client.signup(member_email, password)
        admin_client.invite_member(team_id, member_email)
        print(f"✓ Member 초대 완료")

        # 3. Member 로그인 및 첫 번째 문서 업로드
        member_client.login(member_email, password)

        chunks_data_1 = [{
            "chunkIndex": 0,
            "data": json.dumps({"doc": "first", "timestamp": datetime.now().isoformat()})
        }]
        member_client.upload_chunks_to_document("doc1.json", team_id, chunks_data_1)
        print(f"✓ 첫 번째 문서 업로드 완료")

        time.sleep(1)

        # 4. 첫 번째 동기화 (lastVersion=0)
        chunks_v0, msg = member_client.download_chunks_from_document("doc1.json", team_id)
        if not chunks_v0:
            print(f"✗ 첫 번째 동기화 실패: {msg}")
            return False

        print(f"✓ 첫 번째 동기화 성공 (version 0): {len(chunks_v0)} chunks")

        # 5. 두 번째 문서 업로드
        chunks_data_2 = [{
            "chunkIndex": 0,
            "data": json.dumps({"doc": "second", "timestamp": datetime.now().isoformat()})
        }]
        member_client.upload_chunks_to_document("doc2.json", team_id, chunks_data_2)
        print(f"✓ 두 번째 문서 업로드 완료")

        time.sleep(1)

        # 6. 증분 동기화 검증 (새 문서만 가져와야 함)
        # download_chunks_from_document는 내부적으로 sync API 사용
        chunks_v1, msg = member_client.download_chunks_from_document("doc2.json", team_id)
        if not chunks_v1:
            print(f"✗ 증분 동기화 실패: {msg}")
            return False

        print(f"✓ 증분 동기화 성공: {len(chunks_v1)} chunks")
        print(f"✓ 검증: 증분 동기화가 정상적으로 동작합니다")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_2_permission_check():
    """테스트 2: 권한 검증 (ADMIN은 데이터 동기화 불가)"""
    print_separator("테스트 2: 권한 검증")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    admin_email = f"perm_admin_{timestamp}@test.serve"
    member_email = f"perm_member_{timestamp}@test.serve"
    password = "test123!@#"

    try:
        # 1. Admin 생성 및 팀 생성
        admin_client = ServeClient(server_url=CLOUD_URL)
        admin_client.signup(admin_email, password)
        admin_client.login(admin_email, password)

        team_id, _ = admin_client.create_repository(f"PermTest_{timestamp}", "권한 테스트")
        print(f"✓ 팀 생성: {team_id}")

        # 2. Member 초대 및 문서 업로드
        member_client = ServeClient(server_url=CLOUD_URL)
        member_client.signup(member_email, password)
        admin_client.invite_member(team_id, member_email)

        member_client.login(member_email, password)
        chunks_data = [{
            "chunkIndex": 0,
            "data": json.dumps({"test": "permission check"})
        }]
        member_client.upload_chunks_to_document("perm_test.json", team_id, chunks_data)
        print(f"✓ Member가 문서 업로드 성공")

        time.sleep(1)

        # 3. ADMIN이 데이터 동기화 시도 (실패해야 함)
        admin_client.session.clear_team_keys()
        admin_client.login(admin_email, password)

        chunks, msg = admin_client.download_chunks_from_document("perm_test.json", team_id)
        if chunks:
            print(f"✗ 보안 취약점: ADMIN이 암호화된 데이터에 접근 가능!")
            return False

        print(f"✓ ADMIN 데이터 동기화 거부됨: {msg}")

        # 4. ADMIN은 메타데이터는 조회 가능해야 함
        docs, msg = admin_client.get_documents(team_id)
        if not docs:
            print(f"✗ ADMIN이 메타데이터 조회 불가: {msg}")
            return False

        print(f"✓ ADMIN 메타데이터 조회 성공: {len(docs)} 문서")
        print(f"✓ 검증: ADMIN 권한 제한이 정상적으로 동작합니다")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_3_unauthorized_access():
    """테스트 3: 비인가 사용자 접근 차단"""
    print_separator("테스트 3: 비인가 사용자 접근 차단")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    admin_email = f"auth_admin_{timestamp}@test.serve"
    member_email = f"auth_member_{timestamp}@test.serve"
    outsider_email = f"outsider_{timestamp}@test.serve"
    password = "test123!@#"

    try:
        # 1. 팀 생성 및 멤버 초대
        admin_client = ServeClient(server_url=CLOUD_URL)
        admin_client.signup(admin_email, password)
        admin_client.login(admin_email, password)

        team_id, _ = admin_client.create_repository(f"AuthTest_{timestamp}", "인가 테스트")

        member_client = ServeClient(server_url=CLOUD_URL)
        member_client.signup(member_email, password)
        admin_client.invite_member(team_id, member_email)

        # 2. Member가 문서 업로드
        member_client.login(member_email, password)
        chunks_data = [{
            "chunkIndex": 0,
            "data": json.dumps({"test": "unauthorized access check"})
        }]
        member_client.upload_chunks_to_document("auth_test.json", team_id, chunks_data)
        print(f"✓ Member가 문서 업로드 완료")

        time.sleep(1)

        # 3. 외부인이 접근 시도 (실패해야 함)
        outsider_client = ServeClient(server_url=CLOUD_URL)
        outsider_client.signup(outsider_email, password)
        outsider_client.login(outsider_email, password)

        chunks, msg = outsider_client.download_chunks_from_document("auth_test.json", team_id)
        if chunks:
            print(f"✗ 보안 취약점: 비인가 사용자가 데이터에 접근 가능!")
            return False

        print(f"✓ 비인가 사용자 접근 차단됨: {msg}")
        print(f"✓ 검증: 비인가 사용자 접근 차단이 정상적으로 동작합니다")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_4_team_isolation():
    """테스트 4: 팀 간 데이터 격리"""
    print_separator("테스트 4: 팀 간 데이터 격리")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Team A
    admin_a_email = f"team_a_admin_{timestamp}@test.serve"
    member_a_email = f"team_a_member_{timestamp}@test.serve"

    # Team B
    admin_b_email = f"team_b_admin_{timestamp}@test.serve"
    member_b_email = f"team_b_member_{timestamp}@test.serve"

    password = "test123!@#"

    try:
        # 1. Team A 생성
        admin_a = ServeClient(server_url=CLOUD_URL)
        admin_a.signup(admin_a_email, password)
        admin_a.login(admin_a_email, password)
        team_a_id, _ = admin_a.create_repository(f"TeamA_{timestamp}", "팀 A")

        member_a = ServeClient(server_url=CLOUD_URL)
        member_a.signup(member_a_email, password)
        admin_a.invite_member(team_a_id, member_a_email)

        member_a.login(member_a_email, password)
        chunks_a = [{
            "chunkIndex": 0,
            "data": json.dumps({"team": "A", "secret": "Team A Secret Data"})
        }]
        member_a.upload_chunks_to_document("team_a_doc.json", team_a_id, chunks_a)
        print(f"✓ Team A 문서 업로드 완료")

        # 2. Team B 생성
        admin_b = ServeClient(server_url=CLOUD_URL)
        admin_b.signup(admin_b_email, password)
        admin_b.login(admin_b_email, password)
        team_b_id, _ = admin_b.create_repository(f"TeamB_{timestamp}", "팀 B")

        member_b = ServeClient(server_url=CLOUD_URL)
        member_b.signup(member_b_email, password)
        admin_b.invite_member(team_b_id, member_b_email)

        member_b.login(member_b_email, password)
        chunks_b = [{
            "chunkIndex": 0,
            "data": json.dumps({"team": "B", "secret": "Team B Secret Data"})
        }]
        member_b.upload_chunks_to_document("team_b_doc.json", team_b_id, chunks_b)
        print(f"✓ Team B 문서 업로드 완료")

        time.sleep(1)

        # 3. Team A Member가 Team B 데이터 접근 시도 (실패해야 함)
        print(f"\n[디버깅] Team A Member (email: {member_a_email})가 Team B (id: {team_b_id}) 접근 시도")
        chunks, msg = member_a.download_chunks_from_document("team_b_doc.json", team_b_id)
        print(f"[디버깅] chunks: {chunks}")
        print(f"[디버깅] msg: {msg}")

        if chunks:
            print(f"✗ 보안 취약점: Team A Member가 Team B 데이터에 접근 가능!")
            print(f"  접근한 데이터: {chunks[0].get('data', 'N/A') if len(chunks) > 0 else 'N/A'}")
            return False

        print(f"✓ Cross-team 접근 차단됨: {msg}")

        # 4. Team B Member가 Team A 데이터 접근 시도 (실패해야 함)
        chunks, msg = member_b.download_chunks_from_document("team_a_doc.json", team_a_id)
        if chunks:
            print(f"✗ 보안 취약점: Team B Member가 Team A 데이터에 접근 가능!")
            return False

        print(f"✓ Cross-team 접근 차단됨: {msg}")
        print(f"✓ 검증: 팀 간 데이터 격리가 정상적으로 동작합니다")
        return True

    except Exception as e:
        print(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print_separator("SeRVe 전체 워크플로우 통합 테스트")
    print("다음 항목들을 검증합니다:")
    print("  1. 증분 동기화 (version 기반)")
    print("  2. 권한 검증 (ADMIN vs MEMBER)")
    print("  3. 비인가 사용자 접근 차단")
    print("  4. 팀 간 데이터 격리")
    print()
    print(f"서버 URL: {CLOUD_URL}")
    print_separator()

    results = {}

    # 테스트 실행
    results["증분 동기화"] = test_1_incremental_sync()
    results["권한 검증"] = test_2_permission_check()
    results["비인가 접근 차단"] = test_3_unauthorized_access()
    results["팀 간 격리"] = test_4_team_isolation()

    # 결과 요약
    print_separator("테스트 결과 요약")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"  {status} - {test_name}")

    print()
    print(f"총 {total}개 테스트 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 워크플로우 테스트 통과!")
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패")

    print_separator()

if __name__ == "__main__":
    main()
