#!/usr/bin/env python3
"""
팀 간 격리 디버깅 테스트
각 API 호출을 개별적으로 테스트하여 어디서 보안 검증이 실패하는지 확인
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from serve_sdk import ServeClient
import json
from datetime import datetime

CLOUD_URL = "http://172.18.0.1:8080"

def test_team_isolation_detailed():
    """팀 간 격리 상세 테스트"""
    print("=" * 70)
    print("  팀 간 격리 상세 디버깅 테스트")
    print("=" * 70)

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
        print("\n[Step 1] Team A 생성 및 멤버 초대")
        admin_a = ServeClient(server_url=CLOUD_URL)
        admin_a.signup(admin_a_email, password)
        admin_a.login(admin_a_email, password)
        team_a_id, _ = admin_a.create_repository(f"TeamA_{timestamp}", "팀 A")
        print(f"  ✓ Team A ID: {team_a_id}")
        print(f"  ✓ Admin A email: {admin_a_email}")
        print(f"  ✓ Admin A user_id: {admin_a.session.user_id}")

        member_a = ServeClient(server_url=CLOUD_URL)
        member_a.signup(member_a_email, password)
        admin_a.invite_member(team_a_id, member_a_email)
        member_a.login(member_a_email, password)
        print(f"  ✓ Member A email: {member_a_email}")
        print(f"  ✓ Member A user_id: {member_a.session.user_id}")

        chunks_a = [{
            "chunkIndex": 0,
            "data": json.dumps({"team": "A", "secret": "Team A Secret Data"})
        }]
        member_a.upload_chunks_to_document("team_a_doc.json", team_a_id, chunks_a)
        print(f"  ✓ Team A 문서 업로드 완료")

        # 2. Team B 생성
        print("\n[Step 2] Team B 생성 및 멤버 초대")
        admin_b = ServeClient(server_url=CLOUD_URL)
        admin_b.signup(admin_b_email, password)
        admin_b.login(admin_b_email, password)
        team_b_id, _ = admin_b.create_repository(f"TeamB_{timestamp}", "팀 B")
        print(f"  ✓ Team B ID: {team_b_id}")
        print(f"  ✓ Admin B email: {admin_b_email}")
        print(f"  ✓ Admin B user_id: {admin_b.session.user_id}")

        member_b = ServeClient(server_url=CLOUD_URL)
        member_b.signup(member_b_email, password)
        admin_b.invite_member(team_b_id, member_b_email)
        member_b.login(member_b_email, password)
        print(f"  ✓ Member B email: {member_b_email}")
        print(f"  ✓ Member B user_id: {member_b.session.user_id}")

        chunks_b = [{
            "chunkIndex": 0,
            "data": json.dumps({"team": "B", "secret": "Team B Secret Data"})
        }]
        member_b.upload_chunks_to_document("team_b_doc.json", team_b_id, chunks_b)
        print(f"  ✓ Team B 문서 업로드 완료")

        # 3. Team A Member가 Team B 접근 시도 - 단계별 테스트
        print("\n" + "=" * 70)
        print("  [SECURITY TEST] Team A Member → Team B 접근 시도")
        print("=" * 70)

        print(f"\n[Step 3-1] Team A Member가 Team B 문서 목록 조회 시도")
        print(f"  요청자: {member_a_email} (user_id: {member_a.session.user_id})")
        print(f"  대상 팀: Team B (team_id: {team_b_id})")

        success, documents = member_a.api.get_documents(team_b_id, member_a.session.access_token)
        if success:
            print(f"  ✗ 보안 취약점: Team A Member가 Team B 문서 목록 조회 성공!")
            print(f"  응답 데이터: {documents}")
            return False
        else:
            print(f"  ✓ 접근 차단됨 (예상된 동작)")
            print(f"  에러 메시지: {documents}")

        print(f"\n[Step 3-2] Team A Member가 Team B 청크 동기화 시도")
        success, chunks = member_a.api.sync_team_chunks(team_b_id, -1, member_a.session.access_token)
        if success:
            print(f"  ✗ 보안 취약점: Team A Member가 Team B 청크 동기화 성공!")
            print(f"  응답 데이터: {chunks}")
            return False
        else:
            print(f"  ✓ 접근 차단됨 (예상된 동작)")
            print(f"  에러 메시지: {chunks}")

        print(f"\n[Step 3-3] Team A Member가 Team B 팀 키 조회 시도")
        success, team_key = member_a.api.get_team_key(team_b_id, member_a.session.user_id, member_a.session.access_token)
        if success:
            print(f"  ✗ 보안 취약점: Team A Member가 Team B 팀 키 조회 성공!")
            print(f"  응답 데이터: {team_key[:50]}..." if len(team_key) > 50 else team_key)
            return False
        else:
            print(f"  ✓ 접근 차단됨 (예상된 동작)")
            print(f"  에러 메시지: {team_key}")

        # 4. Team A Member가 Team A 접근 시도 - 정상 케이스
        print("\n" + "=" * 70)
        print("  [NORMAL TEST] Team A Member → Team A 접근 시도")
        print("=" * 70)

        print(f"\n[Step 4-1] Team A Member가 Team A 문서 목록 조회 시도 (정상)")
        success, documents = member_a.api.get_documents(team_a_id, member_a.session.access_token)
        if not success:
            print(f"  ✗ 오류: 자기 팀 문서 조회 실패!")
            print(f"  에러 메시지: {documents}")
            return False
        else:
            print(f"  ✓ 조회 성공 (예상된 동작)")
            print(f"  문서 수: {len(documents)}")

        print("\n" + "=" * 70)
        print("  ✅ 팀 간 격리 테스트 통과!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = test_team_isolation_detailed()
    sys.exit(0 if result else 1)
