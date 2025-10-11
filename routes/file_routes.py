# routes/file_routes.py
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from datetime import datetime
import urllib.parse
import json
from bson import ObjectId
from pyrogram.errors import FloodWait

from config import settings
from db import database
from pyro_client import get_pyro_client

router = APIRouter(tags=["files"])
limiter = Limiter(key_func=get_remote_address)

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

json_encoder = JSONEncoder()

async def get_file_metadata(file_id: str, code: str):
    """Get file metadata with Redis caching"""
    cache_key = f"file:{file_id}:{code}"
    
    # Try to get from Redis cache first
    cached_data = await database.cache_get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except json.JSONDecodeError:
            # Invalid cache, delete it
            await database.cache_delete(cache_key)
    
    # Cache miss, query MongoDB
    files_collection = database.get_collection("files")
    file_data = await files_collection.find_one({
        "file_id": file_id,
        "unique_code": code
    })
    
    if file_data:
        # Convert ObjectId to string for JSON serialization
        file_data["_id"] = str(file_data["_id"])
        
        # Cache the result
        await database.cache_set(cache_key, json_encoder.encode(file_data))
        
        return file_data
    
    return None

@router.get("/dl/{file_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def download_file(request: Request, file_id: str, code: str, response: Response):
    """
    Stream file directly from Telegram with Redis caching
    """
    try:
        # Validate parameters
        if not file_id or not code:
            raise HTTPException(status_code=400, detail="Missing file ID or code")
        
        # Get file metadata (with Redis caching)
        file_data = await get_file_metadata(file_id, code)
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Update download statistics
        files_collection = database.get_collection("files")
        await files_collection.update_one(
            {"_id": ObjectId(file_data["_id"])},
            {
                "$inc": {"download_count": 1},
                "$set": {"last_downloaded": datetime.utcnow()}
            }
        )
        
        # Clear cache to reflect updated download count
        cache_key = f"file:{file_id}:{code}"
        await database.cache_delete(cache_key)
        
        # Get Pyrogram client
        client = await get_pyro_client()
        if not client or not client.is_connected:
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        
        # Stream file from Telegram
        try:
            file_path = await client.download_media(
                message=file_data["message_id"],
                chat_id=file_data["channel_id"],
                in_memory=True
            )
            
            if not file_path:
                raise HTTPException(status_code=404, detail="File not found on Telegram")
            
            # Set response headers
            filename = urllib.parse.quote(file_data["file_name"])
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers["Content-Type"] = file_data.get("mime_type", "application/octet-stream")
            response.headers["Content-Length"] = str(file_data["file_size"])
            response.headers["Cache-Control"] = "no-cache"
            response.headers["X-File-Name"] = filename
            
            return Response(
                content=file_path.getvalue() if hasattr(file_path, 'getvalue') else file_path.read(),
                media_type=file_data.get("mime_type", "application/octet-stream")
            )
            
        except FloodWait as e:
            raise HTTPException(status_code=429, detail=f"Rate limited. Please wait {e.x} seconds.")
        except Exception as e:
            print(f"Telegram download error: {e}")
            raise HTTPException(status_code=500, detail="Error downloading file from Telegram")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Download endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/file/{file_id}/info")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def get_file_info(request: Request, file_id: str, code: str):
    """
    Get file information without downloading (with Redis caching)
    """
    try:
        # Get file metadata (with Redis caching)
        file_data = await get_file_metadata(file_id, code)
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Remove internal fields
        file_data.pop("_id", None)
        file_data.pop("channel_id", None)
        file_data.pop("message_id", None)
        
        return {
            "status": "success",
            "data": file_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"File info error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")