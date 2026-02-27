"""
NPZ file validation utilities for processed_demo.npz format.

This module validates that NPZ files conform to the canonical data contract
used by the ricl_openpi_libero project for VLA training and inference.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class NpzValidationError(Exception):
    """Raised when NPZ validation fails."""
    pass


# Canonical data contract from ricl_openpi_libero
REQUIRED_KEYS = [
    'state',
    'actions',
    'base_image',
    'wrist_image',
    'base_image_embeddings',
    'wrist_image_embeddings',
    'prompt'
]

REQUIRED_SHAPES = {
    'state': (None, 8),              # (T, 8) - robot state
    'actions': (None, 7),            # (T, 7) - actions
    'base_image': (None, 224, 224, 3),      # (T, 224, 224, 3) - base camera RGB
    'wrist_image': (None, 224, 224, 3),     # (T, 224, 224, 3) - wrist camera RGB
}

# Optional legacy keys for backward compatibility
LEGACY_KEYS = [
    'joint_positions',
    'joint_velocities',
    'end_effector_pose',
    'gripper_state',
    'timestamps'
]


def validate_npz(npz_path: str, strict: bool = True) -> Tuple[bool, List[str]]:
    """
    Validate an NPZ file against the canonical data contract.
    
    Args:
        npz_path: Path to the NPZ file
        strict: If True, require all canonical keys. If False, allow legacy format.
        
    Returns:
        (is_valid, error_messages) tuple
        
    Example:
        >>> valid, errors = validate_npz("demo.npz")
        >>> if not valid:
        ...     for err in errors:
        ...         print(f"Error: {err}")
    """
    errors = []
    path = Path(npz_path)
    
    if not path.exists():
        return False, [f"File not found: {npz_path}"]
    
    try:
        with np.load(npz_path, allow_pickle=True) as data:
            keys = set(data.files)
            
            # Check for required keys
            missing_keys = set(REQUIRED_KEYS) - keys
            if missing_keys:
                if strict:
                    errors.append(f"Missing required keys: {sorted(missing_keys)}")
                else:
                    # Check if it's legacy format
                    legacy_found = keys & set(LEGACY_KEYS)
                    if not legacy_found:
                        errors.append(f"Missing required keys: {sorted(missing_keys)} (not legacy format either)")
            
            # Validate shapes for required keys
            for key, expected_shape in REQUIRED_SHAPES.items():
                if key not in data:
                    continue
                    
                arr = data[key]
                actual_shape = arr.shape
                
                # Check dimensions match (None means any size is OK)
                if len(actual_shape) != len(expected_shape):
                    errors.append(
                        f"Key '{key}': expected {len(expected_shape)} dimensions, "
                        f"got {len(actual_shape)}"
                    )
                    continue
                
                # Check each dimension
                for i, (expected, actual) in enumerate(zip(expected_shape, actual_shape)):
                    if expected is not None and expected != actual:
                        errors.append(
                            f"Key '{key}': dimension {i} expected {expected}, got {actual}"
                        )
            
            # Validate embeddings exist and have correct ndim
            for embed_key in ['base_image_embeddings', 'wrist_image_embeddings']:
                if embed_key in data:
                    arr = data[embed_key]
                    if arr.ndim != 2:
                        errors.append(
                            f"Key '{embed_key}': expected 2D array (T, D), got shape {arr.shape}"
                        )
            
            # Validate prompt is string or can be converted
            if 'prompt' in data:
                try:
                    prompt = str(data['prompt'])
                    if not prompt.strip():
                        errors.append("Key 'prompt': empty or whitespace-only")
                except Exception as e:
                    errors.append(f"Key 'prompt': cannot convert to string: {e}")
            
            # Check temporal consistency (all time-series arrays should have same T)
            time_keys = ['state', 'actions', 'base_image', 'wrist_image', 
                        'base_image_embeddings', 'wrist_image_embeddings']
            time_lengths = {}
            for key in time_keys:
                if key in data:
                    time_lengths[key] = data[key].shape[0]
            
            if time_lengths:
                unique_lengths = set(time_lengths.values())
                if len(unique_lengths) > 1:
                    errors.append(
                        f"Inconsistent time dimensions: {time_lengths}"
                    )
    
    except Exception as e:
        return False, [f"Failed to load NPZ file: {e}"]
    
    return len(errors) == 0, errors


def get_npz_info(npz_path: str) -> Dict[str, any]:
    """
    Get summary information about an NPZ file.
    
    Args:
        npz_path: Path to the NPZ file
        
    Returns:
        Dictionary with keys: 'keys', 'shapes', 'dtypes', 'total_size_mb', 'trajectory_length'
    """
    info = {
        'keys': [],
        'shapes': {},
        'dtypes': {},
        'total_size_mb': 0,
        'trajectory_length': None
    }
    
    try:
        with np.load(npz_path, allow_pickle=True) as data:
            info['keys'] = list(data.files)
            total_bytes = 0
            
            for key in data.files:
                arr = data[key]
                info['shapes'][key] = arr.shape
                info['dtypes'][key] = str(arr.dtype)
                total_bytes += arr.nbytes
                
                # Infer trajectory length from first time-series array
                if info['trajectory_length'] is None and arr.ndim >= 1:
                    if key in ['state', 'actions', 'base_image', 'wrist_image']:
                        info['trajectory_length'] = arr.shape[0]
            
            info['total_size_mb'] = total_bytes / (1024 * 1024)
    
    except Exception as e:
        info['error'] = str(e)
    
    return info


def convert_legacy_to_canonical(legacy_npz: str, output_npz: str, 
                                prompt: str = "legacy trajectory",
                                base_image: Optional[np.ndarray] = None,
                                wrist_image: Optional[np.ndarray] = None) -> bool:
    """
    Convert legacy NPZ format to canonical processed_demo.npz format.
    
    Args:
        legacy_npz: Path to legacy NPZ with joint_positions, etc.
        output_npz: Path to save canonical NPZ
        prompt: Text prompt describing the task
        base_image: Optional (T, 224, 224, 3) base camera images
        wrist_image: Optional (T, 224, 224, 3) wrist camera images
        
    Returns:
        True if conversion successful
        
    Note:
        This function creates placeholder embeddings and images if not provided.
        For production use, compute real embeddings using a vision model.
    """
    try:
        with np.load(legacy_npz, allow_pickle=True) as data:
            T = data['joint_positions'].shape[0] if 'joint_positions' in data else 100
            
            # Build state array (T, 8) from joint_positions (T, 7) + gripper (T, 1)
            state = np.zeros((T, 8), dtype=np.float32)
            if 'joint_positions' in data:
                state[:, :7] = data['joint_positions']
            if 'gripper_state' in data:
                state[:, 7] = data['gripper_state']
            
            # Build actions array (T, 7) - use joint velocities if available
            actions = np.zeros((T, 7), dtype=np.float32)
            if 'joint_velocities' in data:
                actions = data['joint_velocities'][:, :7]
            
            # Handle images
            if base_image is None:
                base_image = np.zeros((T, 224, 224, 3), dtype=np.uint8)
            if wrist_image is None:
                wrist_image = np.zeros((T, 224, 224, 3), dtype=np.uint8)
            
            # Create placeholder embeddings (T, 512) - DINOv2 dimension
            base_image_embeddings = np.zeros((T, 512), dtype=np.float32)
            wrist_image_embeddings = np.zeros((T, 512), dtype=np.float32)
            
            # Save canonical format
            np.savez(
                output_npz,
                state=state,
                actions=actions,
                base_image=base_image,
                wrist_image=wrist_image,
                base_image_embeddings=base_image_embeddings,
                wrist_image_embeddings=wrist_image_embeddings,
                prompt=prompt
            )
            
            return True
    
    except Exception as e:
        print(f"Conversion failed: {e}")
        return False
