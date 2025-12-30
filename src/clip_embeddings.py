from sentence_transformers import SentenceTransformer
from PIL import Image
from typing import List
import io


class CLIPEmbeddings:
    """CLIP embedding wrapper for both text and images

    This class provides a unified interface for generating embeddings from both
    text and images using the CLIP model via sentence-transformers.
    Compatible with langchain's embedding interface.
    """

    def __init__(self, model_name='clip-ViT-B-32'):
        """
        Initialize CLIP embeddings model

        Args:
            model_name: Name of the CLIP model to use (default: clip-ViT-B-32)
                       This model produces 512-dimensional embeddings
        """
        import torch
        # Explicitly set device to avoid meta tensor issues
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name

    def embed_text(self, text: str) -> List[float]:
        """
        Generate 512-dim embedding from text

        Args:
            text: Input text string

        Returns:
            List of 512 floats representing the text embedding
        """
        return self.model.encode(text, convert_to_numpy=True).tolist()

    def embed_image(self, image: Image.Image) -> List[float]:
        """
        Generate 512-dim embedding from PIL Image

        Args:
            image: PIL Image object

        Returns:
            List of 512 floats representing the image embedding
        """
        # Preprocess: resize to max 1024x1024, convert to RGB
        image = self._preprocess_image(image)
        return self.model.encode(image, convert_to_numpy=True).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Langchain compatibility: batch embed texts

        Args:
            texts: List of text strings

        Returns:
            List of embeddings (each embedding is a list of 512 floats)
        """
        return [self.embed_text(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """
        Langchain compatibility: embed query text

        Args:
            text: Query text string

        Returns:
            List of 512 floats representing the text embedding
        """
        return self.embed_text(text)

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image before embedding generation

        - Resize to max 1024x1024 preserving aspect ratio
        - Convert to RGB format

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image
        """
        # Resize to max 1024x1024 preserving aspect ratio
        image.thumbnail((1024, 1024), Image.LANCZOS)

        # Convert to RGB (handle RGBA, grayscale, etc.)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image
