"""
Build local vector DB from approved demos.

Creates vector DB artifacts (embeddings, episode metadata) for RAG-based
VLA inference. The vector DB is stored locally in ~/.serve/vector_db/<team_id>/
"""
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import click
import numpy as np

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


def maybe_build_faiss(embeddings: np.ndarray, out_dir: Path) -> bool:
    """
    Build FAISS index if faiss is available.
    
    Args:
        embeddings: Embeddings array (N, D)
        out_dir: Output directory
    
    Returns:
        True if FAISS index was built, False otherwise
    """
    try:
        import faiss
    except ImportError:
        logger.warning("faiss not available; skipping FAISS index build")
        return False
    except Exception as exc:
        logger.warning(f"faiss import error; skipping FAISS index build: {exc}")
        return False
    
    try:
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings.astype(np.float32, copy=False))
        faiss.write_index(index, str(out_dir / "index.faiss"))
        logger.info("FAISS index built successfully")
        return True
    except Exception as exc:
        logger.error(f"Failed to build FAISS index: {exc}")
        return False


@click.command(name='build-index')
@click.argument('team-id')
@click.option('--approved-root', type=click.Path(exists=True), default=None,
              help='Directory containing approved demos (default: ~/.serve/approved/<team-id>)')
@click.option('--output-root', type=click.Path(), default=None,
              help='Output directory for vector DB (default: ~/.serve/vector_db)')
@click.option('--overwrite', is_flag=True, help='Overwrite existing vector DB')
@click.option('--write-faiss', is_flag=True, help='Build FAISS index (requires faiss-cpu or faiss-gpu)')
@click.option('--embedding-key', default='base_image_embeddings',
              help='Which embedding key to use (default: base_image_embeddings)')
def build_index_command(
    team_id: str,
    approved_root: str,
    output_root: str,
    overwrite: bool,
    write_faiss: bool,
    embedding_key: str,
):
    """
    Build local vector DB from approved demos for RAG-based inference.
    
    TEAM_ID: Team identifier for vector DB namespace
    
    \b
    Output structure:
        ~/.serve/vector_db/<team-id>/
        ├── vectors.npz           # Embeddings + metadata
        │   ├── embeddings        # (N, D) float32 array
        │   ├── episode_ids       # (N,) int32 array
        │   └── step_indices      # (N,) int32 array
        ├── episodes.json         # Episode metadata
        ├── summary.json          # Vector DB metadata
        └── index.faiss           # Optional FAISS index
    
    \b
    Examples:
        # Build vector DB from default approved directory
        serve data build-index my-team-id
        
        # Build from custom approved directory
        serve data build-index my-team-id --approved-root ./runtime_demos/approved
        
        # Rebuild existing vector DB
        serve data build-index my-team-id --overwrite
        
        # Build with FAISS index for faster retrieval
        serve data build-index my-team-id --write-faiss
        
        # Use wrist camera embeddings instead of base camera
        serve data build-index my-team-id --embedding-key wrist_image_embeddings
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Resolve paths
    home = Path.home()
    
    if approved_root is None:
        approved_path = home / ".serve" / "approved" / team_id
    else:
        approved_path = Path(approved_root).resolve()
    
    if output_root is None:
        output_path = home / ".serve" / "vector_db" / team_id
    else:
        output_path = Path(output_root).resolve() / team_id
    
    # Validate approved root exists
    if not approved_path.exists():
        click.echo(click.style(f"❌ Approved root does not exist: {approved_path}", fg="red"))
        click.echo(f"\nTip: Approve demos first using: serve data review --approved-root {approved_path.parent}")
        raise click.Abort()
    
    # Check if output exists
    if output_path.exists():
        if not overwrite:
            click.echo(click.style(f"❌ Vector DB already exists: {output_path}", fg="red"))
            click.echo("Use --overwrite to rebuild")
            raise click.Abort()
        shutil.rmtree(output_path)
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find approved episodes
    episode_dirs = find_episode_dirs(approved_path)
    if not episode_dirs:
        click.echo(click.style(f"❌ No approved episodes found in {approved_path}", fg="red"))
        click.echo("\nTip: Approve demos first using: serve data review")
        raise click.Abort()
    
    click.echo(f"Building vector DB from {len(episode_dirs)} approved episode(s)...")
    click.echo(f"Approved root: {approved_path}")
    click.echo(f"Output: {output_path}")
    click.echo(f"Embedding key: {embedding_key}")
    click.echo("")
    
    # Build vector DB
    all_embeddings: List[np.ndarray] = []
    all_episode_ids: List[np.ndarray] = []
    all_step_indices: List[np.ndarray] = []
    episodes_meta: List[Dict] = []
    
    with click.progressbar(enumerate(episode_dirs), length=len(episode_dirs),
                          label="Processing episodes") as bar:
        for ep_id, ep_dir in bar:
            npz_path = ep_dir / "processed_demo.npz"
            
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
            
            num_steps = emb.shape[0]
            all_embeddings.append(emb)
            all_episode_ids.append(np.full((num_steps,), ep_id, dtype=np.int32))
            all_step_indices.append(np.arange(num_steps, dtype=np.int32))
            
            # Build episode metadata
            rel_path = ep_dir.relative_to(approved_path)
            episodes_meta.append({
                "episode_id": ep_id,
                "relative_path": str(rel_path),
                "processed_demo_path": str(npz_path.resolve()),
                "num_steps": int(num_steps),
                "state_dim": int(np.asarray(data["state"]).shape[1]),
                "action_dim": int(np.asarray(data["actions"]).shape[1]),
                "prompt": to_prompt(data["prompt"]),
            })
    
    if not all_embeddings:
        click.echo(click.style("❌ No valid embeddings found", fg="red"))
        raise click.Abort()
    
    # Concatenate all arrays
    embeddings = np.concatenate(all_embeddings, axis=0)
    episode_ids = np.concatenate(all_episode_ids, axis=0)
    step_indices = np.concatenate(all_step_indices, axis=0)
    
    click.echo("")
    click.echo(f"Collected {embeddings.shape[0]} vectors from {len(episodes_meta)} episodes")
    click.echo(f"Embedding dimension: {embeddings.shape[1]}")
    
    # Save vectors.npz
    click.echo("\nSaving vectors.npz...")
    np.savez_compressed(
        output_path / "vectors.npz",
        embeddings=embeddings,
        episode_ids=episode_ids,
        step_indices=step_indices,
    )
    
    # Save episodes.json
    click.echo("Saving episodes.json...")
    (output_path / "episodes.json").write_text(
        json.dumps(episodes_meta, indent=2),
        encoding="utf-8"
    )
    
    # Build summary
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "team_id": team_id,
        "approved_root": str(approved_path),
        "num_episodes": len(episodes_meta),
        "num_vectors": int(embeddings.shape[0]),
        "embedding_dim": int(embeddings.shape[1]),
        "embedding_key": embedding_key,
        "files": ["vectors.npz", "episodes.json"],
    }
    
    # Build FAISS index if requested
    if write_faiss:
        click.echo("Building FAISS index...")
        faiss_ok = maybe_build_faiss(embeddings, output_path)
        summary["faiss_index_built"] = bool(faiss_ok)
        if faiss_ok:
            summary["files"].append("index.faiss")
    
    # Save summary.json
    click.echo("Saving summary.json...")
    (output_path / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8"
    )
    
    click.echo("")
    click.echo(click.style("✓ Vector DB built successfully!", fg="green", bold=True))
    click.echo(f"Location: {output_path}")
    click.echo(f"Vectors: {embeddings.shape[0]}")
    click.echo(f"Episodes: {len(episodes_meta)}")
    click.echo(f"Embedding dim: {embeddings.shape[1]}")
    
    if write_faiss and summary.get("faiss_index_built"):
        click.echo(click.style("✓ FAISS index built", fg="green"))
    elif write_faiss:
        click.echo(click.style("⚠ FAISS index not built (faiss not available)", fg="yellow"))
