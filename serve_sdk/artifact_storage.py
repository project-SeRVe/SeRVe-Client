"""
Artifact storage utilities for object-key based file management.

Manages the ~/.serve/artifacts/ directory with object-key based naming.
Replaces directory tree structure (pending/approved/rejected) with
flat storage + database status tracking.
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_artifacts_root() -> Path:
    """
    Get the artifacts root directory (~/.serve/artifacts/).
    
    Returns:
        Path to artifacts directory
    """
    home = Path.home()
    artifacts_dir = home / ".serve" / "artifacts"
    return artifacts_dir


def ensure_artifacts_dir() -> Path:
    """
    Ensure artifacts directory exists.
    
    Returns:
        Path to artifacts directory
    
    Raises:
        OSError: If directory creation fails
    """
    artifacts_dir = get_artifacts_root()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def generate_object_key(artifact_id: str) -> str:
    """
    Generate object key from artifact ID.
    
    Uses first 16 characters of artifact_id as object key.
    Format: <artifact_id_prefix>.npz
    
    Args:
        artifact_id: Artifact UUID from local.db
    
    Returns:
        Object key string (e.g., "a1b2c3d4e5f6g7h8.npz")
    
    Examples:
        >>> generate_object_key("a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6")
        'a1b2c3d4e5f6g7h8.npz'
    """
    # Remove hyphens and take first 16 chars
    clean_id = artifact_id.replace("-", "")[:16]
    return f"{clean_id}.npz"


def generate_object_key_from_content(file_path: Path) -> str:
    """
    Generate object key from file content SHA256 hash.
    
    Alternative to artifact_id-based keys. Uses first 16 characters
    of SHA256 hash as object key.
    
    Args:
        file_path: Path to file to hash
    
    Returns:
        Object key string (e.g., "1a2b3c4d5e6f7g8h.npz")
    
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    hash_hex = sha256_hash.hexdigest()[:16]
    return f"{hash_hex}.npz"


def get_artifact_path(object_key: str) -> Path:
    """
    Get full path to artifact file from object key.
    
    Args:
        object_key: Object key (e.g., "a1b2c3d4e5f6g7h8.npz")
    
    Returns:
        Full path to artifact file
    
    Examples:
        >>> get_artifact_path("a1b2c3d4e5f6g7h8.npz")
        PosixPath('/home/user/.serve/artifacts/a1b2c3d4e5f6g7h8.npz')
    """
    artifacts_dir = get_artifacts_root()
    return artifacts_dir / object_key


def store_artifact(source_path: Path, artifact_id: str) -> tuple[str, Path]:
    """
    Store artifact file with object-key based naming.
    
    Copies source file to ~/.serve/artifacts/<object_key>
    
    Args:
        source_path: Source file path (processed_demo.npz)
        artifact_id: Artifact UUID from local.db
    
    Returns:
        Tuple of (object_key, destination_path)
    
    Raises:
        FileNotFoundError: If source file does not exist
        OSError: If copy fails
    
    Examples:
        >>> store_artifact(Path("demo/processed_demo.npz"), "a1b2c3d4-...")
        ('a1b2c3d4e5f6g7h8.npz', PosixPath('~/.serve/artifacts/a1b2c3d4e5f6g7h8.npz'))
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    # Ensure artifacts directory exists
    artifacts_dir = ensure_artifacts_dir()
    
    # Generate object key and destination path
    object_key = generate_object_key(artifact_id)
    dest_path = artifacts_dir / object_key
    
    # Copy file (overwrite if exists)
    import shutil
    shutil.copy2(source_path, dest_path)
    
    logger.debug(f"Stored artifact: {source_path} → {dest_path}")
    
    return object_key, dest_path


def get_artifact_size(object_key: str) -> Optional[int]:
    """
    Get artifact file size in bytes.
    
    Args:
        object_key: Object key
    
    Returns:
        File size in bytes, or None if file does not exist
    """
    artifact_path = get_artifact_path(object_key)
    if artifact_path.exists():
        return artifact_path.stat().st_size
    return None


def artifact_exists(object_key: str) -> bool:
    """
    Check if artifact file exists.
    
    Args:
        object_key: Object key
    
    Returns:
        True if file exists, False otherwise
    """
    return get_artifact_path(object_key).exists()


def delete_artifact(object_key: str) -> bool:
    """
    Delete artifact file.
    
    Args:
        object_key: Object key
    
    Returns:
        True if file was deleted, False if file did not exist
    
    Raises:
        OSError: If deletion fails
    """
    artifact_path = get_artifact_path(object_key)
    if artifact_path.exists():
        artifact_path.unlink()
        logger.debug(f"Deleted artifact: {artifact_path}")
        return True
    return False


def cleanup_orphan_artifacts() -> list[str]:
    """
    Remove artifact files not referenced in local.db.
    
    Scans ~/.serve/artifacts/ and deletes files without DB records.
    
    Returns:
        List of deleted object keys
    
    Examples:
        >>> cleanup_orphan_artifacts()
        ['a1b2c3d4e5f6g7h8.npz', 'orphan123456789a.npz']
    """
    artifacts_dir = get_artifacts_root()
    if not artifacts_dir.exists():
        return []
    
    # Get all object keys from DB
    from serve_sdk.local_db import get_default_db
    db = get_default_db()
    
    try:
        db_artifacts = db.conn.execute(
            "SELECT object_key FROM artifact"
        ).fetchall()
        db_object_keys = {row["object_key"] for row in db_artifacts}
    finally:
        db.close()
    
    # Find and delete orphan files
    orphans = []
    for file_path in artifacts_dir.glob("*.npz"):
        object_key = file_path.name
        
        if object_key not in db_object_keys:
            try:
                file_path.unlink()
                orphans.append(object_key)
                logger.info(f"Deleted orphan artifact: {object_key}")
            except Exception as exc:
                logger.warning(f"Failed to delete orphan {object_key}: {exc}")
    
    return orphans
