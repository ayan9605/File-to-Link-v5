# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import uvicorn
import time
import asyncio

from config import settings
from db import database
from routes.file_routes import router as file_router
from routes.admin_routes import router as admin_router
from pyro_client import start_pyro_client, stop_pyro_client

# Initialize FastAPI app
app = FastAPI(
    title="FileToLink System v8.0",
    description="High-performance file sharing using Telegram as backend with Redis caching",
    version="8.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(file_router)
app.include_router(admin_router, prefix="/admin/api")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Connect to database and Redis
        await database.connect()
        
        # Start Pyrogram client
        await start_pyro_client()
        
        print("✅ FileToLink System v8.0 started successfully")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await stop_pyro_client()
    await database.close()
    print("✅ FileToLink system shutdown complete")

@app.get("/")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def root(request: Request):
    """Health check endpoint"""
    return {
        "status": "active",
        "service": "FileToLink System",
        "version": "8.0.0",
        "timestamp": time.time()
    }

@app.get("/health")
async def health_check():
    """Advanced health check that verifies all services"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {}
    }
    
    try:
        # Check MongoDB
        await database.client.admin.command('ping')
        health_status["services"]["mongodb"] = "healthy"
    except Exception as e:
        health_status["services"]["mongodb"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        # Check Redis
        await database.redis_client.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        # Check Pyrogram client
        from pyro_client import get_pyro_client
        client = await get_pyro_client()
        if client and client.is_connected:
            health_status["services"]["pyrogram"] = "healthy"
        else:
            health_status["services"]["pyrogram"] = "unhealthy: client not connected"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["pyrogram"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Serve admin panel"""
    return templates.TemplateResponse("admin.html", {"request": request})

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )