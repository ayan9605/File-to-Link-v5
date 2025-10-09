from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import StreamingResponse
import io
import logging
import os

from config import settings
from db import get_database
from utils.helpers import generate_links, format_size
from bot import telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/dl/{file_id}")
async def download_file_api(file_id: str, code: str, request: Request, response: Response):
    db = get_database()

    # Find file metadata from DB
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code})
    if not file_data:
        raise HTTPException(404, "File not found")

    # Try to serve file from Telegram CDN if stored in channel
    if file_data.get('telegram_file_id') and telegram_bot.application:
        try:
            bot = telegram_bot.application.bot
            logger.info(f"Streaming file {file_id} from Telegram CDN")

            telegram_file = await bot.get_file(file_data['telegram_file_id'])
            file_url = telegram_file.file_path
            if not file_url:
                raise HTTPException(404, "Telegram file URL not found")

            full_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_url}"

            async def file_streamer():
                import httpx
                async with httpx.AsyncClient() as client:
                    async with client.stream("GET", full_url) as resp:
                        if resp.status_code != 200:
                            raise HTTPException(resp.status_code, "Failed to fetch file from Telegram CDN")
                        async for chunk in resp.aiter_bytes():
                            yield chunk

            headers = {
                "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
                "Content-Type": file_data.get('mime_type', 'application/octet-stream'),
                "Content-Length": str(file_data.get('file_size', 0))
            }

            return StreamingResponse(file_streamer(), headers=headers, media_type=headers["Content-Type"])

        except Exception as e:
            logger.error(f"Failed to stream from Telegram CDN: {e}")
            # fall back to local file streaming below

    # Fallback to local file system (for old files or fallback)
    file_path = file_data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(410, "File no longer available")

    async def local_file_sender():
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            chunk = await f.read(4096)
            while chunk:
                yield chunk
                chunk = await f.read(4096)

    headers = {
        "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
        "Content-Type": file_data.get('mime_type', 'application/octet-stream'),
        "Content-Length": str(os.path.getsize(file_path))
    }

    logger.info(f"Streaming file {file_id} from local storage")
    return StreamingResponse(local_file_sender(), headers=headers, media_type=headers["Content-Type"])