"""
Utility Helper Functions
File handling, security, and Telegram integration utilities
"""

import asyncio
import aiofiles
import aiohttp
import hashlib
import secrets
import string
import logging
from datetime import datetime
from typing import Optional, Tuple, AsyncGenerator, Dict, Any
from telegram import Bot
from telegram.error import TelegramError
import mimetypes
import re

from config import settings

logger = logging.getLogger(__name__)

def generate_unique_code(length: int = 32) -> str:
    """Generate cryptographically secure unique code"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_file_id(length: int = 16) -> str:
    """Generate shorter file ID for URLs"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_file_hash(file_content: bytes) -> str:
    """Generate SHA256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

def validate_file_name(filename: str) -> bool:
    """Validate filename for security"""
    if not filename or len(filename) > 255:
        return False
    
    # Check for dangerous patterns
    dangerous_patterns = [
        r'\.\./', r'\.\.\\', r'^\.', r'\/$', r'\\$',
        r'[<>:"|?*]', r'[\x00-\x1f]', r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return False
    
    return True

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    if not filename:
        return "unnamed_file"
    
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[<>:"|?*\\/]', '_', filename)
    sanitized = re.sub(r'[\x00-\x1f]', '', sanitized)
    
    # Limit length
    if len(sanitized) > 200:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:190] + ('.' + ext if ext else '')
    
    return sanitized or "unnamed_file"

def get_content_type(filename: str) -> str:
    """Get MIME content type from filename"""
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """Parse HTTP Range header for partial content requests"""
    try:
        # Range header format: "bytes=start-end"
        if not range_header.startswith("bytes="):
            return None
        
        range_spec = range_header[6:]  # Remove "bytes="
        
        # Handle single range (we don't support multiple ranges)
        if ',' in range_spec:
            range_spec = range_spec.split(',')[0]
        
        if '-' not in range_spec:
            return None
        
        start_str, end_str = range_spec.split('-', 1)
        
        # Parse start and end
        if start_str == '':
            # Suffix-byte-range: "-500" means last 500 bytes
            if end_str == '':
                return None
            suffix_length = int(end_str)
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        elif end_str == '':
            # Start only: "500-" means from byte 500 to end
            start = int(start_str)
            end = file_size - 1
        else:
            # Both start and end: "500-999"
            start = int(start_str)
            end = int(end_str)
        
        # Validate range
        if start < 0 or start >= file_size or end < start or end >= file_size:
            return None
        
        return (start, end)
        
    except (ValueError, IndexError):
        return None

async def get_telegram_file_stream(file_id: str) -> Optional[AsyncGenerator[bytes, None]]:
    """Get file stream from Telegram"""
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Get file info
        file_info = await bot.get_file(file_id)
        
        if not file_info.file_path:
            return None
        
        # Download file in chunks
        async def stream_generator():
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_info.file_path}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                            yield chunk
                    else:
                        logger.error(f"Failed to download file from Telegram: {response.status}")
                        return
        
        return stream_generator()
        
    except Exception as e:
        logger.error(f"Error getting Telegram file stream: {e}")
        return None

async def stream_file_range(
    file_stream: AsyncGenerator[bytes, None], 
    start: int, 
    end: int
) -> AsyncGenerator[bytes, None]:
    """Stream partial file content for Range requests"""
    try:
        bytes_sent = 0
        bytes_to_send = end - start + 1
        current_pos = 0
        
        async for chunk in file_stream:
            chunk_size = len(chunk)
            chunk_end = current_pos + chunk_size - 1
            
            # Skip chunks before start position
            if chunk_end < start:
                current_pos += chunk_size
                continue
            
            # Calculate which part of chunk to send
            chunk_start_offset = max(0, start - current_pos)
            chunk_end_offset = min(chunk_size, end - current_pos + 1)
            
            if chunk_start_offset < chunk_end_offset:
                partial_chunk = chunk[chunk_start_offset:chunk_end_offset]
                yield partial_chunk
                bytes_sent += len(partial_chunk)
                
                # Stop if we've sent enough bytes
                if bytes_sent >= bytes_to_send:
                    break
            
            current_pos += chunk_size
            
            # Stop if we've passed the end position
            if current_pos > end:
                break
                
    except Exception as e:
        logger.error(f"Error streaming file range: {e}")

async def upload_to_telegram_channel(file_path: str, filename: str) -> Tuple[str, int]:
    """Upload file to Telegram channel for storage"""
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Send file to channel
        with open(file_path, 'rb') as file:
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                message = await bot.send_photo(
                    chat_id=settings.CHANNEL_ID,
                    photo=file,
                    caption=f"📁 {filename}"
                )
                telegram_file_id = message.photo[-1].file_id
            elif filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                message = await bot.send_video(
                    chat_id=settings.CHANNEL_ID,
                    video=file,
                    caption=f"📁 {filename}"
                )
                telegram_file_id = message.video.file_id
            elif filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                message = await bot.send_audio(
                    chat_id=settings.CHANNEL_ID,
                    audio=file,
                    caption=f"📁 {filename}"
                )
                telegram_file_id = message.audio.file_id
            else:
                message = await bot.send_document(
                    chat_id=settings.CHANNEL_ID,
                    document=file,
                    caption=f"📁 {filename}"
                )
                telegram_file_id = message.document.file_id
        
        return telegram_file_id, message.message_id
        
    except Exception as e:
        logger.error(f"Error uploading to Telegram channel: {e}")
        raise

def generate_cache_headers(file_doc: Dict[str, Any]) -> Dict[str, str]:
    """Generate appropriate cache headers for files"""
    upload_time = datetime.fromtimestamp(file_doc["upload_time"])
    etag = f'"{file_doc["unique_code"]}"'
    
    headers = {
        "ETag": etag,
        "Last-Modified": upload_time.strftime('%a, %d %b %Y %H:%M:%S GMT'),
        "Cache-Control": f"public, max-age={settings.CACHE_TTL}, stale-while-revalidate=86400"
    }
    
    # Add immutable cache for files (they don't change)
    if settings.CACHE_TTL > 3600:  # If cache TTL > 1 hour
        headers["Cache-Control"] += ", immutable"
    
    return headers

def is_safe_file_type(filename: str, content_type: str = None) -> bool:
    """Check if file type is safe for upload"""
    if not filename:
        return False
    
    # Get extension
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # Check against allowed extensions
    if ext not in settings.ALLOWED_EXTENSIONS:
        return False
    
    # Additional checks for potentially dangerous files
    dangerous_extensions = [
        'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js',
        'jar', 'msi', 'deb', 'rpm', 'dmg', 'pkg', 'app'
    ]
    
    if ext in dangerous_extensions:
        return False
    
    # Check content type if provided
    if content_type:
        dangerous_content_types = [
            'application/x-executable',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-sh',
            'text/x-shellscript'
        ]
        
        if content_type in dangerous_content_types:
            return False
    
    return True

def get_file_icon(filename: str, content_type: str = None) -> str:
    """Get appropriate icon emoji for file type"""
    if not filename:
        return "📄"
    
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    icon_map = {
        # Images
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'bmp': '🖼️', 'webp': '🖼️',
        # Videos
        'mp4': '🎥', 'avi': '🎥', 'mov': '🎥', 'mkv': '🎥', 'wmv': '🎥', 'flv': '🎥',
        # Audio
        'mp3': '🎵', 'wav': '🎵', 'ogg': '🎵', 'm4a': '🎵', 'flac': '🎵', 'aac': '🎵',
        # Documents
        'pdf': '📕', 'doc': '📘', 'docx': '📘', 'txt': '📝', 'rtf': '📝',
        # Spreadsheets
        'xls': '📊', 'xlsx': '📊', 'csv': '📊',
        # Presentations
        'ppt': '📊', 'pptx': '📊',
        # Archives
        'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️', 'tar': '🗜️', 'gz': '🗜️',
        # Code
        'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨', 'json': '📋',
    }
    
    return icon_map.get(ext, "📄")

async def validate_and_process_upload(
    file_content: bytes,
    filename: str,
    max_size: int = None
) -> Dict[str, Any]:
    """Validate and process file upload"""
    max_size = max_size or settings.MAX_FILE_SIZE
    
    # Basic validation
    if len(file_content) == 0:
        raise ValueError("Empty file")
    
    if len(file_content) > max_size:
        raise ValueError(f"File too large: {len(file_content)} bytes (max: {max_size})")
    
    # Sanitize filename
    safe_filename = sanitize_filename(filename)
    
    # Validate file type
    content_type = get_content_type(safe_filename)
    
    if not is_safe_file_type(safe_filename, content_type):
        raise ValueError(f"File type not allowed: {safe_filename}")
    
    # Generate file hash for deduplication (optional)
    file_hash = get_file_hash(file_content)
    
    return {
        "filename": safe_filename,
        "content_type": content_type,
        "size": len(file_content),
        "hash": file_hash,
        "icon": get_file_icon(safe_filename, content_type)
    }

def log_file_operation(operation: str, file_data: Dict[str, Any], user_id: int = None):
    """Log file operations for monitoring"""
    log_data = {
        "operation": operation,
        "file_id": file_data.get("file_id", "unknown"),
        "filename": file_data.get("file_name", "unknown"),
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "file_size": file_data.get("file_size", 0)
    }
    
    logger.info(f"File operation: {operation} | {log_data}")

# Security utilities
def rate_limit_key(ip: str, user_id: int = None) -> str:
    """Generate rate limit key for user/IP"""
    if user_id:
        return f"rate_limit:user:{user_id}"
    return f"rate_limit:ip:{ip}"

async def check_file_virus(file_content: bytes) -> bool:
    """Basic virus/malware detection (placeholder for integration with AV services)"""
    # This is a placeholder - in production you'd integrate with:
    # - VirusTotal API
    # - ClamAV
    # - Windows Defender API
    # - Other antivirus services
    
    # Basic checks for known malicious patterns
    malicious_signatures = [
        b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",  # EICAR test
    ]
    
    for signature in malicious_signatures:
        if signature in file_content:
            return True  # Malicious
    
    return False  # Clean

def get_client_info(request) -> Dict[str, str]:
    """Extract client information from request"""
    return {
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent", "Unknown"),
        "referer": request.headers.get("referer", ""),
        "accept_language": request.headers.get("accept-language", ""),
        "x_forwarded_for": request.headers.get("x-forwarded-for", "")
    }
