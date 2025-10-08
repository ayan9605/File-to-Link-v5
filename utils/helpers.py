import secrets
import string
import hashlib
import os
import math
from typing import Dict, Any
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import aiohttp
import aiofiles
from config import settings

limiter = Limiter(key_func=get_remote_address)

def generate_unique_code(length: int = 12) -> str:
    """Generate a unique code for file access"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_file_type(filename: str) -> bool:
    """Validate file type based on extension"""
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    allowed_extensions = []
    for category in settings.ALLOWED_EXTENSIONS.values():
        allowed_extensions.extend(category)
    return ext in allowed_extensions

def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of file (sync)"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""

async def async_calculate_file_hash(file_path: str) -> str:
    """Async calculate MD5 hash of file"""
    hash_md5 = hashlib.md5()
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(4096)
                if not chunk:
                    break
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""

def generate_links(file_id: str, unique_code: str) -> Dict[str, str]:
    """Generate three download links for a file"""
    base_bot_link = f"https://t.me/{settings.BOT_USERNAME}?start={unique_code}" if settings.BOT_USERNAME else f"https://t.me/your_bot?start={unique_code}"
    
    # Use direct routes for CDN and Render (without /api/v1 prefix)
    return {
        "cloudflare": f"{settings.CLOUDFLARE_WORKER_URL}/dl/{file_id}?code={unique_code}",
        "render": f"{settings.RENDER_URL}/dl/{file_id}?code={unique_code}",
        "bot": base_bot_link
    }

async def make_telegram_request(token: str, method: str, data: Dict[str, Any] = None):
    """Make async request to Telegram API"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                return await response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal"""
    return os.path.basename(filename).replace('/', '_').replace('\\', '_')