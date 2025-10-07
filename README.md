# FastAPI + Telegram Bot File-To-Link System V5

## 🚀 Complete Production-Ready File Sharing Backend

A high-performance, async file-to-link delivery system with **triple link generation**, **dual admin panels**, and **CDN integration**.

---

## ✨ Key Features

### 🔗 Triple Link Generation
Each uploaded file automatically generates **3 working download links**:
1. **⚡ Cloudflare Worker** → Rocket-fast CDN cached downloads
2. **🌐 Render (Origin)** → Standard server downloads  
3. **🤖 Bot Direct Access** → File streamed from private Telegram channel

### 🎛️ Dual Admin Panels
1. **📱 Telegram Bot Admin Panel** - In-bot admin interface with user management
2. **💻 Web Admin Dashboard** - Modern responsive web interface with analytics

### 🚀 Performance Features
- **Async everything** - FastAPI (ASGI) + Motor + python-telegram-bot v21+
- **Streaming downloads** - Chunked transfer for large files (>200MB)
- **HTTP Range support** - Media player compatibility  
- **CDN caching** - Cloudflare Worker with intelligent caching
- **Rate limiting** - Per-IP protection against abuse
- **Auto-scaling** - Handles >100 concurrent operations

---

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Cloudflare    │    │    Render.com    │    │   MongoDB       │
│     Worker      │◄──►│   (FastAPI)      │◄──►│    Atlas        │
│   (CDN Cache)   │    │                  │    │  (Database)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                        ▲                        
         │                        │                        
         ▼                        ▼                        
┌─────────────────┐    ┌──────────────────┐              
│     Users       │    │   Telegram Bot   │              
│  (Download)     │    │  (File Upload)   │              
└─────────────────┘    └──────────────────┘              
```

---

## 📂 Project Structure

```
/app/
├── main.py                    # FastAPI app, routes, middleware
├── bot.py                     # Telegram bot (webhook, admin panel)  
├── db.py                      # MongoDB connection (Motor, async)
├── config.py                  # Environment variables handler
├── requirements.txt           # Python dependencies
├── Procfile                   # Render deployment
├── render.yaml               # Render configuration
├── .env.example              # Environment template
├── worker.js                 # Cloudflare Worker (CDN proxy)
├── routes/
│   ├── file_routes.py        # /dl, /upload, /random endpoints
│   └── admin_routes.py       # Web admin panel endpoints
├── utils/
│   └── helpers.py            # Security, file handling utilities
├── templates/
│   ├── admin_dashboard.html  # Web admin interface
│   ├── login.html           # Admin login page
│   ├── file_management.html # File management UI
│   └── user_management.html # User management UI
└── static/
    ├── admin.css            # Modern dark theme styles
    └── admin.js             # Admin panel JavaScript
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.11+
- MongoDB Atlas account
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Cloudflare account (for CDN)
- Render.com account (for hosting)

### 2. Environment Setup

Copy `.env.example` to `.env` and configure:

```bash
# Database
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=filetolinkv5

# Telegram Bot  
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
BOT_USERNAME=your_bot_username
CHANNEL_ID=-1001234567890  # Private channel for storage

# Admin
SUPER_ADMIN_ID=123456789  # Your Telegram user ID
WEB_ADMIN_SECRET=your_secure_password

# URLs
BASE_URL=https://filetolinkv5.onrender.com
CLOUDFLARE_URL=https://filetolinkv5.username.workers.dev

# Security
SECRET_KEY=your_super_secret_key_here_32_chars_min
```

### 3. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app --reload --port 8000

# Set webhook (replace with your ngrok URL for testing)
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://yourapp.ngrok.io/webhook/{BOT_TOKEN_SUFFIX}"}'
```

---

## 🚀 Deployment Guide

### Option 1: Render.com (Recommended)

1. **Fork this repository** to your GitHub
2. **Connect to Render.com** and create a new web service
3. **Set environment variables** in Render dashboard:
   - `MONGODB_URL` - Your MongoDB Atlas connection string
   - `BOT_TOKEN` - From @BotFather  
   - `BOT_USERNAME` - Your bot username
   - `CHANNEL_ID` - Private channel ID for file storage
   - `SUPER_ADMIN_ID` - Your Telegram user ID
   - `SECRET_KEY` - Generate a secure random string
   - `WEB_ADMIN_SECRET` - Admin panel password
4. **Deploy** - Render will automatically build and deploy

### Option 2: Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with production server
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Cloudflare Worker Setup

1. Create a new Cloudflare Worker
2. Replace the worker code with `worker.js`
3. Update `BACKEND_URL` to your deployed API URL
4. Set up custom domain (optional): `filetolinkv5.yourdomain.com`

---

## 🎯 Usage Guide

### 📤 File Upload (Telegram Bot)

1. Start your bot: `/start`  
2. Send any file (document, photo, video, audio)
3. Bot processes and generates **3 download links**:
   - ⚡ **Fast**: `https://filetolinkv5.username.workers.dev/dl/{id}?code={code}`
   - 🌐 **Normal**: `https://filetolinkv5.onrender.com/api/dl/{id}?code={code}`  
   - 🤖 **Bot**: `https://t.me/your_bot?start={code}`

### 📥 File Download

**Method 1: Direct Links**
```bash
curl -L "https://filetolinkv5.onrender.com/api/dl/{file_id}?code={unique_code}"
```

**Method 2: Bot Access**
- Start bot with code: `/start {unique_code}`
- Bot sends file directly from private channel

**Method 3: API Upload**
```bash
curl -X POST "https://filetolinkv5.onrender.com/api/upload" \
     -H "Authorization: Bearer your_token" \
     -F "file=@document.pdf" \
     -F "user_id=123456789"
```

---

## 🎛️ Admin Panel Features

### 📱 Telegram Bot Admin Panel

Access via `/admin` command (admin only):

- **📊 System Statistics** - Files, users, storage, downloads
- **👥 User Management** - Block/unblock users, view activity  
- **📁 File Management** - Delete files, view downloads
- **📢 Broadcast Messages** - Send announcements to all users
- **📋 Activity Logs** - Monitor all admin actions
- **⚙️ Settings** - Configure bot parameters

### 💻 Web Admin Dashboard

Access at: `https://filetolinkv5.onrender.com/admin/dashboard`

**Features:**
- 🎨 **Modern dark theme** with smooth animations
- 📊 **Real-time analytics** with Chart.js visualizations  
- 📁 **File management** with search, filter, bulk actions
- 👥 **User management** with profiles and statistics
- 📈 **Download analytics** with trends and insights
- 🔧 **System health** monitoring and logs
- 📱 **Fully responsive** design for all devices

**Login:** 
- Username: `admin`  
- Password: `{WEB_ADMIN_SECRET}`

---

## 📊 API Endpoints

### File Operations
```bash
# Download file
GET /api/dl/{file_id}?code={unique_code}

# Upload file  
POST /api/upload

# Get random file
GET /api/random

# Search files
GET /api/search?q={query}

# File info
GET /api/file/{unique_code}
```

### Admin Endpoints  
```bash
# System stats
GET /admin/api/stats

# Files list  
GET /admin/api/files?page=1&limit=50

# Users list
GET /admin/api/users?page=1&limit=50

# Analytics
GET /admin/api/analytics?period=7

# Admin logs
GET /admin/api/logs?page=1&limit=100
```

### Health Checks
```bash
# Application health
GET /health

# File system health  
GET /api/health/files
```

---

## ⚙️ Configuration Options

### File Settings
```python
MAX_FILE_SIZE = 2147483648    # 2GB limit
ALLOWED_EXTENSIONS = [        # Allowed file types
    "jpg", "jpeg", "png", "gif", "pdf", 
    "mp4", "mp3", "zip", "doc", "txt"
]
```

### Security Settings
```python
RATE_LIMIT_PER_MINUTE = 60   # Per-IP rate limiting
SECRET_KEY = "your-key"       # JWT/session encryption
WEB_ADMIN_SECRET = "admin123" # Web admin password
```

### Performance Settings  
```python
CACHE_TTL = 3600             # CDN cache duration (1 hour)
ENABLE_ANALYTICS = True      # Download tracking
ENABLE_FILE_TTL = False      # Auto-delete old files
FILE_TTL_DAYS = 30          # File retention period
```

---

## 🔒 Security Features

### 🛡️ Built-in Protection
- **Rate limiting** - Prevents API abuse
- **File validation** - Secure file type checking
- **SQL injection** protection via MongoDB
- **XSS protection** - Sanitized inputs and outputs
- **CORS configuration** - Controlled cross-origin access
- **Secure headers** - CSP, HSTS, X-Frame-Options

### 🔐 Authentication  
- **Bot admin** - Telegram user ID verification
- **Web admin** - HTTP Basic Authentication  
- **API access** - JWT token support (extensible)

### 📁 File Security
- **Unique codes** - Cryptographically secure file IDs
- **Private storage** - Files stored in private Telegram channel
- **Access control** - File owners can delete their uploads
- **Virus scanning** - Extensible malware detection hooks

---

## 📈 Monitoring & Analytics

### 📊 Built-in Metrics
- **Upload/download** counts and trends
- **User activity** tracking and retention
- **File type** distribution analysis  
- **Geographic** usage patterns
- **Peak usage** hours identification
- **Error rates** and system health

### 📋 Admin Logging
- All admin actions automatically logged
- **User management** operations tracking
- **File operations** audit trail
- **System changes** history
- **Broadcast messages** records

---

## 🔧 Advanced Configuration

### Database Indexes
```javascript
// Optimized indexes for high performance
db.files.createIndex({ "file_id": 1, "unique_code": 1 }, { unique: true })
db.files.createIndex({ "upload_time": -1 })  
db.files.createIndex({ "file_name": "text" })  // Text search
db.users.createIndex({ "user_id": 1 }, { unique: true })
db.analytics.createIndex({ "download_time": -1 })
```

### Cloudflare Worker Optimizations
```javascript
// Intelligent caching strategy
const CACHE_TTL = 3600;                    // 1 hour base cache
const STALE_WHILE_REVALIDATE = 86400;      // 24 hour stale serving  
const MAX_FILE_SIZE = 100 * 1024 * 1024;  // 100MB cache limit
```

### MongoDB Connection Tuning
```python
# Production connection settings
client = AsyncIOMotorClient(
    MONGODB_URL,
    maxPoolSize=50,      # Connection pool size
    minPoolSize=10,      # Minimum connections  
    maxIdleTimeMS=45000, # Idle timeout
    waitQueueTimeoutMS=5000,
    serverSelectionTimeoutMS=5000
)
```

---

## 🚨 Troubleshooting

### Common Issues

**Bot not responding**
```bash
# Check webhook status
curl "https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"

# Reset webhook  
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
     -d "url=https://yourapp.onrender.com/webhook/{TOKEN_SUFFIX}"
```

**Files not downloading**
```bash
# Check file exists
curl "https://yourapp.onrender.com/api/file/{unique_code}"

# Test direct download
curl -I "https://yourapp.onrender.com/api/dl/{file_id}?code={code}"
```

**Admin panel not loading**
- Verify `WEB_ADMIN_SECRET` environment variable
- Check browser console for JavaScript errors
- Ensure admin credentials are correct

**Database connection issues**
- Verify MongoDB Atlas IP whitelist includes `0.0.0.0/0`
- Check connection string format
- Test connection from MongoDB Compass

### Performance Issues

**High memory usage**
- Reduce `maxPoolSize` in database connection
- Enable file streaming for large uploads
- Monitor file upload sizes

**Slow response times**  
- Enable Cloudflare Worker caching
- Optimize database queries with indexes
- Use CDN for static assets

---

## 📚 API Response Examples

### File Upload Response
```json
{
  "success": true,
  "file_id": "abc123def456",
  "unique_code": "xY9kL2mN8pQ4rT6vW1zA3bC5dE7fG0hJ",
  "file_name": "document.pdf", 
  "file_size": 1048576,
  "urls": {
    "cloudflare": "https://filetolinkv5.username.workers.dev/dl/abc123def456?code=xY9kL2mN...",
    "render": "https://filetolinkv5.onrender.com/api/dl/abc123def456?code=xY9kL2mN...",
    "bot": "https://t.me/your_bot?start=xY9kL2mN8pQ4rT6vW1zA3bC5dE7fG0hJ"
  },
  "upload_time": "2024-01-15T10:30:00Z"
}
```

### System Stats Response  
```json
{
  "files": {
    "total": 15420,
    "deleted": 89,
    "recent_uploads": 245
  },
  "users": {
    "total": 3456,  
    "blocked": 12,
    "recent_active": 892
  },
  "storage": {
    "total_bytes": 52843274240,
    "total_mb": 50400.5,
    "total_gb": 49.22
  },
  "recent_activity": {
    "uploads_24h": 245,
    "downloads_24h": 1337
  }
}
```

---

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Install dependencies: `pip install -r requirements.txt`  
4. Make changes and test locally
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open Pull Request

### Code Style
- Follow PEP 8 for Python code
- Use async/await for all I/O operations
- Add type hints for function parameters
- Document functions with docstrings
- Use meaningful variable names

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern, fast web framework for Python
- **python-telegram-bot** - Telegram Bot API wrapper
- **Motor** - Async MongoDB driver for Python  
- **Cloudflare Workers** - Edge computing platform
- **Render.com** - Cloud application platform
- **Chart.js** - Beautiful charts for the web

---

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/filetolinkv5/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/yourusername/filetolinkv5/discussions)
- 📧 **Email**: support@yourcompany.com
- 💬 **Telegram**: [@YourSupportBot](https://t.me/YourSupportBot)

---

**🚀 Ready to deploy? Start with the [Quick Setup Guide](#installation--setup)!**