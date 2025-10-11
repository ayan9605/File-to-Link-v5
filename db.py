# db.py
import motor.motor_asyncio
import redis.asyncio as redis
from bson import ObjectId
import json
from config import settings
from urllib.parse import urlparse


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.redis_client = None
        self.json_encoder = JSONEncoder()

    async def connect(self):
        """Connect to MongoDB and Redis"""
        try:
            # Connect to MongoDB
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                settings.DATABASE_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=100,
                minPoolSize=10
            )
            self.db = self.client[settings.DATABASE_NAME]

            # Test MongoDB connection
            await self.client.admin.command('ping')
            print("✅ Connected to MongoDB")

            # Create indexes
            await self.db.files.create_index("unique_code", unique=True)
            await self.db.files.create_index("file_id", unique=True)
            await self.db.files.create_index("upload_date")
            await self.db.files.create_index("user_id")
            await self.db.files.create_index([("file_name", "text")])

            # Connect to Redis
            if settings.REDIS_URL:
                # Use redis.from_url instead of Redis(...)
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    password=settings.REDIS_PASSWORD  # optional
                )
                # Test Redis connection
                await self.redis_client.ping()
                print("✅ Connected to Redis")
            else:
                print("⚠ REDIS_URL not set, skipping Redis connection")

        except Exception as e:
            print(f"❌ Database connection error: {e}")
            raise

    async def close(self):
        """Close database connections"""
        if self.client:
            self.client.close()
        if self.redis_client:
            await self.redis_client.close()

    def get_collection(self, name: str):
        """Get a collection from database"""
        return self.db[name]

    async def cache_get(self, key: str):
        """Get value from Redis cache"""
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            print(f"Redis get error: {e}")
            return None

    async def cache_set(self, key: str, value: str, ttl: int = None):
        """Set value in Redis cache"""
        try:
            if ttl is None:
                ttl = settings.REDIS_TTL
            await self.redis_client.setex(key, ttl, value)
        except Exception as e:
            print(f"Redis set error: {e}")

    async def cache_delete(self, key: str):
        """Delete key from Redis cache"""
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            print(f"Redis delete error: {e}")

    async def cache_exists(self, key: str):
        """Check if key exists in Redis cache"""
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False


# Global database instance
database = Database()