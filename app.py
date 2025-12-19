import streamlit as st
import os
from PIL import Image
import io
import requests
from vision_engine import VisionEngine
from serve_connector import ServeConnector
from config import SERVER_URL

# 페이지 설정
st.set_page_config(page_title="SeRVe: Secure Edge AI", layout="wide")

# 세션 상태 초기화
if 'serve_conn' not in st.session_state:
    st.session_state.serve_conn = ServeConnector()
    st.session_state.is_logged_in = False
    st.session_state.current_repo = None
    st.session_state.server_connected = False
    st.session_state.server_url = SERVER_URL

# 서버 연결 확인 함수
def check_server_connection(url):
    """서버 연결 테스트"""
    try:
        # 간단한 헬스 체크 (루트 경로 또는 actuator)
        test_url = url.rstrip('/')
        response = requests.get(f"{test_url}/actuator/health", timeout=3)
        if response.status_code == 200:
            return True, "서버 연결 성공"
    except:
        pass

    # actuator가 없는 경우 다른 방법으로 테스트
    try:
        test_url = url.rstrip('/')
        response = requests.get(test_url, timeout=3)
        # 응답이 있으면 (200이 아니어도) 서버는 실행 중
        return True, "서버 연결 성공"
    except requests.exceptions.ConnectionError:
        return False, "서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요."
    except requests.exceptions.Timeout:
        return False, "서버 응답 시간 초과"
    except Exception as e:
        return False, f"연결 오류: {str(e)}"

# 로그인 체크
def is_logged_in():
    return st.session_state.serve_conn.user_id is not None

# ==================== 서버 연결 화면 ====================
if not st.session_state.server_connected:
    st.title("SeRVe: Zero-Trust Physical AI")
    st.subheader("1단계: 보안 서버 연결")

    col1, col2 = st.columns([3, 1])

    with col1:
        server_url_input = st.text_input(
            "서버 URL",
            value=st.session_state.server_url,
            placeholder="http://localhost:8080",
            help="SeRVe 서버의 주소를 입력하세요 (예: http://localhost:8080)"
        )

    with col2:
        st.write("")  # 간격 맞추기
        st.write("")
        connect_button = st.button("연결 및 핸드셰이크", type="primary", use_container_width=True)

    if connect_button:
        with st.spinner("서버 연결 및 보안 채널 수립 중..."):
            # 1. 서버 연결 확인
            success, msg = check_server_connection(server_url_input)

            if success:
                # URL 업데이트 (Config 및 인스턴스)
                st.session_state.serve_conn.server_url = server_url_input
                import config
                config.SERVER_URL = server_url_input
                st.session_state.server_url = server_url_input

                # 2. 연결 즉시 핸드셰이크 시도
                # 서버 SecurityConfig에서 /api/security/** 가 허용되어 있어야 함
                h_success, h_msg = st.session_state.serve_conn.perform_handshake()
                
                if h_success:
                    st.session_state.server_connected = True
                    st.success(f"연결 및 핸드셰이크 성공!\nAES 키 교환 완료.")
                    st.rerun() # 성공 시 새로고침하여 로그인 화면으로 이동
                else:
                    st.error(f"서버 연결은 되었으나 핸드셰이크에 실패했습니다.\n{h_msg}")
                    st.info("서버의 SecurityConfig에서 /api/security/** 경로가 인증 예외 처리되어 있는지 확인하세요.")
            else:
                st.error(msg)

    st.divider()

    st.info("""
    **서버 연결 안내**

    1. SeRVe 서버가 실행 중인지 확인하세요.
    2. 서버 URL을 입력하세요 (포트 번호 포함).
    3. '서버 연결' 버튼을 클릭하세요.

    **서버 실행 방법:**
    ```bash
    cd SeRVe
    ./gradlew bootRun
    ```
    """)

    # 서버 연결 없이도 데모 모드로 실행할 수 있도록
    st.divider()
    if st.checkbox("서버 연결 없이 데모 모드로 실행 (기능 제한)"):
        st.warning("서버에 연결되지 않은 상태입니다. 일부 기능이 작동하지 않을 수 있습니다.")
        if st.button("데모 모드로 계속"):
            st.session_state.server_connected = True
            st.rerun()

# ==================== 로그인/회원가입 화면 ====================
elif not is_logged_in():
    # 상단에 서버 연결 상태 표시
    with st.sidebar:
        st.header("서버 연결 상태")
        
        # 핸드셰이크가 되어 있으면(aes_handle 존재) 보안 연결 표시
        if st.session_state.serve_conn.aes_handle:
            st.success(f"보안 연결됨 (AES-GCM)\nServer: {st.session_state.server_url}")
        else:
            # 데모 모드 등 핸드셰이크가 안 된 경우
            st.warning(f"연결됨 (보안 미적용): {st.session_state.server_url}")

        if st.button("서버 연결 변경"):
            st.session_state.server_connected = False
            st.session_state.serve_conn.logout() # 로그아웃 처리
            st.rerun()
        st.divider()

    st.title("SeRVe: Zero-Trust Physical AI")
    st.subheader("2단계: 사용자 인증")

    tab1, tab2 = st.tabs(["로그인", "회원가입"])

    with tab1:
        st.subheader("로그인")
        login_email = st.text_input("이메일", key="login_email")
        login_password = st.text_input("비밀번호", type="password", key="login_password")

        if st.button("로그인", type="primary"):
            if login_email and login_password:
                try:
                    success, msg = st.session_state.serve_conn.login(login_email, login_password)
                    if success:
                        st.success(msg)
                        st.session_state.is_logged_in = True
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"로그인 중 오류 발생: {str(e)}")
                    st.info("서버 연결을 확인해주세요.")
            else:
                st.warning("이메일과 비밀번호를 입력해주세요.")

    with tab2:
        st.subheader("회원가입")
        signup_email = st.text_input("이메일", key="signup_email")
        signup_password = st.text_input("비밀번호", type="password", key="signup_password")
        signup_password_confirm = st.text_input("비밀번호 확인", type="password", key="signup_password_confirm")

        st.info("회원가입 시 자동으로 공개키/개인키 쌍이 생성됩니다. (데모용 임시 키)")

        if st.button("회원가입", type="primary"):
            if signup_email and signup_password and signup_password_confirm:
                if signup_password != signup_password_confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    try:
                        # 데모용 임시 키 생성
                        public_key = "demo_public_key_" + signup_email
                        encrypted_private_key = "demo_encrypted_private_key_" + signup_email

                        success, msg = st.session_state.serve_conn.signup(
                            signup_email, signup_password, public_key, encrypted_private_key
                        )
                        if success:
                            st.success(msg)
                            st.info("회원가입이 완료되었습니다. 로그인 탭에서 로그인해주세요.")
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.error(f"회원가입 중 오류 발생: {str(e)}")
                        st.info("서버 연결을 확인해주세요.")
            else:
                st.warning("모든 필드를 입력해주세요.")

# ==================== 메인 애플리케이션 ====================
else:
    st.title("SeRVe: Zero-Trust Physical AI Demo")

    # 사이드바: 사용자 정보 및 시스템 상태
    with st.sidebar:
        st.header("서버 연결 상태")
        st.success(f"✓ {st.session_state.server_url}")
        if st.button("서버 연결 변경", key="change_server_main"):
            st.session_state.server_connected = False
            st.session_state.serve_conn.logout()
            st.session_state.is_logged_in = False
            st.session_state.current_repo = None
            st.rerun()

        st.divider()

        st.header("사용자 정보")
        st.write(f"**이메일:** {st.session_state.serve_conn.email}")
        st.write(f"**User ID:** {st.session_state.serve_conn.user_id}")

        if st.button("로그아웃"):
            st.session_state.serve_conn.logout()
            st.session_state.is_logged_in = False
            st.session_state.current_repo = None
            st.rerun()

        st.divider()

        # 핸드셰이크 상태
        st.header("보안 핸드셰이크")
        handshake_status = "연결됨" if st.session_state.serve_conn.aes_handle else "연결 안됨"
        st.write(f"**상태:** {handshake_status}")

        if st.button("핸드셰이크 수행"):
            try:
                success, msg = st.session_state.serve_conn.perform_handshake()
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            except Exception as e:
                st.error(f"핸드셰이크 중 오류 발생: {str(e)}")
                st.info("서버 연결을 확인해주세요.")

        st.divider()

        # 가상 카메라 (이미지 폴더 로드)
        st.header("Virtual Camera")
        image_folder = "test_images"
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)
            st.warning(f"'{image_folder}' 폴더에 테스트 이미지를 넣어주세요.")

        image_files = [f for f in os.listdir(image_folder) if f.endswith(('jpg', 'png', 'jpeg'))]
        if image_files:
            selected_image = st.selectbox("이미지 선택", image_files)
        else:
            selected_image = None
            st.info("이미지 파일이 없습니다.")

    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs(["저장소 관리", "문서 관리", "멤버 관리", "Vision AI 분석"])

    # ==================== 탭 1: 저장소 관리 ====================
    with tab1:
        st.subheader("저장소 관리")

        col1, col2 = st.columns(2)

        with col1:
            st.write("### 내 저장소 목록")
            if st.button("저장소 목록 새로고침"):
                repos, msg = st.session_state.serve_conn.get_my_repositories()
                if repos is not None:
                    st.session_state.my_repos = repos
                    st.success(msg)
                else:
                    st.error(msg)

            if 'my_repos' in st.session_state and st.session_state.my_repos:
                for repo in st.session_state.my_repos:
                    with st.expander(f"📁 {repo['name']} (ID: {repo['id']})"):
                        st.write(f"**설명:** {repo['description']}")
                        st.write(f"**타입:** {repo['type']}")
                        st.write(f"**소유자:** {repo['ownerEmail']}")

                        if st.button(f"이 저장소 선택", key=f"select_repo_{repo['id']}"):
                            st.session_state.current_repo = repo
                            st.success(f"저장소 '{repo['name']}'가 선택되었습니다.")

                        if st.button(f"삭제", key=f"delete_repo_{repo['id']}"):
                            success, msg = st.session_state.serve_conn.delete_repository(repo['id'])
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.info("저장소가 없습니다. 새 저장소를 생성해주세요.")

        with col2:
            st.write("### 새 저장소 생성")
            new_repo_name = st.text_input("저장소 이름")
            new_repo_desc = st.text_area("저장소 설명")

            if st.button("저장소 생성", type="primary"):
                if new_repo_name:
                    # 데모용 임시 팀 키
                    encrypted_team_key = "demo_team_key_" + new_repo_name

                    repo_id, msg = st.session_state.serve_conn.create_repository(
                        new_repo_name, new_repo_desc, encrypted_team_key
                    )
                    if repo_id:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("저장소 이름을 입력해주세요.")

        # 선택된 저장소 표시
        if st.session_state.current_repo:
            st.divider()
            st.info(f"**현재 선택된 저장소:** {st.session_state.current_repo['name']} (ID: {st.session_state.current_repo['id']})")

    # ==================== 탭 2: 문서 관리 ====================
    with tab2:
        st.subheader("문서 관리")

        if not st.session_state.current_repo:
            st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.write("### 문서 업로드")
                upload_text = st.text_area("문서 내용", "This is a hydraulic valve (Type-K). Pressure limit: 500bar.")

                if st.button("암호화 및 업로드", type="primary"):
                    if not st.session_state.serve_conn.aes_handle:
                        st.error("먼저 핸드셰이크를 수행해주세요! (사이드바)")
                    else:
                        doc_id, msg = st.session_state.serve_conn.upload_secure_document(
                            upload_text, st.session_state.current_repo['id']
                        )
                        if doc_id:
                            st.success(f"{msg} (Doc ID: {doc_id})")
                            st.session_state.last_doc_id = int(doc_id)
                        else:
                            st.error(msg)

            with col2:
                st.write("### 문서 다운로드")
                doc_id = st.number_input("문서 ID", min_value=1, value=st.session_state.get('last_doc_id', 1))

                if st.button("다운로드 및 복호화"):
                    if not st.session_state.serve_conn.aes_handle:
                        st.error("먼저 핸드셰이크를 수행해주세요! (사이드바)")
                    else:
                        content, msg = st.session_state.serve_conn.get_secure_document(doc_id)
                        if content:
                            st.success(msg)
                            st.text_area("복호화된 내용", content, height=150)
                        else:
                            st.error(msg)

    # ==================== 탭 3: 멤버 관리 ====================
    with tab3:
        st.subheader("멤버 관리")

        if not st.session_state.current_repo:
            st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
        else:
            st.info(f"**저장소:** {st.session_state.current_repo['name']}")

            col1, col2 = st.columns(2)

            with col1:
                st.write("### 멤버 목록")
                if st.button("멤버 목록 새로고침"):
                    members, msg = st.session_state.serve_conn.get_members(st.session_state.current_repo['id'])
                    if members is not None:
                        st.session_state.current_members = members
                        st.success(msg)
                    else:
                        st.error(msg)

                if 'current_members' in st.session_state and st.session_state.current_members:
                    for member in st.session_state.current_members:
                        with st.expander(f"👤 {member['email']} ({member['role']})"):
                            st.write(f"**User ID:** {member['userId']}")

                            # 강퇴 버튼
                            admin_id = st.text_input("관리자 ID", key=f"admin_kick_{member['userId']}")
                            if st.button("강퇴", key=f"kick_{member['userId']}"):
                                if admin_id:
                                    success, msg = st.session_state.serve_conn.kick_member(
                                        st.session_state.current_repo['id'], member['userId'], admin_id
                                    )
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.warning("관리자 ID를 입력해주세요.")

                            # 권한 변경
                            new_role = st.selectbox("새 역할", ["ADMIN", "MEMBER"], key=f"role_{member['userId']}")
                            admin_id_role = st.text_input("관리자 ID", key=f"admin_role_{member['userId']}")
                            if st.button("권한 변경", key=f"update_role_{member['userId']}"):
                                if admin_id_role:
                                    success, msg = st.session_state.serve_conn.update_member_role(
                                        st.session_state.current_repo['id'], member['userId'], admin_id_role, new_role
                                    )
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.warning("관리자 ID를 입력해주세요.")
                else:
                    st.info("멤버가 없거나 목록을 불러오지 않았습니다.")

            with col2:
                st.write("### 멤버 초대")
                invite_email = st.text_input("초대할 사용자 이메일")

                if st.button("초대", type="primary"):
                    if invite_email:
                        # 데모용 임시 암호화된 팀 키
                        encrypted_team_key = "demo_team_key_for_" + invite_email

                        success, msg = st.session_state.serve_conn.invite_member(
                            st.session_state.current_repo['id'], invite_email, encrypted_team_key
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("초대할 사용자의 이메일을 입력해주세요.")

    # ==================== 탭 4: Vision AI 분석 ====================
    with tab4:
        st.subheader("Edge AI Analysis")

        col1, col2 = st.columns(2)

        # 왼쪽: 로봇의 시야 (카메라)
        with col1:
            st.write("### Robot View")
            if selected_image:
                img_path = os.path.join(image_folder, selected_image)
                image = Image.open(img_path)

                # 이미지를 바이트로 변환 (Ollama 전송용)
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format=image.format)
                img_bytes = img_byte_arr.getvalue()

                st.image(image, caption="Captured Image", use_container_width=True)
            else:
                st.info("이미지를 선택해주세요. (사이드바)")

        # 오른쪽: AI의 판단 (RAG vs No-RAG)
        with col2:
            st.write("### AI Analysis")

            vision = VisionEngine()

            tab_a, tab_b = st.tabs(["일반 추론", "보안 RAG 추론"])

            # Tab A: 일반 추론 (보안 DB 없이 그냥 보기)
            with tab_a:
                if st.button("분석 (컨텍스트 없음)", type="primary"):
                    if selected_image:
                        with st.spinner("Analyzing..."):
                            result = vision.analyze_image(img_bytes, "What is this object? Describe it.")
                            st.write(result)
                    else:
                        st.warning("이미지가 없습니다.")

            # Tab B: 보안 RAG 추론 (SeRVe 연동)
            with tab_b:
                doc_id_rag = st.number_input("Document ID (SeRVe)", min_value=1, value=st.session_state.get('last_doc_id', 1))

                if st.button("분석 (SeRVe 연동)", type="primary"):
                    if not st.session_state.serve_conn.aes_handle:
                        st.error("먼저 사이드바에서 SeRVe와 핸드셰이크를 수행해주세요!")
                    elif selected_image:
                        with st.spinner("Fetching Secure Data & Decrypting..."):
                            # 1. SeRVe에서 보안 문서 가져오기
                            context_text, msg = st.session_state.serve_conn.get_secure_document(doc_id_rag)

                            if context_text:
                                st.success(f"Context Loaded: {msg}")
                                with st.expander("Decrypted Context (보안 해제됨)"):
                                    st.info(context_text)

                                # 2. RAG 추론
                                with st.spinner("Thinking with Secure Context..."):
                                    result = vision.analyze_with_context(img_bytes, context_text)
                                    st.markdown("### Result")
                                    st.write(result)
                            else:
                                st.error(msg)
                    else:
                        st.warning("이미지가 없습니다.")
