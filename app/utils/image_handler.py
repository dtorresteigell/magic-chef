from PIL import Image
import os
from werkzeug.utils import secure_filename
import uuid

# Allowed extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Image sizes
THUMBNAIL_SIZE = (300, 300)
MEDIUM_SIZE = (800, 800)
MAX_SIZE = (1920, 1920)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_filename(original_filename):
    """Generate a unique filename using UUID"""
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    return unique_name


def optimize_image(image_path, max_size=MAX_SIZE, quality=85):
    """
    Optimize image: resize if too large and compress
    
    Args:
        image_path: Path to the image
        max_size: Maximum dimensions (width, height)
        quality: JPEG quality (1-100)
    """
    try:
        img = Image.open(image_path)
        
        # Convert RGBA to RGB if necessary (for JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize if image is larger than max_size
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save with optimization
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
        elif image_path.lower().endswith('.png'):
            img.save(image_path, 'PNG', optimize=True)
        else:
            img.save(image_path, quality=quality, optimize=True)
        
        return True
    except Exception as e:
        print(f"Error optimizing image: {e}")
        return False


def create_thumbnail(source_path, thumb_path, size=THUMBNAIL_SIZE):
    """
    Create a thumbnail version of an image
    
    Args:
        source_path: Path to original image
        thumb_path: Path where thumbnail should be saved
        size: Thumbnail dimensions (width, height)
    """
    try:
        img = Image.open(source_path)
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Create thumbnail (maintains aspect ratio, crops to fit)
        img = img.convert('RGB')
        
        # Calculate crop to center
        width, height = img.size
        target_ratio = size[0] / size[1]
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # Image is wider, crop width
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img = img.crop((left, 0, left + new_width, height))
        else:
            # Image is taller, crop height
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img = img.crop((0, top, width, top + new_height))
        
        # Resize to thumbnail size
        img = img.resize(size, Image.Resampling.LANCZOS)
        
        # Save thumbnail
        img.save(thumb_path, 'JPEG', quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return False


def process_recipe_image(file, upload_folder):
    """
    Process uploaded recipe image: save, optimize, create thumbnail
    
    Args:
        file: FileStorage object from request.files
        upload_folder: Directory to save images
        
    Returns:
        tuple: (filename, thumbnail_filename) or (None, None) on error
    """
    if not file or not file.filename:
        return None, None
    
    if not allowed_file(file.filename):
        return None, None
    
    # Generate unique filename
    filename = generate_unique_filename(file.filename)
    filepath = os.path.join(upload_folder, filename)
    
    # Create thumbnails subdirectory if it doesn't exist
    thumb_folder = os.path.join(upload_folder, 'thumbnails')
    os.makedirs(thumb_folder, exist_ok=True)
    
    try:
        # Save original file
        file.save(filepath)
        
        # Optimize the main image
        optimize_image(filepath, max_size=MEDIUM_SIZE)
        
        # Create thumbnail
        thumb_filename = f"thumb_{filename}"
        thumb_path = os.path.join(thumb_folder, thumb_filename)
        create_thumbnail(filepath, thumb_path)
        
        return filename, thumb_filename
    
    except Exception as e:
        print(f"Error processing image: {e}")
        # Clean up if something went wrong
        if os.path.exists(filepath):
            os.remove(filepath)
        return None, None


def delete_recipe_images(filename, upload_folder):
    """
    Delete recipe image and its thumbnail
    
    Args:
        filename: Name of the image file
        upload_folder: Directory where images are stored
    """
    if not filename:
        return
    
    # Delete main image
    filepath = os.path.join(upload_folder, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error deleting image: {e}")
    
    # Delete thumbnail
    thumb_filename = f"thumb_{filename}"
    thumb_path = os.path.join(upload_folder, 'thumbnails', thumb_filename)
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except Exception as e:
            print(f"Error deleting thumbnail: {e}")