"""
Image preprocessing utilities for robot demo data.
Ported from ricl_openpi_libero/openpi_client/image_tools.py
"""
import numpy as np
from PIL import Image


def resize_with_pad(images: np.ndarray, height: int, width: int, method=Image.BILINEAR) -> np.ndarray:
    """
    Replicates tf.image.resize_with_pad for multiple images using PIL.
    Resizes a batch of images to a target height and width without distortion by padding with zeros.

    Args:
        images: A batch of images in [..., height, width, channel] format (uint8)
        height: The target height of the image
        width: The target width of the image
        method: The interpolation method to use (default: bilinear)

    Returns:
        The resized images in [..., height, width, channel] format (uint8)
    """
    # If the images are already the correct size, return them as is
    if images.shape[-3:-1] == (height, width):
        return images

    original_shape = images.shape
    images = images.reshape(-1, *original_shape[-3:])
    resized = np.stack([_resize_with_pad_pil(Image.fromarray(im), height, width, method) for im in images])
    return resized.reshape(*original_shape[:-3], *resized.shape[-3:])


def _resize_with_pad_pil(image: Image.Image, height: int, width: int, method: int) -> np.ndarray:
    """
    Replicates tf.image.resize_with_pad for one image using PIL.
    Resizes an image to a target height and width without distortion by padding with zeros.

    Args:
        image: PIL Image
        height: Target height
        width: Target width
        method: PIL resampling method

    Returns:
        Resized and padded image as numpy array (uint8)
    """
    cur_width, cur_height = image.size
    if cur_width == width and cur_height == height:
        return np.array(image)  # No need to resize if already correct size

    ratio = max(cur_width / width, cur_height / height)
    resized_height = int(cur_height / ratio)
    resized_width = int(cur_width / ratio)
    resized_image = image.resize((resized_width, resized_height), resample=method)

    # Create zero-padded canvas
    zero_image = Image.new(resized_image.mode, (width, height), 0)
    pad_height = max(0, int((height - resized_height) / 2))
    pad_width = max(0, int((width - resized_width) / 2))
    zero_image.paste(resized_image, (pad_width, pad_height))
    
    assert zero_image.size == (width, height)
    return np.array(zero_image)


def ensure_uint8_image(image: np.ndarray) -> np.ndarray:
    """
    Convert image array to uint8 RGB format (H, W, 3).

    Args:
        image: Input image array (any dtype, any shape)

    Returns:
        uint8 RGB image in (H, W, 3) format

    Raises:
        ValueError: If image cannot be converted to RGB format
    """
    arr = np.asarray(image)
    
    # Convert to uint8 if needed
    if arr.dtype == np.uint8:
        pass
    elif np.issubdtype(arr.dtype, np.floating):
        max_val = float(np.max(arr)) if arr.size else 1.0
        if max_val <= 1.5:
            # Assume normalized [0, 1] range
            arr = np.clip(arr, 0.0, 1.0) * 255.0
        else:
            # Assume [0, 255] range
            arr = np.clip(arr, 0.0, 255.0)
        arr = arr.astype(np.uint8)
    else:
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    # Convert channel-first to channel-last if needed
    if arr.ndim == 3 and arr.shape[0] == 3 and arr.shape[-1] != 3:
        arr = np.transpose(arr, (1, 2, 0))
    
    # Validate final shape
    if arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(f"Unsupported image shape: {arr.shape}. Expected (H, W, 3).")
    
    return arr
