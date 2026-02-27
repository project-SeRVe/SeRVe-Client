"""
Validation command for processed_demo.npz files.

Validates that NPZ files conform to the canonical data contract required by
SeRVe-Client's vector DB and VLA inference pipeline.
"""
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict

import click
import numpy as np

logger = logging.getLogger(__name__)

REQUIRED_KEYS = (
    "state",
    "actions",
    "base_image",
    "wrist_image",
    "base_image_embeddings",
    "wrist_image_embeddings",
    "prompt",
)


def _normalize_prompt(value) -> Optional[str]:
    """
    Normalize prompt value from NPZ file to string.
    
    Args:
        value: Prompt value (can be ndarray, bytes, or str)
    
    Returns:
        Normalized string or None if invalid
    """
    if isinstance(value, np.ndarray):
        if value.shape == ():
            value = value.item()
        elif value.size == 1:
            value = value.reshape(()).item()
        else:
            return None
    
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    
    if not isinstance(value, str):
        return None
    
    value = value.strip()
    return value if value else None


def validate_one(npz_path: Path, expected_embed_dim: Optional[int] = None) -> Dict:
    """
    Validate a single processed_demo.npz file.
    
    Args:
        npz_path: Path to processed_demo.npz file
        expected_embed_dim: Expected embedding dimension (optional)
    
    Returns:
        Validation result dictionary with keys:
        - file: str - Path to file
        - ok: bool - Whether validation passed
        - errors: List[str] - List of error messages
        - num_steps: int - Number of timesteps (if valid)
        - embed_dim: int - Embedding dimension (if valid)
    """
    result = {"file": str(npz_path), "ok": True, "errors": []}
    
    # Try to load NPZ file
    try:
        data = np.load(npz_path, allow_pickle=True)
    except Exception as exc:
        result["ok"] = False
        result["errors"].append(f"failed_to_load: {exc}")
        return result
    
    # Check for missing keys
    missing = [k for k in REQUIRED_KEYS if k not in data.files]
    if missing:
        result["ok"] = False
        result["errors"].append(f"missing_keys: {missing}")
        return result
    
    # Load all arrays
    state = data["state"]
    actions = data["actions"]
    base_image = data["base_image"]
    wrist_image = data["wrist_image"]
    base_emb = data["base_image_embeddings"]
    wrist_emb = data["wrist_image_embeddings"]
    prompt = _normalize_prompt(data["prompt"])
    
    # Validate state shape: (T, 8)
    if state.ndim != 2 or state.shape[1] != 8:
        result["ok"] = False
        result["errors"].append(f"state_shape_invalid: {state.shape}")
    
    # Validate actions shape: (T, 7)
    if actions.ndim != 2 or actions.shape[1] != 7:
        result["ok"] = False
        result["errors"].append(f"actions_shape_invalid: {actions.shape}")
    
    # Validate base_image shape: (T, 224, 224, 3)
    if base_image.ndim != 4 or tuple(base_image.shape[1:]) != (224, 224, 3):
        result["ok"] = False
        result["errors"].append(f"base_image_shape_invalid: {base_image.shape}")
    
    # Validate wrist_image shape: (T, 224, 224, 3)
    if wrist_image.ndim != 4 or tuple(wrist_image.shape[1:]) != (224, 224, 3):
        result["ok"] = False
        result["errors"].append(f"wrist_image_shape_invalid: {wrist_image.shape}")
    
    # Validate embedding shapes: (T, D)
    if base_emb.ndim != 2:
        result["ok"] = False
        result["errors"].append(f"base_emb_shape_invalid: {base_emb.shape}")
    
    if wrist_emb.ndim != 2:
        result["ok"] = False
        result["errors"].append(f"wrist_emb_shape_invalid: {wrist_emb.shape}")
    
    # Check embedding dimension consistency
    if base_emb.ndim == 2 and wrist_emb.ndim == 2 and base_emb.shape[1] != wrist_emb.shape[1]:
        result["ok"] = False
        result["errors"].append(f"embedding_dim_mismatch: {base_emb.shape[1]} vs {wrist_emb.shape[1]}")
    
    # Check expected embedding dimension if provided
    if expected_embed_dim is not None:
        if base_emb.ndim == 2 and base_emb.shape[1] != expected_embed_dim:
            result["ok"] = False
            result["errors"].append(f"base_embed_dim_invalid: expected={expected_embed_dim} got={base_emb.shape[1]}")
        if wrist_emb.ndim == 2 and wrist_emb.shape[1] != expected_embed_dim:
            result["ok"] = False
            result["errors"].append(f"wrist_embed_dim_invalid: expected={expected_embed_dim} got={wrist_emb.shape[1]}")
    
    # Check time dimension consistency across all arrays
    lengths = []
    for arr in (state, actions, base_image, wrist_image, base_emb, wrist_emb):
        if arr.ndim >= 1:
            lengths.append(arr.shape[0])
    
    if lengths and len(set(lengths)) != 1:
        result["ok"] = False
        result["errors"].append(f"time_length_mismatch: {lengths}")
    
    # Validate prompt
    if prompt is None:
        result["ok"] = False
        result["errors"].append("prompt_invalid")
    
    # Add metadata
    result["num_steps"] = int(lengths[0]) if lengths else 0
    result["embed_dim"] = int(base_emb.shape[1]) if base_emb.ndim == 2 else None
    
    return result


def find_npz_files(root: Path) -> List[Path]:
    """
    Find all processed_demo.npz files in directory tree.
    
    Args:
        root: Root path (file or directory)
    
    Returns:
        List of paths to processed_demo.npz files
    """
    if root.is_file() and root.name == "processed_demo.npz":
        return [root]
    return sorted(root.rglob("processed_demo.npz"))


@click.command(name='validate')
@click.argument('path', type=click.Path(exists=True))
@click.option('--embed-dim', type=int, default=None, help='Expected embedding dimension (default: any)')
@click.option('--report-json', type=click.Path(), help='Save validation report to JSON file')
@click.option('--allow-fail', is_flag=True, help='Exit with code 0 even if validation fails')
@click.option('--verbose', is_flag=True, help='Show all validation results (not just failures)')
def validate_command(
    path: str,
    embed_dim: Optional[int],
    report_json: Optional[str],
    allow_fail: bool,
    verbose: bool,
):
    """
    Validate processed_demo.npz files against canonical data contract.
    
    PATH: Path to processed_demo.npz file or directory containing demos
    
    \b
    Validates:
    - All required keys present
    - state: (T, 8) - joint positions + gripper
    - actions: (T, 7) - joint velocities + gripper
    - base_image: (T, 224, 224, 3) - RGB base camera
    - wrist_image: (T, 224, 224, 3) - RGB wrist camera
    - base_image_embeddings: (T, D) - DINOv2 embeddings
    - wrist_image_embeddings: (T, D) - DINOv2 embeddings
    - prompt: string - task description
    - Time dimension consistency across all arrays
    
    \b
    Examples:
        # Validate single file
        serve data validate ./demo_0/processed_demo.npz
        
        # Validate all demos in directory
        serve data validate ./scenario_1
        
        # Validate with expected embedding dimension
        serve data validate ./scenario_1 --embed-dim 49152
        
        # Generate JSON report
        serve data validate ./all_scenarios --report-json validation_report.json
        
        # Show all results (not just failures)
        serve data validate ./scenario_1 --verbose
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    root = Path(path).resolve()
    files = find_npz_files(root)
    
    if not files:
        click.echo(click.style(f"❌ No processed_demo.npz found in: {root}", fg="red"))
        raise click.Abort()
    
    click.echo(f"Found {len(files)} processed_demo.npz file(s) in {root}")
    click.echo("")
    
    # Validate all files
    results = []
    with click.progressbar(files, label="Validating demos") as bar:
        for npz_path in bar:
            result = validate_one(npz_path, embed_dim)
            results.append(result)
    
    # Compute summary
    failed = [r for r in results if not r["ok"]]
    passed = len(results) - len(failed)
    
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"Validation Summary: {passed} passed, {len(failed)} failed")
    click.echo("=" * 60)
    
    # Show detailed results
    if verbose:
        # Show all results
        for result in results:
            if result["ok"]:
                click.echo(click.style(f"✓ {result['file']}", fg="green"))
                click.echo(f"  Steps: {result['num_steps']}, Embed Dim: {result['embed_dim']}")
            else:
                click.echo(click.style(f"✗ {result['file']}", fg="red"))
                for error in result["errors"]:
                    click.echo(f"  - {error}")
    else:
        # Show only failures
        if failed:
            click.echo("")
            click.echo(click.style("Failed validations:", fg="red", bold=True))
            for result in failed[:20]:  # Limit to first 20 failures
                click.echo(click.style(f"✗ {result['file']}", fg="red"))
                for error in result["errors"]:
                    click.echo(f"  - {error}")
            
            if len(failed) > 20:
                click.echo(f"... and {len(failed) - 20} more failures")
        else:
            click.echo("")
            click.echo(click.style("✓ All demos passed validation!", fg="green", bold=True))
    
    # Save JSON report if requested
    if report_json:
        report_path = Path(report_json).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "root": str(root),
            "total": len(results),
            "passed": passed,
            "failed": len(failed),
            "results": results,
        }
        
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        click.echo("")
        click.echo(f"Saved validation report: {report_path}")
    
    # Exit with appropriate code
    if failed and not allow_fail:
        click.echo("")
        click.echo(click.style(f"Validation failed: {len(failed)} demo(s) have errors", fg="red"))
        raise click.Abort()
