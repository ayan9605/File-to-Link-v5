# routes/admin_routes.py
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import secrets
from typing import Dict, Any
import json
from bson import ObjectId

from config import settings
from db import database

router = APIRouter(tags=["admin"])

# Simple session storage (use Redis in production)
admin_sessions = {}

def verify_admin_auth(request: Request):
    """Verify admin authentication"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = auth_header[7:]
    if token not in admin_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return admin_sessions[token]

@router.post("/auth/login")
async def admin_login(request: Request):
    """Admin login endpoint"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        if (username == settings.ADMIN_USERNAME and 
            password == settings.ADMIN_PASSWORD):
            
            # Generate session token
            token = secrets.token_urlsafe(32)
            admin_sessions[token] = {
                "username": username,
                "login_time": datetime.utcnow()
            }
            
            return {
                "status": "success",
                "token": token,
                "message": "Login successful"
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid request")

@router.post("/auth/logout")
async def admin_logout(request: Request, admin: Dict = Depends(verify_admin_auth)):
    """Admin logout endpoint"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:]
    
    if token in admin_sessions:
        del admin_sessions[token]
    
    return {"status": "success", "message": "Logout successful"}

@router.get("/stats")
async def get_stats(admin: Dict = Depends(verify_admin_auth)):
    """Get comprehensive system statistics"""
    try:
        files_collection = database.get_collection("files")
        
        # Total files count
        total_files = await files_collection.count_documents({})
        
        # Total downloads
        total_downloads_cursor = files_collection.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$download_count"}}}
        ])
        total_downloads_result = await total_downloads_cursor.to_list(length=1)
        total_downloads = total_downloads_result[0]["total"] if total_downloads_result else 0
        
        # Storage used
        storage_cursor = files_collection.aggregate([
            {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
        ])
        storage_result = await storage_cursor.to_list(length=1)
        total_storage = storage_result[0]["total_size"] if storage_result else 0
        
        # Recent uploads (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_uploads = await files_collection.count_documents({
            "upload_date": {"$gte": yesterday}
        })
        
        # Recent downloads (last 24 hours)
        recent_downloads_cursor = files_collection.aggregate([
            {"$match": {"last_downloaded": {"$gte": yesterday}}},
            {"$group": {"_id": None, "count": {"$sum": "$download_count"}}}
        ])
        recent_downloads_result = await recent_downloads_cursor.to_list(length=1)
        recent_downloads = recent_downloads_result[0]["count"] if recent_downloads_result else 0
        
        # Unique users
        unique_users_cursor = files_collection.aggregate([
            {"$group": {"_id": "$user_id"}},
            {"$count": "total"}
        ])
        unique_users_result = await unique_users_cursor.to_list(length=1)
        unique_users = unique_users_result[0]["total"] if unique_users_result else 0
        
        # Redis cache stats
        try:
            redis_info = await database.redis_client.info("memory")
            redis_memory = redis_info.get("used_memory_human", "N/A")
        except Exception as e:
            print(f"Redis info error: {e}")
            redis_memory = "N/A"
        
        return {
            "status": "success",
            "data": {
                "total_files": total_files,
                "total_downloads": total_downloads,
                "total_storage": total_storage,
                "recent_uploads": recent_uploads,
                "recent_downloads": recent_downloads,
                "unique_users": unique_users,
                "redis_memory": redis_memory,
                "cache_ttl": settings.REDIS_TTL
            }
        }
    
    except Exception as e:
        print(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")

@router.get("/files")
async def get_files_list(
    admin: Dict = Depends(verify_admin_auth),
    page: int = 1,
    limit: int = 50,
    search: str = None
):
    """Get paginated files list"""
    try:
        files_collection = database.get_collection("files")
        
        # Build query
        query = {}
        if search:
            query["$or"] = [
                {"file_name": {"$regex": search, "$options": "i"}},
                {"unique_code": {"$regex": search, "$options": "i"}},
                {"user_name": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await files_collection.count_documents(query)
        
        # Get paginated files
        skip = (page - 1) * limit
        files_cursor = files_collection.find(query).sort("upload_date", -1).skip(skip).limit(limit)
        files = await files_cursor.to_list(length=limit)
        
        # Clean up data for response
        for file in files:
            file["_id"] = str(file["_id"])
            # Keep channel_id and message_id for internal use but don't expose to frontend
            if "channel_id" in file:
                del file["channel_id"]
            if "message_id" in file:
                del file["message_id"]
        
        return {
            "status": "success",
            "data": {
                "files": files,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        }
    
    except Exception as e:
        print(f"Files list error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving files list")

@router.delete("/files/{file_id}")
async def delete_file(file_id: str, admin: Dict = Depends(verify_admin_auth)):
    """Delete a file from database and clear cache"""
    try:
        files_collection = database.get_collection("files")
        
        # Find file
        file_data = await files_collection.find_one({"file_id": file_id})
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Clear Redis cache
        cache_key = f"file:{file_id}:{file_data['unique_code']}"
        await database.cache_delete(cache_key)
        
        # Delete from database
        result = await files_collection.delete_one({"file_id": file_id})
        
        if result.deleted_count == 1:
            return {
                "status": "success",
                "message": "File deleted from database and cache cleared."
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete file")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete file error: {e}")
        raise HTTPException(status_code=500, detail="Error deleting file")

@router.get("/charts")
async def get_chart_data(admin: Dict = Depends(verify_admin_auth)):
    """Get data for charts"""
    try:
        files_collection = database.get_collection("files")
        
        # Uploads per day (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        uploads_pipeline = [
            {"$match": {"upload_date": {"$gte": seven_days_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$upload_date"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        downloads_pipeline = [
            {"$match": {"last_downloaded": {"$gte": seven_days_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$last_downloaded"}},
                "count": {"$sum": "$download_count"}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        file_types_pipeline = [
            {"$group": {
                "_id": "$file_type",
                "count": {"$sum": 1}
            }}
        ]
        
        top_files_pipeline = [
            {"$sort": {"download_count": -1}},
            {"$limit": 10},
            {"$project": {
                "file_name": 1,
                "download_count": 1,
                "file_size": 1
            }}
        ]
        
        uploads_data = await files_collection.aggregate(uploads_pipeline).to_list(length=None)
        downloads_data = await files_collection.aggregate(downloads_pipeline).to_list(length=None)
        file_types_data = await files_collection.aggregate(file_types_pipeline).to_list(length=None)
        top_files_data = await files_collection.aggregate(top_files_pipeline).to_list(length=None)
        
        return {
            "status": "success",
            "data": {
                "uploads_over_time": uploads_data,
                "downloads_over_time": downloads_data,
                "file_types": file_types_data,
                "top_files": top_files_data
            }
        }
    
    except Exception as e:
        print(f"Charts data error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving chart data")