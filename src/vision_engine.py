import ollama
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class VisionEngine:
    def __init__(self, model_name="llava", embedding_model="nomic-embed-text", use_multimodal=False):
        """
        Vision Engine with RAG capabilities

        Args:
            model_name: Ollama vision model (llava)
            embedding_model: Ollama embedding model (nomic-embed-text)
            use_multimodal: Use CLIP embeddings for multimodal RAG (images + text)
        """
        self.model_name = model_name
        self.embedding_model = embedding_model
        self.use_multimodal = use_multimodal
        self.embeddings = None  # Lazy loading
        self.clip_embeddings = None  # NEW: CLIP for multimodal

    def _get_embeddings(self):
        """Get or create embeddings instance (lazy loading)

        Returns:
            CLIP embeddings if use_multimodal=True, else nomic-embed-text
        """
        if self.use_multimodal:
            # Use CLIP for both text and images (512-dim embeddings)
            if self.clip_embeddings is None:
                from clip_embeddings import CLIPEmbeddings
                self.clip_embeddings = CLIPEmbeddings()
            return self.clip_embeddings
        else:
            # Use text-only embeddings (768-dim)
            if self.embeddings is None:
                import os
                ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                self.embeddings = OllamaEmbeddings(
                    model=self.embedding_model,
                    base_url=ollama_url
                )
            return self.embeddings

    def analyze_image(self, image_bytes, prompt="Describe this image in detail."):
        """
        [기존 메서드 - 변경 없음]
        이미지 바이트와 프롬프트를 받아 Ollama(LLaVA)에게 분석을 요청합니다.
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [image_bytes]
                    }
                ]
            )
            return response['message']['content']
        except Exception as e:
            return f"AI 분석 실패: {str(e)}"


    def analyze_with_vectorstore(
        self,
        image_bytes,
        vectorstore: Chroma,
        top_k=3,
        query="Describe technical specifications and safety information"
    ):
        """
        [RAG 기반] 기존 벡터 스토어를 활용하여 이미지를 분석합니다.

        Args:
            image_bytes: 이미지 바이트 데이터
            vectorstore: 기존 Chroma 벡터 스토어
            top_k: 검색할 관련 청크 수
            query: 검색 쿼리 (기본값: 기술 사양 및 안전 정보)

        Returns:
            str: AI 분석 결과
        """
        try:
            # 1. Semantic Search from existing vector store
            relevant_docs = vectorstore.similarity_search(query, k=top_k)

            # 2. Construct RAG Prompt
            retrieved_context = "\n\n".join([doc.page_content for doc in relevant_docs])

            rag_prompt = f"""You are a secure industrial AI assistant.
Analyze the provided image based strictly on the following secure context document.

[SECURE CONTEXT START]
{retrieved_context}
[SECURE CONTEXT END]

Question: What is this object based on the context above? Provide technical details if available.
"""

            # 3. Call LLM with image
            return self.analyze_image(image_bytes, rag_prompt)

        except Exception as e:
            return f"벡터스토어 RAG 분석 실패: {str(e)}"

    # ==================== Phase 2: Vector Store Management ====================

    def create_vector_store(
        self,
        text_content: str,
        collection_name: str = "serve_rag",
        persist_directory: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        document_name: Optional[str] = None
    ) -> Chroma:
        """
        Create and optionally persist a vector store from text content

        Args:
            text_content: 전체 텍스트
            collection_name: ChromaDB 컬렉션 이름
            persist_directory: 저장 디렉토리 (None이면 in-memory)
            chunk_size: 청크 크기
            chunk_overlap: 청크 오버랩
            document_name: 문서 이름 (메타데이터에 저장)

        Returns:
            Chroma: Vector store 인스턴스
        """
        import os
        import shutil
        import time
        import gc
        import chromadb
        from chromadb.config import Settings

        # Convert to absolute path to avoid permission issues
        if persist_directory:
            persist_directory = os.path.abspath(persist_directory)

        # persist_directory가 지정된 경우, 기존 디렉토리를 완전히 삭제
        if persist_directory and os.path.exists(persist_directory):
            print(f"기존 벡터스토어 디렉토리 삭제 중: {persist_directory}")

            # 1. ChromaDB 클라이언트를 사용하여 컬렉션 삭제 및 리셋
            try:
                temp_settings = Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True
                )
                temp_client = chromadb.PersistentClient(path=persist_directory, settings=temp_settings)

                # 모든 컬렉션 삭제 시도
                try:
                    collections = temp_client.list_collections()
                    for col in collections:
                        try:
                            temp_client.delete_collection(col.name)
                            print(f"컬렉션 '{col.name}' 삭제 완료")
                        except Exception:
                            pass
                except Exception:
                    pass

                # ChromaDB 리셋 (모든 데이터 삭제)
                try:
                    temp_client.reset()
                    print("ChromaDB 리셋 완료")
                except Exception as e:
                    print(f"ChromaDB 리셋 중 오류 (무시): {str(e)}")

                # 클라이언트 명시적 정리
                del temp_client
            except Exception as e:
                print(f"ChromaDB 클라이언트 정리 중 오류: {str(e)}")

            # 2. 강력한 가비지 컬렉션
            gc.collect()
            time.sleep(0.5)
            gc.collect()
            time.sleep(0.3)

            # 3. SQLite WAL 파일도 함께 삭제 시도
            try:
                sqlite_files = ['chroma.sqlite3', 'chroma.sqlite3-wal', 'chroma.sqlite3-shm']
                for sqlite_file in sqlite_files:
                    sqlite_path = os.path.join(persist_directory, sqlite_file)
                    if os.path.exists(sqlite_path):
                        try:
                            os.chmod(sqlite_path, 0o777)
                            os.remove(sqlite_path)
                            print(f"SQLite 파일 삭제: {sqlite_file}")
                        except Exception as e:
                            print(f"{sqlite_file} 삭제 실패 (무시): {str(e)}")
            except Exception:
                pass

            # 4. 디렉토리 삭제 (재시도)
            max_retries = 5
            deleted = False
            for retry in range(max_retries):
                try:
                    time.sleep(0.5)
                    shutil.rmtree(persist_directory)
                    print("벡터스토어 디렉토리 삭제 완료")
                    deleted = True
                    break
                except (PermissionError, OSError) as e:
                    if retry < max_retries - 1:
                        print(f"디렉토리 삭제 재시도 중... ({retry + 1}/{max_retries})")
                        gc.collect()
                        time.sleep(1.0)
                    else:
                        print(f"디렉토리 삭제 실패: {str(e)}")
                        # 마지막 시도: 개별 파일 삭제
                        try:
                            print("개별 파일 삭제 시도...")
                            for root, dirs, files in os.walk(persist_directory, topdown=False):
                                for name in files:
                                    file_path = os.path.join(root, name)
                                    try:
                                        os.chmod(file_path, 0o777)
                                        os.remove(file_path)
                                    except Exception:
                                        pass
                                for name in dirs:
                                    dir_path = os.path.join(root, name)
                                    try:
                                        os.rmdir(dir_path)
                                    except Exception:
                                        pass
                            os.rmdir(persist_directory)
                            print("개별 파일 삭제 완료")
                            deleted = True
                        except Exception as cleanup_err:
                            print(f"개별 파일 삭제도 실패: {str(cleanup_err)}")

            # 5. 삭제 실패 시 명확한 에러 발생
            if not deleted and os.path.exists(persist_directory):
                raise Exception(
                    f"벡터스토어 디렉토리를 삭제할 수 없습니다.\n"
                    f"다음 중 하나를 시도하세요:\n"
                    f"1. Streamlit 앱을 완전히 종료하고 다시 시작\n"
                    f"2. 터미널에서 수동으로 삭제: rm -rf '{persist_directory}'\n"
                    f"3. 다른 프로세스(Jupyter, Python 등)가 해당 디렉토리를 사용 중인지 확인"
                )

            # 6. 파일 시스템 정리 대기
            time.sleep(0.5)
            gc.collect()

        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text_content)

        # Create documents with metadata
        metadata = {"document_name": document_name} if document_name else {}
        documents = [Document(page_content=chunk, metadata=metadata.copy()) for chunk in chunks]

        # Create vector store with explicit client and settings
        if persist_directory:
            # Ensure directory exists with proper permissions
            os.makedirs(persist_directory, mode=0o777, exist_ok=True)

            # Set directory permissions explicitly
            os.chmod(persist_directory, 0o777)

            # Create ChromaDB client with proper settings
            settings = Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True
            )
            client = chromadb.PersistentClient(path=persist_directory, settings=settings)
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self._get_embeddings(),
                collection_name=collection_name,
                client=client,
                persist_directory=persist_directory
            )
        else:
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self._get_embeddings(),
                collection_name=collection_name,
                persist_directory=persist_directory
            )

        return vectorstore

    def load_vector_store(
        self,
        collection_name: str = "serve_rag",
        persist_directory: str = "./local_vectorstore"
    ) -> Optional[Chroma]:
        """
        Load existing vector store from disk

        Args:
            collection_name: ChromaDB 컬렉션 이름
            persist_directory: 저장 디렉토리

        Returns:
            Chroma: Vector store 인스턴스 또는 None (존재하지 않는 경우)
        """
        try:
            import os
            import shutil
            import chromadb
            from chromadb.config import Settings

            # Convert to absolute path
            persist_directory = os.path.abspath(persist_directory)

            if not os.path.exists(persist_directory):
                return None

            # 명시적으로 클라이언트 생성하여 로드
            try:
                settings = Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True
                )
                client = chromadb.PersistentClient(path=persist_directory, settings=settings)
                vectorstore = Chroma(
                    collection_name=collection_name,
                    embedding_function=self._get_embeddings(),
                    client=client,
                    persist_directory=persist_directory
                )

                # 벡터스토어가 비어있는지 확인
                collection = vectorstore._collection
                if collection.count() == 0:
                    # 비어있는 벡터스토어는 None으로 처리하여 UI에서 재생성 가능하도록 함
                    print("벡터스토어가 비어있습니다. 새로 생성해주세요.")
                    return None

                return vectorstore
            except Exception as load_error:
                # 로드 실패 시 클라이언트 없이 재시도
                print(f"클라이언트를 사용한 로드 실패, 기본 방식으로 재시도: {str(load_error)}")
                vectorstore = Chroma(
                    collection_name=collection_name,
                    embedding_function=self._get_embeddings(),
                    persist_directory=persist_directory
                )

                # 벡터스토어가 비어있는지 확인
                collection = vectorstore._collection
                if collection.count() == 0:
                    print("벡터스토어가 비어있습니다. 새로 생성해주세요.")
                    return None

                return vectorstore

        except Exception as e:
            error_msg = str(e).lower()
            # 읽기 전용 오류 또는 데이터베이스 오류 감지
            if "readonly" in error_msg or "database" in error_msg or "attempt to write" in error_msg:
                print(f"손상된 벡터스토어 감지: {str(e)}")
                print(f"벡터스토어 디렉토리 삭제 중: {persist_directory}")
                try:
                    import shutil
                    import time
                    import gc

                    if os.path.exists(persist_directory):
                        # 가비지 컬렉션
                        gc.collect()
                        time.sleep(0.3)

                        # 디렉토리 삭제 재시도
                        max_retries = 3
                        for retry in range(max_retries):
                            try:
                                shutil.rmtree(persist_directory)
                                print("손상된 벡터스토어가 삭제되었습니다. 새로 생성해주세요.")
                                break
                            except Exception as retry_error:
                                if retry < max_retries - 1:
                                    print(f"삭제 재시도 중... ({retry + 1}/{max_retries})")
                                    gc.collect()
                                    time.sleep(0.5)
                                else:
                                    print(f"디렉토리 삭제 실패: {str(retry_error)}")
                                    print(f"앱 재시작 후 다시 시도하거나 수동으로 '{persist_directory}' 디렉토리를 삭제해주세요.")

                except Exception as cleanup_error:
                    print(f"정리 중 오류: {str(cleanup_error)}")
            else:
                print(f"벡터스토어 로드 실패: {str(e)}")
            return None

    def extract_vectors(self, vectorstore: Chroma) -> Dict[str, Any]:
        """
        Extract vectors from ChromaDB collection for encryption/sharing
        For image chunks: reads image file and converts to base64

        Args:
            vectorstore: ChromaDB vector store 인스턴스

        Returns:
            dict: {'ids': [...], 'embeddings': [...], 'documents': [...], 'metadatas': [...]}
        """
        import base64
        import os

        collection = vectorstore._collection
        result = collection.get(include=["embeddings", "documents", "metadatas"])

        # Process metadatas to embed image data for remote upload
        if result.get('metadatas'):
            for metadata in result['metadatas']:
                if metadata.get('modality') == 'image':
                    image_path = metadata.get('image_path')
                    if image_path and os.path.exists(image_path):
                        # Read and encode image as base64
                        with open(image_path, 'rb') as f:
                            image_bytes = f.read()
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            metadata['image_base64'] = image_base64
                            # Keep image_path for reference

        return result

    def add_to_vector_store(
        self,
        vectorstore: Chroma,
        text_content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        document_name: Optional[str] = None
    ) -> Chroma:
        """
        기존 벡터 스토어에 새 텍스트를 추가합니다.

        Args:
            vectorstore: 기존 Chroma 벡터 스토어
            text_content: 추가할 텍스트
            chunk_size: 청크 크기
            chunk_overlap: 청크 오버랩
            document_name: 문서 이름 (메타데이터에 저장)

        Returns:
            Chroma: 업데이트된 vector store (동일한 인스턴스)
        """
        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text_content)

        # Create documents with metadata
        metadata = {"document_name": document_name} if document_name else {}
        documents = [Document(page_content=chunk, metadata=metadata.copy()) for chunk in chunks]

        # Add to existing vector store
        vectorstore.add_documents(documents)

        return vectorstore

    def create_vector_store_with_image(
        self,
        image,  # PIL.Image object
        caption: str,
        collection_name: str = "serve_rag",
        persist_directory: Optional[str] = None,
        document_name: str = "Images",
        image_directory: str = "./rag_images"
    ) -> Chroma:
        """
        Create a new vectorstore starting with an image + caption (multimodal mode)

        Args:
            image: PIL.Image object
            caption: Image description
            collection_name: ChromaDB collection name
            persist_directory: Storage directory (None for in-memory)
            document_name: Document name for metadata
            image_directory: Directory to save images

        Returns:
            Chroma vectorstore with the first image added
        """
        import os
        import shutil
        import time
        import gc
        import chromadb
        from chromadb.config import Settings

        if not self.use_multimodal:
            raise ValueError("Must use multimodal mode (VisionEngine(use_multimodal=True)) to create vectorstore with images")

        # Convert to absolute path to avoid permission issues
        if persist_directory:
            persist_directory = os.path.abspath(persist_directory)

        # Clean up existing directory if it exists (same as create_vector_store)
        if persist_directory and os.path.exists(persist_directory):
            print(f"기존 벡터스토어 디렉토리 삭제 중: {persist_directory}")

            # 1. ChromaDB 클라이언트를 사용하여 컬렉션 삭제 및 리셋
            try:
                temp_settings = Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True
                )
                temp_client = chromadb.PersistentClient(path=persist_directory, settings=temp_settings)

                # 모든 컬렉션 삭제 시도
                try:
                    collections = temp_client.list_collections()
                    for col in collections:
                        try:
                            temp_client.delete_collection(col.name)
                            print(f"컬렉션 '{col.name}' 삭제 완료")
                        except Exception:
                            pass
                except Exception:
                    pass

                # ChromaDB 리셋 (모든 데이터 삭제)
                try:
                    temp_client.reset()
                    print("ChromaDB 리셋 완료")
                except Exception as e:
                    print(f"ChromaDB 리셋 중 오류 (무시): {str(e)}")

                # 클라이언트 명시적 정리
                del temp_client
            except Exception as e:
                print(f"ChromaDB 클라이언트 정리 중 오류: {str(e)}")

            # 2. 강력한 가비지 컬렉션
            gc.collect()
            time.sleep(0.5)
            gc.collect()
            time.sleep(0.3)

            # 3. SQLite WAL 파일도 함께 삭제 시도
            try:
                sqlite_files = ['chroma.sqlite3', 'chroma.sqlite3-wal', 'chroma.sqlite3-shm']
                for sqlite_file in sqlite_files:
                    sqlite_path = os.path.join(persist_directory, sqlite_file)
                    if os.path.exists(sqlite_path):
                        try:
                            os.chmod(sqlite_path, 0o777)
                            os.remove(sqlite_path)
                            print(f"SQLite 파일 삭제: {sqlite_file}")
                        except Exception as e:
                            print(f"{sqlite_file} 삭제 실패 (무시): {str(e)}")
            except Exception:
                pass

            # 4. 디렉토리 삭제 (재시도)
            max_retries = 5
            deleted = False
            for retry in range(max_retries):
                try:
                    time.sleep(0.5)
                    shutil.rmtree(persist_directory)
                    print("벡터스토어 디렉토리 삭제 완료")
                    deleted = True
                    break
                except (PermissionError, OSError) as e:
                    if retry < max_retries - 1:
                        print(f"디렉토리 삭제 재시도 중... ({retry + 1}/{max_retries})")
                        gc.collect()
                        time.sleep(1.0)
                    else:
                        print(f"디렉토리 삭제 실패: {str(e)}")
                        # 마지막 시도: 개별 파일 삭제
                        try:
                            print("개별 파일 삭제 시도...")
                            for root, dirs, files in os.walk(persist_directory, topdown=False):
                                for name in files:
                                    file_path = os.path.join(root, name)
                                    try:
                                        os.chmod(file_path, 0o777)
                                        os.remove(file_path)
                                    except Exception:
                                        pass
                                for name in dirs:
                                    dir_path = os.path.join(root, name)
                                    try:
                                        os.rmdir(dir_path)
                                    except Exception:
                                        pass
                            os.rmdir(persist_directory)
                            print("개별 파일 삭제 완료")
                            deleted = True
                        except Exception as cleanup_err:
                            print(f"개별 파일 삭제도 실패: {str(cleanup_err)}")

            # 5. 삭제 실패 시 명확한 에러 발생
            if not deleted and os.path.exists(persist_directory):
                raise Exception(
                    f"벡터스토어 디렉토리를 삭제할 수 없습니다.\n"
                    f"다음 중 하나를 시도하세요:\n"
                    f"1. Streamlit 앱을 완전히 종료하고 다시 시작\n"
                    f"2. 터미널에서 수동으로 삭제: rm -rf '{persist_directory}'\n"
                    f"3. 다른 프로세스(Jupyter, Python 등)가 해당 디렉토리를 사용 중인지 확인"
                )

            # 6. 파일 시스템 정리 대기
            time.sleep(0.5)
            gc.collect()

        # Create vectorstore with explicit settings
        if persist_directory:
            # Ensure directory exists with proper permissions
            os.makedirs(persist_directory, mode=0o777, exist_ok=True)

            # Set directory permissions explicitly
            os.chmod(persist_directory, 0o777)

            # Create ChromaDB client with proper settings
            settings = Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True
            )
            client = chromadb.PersistentClient(path=persist_directory, settings=settings)
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=self._get_embeddings(),
                client=client,
                persist_directory=persist_directory
            )
        else:
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=self._get_embeddings(),
                persist_directory=persist_directory
            )

        # Add the first image
        self.add_image_to_vector_store(
            vectorstore,
            image,
            caption,
            document_name=document_name,
            image_directory=image_directory
        )

        return vectorstore

    def add_image_to_vector_store(
        self,
        vectorstore: Chroma,
        image,  # PIL.Image or file-like object
        caption: str,
        document_name: str = "Images",
        image_directory: str = "./rag_images"
    ) -> Chroma:
        """
        Add image + caption to multimodal vectorstore using CLIP embeddings

        Args:
            vectorstore: Existing Chroma vectorstore (must use CLIP embeddings)
            image: PIL.Image object or file-like object
            caption: User-provided text description of image
            document_name: Document name for grouping
            image_directory: Directory to save images

        Returns:
            Updated vectorstore
        """
        from PIL import Image
        import image_utils
        import uuid
        import os

        # Convert to PIL Image if needed
        if not isinstance(image, Image.Image):
            image = Image.open(image)

        # Save image to disk
        image_path = image_utils.save_image(image, image_directory)

        # Create metadata
        metadata = {
            "modality": "image",
            "image_path": image_path,
            "caption": caption,
            "document_name": document_name,
            "image_filename": os.path.basename(image_path)
        }

        # Generate CLIP embedding from image
        if not self.use_multimodal:
            raise ValueError("Must use multimodal mode (VisionEngine(use_multimodal=True)) to add images")

        clip_emb = self._get_embeddings()
        image_embedding = clip_emb.embed_image(image)

        # Add to vectorstore with manual embedding
        # Note: ChromaDB allows adding documents with pre-computed embeddings
        collection = vectorstore._collection
        collection.add(
            ids=[f"img_{uuid.uuid4()}"],
            embeddings=[image_embedding],
            documents=[caption],
            metadatas=[metadata]
        )

        return vectorstore

    def similarity_search_by_image(
        self,
        input_image,  # bytes or PIL.Image
        vectorstore: Chroma,
        k: int = 3,
        modality_filter: str = "image"
    ) -> List[Document]:
        """
        Search for similar images using CLIP embedding of input image

        Args:
            input_image: Input image as bytes or PIL.Image
            vectorstore: Chroma vectorstore with images
            k: Number of results to return
            modality_filter: Filter by modality ("image", "text", or "all")

        Returns:
            List of Document objects with image metadata
        """
        from PIL import Image
        import io

        # Convert bytes to PIL Image if needed
        if isinstance(input_image, bytes):
            input_image = Image.open(io.BytesIO(input_image))

        # Generate CLIP embedding from input image
        clip_emb = self._get_embeddings()
        query_embedding = clip_emb.embed_image(input_image)

        # Query ChromaDB with embedding vector
        collection = vectorstore._collection

        # Build metadata filter
        where_filter = None
        if modality_filter != "all":
            where_filter = {"modality": modality_filter}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter
        )

        # Convert to Document objects
        documents = []
        for i in range(len(results['ids'][0])):
            doc = Document(
                page_content=results['documents'][0][i],
                metadata=results['metadatas'][0][i]
            )
            documents.append(doc)

        return documents

    def analyze_with_multimodal_rag(
        self,
        image_bytes,
        vectorstore: Chroma,
        top_k_images: int = 3,
        top_k_text: int = 2,
        text_query: str = None,
        use_image_search: bool = True
    ) -> str:
        """
        Multimodal RAG: retrieve similar images + text chunks, use captions in prompt

        Args:
            image_bytes: Input image as bytes
            vectorstore: Chroma vectorstore with images and text
            top_k_images: Number of similar images to retrieve
            top_k_text: Number of text chunks to retrieve
            text_query: Optional text query for retrieving text chunks
            use_image_search: Whether to use image similarity search

        Returns:
            AI analysis result
        """
        retrieved_captions = []
        retrieved_text_context = ""

        # 1. Retrieve similar images by CLIP embedding
        if use_image_search:
            similar_images = self.similarity_search_by_image(
                image_bytes,
                vectorstore,
                k=top_k_images,
                modality_filter="image"
            )
            retrieved_captions = [doc.metadata.get('caption', '') for doc in similar_images]

        # 2. Optionally retrieve text chunks
        if text_query and top_k_text > 0:
            text_docs = vectorstore.similarity_search(
                text_query,
                k=top_k_text,
                filter={"modality": "text"}
            )
            retrieved_text_context = "\n\n".join([doc.page_content for doc in text_docs])

        # 3. Construct multimodal RAG prompt
        captions_section = ""
        if retrieved_captions:
            captions_section = "[SIMILAR IMAGES IN DATABASE]\n" + \
                              "\n".join([f"- {cap}" for cap in retrieved_captions if cap])

        text_section = ""
        if retrieved_text_context:
            text_section = f"\n\n[TECHNICAL DOCUMENTATION]\n{retrieved_text_context}"

        rag_prompt = f"""You are a secure industrial AI assistant with multimodal knowledge.
Analyze the provided image based strictly on the following retrieved information.

{captions_section}{text_section}

Question: What is this object? Provide technical details based on the above context.
If the image doesn't match any retrieved information, say "No matching equipment found in database."
"""

        # 4. Call LLaVA with multimodal RAG prompt
        return self.analyze_image(image_bytes, rag_prompt)

    def cleanup_vector_store(
        self,
        vectorstore: Chroma,
        persist_directory: str = "./local_vectorstore"
    ) -> None:
        """
        ChromaDB 벡터 스토어를 안전하게 정리합니다.

        Args:
            vectorstore: 정리할 Chroma 벡터 스토어
            persist_directory: 저장 디렉토리
        """
        try:
            import gc
            import time
            import shutil
            import os

            # ChromaDB 클라이언트와 컬렉션 정리
            if vectorstore is not None:
                # 컬렉션 이름 가져오기
                collection_name = vectorstore._collection.name if hasattr(vectorstore, '_collection') else None

                # 클라이언트를 통해 컬렉션 삭제
                if hasattr(vectorstore, '_client') and collection_name:
                    try:
                        vectorstore._client.delete_collection(collection_name)
                    except Exception as e:
                        print(f"컬렉션 삭제 중 오류 (무시 가능): {str(e)}")

                # ChromaDB 클라이언트 정리 시도
                if hasattr(vectorstore, '_client'):
                    try:
                        # 클라이언트의 시스템 캐시 정리
                        if hasattr(vectorstore._client, 'clear_system_cache'):
                            vectorstore._client.clear_system_cache()
                    except Exception as e:
                        print(f"클라이언트 캐시 정리 중 오류 (무시 가능): {str(e)}")

                # 명시적으로 객체 삭제
                del vectorstore

            # 가비지 컬렉션 여러 번 강제 실행
            gc.collect()
            time.sleep(0.3)
            gc.collect()

            # 디렉토리 삭제 (재시도 로직 포함)
            if os.path.exists(persist_directory):
                max_retries = 5
                for retry in range(max_retries):
                    try:
                        # 추가 대기
                        time.sleep(0.3)
                        shutil.rmtree(persist_directory)
                        print(f"벡터스토어 디렉토리 삭제 완료: {persist_directory}")
                        break
                    except PermissionError as pe:
                        if retry < max_retries - 1:
                            print(f"디렉토리 삭제 재시도 중... ({retry + 1}/{max_retries})")
                            gc.collect()
                            time.sleep(0.5)
                        else:
                            print(f"디렉토리 삭제 실패: {str(pe)}")
                            raise
                    except Exception as e:
                        if retry < max_retries - 1:
                            print(f"디렉토리 삭제 재시도 중... ({retry + 1}/{max_retries}): {str(e)}")
                            gc.collect()
                            time.sleep(0.5)
                        else:
                            raise

        except Exception as e:
            print(f"벡터스토어 정리 중 오류: {str(e)}")
