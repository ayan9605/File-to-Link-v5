"""
FastAPI Main Application - File-To-Link System
High-performance async file sharing backend with triple link generation
"""

from fastapi import FastAPI, Request, HTTPException, Depends, status, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import asyncio
import uvicorn
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import time

from config import settings
from db import get_database, init_database
from routes.file_routes import router as file_router
from routes.admin_routes import router as admin_router
from bot import setup_bot, get_application
import utils.helpers as helpers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# FastAPI lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting FastAPI File-To-Link System...")
    
    # Initialize database
    await init_database()
    logger.info("📦 MongoDB initialized successfully")
    
    # Setup Telegram bot
    await setup_bot()
    logger.info("🤖 Telegram bot initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("🔴 Shutting down application...")
    app_instance = get_application()
    if app_instance:
        await app_instance.stop()
        await app_instance.shutdown()

# Initialize FastAPI app
app = FastAPI(
    title="File-To-Link System V5",
    description="Production-ready file sharing backend with triple link generation",
    version="5.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Security
security = HTTPBearer()

# Middleware setup
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Basic rate limiting per IP"""
    client_ip = request.client.host
    current_time = time.time()
    
    # Simple in-memory rate limiting (for production, use Redis)
    if not hasattr(app, 'rate_limit_storage'):
        app.rate_limit_storage = {}
    
    if client_ip in app.rate_limit_storage:
        requests, first_request_time = app.rate_limit_storage[client_ip]
        
        # Reset counter if window expired
        if current_time - first_request_time > 60:  # 1-minute window
            app.rate_limit_storage[client_ip] = (1, current_time)
        else:
            # Check if limit exceeded
            if requests >= settings.RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."}
                )
            app.rate_limit_storage[client_ip] = (requests + 1, first_request_time)
    else:
        app.rate_limit_storage[client_ip] = (1, current_time)
    
    response = await call_next(request)
    return response

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(file_router, prefix="/api", tags=["files"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🚀 File-To-Link System V5 - Production Ready",
        "version": "5.0.0",
        "status": "active",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/api/docs" if settings.DEBUG else "Contact admin for API documentation"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db = await get_database()
        await db.command("ping")
        
        # Check bot status
        bot_app = get_application()
        bot_status = "running" if bot_app and bot_app.running else "stopped"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "bot": bot_status,
            "version": "5.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/stats")
async def get_public_stats():
    """Public statistics endpoint"""
    try:
        db = await get_database()
        
        # Get basic stats
        total_files = await db.files.count_documents({})
        total_users = await db.users.count_documents({})
        
        # Get recent uploads (last 24 hours)
        yesterday = datetime.utcnow().timestamp() - 86400
        recent_uploads = await db.files.count_documents({
            "upload_time": {"$gte": yesterday}
        })
        
        return {
            "total_files": total_files,
            "total_users": total_users,
            "recent_uploads_24h": recent_uploads,
            "system_status": "operational",
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Stats endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

@app.post("/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, request: Request, background_tasks: BackgroundTasks):
    """Telegram webhook endpoint"""
    if bot_token != settings.BOT_TOKEN.split(':')[-1]:
        raise HTTPException(status_code=403, detail="Invalid bot token")
    
    try:
        # Get update data
        update_data = await request.json()
        logger.info(f"Received webhook update: {update_data.get('update_id', 'unknown')}")
        
        # Process update in background
        bot_app = get_application()
        if bot_app:
            background_tasks.add_task(
                bot_app.process_update,
                bot_app.bot.de_json(update_data, bot_app.bot)
            )
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return JSONResponse(status_code=200, content={"status": "error"})

# Custom exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(settings.PORT),
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
        server_header=False,
        date_header=False
    )
