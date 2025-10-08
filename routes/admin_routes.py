from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
from datetime import datetime, timedelta
import math
import logging

from config import settings
from db import get_database

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

# Simple admin authentication (replace with proper auth in production)
def verify_admin(request: Request):
    """Verify admin access - implement proper authentication in production"""
    # For demo purposes, we'll use a simple token check
    # In production, use JWT, OAuth, or session-based authentication
    admin_token = request.headers.get("X-Admin-Token") or request.query_params.get("admin_token")
    
    # You can implement proper admin authentication here
    # For now, we'll allow access if no admin IDs are configured (development)
    if not settings.TELEGRAM_ADMIN_IDS:
        return True
        
    # In production, you would verify against a proper admin system
    return admin_token == settings.SECRET_KEY

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, is_admin: bool = Depends(verify_admin)):
    if not is_admin:
        return HTMLResponse("""
        <html>
            <head>
                <title>Access Denied</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #d32f2f; }
                </style>
            </head>
            <body>
                <h1 class="error">Access Denied</h1>
                <p>Admin authentication required.</p>
            </body>
        </html>
        """, status_code=403)
    
    return templates.TemplateResponse("admin.html", {"request": request})

@router.get("/stats")
async def get_admin_stats(is_admin: bool = Depends(verify_admin)):
    if not is_admin:
        raise HTTPException(403, "Admin access required")
    
    db = get_database()
    
    try:
        # Get basic statistics
        total_files = await db.files.count_documents({})
        total_users = len(await db.files.distinct("uploader_id"))
        
        # Total storage
        storage_pipeline = [
            {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
        ]
        total_storage_result = await db.files.aggregate(storage_pipeline).to_list(length=1)
        total_storage = total_storage_result[0]["total_size"] if total_storage_result else 0
        
        # Recent uploads (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_uploads = await db.files.count_documents({"upload_time": {"$gte": yesterday}})
        
        # Top uploaders
        top_uploaders_pipeline = [
            {"$group": {
                "_id": "$uploader_id", 
                "count": {"$sum": 1}, 
                "total_size": {"$sum": "$file_size"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        top_uploaders = await db.files.aggregate(top_uploaders_pipeline).to_list(length=10)
        
        return {
            "total_files": total_files,
            "total_users": total_users,
            "total_storage": total_storage,
            "recent_uploads": recent_uploads,
            "top_uploaders": top_uploaders
        }
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        raise HTTPException(500, "Error fetching statistics")

@router.get("/files")
async def get_files_list(
    is_admin: bool = Depends(verify_admin),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    if not is_admin:
        raise HTTPException(403, "Admin access required")
    
    db = get_database()
    
    try:
        skip = (page - 1) * per_page
        total_files = await db.files.count_documents({})
        
        files = await db.files.find(
            {},
            {"_id": 0, "file_path": 0}
        ).skip(skip).limit(per_page).sort("upload_time", -1).to_list(length=per_page)
        
        return {
            "files": files,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_files,
                "pages": math.ceil(total_files / per_page)
            }
        }
    except Exception as e:
        logger.error(f"Files list error: {e}")
        raise HTTPException(500, "Error fetching files list")

@router.delete("/files/{file_id}")
async def delete_file(file_id: str, is_admin: bool = Depends(verify_admin)):
    if not is_admin:
        raise HTTPException(403, "Admin access required")
    
    db = get_database()
    
    try:
        file_data = await db.files.find_one({"file_id": file_id})
        if not file_data:
            raise HTTPException(404, "File not found")
        
        # Delete physical file
        import os
        if os.path.exists(file_data["file_path"]):
            try:
                os.remove(file_data["file_path"])
            except Exception as e:
                logger.error(f"File deletion error: {e}")
                raise HTTPException(500, "Error deleting physical file")
        
        # Delete database record
        await db.files.delete_one({"file_id": file_id})
        
        return {"success": True, "message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete file error: {e}")
        raise HTTPException(500, "Error deleting file")

@router.get("/analytics")
async def get_analytics(
    is_admin: bool = Depends(verify_admin),
    days: int = Query(7, ge=1, le=365)
):
    if not is_admin:
        raise HTTPException(403, "Admin access required")
    
    db = get_database()
    
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily uploads
        daily_uploads_pipeline = [
            {"$match": {"upload_time": {"$gte": start_date}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$upload_time"}},
                "count": {"$sum": 1},
                "total_size": {"$sum": "$file_size"}
            }},
            {"$sort": {"_id": 1}}
        ]
        daily_uploads = await db.files.aggregate(daily_uploads_pipeline).to_list(length=days)
        
        # File type distribution
        file_types_pipeline = [
            {"$group": {
                "_id": "$mime_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        file_types = await db.files.aggregate(file_types_pipeline).to_list(length=10)
        
        return {
            "daily_uploads": daily_uploads,
            "file_types": file_types
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(500, "Error fetching analytics")