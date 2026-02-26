"""
Utilities for handling NPZ files (NumPy compressed archive format).

This module provides functions to serialize robot trajectory data stored in .npz files
into encrypted chunks for upload, and to deserialize downloaded chunks back into .npz files.
"""

import numpy as np
import io
import base64
from typing import List, Dict, Any


def npz_to_chunks(npz_path: str, chunk_size_kb: int = 512) -> List[Dict[str, Any]]:
    """
    Read an NPZ file and serialize it into chunks for encrypted upload.
    
    Args:
        npz_path: Path to the .npz file containing robot trajectory data
        chunk_size_kb: Maximum size of each chunk in KB (default: 512KB)
        
    Returns:
        List of chunk dictionaries with format:
        [{"chunkIndex": 0, "data": "<base64-encoded-binary>"}, ...]
        
    Raises:
        FileNotFoundError: If npz_path does not exist
        IOError: If the file cannot be read or is not a valid NPZ file
    """
    # Read the NPZ file into memory
    with np.load(npz_path, allow_pickle=True) as data:
        # Serialize all arrays to a BytesIO buffer
        buffer = io.BytesIO()
        np.savez(buffer, **{key: data[key] for key in data.files})
        binary_data = buffer.getvalue()
    
    # Calculate chunk size in bytes
    chunk_size_bytes = chunk_size_kb * 1024
    
    # Split binary data into chunks
    chunks = []
    total_size = len(binary_data)
    
    for i in range(0, total_size, chunk_size_bytes):
        chunk_binary = binary_data[i:i + chunk_size_bytes]
        # Encode as base64 for JSON-safe transport
        chunk_b64 = base64.b64encode(chunk_binary).decode('utf-8')
        
        chunks.append({
            "chunkIndex": len(chunks),
            "data": chunk_b64
        })
    
    return chunks


def chunks_to_npz(chunks: List[Dict[str, Any]], output_path: str) -> None:
    """
    Deserialize downloaded chunks back into an NPZ file.
    
    Args:
        chunks: List of decrypted chunk dictionaries from server
                Format: [{"chunkIndex": 0, "data": "<base64-encoded-binary>"}, ...]
        output_path: Path where the reconstructed .npz file should be saved
        
    Raises:
        ValueError: If chunks are malformed or cannot be decoded
        IOError: If the output file cannot be written
    """
    # Sort chunks by index to ensure correct order
    sorted_chunks = sorted(chunks, key=lambda c: c.get("chunkIndex", 0))
    
    # Reconstruct binary data from chunks
    binary_parts = []
    for chunk in sorted_chunks:
        chunk_data = chunk.get("data", "")
        # Decode base64 back to binary
        binary_parts.append(base64.b64decode(chunk_data))
    
    binary_data = b''.join(binary_parts)
    
    # Load NPZ from binary data
    buffer = io.BytesIO(binary_data)
    with np.load(buffer, allow_pickle=True) as data:
        # Extract all arrays
        arrays = {key: data[key] for key in data.files}
    
    # Save to output file
    np.savez(output_path, **arrays)
