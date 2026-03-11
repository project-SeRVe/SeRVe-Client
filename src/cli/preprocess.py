"""
Robot log preprocessing: raw trajectory data → processed_demo.npz

Ported from ricl_openpi_libero/preprocessing/process_robot_demos_to_libero.py
Converts raw robot logs (trajectory.h5 + camera frames) to the canonical NPZ format
required by SeRVe-Client's vector DB and VLA inference pipeline.
"""
import json
import logging
from pathlib import Path
from typing import Optional, List

import click
import h5py
import numpy as np
from PIL import Image

from .image_utils import resize_with_pad, ensure_uint8_image
from .dinov2_utils import load_dinov2, embed_with_batches, create_placeholder_embeddings, EMBED_DIM
from serve_sdk.local_db import get_default_db
from serve_sdk.artifact_storage import store_artifact

logger = logging.getLogger(__name__)


def _read_prompt(demo_dir: Path, prompts: Optional[List[str]]) -> str:
    """
    Extract task prompt from demo directory.
    Priority: provided prompts > meta.json > parent directory name
    
    Args:
        demo_dir: Path to demo directory
        prompts: Optional list of prompts to randomly choose from
    
    Returns:
        Task prompt string
    """
    if prompts:
        return str(np.random.choice(prompts))
    
    # Try reading from meta.json
    meta_path = demo_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            prompt = meta.get("prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt.strip()
        except Exception as exc:
            logger.warning(f"Failed to read {meta_path}: {exc}")
    
    # Fall back to inferring from directory name
    task_name = demo_dir.parent.name
    parts = task_name.split("_")
    # Handle format like "YYYY-MM-DD_task_description"
    if len(parts) > 1 and parts[0].count("-") == 2:
        return " ".join(parts[1:])
    return task_name.replace("_", " ")


def _find_traj_file(demo_dir: Path) -> Path:
    """
    Find trajectory H5 file in demo directory.
    
    Args:
        demo_dir: Path to demo directory
    
    Returns:
        Path to trajectory.h5 or traj.h5
    
    Raises:
        FileNotFoundError: If no trajectory file found
    """
    for name in ("trajectory.h5", "traj.h5"):
        path = demo_dir / name
        if path.exists():
            return path
    raise FileNotFoundError(f"Trajectory file not found in {demo_dir}")


def _prepare_joint7(joint_positions: np.ndarray) -> np.ndarray:
    """
    Convert joint positions to 7-dim format (pad with zeros if needed).
    
    Args:
        joint_positions: Raw joint positions array
    
    Returns:
        Joint positions array with shape (T, 7)
    """
    arr = np.asarray(joint_positions, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    
    out = np.zeros((arr.shape[0], 7), dtype=np.float32)
    copy_cols = min(arr.shape[1], 7)
    out[:, :copy_cols] = arr[:, :copy_cols]
    return out


def _prepare_gripper1(gripper_position: np.ndarray) -> np.ndarray:
    """
    Convert gripper position to 1-dim format.
    
    Args:
        gripper_position: Raw gripper position array
    
    Returns:
        Gripper position array with shape (T, 1)
    """
    arr = np.asarray(gripper_position, dtype=np.float32)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    if arr.shape[1] == 1:
        return arr
    # Average multiple gripper dimensions
    return np.mean(arr, axis=1, keepdims=True)


def _prepare_action7(joint_velocity: np.ndarray, gripper_position: np.ndarray) -> np.ndarray:
    """
    Prepare action array: 6-dim arm velocity + 1-dim gripper.
    
    Args:
        joint_velocity: Joint velocity array
        gripper_position: Gripper position array
    
    Returns:
        Action array with shape (T, 7)
    
    Raises:
        ValueError: If time dimensions mismatch
    """
    joint = np.asarray(joint_velocity, dtype=np.float32)
    if joint.ndim == 1:
        joint = joint.reshape(-1, 1)
    
    grip = _prepare_gripper1(gripper_position)
    
    if joint.shape[0] != grip.shape[0]:
        raise ValueError(f"Action time mismatch: {joint.shape[0]} vs {grip.shape[0]}")
    
    # Action contract is 7-dim: arm(6) + gripper(1)
    arm6 = np.zeros((joint.shape[0], 6), dtype=np.float32)
    copy_cols = min(joint.shape[1], 6)
    arm6[:, :copy_cols] = joint[:, :copy_cols]
    
    return np.concatenate([arm6, grip[:, :1]], axis=1)


def _load_keep_mask(traj_h5: h5py.File, num_steps: int) -> np.ndarray:
    """
    Load skip_action mask from trajectory file.
    
    Args:
        traj_h5: Open H5 file handle
        num_steps: Total number of steps
    
    Returns:
        Boolean mask indicating which steps to keep
    """
    try:
        skip = traj_h5["observation"]["timestamp"]["skip_action"][:]
        if skip.shape[0] != num_steps:
            logger.warning("skip_action length mismatch. Ignoring skip_action.")
            return np.ones(num_steps, dtype=bool)
        return ~skip.astype(bool)
    except Exception:
        # If skip_action doesn't exist, keep all steps
        return np.ones(num_steps, dtype=bool)


def _list_image_files(frames_dir: Path) -> List[Path]:
    """
    List all image files in directory, sorted by filename.
    
    Args:
        frames_dir: Path to frames directory
    
    Returns:
        Sorted list of image file paths
    """
    files = [p for p in frames_dir.iterdir() if p.is_file()]
    return sorted(files)


def _load_camera_frames(
    demo_dir: Path,
    camera_name: str,
    keep_mask: np.ndarray,
    num_steps_after_mask: int,
    rotate_180: bool,
) -> np.ndarray:
    """
    Load and preprocess camera frames.
    
    Args:
        demo_dir: Path to demo directory
        camera_name: Name of camera subdirectory
        keep_mask: Boolean mask for filtering frames
        num_steps_after_mask: Expected number of frames after masking
        rotate_180: Whether to rotate images 180 degrees
    
    Returns:
        Processed frames array with shape (T, 224, 224, 3) in uint8 format
    
    Raises:
        FileNotFoundError: If camera directory or frames not found
        ValueError: If frame count mismatch
    """
    frames_dir = demo_dir / "recordings" / "frames" / camera_name
    if not frames_dir.exists():
        raise FileNotFoundError(f"Missing camera directory: {frames_dir}")
    
    frame_files = _list_image_files(frames_dir)
    if not frame_files:
        raise FileNotFoundError(f"No frames found in {frames_dir}")
    
    # If frame count is pre-mask length, apply mask to frame file list
    if len(frame_files) == keep_mask.shape[0]:
        frame_files = [p for p, keep in zip(frame_files, keep_mask) if keep]
    elif len(frame_files) != num_steps_after_mask:
        raise ValueError(
            f"Frame count mismatch for {camera_name}: "
            f"{len(frame_files)} vs expected {num_steps_after_mask} or {keep_mask.shape[0]}"
        )
    
    # Load and stack frames
    frames = np.stack([ensure_uint8_image(np.array(Image.open(p))) for p in frame_files], axis=0)
    
    # Rotate if requested
    if rotate_180:
        frames = np.ascontiguousarray(frames[:, ::-1, ::-1])
    
    # Resize to 224x224 with padding
    frames = resize_with_pad(frames, 224, 224)
    
    if frames.shape != (num_steps_after_mask, 224, 224, 3):
        raise ValueError(f"Unexpected resized frame shape: {frames.shape}")
    
    return frames


def process_demo_folder(
    demo_dir: Path,
    *,
    dinov2=None,
    prompts: Optional[List[str]] = None,
    wrist_camera: str = "hand_camera",
    base_camera: str = "varied_camera_1",
    rotate_180: bool = False,
    overwrite: bool = False,
    use_placeholder_embeddings: bool = False,
) -> None:
    """
    Process a single demo folder into processed_demo.npz.
    
    Args:
        demo_dir: Path to demo directory
        dinov2: DINOv2 model (required if use_placeholder_embeddings=False)
        prompts: Optional list of prompts to randomly choose from
        wrist_camera: Name of wrist camera subdirectory
        base_camera: Name of base camera subdirectory
        rotate_180: Whether to rotate images 180 degrees
        overwrite: Whether to overwrite existing processed_demo.npz
        use_placeholder_embeddings: If True, use zero embeddings instead of DINOv2
    
    Raises:
        FileNotFoundError: If required files not found
        ValueError: If data shape mismatches occur
    """
    out_file = demo_dir / "processed_demo.npz"
    if out_file.exists() and not overwrite:
        logger.info(f"Already processed: {demo_dir}")
        return
    
    # Load trajectory data
    traj_path = _find_traj_file(demo_dir)
    with h5py.File(traj_path, "r") as traj_h5:
        obs_joint = traj_h5["observation"]["robot_state"]["joint_positions"][:]
        obs_grip = traj_h5["observation"]["robot_state"]["gripper_position"][:]
        act_joint = traj_h5["action"]["joint_velocity"][:]
        act_grip = traj_h5["action"]["gripper_position"][:]
        
        # Prepare state and action arrays
        joint7 = _prepare_joint7(obs_joint)
        grip1 = _prepare_gripper1(obs_grip)
        actions7_full = _prepare_action7(act_joint, act_grip)
        
        num_steps_full = joint7.shape[0]
        if grip1.shape[0] != num_steps_full or actions7_full.shape[0] != num_steps_full:
            raise ValueError(
                f"Time length mismatch in {demo_dir}: "
                f"{joint7.shape[0]=}, {grip1.shape[0]=}, {actions7_full.shape[0]=}"
            )
        
        # Apply skip_action mask
        keep_mask = _load_keep_mask(traj_h5, num_steps_full)
        state = np.concatenate([joint7, grip1], axis=1)[keep_mask].astype(np.float32)
        actions = actions7_full[keep_mask].astype(np.float32)
    
    num_steps = state.shape[0]
    if num_steps == 0:
        raise ValueError(f"All steps filtered by skip_action in {demo_dir}")
    if state.shape != (num_steps, 8):
        raise ValueError(f"Unexpected state shape: {state.shape}")
    if actions.shape != (num_steps, 7):
        raise ValueError(f"Unexpected actions shape: {actions.shape}")
    
    # Load and process camera frames
    base_image = _load_camera_frames(demo_dir, base_camera, keep_mask, num_steps, rotate_180)
    wrist_image = _load_camera_frames(demo_dir, wrist_camera, keep_mask, num_steps, rotate_180)
    
    # Generate embeddings
    if use_placeholder_embeddings:
        base_emb = create_placeholder_embeddings(num_steps)
        wrist_emb = create_placeholder_embeddings(num_steps)
    else:
        if dinov2 is None:
            raise ValueError("dinov2 model required when use_placeholder_embeddings=False")
        base_emb = embed_with_batches(base_image, dinov2)
        wrist_emb = embed_with_batches(wrist_image, dinov2)
    
    if base_emb.shape != (num_steps, EMBED_DIM):
        raise ValueError(f"Unexpected base embedding shape: {base_emb.shape}")
    if wrist_emb.shape != (num_steps, EMBED_DIM):
        raise ValueError(f"Unexpected wrist embedding shape: {wrist_emb.shape}")
    
    # Get prompt
    prompt = _read_prompt(demo_dir, prompts)
    
    # Save processed demo
    processed_demo = {
        "state": state,
        "actions": actions,
        "base_image": base_image,
        "wrist_image": wrist_image,
        "base_image_embeddings": base_emb,
        "wrist_image_embeddings": wrist_emb,
        "prompt": prompt,
    }
    np.savez(out_file, **processed_demo)
    
    # Save metadata
    meta = {
        "source": "robot_raw",
        "trajectory_file": traj_path.name,
        "num_steps": num_steps,
        "state_dim": int(state.shape[1]),
        "action_dim": int(actions.shape[1]),
        "base_camera": base_camera,
        "wrist_camera": wrist_camera,
        "rotate_180": bool(rotate_180),
        "embedding_type": "placeholder" if use_placeholder_embeddings else "dinov2",
    }
    (demo_dir / "episode_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info(f"Saved: {out_file}")

    # Record in local database
    try:
        db = get_default_db()
        
        # Get or create scenario
        scenario_id = db.get_or_create_scenario(prompt)
        
        # Determine demo status based on directory structure
        demo_status = "pending"
        if "/approved/" in str(demo_dir):
            demo_status = "approved"
        elif "/rejected/" in str(demo_dir):
            demo_status = "rejected"
        
        # Create demo record
        demo_id = db.create_demo(
            scenario_id=scenario_id,
            status="pending",  # Always start as pending
            num_steps=num_steps,
            state_dim=int(state.shape[1]),
            action_dim=int(actions.shape[1]),
            image_h=224,
            image_w=224,
            embed_dim=int(base_emb.shape[1]) if not use_placeholder_embeddings else None,
            embed_model_id="dinov2" if not use_placeholder_embeddings else "placeholder"
        )
        
        # Store artifact in ~/.serve/artifacts/ with object-key based naming
        object_key, artifact_path = store_artifact(out_file, demo_id)
        
        # Create artifact record
        db.create_artifact(
            demo_id=demo_id,
            kind="processed",
            object_key=object_key,
            local_path=str(artifact_path)
        )
        
        db.close()
        logger.debug(f"Recorded demo {demo_id} in local.db")
    except Exception as exc:
        logger.warning(f"Failed to record in local.db: {exc}")
        # Don't fail the entire preprocessing if DB fails


def _iter_demo_folders(root: Path) -> List[Path]:
    """
    Find all demo folders in root directory.
    A valid demo folder contains "recordings/" and "trajectory.h5" or "traj.h5".
    
    Args:
        root: Root directory to search
    
    Returns:
        List of demo folder paths
    """
    folders = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        has_recordings = (path / "recordings").exists()
        has_traj = any((path / x).exists() for x in ("trajectory.h5", "traj.h5"))
        if has_recordings and has_traj:
            folders.append(path)
    return folders


def process_scenario_dir(
    scenario_dir: Path,
    *,
    dinov2=None,
    prompts: Optional[List[str]] = None,
    wrist_camera: str = "hand_camera",
    base_camera: str = "varied_camera_1",
    rotate_180: bool = False,
    overwrite: bool = False,
    use_placeholder_embeddings: bool = False,
) -> None:
    """
    Process all demo folders in a scenario directory.
    
    Args:
        scenario_dir: Path to scenario directory containing demo folders
        dinov2: DINOv2 model (required if use_placeholder_embeddings=False)
        prompts: Optional list of prompts to randomly choose from
        wrist_camera: Name of wrist camera subdirectory
        base_camera: Name of base camera subdirectory
        rotate_180: Whether to rotate images 180 degrees
        overwrite: Whether to overwrite existing processed_demo.npz
        use_placeholder_embeddings: If True, use zero embeddings instead of DINOv2
    """
    demo_folders = _iter_demo_folders(scenario_dir)
    logger.info(f"Scenario={scenario_dir.name}, demos={len(demo_folders)}")
    
    for demo_dir in demo_folders:
        try:
            process_demo_folder(
                demo_dir,
                dinov2=dinov2,
                prompts=prompts,
                wrist_camera=wrist_camera,
                base_camera=base_camera,
                rotate_180=rotate_180,
                overwrite=overwrite,
                use_placeholder_embeddings=use_placeholder_embeddings,
            )
        except Exception as exc:
            logger.error(f"Failed to process {demo_dir}: {exc}", exc_info=True)


@click.command(name='preprocess')
@click.argument('input-dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument('output-dir', type=click.Path(file_okay=False, dir_okay=True), required=False)
@click.option('--prompt', multiple=True, help='Task prompt(s) to use (random if multiple)')
@click.option('--wrist-camera', default='hand_camera', help='Wrist camera subdirectory name')
@click.option('--base-camera', default='varied_camera_1', help='Base camera subdirectory name')
@click.option('--rotate-180', is_flag=True, help='Rotate images 180 degrees before resizing')
@click.option('--overwrite', is_flag=True, help='Overwrite existing processed_demo.npz files')
@click.option('--placeholder-embeddings', is_flag=True, help='Use zero embeddings (no GPU required)')
@click.option('--recursive', is_flag=True, help='Process all scenario subdirectories in input-dir')
def preprocess_command(
    input_dir: str,
    output_dir: Optional[str],
    prompt: tuple,
    wrist_camera: str,
    base_camera: str,
    rotate_180: bool,
    overwrite: bool,
    placeholder_embeddings: bool,
    recursive: bool,
):
    """
    Preprocess robot trajectory logs into processed_demo.npz format.
    
    INPUT_DIR: Directory containing demo folders (or scenario directories if --recursive)
    OUTPUT_DIR: Optional output directory (defaults to INPUT_DIR)
    
    \b
    Expected input structure (single scenario):
        input-dir/
        ├── demo_0/
        │   ├── traj.h5
        │   └── recordings/frames/
        │       ├── hand_camera/
        │       └── varied_camera_1/
        ├── demo_1/
        └── ...
    
    \b
    Expected input structure (recursive):
        input-dir/
        ├── scenario_1/
        │   ├── demo_0/...
        │   ├── demo_1/...
        ├── scenario_2/
        │   ├── demo_0/...
        └── ...
    
    \b
    Output:
        Each demo folder gets:
        - processed_demo.npz (canonical format with RGB + embeddings)
        - episode_meta.json (metadata)
    
    \b
    Examples:
        # Process single scenario with DINOv2 embeddings
        serve data preprocess ./raw_demos --prompt "pick up the cube"
        
        # Process multiple scenarios (recursive)
        serve data preprocess ./all_scenarios --recursive
        
        # Quick preprocessing without GPU (for testing structure only)
        serve data preprocess ./raw_demos --placeholder-embeddings
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve() if output_dir else input_path
    
    prompts_list = list(prompt) if prompt else None
    
    # Load DINOv2 if needed
    dinov2 = None
    if not placeholder_embeddings:
        click.echo("Loading DINOv2 model (this may take a minute)...")
        dinov2 = load_dinov2()
        click.echo("DINOv2 loaded successfully.")
    else:
        click.echo("Using placeholder embeddings (zeros). NOT suitable for production.")
    
    # Process directories
    if recursive:
        # Process each scenario subdirectory
        scenario_dirs = sorted([p for p in input_path.iterdir() if p.is_dir()])
        click.echo(f"Found {len(scenario_dirs)} scenario directories in {input_path}")
        
        for scenario_dir in scenario_dirs:
            # Infer prompts from scenario directory name if not provided
            inferred_prompts = None
            if prompts_list is None and "_" in scenario_dir.name:
                parts = scenario_dir.name.split("_")
                if len(parts) > 1 and parts[0].count("-") == 2:  # Format: YYYY-MM-DD_task
                    inferred_prompts = [" ".join(parts[1:])]
            
            click.echo(f"\nProcessing scenario: {scenario_dir.name}")
            process_scenario_dir(
                scenario_dir,
                dinov2=dinov2,
                prompts=inferred_prompts or prompts_list,
                wrist_camera=wrist_camera,
                base_camera=base_camera,
                rotate_180=rotate_180,
                overwrite=overwrite,
                use_placeholder_embeddings=placeholder_embeddings,
            )
    else:
        # Process single scenario directory
        click.echo(f"Processing scenario: {input_path.name}")
        process_scenario_dir(
            input_path,
            dinov2=dinov2,
            prompts=prompts_list,
            wrist_camera=wrist_camera,
            base_camera=base_camera,
            rotate_180=rotate_180,
            overwrite=overwrite,
            use_placeholder_embeddings=placeholder_embeddings,
        )
    
    click.echo("\n✓ Preprocessing complete!")
