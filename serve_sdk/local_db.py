"""
Local SQLite database for metadata management.

Manages Scenario, Demo, and Artifact tables for tracking processed demonstrations
and their lifecycle (pending → approved/rejected).
"""
import hashlib
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

logger = logging.getLogger(__name__)

# Type aliases
DemoStatus = Literal["pending", "approved", "rejected"]
ArtifactKind = Literal["processed", "raw"]


class LocalDB:
    """
    Local SQLite database wrapper for SeRVe-Client metadata.
    
    Manages:
    - Scenarios: Task prompts and their hashes
    - Demos: Individual demonstrations with status tracking
    - Artifacts: NPZ files with object keys and local paths
    """
    
    def __init__(self, db_path: str = "local.db"):
        """
        Initialize local database connection.
        
        Args:
            db_path: Path to SQLite database file (default: "local.db")
        """
        self.db_path = Path(db_path).resolve()
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_connection()
        self._init_schema()
    
    def _ensure_connection(self) -> None:
        """Ensure database connection is established."""
        if self.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            logger.debug(f"Connected to local database: {self.db_path}")
    
    def _init_schema(self) -> None:
        """Initialize database schema if tables don't exist."""
        self._ensure_connection()
        
        # Scenario table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scenario (
                scenario_id TEXT PRIMARY KEY,
                prompt_text TEXT NOT NULL,
                prompt_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Demo table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS demo (
                demo_id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
                num_steps INTEGER NOT NULL,
                state_dim INTEGER NOT NULL,
                action_dim INTEGER NOT NULL,
                image_h INTEGER,
                image_w INTEGER,
                embed_dim INTEGER,
                embed_model_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                source_repo TEXT,
                source_episode_index INTEGER,
                FOREIGN KEY (scenario_id) REFERENCES scenario(scenario_id) ON DELETE CASCADE
            )
        """)
        
        # Artifact table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS artifact (
                artifact_id TEXT PRIMARY KEY,
                demo_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('processed', 'raw')),
                object_key TEXT NOT NULL UNIQUE,
                sha256 TEXT,
                size INTEGER,
                version INTEGER DEFAULT 1,
                enc_algo TEXT,
                nonce TEXT,
                dek_wrapped_by_kek TEXT,
                kek_version TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                local_path TEXT,
                FOREIGN KEY (demo_id) REFERENCES demo(demo_id) ON DELETE CASCADE
            )
        """)
        
        # Indexes for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_demo_scenario 
            ON demo(scenario_id)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_demo_status 
            ON demo(status)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifact_demo 
            ON artifact(demo_id)
        """)
        
        self.conn.commit()
        logger.debug("Database schema initialized")
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Database connection closed")
    
    # ========== Scenario Operations ==========
    
    def get_or_create_scenario(self, prompt_text: str) -> str:
        """
        Get existing scenario ID or create new scenario for prompt.
        
        Args:
            prompt_text: Task prompt text
            
        Returns:
            Scenario ID (UUID)
        """
        self._ensure_connection()
        
        # Generate hash for prompt
        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        
        # Check if scenario exists
        cursor = self.conn.execute(
            "SELECT scenario_id FROM scenario WHERE prompt_hash = ?",
            (prompt_hash,)
        )
        row = cursor.fetchone()
        
        if row:
            return row["scenario_id"]
        
        # Create new scenario
        scenario_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO scenario (scenario_id, prompt_text, prompt_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (scenario_id, prompt_text, prompt_hash, datetime.now(timezone.utc))
        )
        self.conn.commit()
        logger.debug(f"Created scenario {scenario_id} for prompt: {prompt_text[:50]}...")
        
        return scenario_id
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Get scenario by ID.
        
        Args:
            scenario_id: Scenario UUID
            
        Returns:
            Scenario dict or None if not found
        """
        self._ensure_connection()
        cursor = self.conn.execute(
            "SELECT * FROM scenario WHERE scenario_id = ?",
            (scenario_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ========== Demo Operations ==========
    
    def create_demo(
        self,
        scenario_id: str,
        status: DemoStatus,
        num_steps: int,
        state_dim: int,
        action_dim: int,
        image_h: Optional[int] = None,
        image_w: Optional[int] = None,
        embed_dim: Optional[int] = None,
        embed_model_id: Optional[str] = None,
        source_repo: Optional[str] = None,
        source_episode_index: Optional[int] = None,
        demo_id: Optional[str] = None
    ) -> str:
        """
        Create new demo record.
        
        Args:
            scenario_id: Parent scenario UUID
            status: Demo status (pending/approved/rejected)
            num_steps: Number of timesteps
            state_dim: State dimension
            action_dim: Action dimension
            image_h: Image height
            image_w: Image width
            embed_dim: Embedding dimension
            embed_model_id: Embedding model identifier
            source_repo: Source repository name
            source_episode_index: Episode index in source repo
            demo_id: Optional demo UUID (generated if not provided)
            
        Returns:
            Demo ID (UUID)
        """
        self._ensure_connection()
        
        if demo_id is None:
            demo_id = str(uuid.uuid4())
        
        self.conn.execute(
            """
            INSERT INTO demo (
                demo_id, scenario_id, status, num_steps, state_dim, action_dim,
                image_h, image_w, embed_dim, embed_model_id, created_at,
                source_repo, source_episode_index
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                demo_id, scenario_id, status, num_steps, state_dim, action_dim,
                image_h, image_w, embed_dim, embed_model_id, datetime.now(timezone.utc),
                source_repo, source_episode_index
            )
        )
        self.conn.commit()
        logger.debug(f"Created demo {demo_id} with status={status}")
        
        return demo_id
    
    def get_demo(self, demo_id: str) -> Optional[Dict[str, Any]]:
        """
        Get demo by ID.
        
        Args:
            demo_id: Demo UUID
            
        Returns:
            Demo dict or None if not found
        """
        self._ensure_connection()
        cursor = self.conn.execute(
            "SELECT * FROM demo WHERE demo_id = ?",
            (demo_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_demo_status(
        self,
        demo_id: str,
        status: DemoStatus,
        approved_at: Optional[datetime] = None
    ) -> None:
        """
        Update demo status.
        
        Args:
            demo_id: Demo UUID
            status: New status (pending/approved/rejected)
            approved_at: Timestamp for approval (auto-set if status=approved)
        """
        self._ensure_connection()
        
        if status == "approved" and approved_at is None:
            approved_at = datetime.now(timezone.utc)
        
        self.conn.execute(
            "UPDATE demo SET status = ?, approved_at = ? WHERE demo_id = ?",
            (status, approved_at, demo_id)
        )
        self.conn.commit()
        logger.debug(f"Updated demo {demo_id} status to {status}")
    
    def list_demos(
        self,
        scenario_id: Optional[str] = None,
        status: Optional[DemoStatus] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List demos with optional filters.
        
        Args:
            scenario_id: Filter by scenario UUID
            status: Filter by status
            limit: Maximum number of results
            
        Returns:
            List of demo dicts
        """
        self._ensure_connection()
        
        query = "SELECT * FROM demo WHERE 1=1"
        params = []
        
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== Artifact Operations ==========
    
    def create_artifact(
        self,
        demo_id: str,
        kind: ArtifactKind,
        object_key: str,
        local_path: str,
        sha256: Optional[str] = None,
        size: Optional[int] = None,
        version: int = 1,
        enc_algo: Optional[str] = None,
        nonce: Optional[str] = None,
        dek_wrapped_by_kek: Optional[str] = None,
        kek_version: Optional[str] = None,
        artifact_id: Optional[str] = None
    ) -> str:
        """
        Create artifact record.
        
        Args:
            demo_id: Parent demo UUID
            kind: Artifact type (processed/raw)
            object_key: Object storage key
            local_path: Local file path
            sha256: SHA256 hash
            size: File size in bytes
            version: Artifact version
            enc_algo: Encryption algorithm (if encrypted)
            nonce: Encryption nonce
            dek_wrapped_by_kek: Wrapped data encryption key
            kek_version: Key encryption key version
            artifact_id: Optional artifact UUID
            
        Returns:
            Artifact ID (UUID)
        """
        self._ensure_connection()
        
        if artifact_id is None:
            artifact_id = str(uuid.uuid4())
        
        self.conn.execute(
            """
            INSERT INTO artifact (
                artifact_id, demo_id, kind, object_key, sha256, size, version,
                enc_algo, nonce, dek_wrapped_by_kek, kek_version, created_at, local_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id, demo_id, kind, object_key, sha256, size, version,
                enc_algo, nonce, dek_wrapped_by_kek, kek_version,
                datetime.now(timezone.utc), local_path
            )
        )
        self.conn.commit()
        logger.debug(f"Created artifact {artifact_id} for demo {demo_id}")
        
        return artifact_id
    
    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get artifact by ID.
        
        Args:
            artifact_id: Artifact UUID
            
        Returns:
            Artifact dict or None if not found
        """
        self._ensure_connection()
        cursor = self.conn.execute(
            "SELECT * FROM artifact WHERE artifact_id = ?",
            (artifact_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_artifact_by_object_key(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Get artifact by object key.
        
        Args:
            object_key: Object storage key
            
        Returns:
            Artifact dict or None if not found
        """
        self._ensure_connection()
        cursor = self.conn.execute(
            "SELECT * FROM artifact WHERE object_key = ?",
            (object_key,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def list_artifacts(
        self,
        demo_id: Optional[str] = None,
        kind: Optional[ArtifactKind] = None
    ) -> List[Dict[str, Any]]:
        """
        List artifacts with optional filters.
        
        Args:
            demo_id: Filter by demo UUID
            kind: Filter by kind (processed/raw)
            
        Returns:
            List of artifact dicts
        """
        self._ensure_connection()
        
        query = "SELECT * FROM artifact WHERE 1=1"
        params = []
        
        if demo_id:
            query += " AND demo_id = ?"
            params.append(demo_id)
        
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        
        query += " ORDER BY created_at DESC"
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def update_artifact_local_path(self, artifact_id: str, local_path: str) -> None:
        """
        Update artifact local path.
        
        Args:
            artifact_id: Artifact UUID
            local_path: New local file path
        """
        self._ensure_connection()
        self.conn.execute(
            "UPDATE artifact SET local_path = ? WHERE artifact_id = ?",
            (local_path, artifact_id)
        )
        self.conn.commit()
        logger.debug(f"Updated artifact {artifact_id} local_path")
    
    def get_artifacts_by_status(self, status: DemoStatus, kind: str = "processed") -> List[Dict[str, Any]]:
        """
        Get all artifacts for demos with specified status.
        
        Args:
            status: Demo status (pending/approved/rejected)
            kind: Artifact kind (default: processed)
        
        Returns:
            List of dicts with artifact and demo metadata
        """
        self._ensure_connection()
        
        query = """
            SELECT 
                a.artifact_id,
                a.demo_id,
                a.kind,
                a.object_key,
                a.local_path,
                a.sha256,
                a.size,
                a.created_at as artifact_created_at,
                d.scenario_id,
                d.status,
                d.num_steps,
                d.state_dim,
                d.action_dim,
                d.image_h,
                d.image_w,
                d.embed_dim,
                d.embed_model_id,
                d.created_at as demo_created_at,
                d.approved_at,
                s.prompt_text,
                s.prompt_hash
            FROM artifact a
            JOIN demo d ON a.demo_id = d.demo_id
            JOIN scenario s ON d.scenario_id = s.scenario_id
            WHERE d.status = ? AND a.kind = ?
            ORDER BY d.created_at DESC
        """
        
        cursor = self.conn.execute(query, (status, kind))
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== Utility Methods ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with counts per table and status
        """
        self._ensure_connection()
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM scenario")
        scenario_count = cursor.fetchone()["count"]
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM demo")
        demo_count = cursor.fetchone()["count"]
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM artifact")
        artifact_count = cursor.fetchone()["count"]
        
        cursor = self.conn.execute(
            "SELECT status, COUNT(*) as count FROM demo GROUP BY status"
        )
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "scenarios": scenario_count,
            "demos": demo_count,
            "artifacts": artifact_count,
            "demo_status": status_counts,
            "db_path": str(self.db_path)
        }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def delete_artifact(self, artifact_id: str, delete_file: bool = True) -> bool:
        """
        Delete artifact from database and optionally from disk.
        
        Args:
            artifact_id: Artifact UUID
            delete_file: If True, also delete physical file from ~/.serve/artifacts/
        
        Returns:
            True if deleted, False if not found
        """
        self._ensure_connection()
        
        # Get artifact details before deletion
        artifact = self.conn.execute(
            "SELECT object_key FROM artifact WHERE artifact_id = ?",
            (artifact_id,)
        ).fetchone()
        
        if not artifact:
            return False
        
        # Delete from database
        self.conn.execute(
            "DELETE FROM artifact WHERE artifact_id = ?",
            (artifact_id,)
        )
        self.conn.commit()
        
        # Delete physical file if requested
        if delete_file:
            try:
                from serve_sdk.artifact_storage import delete_artifact as delete_file_fn
                delete_file_fn(artifact["object_key"])
                logger.info(f"Deleted artifact file: {artifact['object_key']}")
            except Exception as exc:
                logger.warning(f"Failed to delete artifact file: {exc}")
        
        logger.info(f"Deleted artifact from DB: {artifact_id}")
        return True

    def delete_demo(self, demo_id: str, delete_files: bool = True) -> bool:
        """
        Delete demo and all related artifacts.
        
        Args:
            demo_id: Demo UUID
            delete_files: If True, also delete physical artifact files
        
        Returns:
            True if deleted, False if not found
        """
        self._ensure_connection()
        
        # Check if demo exists
        demo = self.conn.execute(
            "SELECT demo_id FROM demo WHERE demo_id = ?",
            (demo_id,)
        ).fetchone()
        
        if not demo:
            return False
        
        # Delete artifact files if requested (before DB deletion)
        if delete_files:
            artifacts = self.conn.execute(
                "SELECT object_key FROM artifact WHERE demo_id = ?",
                (demo_id,)
            ).fetchall()
            
            from serve_sdk.artifact_storage import delete_artifact as delete_file_fn
            for artifact in artifacts:
                try:
                    delete_file_fn(artifact["object_key"])
                    logger.debug(f"Deleted artifact file: {artifact['object_key']}")
                except Exception as exc:
                    logger.warning(f"Failed to delete artifact file: {exc}")
        
        # Delete demo (artifacts cascade via ON DELETE CASCADE)
        self.conn.execute(
            "DELETE FROM demo WHERE demo_id = ?",
            (demo_id,)
        )
        self.conn.commit()
        
        logger.info(f"Deleted demo from DB: {demo_id}")
        return True

    def delete_scenario(self, scenario_id: str) -> bool:
        """
        Delete scenario and all related demos/artifacts.
        
        WARNING: This cascades to all demos and artifacts!
        
        Args:
            scenario_id: Scenario UUID
        
        Returns:
            True if deleted, False if not found
        """
        self._ensure_connection()
        
        # Check if scenario exists
        scenario = self.conn.execute(
            "SELECT scenario_id FROM scenario WHERE scenario_id = ?",
            (scenario_id,)
        ).fetchone()
        
        if not scenario:
            return False
        
        # Delete all artifact files for demos in this scenario
        artifacts = self.conn.execute(
            """
            SELECT a.object_key
            FROM artifact a
            JOIN demo d ON a.demo_id = d.demo_id
            WHERE d.scenario_id = ?
            """,
            (scenario_id,)
        ).fetchall()
        
        from serve_sdk.artifact_storage import delete_artifact as delete_file_fn
        for artifact in artifacts:
            try:
                delete_file_fn(artifact["object_key"])
                logger.debug(f"Deleted artifact file: {artifact['object_key']}")
            except Exception as exc:
                logger.warning(f"Failed to delete artifact file: {exc}")
        
        # Delete scenario (demos and artifacts cascade)
        self.conn.execute(
            "DELETE FROM scenario WHERE scenario_id = ?",
            (scenario_id,)
        )
        self.conn.commit()
        
        logger.info(f"Deleted scenario from DB: {scenario_id}")
        return True


def get_default_db() -> LocalDB:
    """
    Get default local database instance.
    
    Returns:
        LocalDB instance for local.db in project root
    """
    # Find project root (where local.db should be)
    current = Path(__file__).resolve()
    # Go up from serve_sdk/ to project root
    project_root = current.parent.parent
    db_path = project_root / "local.db"
    
    return LocalDB(str(db_path))
