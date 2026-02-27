"""
Vector DB retrieval utilities for RAG-based VLA inference.

Provides simple vector similarity search for retrieving relevant demonstrations
based on text prompts or visual observations.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


class LocalVectorDB:
    """
    Local vector database for RAG retrieval.
    
    Loads pre-built vector DB artifacts from ~/.serve/vector_db/<team_id>/
    and provides similarity search functionality.
    """
    
    def __init__(self, team_id: str, vector_db_root: Optional[Path] = None):
        """
        Initialize local vector DB.
        
        Args:
            team_id: Team identifier
            vector_db_root: Root directory for vector DBs (default: ~/.serve/vector_db)
        
        Raises:
            FileNotFoundError: If vector DB not found
            ValueError: If vector DB is invalid
        """
        self.team_id = team_id
        
        if vector_db_root is None:
            vector_db_root = Path.home() / ".serve" / "vector_db"
        
        self.db_path = vector_db_root / team_id
        
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Vector DB not found for team {team_id}. "
                f"Build it first using: serve data build-index {team_id}"
            )
        
        # Load vector DB artifacts
        self._load_db()
    
    def _load_db(self):
        """Load vector DB artifacts from disk."""
        # Load summary
        summary_path = self.db_path / "summary.json"
        if not summary_path.exists():
            raise ValueError(f"summary.json not found in {self.db_path}")
        
        self.summary = json.loads(summary_path.read_text(encoding="utf-8"))
        logger.info(f"Loaded vector DB for team {self.team_id}: "
                   f"{self.summary['num_vectors']} vectors, "
                   f"{self.summary['num_episodes']} episodes")
        
        # Load vectors
        vectors_path = self.db_path / "vectors.npz"
        if not vectors_path.exists():
            raise ValueError(f"vectors.npz not found in {self.db_path}")
        
        vectors_data = np.load(vectors_path)
        self.embeddings = vectors_data["embeddings"]  # (N, D)
        self.episode_ids = vectors_data["episode_ids"]  # (N,)
        self.step_indices = vectors_data["step_indices"]  # (N,)
        
        # Load episode metadata
        episodes_path = self.db_path / "episodes.json"
        if not episodes_path.exists():
            raise ValueError(f"episodes.json not found in {self.db_path}")
        
        self.episodes = json.loads(episodes_path.read_text(encoding="utf-8"))
        self.episode_map = {ep["episode_id"]: ep for ep in self.episodes}
        
        # Try to load FAISS index
        faiss_path = self.db_path / "index.faiss"
        if faiss_path.exists():
            try:
                import faiss
                self.faiss_index = faiss.read_index(str(faiss_path))
                logger.info("Loaded FAISS index for fast retrieval")
            except ImportError:
                self.faiss_index = None
                logger.warning("FAISS not available; using numpy for search")
            except Exception as exc:
                self.faiss_index = None
                logger.warning(f"Failed to load FAISS index: {exc}")
        else:
            self.faiss_index = None
    
    def search_by_embedding(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        episode_id: Optional[int] = None,
    ) -> List[Dict]:
        """
        Search for similar vectors by embedding.
        
        Args:
            query_embedding: Query embedding vector (D,) or (1, D)
            k: Number of results to return
            episode_id: Optional episode ID to filter by
        
        Returns:
            List of result dicts with keys:
            - distance: float - L2 distance
            - episode_id: int - Episode identifier
            - step_index: int - Step index within episode
            - episode_meta: dict - Episode metadata
            - processed_demo_path: str - Path to processed_demo.npz
        """
        # Reshape query
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        query_embedding = query_embedding.astype(np.float32)
        
        # Filter by episode if requested
        if episode_id is not None:
            mask = self.episode_ids == episode_id
            search_embeddings = self.embeddings[mask]
            search_episode_ids = self.episode_ids[mask]
            search_step_indices = self.step_indices[mask]
        else:
            search_embeddings = self.embeddings
            search_episode_ids = self.episode_ids
            search_step_indices = self.step_indices
        
        if len(search_embeddings) == 0:
            return []
        
        # Limit k to available vectors
        k = min(k, len(search_embeddings))
        
        # Search using FAISS or numpy
        if self.faiss_index is not None and episode_id is None:
            # Use FAISS for fast search (only if no filtering)
            distances, indices = self.faiss_index.search(query_embedding, k)
            distances = distances[0]
            indices = indices[0]
        else:
            # Use numpy L2 distance
            distances = np.linalg.norm(search_embeddings - query_embedding, axis=1)
            indices = np.argsort(distances)[:k]
            distances = distances[indices]
        
        # Build results
        results = []
        for dist, idx in zip(distances, indices):
            ep_id = int(search_episode_ids[idx])
            step_idx = int(search_step_indices[idx])
            ep_meta = self.episode_map.get(ep_id, {})
            
            results.append({
                "distance": float(dist),
                "episode_id": ep_id,
                "step_index": step_idx,
                "episode_meta": ep_meta,
                "processed_demo_path": ep_meta.get("processed_demo_path", ""),
                "prompt": ep_meta.get("prompt", ""),
            })
        
        return results
    
    def search_by_prompt(
        self,
        query_prompt: str,
        k: int = 5,
    ) -> List[Dict]:
        """
        Search for episodes by prompt text similarity.
        
        This is a simple keyword-based search. For production, use proper
        text embeddings (e.g., sentence-transformers).
        
        Args:
            query_prompt: Query text
            k: Number of results to return
        
        Returns:
            List of episode metadata dicts
        """
        query_lower = query_prompt.lower()
        
        # Simple keyword matching (for demo purposes)
        scores = []
        for ep in self.episodes:
            prompt = ep.get("prompt", "").lower()
            if not prompt:
                scores.append(0)
                continue
            
            # Count matching words
            query_words = set(query_lower.split())
            prompt_words = set(prompt.split())
            overlap = len(query_words & prompt_words)
            scores.append(overlap)
        
        # Get top-k episodes
        top_indices = np.argsort(scores)[::-1][:k]
        results = [self.episodes[idx] for idx in top_indices if scores[idx] > 0]
        
        return results
    
    def get_episode(self, episode_id: int) -> Optional[Dict]:
        """
        Get episode metadata by ID.
        
        Args:
            episode_id: Episode identifier
        
        Returns:
            Episode metadata dict or None if not found
        """
        return self.episode_map.get(episode_id)
    
    def load_demo(self, episode_id: int) -> Optional[Dict]:
        """
        Load processed_demo.npz for episode.
        
        Args:
            episode_id: Episode identifier
        
        Returns:
            Dict with NPZ arrays or None if not found
        """
        ep_meta = self.get_episode(episode_id)
        if ep_meta is None:
            return None
        
        demo_path = Path(ep_meta["processed_demo_path"])
        if not demo_path.exists():
            logger.warning(f"Demo file not found: {demo_path}")
            return None
        
        try:
            data = np.load(demo_path, allow_pickle=True)
            return {
                "state": data["state"],
                "actions": data["actions"],
                "base_image": data["base_image"],
                "wrist_image": data["wrist_image"],
                "base_image_embeddings": data["base_image_embeddings"],
                "wrist_image_embeddings": data["wrist_image_embeddings"],
                "prompt": str(data["prompt"]),
            }
        except Exception as exc:
            logger.error(f"Failed to load demo {demo_path}: {exc}")
            return None
    
    def stats(self) -> Dict:
        """
        Get vector DB statistics.
        
        Returns:
            Statistics dict
        """
        return {
            "team_id": self.team_id,
            "num_episodes": len(self.episodes),
            "num_vectors": len(self.embeddings),
            "embedding_dim": self.embeddings.shape[1],
            "has_faiss": self.faiss_index is not None,
            "created_at": self.summary.get("created_at_utc", "unknown"),
        }
