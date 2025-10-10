from fastapi import APIRouter, Request, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse
import os
import aiofiles
import io
import logging
from datetime import datetime
from typing import Optional
import mimetypes
import hashlib
import secrets

from config import settings
from db import get_database
from utils.helpers import generate_links, format_size, sanitize_filename, validate_file_type, limiter
from bot import telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
@limiter.limit(f"{settings.API_RATE_LIMIT}/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    uploader_id: Optional[str] = None
):
    if not file.filename:
        raise HTTPException(400, "Filename is required")

    safe_filename = sanitize_filename(file.filename)

    if not validate_file_type(safe_filename):
        raise HTTPException(400, "File type not allowed")

    file_id = secrets.token_urlsafe(16)
    unique_code = secrets.token_urlsafe(12)
    file_path = os.path.join(UPLOAD_DIR, file_id)

    try:
        file_size = 0
        hash_md5 = hashlib.md5()

        async with aiofiles.open(file_path, "wb") as f:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > settings.MAX_FILE_SIZE:
                    await f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(413, f"File too large. Max allowed size is {format_size(settings.MAX_FILE_SIZE)}.")
                hash_md5.update(chunk)
                await f.write(chunk)

        file_hash = hash_md5.hexdigest()
        db = get_database()
        file_data = {
            "file_id": file_id,
            "unique_code": unique_code,
            "original_name": safe_filename,
            "file_path": file_path,
            "file_size": file_size,
            "hash": file_hash,
            "uploader_id": uploader_id or "anonymous",
            "upload_time": datetime.utcnow(),
            "mime_type": mimetypes.guess_type(safe_filename)[0] or "application/octet-stream",
            "download_count": 0,
        }

        await db.files.insert_one(file_data)
        links = generate_links(file_id, unique_code)

        return {
            "success": True,
            "file_id": file_id,
            "unique_code": unique_code,
            "links": links,
            "file_info": {
                "name": safe_filename,
                "size": file_size,
                "size_formatted": format_size(file_size),
                "type": file_data["mime_type"]
            }
        }

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(500, f"Upload failed: {e}")

@router.get("/dl/{file_id}")
async def download_file(file_id: str, code: str, request: Request, response: Response):
    db = get_database()
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code})
    if not file_data:
        raise HTTPException(404, "File not found")

    # Stream from Telegram CDN if available
    if file_data.get("telegram_file_id") and telegram_bot.application:
        try:
            bot = telegram_bot.application.bot
            telegram_file = await bot.get_file(file_data["telegram_file_id"])
            file_path = telegram_file.file_path
            if not file_path:
                raise HTTPException(404, "Telegram CDN URL not found")

            # --- CORRECTED TOKEN VARIABLE ---
            url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"

            import httpx
            async def streamer():
                async with httpx.AsyncClient() as client:
                    async with client.stream("GET", url) as resp:
                        if resp.status_code != 200:
                            raise HTTPException(resp.status_code, "Error fetching file from Telegram CDN")
                        async for chunk in resp.aiter_bytes():
                            yield chunk

            headers = {
                "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
                "Content-Type": file_data.get("mime_type", "application/octet-stream"),
                "Content-Length": str(file_data.get("file_size", 0)),
            }
            return StreamingResponse(streamer(), headers=headers)

        except Exception as e:
            logger.error(f"Telegram CDN streaming failed: {e}")

    # Fallback to local file serving
    local_path = file_data.get("file_path")
    if not local_path or not os.path.exists(local_path):
        raise HTTPException(410, "File no longer available")

    import aiofiles

    async def file_stream():
        async with aiofiles.open(local_path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
        "Content-Type": file_data.get("mime_type", "application/octet-stream"),
        "Content-Length": str(os.path.getsize(local_path)),
    }
    return StreamingResponse(file_stream(), headers=headers)

@router.get("/random")
@limiter.limit("10/minute")
async def random_file(request: Request):
    db = get_database()
    cursor = db.files.aggregate([{"$sample": {"size": 1}}])
    random_files = await cursor.to_list(1)
    if not random_files:
        raise HTTPException(404, "No files available")
    file = random_files[0]
    links = generate_links(file["file_id"], file["unique_code"])
    return {"file": file, "links": links}

@router.get("/info/{file_id}")
async def file_info(file_id: str, code: str):
    db = get_database()
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code}, {"_id": 0, "file_path": 0})
    if not file_data:
        raise HTTPException(404, "File not found")
    return file_data

@router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
