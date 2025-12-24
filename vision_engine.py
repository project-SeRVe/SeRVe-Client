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

        # persist_directory가 지정된 경우, 기존 디렉토리를 완전히 삭제
        if persist_directory and os.path.exists(persist_directory):
            try:
                print(f"기존 벡터스토어 디렉토리 삭제 중: {persist_directory}")
                shutil.rmtree(persist_directory)
                # 파일 시스템이 디렉토리를 완전히 정리할 시간을 줌
                time.sleep(0.2)
                gc.collect()
            except Exception as e:
                print(f"디렉토리 삭제 중 오류 (계속 진행): {str(e)}")

        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text_content)

        # Create documents with metadata
        metadata = {"document_name": document_name} if document_name else {}
        documents = [Document(page_content=chunk, metadata=metadata.copy()) for chunk in chunks]

        # Create vector store
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

            if not os.path.exists(persist_directory):
                return None

            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=self._get_embeddings(),
                persist_directory=persist_directory
            )

            # 벡터스토어가 비어있는지 확인
            collection = vectorstore._collection
            if collection.count() == 0:
                # 비어있는 벡터스토어는 None으로 처리하여 UI에서 재생성 가능하도록 함
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
                    if os.path.exists(persist_directory):
                        shutil.rmtree(persist_directory)
                    print("손상된 벡터스토어가 삭제되었습니다. 새로 생성해주세요.")
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

                # 명시적으로 객체 삭제
                del vectorstore

            # 가비지 컬렉션 강제 실행
            gc.collect()

            # 디렉토리 삭제
            import shutil
            import os
            if os.path.exists(persist_directory):
                # SQLite WAL 파일도 함께 삭제되도록 조금 대기
                import time
                time.sleep(0.1)
                shutil.rmtree(persist_directory)

        except Exception as e:
            print(f"벡터스토어 정리 중 오류: {str(e)}")
