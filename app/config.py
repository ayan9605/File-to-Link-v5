"""
Configuration Management with Environment Variables
Handles all application settings and secrets
"""

import os
from typing import List
from pydantic import BaseSettings, validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Server Configuration
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "filetolinkv5")
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "0"))  # Private channel for file storage
    
    # Admin Configuration
    ADMIN_USER_IDS: List[int] = []
    SUPER_ADMIN_ID: int = int(os.getenv("SUPER_ADMIN_ID", "0"))
    WEB_ADMIN_SECRET: str = os.getenv("WEB_ADMIN_SECRET", "admin123")
    
    # File Configuration
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "2147483648"))  # 2GB
    ALLOWED_EXTENSIONS: List[str] = []
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    
    # Security Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-this")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # URL Configuration
    BASE_URL: str = os.getenv("BASE_URL", "https://filetolinkv5.onrender.com")
    CLOUDFLARE_URL: str = os.getenv("CLOUDFLARE_URL", "https://filetolinkv5.username.workers.dev")
    
    # CORS and Security
    CORS_ORIGINS: List[str] = []
    ALLOWED_HOSTS: List[str] = []
    
    # Feature Flags
    ENABLE_FILE_TTL: bool = os.getenv("ENABLE_FILE_TTL", "False").lower() == "true"
    FILE_TTL_DAYS: int = int(os.getenv("FILE_TTL_DAYS", "30"))
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "True").lower() == "true"
    
    # Cache Configuration
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    
    @validator("ADMIN_USER_IDS", pre=True)
    def parse_admin_ids(cls, v):
        """Parse admin user IDs from comma-separated string"""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return v or []
    
    @validator("ALLOWED_EXTENSIONS", pre=True)
    def parse_extensions(cls, v):
        """Parse allowed extensions from comma-separated string"""
        if isinstance(v, str):
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        return v or ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "zip", "rar", "mp4", "mp3", "txt"]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or ["*"]
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from comma-separated string"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or ["*"]
    
    @validator("BOT_TOKEN")
    def validate_bot_token(cls, v):
        """Validate bot token format"""
        if not v or ":" not in v:
            raise ValueError("Invalid bot token format")
        return v
    
    @validator("WEBHOOK_URL")
    def build_webhook_url(cls, v, values):
        """Build webhook URL if not provided"""
        if not v and "BASE_URL" in values and "BOT_TOKEN" in values:
            token_part = values["BOT_TOKEN"].split(":")[-1]
            return f"{values['BASE_URL']}/webhook/{token_part}"
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# Initialize settings
settings = Settings()

# Validate critical settings
def validate_settings():
    """Validate critical settings before app startup"""
    errors = []
    
    if not settings.BOT_TOKEN:
        errors.append("BOT_TOKEN is required")
    
    if not settings.MONGODB_URL:
        errors.append("MONGODB_URL is required")
    
    if not settings.CHANNEL_ID:
        errors.append("CHANNEL_ID is required for file storage")
    
    if not settings.SUPER_ADMIN_ID:
        errors.append("SUPER_ADMIN_ID is required")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

# Additional helper functions
def get_file_url(file_id: str, unique_code: str) -> dict:
    """Generate all three download URLs for a file"""
    return {
        "cloudflare": f"{settings.CLOUDFLARE_URL}/dl/{file_id}?code={unique_code}",
        "render": f"{settings.BASE_URL}/api/dl/{file_id}?code={unique_code}",
        "bot": f"https://t.me/{settings.BOT_USERNAME}?start={unique_code}"
    }

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == settings.SUPER_ADMIN_ID or user_id in settings.ADMIN_USER_IDS

def is_super_admin(user_id: int) -> bool:
    """Check if user is super admin"""
    return user_id == settings.SUPER_ADMIN_ID