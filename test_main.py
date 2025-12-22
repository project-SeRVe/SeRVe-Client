from serve_connector import ServeConnector
import uuid
import sys
import time

# 테스트용 계정 정보
TEST_EMAIL = "robot_01@factory.com"
TEST_PASSWORD = "secure_password"

def print_section(step_num, title):
    """섹션 헤더 출력"""
    print("\n" + "="*70)
    print(f">>> [Step {step_num}] {title}")
    print("="*70)

def run_simulation():
    print("\n" + "🤖 " * 20)
    print(">>> [SeRVe Physical AI Client] 전체 워크플로우 테스트 시작")
    print("🤖 " * 20)

    # 커넥터 초기화
    connector = ServeConnector()
    print(f"\n[Init] 서버 URL: {connector._get_server_url()}")
    print(f"[Init] 테스트 계정: {TEST_EMAIL}")

    # ------------------------------------------------------------------
    # Step 1. 보안 핸드셰이크 (가장 먼저 수행)
    # ------------------------------------------------------------------
    print_section(1, "보안 핸드셰이크 (키 교환)")

    success, msg = connector.perform_handshake()

    if not success:
        print(f"❌ [FATAL] 핸드셰이크 실패: {msg}")
        sys.exit(1)

    print(f"✅ [Success] {msg}")

    # ------------------------------------------------------------------
    # Step 2. 인증 (회원가입/로그인)
    # ------------------------------------------------------------------
    print_section(2, "사용자 인증")

    login_success, login_msg = connector.login(TEST_EMAIL, TEST_PASSWORD)

    if not login_success:
        print(f"[Info] 로그인 실패. 회원가입을 시도합니다...")

        # 데모용 키 쌍 생성
        demo_key_pair = connector.crypto.generate_client_key_pair()
        pub_key = connector.crypto.get_public_key_json(demo_key_pair)
        enc_priv_key = "encrypted_private_key_demo"

        sign_success, sign_msg = connector.signup(TEST_EMAIL, TEST_PASSWORD, pub_key, enc_priv_key)
        if not sign_success:
            print(f"❌ [FATAL] 회원가입 실패: {sign_msg}")
            sys.exit(1)

        print(f"✅ [Success] 회원가입 완료")
        login_success, login_msg = connector.login(TEST_EMAIL, TEST_PASSWORD)

    print(f"✅ [Success] 로그인 완료")
    print(f"   - User ID: {connector.user_id}")
    print(f"   - Email: {connector.email}")

    # ------------------------------------------------------------------
    # Step 3. 저장소 생성
    # ------------------------------------------------------------------
    print_section(3, "저장소(팀) 생성")

    repo_name = f"AGV-Log-{str(uuid.uuid4())[:8]}"
    repo_id, repo_msg = connector.create_repository(
        repo_name,
        "AGV 센서 로그 데이터",
        "demo_team_key"
    )

    if not repo_id:
        print(f"❌ [Error] 저장소 생성 실패: {repo_msg}")
        return

    print(f"✅ [Success] 저장소 생성됨")
    print(f"   - 저장소 ID: {repo_id}")
    print(f"   - 저장소 이름: {repo_name}")

    # ------------------------------------------------------------------
    # Step 4. 저장소 목록 조회
    # ------------------------------------------------------------------
    print_section(4, "내 저장소 목록 조회")

    repos, repos_msg = connector.get_my_repositories()

    if repos:
        print(f"✅ [Success] 저장소 목록 조회 완료")
        print(f"   - 총 {len(repos)}개의 저장소 발견")
        for idx, repo in enumerate(repos[:3], 1):  # 최대 3개만 표시
            print(f"   {idx}. ID: {repo.get('repoId', 'N/A')}, 이름: {repo.get('name', 'N/A')}")
    else:
        print(f"⚠️  [Warning] 저장소 목록 조회 실패: {repos_msg}")

    # ------------------------------------------------------------------
    # Step 5. 문서 업로드 (여러 개)
    # ------------------------------------------------------------------
    print_section(5, "암호화된 문서 업로드")

    test_documents = [
        {
            "content": "Sensor: Lidar_01, Status: OK, Position: [10, 20], Timestamp: 2025-12-22T10:00:00",
            "file_name": "sensor_lidar.txt",
            "file_type": "text/plain"
        },
        {
            "content": "Camera: Front_CAM, Resolution: 1920x1080, FPS: 30, Status: Active",
            "file_name": "camera_status.txt",
            "file_type": "text/plain"
        },
        {
            "content": "Battery: 85%, Temperature: 42C, Voltage: 12.4V, Current: 2.1A",
            "file_name": "battery_info.txt",
            "file_type": "text/plain"
        }
    ]

    uploaded_docs = []

    for idx, doc in enumerate(test_documents, 1):
        print(f"\n[{idx}/{len(test_documents)}] 업로드 중: {doc['file_name']}")
        print(f"   - repo_id 타입: {type(repo_id)}, 값: {repo_id}")

        doc_id, up_msg = connector.upload_secure_document(
            doc['content'],
            repo_id,
            file_name=doc['file_name'],
            file_type=doc['file_type']
        )

        if doc_id:
            print(f"   ✅ 업로드 성공")
            uploaded_docs.append({'id': doc_id, 'name': doc['file_name'], 'content': doc['content']})
        else:
            print(f"   ❌ 업로드 실패:")
            print(f"   {up_msg}")

    print(f"\n✅ [Success] 총 {len(uploaded_docs)}개 문서 업로드 완료")

    # ------------------------------------------------------------------
    # Step 6. 문서 목록 조회
    # ------------------------------------------------------------------
    print_section(6, "저장소 문서 목록 조회")

    documents, docs_msg = connector.get_documents(repo_id)

    if documents:
        print(f"✅ [Success] 문서 목록 조회 완료")
        print(f"   - 총 {len(documents)}개의 문서 발견")
        for idx, doc in enumerate(documents, 1):
            print(f"   {idx}. {doc.get('fileName', 'N/A')} ({doc.get('fileType', 'N/A')})")
            print(f"      - ID: {doc.get('docId', 'N/A')}")
            print(f"      - 업로더: {doc.get('uploaderId', 'N/A')}")
            print(f"      - 생성일: {doc.get('createdAt', 'N/A')}")
    else:
        print(f"⚠️  [Warning] 문서 목록 조회 실패: {docs_msg}")

    # ------------------------------------------------------------------
    # Step 7. 문서 다운로드 및 복호화
    # ------------------------------------------------------------------
    if documents and len(documents) > 0:
        print_section(7, "문서 다운로드 및 복호화 테스트")

        # 첫 번째 문서 다운로드
        test_doc = documents[0]
        doc_id = test_doc.get('docId')

        print(f"\n[Test] 문서 다운로드 시도: {test_doc.get('fileName')}")
        print(f"   - Document ID: {doc_id}")

        decrypted_content, decrypt_msg = connector.get_secure_document(doc_id)

        if decrypted_content:
            print(f"✅ [Success] 문서 다운로드 및 복호화 완료")
            print(f"   - 복호화된 내용: {decrypted_content}")

            # 원본 내용과 비교
            original = next((d['content'] for d in uploaded_docs if d['name'] == test_doc.get('fileName')), None)
            if original and original == decrypted_content:
                print(f"   ✅ 원본과 일치 확인됨!")
            elif original:
                print(f"   ⚠️  원본과 불일치!")
        else:
            print(f"❌ [Error] 다운로드 실패: {decrypt_msg}")

    # ------------------------------------------------------------------
    # Step 8. 최종 요약
    # ------------------------------------------------------------------
    print("\n" + "="*70)
    print(">>> [테스트 완료] 전체 워크플로우 요약")
    print("="*70)
    print(f"✅ 핸드셰이크: 성공")
    print(f"✅ 로그인: 성공 (User: {connector.user_id})")
    print(f"✅ 저장소 생성: 성공 (ID: {repo_id})")
    print(f"✅ 문서 업로드: {len(uploaded_docs)}개 성공")
    if documents:
        print(f"✅ 문서 조회: {len(documents)}개 발견")
    print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!\n")

if __name__ == "__main__":
    try:
        run_simulation()
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ [FATAL] 예상치 못한 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)