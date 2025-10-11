# config.py
import os
from typing import Optional

from pydantic_settings import BaseSettings  # ✅ moved here in Pydantic v2
from pydantic import field_validator        # ✅ updated import (replaces validator in v2)


class Settings(BaseSettings):
    # Telegram Configuration
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    PRIVATE_CHANNEL_ID: int

    # MongoDB Configuration
    MONGODB_URL: str
    DATABASE_NAME: str = "filetolink"

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TTL: int = 300  # 5 minutes default

    # Server Configuration
    RENDER_URL: str
    CLOUDFLARE_WORKER_URL: str
    BOT_USERNAME: str

    # Security
    SECRET_KEY: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Performance Settings
    MAX_WORKERS: int = 4
    WORKER_TIMEOUT: int = 120

    # Derived settings
    @property
    def DATABASE_URI(self) -> str:
        return self.MONGODB_URL

    # ✅ Updated decorator for Pydantic v2
    @field_validator('REDIS_TTL')
    def validate_redis_ttl(cls, v):
        if v < 60:
            raise ValueError('REDIS_TTL must be at least 60 seconds')
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()