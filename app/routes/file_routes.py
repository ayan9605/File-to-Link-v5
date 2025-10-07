"""
File Routes - Download, Upload, and Random File Endpoints
Handles async streaming and HTTP Range requests
"""

import asyncio
import aiofiles
import aiohttp
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, status, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import mimetypes
import os
from urllib.parse import quote

from config import settings, get_file_url
from db import FileManager, UserManager, AnalyticsManager, get_database
import utils.helpers as helpers

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)

@router.get("/dl/{file_id}")
async def download_file(
    file_id: str,
    code: str,
    request: Request,
    range_header: Optional[str] = None
):
    """
    Download file with async streaming and Range support
    Supports partial downloads for media players
    """
    try:
        # Get file info from database
        file_doc = await FileManager.get_file_by_id(file_id, code)
        
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get client info for analytics
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")
        
        # Log download (background task)
        if settings.ENABLE_ANALYTICS:
            await AnalyticsManager.log_download(
                file_id, None, client_ip, user_agent
            )
        
        # Increment download counter
        await FileManager.increment_download_count(file_id)
        
        # Get file from Telegram
        telegram_file_id = file_doc.get("telegram_file_id")
        if not telegram_file_id:
            raise HTTPException(status_code=404, detail="File source not found")
        
        # Stream file from Telegram
        file_stream = await helpers.get_telegram_file_stream(telegram_file_id)
        
        if not file_stream:
            raise HTTPException(status_code=404, detail="Failed to retrieve file")
        
        # Determine content type
        content_type = file_doc.get("content_type", "application/octet-stream")
        if not content_type or content_type == "application/octet-stream":
            content_type = mimetypes.guess_type(file_doc["file_name"])[0] or "application/octet-stream"
        
        # Prepare headers
        headers = {
            "Content-Type": content_type,
            "Content-Disposition": f'inline; filename="{quote(file_doc["file_name"])}"',
            "Cache-Control": f"public, max-age={settings.CACHE_TTL}, stale-while-revalidate=86400",
            "Accept-Ranges": "bytes",
            "ETag": f'"{file_doc["unique_code"]}"',
            "Last-Modified": datetime.fromtimestamp(file_doc["upload_time"]).strftime('%a, %d %b %Y %H:%M:%S GMT')
        }
        
        file_size = file_doc.get("file_size", 0)
        
        # Handle Range requests
        range_header = request.headers.get("range")
        if range_header:
            range_match = helpers.parse_range_header(range_header, file_size)
            if range_match:
                start, end = range_match
                content_length = end - start + 1
                
                headers.update({
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(content_length)
                })
                
                # Create partial stream
                async def partial_stream():
                    async for chunk in helpers.stream_file_range(file_stream, start, end):
                        yield chunk
                
                return StreamingResponse(
                    partial_stream(),
                    status_code=206,
                    headers=headers,
                    media_type=content_type
                )
        
        # Full file download
        headers["Content-Length"] = str(file_size)
        
        async def full_stream():
            async for chunk in file_stream:
                yield chunk
        
        return StreamingResponse(
            full_stream(),
            headers=headers,
            media_type=content_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error for {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Download failed")

@router.post("/upload")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Upload file via API endpoint
    Requires authentication for API uploads
    """
    try:
        # Basic auth check for API uploads (implement JWT/API key as needed)
        if not user_id and not credentials:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate file size
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate file extension
        file_ext = file.filename.split('.')[-1].lower() if file.filename and '.' in file.filename else ''
        if file_ext and file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Generate unique identifiers
        unique_code = helpers.generate_unique_code()
        file_id = helpers.generate_file_id()
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Save file temporarily for Telegram upload
        temp_file_path = f"/tmp/{unique_code}_{file.filename}"
        
        async with aiofiles.open(temp_file_path, 'wb') as f:
            await f.write(file_content)
        
        try:
            # Upload to Telegram channel (implement this function)
            telegram_file_id, channel_message_id = await helpers.upload_to_telegram_channel(temp_file_path, file.filename)
            
            # Create file record
            file_data = {
                "file_id": file_id,
                "unique_code": unique_code,
                "file_name": file.filename,
                "file_size": file_size,
                "content_type": file.content_type or "application/octet-stream",
                "uploader_id": user_id or 0,
                "uploader_username": "api_user",
                "telegram_file_id": telegram_file_id,
                "channel_message_id": channel_message_id,
                "file_extension": file_ext,
                "upload_method": "api"
            }
            
            await FileManager.create_file(file_data)
            
            # Generate URLs
            urls = get_file_url(file_id, unique_code)
            
            return {
                "success": True,
                "file_id": file_id,
                "unique_code": unique_code,
                "file_name": file.filename,
                "file_size": file_size,
                "urls": urls,
                "upload_time": datetime.utcnow().isoformat()
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/random")
async def get_random_file():
    """Get random file info"""
    try:
        random_file = await FileManager.get_random_file()
        
        if not random_file:
            return JSONResponse(
                status_code=404,
                content={"detail": "No files available"}
            )
        
        # Generate URLs
        urls = get_file_url(random_file["file_id"], random_file["unique_code"])
        
        return {
            "file_id": random_file["file_id"],
            "unique_code": random_file["unique_code"],
            "file_name": random_file["file_name"],
            "file_size": random_file.get("file_size", 0),
            "content_type": random_file.get("content_type", "application/octet-stream"),
            "upload_time": random_file["upload_time"],
            "download_count": random_file.get("download_count", 0),
            "urls": urls
        }
        
    except Exception as e:
        logger.error(f"Random file error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get random file")

@router.get("/search")
async def search_files(q: str, limit: int = 20):
    """Search files by name"""
    try:
        if not q or len(q.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search query too short")
        
        if limit > 100:
            limit = 100
        
        results = await FileManager.search_files(q.strip(), limit)
        
        # Format results
        formatted_results = []
        for file_doc in results:
            urls = get_file_url(file_doc["file_id"], file_doc["unique_code"])
            
            formatted_results.append({
                "file_id": file_doc["file_id"],
                "unique_code": file_doc["unique_code"],
                "file_name": file_doc["file_name"],
                "file_size": file_doc.get("file_size", 0),
                "content_type": file_doc.get("content_type", "application/octet-stream"),
                "upload_time": file_doc["upload_time"],
                "download_count": file_doc.get("download_count", 0),
                "urls": urls
            })
        
        return {
            "query": q,
            "total_results": len(results),
            "files": formatted_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/file/{unique_code}")
async def get_file_info(unique_code: str):
    """Get file information by unique code"""
    try:
        file_doc = await FileManager.get_file_by_code(unique_code)
        
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Generate URLs
        urls = get_file_url(file_doc["file_id"], file_doc["unique_code"])
        
        return {
            "file_id": file_doc["file_id"],
            "unique_code": file_doc["unique_code"],
            "file_name": file_doc["file_name"],
            "file_size": file_doc.get("file_size", 0),
            "content_type": file_doc.get("content_type", "application/octet-stream"),
            "upload_time": file_doc["upload_time"],
            "download_count": file_doc.get("download_count", 0),
            "uploader_id": file_doc.get("uploader_id"),
            "urls": urls
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file info")

@router.delete("/file/{unique_code}")
async def delete_file(
    unique_code: str,
    user_id: int = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete file (owner or admin only)"""
    try:
        # Get file info
        file_doc = await FileManager.get_file_by_code(unique_code)
        
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check permissions (owner or admin)
        from config import is_admin
        if file_doc.get("uploader_id") != user_id and not is_admin(user_id):
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Soft delete file
        success = await FileManager.delete_file(file_doc["file_id"])
        
        if success:
            return {"success": True, "message": "File deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete file")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete file error: {e}")
        raise HTTPException(status_code=500, detail="Delete failed")

@router.get("/user/{user_id}/files")
async def get_user_files(
    user_id: int,
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's uploaded files"""
    try:
        if limit > 100:
            limit = 100
        
        files = await FileManager.get_user_files(user_id, limit, skip)
        
        # Format results
        formatted_files = []
        for file_doc in files:
            urls = get_file_url(file_doc["file_id"], file_doc["unique_code"])
            
            formatted_files.append({
                "file_id": file_doc["file_id"],
                "unique_code": file_doc["unique_code"],
                "file_name": file_doc["file_name"],
                "file_size": file_doc.get("file_size", 0),
                "content_type": file_doc.get("content_type", "application/octet-stream"),
                "upload_time": file_doc["upload_time"],
                "download_count": file_doc.get("download_count", 0),
                "urls": urls
            })
        
        return {
            "user_id": user_id,
            "total_files": len(files),
            "files": formatted_files
        }
        
    except Exception as e:
        logger.error(f"User files error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user files")

@router.get("/analytics/downloads")
async def get_download_analytics(
    days: int = 7,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get download analytics (admin only)"""
    try:
        # This would need admin authentication
        if not settings.ENABLE_ANALYTICS:
            raise HTTPException(status_code=404, detail="Analytics disabled")
        
        stats = await AnalyticsManager.get_download_stats(days)
        
        return {
            "period_days": days,
            "analytics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")

# Health check for file system
@router.get("/health/files")
async def files_health_check():
    """File system health check"""
    try:
        db = await get_database()
        
        # Test database connection
        await db.command("ping")
        
        # Get basic stats
        total_files = await db.files.count_documents({"status": "active"})
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_files": total_files,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Files health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
