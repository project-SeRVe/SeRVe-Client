"""
VLA reasoning commands with RAG retrieval support.

Provides Few-Shot and Basic inference modes using local vector DB for
retrieval-augmented generation.
"""
import logging
from pathlib import Path

import click

from .context import CLIContext
from .vector_db import LocalVectorDB

logger = logging.getLogger(__name__)


@click.group()
def reasoning():
    """VLA 추론"""
    pass


@reasoning.command(name="few-shot")
@click.argument('team-id')
@click.argument('robot')
@click.argument('text')
@click.option('--k', type=int, default=5, help='Number of similar demos to retrieve')
@click.option('--vector-db-root', type=click.Path(), default=None,
              help='Vector DB root directory (default: ~/.serve/vector_db)')
def few_shot(team_id: str, robot: str, text: str, k: int, vector_db_root: str):
    """
    Few-Shot 추론: 비슷한 데모를 참고하여 VLA 추론.
    
    Uses RAG (Retrieval-Augmented Generation) to find similar demonstrations
    from the local vector DB and use them as context for VLA inference.
    
    \b
    TEAM_ID: Team identifier (vector DB namespace)
    ROBOT: Robot identifier
    TEXT: Task description for inference
    
    \b
    Examples:
        # Few-shot inference with 5 similar demos
        serve reasoning few-shot my-team-id franka "pick up the red cube"
        
        # Use more demos for context
        serve reasoning few-shot my-team-id franka "stack blocks" --k 10
    """
    ctx = CLIContext()
    ctx.ensure_authenticated()
    
    click.echo(f"[+] Few-Shot Reasoning on {robot}...")
    click.echo(f"    Team: {team_id}")
    click.echo(f"    Task: {text}")
    click.echo("")
    
    # Load vector DB
    try:
        vdb_root = Path(vector_db_root) if vector_db_root else None
        vector_db = LocalVectorDB(team_id, vdb_root)
        
        stats = vector_db.get_stats()
        click.echo(f"Loaded vector DB:")
        click.echo(f"  - Episodes: {stats['num_episodes']}")
        click.echo(f"  - Vectors: {stats['num_vectors']}")
        click.echo(f"  - Embedding dim: {stats['embedding_dim']}")
        click.echo(f"  - Distance: {stats['distance']}")
        click.echo("")
        
    except FileNotFoundError as e:
        click.echo(click.style(f"❌ {e}", fg="red"))
        click.echo(f"\nBuild vector DB first using: serve data build-index {team_id}")
        raise click.Abort()
    except Exception as e:
        click.echo(click.style(f"❌ Failed to load vector DB: {e}", fg="red"))
        logger.exception("Vector DB load error")
        raise click.Abort()
    
    # Search for similar episodes by prompt
    click.echo(f"Searching for {k} similar demonstrations...")
    try:
        results = vector_db.search_by_prompt(text, k=k)
        
        if not results:
            click.echo(click.style("⚠ No relevant demos found", fg="yellow"))
            click.echo("Try building vector DB with more demos or use 'basic' mode")
            raise click.Abort()
        
        click.echo(f"Found {len(results)} relevant demo(s):")
        for idx, result in enumerate(results, 1):
            click.echo(f"{idx}. Episode {result['episode_id']}: {result.get('prompt', 'N/A')}")
            click.echo(f"   Steps: {result.get('num_steps', 'N/A')}")
            click.echo(f"   Path: {result.get('relative_path', 'N/A')}")
        
        click.echo("")
        
    except Exception as e:
        click.echo(click.style(f"❌ Retrieval failed: {e}", fg="red"))
        logger.exception("Retrieval error")
        raise click.Abort()
    
    # TODO: Load demo data and perform VLA inference
    # For now, this is a placeholder showing the workflow
    click.echo(click.style("⚠ VLA inference not yet implemented", fg="yellow"))
    click.echo("")
    click.echo("Next steps for full implementation:")
    click.echo("  1. Load retrieved demo trajectories")
    click.echo("  2. Extract relevant state-action pairs")
    click.echo("  3. Send to VLA model (local or remote)")
    click.echo("  4. Get action predictions")
    click.echo("  5. Return actuation commands")
    click.echo("")
    click.echo("For reference implementation, see:")
    click.echo("  - ricl_openpi_libero/src/openpi/policies/retrieval_store.py")
    click.echo("  - ricl_openpi_libero/scripts/serve_policy_ricl.py")


@reasoning.command(name="basic")
@click.argument('robot')
@click.argument('text')
def basic(robot: str, text: str):
    """
    Basic 추론: VLA 모델만으로 추론 (RAG 없이).
    
    Performs VLA inference without retrieval context. Uses only the
    pre-trained model's knowledge.
    
    \b
    ROBOT: Robot identifier
    TEXT: Task description for inference
    
    \b
    Examples:
        # Basic inference
        serve reasoning basic franka "pick up the object"
    """
    ctx = CLIContext()
    ctx.ensure_authenticated()
    
    click.echo(f"[+] Basic Reasoning on {robot}...")
    click.echo(f"    Task: {text}")
    click.echo("")
    
    # TODO: Perform VLA inference without retrieval
    # For now, this is a placeholder
    click.echo(click.style("⚠ VLA inference not yet implemented", fg="yellow"))
    click.echo("")
    click.echo("Next steps for full implementation:")
    click.echo("  1. Load VLA model (local or remote)")
    click.echo("  2. Encode task text")
    click.echo("  3. Get action predictions")
    click.echo("  4. Return actuation commands")
    click.echo("")
    click.echo("For reference implementation, see:")
    click.echo("  - ricl_openpi_libero/scripts/serve_policy_ricl.py")


@reasoning.command(name="db-info")
@click.argument('team-id')
@click.option('--vector-db-root', type=click.Path(), default=None,
              help='Vector DB root directory (default: ~/.serve/vector_db)')
def db_info(team_id: str, vector_db_root: str):
    """
    Show vector DB information and statistics.
    
    \b
    TEAM_ID: Team identifier (vector DB namespace)
    
    \b
    Examples:
        # Show DB info
        serve reasoning db-info my-team-id
    """
    try:
        vdb_root = Path(vector_db_root) if vector_db_root else None
        vector_db = LocalVectorDB(team_id, vdb_root)
        
        stats = vector_db.get_stats()
        
        click.echo("=" * 60)
        click.echo(f"Vector DB Information: {team_id}")
        click.echo("=" * 60)
        click.echo(f"Episodes:      {stats['num_episodes']}")
        click.echo(f"Vectors:       {stats['num_vectors']}")
        click.echo(f"Embedding Dim: {stats['embedding_dim']}")
        click.echo(f"Distance:      {stats['distance']}")
        click.echo("")
        
        # Show episode list
        click.echo("Episodes:")
        episodes = vector_db.search_by_prompt("", k=10)  # Get first 10 episodes
        for ep in episodes:
            click.echo(f"  {ep['episode_id']}: {ep.get('prompt', 'N/A')}")
            click.echo(f"     Steps: {ep['num_steps']}, Path: {ep['relative_path']}")
        
    except FileNotFoundError as e:
        click.echo(click.style(f"❌ {e}", fg="red"))
        raise click.Abort()
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg="red"))
        logger.exception("DB info error")
        raise click.Abort()
