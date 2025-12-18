import streamlit as st
import os
from PIL import Image
import io
from vision_engine import VisionEngine
from serve_connector import ServeConnector

# 페이지 설정
st.set_page_config(page_title="SeRVe: Secure Edge AI", layout="wide")
st.title("SeRVe: Zero-Trust Physical AI Demo")

# 사이드바: 설정
with st.sidebar:
    st.header("System Status")
    
    # SeRVe 연결 상태
    if 'serve_conn' not in st.session_state:
        st.session_state.serve_conn = ServeConnector()
        st.session_state.is_connected = False
        st.session_state.last_doc_id = 1
    
    if st.button("Connect to SeRVe (Handshake)"):
        success, msg = st.session_state.serve_conn.perform_handshake()
        st.session_state.is_connected = success
        if success:
            st.success(msg)
        else:
            st.error(msg)
            
    st.divider()

    # 데이터 업로드
    st.subheader("Upload New Data")
    upload_text = st.text_area("Secure Context Input", "This is a hydraulic valve (Type-K). Pressure limit: 500bar.")
    
    if st.button("Encrypt & Upload"):
        if not st.session_state.is_connected:
            st.error("먼저 연결(Handshake)해주세요!")
        else:
            doc_id, msg = st.session_state.serve_conn.upload_secure_document(upload_text)
            if doc_id:
                st.success(f"{msg} (Doc ID: {doc_id})")
                st.session_state.last_doc_id = int(doc_id)
            else:
                st.error(msg)

    st.divider()
    
    # 가상 카메라 (이미지 폴더 로드)
    image_folder = "test_images"
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
        st.warning(f"'{image_folder}' 폴더에 테스트 이미지를 넣어주세요.")
        
    image_files = [f for f in os.listdir(image_folder) if f.endswith(('jpg', 'png', 'jpeg'))]
    selected_image = st.selectbox("Virtual Camera (Select Image)", image_files)

# 메인 화면
col1, col2 = st.columns(2)

# 왼쪽: 로봇의 시야 (카메라)
with col1:
    st.subheader("Robot View")
    if selected_image:
        img_path = os.path.join(image_folder, selected_image)
        image = Image.open(img_path)
        
        # 이미지를 바이트로 변환 (Ollama 전송용)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=image.format)
        img_bytes = img_byte_arr.getvalue()
        
        st.image(image, caption="Captured Image", width='stretch')
    else:
        st.info("이미지를 선택해주세요.")

# 오른쪽: AI의 판단 (RAG vs No-RAG)
with col2:
    st.subheader("Edge AI Analysis")
    
    vision = VisionEngine()
    
    tab1, tab2 = st.tabs(["Normal Inference", "Secure RAG Inference"])
    
    # Tab 1: 일반 추론 (보안 DB 없이 그냥 보기)
    with tab1:
        if st.button("Analyze (No Context)", type="primary"):
            if selected_image:
                with st.spinner("Analyzing..."):
                    result = vision.analyze_image(img_bytes, "What is this object? Describe it.")
                    st.write(result)
            else:
                st.warning("이미지가 없습니다.")

    # Tab 2: 보안 RAG 추론 (SeRVe 연동)
    with tab2:
        doc_id = st.number_input("Document ID (SeRVe)", min_value=1, value=st.session_state.last_doc_id)
        
        if st.button("Analyze (With SeRVe)", type="primary"):
            if not st.session_state.get('is_connected'):
                st.error("먼저 사이드바에서 SeRVe와 핸드셰이크를 수행해주세요!")
            elif selected_image:
                with st.spinner("Fetching Secure Data & Decrypting..."):
                    # 1. SeRVe에서 보안 문서 가져오기
                    context_text, msg = st.session_state.serve_conn.get_secure_document(doc_id)
                    
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