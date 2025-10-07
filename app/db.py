"""
Async MongoDB Database Management with Motor
Handles all database operations and connections
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING
from bson import ObjectId
import certifi

from config import settings

logger = logging.getLogger(__name__)

# Global database connection
_database: Optional[AsyncIOMotorDatabase] = None
_client: Optional[AsyncIOMotorClient] = None

async def connect_to_mongo():
    """Create MongoDB connection"""
    global _client, _database
    
    try:
        # Create MongoDB client with SSL certificate verification
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where() if settings.MONGODB_URL.startswith("mongodb+srv://") else None
        )
        
        # Get database
        _database = _client[settings.DATABASE_NAME]
        
        # Test connection
        await _client.admin.command('ping')
        logger.info(f"✅ Connected to MongoDB: {settings.DATABASE_NAME}")
        
        return _database
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection"""
    global _client
    if _client:
        _client.close()
        logger.info("🔴 MongoDB connection closed")

async def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    global _database
    if _database is None:
        _database = await connect_to_mongo()
    return _database

# Database initialization
async def init_database():
    """Initialize database with indexes and collections"""
    db = await get_database()
    
    # Create indexes for files collection
    files_indexes = [
        IndexModel([("file_id", ASCENDING)], unique=True),
        IndexModel([("unique_code", ASCENDING)], unique=True),
        IndexModel([("uploader_id", ASCENDING)]),
        IndexModel([("upload_time", DESCENDING)]),
        IndexModel([("file_name", "text")]),  # Text search index
        IndexModel([("content_type", ASCENDING)]),
    ]
    
    # TTL index for temporary files (if enabled)
    if settings.ENABLE_FILE_TTL:
        ttl_seconds = settings.FILE_TTL_DAYS * 24 * 60 * 60
        files_indexes.append(
            IndexModel([("upload_time", ASCENDING)], expireAfterSeconds=ttl_seconds)
        )
    
    await db.files.create_indexes(files_indexes)
    
    # Create indexes for users collection
    users_indexes = [
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("username", ASCENDING)]),
        IndexModel([("join_date", DESCENDING)]),
        IndexModel([("last_activity", DESCENDING)]),
    ]
    
    await db.users.create_indexes(users_indexes)
    
    # Create indexes for analytics collection
    if settings.ENABLE_ANALYTICS:
        analytics_indexes = [
            IndexModel([("file_id", ASCENDING)]),
            IndexModel([("download_time", DESCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("ip_address", ASCENDING)]),
        ]
        
        # TTL index for analytics (30 days)
        analytics_indexes.append(
            IndexModel([("download_time", ASCENDING)], expireAfterSeconds=2592000)
        )
        
        await db.analytics.create_indexes(analytics_indexes)
    
    # Create indexes for admin logs
    admin_logs_indexes = [
        IndexModel([("admin_id", ASCENDING)]),
        IndexModel([("action", ASCENDING)]),
        IndexModel([("timestamp", DESCENDING)]),
    ]
    
    # TTL index for admin logs (90 days)
    admin_logs_indexes.append(
        IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=7776000)
    )
    
    await db.admin_logs.create_indexes(admin_logs_indexes)
    
    logger.info("📦 Database indexes created successfully")

# File operations
class FileManager:
    """Async file database operations"""
    
    @staticmethod
    async def create_file(file_data: Dict[str, Any]) -> str:
        """Create new file record"""
        db = await get_database()
        
        # Add timestamp
        file_data["upload_time"] = datetime.utcnow().timestamp()
        file_data["download_count"] = 0
        file_data["status"] = "active"
        
        result = await db.files.insert_one(file_data)
        logger.info(f"📁 File created: {file_data.get('file_name')} by {file_data.get('uploader_id')}")
        
        return str(result.inserted_id)
    
    @staticmethod
    async def get_file_by_id(file_id: str, unique_code: str) -> Optional[Dict[str, Any]]:
        """Get file by ID and unique code"""
        db = await get_database()
        
        file_doc = await db.files.find_one({
            "file_id": file_id,
            "unique_code": unique_code,
            "status": "active"
        })
        
        return file_doc
    
    @staticmethod
    async def get_file_by_code(unique_code: str) -> Optional[Dict[str, Any]]:
        """Get file by unique code only"""
        db = await get_database()
        
        file_doc = await db.files.find_one({
            "unique_code": unique_code,
            "status": "active"
        })
        
        return file_doc
    
    @staticmethod
    async def increment_download_count(file_id: str):
        """Increment file download counter"""
        db = await get_database()
        
        await db.files.update_one(
            {"file_id": file_id},
            {
                "$inc": {"download_count": 1},
                "$set": {"last_downloaded": datetime.utcnow().timestamp()}
            }
        )
    
    @staticmethod
    async def get_random_file() -> Optional[Dict[str, Any]]:
        """Get random file using aggregation"""
        db = await get_database()
        
        cursor = db.files.aggregate([
            {"$match": {"status": "active"}},
            {"$sample": {"size": 1}}
        ])
        
        async for doc in cursor:
            return doc
        
        return None
    
    @staticmethod
    async def get_user_files(user_id: int, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get user's uploaded files"""
        db = await get_database()
        
        cursor = db.files.find(
            {"uploader_id": user_id, "status": "active"},
            sort=[("upload_time", DESCENDING)],
            limit=limit,
            skip=skip
        )
        
        return await cursor.to_list(length=limit)
    
    @staticmethod
    async def delete_file(file_id: str) -> bool:
        """Soft delete file"""
        db = await get_database()
        
        result = await db.files.update_one(
            {"file_id": file_id},
            {
                "$set": {
                    "status": "deleted",
                    "deleted_at": datetime.utcnow().timestamp()
                }
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def search_files(query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search files by name"""
        db = await get_database()
        
        cursor = db.files.find(
            {
                "$text": {"$search": query},
                "status": "active"
            },
            sort=[("score", {"$meta": "textScore"})],
            limit=limit
        )
        
        return await cursor.to_list(length=limit)

# User operations
class UserManager:
    """Async user database operations"""
    
    @staticmethod
    async def create_or_update_user(user_data: Dict[str, Any]) -> str:
        """Create or update user record"""
        db = await get_database()
        
        user_id = user_data["user_id"]
        current_time = datetime.utcnow().timestamp()
        
        # Check if user exists
        existing_user = await db.users.find_one({"user_id": user_id})
        
        if existing_user:
            # Update existing user
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        **user_data,
                        "last_activity": current_time
                    }
                }
            )
            return str(existing_user["_id"])
        else:
            # Create new user
            user_data.update({
                "join_date": current_time,
                "last_activity": current_time,
                "total_uploads": 0,
                "total_downloads": 0,
                "is_blocked": False
            })
            
            result = await db.users.insert_one(user_data)
            logger.info(f"👤 New user registered: {user_data.get('username', 'Unknown')} ({user_id})")
            
            return str(result.inserted_id)
    
    @staticmethod
    async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        db = await get_database()
        return await db.users.find_one({"user_id": user_id})
    
    @staticmethod
    async def block_user(user_id: int, blocked_by: int) -> bool:
        """Block user"""
        db = await get_database()
        
        result = await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "is_blocked": True,
                    "blocked_at": datetime.utcnow().timestamp(),
                    "blocked_by": blocked_by
                }
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def unblock_user(user_id: int) -> bool:
        """Unblock user"""
        db = await get_database()
        
        result = await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"is_blocked": False},
                "$unset": {"blocked_at": "", "blocked_by": ""}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def get_users_list(limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get paginated users list"""
        db = await get_database()
        
        cursor = db.users.find(
            {},
            sort=[("join_date", DESCENDING)],
            limit=limit,
            skip=skip
        )
        
        return await cursor.to_list(length=limit)

# Analytics operations
class AnalyticsManager:
    """Async analytics database operations"""
    
    @staticmethod
    async def log_download(file_id: str, user_id: Optional[int], ip_address: str, user_agent: str):
        """Log file download"""
        if not settings.ENABLE_ANALYTICS:
            return
        
        db = await get_database()
        
        analytics_data = {
            "file_id": file_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "download_time": datetime.utcnow().timestamp()
        }
        
        await db.analytics.insert_one(analytics_data)
    
    @staticmethod
    async def get_download_stats(days: int = 7) -> Dict[str, Any]:
        """Get download statistics"""
        db = await get_database()
        
        start_time = (datetime.utcnow() - timedelta(days=days)).timestamp()
        
        # Total downloads in period
        total_downloads = await db.analytics.count_documents({
            "download_time": {"$gte": start_time}
        })
        
        # Top files
        top_files_pipeline = [
            {"$match": {"download_time": {"$gte": start_time}}},
            {"$group": {"_id": "$file_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        top_files = await db.analytics.aggregate(top_files_pipeline).to_list(10)
        
        # Daily breakdown
        daily_pipeline = [
            {"$match": {"download_time": {"$gte": start_time}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": {"$toDate": {"$multiply": ["$download_time", 1000]}}
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_stats = await db.analytics.aggregate(daily_pipeline).to_list(days)
        
        return {
            "total_downloads": total_downloads,
            "top_files": top_files,
            "daily_stats": daily_stats
        }

# Admin operations
class AdminManager:
    """Async admin database operations"""
    
    @staticmethod
    async def log_admin_action(admin_id: int, action: str, details: Dict[str, Any]):
        """Log admin action"""
        db = await get_database()
        
        log_data = {
            "admin_id": admin_id,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().timestamp()
        }
        
        await db.admin_logs.insert_one(log_data)
        logger.info(f"🔧 Admin action logged: {action} by {admin_id}")
    
    @staticmethod
    async def get_admin_logs(limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Get admin logs"""
        db = await get_database()
        
        cursor = db.admin_logs.find(
            {},
            sort=[("timestamp", DESCENDING)],
            limit=limit,
            skip=skip
        )
        
        return await cursor.to_list(length=limit)
    
    @staticmethod
    async def get_system_stats() -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        db = await get_database()
        
        # File stats
        total_files = await db.files.count_documents({"status": "active"})
        total_deleted = await db.files.count_documents({"status": "deleted"})
        
        # User stats
        total_users = await db.users.count_documents({})
        blocked_users = await db.users.count_documents({"is_blocked": True})
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow().timestamp() - 86400
        recent_uploads = await db.files.count_documents({
            "upload_time": {"$gte": yesterday},
            "status": "active"
        })
        
        recent_users = await db.users.count_documents({
            "last_activity": {"$gte": yesterday}
        })
        
        # Storage calculation (approximate)
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
        ]
        
        storage_result = await db.files.aggregate(pipeline).to_list(1)
        total_storage = storage_result[0]["total_size"] if storage_result else 0
        
        return {
            "files": {
                "total": total_files,
                "deleted": total_deleted,
                "recent_uploads": recent_uploads
            },
            "users": {
                "total": total_users,
                "blocked": blocked_users,
                "recent_active": recent_users
            },
            "storage": {
                "total_bytes": total_storage,
                "total_mb": round(total_storage / (1024 * 1024), 2),
                "total_gb": round(total_storage / (1024 * 1024 * 1024), 2)
            }
        }