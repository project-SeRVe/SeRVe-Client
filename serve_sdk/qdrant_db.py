"""
Qdrant vector database client for SeRVe-Client.

Manages local Qdrant instance for RAG-based VLA inference.
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

logger = logging.getLogger(__name__)


class LocalQdrantDB:
    """
    Local Qdrant database for RAG retrieval.
    
    Uses embedded Qdrant instance (no separate server needed) for edge deployment.
    Stores vector embeddings with rich metadata for demonstration retrieval.
    """
    
    def __init__(
        self,
        team_id: str,
        qdrant_root: Optional[Path] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize local Qdrant DB.
        
        Args:
            team_id: Team identifier
            qdrant_root: Root directory for Qdrant storage (default: ~/.serve/qdrant)
            collection_name: Collection name (default: team_{team_id})
        
        Raises:
            FileNotFoundError: If Qdrant DB not found
            ValueError: If Qdrant DB is invalid
        """
        self.team_id = team_id
        
        if qdrant_root is None:
            qdrant_root = Path.home() / ".serve" / "qdrant"
        
        self.qdrant_root = qdrant_root
        self.qdrant_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedded Qdrant client
        self.client = QdrantClient(path=str(self.qdrant_root))
        
        # Collection name
        self.collection_name = collection_name or f"team_{team_id}"
        
        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        if self.collection_name not in collection_names:
            raise FileNotFoundError(
                f"Qdrant collection '{self.collection_name}' not found. "
                f"Build it first using: serve data build-index {team_id}"
            )
        
        logger.info(f"Connected to Qdrant collection: {self.collection_name}")
    
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
            - score: float - Similarity score (higher = more similar)
            - distance: float - L2 distance (for backward compatibility)
            - episode_id: int - Episode identifier
            - step_index: int - Step index within episode
            - episode_meta: dict - Episode metadata (from payload)
            - processed_demo_path: str - Path to processed_demo.npz
            - prompt: str - Task prompt
        """
        # Reshape query
        if query_embedding.ndim == 2:
            query_embedding = query_embedding.flatten()
        
        query_embedding = query_embedding.astype(np.float32).tolist()
        
        # Build filter if episode_id specified
        query_filter = None
        if episode_id is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="episode_id",
                        match=MatchValue(value=episode_id),
                    )
                ]
            )
        
        # Search
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            query_filter=query_filter,
        )
        
        # Build results
        results = []
        for hit in search_results:
            payload = hit.payload or {}
            
            # Convert cosine similarity to distance (for backward compatibility)
            # Qdrant returns score (higher = more similar)
            # We convert to distance (lower = more similar) for consistency
            distance = 1.0 - hit.score if hit.score is not None else 0.0
            
            results.append({
                "score": hit.score,
                "distance": distance,
                "episode_id": payload.get("episode_id", -1),
                "step_index": payload.get("step_index", -1),
                "episode_meta": {
                    "episode_id": payload.get("episode_id"),
                    "relative_path": payload.get("relative_path"),
                    "processed_demo_path": payload.get("processed_demo_path"),
                    "num_steps": payload.get("num_steps"),
                    "state_dim": payload.get("state_dim"),
                    "action_dim": payload.get("action_dim"),
                    "prompt": payload.get("prompt"),
                },
                "processed_demo_path": payload.get("processed_demo_path", ""),
                "prompt": payload.get("prompt", ""),
            })
        
        return results
    
    def search_by_prompt(
        self,
        query_prompt: str,
        k: int = 5,
    ) -> List[Dict]:
        """
        Search for episodes by prompt text similarity.
        
        This uses Qdrant's payload search (keyword matching).
        For semantic search, use proper text embeddings.
        
        Args:
            query_prompt: Query text
            k: Number of results to return
        
        Returns:
            List of episode metadata dicts
        """
        # Use scroll to get all points and filter by prompt
        # This is a simple keyword match; for production, use text embeddings
        
        # Get all unique episodes
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,  # Get all points
            with_payload=True,
            with_vectors=False,
        )
        
        points = scroll_result[0]
        
        # Extract unique episodes
        episodes = {}
        for point in points:
            payload = point.payload or {}
            ep_id = payload.get("episode_id")
            if ep_id is not None and ep_id not in episodes:
                episodes[ep_id] = payload
        
        # Simple keyword matching
        query_lower = query_prompt.lower()
        scores = []
        episode_list = list(episodes.values())
        
        for ep_payload in episode_list:
            prompt = ep_payload.get("prompt", "").lower()
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
        results = [
            {
                "episode_id": episode_list[idx].get("episode_id"),
                "relative_path": episode_list[idx].get("relative_path"),
                "processed_demo_path": episode_list[idx].get("processed_demo_path"),
                "num_steps": episode_list[idx].get("num_steps"),
                "state_dim": episode_list[idx].get("state_dim"),
                "action_dim": episode_list[idx].get("action_dim"),
                "prompt": episode_list[idx].get("prompt"),
            }
            for idx in top_indices if scores[idx] > 0
        ]
        
        return results
    
    def get_episode(self, episode_id: int) -> Optional[Dict]:
        """
        Get episode metadata by ID.
        
        Args:
            episode_id: Episode identifier
        
        Returns:
            Episode metadata dict or None if not found
        """
        # Scroll with filter
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="episode_id",
                        match=MatchValue(value=episode_id),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        
        points = scroll_result[0]
        if not points:
            return None
        
        payload = points[0].payload
        return {
            "episode_id": payload.get("episode_id"),
            "relative_path": payload.get("relative_path"),
            "processed_demo_path": payload.get("processed_demo_path"),
            "num_steps": payload.get("num_steps"),
            "state_dim": payload.get("state_dim"),
            "action_dim": payload.get("action_dim"),
            "prompt": payload.get("prompt"),
        }
    
    def load_demo(self, episode_id: int) -> Optional[Dict]:
        """
        Load processed_demo.npz for episode.
        
        Args:
            episode_id: Episode identifier
        
        Returns:
            Dict with npz data arrays or None if not found
        """
        ep_meta = self.get_episode(episode_id)
        if ep_meta is None:
            return None
        
        demo_path = Path(ep_meta.get("processed_demo_path", ""))
        if not demo_path.exists():
            logger.warning(f"Demo file not found: {demo_path}")
            return None
        
        try:
            data = np.load(demo_path, allow_pickle=True)
            return {
                "state": data["state"],
                "actions": data["actions"],
                "base_image": data["base_image"],
                "wrist_image": data.get("wrist_image"),
                "base_image_embeddings": data["base_image_embeddings"],
                "wrist_image_embeddings": data.get("wrist_image_embeddings"),
                "prompt": str(data.get("prompt", "")),
            }
        except Exception as exc:
            logger.error(f"Failed to load {demo_path}: {exc}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with stats: num_vectors, num_episodes, embedding_dim
        """
        collection_info = self.client.get_collection(self.collection_name)
        
        # Get unique episode count
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        
        points = scroll_result[0]
        unique_episodes = set()
        for point in points:
            payload = point.payload or {}
            ep_id = payload.get("episode_id")
            if ep_id is not None:
                unique_episodes.add(ep_id)
        
        return {
            "team_id": self.team_id,
            "collection_name": self.collection_name,
            "num_vectors": collection_info.points_count,
            "num_episodes": len(unique_episodes),
            "embedding_dim": collection_info.config.params.vectors.size,
            "distance": collection_info.config.params.vectors.distance.name,
        }
