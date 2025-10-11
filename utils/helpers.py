# utils/helpers.py
from config import settings


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def generate_links(file_id: str, unique_code: str) -> dict:
    """Generate all download links for a file"""
    return {
        "render_link": f"{settings.RENDER_URL}/dl/{file_id}?code={unique_code}",
        "cloudflare_link": f"{settings.CLOUDFLARE_WORKER_URL}/dl/{file_id}?code={unique_code}",
        "bot_link": f"https://t.me/{settings.BOT_USERNAME}?start={unique_code}"
    }


def validate_file_type(filename: str) -> bool:
    """Validate file type (basic implementation)"""
    allowed_extensions = {
        '.pdf', '.doc', '.docx', '.txt', '.zip', '.rar', 
        '.7z', '.mp4', '.avi', '.mkv', '.mp3', '.wav', 
        '.jpg', '.jpeg', '.png', '.gif', '.webp'
    }
    
    file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
    return file_ext in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1)
        filename = name[:255-len(ext)-1] + '.' + ext
    
    return filename


def get_cache_key(file_id: str, unique_code: str) -> str:
    """Generate consistent cache key for file metadata"""
    return f"file:{file_id}:{unique_code}"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"