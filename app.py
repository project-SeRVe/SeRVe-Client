import streamlit as st
import os
from PIL import Image
import io
import requests
from vision_engine import VisionEngine
from serve_sdk import ServeClient
from config import SERVER_URL

# 페이지 설정
st.set_page_config(page_title="SeRVe: Secure Edge AI", layout="wide")

# 세션 상태 초기화
if 'serve_client' not in st.session_state:
    st.session_state.serve_client = ServeClient(SERVER_URL)
    st.session_state.is_logged_in = False
    st.session_state.current_repo = None
    st.session_state.server_connected = False
    st.session_state.server_url = SERVER_URL
    st.session_state.success_message = None  # 성공 메시지 표시용

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
    return st.session_state.serve_client.session.user_id is not None

# 현재 저장소 ID 가져오기
def get_current_repo_id():
    """현재 선택된 저장소의 ID를 반환"""
    if not st.session_state.current_repo:
        return None
    # 서버 응답: Teamid (대문자) 또는 teamid (소문자) 모두 처리
    return st.session_state.current_repo.get('Teamid') or st.session_state.current_repo.get('teamid')

# 저장소 목록에서 ID 추출
def get_repo_id(repo):
    """저장소 딕셔너리에서 ID를 추출"""
    # 서버 응답: Teamid (대문자) 또는 teamid (소문자) 모두 처리
    return repo.get('Teamid') or repo.get('teamid')

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
        connect_button = st.button("서버 연결", type="primary", width="stretch")

    if connect_button:
        with st.spinner("서버 연결 및 보안 채널 수립 중..."):
            # 1. 서버 연결 확인
            success, msg = check_server_connection(server_url_input)

            if success:
                # URL 업데이트 (Config 및 새 클라이언트 인스턴스 생성)
                import config
                config.SERVER_URL = server_url_input
                st.session_state.server_url = server_url_input
                st.session_state.serve_client = ServeClient(server_url_input)

                # 2. 연결 성공
                st.session_state.server_connected = True
                st.success(f"서버 연결 성공!\n{server_url_input}")
                st.rerun() # 성공 시 새로고침하여 로그인 화면으로 이동
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
        st.success(f"연결됨\nServer: {st.session_state.server_url}")

        if st.button("서버 연결 변경"):
            st.session_state.server_connected = False
            st.session_state.serve_client.logout() # 로그아웃 처리
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
                    success, msg = st.session_state.serve_client.login(login_email, login_password)
                    if success:
                        # 로그인 성공 시 이전 세션 데이터 초기화
                        st.session_state.is_logged_in = True
                        st.session_state.current_repo = None
                        st.session_state.success_message = None
                        # 기존 데이터 초기화
                        if 'my_repos' in st.session_state:
                            del st.session_state.my_repos
                        if 'current_documents' in st.session_state:
                            del st.session_state.current_documents
                        if 'current_members' in st.session_state:
                            del st.session_state.current_members
                        st.success(msg)
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

        st.info("회원가입 시 자동으로 공개키/개인키 쌍이 생성됩니다.")

        if st.button("회원가입", type="primary"):
            if signup_email and signup_password and signup_password_confirm:
                if signup_password != signup_password_confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    try:
                        success, msg = st.session_state.serve_client.signup(
                            signup_email, signup_password
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
            st.session_state.serve_client.logout()
            st.session_state.is_logged_in = False
            st.session_state.current_repo = None
            st.rerun()

        st.divider()

        st.header("사용자 정보")
        st.write(f"**이메일:** {st.session_state.serve_client.session.email}")
        st.write(f"**User ID:** {st.session_state.serve_client.session.user_id}")

        if st.button("로그아웃"):
            st.session_state.serve_client.logout()
            st.session_state.is_logged_in = False
            st.session_state.current_repo = None
            st.rerun()

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
    tab1, tab2, tab3, tab4 = st.tabs(["저장소 관리", "문서 관리", "멤버 관리", "추론"])

    # ==================== 탭 1: 저장소 관리 ====================
    with tab1:
        st.subheader("저장소 관리")

        # 성공 메시지 표시 (rerun 후)
        if st.session_state.success_message:
            st.success(st.session_state.success_message)
            st.session_state.success_message = None  # 메시지 초기화

        # 탭 진입 시 자동 새로고침
        if 'my_repos' not in st.session_state:
            repos, msg = st.session_state.serve_client.get_my_repositories()
            if repos is not None:
                st.session_state.my_repos = repos

        col1, col2 = st.columns(2)

        with col1:
            st.write("### 내 저장소 목록")
            if st.button("저장소 목록 새로고침"):
                repos, msg = st.session_state.serve_client.get_my_repositories()
                if repos is not None:
                    st.session_state.my_repos = repos
                    st.success(msg)
                else:
                    st.error(msg)

            if 'my_repos' in st.session_state and st.session_state.my_repos:
                for repo in st.session_state.my_repos:
                    repo_id = get_repo_id(repo)
                    with st.expander(f"📁 {repo['name']} (ID: {repo_id})"):
                        st.write(f"**설명:** {repo['description']}")
                        st.write(f"**타입:** {repo['type']}")
                        st.write(f"**소유자:** {repo['ownerEmail']}")

                        if st.button(f"이 저장소 선택", key=f"select_repo_{repo_id}"):
                            st.session_state.current_repo = repo
                            st.success(f"저장소 '{repo['name']}'가 선택되었습니다.")

                        if st.button(f"삭제", key=f"delete_repo_{repo_id}"):
                            success, msg = st.session_state.serve_client.delete_repository(repo_id)
                            if success:
                                # 저장소 목록 새로고침
                                repos, _ = st.session_state.serve_client.get_my_repositories()
                                if repos is not None:
                                    st.session_state.my_repos = repos
                                # 삭제된 저장소가 현재 선택된 저장소인 경우 초기화
                                if st.session_state.current_repo and get_repo_id(st.session_state.current_repo) == repo_id:
                                    st.session_state.current_repo = None
                                # 성공 메시지를 세션에 저장하고 rerun
                                st.session_state.success_message = f"저장소가 성공적으로 삭제되었습니다: {msg}"
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
                    repo_id, msg = st.session_state.serve_client.create_repository(
                        new_repo_name, new_repo_desc
                    )
                    if repo_id:
                        # 저장소 목록 새로고침
                        repos, _ = st.session_state.serve_client.get_my_repositories()
                        if repos is not None:
                            st.session_state.my_repos = repos
                        # 성공 메시지를 세션에 저장하고 rerun
                        st.session_state.success_message = f"저장소가 성공적으로 생성되었습니다: {msg}"
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("저장소 이름을 입력해주세요.")

        # 선택된 저장소 표시
        if st.session_state.current_repo:
            st.divider()
            current_repo_id = get_current_repo_id()
            st.info(f"**현재 선택된 저장소:** {st.session_state.current_repo['name']} (ID: {current_repo_id})")

    # ==================== 탭 2: 문서 관리 ====================
    with tab2:
        st.subheader("문서 관리")

        if not st.session_state.current_repo:
            st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
        else:
            # 탭 진입 시 자동 새로고침 (저장소가 선택된 경우에만)
            if 'current_documents' not in st.session_state:
                repo_id = get_current_repo_id()
                docs, msg = st.session_state.serve_client.get_documents(repo_id)
                if docs is not None:
                    st.session_state.current_documents = docs

            # 문서 목록 표시
            st.write("### 문서 목록")
            col_list1, col_list2 = st.columns([3, 1])

            with col_list1:
                st.info(f"**저장소:** {st.session_state.current_repo['name']}")

            with col_list2:
                if st.button("문서 목록 새로고침"):
                    repo_id = get_current_repo_id()
                    docs, msg = st.session_state.serve_client.get_documents(repo_id)
                    if docs is not None:
                        st.session_state.current_documents = docs
                        st.success(msg)
                    else:
                        st.error(msg)

            # 문서 목록 표시
            if 'current_documents' in st.session_state and st.session_state.current_documents:
                for doc in st.session_state.current_documents:
                    doc_id = doc.get('docId')
                    file_name = doc.get('fileName', 'N/A')
                    file_type = doc.get('fileType', 'N/A')
                    uploader_id = doc.get('uploaderId', 'N/A')
                    created_at = doc.get('createdAt', 'N/A')

                    with st.expander(f"📄 {file_name} (ID: {doc_id})"):
                        col_a, col_b, col_c = st.columns([2, 1, 1])

                        with col_a:
                            st.write(f"**파일 타입:** {file_type}")
                            st.write(f"**업로더:** {uploader_id}")
                            st.write(f"**생성 시간:** {created_at}")

                        with col_b:
                            if st.button("다운로드", key=f"download_{doc_id}"):
                                repo_id = get_current_repo_id()
                                content, msg = st.session_state.serve_client.download_document(
                                    doc_id, repo_id
                                )
                                if content:
                                    st.success(msg)
                                    st.text_area("복호화된 내용", content, height=150, key=f"content_{doc_id}")
                                else:
                                    st.error(msg)

                        with col_c:
                            if st.button("삭제", key=f"delete_doc_{doc_id}"):
                                repo_id = get_current_repo_id()
                                success, msg = st.session_state.serve_client.delete_document(
                                    repo_id, str(doc_id)
                                )
                                if success:
                                    st.success(msg)
                                    # 문서 목록 새로고침
                                    docs, _ = st.session_state.serve_client.get_documents(repo_id)
                                    if docs is not None:
                                        st.session_state.current_documents = docs
                                    st.rerun()
                                else:
                                    st.error(msg)
            else:
                st.info("문서가 없거나 목록을 불러오지 않았습니다. '문서 목록 새로고침' 버튼을 클릭하세요.")

            st.divider()

            # 문서 업로드 / 다운로드
            col1, col2 = st.columns(2)

            with col1:
                st.write("### 문서 업로드")
                upload_file_name = st.text_input("파일명", value="document.txt", key="upload_file_name")
                upload_file_type = st.selectbox(
                    "파일 타입",
                    ["text/plain", "application/json", "text/markdown", "application/octet-stream"],
                    key="upload_file_type"
                )
                upload_text = st.text_area("문서 내용", "This is a hydraulic valve (Type-K). Pressure limit: 500bar.")

                if st.button("암호화 및 업로드", type="primary"):
                    if not upload_file_name:
                        st.warning("파일명을 입력해주세요.")
                    else:
                        repo_id = get_current_repo_id()
                        success, msg = st.session_state.serve_client.upload_document(
                            upload_text, repo_id, upload_file_name, upload_file_type
                        )
                        if success:
                            st.success(msg)
                            # 문서 목록 자동 새로고침
                            docs, _ = st.session_state.serve_client.get_documents(repo_id)
                            if docs is not None:
                                st.session_state.current_documents = docs
                                # 마지막 문서 ID 업데이트 (가장 최근에 업로드된 문서)
                                if docs:
                                    st.session_state.last_doc_id = docs[-1].get('docId', '')
                        else:
                            st.error(msg)

            with col2:
                st.write("### 문서 다운로드 (ID로 직접 조회)")
                doc_id_input = st.text_input("문서 ID (UUID)", value=st.session_state.get('last_doc_id', ''), key="doc_id_download")

                if st.button("다운로드 및 복호화"):
                    if not doc_id_input:
                        st.warning("문서 ID를 입력해주세요.")
                    else:
                        repo_id = get_current_repo_id()
                        content, msg = st.session_state.serve_client.download_document(
                            doc_id_input, repo_id
                        )
                        if content:
                            st.success(msg)
                            st.text_area("복호화된 내용", content, height=150)
                        else:
                            st.error(msg)

    # ==================== 탭 3: 멤버 관리 ====================
    with tab3:
        st.subheader("멤버 관리")

        # 성공 메시지 표시 (rerun 후)
        if st.session_state.success_message:
            st.success(st.session_state.success_message)
            st.session_state.success_message = None  # 메시지 초기화

        if not st.session_state.current_repo:
            st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
        else:
            # 탭 진입 시 자동 새로고침 (저장소가 선택된 경우에만)
            if 'current_members' not in st.session_state:
                repo_id = get_current_repo_id()
                members, msg = st.session_state.serve_client.get_members(repo_id)
                if members is not None:
                    st.session_state.current_members = members

            st.info(f"**저장소:** {st.session_state.current_repo['name']}")

            col1, col2 = st.columns(2)

            with col1:
                st.write("### 멤버 목록")
                if st.button("멤버 목록 새로고침"):
                    repo_id = get_current_repo_id()
                    members, msg = st.session_state.serve_client.get_members(repo_id)
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
                            if st.button("강퇴", key=f"kick_{member['userId']}"):
                                repo_id = get_current_repo_id()
                                success, msg = st.session_state.serve_client.kick_member(
                                    repo_id, member['userId']
                                )
                                if success:
                                    # 멤버 목록 새로고침
                                    members, _ = st.session_state.serve_client.get_members(repo_id)
                                    if members is not None:
                                        st.session_state.current_members = members
                                    # 성공 메시지를 세션에 저장하고 rerun
                                    st.session_state.success_message = f"멤버가 성공적으로 강퇴되었습니다: {msg}"
                                    st.rerun()
                                else:
                                    st.error(msg)

                            # 권한 변경
                            new_role = st.selectbox("새 역할", ["ADMIN", "MEMBER"], key=f"role_{member['userId']}")
                            if st.button("권한 변경", key=f"update_role_{member['userId']}"):
                                repo_id = get_current_repo_id()
                                success, msg = st.session_state.serve_client.update_member_role(
                                    repo_id, member['userId'], new_role
                                )
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                else:
                    st.info("멤버가 없거나 목록을 불러오지 않았습니다.")

            with col2:
                st.write("### 멤버 초대")
                invite_email = st.text_input("초대할 사용자 이메일")

                if st.button("초대", type="primary"):
                    if invite_email:
                        repo_id = get_current_repo_id()
                        success, msg = st.session_state.serve_client.invite_member(
                            repo_id, invite_email
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

                st.image(image, caption="Captured Image", width="stretch")
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
                doc_id_rag = st.text_input("Document ID (SeRVe)", value=st.session_state.get('last_doc_id', ''), key="doc_id_rag")

                if st.button("분석 (SeRVe 연동)", type="primary"):
                    if not st.session_state.current_repo:
                        st.error("먼저 저장소를 선택해주세요! (저장소 관리 탭)")
                    elif not doc_id_rag:
                        st.warning("문서 ID를 입력해주세요.")
                    elif selected_image:
                        with st.spinner("Fetching Secure Data & Decrypting..."):
                            # 1. SeRVe에서 보안 문서 가져오기
                            repo_id = get_current_repo_id()
                            context_text, msg = st.session_state.serve_client.download_document(
                                doc_id_rag, repo_id
                            )

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
