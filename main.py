from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import time
import logging
import os
from contextlib import asynccontextmanager

from config import settings
from db import connect_to_mongo, close_mongo_connection
from utils.helpers import limiter
from routes import file_routes, admin_routes
from bot import telegram_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await connect_to_mongo()
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        # Don't raise, allow app to start without DB for health checks
    
    try:
        if settings.TELEGRAM_BOT_TOKEN:
            await telegram_bot.initialize()
            
            # Set webhook in production
            if settings.RENDER_URL and settings.RENDER_URL != "http://localhost:8000":
                await telegram_bot.set_webhook(settings.RENDER_URL)
            logger.info("Telegram bot initialized successfully")
        else:
            logger.warning("No Telegram bot token provided, bot features disabled")
    except Exception as e:
        logger.error(f"Telegram bot initialization failed: {e}")
    
    logger.info("Application started successfully")
    yield
    
    # Shutdown
    await close_mongo_connection()
    logger.info("Application shutdown")

app = FastAPI(
    title="FileToLink System", 
    version="5.0",
    lifespan=lifespan
)

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add more specific CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- CORRECTED ROUTING ---
# Include routers
app.include_router(admin_routes.router, prefix="/admin")
app.include_router(file_routes.router, prefix="/api/v1") # For API-specific routes
app.include_router(file_routes.router, tags=["Direct Downloads"]) # For direct /dl links

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook"""
    if not settings.TELEGRAM_BOT_TOKEN:
        return JSONResponse(
            status_code=501,
            content={"status": "error", "message": "Telegram bot not configured"}
        )
    
    try:
        json_data = await request.json()
        
        from telegram import Update
        update = Update.de_json(json_data, telegram_bot.application.bot)
        
        await telegram_bot.application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/")
async def root():
    return {
        "message": "FileToLink System v5.0", 
        "status": "active",
        "features": [
            "Triple link generation",
            "Telegram bot integration", 
            "Admin dashboard",
            "File streaming",
            "Rate limiting"
        ],
        "endpoints": {
            "upload": "/api/v1/upload",
            "download_api": "/api/v1/dl/{file_id}",
            "download_direct": "/dl/{file_id}",
            "random": "/api/v1/random",
            "admin": "/admin",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    from db import mongodb
    db_status = "connected" if mongodb.client else "disconnected"
    bot_status = "connected" if telegram_bot.application else "disconnected"
    
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "database": db_status,
        "telegram_bot": bot_status,
        "version": "5.0"
    }

@app.get("/test-routes")
async def test_routes():
    """Test all download routes"""
    return {
        "api_route": "/api/v1/dl/{file_id}?code={code}",
        "direct_route": "/dl/{file_id}?code={code}",
        "cdn_route": f"{settings.CLOUDFLARE_WORKER_URL}/dl/{{file_id}}?code={{code}}",
        "render_route": f"{settings.RENDER_URL}/dl/{{file_id}}?code={{code}}",
        "bot_route": f"https://t.me/{settings.BOT_USERNAME}?start={{code}}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
