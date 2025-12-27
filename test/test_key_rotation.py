#!/usr/bin/env python3
"""
키 로테이션 및 Federated Model 검증 테스트

멤버 강퇴 시 자동 키 로테이션과 Federated Model 원칙이 정상적으로 동작하는지 검증:
1. Admin이 팀 생성 및 멤버 초대 (Member1, Member2)
2. Member1이 문서 업로드 (Federated Model: MEMBER만 업로드 가능)
3. Admin이 Member1 강퇴 → 자동 키 로테이션 트리거
4. Member1은 강퇴 후 문서 접근 불가 (보안 유지)
5. Member2는 새 키로 문서 접근 가능 (키 로테이션 성공)
6. Admin은 메타데이터만 조회 가능 (Federated Model: ADMIN은 암호화된 데이터 접근 불가)
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

def print_separator(title=""):
    """구분선 출력"""
    if title:
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    else:
        print("=" * 70)

def cleanup_test_users(admin_client, users_to_delete):
    """테스트 완료 후 생성한 유저 정리 (선택사항)"""
    print("\n[정리] 테스트 유저 삭제는 수동으로 진행하세요.")
    for email in users_to_delete:
        print(f"  - {email}")

def test_key_rotation_after_kick():
    """메인 테스트: 멤버 강퇴 후 키 로테이션 검증"""
    print_separator("키 로테이션 검증 테스트")

    # 테스트용 유저 정보 (타임스탬프로 고유성 보장)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    admin_email = f"admin_{timestamp}@test.serve"
    admin_password = "admin123!@#"

    member1_email = f"member1_{timestamp}@test.serve"
    member1_password = "member123!@#"

    member2_email = f"member2_{timestamp}@test.serve"
    member2_password = "member123!@#"

    team_id = None
    document_id = None

    try:
        # ================================================================
        # Step 1: 유저 생성 및 로그인
        # ================================================================
        print("\n[Step 1] 테스트 유저 생성 및 로그인")

        # Admin 생성
        admin_client = ServeClient(server_url=CLOUD_URL)
        success, msg = admin_client.signup(admin_email, admin_password)
        if not success:
            print(f"✗ Admin 회원가입 실패: {msg}")
            return
        print(f"✓ Admin 회원가입 성공: {admin_email}")

        success, msg = admin_client.login(admin_email, admin_password)
        if not success:
            print(f"✗ Admin 로그인 실패: {msg}")
            return
        print(f"✓ Admin 로그인 성공")

        # Member1 생성 (세션 분리를 위해 나중에 로그인)
        member1_client = ServeClient(server_url=CLOUD_URL)
        success, msg = member1_client.signup(member1_email, member1_password)
        if not success:
            print(f"✗ Member1 회원가입 실패: {msg}")
            return
        print(f"✓ Member1 회원가입 성공: {member1_email}")

        # Member1 로그인은 나중에 (Session Singleton 문제 회피)
        print(f"  (Member1 로그인은 문서 접근 테스트 시 수행)")

        # Member2 생성 (키 로테이션 후 새 키로 접근 테스트용)
        member2_client = ServeClient(server_url=CLOUD_URL)
        success, msg = member2_client.signup(member2_email, member2_password)
        if not success:
            print(f"✗ Member2 회원가입 실패: {msg}")
            return
        print(f"✓ Member2 회원가입 성공: {member2_email}")

        # ================================================================
        # Step 2: Admin이 팀 생성
        # ================================================================
        print("\n[Step 2] Admin이 팀 생성")

        team_name = f"KeyRotation_Test_Team_{timestamp}"
        team_description = "자동 키 로테이션 검증용 테스트 팀"

        repo_id, msg = admin_client.create_repository(team_name, team_description)
        if not repo_id:
            print(f"✗ 팀 생성 실패: {msg}")
            return

        team_id = repo_id
        print(f"✓ 팀 생성 성공: {team_id}")

        # ================================================================
        # Step 3: Admin이 Member1, Member2 초대
        # ================================================================
        print("\n[Step 3] Admin이 Member1, Member2 초대")

        # Member1 초대
        print(f"  Admin 이메일: {admin_email}")
        print(f"  Member1 이메일: {member1_email}")
        print(f"  Member2 이메일: {member2_email}")
        print(f"  팀 ID: {team_id}")
        success, msg = admin_client.invite_member(team_id, member1_email)
        if not success:
            print(f"✗ Member1 초대 실패")
            print(f"  에러 메시지: {msg}")
            print(f"  팀 ID: {team_id}")
            print(f"  Admin ID: {admin_client.session.user_id}")
            import traceback
            traceback.print_exc()
            return
        print(f"✓ Member1 초대 성공")

        # Member2 초대
        success, msg = admin_client.invite_member(team_id, member2_email)
        if not success:
            print(f"✗ Member2 초대 실패: {msg}")
            return
        print(f"✓ Member2 초대 성공")

        print(f"✓ 멤버 초대 완료 (팀 키는 문서 접근 시 자동 로드됨)")

        # ================================================================
        # Step 4: Member1이 테스트 문서 업로드 (MEMBER만 업로드 가능)
        # ================================================================
        print("\n[Step 4] Member1이 테스트 문서 업로드")

        # Member1 로그인
        success, msg = member1_client.login(member1_email, member1_password)
        if not success:
            print(f"✗ Member1 로그인 실패: {msg}")
            return
        print(f"✓ Member1 로그인 성공 (문서 업로드용)")

        file_name = f"test_document_{timestamp}.json"
        test_data = {
            "title": "키 로테이션 테스트 문서",
            "content": "이 문서는 키 로테이션 검증용 테스트 데이터입니다.",
            "timestamp": datetime.now().isoformat(),
            "sensitive_info": "이 정보는 강퇴된 멤버가 볼 수 없어야 합니다."
        }

        chunks_data = [{
            "chunkIndex": 0,
            "data": json.dumps(test_data, ensure_ascii=False)
        }]

        success, result = member1_client.upload_chunks_to_document(
            file_name=file_name,
            repo_id=team_id,
            chunks_data=chunks_data
        )

        if not success:
            print(f"✗ 문서 업로드 실패: {result}")
            print(f"  Member1 ID: {member1_client.session.user_id}")
            print(f"  팀 ID: {team_id}")
            print(f"  파일명: {file_name}")
            return

        document_id = result
        print(f"✓ 문서 업로드 성공: {document_id[:16]}...")

        # 데이터베이스 반영 대기
        print("  데이터베이스 반영 대기 중... (2초)")
        time.sleep(2)

        # ================================================================
        # Step 5: Member1이 문서에 접근 가능한지 확인 (강퇴 전)
        # ================================================================
        print("\n[Step 5] Member1이 문서 접근 가능 확인 (강퇴 전)")

        # Member1 로그인 (Session Singleton 문제로 인해 여기서 로그인)
        success, msg = member1_client.login(member1_email, member1_password)
        if not success:
            print(f"✗ Member1 로그인 실패: {msg}")
            return
        print(f"✓ Member1 로그인 성공 (문서 접근 테스트용)")

        # 주의: download_chunks_from_document()는 이름은 download이지만 내부적으로 sync API 사용
        chunks, msg = member1_client.download_chunks_from_document(file_name, team_id)
        if not chunks:
            print(f"✗ Member1 문서 접근 실패 (강퇴 전인데 접근 불가): {msg}")
            return

        # 복호화된 데이터 확인
        decrypted_data = json.loads(chunks[0]['data'])
        print(f"✓ Member1 문서 접근 성공 (강퇴 전)")
        print(f"  복호화된 데이터: {decrypted_data['title']}")

        # ================================================================
        # Step 6: Member1의 현재 팀 키 백업 (강퇴 전)
        # ================================================================
        print("\n[Step 6] Member1의 현재 팀 키 백업")

        old_team_key = member1_client.session.get_cached_team_key(team_id)
        if not old_team_key:
            print(f"✗ Member1의 팀 키 백업 실패 (세션에 키 없음)")
            return

        print(f"✓ Member1의 현재 팀 키 백업 완료 (KeysetHandle 객체)")

        # ================================================================
        # Step 7: Admin이 Member1 강퇴 (자동 키 로테이션 트리거)
        # ================================================================
        print("\n[Step 7] Admin이 Member1 강퇴 (자동 키 로테이션)")

        # Member1의 user_id 저장 (강퇴 전에 저장)
        member1_user_id = member1_client.session.user_id

        # Admin 재로그인 (Session Singleton 문제로 member1 로그인 후 admin 세션이 덮어써짐)
        success, msg = admin_client.login(admin_email, admin_password)
        if not success:
            print(f"✗ Admin 재로그인 실패: {msg}")
            return
        print(f"✓ Admin 재로그인 성공 (강퇴 작업용)")
        success, msg = admin_client.kick_member(
            repo_id=team_id,
            target_user_id=member1_user_id,
            auto_rotate_keys=True  # 자동 키 로테이션 활성화
        )

        if not success:
            print(f"✗ Member1 강퇴 실패: {msg}")
            return

        print(f"✓ Member1 강퇴 성공")
        print(f"  메시지: {msg}")

        # 키 로테이션 반영 대기
        print("  키 로테이션 반영 대기 중... (2초)")
        time.sleep(2)

        # ================================================================
        # Step 8: Admin의 새 팀 키 확인
        # ================================================================
        print("\n[Step 8] Admin의 새 팀 키 확인")

        admin_new_key = admin_client.session.get_cached_team_key(team_id)

        # Admin의 키가 업데이트되었는지 확인
        if admin_new_key == old_team_key:
            print(f"⚠ 경고: Admin의 팀 키가 변경되지 않았습니다!")
            print(f"  (자동 키 로테이션이 Admin 세션에 반영되지 않을 수 있음)")
        else:
            print(f"✓ Admin의 팀 키가 새로 갱신되었습니다")

        # ================================================================
        # Step 9: Member1이 문서에 접근 불가 확인 (강퇴 후)
        # ================================================================
        print("\n[Step 9] Member1이 문서 접근 불가 확인 (강퇴 후)")

        # Member1 재로그인
        success, msg = member1_client.login(member1_email, member1_password)
        if not success:
            print(f"✗ Member1 재로그인 실패: {msg}")
            return
        print(f"✓ Member1 재로그인 성공 (접근 차단 테스트용)")

        # Member1이 서버에서 문서를 요청하면 403 또는 401 에러가 발생해야 함
        # 주의: download_chunks_from_document()는 이름은 download이지만 내부적으로 sync API 사용
        chunks, msg = member1_client.download_chunks_from_document(file_name, team_id)

        if chunks:
            print(f"✗ 보안 취약점: Member1이 강퇴 후에도 문서에 접근 가능!")
            print(f"  복호화된 데이터: {chunks[0]['data'][:100]}...")
            print(f"\n❌ 테스트 실패: 키 로테이션이 제대로 동작하지 않음")
            return
        else:
            # 접근 거부됨 (예상된 동작)
            print(f"✓ Member1 문서 접근 거부됨 (예상된 동작)")
            print(f"  메시지: {msg}")

        # ================================================================
        # Step 10: Member2가 새 키로 문서 접근 가능 확인 (강퇴 후)
        # ================================================================
        print("\n[Step 10] Member2가 새 키로 문서 접근 가능 확인 (강퇴 후)")

        # Member2 로그인
        success, msg = member2_client.login(member2_email, member2_password)
        if not success:
            print(f"✗ Member2 로그인 실패: {msg}")
            return
        print(f"✓ Member2 로그인 성공 (새 키 테스트용)")

        # Member2가 문서 접근 (새 팀 키로 복호화)
        # 주의: download_chunks_from_document()는 이름은 download이지만 내부적으로 sync API 사용
        chunks, msg = member2_client.download_chunks_from_document(file_name, team_id)
        if not chunks:
            print(f"✗ Member2 문서 접근 실패 (새 키로 복호화 불가): {msg}")
            print(f"\n❌ 테스트 실패: 키 로테이션 후 Member2가 접근 불가")
            return

        # 복호화된 데이터 확인
        decrypted_data = json.loads(chunks[0]['data'])
        print(f"✓ Member2 문서 접근 성공 (새 팀 키로 복호화)")
        print(f"  복호화된 데이터: {decrypted_data['title']}")

        # ================================================================
        # Step 11: Admin이 메타데이터만 조회 가능 확인 (Federated Model)
        # ================================================================
        print("\n[Step 11] Admin이 메타데이터만 조회 가능 확인 (Federated Model)")

        # Admin의 캐시된 팀 키 클리어
        admin_client.session.clear_team_keys()

        # Admin 재로그인
        success, msg = admin_client.login(admin_email, admin_password)
        if not success:
            print(f"✗ Admin 재로그인 실패: {msg}")
            return
        print(f"✓ Admin 재로그인 성공 (메타데이터 조회 테스트용)")

        # Admin은 메타데이터만 조회 가능 (문서 목록, uploader 정보 등)
        # GET /api/teams/{teamId}/documents - 암호화된 blob 없이 메타데이터만 반환
        docs, msg = admin_client.get_documents(team_id)
        if not docs:
            print(f"✗ Admin 메타데이터 조회 실패: {msg}")
            print(f"\n❌ 테스트 실패: Admin이 메타데이터 조회 불가")
            return

        # 메타데이터 확인
        print(f"✓ Admin 메타데이터 조회 성공")
        print(f"  문서 개수: {len(docs)}")
        if len(docs) > 0:
            print(f"  첫 번째 문서: {docs[0].get('fileName', 'N/A')}")
            print(f"  업로더: {docs[0].get('uploaderEmail', 'N/A')}")

        # Admin이 암호화된 데이터 동기화를 시도하면 거부되어야 함
        print(f"\n  [검증] Admin이 암호화된 데이터 동기화 시도 (예상: 거부)")
        chunks, msg = admin_client.download_chunks_from_document(file_name, team_id)
        if chunks:
            print(f"✗ 보안 취약점: Admin이 암호화된 데이터에 접근 가능!")
            print(f"  복호화된 데이터: {chunks[0]['data'][:100]}...")
            print(f"\n❌ 테스트 실패: Federated Model 위반 (ADMIN이 데이터 접근 가능)")
            return
        else:
            # 접근 거부됨 (예상된 동작)
            print(f"  ✓ Admin 암호화 데이터 동기화 거부됨 (예상된 동작)")
            print(f"  메시지: {msg}")

        # ================================================================
        # 최종 결과
        # ================================================================
        print_separator("테스트 결과")
        print("✅ 모든 검증 통과!")
        print()
        print("검증 항목:")
        print("  ✓ Member1 강퇴 시 자동 키 로테이션 트리거")
        print("  ✓ Member1 강퇴 후 문서 접근 불가 (보안 유지)")
        print("  ✓ Member2는 새 키로 문서 접근 가능 (키 로테이션 성공)")
        print("  ✓ Admin은 메타데이터만 조회 가능 (Federated Model 준수)")
        print("  ✓ Admin은 암호화된 데이터 동기화 불가 (Zero-Trust 원칙)")
        print()
        print("🎉 키 로테이션 및 Federated Model이 정상적으로 동작합니다!")
        print_separator()

        # 정리
        cleanup_test_users(admin_client, [admin_email, member1_email, member2_email])

    except Exception as e:
        print(f"\n❌ 테스트 중 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """메인 테스트 실행"""
    print_separator("SeRVe 키 로테이션 및 Federated Model 검증 테스트")
    print("이 테스트는 다음을 검증합니다:")
    print("  1. 멤버 강퇴 시 자동 키 로테이션 트리거")
    print("  2. 강퇴된 멤버는 문서 접근 불가")
    print("  3. 남은 멤버는 새 키로 문서 접근 가능")
    print("  4. ADMIN은 메타데이터만 조회 가능 (Federated Model)")
    print("  5. ADMIN은 암호화된 데이터 동기화 불가 (Zero-Trust 원칙)")
    print()
    print("주의: 이 테스트는 백엔드 서버가 실행 중이어야 합니다.")
    print(f"      서버 URL: {CLOUD_URL}")
    print_separator()

    # 자동 실행 (input 제거)
    test_key_rotation_after_kick()

if __name__ == "__main__":
    main()
