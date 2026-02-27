"""
DINOv2 embedding utilities for robot demo preprocessing.
Ported from ricl_openpi_libero/src/openpi/policies/utils.py
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

# DINOv2 embedding configuration
EMBEDDING_TYPE = '64PATCHES'  # Options: 'CLS', 'AVG', '16PATCHES', '64PATCHES'
EMBED_DIM = int(EMBEDDING_TYPE.split('PATCHES')[0]) * 768 if 'PATCHES' in EMBEDDING_TYPE else 768

# ImageNet normalization constants
IMAGENET_DEFAULT_MEAN = (0.485, 0.456, 0.406)
IMAGENET_DEFAULT_STD = (0.229, 0.224, 0.225)


def load_dinov2():
    """
    Load DINOv2 ViT-B/14 model from torch hub.
    Automatically uses GPU if available, CPU otherwise.
    
    Returns:
        DINOv2 model in eval mode
    """
    import torch
    import os
    
    # Force safe CPU path if CUDA unavailable
    if not torch.cuda.is_available() and os.environ.get("XFORMERS_DISABLED") is None:
        os.environ["XFORMERS_DISABLED"] = "1"
        logger.info("CUDA not available; set XFORMERS_DISABLED=1 for CPU compatibility")
    
    dinov2 = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14')
    dinov2.eval()
    
    if torch.cuda.is_available():
        dinov2 = dinov2.cuda()
        logger.info("Loaded DINOv2 on CUDA")
    else:
        logger.info("Loaded DINOv2 on CPU")
    
    return dinov2


def process_dinov2(images: np.ndarray):
    """
    Preprocess images for DINOv2 inference.
    
    Args:
        images: numpy array in uint8 format, shape (B, H, W, 3) or (H, W, 3)
    
    Returns:
        Preprocessed tensor ready for DINOv2
    """
    import torch
    import torchvision.transforms as TorchVT
    from .image_utils import resize_with_pad
    
    assert isinstance(images, np.ndarray)
    assert images.dtype == np.uint8
    
    # Add batch dimension if not present
    if len(images.shape) == 3:
        images = images[np.newaxis, ...]
    
    # Resize to 224x224 if needed
    if not (images.shape[1:3] == (224, 224) or images.shape[2:4] == (224, 224)):
        # If channel-first, convert to channel-last before resize
        if images.shape[1] == 3:
            images = images.transpose(0, 2, 3, 1)
        # Actual resolution change
        images = resize_with_pad(images, 224, 224)
    
    # Convert to channel-first if needed
    if images.shape[3] == 3:
        images = images.transpose(0, 3, 1, 2)
    
    # Convert uint8 numpy to float32 tensor and normalize from [0,255] to [0,1]
    images = torch.from_numpy(images).float() / 255.0
    
    # Normalize with ImageNet mean and std
    normalize = TorchVT.Normalize(IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD)
    images = normalize(images)
    
    # Move to GPU if available
    if torch.cuda.is_available():
        images = images.cuda()
    
    return images


def embed(images: np.ndarray, dinov2):
    """
    Extract DINOv2 embeddings from images.
    
    Args:
        images: numpy array in uint8 format, shape (B, H, W, 3) or (H, W, 3)
        dinov2: DINOv2 model from load_dinov2()
    
    Returns:
        numpy array of embeddings, shape (B, EMBED_DIM)
    """
    import torch
    import math
    
    images = process_dinov2(images)
    
    with torch.no_grad():
        images = images.to(torch.bfloat16)
        dinov2 = dinov2.to(torch.bfloat16)
        features = dinov2.forward_features(images)
        # features keys: ['x_norm_clstoken', 'x_norm_regtokens', 'x_norm_patchtokens', 'x_prenorm', 'masks']
        
        if EMBEDDING_TYPE == 'CLS':
            # Output of the CLS token
            batch_embeddings = features["x_norm_clstoken"]  # (batch_size, 768)
        
        elif EMBEDDING_TYPE == 'AVG':
            # Average of all patch tokens (256 patches for 224x224 image)
            batch_embeddings = features["x_norm_patchtokens"]  # (batch_size, 256, 768)
            batch_embeddings = batch_embeddings.mean(dim=1)  # (batch_size, 768)
        
        elif 'PATCHES' in EMBEDDING_TYPE:
            # Reduce 256 patches to N patches by spatial pooling
            batch_embeddings = features["x_norm_patchtokens"]  # (batch_size, 256, 768)
            batch_size = batch_embeddings.shape[0]
            N_patches = int(EMBEDDING_TYPE.split('PATCHES')[0])
            
            assert 256 % N_patches == 0, f"256 is not divisible by {N_patches=}"
            assert math.sqrt(N_patches) ** 2 == N_patches, f"{N_patches=} must be a perfect square"
            
            patches = []
            rows, cols = 16, 16  # 16*16 = 256 patches
            patch_rows = int(rows // math.sqrt(N_patches))
            patch_cols = int(cols // math.sqrt(N_patches))
            
            for i in range(0, rows, patch_rows):
                for j in range(0, cols, patch_cols):
                    # Extract patch indices
                    patch_indices_2d = [(r, c) for r in range(i, i + patch_rows) for c in range(j, j + patch_cols)]
                    patch_indices_in_flattened = [r * cols + c for r, c in patch_indices_2d]
                    
                    # Pool patch
                    patch = batch_embeddings[:, patch_indices_in_flattened, :]  # (batch_size, patch_size, 768)
                    assert patch.shape == (batch_size, patch_rows * patch_cols, 768)
                    patch = patch.mean(dim=1)  # (batch_size, 768)
                    patches.append(patch)
            
            assert len(patches) == N_patches
            batch_embeddings = torch.cat(patches, dim=1)  # (batch_size, N_patches*768)
    
    return batch_embeddings.float().cpu().numpy()


def embed_with_batches(images: np.ndarray, dinov2, batch_size: int = 256) -> np.ndarray:
    """
    Extract DINOv2 embeddings with batching to avoid OOM.
    
    Args:
        images: numpy array in uint8 format, shape (T, H, W, 3)
        dinov2: DINOv2 model from load_dinov2()
        batch_size: Number of images to process per batch
    
    Returns:
        numpy array of embeddings, shape (T, EMBED_DIM)
    """
    all_embeddings = []
    for i in range(0, len(images), batch_size):
        images_batch = images[i:i + batch_size]
        embeddings = embed(images_batch, dinov2)
        all_embeddings.append(embeddings)
    return np.concatenate(all_embeddings, axis=0)


def create_placeholder_embeddings(num_steps: int) -> np.ndarray:
    """
    Create placeholder embeddings for demos without DINOv2 computation.
    Useful for quick testing or when GPU is unavailable.
    
    Args:
        num_steps: Number of timesteps
    
    Returns:
        Zero embeddings of shape (num_steps, EMBED_DIM)
    """
    logger.warning(f"Creating placeholder embeddings (zeros) for {num_steps} steps. "
                   f"This is NOT suitable for production use.")
    return np.zeros((num_steps, EMBED_DIM), dtype=np.float32)
