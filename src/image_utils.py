import os
import uuid
from PIL import Image
from typing import Set


def generate_unique_filename(extension: str = 'jpg') -> str:
    """
    Generate UUID-based unique filename

    Args:
        extension: File extension (default: 'jpg')

    Returns:
        Unique filename string (e.g., "a1b2c3d4-5678-90ab-cdef-1234567890ab.jpg")
    """
    return f"{uuid.uuid4()}.{extension}"


def save_image(image: Image.Image, directory: str = './rag_images') -> str:
    """
    Save image to directory with unique filename and compression

    The image is:
    - Saved with a UUID-based unique filename
    - Compressed as JPEG with quality 85
    - Optimized for storage
    - RGBA images are converted to RGB (transparent -> white background)

    Args:
        image: PIL Image object to save
        directory: Directory path to save image (default: './rag_images')

    Returns:
        Relative file path of saved image (e.g., "./rag_images/abc123.jpg")
    """
    # Ensure directory exists
    os.makedirs(directory, exist_ok=True)

    # Convert RGBA to RGB if needed (JPEG doesn't support transparency)
    if image.mode in ('RGBA', 'LA', 'P'):
        # Create a white background
        background = Image.new('RGB', image.size, (255, 255, 255))
        # Paste image on white background (handling transparency)
        if image.mode == 'P':
            image = image.convert('RGBA')
        background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
        image = background

    # Generate unique filename
    filename = generate_unique_filename('jpg')
    filepath = os.path.join(directory, filename)

    # Save as JPEG with quality 85 (good balance of size vs quality)
    image.save(filepath, 'JPEG', quality=85, optimize=True)

    return filepath


def cleanup_orphaned_images(vectorstore, image_directory: str = './rag_images'):
    """
    Remove image files not referenced in vectorstore metadata

    This prevents disk space leaks when image chunks are deleted from the
    vectorstore but the actual image files remain on disk.

    Args:
        vectorstore: Chroma vectorstore instance
        image_directory: Directory containing images (default: './rag_images')
    """
    from vision_engine import VisionEngine

    # Get all active image paths from vectorstore metadata
    vision = VisionEngine()
    vectors = vision.extract_vectors(vectorstore)

    active_paths = {
        m.get('image_path')
        for m in vectors.get('metadatas', [])
        if m.get('modality') == 'image' and m.get('image_path')
    }

    # Delete files not in active set
    if os.path.exists(image_directory):
        deleted_count = 0
        for filename in os.listdir(image_directory):
            filepath = os.path.join(image_directory, filename)
            if filepath not in active_paths:
                try:
                    os.remove(filepath)
                    print(f"Deleted orphaned image: {filename}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {filename}: {str(e)}")

        print(f"Cleanup complete: {deleted_count} orphaned image(s) deleted")
    else:
        print(f"Image directory '{image_directory}' does not exist")
