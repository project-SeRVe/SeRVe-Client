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
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
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
EDGE_EMAIL={EDGE_EMAIL}
EDGE_PASSWORD={EDGE_PASSWORD}

# 팀 ID (클라우드 서버의 저장소 ID)
TEAM_ID={team_id}
""")

    print(f"✓ .env 파일 업데이트 완료: TEAM_ID={team_id}")

def main():
    """메인 설정 함수"""
    print("=" * 60)
    print("SeRVe Edge 계정 설정")
    print("=" * 60)

    # 클라이언트 초기화
    print(f"\n1. 클라우드 서버 연결 중: {CLOUD_URL}")
    client = ServeClient(server_url=CLOUD_URL)
    print(f"   ✓ 연결됨")

    # 회원가입
    print(f"\n2. Edge 계정 생성 중: {EDGE_EMAIL}")
    success, msg = client.signup(EDGE_EMAIL, EDGE_PASSWORD)

    if success:
        print(f"   ✓ 계정 생성됨: {msg}")
    elif "already exists" in msg.lower() or "duplicate" in msg.lower():
        print(f"   ℹ 계정이 이미 존재함, 회원가입 건너뜀")
    else:
        print(f"   ✗ 회원가입 실패: {msg}")
        return False

    # 로그인
    print(f"\n3. {EDGE_EMAIL}로 로그인 중")
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"   ✗ 로그인 실패: {msg}")
        return False

    print(f"   ✓ 로그인 성공: {msg}")

    # 기존 저장소 확인
    print(f"\n4. 기존 저장소 확인 중")
    repos, msg = client.get_my_repositories()

    if repos and len(repos) > 0:
        print(f"   ℹ {len(repos)}개의 기존 저장소 발견")

        # 첫 번째 저장소 사용
        repo = repos[0]
        repo_id = repo.get('Teamid') or repo.get('teamid')
        repo_name = repo.get('name')

        print(f"   ✓ 기존 저장소 사용: {repo_name} (ID: {repo_id})")
    else:
        # 새 저장소 생성
        print(f"\n5. 저장소 생성 중: {REPO_NAME}")
        repo_id, msg = client.create_repository(REPO_NAME, REPO_DESC)

        if not repo_id:
            print(f"   ✗ 저장소 생성 실패: {msg}")
            return False

        print(f"   ✓ 저장소 생성됨: {msg}")
        print(f"   ✓ 저장소 ID: {repo_id}")

    # .env 파일 업데이트
    print(f"\n6. .env 파일 업데이트 중")
    update_env_file(repo_id)

    print("\n" + "=" * 60)
    print("설정 완료!")
    print("=" * 60)
    print(f"\nEdge 계정: {EDGE_EMAIL}")
    print(f"저장소 ID: {repo_id}")
    print(f"\n이제 다음 명령어로 Edge 서버를 실행할 수 있습니다:")
    print(f"  cd edge-server")
    print(f"  docker-compose up --build")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n✗ 사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
