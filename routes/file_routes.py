lfrom fastapi import APIRouter, Request, HTTPException, Response, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
import os
import aiofiles
import secrets
import mimetypes
import hashlib
import logging
import io
from typing import Optional
from datetime import datetime

from config import settings
from db import get_database
from utils import helpers  # assuming helpers has generate_links, format_size, validate, sanitize
from bot import telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
@helpers.limiter.limit(f"{settings.API_RATE_LIMIT}/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    uploader_id: Optional[str] = None
):
    if not file.filename:
        raise HTTPException(400, "Filename is required")

    safe_filename = helpers.sanitize_filename(file.filename)
    if not helpers.validate_file_type(safe_filename):
        raise HTTPException(400, "File type not allowed")

    file_id = secrets.token_urlsafe(16)
    unique_code = helpers.generate_unique_code()
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
                    raise HTTPException(413, f"File too large. Maximum size is {helpers.format_size(settings.MAX_FILE_SIZE)}")
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
            # No telegram data here for uploaded files
        }

        await db.files.insert_one(file_data)

        links = helpers.generate_links(file_id, unique_code)

        return {
            "success": True,
            "file_id": file_id,
            "unique_code": unique_code,
            "links": links,
            "file_info": {
                "name": safe_filename,
                "size": file_size,
                "size_formatted": helpers.format_size(file_size),
                "type": file_data["mime_type"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(500, f"Upload failed: {e}")


async def download_file_handler(file_id: str, code: str, request: Request, response: Response):
    db = get_database()
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code})

    if not file_data:
        raise HTTPException(404, "File not found")

    # Try to fetch from Telegram CDN if telegram info present
    if file_data.get("telegram_file_id") and telegram_bot.application:
        try:
            bot = telegram_bot.application.bot
            logger.info(f"Fetching file from Telegram CDN: {file_id}")

            telegram_file = await bot.get_file(file_data["telegram_file_id"])
            file_url = telegram_file.file_path
            if not file_url:
                raise HTTPException(404, "Telegram file URL not found")

            url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_url}"

            async def streamer():
                import httpx
                async with httpx.AsyncClient() as client:
                    async with client.stream('GET', url) as resp:
                        if resp.status_code != 200:
                            raise HTTPException(resp.status_code, "Error fetching from Telegram CDN")
                        async for chunk in resp.aiter_bytes():
                            yield chunk

            headers = {
                "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
                "Content-Type": file_data.get("mime_type", "application/octet-stream"),
                "Content-Length": str(file_data.get("file_size", 0)),
            }

            logger.info(f"Streaming {file_id} from Telegram CDN")
            return StreamingResponse(streamer(), headers=headers, media_type=headers["Content-Type"])

        except Exception as e:
            logger.error(f"Telegram CDN fetch failure: {e}")
            # Fallback to local file serving below

    # Fallback to local file serving
    file_path = file_data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(410, "File no longer available")

    async def file_sender(start: int = 0, end: Optional[int] = None):
        async with aiofiles.open(file_path, "rb") as f:
            if start:
                await f.seek(start)
            remaining = (end - start + 1) if end is not None else None
            while True:
                chunk_size = 4096
                if remaining is not None:
                    if remaining <= 0:
                        break
                    chunk_size = min(chunk_size, remaining)
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)

    headers = {
        "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
        "Content-Type": file_data.get("mime_type", "application/octet-stream"),
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
        "ETag": file_data.get("hash", ""),
        "Accept-Ranges": "bytes",
    }

    range_header = request.headers.get("range")
    file_size = os.path.getsize(file_path)

    if range_header:
        try:
            bytes_unit, range_spec = range_header.split("=")
            start_str, end_str = range_spec.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            if end >= file_size:
                end = file_size - 1
            length = end - start + 1

            headers.update(
                {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                }
            )
            response.status_code = 206
            return StreamingResponse(file_sender(start, end), headers=headers, media_type=headers["Content-Type"])
        except Exception as e:
            logger.error(f"Range request parse error: {e}")

    headers["Content-Length"] = str(file_size)
    return StreamingResponse(file_sender(), headers=headers, media_type=headers["Content-Type"])

# Register routes for convenience
@router.get("/random")
@helpers.limiter.limit("10/minute")
async def random_file(request: Request):
    db = get_database()
    cursor = db.files.aggregate([{"$sample": {"size": 1}}])
    random_files = await cursor.to_list(length=1)
    if not random_files:
        raise HTTPException(404, "No files available")
    file_info = random_files[0]
    links = helpers.generate_links(file_info["file_id"], file_info["unique_code"])
    return {"file": file_info, "links": links}

@router.get("/info/{file_id}")
async def file_info(file_id: str, code: str):
    db = get_database()
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code}, {"_id": 0, "file_path": 0})
    if not file_data:
        raise HTTPException(404, "File not found")
    return file_data

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}