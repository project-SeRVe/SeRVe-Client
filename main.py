from serve_connector import ServeConnector
import uuid
import sys

# 테스트용 계정 정보
TEST_EMAIL = "robot_01@factory.com"
TEST_PASSWORD = "secure_password"

def run_simulation():
    print(">>> [Physical AI Client] 시뮬레이션 시작")
    
    # 1. 커넥터 초기화
    connector = ServeConnector()
    print(f"[Init] 서버 URL: {connector._get_server_url()}")

    # ------------------------------------------------------------------
    # Step 1. 보안 핸드셰이크 (가장 먼저 수행)
    # ------------------------------------------------------------------
    print("\n>>> [Step 1] 보안 핸드셰이크 시도...")
    # 서버의 SecurityConfig에서 /api/security/** 가 permitAll()이어야 함
    success, msg = connector.perform_handshake()
    
    if not success:
        print(f"[FATAL] 핸드셰이크 실패: {msg}")
        sys.exit(1)
        
    print(f"[Success] {msg}")

    # ------------------------------------------------------------------
    # Step 2. 로그인 (인증)
    # ------------------------------------------------------------------
    print("\n>>> [Step 2] 로그인 시도...")
    
    login_success, login_msg = connector.login(TEST_EMAIL, TEST_PASSWORD)
    
    if not login_success:
        print(f"[Info] 로그인 실패 ({login_msg}). 회원가입을 시도합니다.")
        # 데모용 임시 키 생성
        demo_key_pair = connector.crypto.generate_client_key_pair()
        pub_key = connector.crypto.get_public_key_json(demo_key_pair)
        enc_priv_key = "encrypted_private_key_demo"
        
        sign_success, sign_msg = connector.signup(TEST_EMAIL, TEST_PASSWORD, pub_key, enc_priv_key)
        if not sign_success:
            print(f"[FATAL] 회원가입 실패: {sign_msg}")
            sys.exit(1)
            
        login_success, login_msg = connector.login(TEST_EMAIL, TEST_PASSWORD)

    print(f"[Success] 로그인 완료 (Token 획득)")

    # ------------------------------------------------------------------
    # Step 3. 업무 수행 (저장소 생성 및 보안 업로드)
    # ------------------------------------------------------------------
    print("\n>>> [Step 3] 저장소 생성 및 데이터 업로드...")
    
    repo_name = f"AGV-Log-{str(uuid.uuid4())[:8]}"
    repo_id, repo_msg = connector.create_repository(repo_name, "AGV Log Data", "demo_team_key")
    
    if not repo_id:
        print(f"[Error] 저장소 생성 실패: {repo_msg}")
        return

    print(f"[Success] 저장소 생성됨 (ID: {repo_id})")

    sensor_data = "Sensor: Lidar_01, Status: OK, Loc: [10, 20]"
    doc_id, up_msg = connector.upload_secure_document(sensor_data, repo_id)
    
    if doc_id:
        print(f"[Success] 암호화 업로드 완료 (Doc ID: {doc_id})")
    else:
        print(f"[Error] 업로드 실패: {up_msg}")

if __name__ == "__main__":
    run_simulation()