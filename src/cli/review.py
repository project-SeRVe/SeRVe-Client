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
@click.option('--log-path', type=click.Path(), default='runtime_demos/review_log.jsonl',
              help='Path to review log file')
@click.option('--reviewer', default=None, help='Reviewer name (default: $USER)')
@click.option('--reason-required', is_flag=True, help='Require reason for all decisions')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--limit', type=int, default=None, help='Max number of pending episodes to review')
@click.option('--status', type=click.Choice(['pending', 'approved', 'rejected']), default='pending',
              help='Status of demos to review (default: pending)')
def review_command(
    log_path: str,
    reviewer: Optional[str],
    reason_required: bool,
    dry_run: bool,
    limit: Optional[int],
    status: str,
):
    """
    Manual O/X review loop for demos from local.db.
    
    Queries local.db for demos by status (pending/approved/rejected).
    Updates demo status in database - no file movements.
    
    \b
    Decision keys:
        [o] approve - Mark as approved in local.db
        [x] reject - Mark as rejected in local.db
        [s] skip - Skip this demo (no change)
        [q] quit - Exit review loop
    
    \b
    Examples:
        # Review pending demos
        serve data review
        
        # Review approved demos (for re-review)
        serve data review --status approved
        
        # Review with required reasons
        serve data review --reason-required
        
        # Dry run to see what would happen
        serve data review --dry-run
        
        # Review only first 10 demos
        serve data review --limit 10
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Get reviewer name
    if reviewer is None:
        reviewer = os.environ.get("USER", "unknown")
    
    # Query local.db for demos by status
    try:
        db = get_default_db()
        # Get artifacts with matching demo status
        cursor = db.conn.execute(
            """
            SELECT a.artifact_id, a.local_path, a.object_key, d.demo_id, d.status, d.num_steps, s.prompt_text
            FROM artifact a
            JOIN demo d ON a.demo_id = d.demo_id
            JOIN scenario s ON d.scenario_id = s.scenario_id
            WHERE d.status = ? AND a.kind = 'processed'
            ORDER BY d.created_at DESC
            """,
            (status,)
        )
        rows = cursor.fetchall()
        if limit is not None:
            rows = rows[:limit]
        db.close()
    except Exception as exc:
        click.echo(click.style(f"❌ Failed to query local.db: {exc}", fg="red"))
        raise click.Abort()
    
    if not rows:
        click.echo(f"No {status} demos to review.")
        return
    
    log_file = Path(log_path).resolve()
    
    click.echo(f"Found {len(rows)} {status} demo(s)")
    click.echo("")
    click.echo("Decision keys: [o] approve, [x] reject, [s] skip, [q] quit")
    click.echo(f"Reviewer: {reviewer}")
    if dry_run:
        click.echo(click.style("DRY RUN MODE - No changes will be made", fg="yellow", bold=True))
    click.echo("")
    
    # Review loop
    for idx, row in enumerate(rows, start=1):
        artifact_id = row["artifact_id"]
        local_path = row["local_path"]
        object_key = row["object_key"]
        demo_id = row["demo_id"]
        current_status = row["status"]
        num_steps = row["num_steps"]
        prompt_text = row["prompt_text"]
        
        # Display demo info
        click.echo(f"[{idx}/{len(rows)}] Demo {demo_id}")
        click.echo(f"  Object key: {object_key}")
        click.echo(f"  Status: {current_status}")
        if num_steps is not None:
            click.echo(f"  Steps: {num_steps}")
        if prompt_text:
            click.echo(f"  Prompt: {prompt_text}")
        
        # Check artifact file
        artifact_path = Path(local_path)
        if artifact_path.exists():
            size_mb = artifact_path.stat().st_size / (1024 * 1024)
            click.echo(f"  NPZ size: {size_mb:.2f} MB")
        else:
            click.echo(click.style(f"  ⚠ Artifact file not found: {artifact_path}", fg="yellow"))
        
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
            
            # Determine new status
            new_status = "approved" if decision_input == "o" else "rejected"
            
            # Update local.db status
            if not dry_run:
                try:
                    db = get_default_db()
                    db.update_demo_status(demo_id, new_status)
                    db.close()
                    logger.debug(f"Updated demo {demo_id} status: {current_status} → {new_status}")
                except Exception as exc:
                    click.echo(click.style(f"  ✗ Failed to update local.db: {exc}", fg="red"))
                    logger.exception("Failed to update demo status")
                    break
            
            # Log decision
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reviewer": reviewer,
                "decision": new_status,
                "reason": reason,
                "demo_id": demo_id,
                "artifact_id": artifact_id,
                "object_key": object_key,
                "previous_status": current_status,
            }
            append_log(log_file, record, dry_run=dry_run)
            
            # Display result
            status_color = "green" if new_status == "approved" else "yellow"
            action_text = "Would update" if dry_run else "Updated"
            click.echo(click.style(f"  ✓ {action_text} status: {current_status} → {new_status}", fg=status_color))
            break
        
        # Handle quit
        if decision_input == "q":
            click.echo("\nQuit requested.")
            break
        
        click.echo("")
    
    click.echo("Review complete.")
    if not dry_run:
        click.echo(f"Review log: {log_file}")
