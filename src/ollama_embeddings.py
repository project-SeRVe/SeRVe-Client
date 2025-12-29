"""Ollama API를 사용한 임베딩 생성"""
import requests
from typing import List
import os


class OllamaEmbeddings:
    """Ollama API를 사용한 임베딩 래퍼
    
    로컬 모델 다운로드 없이 Ollama 서버의 임베딩 API를 사용합니다.
    """
    
    def __init__(self, model_name='nomic-embed-text', base_url=None):
        """
        Initialize Ollama embeddings
        
        Args:
            model_name: Ollama 임베딩 모델 이름 (default: nomic-embed-text)
            base_url: Ollama API URL (default: OLLAMA_BASE_URL 환경변수 또는 http://localhost:11434)
        """
        self.model_name = model_name
        self.base_url = base_url or os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.api_url = f"{self.base_url}/api/embeddings"
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding from text using Ollama API
        
        Args:
            text: Input text string
        
        Returns:
            List of floats representing the text embedding
        """
        response = requests.post(
            self.api_url,
            json={"model": self.model_name, "prompt": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()['embedding']
    
    def embed_image(self, image) -> List[float]:
        """
        Generate embedding from image (using LLaVA for caption, then embed)
        
        Args:
            image: PIL Image object
        
        Returns:
            List of floats representing the image embedding
        """
        # 이미지를 텍스트 설명으로 변환 (간단 구현)
        # TODO: LLaVA로 더 나은 캡션 생성
        caption = "image content"
        return self.embed_text(caption)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Langchain compatibility: batch embed texts
        
        Args:
            texts: List of text strings
        
        Returns:
            List of embeddings
        """
        return [self.embed_text(t) for t in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """
        Langchain compatibility: embed query text
        
        Args:
            text: Query text string
        
        Returns:
            Embedding vector
        """
        return self.embed_text(text)
