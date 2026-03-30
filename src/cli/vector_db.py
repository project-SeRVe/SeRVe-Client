"""
FAISS-based vector DB retrieval utilities for RAG-based VLA inference.

VLA 서버(ricl_openpi_libero)와 동일하게 FAISS(L2) 인덱스를 사용합니다.
~/.serve/faiss/<team_id>/ 에 저장된 인덱스를 로드하여 유사도 검색을 수행합니다.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)


class LocalVectorDB:
    """
    Local FAISS vector database for RAG retrieval.

    ~/.serve/faiss/<team_id>/ 의 FAISS 인덱스를 로드합니다.
    VLA 서버(ricl_openpi_libero)와 동일한 L2 거리 방식을 사용합니다.
    """

    def __init__(self, team_id: str, faiss_root: Optional[Path] = None):
        """
        Initialize local FAISS vector DB.

        Args:
            team_id: Team identifier
            faiss_root: Root directory for FAISS storage (default: ~/.serve/faiss)

        Raises:
            FileNotFoundError: If FAISS index not found
            ImportError: If faiss-cpu not installed
        """
        try:
            import faiss
            self._faiss = faiss
        except ImportError:
            raise ImportError("faiss-cpu가 설치되지 않았습니다. 설치: pip install faiss-cpu")

        self.team_id = team_id

        if faiss_root is None:
            faiss_root = Path.home() / ".serve" / "faiss"

        self.index_dir = faiss_root / team_id

        if not self.index_dir.exists():
            raise FileNotFoundError(
                f"FAISS 인덱스를 찾을 수 없습니다: {self.index_dir}\n"
                f"먼저 인덱스를 빌드하세요: serve data build-index {team_id}"
            )

        index_path = self.index_dir / "index.faiss"
        meta_path = self.index_dir / "metadata.npz"

        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"index.faiss 또는 metadata.npz가 없습니다: {self.index_dir}\n"
                f"재빌드: serve data build-index {team_id} --overwrite"
            )

        # Load FAISS index
        self._index = faiss.read_index(str(index_path))

        # Load metadata
        meta = np.load(meta_path, allow_pickle=True)
        self._episode_idx = meta["episode_idx"]   # (N,) int32
        self._step_idx = meta["step_idx"]         # (N,) int32
        self._num_steps = meta["num_steps"]       # (N,) int32
        self._state_dim = meta["state_dim"]       # (N,) int32
        self._action_dim = meta["action_dim"]     # (N,) int32
        self._npz_path = meta["npz_path"]         # (N,) str
        self._relative_path = meta["relative_path"]  # (N,) str
        self._prompt = meta["prompt"]             # (N,) str

        # Load index info
        info_path = self.index_dir / "index_info.json"
        if info_path.exists():
            self._info = json.loads(info_path.read_text())
        else:
            self._info = {}

        logger.info(f"Loaded FAISS index: {self.index_dir} ({self._index.ntotal} vectors)")

    def search_by_embedding(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
    ) -> List[Dict]:
        """
        Search for similar vectors by embedding (L2 distance).

        Args:
            query_embedding: Query embedding vector (D,) or (1, D)
            k: Number of results to return

        Returns:
            List of result dicts with keys:
            - score: float - similarity score (1 / (1 + L2_distance))
            - distance: float - L2 distance
            - episode_id: int
            - step_index: int
            - processed_demo_path: str
            - relative_path: str
            - prompt: str
            - num_steps: int
        """
        if query_embedding.ndim == 2:
            query_embedding = query_embedding.flatten()

        query = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self._index.search(query, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            score = 1.0 / (1.0 + float(dist))  # L2 → similarity
            results.append({
                "score": score,
                "distance": float(dist),
                "episode_id": int(self._episode_idx[idx]),
                "step_index": int(self._step_idx[idx]),
                "num_steps": int(self._num_steps[idx]),
                "state_dim": int(self._state_dim[idx]),
                "action_dim": int(self._action_dim[idx]),
                "processed_demo_path": str(self._npz_path[idx]),
                "relative_path": str(self._relative_path[idx]),
                "prompt": str(self._prompt[idx]),
            })

        return results

    def search_by_prompt(
        self,
        query_prompt: str,
        k: int = 5,
    ) -> List[Dict]:
        """
        Search for episodes by prompt text (keyword matching).

        Args:
            query_prompt: Query text
            k: Number of results to return

        Returns:
            List of unique episode metadata dicts
        """
        # Collect unique episodes with their metadata
        unique_episodes: Dict[int, Dict] = {}
        for i in range(len(self._episode_idx)):
            ep_id = int(self._episode_idx[i])
            if ep_id not in unique_episodes:
                unique_episodes[ep_id] = {
                    "episode_id": ep_id,
                    "num_steps": int(self._num_steps[i]),
                    "state_dim": int(self._state_dim[i]),
                    "action_dim": int(self._action_dim[i]),
                    "processed_demo_path": str(self._npz_path[i]),
                    "relative_path": str(self._relative_path[i]),
                    "prompt": str(self._prompt[i]),
                }

        if not query_prompt:
            return list(unique_episodes.values())[:k]

        # Keyword matching score
        query_words = set(query_prompt.lower().split())
        scored = []
        for ep_id, ep_meta in unique_episodes.items():
            prompt_words = set(ep_meta["prompt"].lower().split())
            overlap = len(query_words & prompt_words)
            scored.append((overlap, ep_meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for score, ep in scored[:k] if score > 0 or not query_prompt]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        unique_episodes = len(set(self._episode_idx.tolist()))
        return {
            "team_id": self.team_id,
            "index_dir": str(self.index_dir),
            "num_vectors": self._index.ntotal,
            "num_episodes": unique_episodes,
            "embedding_dim": self._info.get("embedding_dim", self._index.d),
            "distance": self._info.get("metric", "L2"),
            "embedding_key": self._info.get("embedding_key", "unknown"),
        }

    def load_demo(self, processed_demo_path: str) -> Optional[Dict]:
        """Load processed_demo.npz from path."""
        demo_path = Path(processed_demo_path)
        if not demo_path.exists():
            logger.warning(f"Demo file not found: {demo_path}")
            return None

        try:
            data = np.load(demo_path, allow_pickle=True)
            result = {
                "state": data["state"] if "state" in data.files else None,
                "actions": data["actions"] if "actions" in data.files else None,
                "prompt": str(data["prompt"]) if "prompt" in data.files else "",
            }
            for key in ("base_image", "wrist_image", "top_image",
                        "base_image_embeddings", "wrist_image_embeddings",
                        "top_image_embeddings"):
                if key in data.files:
                    result[key] = data[key]
            return result
        except Exception as exc:
            logger.error(f"Failed to load {demo_path}: {exc}")
            return None
