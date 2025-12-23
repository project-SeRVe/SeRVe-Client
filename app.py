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
    st.session_state.local_vectorstore = None  # 로컬 벡터DB
    st.session_state.vectorstore_info = None  # 벡터DB 메타정보

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
        st.subheader("로컬 벡터DB 관리")

        # ========== 로컬 벡터DB 상태 표시 ==========
        st.write("## 📊 벡터DB 상태")
        if st.session_state.local_vectorstore:
            col_status1, col_status2 = st.columns([3, 1])
            with col_status1:
                st.success(f"✓ 로컬 벡터DB 활성화됨: {st.session_state.vectorstore_info}")
            with col_status2:
                if st.button("🗑️ 초기화", help="벡터DB를 삭제하고 새로 시작합니다"):
                    st.session_state.local_vectorstore = None
                    st.session_state.vectorstore_info = None
                    st.success("로컬 벡터DB가 초기화되었습니다.")
                    st.rerun()
        else:
            st.info("로컬 벡터DB가 없습니다. 아래에서 새로 생성하세요.")

        st.divider()

        # ========== 1. 벡터DB 생성 ==========
        st.write("## 1️⃣ 로컬 벡터DB 생성")

        # 청크 설정 (공통)
        col_chunk1, col_chunk2 = st.columns(2)
        with col_chunk1:
            chunk_size = st.number_input("청크 크기", value=500, min_value=100, max_value=2000, key="chunk_size")
        with col_chunk2:
            chunk_overlap = st.number_input("청크 오버랩", value=50, min_value=0, max_value=500, key="chunk_overlap")

        col_create1, col_create2 = st.columns(2)

        with col_create1:
            st.write("### 텍스트로 생성")
            vector_text_input = st.text_area(
                "문서 내용",
                "This is a hydraulic valve (Type-K). Pressure limit: 500bar. Use only with certified hydraulic fluids.",
                height=150,
                key="vector_text_input"
            )

            if st.button("텍스트로 벡터DB 생성", type="primary", disabled=st.session_state.local_vectorstore is not None):
                if not vector_text_input:
                    st.warning("문서 내용을 입력해주세요.")
                else:
                    try:
                        vision = VisionEngine()
                        with st.spinner("벡터 생성 중..."):
                            vectorstore = vision.create_vector_store(
                                text_content=vector_text_input,
                                collection_name="serve_local_rag",
                                persist_directory=None,
                                chunk_size=chunk_size,
                                chunk_overlap=chunk_overlap
                            )
                            st.session_state.local_vectorstore = vectorstore
                            st.session_state.vectorstore_info = f"{len(vector_text_input)} chars"
                            st.success("✓ 로컬 벡터DB가 생성되었습니다!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"벡터DB 생성 실패: {str(e)}")

            if st.session_state.local_vectorstore:
                st.info("💡 벡터DB가 이미 존재합니다. 새로 생성하려면 먼저 초기화하세요.")

        with col_create2:
            st.write("### 파일로 생성")
            uploaded_file_create = st.file_uploader(
                "텍스트 파일 선택",
                type=['txt', 'md', 'json'],
                key="vector_file_create"
            )

            if uploaded_file_create:
                st.info(f"파일: {uploaded_file_create.name} ({uploaded_file_create.size} bytes)")

            if st.button("파일로 벡터DB 생성", type="primary", disabled=st.session_state.local_vectorstore is not None or uploaded_file_create is None):
                try:
                    file_content = uploaded_file_create.read().decode('utf-8')
                    vision = VisionEngine()
                    with st.spinner("파일 처리 및 벡터 생성 중..."):
                        vectorstore = vision.create_vector_store(
                            text_content=file_content,
                            collection_name="serve_local_rag",
                            persist_directory=None,
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap
                        )
                        st.session_state.local_vectorstore = vectorstore
                        st.session_state.vectorstore_info = f"{uploaded_file_create.name}"
                        st.success(f"✓ '{uploaded_file_create.name}'로부터 벡터DB가 생성되었습니다!")
                        st.rerun()
                except Exception as e:
                    st.error(f"파일 처리 실패: {str(e)}")

            if st.session_state.local_vectorstore:
                st.info("💡 벡터DB가 이미 존재합니다. 새로 생성하려면 먼저 초기화하세요.")

        st.divider()

        # ========== 2. 벡터DB에 문서 추가 ==========
        st.write("## 2️⃣ 로컬 벡터DB에 문서 추가")

        if not st.session_state.local_vectorstore:
            st.warning("먼저 위에서 로컬 벡터DB를 생성해주세요.")
        else:
            col_add1, col_add2 = st.columns(2)

            with col_add1:
                st.write("### 텍스트 추가")
                add_text_input = st.text_area(
                    "추가할 문서 내용",
                    "Safety Warning: Maximum temperature: 80°C. Do not exceed rated pressure.",
                    height=120,
                    key="add_text_input"
                )

                if st.button("텍스트를 벡터DB에 추가", type="secondary"):
                    if not add_text_input:
                        st.warning("추가할 내용을 입력해주세요.")
                    else:
                        try:
                            vision = VisionEngine()
                            with st.spinner("벡터 추가 중..."):
                                vision.add_to_vector_store(
                                    st.session_state.local_vectorstore,
                                    add_text_input,
                                    chunk_size=chunk_size,
                                    chunk_overlap=chunk_overlap
                                )
                                st.success("✓ 텍스트가 벡터DB에 추가되었습니다!")
                        except Exception as e:
                            st.error(f"텍스트 추가 실패: {str(e)}")

            with col_add2:
                st.write("### 파일 추가")
                uploaded_file_add = st.file_uploader(
                    "추가할 파일 선택",
                    type=['txt', 'md', 'json'],
                    key="vector_file_add"
                )

                if uploaded_file_add:
                    st.info(f"파일: {uploaded_file_add.name} ({uploaded_file_add.size} bytes)")

                    if st.button("파일을 벡터DB에 추가", type="secondary"):
                        try:
                            file_content = uploaded_file_add.read().decode('utf-8')
                            vision = VisionEngine()
                            with st.spinner("파일 처리 및 벡터 추가 중..."):
                                vision.add_to_vector_store(
                                    st.session_state.local_vectorstore,
                                    file_content,
                                    chunk_size=chunk_size,
                                    chunk_overlap=chunk_overlap
                                )
                                st.success(f"✓ '{uploaded_file_add.name}' 파일이 벡터DB에 추가되었습니다!")
                        except Exception as e:
                            st.error(f"파일 추가 실패: {str(e)}")

        st.divider()

        # ========== 3. SeRVe 서버에 업로드 ==========
        st.write("## 3️⃣ SeRVe 서버에 업로드")

        if not st.session_state.local_vectorstore:
            st.warning("업로드할 로컬 벡터DB가 없습니다. 먼저 벡터DB를 생성하세요.")
        elif not st.session_state.current_repo:
            st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
        else:
            st.info(f"**저장소:** {st.session_state.current_repo['name']}")

            upload_file_name = st.text_input(
                "서버에 저장할 파일명",
                value="vector_db.json",
                key="upload_vector_filename"
            )

            if st.button("🚀 로컬 벡터DB → SeRVe 서버 업로드", type="primary"):
                if not upload_file_name:
                    st.warning("파일명을 입력해주세요.")
                else:
                    try:
                        vision = VisionEngine()
                        with st.spinner("벡터 추출 중..."):
                            # 벡터 추출
                            vector_data = vision.extract_vectors(st.session_state.local_vectorstore)

                            # JSON으로 직렬화
                            import json
                            vector_json = json.dumps(vector_data)

                            st.info(f"추출된 벡터 개수: {len(vector_data['ids'])}")

                        with st.spinner("암호화 및 업로드 중..."):
                            # SeRVe 서버에 업로드
                            repo_id = get_current_repo_id()
                            success, msg = st.session_state.serve_client.upload_document(
                                vector_json,
                                repo_id,
                                upload_file_name,
                                "application/json"
                            )

                            if success:
                                st.success(f"✓ 벡터DB가 SeRVe 서버에 업로드되었습니다!")
                                st.info(msg)
                            else:
                                st.error(msg)
                    except Exception as e:
                        st.error(f"업로드 실패: {str(e)}")

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

            tab_a, tab_b = st.tabs(["일반 추론", "로컬 벡터DB RAG 추론"])

            # Tab A: 일반 추론 (보안 DB 없이 그냥 보기)
            with tab_a:
                if st.button("분석 (컨텍스트 없음)", type="primary"):
                    if selected_image:
                        with st.spinner("Analyzing..."):
                            result = vision.analyze_image(img_bytes, "What is this object? Describe it.")
                            st.write(result)
                    else:
                        st.warning("이미지가 없습니다.")

            # Tab B: 로컬 벡터DB를 사용한 RAG 추론
            with tab_b:
                if not st.session_state.local_vectorstore:
                    st.warning("로컬 벡터DB가 없습니다. 먼저 '문서 관리' 탭에서 벡터DB를 생성하거나 다운로드하세요.")
                else:
                    st.info(f"✓ 사용 중인 벡터DB: {st.session_state.vectorstore_info}")

                    # 검색 파라미터 설정
                    col_param1, col_param2 = st.columns(2)
                    with col_param1:
                        top_k = st.number_input("검색할 청크 수 (top_k)", value=3, min_value=1, max_value=10, key="rag_top_k")
                    with col_param2:
                        st.write("")  # 간격

                    search_query = st.text_input(
                        "검색 쿼리 (선택사항)",
                        value="Describe technical specifications and safety information",
                        key="rag_query"
                    )

                    if st.button("분석 (로컬 벡터DB 활용)", type="primary"):
                        if not selected_image:
                            st.warning("이미지가 없습니다.")
                        else:
                            with st.spinner("로컬 벡터DB에서 관련 문맥 검색 중..."):
                                try:
                                    # 로컬 벡터DB를 사용한 RAG 추론
                                    result = vision.analyze_with_vectorstore(
                                        img_bytes,
                                        st.session_state.local_vectorstore,
                                        top_k=top_k,
                                        query=search_query
                                    )

                                    st.markdown("### 🤖 AI Analysis Result")
                                    st.write(result)

                                    # 검색된 문맥도 표시 (디버깅용)
                                    with st.expander("검색된 문맥 확인"):
                                        relevant_docs = st.session_state.local_vectorstore.similarity_search(
                                            search_query, k=top_k
                                        )
                                        for i, doc in enumerate(relevant_docs):
                                            st.markdown(f"**청크 {i+1}:**")
                                            st.info(doc.page_content)
                                except Exception as e:
                                    st.error(f"RAG 추론 실패: {str(e)}")
