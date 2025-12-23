import ollama
from pathlib import Path
from typing import Optional, List
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

    def analyze_with_context(
        self,
        image_bytes,
        context_text,
        top_k=3,
        chunk_size=500,
        chunk_overlap=50
    ):
        """
        [RAG 기반] 복호화된 보안 문서(Context)를 참고하여 이미지를 분석합니다.

        Args:
            image_bytes: 이미지 바이트 데이터
            context_text: 컨텍스트 텍스트 (전체 문서)
            top_k: 검색할 관련 청크 수
            chunk_size: 청크 크기
            chunk_overlap: 청크 오버랩

        Returns:
            str: AI 분석 결과
        """
        try:
            # 1. Text Splitting
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = text_splitter.split_text(context_text)

            # 2. Create Documents
            documents = [Document(page_content=chunk) for chunk in chunks]

            # 3. Create Vector Store (in-memory)
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self._get_embeddings(),
                collection_name="temp_rag_context"
            )

            # 4. Semantic Search
            query = "Describe technical specifications and safety information"
            relevant_docs = vectorstore.similarity_search(query, k=top_k)

            # 5. Construct RAG Prompt
            retrieved_context = "\n\n".join([doc.page_content for doc in relevant_docs])

            rag_prompt = f"""You are a secure industrial AI assistant.
Analyze the provided image based strictly on the following secure context document.

[SECURE CONTEXT START]
{retrieved_context}
[SECURE CONTEXT END]

Question: What is this object based on the context above? Provide technical details if available.
"""

            # 6. Call LLM with image
            return self.analyze_image(image_bytes, rag_prompt)

        except Exception as e:
            return f"RAG 분석 실패: {str(e)}"

    # ==================== Phase 2: Vector Store Management ====================

    def create_vector_store(
        self,
        text_content: str,
        collection_name: str = "serve_rag",
        persist_directory: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> Chroma:
        """
        Create and optionally persist a vector store from text content

        Args:
            text_content: 전체 텍스트
            collection_name: ChromaDB 컬렉션 이름
            persist_directory: 저장 디렉토리 (None이면 in-memory)
            chunk_size: 청크 크기
            chunk_overlap: 청크 오버랩

        Returns:
            Chroma: Vector store 인스턴스
        """
        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(text_content)
        documents = [Document(page_content=chunk) for chunk in chunks]

        # Create vector store
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self._get_embeddings(),
            collection_name=collection_name,
            persist_directory=persist_directory
        )

        return vectorstore

    def extract_vectors(self, vectorstore: Chroma) -> dict:
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

    def reconstruct_vector_store(
        self,
        vector_data: dict,
        collection_name: str = "serve_rag_shared",
        persist_directory: Optional[str] = None
    ) -> Chroma:
        """
        Reconstruct vector store from extracted vector data

        Args:
            vector_data: extract_vectors()로 추출된 데이터
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리

        Returns:
            Chroma: 재구성된 vector store
        """
        import chromadb
        from chromadb.config import Settings

        # Create client
        if persist_directory:
            client = chromadb.Client(Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False
            ))
        else:
            client = chromadb.Client()

        # Create or get collection
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=None  # We already have embeddings
        )

        # Add vectors
        collection.add(
            ids=vector_data['ids'],
            embeddings=vector_data['embeddings'],
            documents=vector_data['documents'],
            metadatas=vector_data['metadatas'] if vector_data['metadatas'] else None
        )

        # Wrap in Langchain Chroma
        vectorstore = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=self._get_embeddings()
        )

        return vectorstore
