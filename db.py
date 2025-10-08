from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    database = None

mongodb = MongoDB()

async def connect_to_mongo():
    try:
        if not settings.MONGODB_URI:
            raise ValueError("MONGODB_URI is not set")
            
        mongodb.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            maxPoolSize=50,
            minPoolSize=10
        )
        
        # Test connection
        await mongodb.client.admin.command('ping')
        mongodb.database = mongodb.client[settings.DATABASE_NAME]
        
        # Create indexes
        await mongodb.database.files.create_index("file_id", unique=True)
        await mongodb.database.files.create_index("unique_code", unique=True)
        await mongodb.database.files.create_index("uploader_id")
        await mongodb.database.files.create_index("upload_time")
        
        # Optional TTL index (30 days)
        try:
            await mongodb.database.files.create_index(
                [("upload_time", 1)], 
                expireAfterSeconds=86400 * 30
            )
        except Exception as e:
            logger.warning(f"TTL index creation warning: {e}")
        
        await mongodb.database.users.create_index("user_id", unique=True)
        
        logger.info("Connected to MongoDB successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
        logger.info("MongoDB connection closed")

def get_database():
    return mongodb.database