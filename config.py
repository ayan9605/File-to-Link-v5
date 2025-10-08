import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "filetolink")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Parse admin IDs safely
    admin_ids = os.getenv("TELEGRAM_ADMIN_IDS", "")
    TELEGRAM_ADMIN_IDS = [int(x.strip()) for x in admin_ids.split(",") if x.strip() and x.strip().isdigit()]
    
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    RENDER_URL = os.getenv("RENDER_URL", "http://localhost:8000")
    CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL", "http://localhost:8000")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "")
    PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0")) if os.getenv("PRIVATE_CHANNEL_ID") else 0
    API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "5368709120"))  # 5GB default
    
    ALLOWED_EXTENSIONS = {
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        'videos': ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
        'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz']
    }

settings = Settings()