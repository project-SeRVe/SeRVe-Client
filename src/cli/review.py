"""
Manual review command for processed demos (O/X routing).

Allows manual inspection and approval/rejection of processed_demo.npz files
before uploading to the server or building into the vector DB.
"""
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List

import click

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


def read_optional_json(path: Path) -> Optional[Dict]:
    """
    Read JSON file, return None if not found or invalid.
    
    Args:
        path: Path to JSON file
    
    Returns:
        Parsed JSON dict or None
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def move_episode(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> None:
    """
    Move episode directory from source to destination.
    
    Args:
        src: Source episode directory
        dst: Destination path
        overwrite: Whether to overwrite existing destination
        dry_run: If True, don't actually move
    
    Raises:
        FileExistsError: If destination exists and overwrite=False
    """
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        if not dry_run:
            shutil.rmtree(dst)
    
    if dry_run:
        return
    
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def append_log(log_path: Path, row: Dict, dry_run: bool) -> None:
    """
    Append review decision to JSONL log file.
    
    Args:
        log_path: Path to log file
        row: Review record dictionary
        dry_run: If True, don't actually write
    """
    if dry_run:
        return
    
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_review_record(
    reviewer: str,
    decision: str,
    reason: str,
    source: Path,
    target: Path,
    rel_path: Path,
    episode_meta: Optional[Dict],
) -> Dict:
    """
    Build review record for logging.
    
    Args:
        reviewer: Reviewer name
        decision: "approved" or "rejected"
        reason: Reason for decision
        source: Source episode path
        target: Target episode path
        rel_path: Relative episode path
        episode_meta: Episode metadata dict
    
    Returns:
        Review record dictionary
    """
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": reviewer,
        "decision": decision,
        "reason": reason,
        "source": str(source),
        "target": str(target),
        "relative_episode_path": str(rel_path),
        "episode_meta": episode_meta,
    }


@click.command(name='review')
@click.option('--pending-root', type=click.Path(exists=True), default='runtime_demos/pending',
              help='Directory containing pending demos')
@click.option('--approved-root', type=click.Path(), default='runtime_demos/approved',
              help='Directory for approved demos')
@click.option('--rejected-root', type=click.Path(), default='runtime_demos/rejected',
              help='Directory for rejected demos')
@click.option('--log-path', type=click.Path(), default='runtime_demos/review_log.jsonl',
              help='Path to review log file')
@click.option('--reviewer', default=None, help='Reviewer name (default: $USER)')
@click.option('--reason-required', is_flag=True, help='Require reason for all decisions')
@click.option('--overwrite', is_flag=True, help='Overwrite existing approved/rejected demos')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--limit', type=int, default=None, help='Max number of pending episodes to review')
def review_command(
    pending_root: str,
    approved_root: str,
    rejected_root: str,
    log_path: str,
    reviewer: Optional[str],
    reason_required: bool,
    overwrite: bool,
    dry_run: bool,
    limit: Optional[int],
):
    """
    Manual O/X review loop for processed demos.
    
    Allows manual inspection and approval/rejection of processed_demo.npz files.
    Approved demos can be uploaded or used for vector DB building.
    Rejected demos are archived separately.
    
    \b
    Decision keys:
        [o] approve - Move to approved directory
        [x] reject - Move to rejected directory
        [s] skip - Skip this demo (leave in pending)
        [q] quit - Exit review loop
    
    \b
    Examples:
        # Review pending demos
        serve data review --pending-root ./runtime_demos/pending
        
        # Review with required reasons
        serve data review --reason-required
        
        # Dry run to see what would happen
        serve data review --dry-run
        
        # Review only first 10 demos
        serve data review --limit 10
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Resolve paths
    pending_path = Path(pending_root).resolve()
    approved_path = Path(approved_root).resolve()
    rejected_path = Path(rejected_root).resolve()
    log_file = Path(log_path).resolve()
    
    # Get reviewer name
    if reviewer is None:
        reviewer = os.environ.get("USER", "unknown")
    
    # Validate pending root exists
    if not pending_path.exists():
        click.echo(click.style(f"❌ Pending root does not exist: {pending_path}", fg="red"))
        raise click.Abort()
    
    # Find pending episodes
    episode_dirs = find_episode_dirs(pending_path)
    if limit is not None:
        episode_dirs = episode_dirs[:limit]
    
    if not episode_dirs:
        click.echo("No pending episodes to review.")
        return
    
    click.echo(f"Found {len(episode_dirs)} pending episode(s) in {pending_path}")
    click.echo("")
    click.echo("Decision keys: [o] approve, [x] reject, [s] skip, [q] quit")
    click.echo(f"Reviewer: {reviewer}")
    if dry_run:
        click.echo(click.style("DRY RUN MODE - No changes will be made", fg="yellow", bold=True))
    click.echo("")
    
    # Review loop
    for idx, episode_dir in enumerate(episode_dirs, start=1):
        rel_path = episode_dir.relative_to(pending_path)
        meta = read_optional_json(episode_dir / "episode_meta.json")
        
        # Extract metadata
        num_steps = meta.get("num_steps") if isinstance(meta, dict) else None
        prompt = None
        if isinstance(meta, dict):
            prompt = meta.get("task_description") or meta.get("prompt")
        
        # Display episode info
        click.echo(f"[{idx}/{len(episode_dirs)}] {rel_path}")
        if num_steps is not None:
            click.echo(f"  Steps: {num_steps}")
        if prompt:
            click.echo(f"  Prompt: {prompt}")
        
        # Check for processed_demo.npz
        npz_file = episode_dir / "processed_demo.npz"
        if npz_file.exists():
            size_mb = npz_file.stat().st_size / (1024 * 1024)
            click.echo(f"  NPZ size: {size_mb:.2f} MB")
        else:
            click.echo(click.style("  ⚠ processed_demo.npz not found!", fg="yellow"))
        
        # Decision loop
        while True:
            decision_input = click.prompt(
                "Decision (o=approve, x=reject, s=skip, q=quit)",
                type=str,
                default="s"
            ).strip().lower()
            
            if decision_input not in {"o", "x", "s", "q"}:
                click.echo(click.style("Invalid input. Use one of: o, x, s, q", fg="red"))
                continue
            
            # Handle skip and quit
            if decision_input in {"s", "q"}:
                break
            
            # Get reason
            reason = click.prompt("Reason (optional)", type=str, default="").strip()
            if reason_required and not reason:
                click.echo(click.style("Reason is required", fg="red"))
                continue
            
            # Determine target
            decision = "approved" if decision_input == "o" else "rejected"
            target_root = approved_path if decision == "approved" else rejected_path
            target_dir = target_root / rel_path
            
            # Move episode
            try:
                move_episode(episode_dir, target_dir, overwrite=overwrite, dry_run=dry_run)
                
                # Log decision
                record = build_review_record(
                    reviewer=reviewer,
                    decision=decision,
                    reason=reason,
                    source=episode_dir,
                    target=target_dir,
                    rel_path=rel_path,
                    episode_meta=meta,
                )
                append_log(log_file, record, dry_run=dry_run)
                
                # Display result
                status_color = "green" if decision == "approved" else "yellow"
                action_text = "Would move" if dry_run else "Moved"
                click.echo(click.style(f"  ✓ {action_text} → {decision}: {target_dir}", fg=status_color))
                break
                
            except FileExistsError as e:
                click.echo(click.style(f"  ✗ {e}", fg="red"))
                click.echo("  Use --overwrite to replace existing demos")
                continue
            except Exception as e:
                click.echo(click.style(f"  ✗ Error: {e}", fg="red"))
                logger.exception("Failed to move episode")
                break
        
        # Handle quit
        if decision_input == "q":
            click.echo("\nQuit requested.")
            break
        
        click.echo("")
    
    click.echo("Review complete.")
    if not dry_run:
        click.echo(f"Review log: {log_file}")
