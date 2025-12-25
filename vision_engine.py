import ollama
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class VisionEngine:
    def __init__(self, model_name="llava", embedding_model="nomic-embed-text"):
        """
        Vision Engine with RAG capabilities

        Args:
            model_name: Ollama vision model (llava)
            embedding_model: Ollama embedding model (nomic-embed-text)
        """
        self.model_name = model_name
        self.embedding_model = embedding_model
        self.embeddings = None  # Lazy loading

    def _get_embeddings(self):
        """Get or create embeddings instance (lazy loading)"""
        if self.embeddings is None:
            self.embeddings = OllamaEmbeddings(
                model=self.embedding_model,
                base_url="http://localhost:11434"
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

        # persist_directory가 지정된 경우, 기존 디렉토리를 완전히 삭제
        if persist_directory and os.path.exists(persist_directory):
            try:
                print(f"기존 벡터스토어 디렉토리 삭제 중: {persist_directory}")

                # 1. 기존 ChromaDB 클라이언트가 있다면 명시적으로 정리
                try:
                    # 임시로 클라이언트를 생성하여 컬렉션 삭제 시도
                    temp_client = chromadb.PersistentClient(path=persist_directory)
                    try:
                        temp_client.delete_collection(collection_name)
                        print(f"기존 컬렉션 '{collection_name}' 삭제 완료")
                    except Exception:
                        pass  # 컬렉션이 없을 수 있음
                    # 클라이언트 정리
                    del temp_client
                except Exception as e:
                    print(f"ChromaDB 클라이언트 정리 중 오류 (무시): {str(e)}")

                # 2. 가비지 컬렉션으로 모든 파일 핸들 정리
                gc.collect()
                time.sleep(0.5)
                gc.collect()

                # 3. 디렉토리 삭제 (여러 번 재시도)
                max_retries = 5
                for retry in range(max_retries):
                    try:
                        # 추가 대기
                        time.sleep(0.3)

                        # 디렉토리 삭제
                        shutil.rmtree(persist_directory)
                        print("벡터스토어 디렉토리 삭제 완료")
                        break
                    except (PermissionError, OSError) as e:
                        if retry < max_retries - 1:
                            print(f"디렉토리 삭제 재시도 중... ({retry + 1}/{max_retries})")
                            gc.collect()
                            time.sleep(0.7)
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
                            except Exception as cleanup_err:
                                print(f"개별 파일 삭제도 실패: {str(cleanup_err)}")
                                raise Exception(f"벡터스토어 디렉토리를 삭제할 수 없습니다. 수동으로 '{persist_directory}' 디렉토리를 삭제하거나, 실행 중인 다른 프로세스를 종료해주세요.")

                # 4. 디렉토리가 완전히 삭제되었는지 확인
                if os.path.exists(persist_directory):
                    raise Exception(f"디렉토리 삭제 확인 실패: {persist_directory}")

                # 5. 파일 시스템이 정리될 시간을 충분히 줌
                time.sleep(0.5)
                gc.collect()

            except Exception as e:
                error_msg = str(e)
                if "삭제할 수 없습니다" in error_msg or "삭제 확인 실패" in error_msg:
                    raise
                print(f"디렉토리 삭제 중 오류 (계속 진행): {error_msg}")

        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text_content)

        # Create documents with metadata
        metadata = {"document_name": document_name} if document_name else {}
        documents = [Document(page_content=chunk, metadata=metadata.copy()) for chunk in chunks]

        # Create vector store with explicit client
        if persist_directory:
            # 명시적으로 새 클라이언트 생성
            client = chromadb.PersistentClient(path=persist_directory)
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

            if not os.path.exists(persist_directory):
                return None

            # 명시적으로 클라이언트 생성하여 로드
            try:
                client = chromadb.PersistentClient(path=persist_directory)
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

        Args:
            vectorstore: ChromaDB vector store 인스턴스

        Returns:
            dict: {'ids': [...], 'embeddings': [...], 'documents': [...], 'metadatas': [...]}
        """
        collection = vectorstore._collection
        result = collection.get(include=["embeddings", "documents", "metadatas"])
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
