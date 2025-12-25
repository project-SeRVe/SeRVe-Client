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

    # 로컬 벡터DB 자동 로드 (디스크에 저장된 경우)
    try:
        vision = VisionEngine()
        loaded_vectorstore = vision.load_vector_store(
            collection_name="serve_local_rag",
            persist_directory="./local_vectorstore"
        )
        st.session_state.local_vectorstore = loaded_vectorstore
        if loaded_vectorstore is None:
            # 손상된 벡터스토어가 자동으로 정리되었을 수 있음
            print("벡터스토어가 없거나 손상되어 초기화되었습니다.")
    except Exception as e:
        st.session_state.local_vectorstore = None
        error_msg = str(e).lower()
        print(f"벡터스토어 자동 로드 실패: {str(e)}")

        # 읽기 전용 오류 또는 데이터베이스 오류 시 강력한 정리 수행
        if "readonly" in error_msg or "database" in error_msg or "attempt to write" in error_msg:
            print("손상된 벡터스토어 감지 - 강력한 정리 수행 중...")
            try:
                import shutil
                import time
                import gc

                persist_dir = "./local_vectorstore"
                if os.path.exists(persist_dir):
                    # 가비지 컬렉션
                    gc.collect()
                    time.sleep(0.3)

                    # 디렉토리 삭제 재시도
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            shutil.rmtree(persist_dir)
                            print("손상된 벡터스토어 디렉토리를 삭제했습니다.")
                            break
                        except Exception as retry_error:
                            if retry < max_retries - 1:
                                print(f"삭제 재시도 중... ({retry + 1}/{max_retries})")
                                gc.collect()
                                time.sleep(0.5)
                            else:
                                print(f"디렉토리 삭제 실패. 앱 재시작 후 다시 시도하거나 수동으로 '{persist_dir}' 디렉토리를 삭제해주세요.")
            except Exception as cleanup_error:
                print(f"정리 중 오류: {str(cleanup_error)}")
        else:
            # 다른 종류의 오류 - 일반 정리
            try:
                import shutil
                persist_dir = "./local_vectorstore"
                if os.path.exists(persist_dir):
                    shutil.rmtree(persist_dir)
                    print("벡터스토어 디렉토리를 삭제했습니다.")
            except Exception as cleanup_error:
                print(f"정리 중 오류: {str(cleanup_error)}")

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

    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs(["원격 저장소 관리", "문서 관리", "멤버 관리", "추론"])

    # ==================== 탭 1: 저장소 관리 ====================
    with tab1:
        st.subheader("원격 저장소 관리")

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
            st.write("### 내 원격 저장소 목록")
            if st.button("원격 저장소 목록 새로고침"):
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

                        if st.button(f"이 원격 저장소 선택", key=f"select_repo_{repo_id}"):
                            st.session_state.current_repo = repo
                            st.success(f"원격 저장소 '{repo['name']}'가 선택되었습니다.")

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
                                st.session_state.success_message = f"원격 저장소가 성공적으로 삭제되었습니다: {msg}"
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.info("원격 저장소가 없습니다. 새 원격 저장소를 생성해주세요.")

        with col2:
            st.write("### 새 원격 저장소 생성")
            new_repo_name = st.text_input("원격 저장소 이름")
            new_repo_desc = st.text_area("원격 저장소 설명")

            if st.button("원격 저장소 생성", type="primary"):
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
                        st.session_state.success_message = f"원격 저장소가 성공적으로 생성되었습니다: {msg}"
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("원격 저장소 이름을 입력해주세요.")

        # 선택된 저장소 표시
        if st.session_state.current_repo:
            st.divider()
            current_repo_id = get_current_repo_id()
            st.info(f"**현재 선택된 원격 저장소:** {st.session_state.current_repo['name']} (ID: {current_repo_id})")

    # ==================== 탭 2: 문서 관리 ====================
    with tab2:
        st.subheader("로컬 벡터DB 관리")

        # ========== 로컬 벡터DB 상태 표시 ==========
        st.write("## 📊 벡터DB 상태")
        if st.session_state.local_vectorstore:
            col_status1, col_status2 = st.columns([3, 1])
            with col_status1:
                st.success(f"✓ 로컬 벡터DB 활성화됨")
            with col_status2:
                if st.button("🗑️ 초기화", help="벡터DB를 삭제하고 새로 시작합니다"):
                    try:
                        vision = VisionEngine()
                        # ChromaDB 리소스를 안전하게 정리
                        vision.cleanup_vector_store(
                            st.session_state.local_vectorstore,
                            persist_directory="./local_vectorstore"
                        )
                        # 추가 정리
                        import gc
                        import time
                        st.session_state.local_vectorstore = None
                        gc.collect()
                        time.sleep(0.5)
                        gc.collect()
                        st.success("로컬 벡터DB가 초기화되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"초기화 중 오류: {str(e)}")
                        # 오류가 발생해도 세션 상태는 초기화
                        st.session_state.local_vectorstore = None
                        st.rerun()
        else:
            st.info("로컬 벡터DB가 없습니다. 아래에서 새로 생성하세요.")

        st.divider()

        # ========== 1. 벡터DB 생성 ==========
        st.write("## 1️⃣ 로컬 저장소(벡터DB) 생성")

        # 청크 설정 (공통)
        col_chunk1, col_chunk2 = st.columns(2)
        with col_chunk1:
            chunk_size = st.number_input("청크 크기", value=500, min_value=100, max_value=2000, key="chunk_size")
        with col_chunk2:
            chunk_overlap = st.number_input("청크 오버랩", value=50, min_value=0, max_value=500, key="chunk_overlap")

        col_create1, col_create2 = st.columns(2)

        with col_create1:
            st.write("### 텍스트로 생성")
            vector_text_name = st.text_input(
                "문서 이름",
                "Hydraulic Valve Manual",
                key="vector_text_name"
            )
            vector_text_input = st.text_area(
                "문서 내용",
                "This is a hydraulic valve (Type-K). Pressure limit: 500bar. Use only with certified hydraulic fluids.",
                height=120,
                key="vector_text_input"
            )

            if st.button("텍스트로 벡터DB 생성", type="primary", disabled=st.session_state.local_vectorstore is not None):
                if not vector_text_input:
                    st.warning("문서 내용을 입력해주세요.")
                elif not vector_text_name:
                    st.warning("문서 이름을 입력해주세요.")
                else:
                    try:
                        vision = VisionEngine()
                        with st.spinner("벡터 생성 중..."):
                            vectorstore = vision.create_vector_store(
                                text_content=vector_text_input,
                                collection_name="serve_local_rag",
                                persist_directory="./local_vectorstore",
                                chunk_size=chunk_size,
                                chunk_overlap=chunk_overlap,
                                document_name=vector_text_name
                            )
                            st.session_state.local_vectorstore = vectorstore
                            st.success("✓ 로컬 벡터DB가 생성되었습니다!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"벡터DB 생성 실패: {str(e)}")

            if st.session_state.local_vectorstore:
                st.info("💡 벡터DB가 생성되었습니다. 새로 생성하려면 먼저 초기화하세요.")

        with col_create2:
            st.write("### 파일로 생성")
            uploaded_file_create = st.file_uploader(
                "텍스트 파일 선택",
                type=['txt', 'md', 'json'],
                key="vector_file_create"
            )

            if uploaded_file_create:
                st.info(f"파일: {uploaded_file_create.name} ({uploaded_file_create.size} bytes)")

            vector_file_name = st.text_input(
                "문서 이름",
                value=uploaded_file_create.name if uploaded_file_create else "",
                key="vector_file_name"
            )

            if st.button("파일로 벡터DB 생성", type="primary", disabled=st.session_state.local_vectorstore is not None or uploaded_file_create is None):
                if not vector_file_name:
                    st.warning("문서 이름을 입력해주세요.")
                else:
                    try:
                        file_content = uploaded_file_create.read().decode('utf-8')
                        vision = VisionEngine()
                        with st.spinner("파일 처리 및 벡터 생성 중..."):
                            vectorstore = vision.create_vector_store(
                                text_content=file_content,
                                collection_name="serve_local_rag",
                                persist_directory="./local_vectorstore",
                                chunk_size=chunk_size,
                                chunk_overlap=chunk_overlap,
                                document_name=vector_file_name
                            )
                            st.session_state.local_vectorstore = vectorstore
                            st.success(f"✓ '{vector_file_name}'로부터 벡터DB가 생성되었습니다!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"파일 처리 실패: {str(e)}")

            if st.session_state.local_vectorstore:
                st.info("💡 벡터DB가 생성되었습니다. 새로 생성하려면 먼저 초기화하세요.")

        st.divider()

        # ========== 2. 벡터DB에 문서 추가 ==========
        st.write("## 2️⃣ 로컬 저장소(벡터DB)에 문서 추가")

        if not st.session_state.local_vectorstore:
            st.warning("먼저 위에서 로컬 벡터DB를 생성해주세요.")
        else:
            col_add1, col_add2 = st.columns(2)

            with col_add1:
                st.write("### 텍스트 추가")
                add_text_name = st.text_input(
                    "문서 이름",
                    "Safety Warning",
                    key="add_text_name"
                )
                add_text_input = st.text_area(
                    "추가할 문서 내용",
                    "Safety Warning: Maximum temperature: 80°C. Do not exceed rated pressure.",
                    height=90,
                    key="add_text_input"
                )

                if st.button("텍스트를 벡터DB에 추가", type="secondary"):
                    if not add_text_input:
                        st.warning("추가할 내용을 입력해주세요.")
                    elif not add_text_name:
                        st.warning("문서 이름을 입력해주세요.")
                    else:
                        try:
                            vision = VisionEngine()
                            with st.spinner("벡터 추가 중..."):
                                vision.add_to_vector_store(
                                    st.session_state.local_vectorstore,
                                    add_text_input,
                                    chunk_size=chunk_size,
                                    chunk_overlap=chunk_overlap,
                                    document_name=add_text_name
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

                add_file_name = st.text_input(
                    "문서 이름",
                    value=uploaded_file_add.name if uploaded_file_add else "",
                    key="add_file_name"
                )

                if uploaded_file_add:
                    if st.button("파일을 벡터DB에 추가", type="secondary"):
                        if not add_file_name:
                            st.warning("문서 이름을 입력해주세요.")
                        else:
                            try:
                                file_content = uploaded_file_add.read().decode('utf-8')
                                vision = VisionEngine()
                                with st.spinner("파일 처리 및 벡터 추가 중..."):
                                    vision.add_to_vector_store(
                                        st.session_state.local_vectorstore,
                                        file_content,
                                        chunk_size=chunk_size,
                                        chunk_overlap=chunk_overlap,
                                        document_name=add_file_name
                                    )
                                    st.success(f"✓ '{add_file_name}' 파일이 벡터DB에 추가되었습니다!")
                            except Exception as e:
                                st.error(f"파일 추가 실패: {str(e)}")

        st.divider()

        # ========== 3. 청크 관리 (로컬 & 원격) ==========
        st.write("## 3️⃣ 청크 관리(업로드, 다운로드, 삭제)")

        col_local, col_remote = st.columns(2)

        # ========== 왼쪽: 로컬 벡터 DB 청크 목록 ==========
        with col_local:
            st.write("### 📊 로컬 저장소(벡터DB)")

            if not st.session_state.local_vectorstore:
                st.info("로컬 벡터DB가 없습니다.")
            else:
                if st.button("🔄 로컬 청크 목록 새로고침", key="refresh_local_chunks"):
                    try:
                        vision = VisionEngine()
                        vector_data = vision.extract_vectors(st.session_state.local_vectorstore)

                        # 세션에 저장
                        st.session_state.local_chunks_data = vector_data
                        st.success(f"✓ {len(vector_data['ids'])}개 청크 로드")
                    except Exception as e:
                        st.error(f"청크 추출 실패: {str(e)}")

                # 로컬 청크 표시
                if 'local_chunks_data' in st.session_state:
                    vector_data = st.session_state.local_chunks_data
                    num_chunks = len(vector_data['ids'])

                    # 문서별로 청크 그룹화
                    docs_by_name = {}
                    for i in range(num_chunks):
                        metadata = vector_data['metadatas'][i] if vector_data['metadatas'] else {}
                        doc_name = metadata.get('document_name', 'Unnamed Document')

                        if doc_name not in docs_by_name:
                            docs_by_name[doc_name] = []
                        docs_by_name[doc_name].append(i)

                    st.info(f"**문서 수:** {len(docs_by_name)}, **총 청크:** {num_chunks}")

                    # 청크 선택 상태 초기화
                    if 'selected_local_chunks' not in st.session_state:
                        st.session_state.selected_local_chunks = set()

                    # 청크 목록 표시 (문서별로 그룹화, 스크롤 가능)
                    with st.container(height=300):
                        for doc_name, chunk_indices in docs_by_name.items():
                            # 문서별 expander
                            with st.expander(f"📄 {doc_name} ({len(chunk_indices)}개 청크)", expanded=True):
                                # 문서 전체 선택 체크박스
                                doc_select_key = f"select_doc_{doc_name}"
                                doc_all_selected = all(idx in st.session_state.selected_local_chunks for idx in chunk_indices)

                                # 이전 상태 저장 (실제 클릭 감지용)
                                prev_select_key = f"_prev_select_doc_{doc_name}"
                                if prev_select_key not in st.session_state:
                                    st.session_state[prev_select_key] = doc_all_selected

                                select_doc = st.checkbox(
                                    f"전체 선택",
                                    value=doc_all_selected,
                                    key=doc_select_key
                                )

                                # 실제로 체크박스를 클릭했는지 확인 (이전 상태와 현재 상태 비교)
                                if select_doc != st.session_state[prev_select_key]:
                                    if select_doc:
                                        # 모든 청크 선택
                                        for idx in chunk_indices:
                                            st.session_state.selected_local_chunks.add(idx)
                                            st.session_state[f"local_chunk_{idx}"] = True
                                    else:
                                        # 모든 청크 선택 해제
                                        for idx in chunk_indices:
                                            st.session_state.selected_local_chunks.discard(idx)
                                            st.session_state[f"local_chunk_{idx}"] = False
                                    st.session_state[prev_select_key] = select_doc
                                else:
                                    # 개별 체크박스 변경으로 인한 상태 업데이트
                                    st.session_state[prev_select_key] = doc_all_selected

                                # 청크 목록
                                for i in chunk_indices:
                                    chunk_doc = vector_data['documents'][i] if vector_data['documents'] else ""
                                    chunk_preview = chunk_doc[:40] + "..." if len(chunk_doc) > 40 else chunk_doc

                                    # 청크 체크박스 상태 초기화
                                    if f"local_chunk_{i}" not in st.session_state:
                                        st.session_state[f"local_chunk_{i}"] = i in st.session_state.selected_local_chunks

                                    is_selected = st.checkbox(
                                        f"Chunk {i}: {chunk_preview}",
                                        key=f"local_chunk_{i}"
                                    )

                                    if is_selected:
                                        st.session_state.selected_local_chunks.add(i)
                                    else:
                                        st.session_state.selected_local_chunks.discard(i)

                    st.write(f"**선택된 청크:** {len(st.session_state.selected_local_chunks)}개")

                    # 업로드/삭제 버튼
                    st.divider()

                    col_upload, col_delete = st.columns(2)

                    with col_upload:
                        st.write("**청크 업로드**")
                        upload_to_doc = st.text_input(
                            "문서 이름",
                            value="local_chunks",
                            key="upload_local_chunks_docname"
                        )

                        if st.button("⬆️ 선택한 청크 업로드", type="primary", key="upload_selected_local"):
                            if len(st.session_state.selected_local_chunks) == 0:
                                st.warning("업로드할 청크를 선택해주세요.")
                            elif not upload_to_doc:
                                st.warning("문서 이름을 입력해주세요.")
                            else:
                                try:
                                    import json
                                    repo_id = get_current_repo_id()

                                    # 선택된 청크만 추출
                                    selected_indices = sorted(list(st.session_state.selected_local_chunks))
                                    chunks_data = []
                                    for idx, chunk_idx in enumerate(selected_indices):
                                        chunk_content = {
                                            'id': vector_data['ids'][chunk_idx],
                                            'embedding': vector_data['embeddings'][chunk_idx] if vector_data['embeddings'] else None,
                                            'document': vector_data['documents'][chunk_idx] if vector_data['documents'] else None,
                                            'metadata': vector_data['metadatas'][chunk_idx] if vector_data['metadatas'] else None
                                        }
                                        chunks_data.append({
                                            "chunkIndex": idx,  # 새 인덱스 (0부터 시작)
                                            "data": json.dumps(chunk_content)
                                        })

                                    with st.spinner("문서 생성 중..."):
                                        # 문서 메타데이터 생성
                                        success, msg = st.session_state.serve_client.upload_document(
                                            f"Local chunks upload: {len(chunks_data)} chunks",
                                            repo_id,
                                            upload_to_doc,
                                            "application/json"
                                        )

                                        if not success:
                                            st.error(f"문서 생성 실패: {msg}")
                                        else:
                                            # 문서 ID 조회
                                            docs, _ = st.session_state.serve_client.get_documents(repo_id)
                                            if docs and len(docs) > 0:
                                                latest_doc = docs[-1]
                                                doc_id = latest_doc.get('docId')

                                                # 청크 업로드
                                                with st.spinner(f"청크 업로드 중... ({len(chunks_data)}개)"):
                                                    success, msg = st.session_state.serve_client.upload_chunks_to_document(
                                                        doc_id, repo_id, chunks_data
                                                    )

                                                    if success:
                                                        st.success(f"✓ {len(chunks_data)}개 청크 업로드 완료!")
                                                        # 선택 초기화
                                                        st.session_state.selected_local_chunks = set()
                                                        # 모든 청크 체크박스 상태 초기화
                                                        for i in range(num_chunks):
                                                            if f"local_chunk_{i}" in st.session_state:
                                                                del st.session_state[f"local_chunk_{i}"]
                                                        # 문서 전체 선택 체크박스 초기화
                                                        for doc_name in docs_by_name.keys():
                                                            if f"select_doc_{doc_name}" in st.session_state:
                                                                del st.session_state[f"select_doc_{doc_name}"]
                                                    else:
                                                        st.error(f"청크 업로드 실패: {msg}")

                                except Exception as e:
                                    st.error(f"업로드 오류: {str(e)}")
                                    import traceback
                                    st.code(traceback.format_exc())

                    with col_delete:
                        st.write("**청크 삭제**")
                        st.write("")  # 간격 맞추기
                        st.write("")  # 간격 맞추기

                        if st.button("🗑️ 선택한 청크 삭제", type="secondary", key="delete_selected_local"):
                            if len(st.session_state.selected_local_chunks) == 0:
                                st.warning("삭제할 청크를 선택해주세요.")
                            else:
                                try:
                                    # 선택된 청크의 ID 수집
                                    selected_indices = sorted(list(st.session_state.selected_local_chunks))
                                    ids_to_delete = [vector_data['ids'][idx] for idx in selected_indices]

                                    with st.spinner(f"{len(ids_to_delete)}개 청크 삭제 중..."):
                                        # 벡터DB에서 삭제
                                        st.session_state.local_vectorstore.delete(ids=ids_to_delete)

                                        # 삭제 후 벡터스토어가 비어있는지 확인
                                        collection = st.session_state.local_vectorstore._collection
                                        if collection.count() == 0:
                                            # 빈 벡터스토어는 안전하게 정리
                                            try:
                                                vision = VisionEngine()
                                                # 벡터스토어 정리
                                                vision.cleanup_vector_store(
                                                    st.session_state.local_vectorstore,
                                                    persist_directory="./local_vectorstore"
                                                )
                                                # 추가 정리
                                                import gc
                                                import time
                                                st.session_state.local_vectorstore = None
                                                gc.collect()
                                                time.sleep(0.5)
                                                gc.collect()
                                            except Exception as e:
                                                print(f"벡터스토어 정리 중 오류: {str(e)}")
                                                st.session_state.local_vectorstore = None
                                            st.success(f"✓ 모든 청크가 삭제되어 로컬 벡터DB가 초기화되었습니다!")
                                        else:
                                            st.success(f"✓ {len(ids_to_delete)}개 청크가 로컬 벡터DB에서 삭제되었습니다!")

                                        # 선택 초기화
                                        st.session_state.selected_local_chunks = set()
                                        # 삭제된 청크의 위젯 상태 초기화
                                        for idx in selected_indices:
                                            if f"local_chunk_{idx}" in st.session_state:
                                                del st.session_state[f"local_chunk_{idx}"]
                                        # 문서 전체 선택 체크박스 초기화
                                        for doc_name in docs_by_name.keys():
                                            if f"select_doc_{doc_name}" in st.session_state:
                                                del st.session_state[f"select_doc_{doc_name}"]

                                        # 벡터 데이터 새로고침 또는 재시작
                                        if st.session_state.local_vectorstore is None:
                                            st.info("벡터DB가 초기화되었습니다. 이제 새로운 벡터DB를 생성할 수 있습니다.")
                                            st.rerun()
                                        else:
                                            st.info("목록을 새로고침하세요.")

                                except Exception as e:
                                    st.error(f"삭제 오류: {str(e)}")
                                    import traceback
                                    st.code(traceback.format_exc())

            # ========== 오른쪽: 원격 저장소 청크 목록 ==========
            with col_remote:
                st.write("### 🌐 원격 저장소")

                if not st.session_state.current_repo:
                    st.warning("먼저 저장소를 선택해주세요. (저장소 관리 탭)")
                else:
                    if st.button("🔄 원격 청크 목록 새로고침", key="refresh_remote_chunks"):
                        try:
                            repo_id = get_current_repo_id()
                            docs, msg = st.session_state.serve_client.get_documents(repo_id)

                            if docs is not None:
                                # 각 문서의 청크 조회
                                remote_chunks_by_doc = {}
                                for doc in docs:
                                    doc_id = doc.get('docId')
                                    doc_name = doc.get('fileName', 'Unknown')

                                    chunks, chunk_msg = st.session_state.serve_client.download_chunks_from_document(
                                        doc_id, repo_id
                                    )

                                    if chunks is not None:
                                        remote_chunks_by_doc[doc_id] = {
                                            'name': doc_name,
                                            'chunks': chunks
                                        }

                                st.session_state.remote_chunks_by_doc = remote_chunks_by_doc
                                total_chunks = sum(len(info['chunks']) for info in remote_chunks_by_doc.values())
                                st.success(f"✓ {len(remote_chunks_by_doc)}개 문서, {total_chunks}개 청크 로드")
                            else:
                                st.error(msg)

                        except Exception as e:
                            st.error(f"청크 조회 실패: {str(e)}")

                    # 원격 청크 표시
                    if 'remote_chunks_by_doc' in st.session_state:
                        remote_chunks = st.session_state.remote_chunks_by_doc

                        if len(remote_chunks) == 0:
                            st.info("원격 저장소에 청크가 없습니다.")
                        else:
                            total_chunks = sum(len(info['chunks']) for info in remote_chunks.values())
                            st.info(f"**문서 수:** {len(remote_chunks)}, **총 청크:** {total_chunks}")

                            # 선택 상태 초기화
                            if 'selected_remote_chunks' not in st.session_state:
                                st.session_state.selected_remote_chunks = {}  # {doc_id: set(chunk_indices)}

                            # 문서별 청크 표시 (스크롤 가능)
                            with st.container(height=300):
                                for doc_id, doc_info in remote_chunks.items():
                                    doc_name = doc_info['name']
                                    chunks = doc_info['chunks']

                                    # 문서 전체 선택 체크박스
                                    with st.expander(f"📄 {doc_name} ({len(chunks)}개 청크)", expanded=True):
                                        # 문서별 선택 상태 초기화
                                        if doc_id not in st.session_state.selected_remote_chunks:
                                            st.session_state.selected_remote_chunks[doc_id] = set()

                                        doc_all_selected_remote = len(st.session_state.selected_remote_chunks[doc_id]) == len(chunks)

                                        # 이전 상태 저장 (실제 클릭 감지용)
                                        prev_select_key = f"_prev_select_all_doc_{doc_id}"
                                        if prev_select_key not in st.session_state:
                                            st.session_state[prev_select_key] = doc_all_selected_remote

                                        select_all_doc = st.checkbox(
                                            f"전체 선택",
                                            value=doc_all_selected_remote,
                                            key=f"select_all_doc_{doc_id}"
                                        )

                                        # 실제로 체크박스를 클릭했는지 확인
                                        if select_all_doc != st.session_state[prev_select_key]:
                                            if select_all_doc:
                                                # 모든 청크 선택
                                                st.session_state.selected_remote_chunks[doc_id] = set(range(len(chunks)))
                                                # 모든 개별 체크박스 위젯 상태도 업데이트
                                                for i in range(len(chunks)):
                                                    st.session_state[f"remote_chunk_{doc_id}_{i}"] = True
                                            else:
                                                # 모든 청크 선택 해제
                                                st.session_state.selected_remote_chunks[doc_id] = set()
                                                # 모든 개별 체크박스 위젯 상태도 업데이트
                                                for i in range(len(chunks)):
                                                    st.session_state[f"remote_chunk_{doc_id}_{i}"] = False
                                            st.session_state[prev_select_key] = select_all_doc
                                        else:
                                            # 개별 체크박스 변경으로 인한 상태 업데이트
                                            st.session_state[prev_select_key] = doc_all_selected_remote

                                        # 청크 목록
                                        for i, chunk in enumerate(chunks):
                                            chunk_idx = chunk['chunkIndex']
                                            chunk_data = chunk.get('data', '')
                                            chunk_preview = chunk_data[:40] + "..." if len(chunk_data) > 40 else chunk_data
                                            chunk_version = chunk.get('version', 'N/A')

                                            # 청크 체크박스 상태 초기화
                                            if f"remote_chunk_{doc_id}_{i}" not in st.session_state:
                                                st.session_state[f"remote_chunk_{doc_id}_{i}"] = i in st.session_state.selected_remote_chunks[doc_id]

                                            is_selected = st.checkbox(
                                                f"Chunk {chunk_idx} (v{chunk_version}): {chunk_preview}",
                                                key=f"remote_chunk_{doc_id}_{i}"
                                            )

                                            if is_selected:
                                                st.session_state.selected_remote_chunks[doc_id].add(i)
                                            else:
                                                st.session_state.selected_remote_chunks[doc_id].discard(i)

                            # 선택된 청크 수 계산
                            total_selected = sum(len(indices) for indices in st.session_state.selected_remote_chunks.values())
                            st.write(f"**선택된 청크:** {total_selected}개")

                            # 다운로드/삭제 버튼
                            st.divider()
                            col_download, col_delete = st.columns(2)

                            with col_download:
                                st.write("**청크 다운로드**")
                                if st.button("⬇️ 선택한 청크 다운로드", type="primary", key="download_selected_remote"):
                                    if total_selected == 0:
                                        st.warning("다운로드할 청크를 선택해주세요.")
                                    else:
                                        try:
                                            vision = VisionEngine()
                                            downloaded_chunks = []

                                            for doc_id, selected_indices in st.session_state.selected_remote_chunks.items():
                                                if len(selected_indices) > 0:
                                                    doc_info = remote_chunks[doc_id]
                                                    for idx in selected_indices:
                                                        chunk = doc_info['chunks'][idx]
                                                        downloaded_chunks.append({
                                                            'doc_name': doc_info['name'],
                                                            'chunk_index': chunk['chunkIndex'],
                                                            'data': chunk['data'],
                                                            'version': chunk['version']
                                                        })

                                            # 다운로드된 청크를 로컬 벡터DB에 추가
                                            with st.spinner(f"{len(downloaded_chunks)}개 청크 다운로드 중..."):
                                                if not st.session_state.local_vectorstore:
                                                    st.warning("로컬 벡터DB가 없습니다. 먼저 벡터DB를 생성하세요.")
                                                else:
                                                    import json
                                                    for chunk in downloaded_chunks:
                                                        try:
                                                            chunk_content = json.loads(chunk['data'])
                                                            document_text = chunk_content.get('document', '')

                                                            if document_text:
                                                                vision.add_to_vector_store(
                                                                    st.session_state.local_vectorstore,
                                                                    document_text
                                                                )
                                                        except Exception as e:
                                                            st.warning(f"청크 {chunk['chunk_index']} 추가 실패: {str(e)}")

                                                    st.success(f"✓ {len(downloaded_chunks)}개 청크를 로컬 벡터DB에 추가했습니다!")
                                                    # 선택 초기화
                                                    st.session_state.selected_remote_chunks = {}
                                                    # 모든 원격 청크 체크박스 상태 초기화
                                                    for doc_id, doc_info in remote_chunks.items():
                                                        if f"select_all_doc_{doc_id}" in st.session_state:
                                                            del st.session_state[f"select_all_doc_{doc_id}"]
                                                        for i in range(len(doc_info['chunks'])):
                                                            if f"remote_chunk_{doc_id}_{i}" in st.session_state:
                                                                del st.session_state[f"remote_chunk_{doc_id}_{i}"]

                                        except Exception as e:
                                            st.error(f"다운로드 오류: {str(e)}")

                            with col_delete:
                                st.write("**청크 삭제**")
                                if st.button("🗑️ 선택한 청크 삭제", type="secondary", key="delete_selected_remote"):
                                    if total_selected == 0:
                                        st.warning("삭제할 청크를 선택해주세요.")
                                    else:
                                        try:
                                            deleted_count = 0
                                            failed_count = 0

                                            with st.spinner("청크 삭제 중..."):
                                                for doc_id, selected_indices in st.session_state.selected_remote_chunks.items():
                                                    if len(selected_indices) > 0:
                                                        doc_info = remote_chunks[doc_id]
                                                        for idx in selected_indices:
                                                            chunk = doc_info['chunks'][idx]
                                                            chunk_index = chunk['chunkIndex']

                                                            success, msg = st.session_state.serve_client.delete_chunk_from_document(
                                                                doc_id, chunk_index
                                                            )

                                                            if success:
                                                                deleted_count += 1
                                                            else:
                                                                failed_count += 1

                                            if deleted_count > 0:
                                                st.success(f"✓ {deleted_count}개 청크 삭제 완료!")
                                            if failed_count > 0:
                                                st.error(f"✗ {failed_count}개 청크 삭제 실패")

                                            # 선택 초기화
                                            st.session_state.selected_remote_chunks = {}
                                            # 모든 원격 청크 체크박스 상태 초기화
                                            for doc_id, doc_info in remote_chunks.items():
                                                if f"select_all_doc_{doc_id}" in st.session_state:
                                                    del st.session_state[f"select_all_doc_{doc_id}"]
                                                for i in range(len(doc_info['chunks'])):
                                                    if f"remote_chunk_{doc_id}_{i}" in st.session_state:
                                                        del st.session_state[f"remote_chunk_{doc_id}_{i}"]
                                            # 목록 새로고침 필요 알림
                                            st.info("목록을 새로고침하세요.")

                                        except Exception as e:
                                            st.error(f"삭제 오류: {str(e)}")

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

        # 이미지 선택 섹션
        st.write("### 이미지 선택")

        image_source = st.radio(
            "이미지 소스",
            ["기본 이미지", "파일 업로드"],
            horizontal=True
        )

        selected_image = None
        image = None
        img_bytes = None

        if image_source == "기본 이미지":
            # 가상 카메라 (이미지 폴더 로드)
            image_folder = "test_images"
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)
                st.warning(f"'{image_folder}' 폴더에 테스트 이미지를 넣어주세요.")

            image_files = [f for f in os.listdir(image_folder) if f.endswith(('jpg', 'png', 'jpeg'))]
            if image_files:
                selected_image = st.selectbox("이미지 선택", image_files)
                if selected_image:
                    img_path = os.path.join(image_folder, selected_image)
                    image = Image.open(img_path)
            else:
                st.info("이미지 파일이 없습니다.")

        else:  # 파일 업로드
            uploaded_file = st.file_uploader(
                "이미지를 드래그 앤 드롭하거나 클릭하여 선택하세요",
                type=['jpg', 'png', 'jpeg'],
                help="분석할 이미지를 업로드하세요"
            )

            if uploaded_file:
                image = Image.open(uploaded_file)
                selected_image = uploaded_file.name

        # 이미지가 선택되었으면 바이트로 변환
        if image:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format=image.format if hasattr(image, 'format') and image.format else 'PNG')
            img_bytes = img_byte_arr.getvalue()

        st.divider()

        col1, col2 = st.columns(2)

        # 왼쪽: 로봇의 시야 (카메라)
        with col1:
            st.write("### Robot View")
            if image:
                st.image(image, caption=f"Selected: {selected_image}", use_container_width=True)
            else:
                st.info("위에서 이미지를 선택해주세요.")

        # 오른쪽: AI의 판단 (RAG vs No-RAG)
        with col2:
            st.write("### AI Analysis")

            vision = VisionEngine()

            tab_a, tab_b = st.tabs(["일반 추론", "로컬 벡터DB RAG 추론"])

            # Tab A: 일반 추론 (보안 DB 없이 그냥 보기)
            with tab_a:
                if st.button("분석 (컨텍스트 없음)", type="primary"):
                    if img_bytes:
                        with st.spinner("Analyzing..."):
                            result = vision.analyze_image(img_bytes, "What is this object? Describe it.")
                            st.write(result)
                    else:
                        st.warning("위에서 이미지를 선택해주세요.")

            # Tab B: 로컬 벡터DB를 사용한 RAG 추론
            with tab_b:
                if not st.session_state.local_vectorstore:
                    st.warning("로컬 벡터DB가 없습니다. 먼저 '문서 관리' 탭에서 벡터DB를 생성하거나 다운로드하세요.")
                else:
                    st.info(f"✓ 로컬 벡터DB가 생성되어 있습니다.")

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
                        if not img_bytes:
                            st.warning("위에서 이미지를 선택해주세요.")
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
