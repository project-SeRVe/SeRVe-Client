"""
Build local Qdrant vector DB from approved demos.

Creates Qdrant collection with embeddings and metadata for RAG-based
VLA inference. The vector DB is stored locally in ~/.serve/qdrant/
"""
import logging
from pathlib import Path
from typing import List

import click
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from serve_sdk.local_db import get_default_db

logger = logging.getLogger(__name__)


def find_episode_dirs(root: Path) -> List[Path]:
    """
    Find all episode directories containing processed_demo.npz.
    
    Args:
        root: Root directory to search
    
    Returns:
        List of episode directory paths
    """
    return sorted({p.parent for p in root.rglob("processed_demo.npz")})


def to_prompt(value) -> str:
    """
    Extract prompt string from NPZ value.
    
    Args:
        value: Prompt value (can be ndarray, bytes, or str)
    
    Returns:
        Prompt string (empty if invalid)
    """
    if isinstance(value, np.ndarray):
        if value.shape == ():
            value = value.item()
        elif value.size == 1:
            value = value.reshape(()).item()
    
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    
    if not isinstance(value, str):
        return ""
    
    return value


@click.command(name='build-index')
@click.argument('team-id')
@click.option('--overwrite', is_flag=True, help='Overwrite existing Qdrant collection')
@click.option('--embedding-key', default='base_image_embeddings',
              help='Which embedding key to use (default: base_image_embeddings)')
def build_index_command(
    team_id: str,
    overwrite: bool,
    embedding_key: str,
):
    """
    Build local Qdrant vector DB from approved demos (queried from local.db).
    
    TEAM_ID: Team identifier for Qdrant collection namespace
    
    \b
    Output:
        Qdrant collection 'team_{team_id}' in ~/.serve/qdrant/
        Contains vectors with rich metadata (episode_id, step_index, prompt, etc.)
    
    \b
    Examples:
        # Build vector DB from approved demos in local.db
        serve data build-index my-team-id
        
        # Rebuild existing vector DB
        serve data build-index my-team-id --overwrite
        
        # Use wrist camera embeddings instead of base camera
        serve data build-index my-team-id --embedding-key wrist_image_embeddings
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Query local.db for approved artifacts
    try:
        db = get_default_db()
        approved_artifacts = db.get_artifacts_by_status("approved", kind="processed")
        db.close()
    except Exception as exc:
        click.echo(click.style(f"❌ Failed to query local.db: {exc}", fg="red"))
        raise click.Abort()
    
    if not approved_artifacts:
        click.echo(click.style("❌ No approved artifacts found in local.db", fg="red"))
        click.echo("\nTip: Approve demos first using: serve data review")
        raise click.Abort()
    
    # Initialize Qdrant client
    home = Path.home()
    qdrant_root = home / ".serve" / "qdrant"
    qdrant_root.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_root))
    
    collection_name = f"team_{team_id}"
    
    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [col.name for col in collections]
    
    if collection_name in collection_names:
        if not overwrite:
            click.echo(click.style(f"❌ Qdrant collection '{collection_name}' already exists", fg="red"))
            click.echo("Use --overwrite to rebuild")
            raise click.Abort()
        click.echo(f"Deleting existing collection: {collection_name}")
        client.delete_collection(collection_name)
    
    click.echo(f"Building Qdrant vector DB from {len(approved_artifacts)} approved artifact(s)...")
    click.echo(f"Collection: {collection_name}")
    click.echo(f"Embedding key: {embedding_key}")
    click.echo("")
    
    # Collect all embeddings and metadata
    all_points = []
    point_id = 0
    episodes_processed = 0
    embedding_dim = None
    
    with click.progressbar(enumerate(approved_artifacts), length=len(approved_artifacts),
                          label="Processing artifacts") as bar:
        for artifact_idx, artifact in bar:
            artifact_id = artifact["artifact_id"]
            local_path = artifact["local_path"]
            object_key = artifact["object_key"]
            demo_id = artifact["demo_id"]
            num_steps = artifact["num_steps"]
            state_dim = artifact["state_dim"]
            action_dim = artifact["action_dim"]
            prompt_text = artifact["prompt_text"]
            
            npz_path = Path(local_path)
            
            try:
                data = np.load(npz_path, allow_pickle=True)
            except Exception as exc:
                click.echo(click.style(f"\n✗ Failed to load {npz_path}: {exc}", fg="red"))
                continue
            
            # Validate required keys
            required_keys = [embedding_key, "state", "actions", "prompt"]
            missing = [k for k in required_keys if k not in data.files]
            if missing:
                click.echo(click.style(f"\n✗ Missing keys in {npz_path}: {missing}", fg="red"))
                continue
            
            # Extract embeddings
            emb = np.asarray(data[embedding_key], dtype=np.float32)
            if emb.ndim != 2:
                click.echo(click.style(f"\n✗ Invalid embeddings shape in {npz_path}: {emb.shape}", fg="red"))
                continue
            
            num_steps_actual = emb.shape[0]
            if embedding_dim is None:
                embedding_dim = emb.shape[1]
            elif embedding_dim != emb.shape[1]:
                click.echo(click.style(f"\n✗ Embedding dimension mismatch in {npz_path}: expected {embedding_dim}, got {emb.shape[1]}", fg="red"))
                continue
            
            # Use prompt from file (fallback to DB)
            prompt = to_prompt(data["prompt"])
            if not prompt:
                prompt = prompt_text
            
            # Create points for each step
            for step_idx in range(num_steps_actual):
                vector = emb[step_idx].tolist()
                payload = {
                    "demo_id": demo_id,
                    "artifact_id": artifact_id,
                    "object_key": object_key,
                    "step_index": step_idx,
                    "num_steps": num_steps_actual,
                    "state_dim": state_dim,
                    "action_dim": action_dim,
                    "prompt": prompt,
                }
                
                all_points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                ))
                point_id += 1
            
            episodes_processed += 1
    if not all_points:
        click.echo(click.style("❌ No valid embeddings found", fg="red"))
        raise click.Abort()
    
    click.echo("")
    click.echo(f"Collected {len(all_points)} vectors from {episodes_processed} episodes")
    click.echo(f"Embedding dimension: {embedding_dim}")
    
    # Create Qdrant collection
    click.echo(f"\nCreating Qdrant collection: {collection_name}...")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
    )
    
    # Upload points in batches
    click.echo("Uploading vectors to Qdrant...")
    batch_size = 100
    
    with click.progressbar(range(0, len(all_points), batch_size),
                          label="Uploading batches") as bar:
        for i in bar:
            batch = all_points[i:i + batch_size]
            client.upsert(
                collection_name=collection_name,
                points=batch,
            )
    
    click.echo("")
    click.echo(click.style("✓ Qdrant vector DB built successfully!", fg="green", bold=True))
    click.echo(f"Collection: {collection_name}")
    click.echo(f"Location: {qdrant_root}")
    click.echo(f"Vectors: {len(all_points)}")
    click.echo(f"Episodes: {episodes_processed}")
    click.echo(f"Embedding dim: {embedding_dim}")
