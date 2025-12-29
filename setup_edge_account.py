#!/usr/bin/env python3
"""
Edge 계정 자동 설정
Edge 계정 생성, 저장소 생성, 그리고 TEAM_ID로 .env 파일 업데이트
"""

import sys
from pathlib import Path

# SeRVe-Client를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "SeRVe-Client"))

from serve_sdk import ServeClient

# 설정
CLOUD_URL = "http://localhost:8080"

# ADMIN 계정 (저장소 생성자)
ADMIN_EMAIL = "admin@serve.local"
ADMIN_PASSWORD = "admin123"

# EDGE 계정 1 (MEMBER role로 데이터 업로드)
EDGE1_EMAIL = "edge1@serve.local"
EDGE1_PASSWORD = "edge123"

# EDGE 계정 2 (팀에 초대되지 않음 - 접근 불가)
EDGE2_EMAIL = "edge2@serve.local"
EDGE2_PASSWORD = "edge456"

REPO_NAME = "Edge Server Repository"
REPO_DESC = "Edge 서버 데이터 수집 및 처리용 저장소"

def update_env_file(team_id):
    """TEAM_ID로 .env 파일 업데이트"""
    env_file = Path(__file__).parent / ".env"

    # 현재 .env 파일 내용 읽기
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # TEAM_ID 라인 업데이트
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('TEAM_ID='):
                lines[i] = f'TEAM_ID={team_id}\n'
                updated = True
                break

        # TEAM_ID 라인이 없으면 추가
        if not updated:
            lines.append(f'\nTEAM_ID={team_id}\n')

        # 다시 쓰기
        with open(env_file, 'w') as f:
            f.writelines(lines)
    else:
        # 새 .env 파일 생성
        with open(env_file, 'w') as f:
            f.write(f"""# SeRVe Edge Server 설정

# 클라우드 서버
CLOUD_URL={CLOUD_URL}
EDGE_EMAIL={EDGE1_EMAIL}
EDGE_PASSWORD={EDGE1_PASSWORD}

# 팀 ID (클라우드 서버의 저장소 ID)
TEAM_ID={team_id}
""")

    print(f".env 파일 업데이트 완료: TEAM_ID={team_id}")

def main():
    """메인 설정 함수 - Federated Model 지원"""
    print("=" * 60)
    print("SeRVe Edge 계정 설정 (Federated Model)")
    print("=" * 60)
    print("ADMIN: 저장소 생성자, 메타데이터만 조회 가능")
    print("EDGE1 (MEMBER): 데이터 업로드/동기화 가능")
    print("EDGE2 (미초대): 저장소 접근 불가 (보안 시연용)")
    print("=" * 60)

    # ========== STEP 1: ADMIN 계정으로 저장소 생성 ==========
    print(f"\n[ADMIN 계정] 저장소 생성")
    print(f"1. ADMIN 계정 생성 중: {ADMIN_EMAIL}")

    admin_client = ServeClient(server_url=CLOUD_URL)
    success, msg = admin_client.signup(ADMIN_EMAIL, ADMIN_PASSWORD)

    if success:
        print(f"   ADMIN 계정 생성됨: {msg}")
    elif "already exists" in msg.lower() or "duplicate" in msg.lower():
        print(f"   ADMIN 계정이 이미 존재함")
    else:
        print(f"   회원가입 실패: {msg}")
        return False

    # ADMIN 로그인
    print(f"\n2. ADMIN 계정 로그인 중: {ADMIN_EMAIL}")
    success, msg = admin_client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not success:
        print(f"   로그인 실패: {msg}")
        return False
    print(f"   로그인 성공")

    # 저장소 확인/생성
    print(f"\n3. 저장소 확인 중")
    repos, msg = admin_client.get_my_repositories()

    if repos and len(repos) > 0:
        repo = repos[0]
        repo_id = repo.get('Teamid') or repo.get('teamid')
        repo_name = repo.get('name')
        print(f"   기존 저장소 사용: {repo_name} (ID: {repo_id})")
    else:
        # 저장소 이름 충돌 시 타임스탬프 추가
        import datetime
        repo_name_to_create = REPO_NAME

        print(f"   저장소 생성 중: {repo_name_to_create}")
        repo_id, msg = admin_client.create_repository(repo_name_to_create, REPO_DESC)

        # 이름 충돌 시 타임스탬프 추가하여 재시도
        if not repo_id and "이미 존재" in msg:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            repo_name_to_create = f"{REPO_NAME}_{timestamp}"
            print(f"   저장소 이름 충돌 감지, 새 이름으로 재시도: {repo_name_to_create}")
            repo_id, msg = admin_client.create_repository(repo_name_to_create, REPO_DESC)

        if not repo_id:
            print(f"   저장소 생성 실패: {msg}")
            return False
        print(f"   저장소 생성됨 (ID: {repo_id})")

    # ========== STEP 2: EDGE1 계정 생성 및 MEMBER로 초대 ==========
    print(f"\n[EDGE1 계정] MEMBER로 초대")
    print(f"4. EDGE1 계정 생성 중: {EDGE1_EMAIL}")

    edge1_client = ServeClient(server_url=CLOUD_URL)
    success, msg = edge1_client.signup(EDGE1_EMAIL, EDGE1_PASSWORD)

    if success:
        print(f"   EDGE1 계정 생성됨: {msg}")
    elif "already exists" in msg.lower() or "duplicate" in msg.lower():
        print(f"   EDGE1 계정이 이미 존재함")
    else:
        print(f"   회원가입 실패: {msg}")
        return False

    # EDGE1 계정을 MEMBER로 초대
    print(f"\n5. EDGE1 계정을 MEMBER로 초대 중")
    success, msg = admin_client.invite_member(repo_id, EDGE1_EMAIL)

    if success:
        print(f"   MEMBER 초대 성공: {msg}")
    elif "already" in msg.lower():
        print(f"   이미 멤버로 등록되어 있음")
    else:
        print(f"   초대 실패: {msg}")
        return False

    # ========== STEP 3: EDGE2 계정 생성 (초대하지 않음) ==========
    print(f"\n[EDGE2 계정] 계정 생성만 (팀에 초대하지 않음)")
    print(f"6. EDGE2 계정 생성 중: {EDGE2_EMAIL}")

    edge2_client = ServeClient(server_url=CLOUD_URL)
    success, msg = edge2_client.signup(EDGE2_EMAIL, EDGE2_PASSWORD)

    if success:
        print(f"   EDGE2 계정 생성됨: {msg}")
    elif "already exists" in msg.lower() or "duplicate" in msg.lower():
        print(f"   EDGE2 계정이 이미 존재함")
    else:
        print(f"   회원가입 실패: {msg}")
        return False

    print(f"   EDGE2 계정은 저장소에 초대되지 않음 (접근 불가)")

    # ========== STEP 4: .env 파일 업데이트 ==========
    print(f"\n7. .env 파일 업데이트 중")
    update_env_file(repo_id)

    print("\n" + "=" * 60)
    print("설정 완료!")
    print("=" * 60)
    print(f"ADMIN 계정:  {ADMIN_EMAIL} (저장소 관리)")
    print(f"EDGE1 계정:  {EDGE1_EMAIL} (MEMBER - 데이터 업로드/동기화 가능)")
    print(f"EDGE2 계정:  {EDGE2_EMAIL} (미초대 - 저장소 접근 불가)")
    print(f"저장소 ID:   {repo_id}")
    print(f"\n이제 다음 명령어로 Edge 서버를 실행할 수 있습니다:")
    print(f"  docker compose down && docker compose up -d")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
