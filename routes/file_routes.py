from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import os
import aiofiles
import secrets
from typing import Optional
import mimetypes
from datetime import datetime
import hashlib
import logging
import io

from config import settings
from db import get_database
from utils.helpers import (
    generate_unique_code, 
    validate_file_type, 
    generate_links,
    limiter,
    format_size,
    sanitize_filename
)
from bot import telegram_bot  # NEW: Import telegram_bot

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

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)

    if not validate_file_type(safe_filename):
        raise HTTPException(400, "File type not allowed")

    # Generate unique identifiers
    file_id = secrets.token_urlsafe(16)
    unique_code = generate_unique_code()

    file_path = os.path.join(UPLOAD_DIR, file_id)

    try:
        file_size = 0
        hash_md5 = hashlib.md5()

        async with aiofiles.open(file_path, "wb") as f:
            while True:
                # Read file in chunks
                chunk = await file.read(8192)  # 8KB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > settings.MAX_FILE_SIZE:
                    await f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(413, f"File too large. Maximum size is {format_size(settings.MAX_FILE_SIZE)}")
                hash_md5.update(chunk)
                await f.write(chunk)

        file_hash = hash_md5.hexdigest()

        # Store in database
        db = get_database()
        file_data = {
            "file_id": file_id,
            "unique_code": unique_code,
            "original_name": safe_filename,
            "file_path": file_path,
            "file_size": file_size,
            "file_hash": file_hash,
            "uploader_id": uploader_id or "anonymous",
            "upload_time": datetime.utcnow(),
            "mime_type": mimetypes.guess_type(safe_filename)[0] or "application/octet-stream",
            "download_count": 0
        }

        await db.files.insert_one(file_data)

        # Generate links
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        # Clean up if error occurs
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(500, f"Upload failed: {str(e)}")

# This function is used by both API route and direct route
async def download_file_handler(file_id: str, code: str, request: Request, response: Response):
    db = get_database()

    # Find file in database
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code})
    if not file_data:
        raise HTTPException(404, "File not found")

    # NEW: Try to get file from Telegram channel first
    if file_data.get('telegram_file_id') and telegram_bot.application:
        try:
            logger.info(f"Attempting to fetch file from Telegram: {file_data.get('telegram_file_id')}")

            # Get bot instance
            bot = telegram_bot.application.bot

            # Get file object from Telegram
            telegram_file = await bot.get_file(file_data['telegram_file_id'])

            # Download file as bytearray
            file_bytes = await telegram_file.download_as_bytearray()

            # Update download count
            await db.files.update_one(
                {"file_id": file_id},
                {"$inc": {"download_count": 1}}
            )

            logger.info(f"✅ Successfully fetched file from Telegram ({len(file_bytes)} bytes)")

            # Handle range requests for Telegram files
            file_size = len(file_bytes)
            range_header = request.headers.get("range")

            headers = {
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_data["original_name"]}"',
                "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
                "ETag": file_data.get("file_hash", "")
            }

            if range_header:
                try:
                    # Parse range header: bytes=start-end
                    range_str = range_header.strip().lower().replace("bytes=", "")
                    start_str, end_str = range_str.split("-")

                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1

                    if end >= file_size:
                        end = file_size - 1

                    content_length = end - start + 1

                    # Extract byte range from file_bytes
                    range_bytes = file_bytes[start:end+1]

                    response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                    response.headers["Content-Length"] = str(content_length)
                    response.status_code = 206

                    return StreamingResponse(
                        io.BytesIO(range_bytes),
                        media_type=file_data["mime_type"],
                        headers=headers
                    )
                except Exception as e:
                    logger.error(f"Range request error: {e}")
                    # Fall through to full file

            # Full file download
            headers["Content-Length"] = str(file_size)

            return StreamingResponse(
                io.BytesIO(file_bytes),
                media_type=file_data["mime_type"],
                headers=headers
            )

        except Exception as telegram_err:
            logger.error(f"Failed to fetch from Telegram: {telegram_err}", exc_info=True)
            logger.info("Falling back to local file storage")
            # Fall through to local file method below

    # FALLBACK: Use local file (for old files or if Telegram fetch failed)
    file_path = file_data.get("file_path")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(410, "File no longer available. Not found in channel or local storage.")

    # Update download count
    await db.files.update_one(
        {"file_id": file_id},
        {"$inc": {"download_count": 1}}
    )

    # Get file size for range requests
    file_size = os.path.getsize(file_path)

    # Handle range requests (for media players)
    range_header = request.headers.get("range")

    async def file_sender_range(start: int, end: int):
        async with aiofiles.open(file_path, "rb") as f:
            await f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk_size = min(4096, remaining)
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)

    async def file_sender_full():
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(4096)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_data["original_name"]}"',
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
        "ETag": file_data.get("file_hash", "")
    }

    if range_header:
        try:
            # Parse range header: bytes=start-end
            range_str = range_header.strip().lower().replace("bytes=", "")
            start_str, end_str = range_str.split("-")

            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1

            if end >= file_size:
                end = file_size - 1

            content_length = end - start + 1

            response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            response.headers["Content-Length"] = str(content_length)
            response.status_code = 206

            return StreamingResponse(
                file_sender_range(start, end),
                media_type=file_data["mime_type"],
                headers=headers
            )
        except Exception as e:
            logger.error(f"Range header error: {e}")
            # Fall back to full file download

    # Regular download
    headers["Content-Length"] = str(file_size)

    return StreamingResponse(
        file_sender_full(),
        media_type=file_data["mime_type"],
        headers=headers
    )

# API route (with /api/v1 prefix)
@router.get("/dl/{file_id}")
async def download_file_api(
    file_id: str,
    code: str,
    request: Request,
    response: Response
):
    """Download file via API route"""
    return await download_file_handler(file_id, code, request, response)

@router.get("/random")
@limiter.limit("10/minute")
async def get_random_file(request: Request):
    db = get_database()

    try:
        # Use MongoDB aggregation to get random file
        pipeline = [
            {"$sample": {"size": 1}},
            {"$project": {
                "file_id": 1,
                "unique_code": 1,
                "original_name": 1,
                "file_size": 1,
                "mime_type": 1,
                "upload_time": 1
            }}
        ]

        cursor = db.files.aggregate(pipeline)
        random_files = await cursor.to_list(length=1)

        if not random_files:
            raise HTTPException(404, "No files available")

        file_data = random_files[0]
        links = generate_links(file_data["file_id"], file_data["unique_code"])

        return {
            "file": file_data,
            "links": links
        }
    except Exception as e:
        logger.error(f"Random file error: {e}")
        raise HTTPException(500, "Error fetching random file")

@router.get("/info/{file_id}")
async def get_file_info(file_id: str, code: str):
    db = get_database()

    file_data = await db.files.find_one(
        {"file_id": file_id, "unique_code": code},
        {"_id": 0, "file_path": 0}
    )

    if not file_data:
        raise HTTPException(404, "File not found")

    return file_data

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
