# FileToLink System v8.0 🚀

A high-performance, production-ready file sharing system that uses Telegram as a distributed, cost-effective file backend with Redis caching and Cloudflare CDN.

![FileToLink System](https://img.shields.io/badge/Version-8.0-success) ![Python](https://img.shields.io/badge/Python-3.8+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green) ![Redis](https://img.shields.io/badge/Redis-Cached-red)

## 🌟 Overview

FileToLink is a sophisticated file sharing system that leverages Telegram's MTProto protocol for true streaming capabilities. Unlike traditional file sharing services, it uses Telegram's infrastructure for storage and bandwidth, making it extremely cost-effective while maintaining high performance through Redis caching and Cloudflare CDN.

### 🎯 Key Features

- **⚡ True Streaming**: Direct MTProto streaming from Telegram's data centers
- **🔒 Redis Caching**: Ultra-fast metadata lookups with configurable TTL
- **🌐 CDN Integration**: Cloudflare Workers for edge caching
- **🔄 Background Processing**: Non-blocking file uploads for better user experience
- **📊 Advanced Admin Panel**: Real-time analytics and file management
- **🔐 Secure Authentication**: JWT-based admin authentication
- **🚀 Production Ready**: Gunicorn with Uvicorn workers
- **📱 Mobile Responsive**: Works seamlessly on all devices
- **📈 Real-time Analytics**: Charts and statistics for system monitoring

## 🏗 Architecture

```
User Upload → Telegram Bot → Background Processing → Private Channel
      ↓
Redis Cache ← MongoDB Metadata → FastAPI Streaming → Cloudflare CDN
      ↓
    User Download (Multiple Links Available)
```

### Workflow Details

1. **File Upload**: Users send files to Telegram bot
2. **Background Processing**: Files are processed asynchronously
3. **Telegram Storage**: Files stored in private channel
4. **Metadata Management**: File info stored in MongoDB with Redis caching
5. **Multiple Download Options**: 
   - 🌐 Direct server link
   - 🚀 Cloudflare CDN link
   - 🤖 Telegram bot link

## 🛠 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI + Python 3.8+ | High-performance API framework |
| **Telegram** | Pyrogram | MTProto protocol for true streaming |
| **Database** | MongoDB + Motor | Async document storage |
| **Caching** | Redis | High-speed metadata caching |
| **Server** | Gunicorn + Uvicorn | Production ASGI server |
| **CDN** | Cloudflare Workers | Edge caching and distribution |
| **Frontend** | Vanilla JS + Chart.js | Admin panel with real-time charts |
| **Deployment** | Render.com | Cloud hosting platform |

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- MongoDB database (Atlas recommended)
- Redis server
- Telegram Bot Token
- Telegram API ID & Hash

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/filetolink-v8.git
cd filetolink-v8

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Step 3: Environment Variables

```bash
# Telegram Configuration
API_ID=123456
API_HASH="your_api_hash_here"
BOT_TOKEN="your_bot_token_here"
PRIVATE_CHANNEL_ID=-1001234567890

# MongoDB Configuration
MONGODB_URL="mongodb+srv://username:password@cluster.mongodb.net/filetolink?retryWrites=true&w=majority"
DATABASE_NAME="filetolink"

# Redis Configuration
REDIS_URL="redis://localhost:6379"
REDIS_PASSWORD="your_redis_password"
REDIS_TTL=300

# Server Configuration
RENDER_URL="https://your-app.onrender.com"
CLOUDFLARE_WORKER_URL="https://your-worker.your-subdomain.workers.dev"
BOT_USERNAME="your_bot_username"

# Security
SECRET_KEY="your-32-character-secret-key-here"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="secure-admin-password"

# Performance
MAX_WORKERS=4
WORKER_TIMEOUT=120
RATE_LIMIT_PER_MINUTE=60
```

### Step 4: Database Setup

The system will automatically create necessary indexes on first run. Ensure your MongoDB user has read/write permissions.

### Step 5: Run the Application

```bash
# Development mode
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
chmod +x start.sh
./start.sh
```

## 🚀 Deployment

### Option 1: Render.com (Recommended)

1. **Create Web Service** on Render
2. **Connect your GitHub repository**
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `chmod +x start.sh && ./start.sh`
5. **Add Environment Variables** from your `.env` file

### Option 2: Other Platforms

The application can be deployed on any platform supporting Python:
- Heroku
- Railway
- DigitalOcean App Platform
- AWS Elastic Beanstalk

### Cloudflare Worker Setup

1. Create a new Worker in Cloudflare dashboard
2. Copy the `cloudflare-worker.js` content
3. Deploy with your Render URL
4. (Optional) Set up custom domain

## 📊 Admin Panel

Access the admin panel at: `https://your-domain.com/admin`

### Features

- **📈 Real-time Statistics**: Files, downloads, storage usage
- **📊 Interactive Charts**: Uploads, downloads, file types
- **🔍 File Management**: Search, view, and delete files
- **👥 User Analytics**: Unique users and their activity
- **🔄 Cache Management**: Redis memory usage and TTL settings

### Default Credentials

- Username: `admin`
- Password: `secure-admin-password` (change in production!)

## 🔧 API Endpoints

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Advanced health check |
| `GET` | `/dl/{file_id}?code={code}` | Download file |
| `GET` | `/file/{file_id}/info?code={code}` | Get file info |

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin` | Admin panel HTML |
| `POST` | `/admin/api/auth/login` | Admin login |
| `POST` | `/admin/api/auth/logout` | Admin logout |
| `GET` | `/admin/api/stats` | System statistics |
| `GET` | `/admin/api/files` | Paginated files list |
| `DELETE` | `/admin/api/files/{file_id}` | Delete file |
| `GET` | `/admin/api/charts` | Chart data |

## 🤖 Bot Commands

- `/start` - Welcome message and file access
- `/stats` - User statistics
- Send any file to upload and get shareable links

## 🔗 Download Links

The system generates three types of download links:

1. **🌐 Direct Link**: `https://your-render-url/dl/{file_id}?code={code}`
   - Direct streaming from origin server
   - Uses Redis caching for metadata

2. **🚀 CDN Link**: `https://your-worker-url/dl/{file_id}?code={code}`
   - Edge cached via Cloudflare
   - Faster for popular files
   - Reduces origin server load

3. **🤖 Bot Link**: `https://t.me/your_bot?start={code}`
   - Direct in-app access
   - Best for mobile users
   - No download required

## ⚡ Performance Optimizations

### Redis Caching Strategy

```python
# Cache key structure
file:{file_id}:{unique_code}

# TTL: 5 minutes (configurable)
# Benefits: Reduces MongoDB queries by 90%+
```

### Background Processing

- Immediate "Processing..." response to users
- Asynchronous file handling
- Non-blocking upload experience

### Database Indexes

```javascript
// Automatic index creation
files.unique_code (unique)
files.file_id (unique) 
files.upload_date
files.user_id
files.file_name (text search)
```

## 🛡 Security Features

- **Rate Limiting**: Configurable per-minute limits
- **Input Validation**: Pydantic models for all inputs
- **Authentication**: JWT-based admin authentication
- **CORS Protection**: Configurable origins
- **Security Headers**: XSS protection, no-sniff, etc.
- **Environment Variables**: Secure configuration management

## 📈 Monitoring & Analytics

### Health Checks

```bash
# Basic health check
curl https://your-domain.com/health

# Response
{
  "status": "healthy",
  "services": {
    "mongodb": "healthy",
    "redis": "healthy", 
    "pyrogram": "healthy"
  }
}
```

### Key Metrics

- Total files and storage usage
- Download statistics
- User engagement
- Cache hit rates
- System performance

## 🔄 Configuration Options

### Redis Settings

```python
REDIS_TTL=300           # Cache timeout in seconds
REDIS_URL=redis://...   # Redis connection string
```

### Performance Tuning

```python
MAX_WORKERS=4           # Gunicorn worker processes
WORKER_TIMEOUT=120      # Request timeout in seconds
RATE_LIMIT_PER_MINUTE=60 # API rate limiting
```

### Telegram Settings

```python
PRIVATE_CHANNEL_ID=-1001234567890  # Private channel for file storage
BOT_USERNAME=your_bot_username     # Bot username for links
```

## 🐛 Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check API_ID and API_HASH
   - Verify BOT_TOKEN is valid
   - Ensure bot has message permissions

2. **File upload failures**
   - Check PRIVATE_CHANNEL_ID format
   - Verify bot is admin in channel
   - Check MongoDB connection

3. **Download issues**
   - Verify Redis connection
   - Check file exists in database
   - Validate unique codes

4. **Admin panel login fails**
   - Check ADMIN_USERNAME and ADMIN_PASSWORD
   - Verify SECRET_KEY length (min 32 chars)

### Logs and Debugging

```bash
# Check application logs
tail -f your-log-file.log

# Test Redis connection
redis-cli ping

# Test MongoDB connection
mongosh "your-connection-string" --eval "db.adminCommand('ping')"
```

## 🔄 Updates and Maintenance

### Regular Maintenance Tasks

1. **Monitor storage usage** in Telegram and MongoDB
2. **Check Redis memory** usage and clear cache if needed
3. **Review logs** for errors and performance issues
4. **Update dependencies** regularly

### Backup Strategy

- MongoDB: Use Atlas backup or mongodump
- Redis: Regular RDB/AOF backups
- Configuration: Version control for .env

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests (if available)
pytest

# Code formatting
black .
isort .
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Telegram** for the robust MTProto protocol
- **FastAPI** team for the excellent web framework
- **Pyrogram** for seamless Telegram integration
- **Render.com** for reliable hosting
- **Cloudflare** for CDN services

## 📞 Support

If you need help:

1. Check the [troubleshooting](#troubleshooting) section
2. Review existing [GitHub issues](https://github.com/yourusername/filetolink-v8/issues)
3. Create a new issue with detailed information

## 🚀 Future Enhancements

- [ ] User authentication system
- [ ] File expiration dates
- [ ] Bandwidth limiting
- [ ] Advanced analytics
- [ ] Mobile app
- [ ] Browser extensions
- [ ] API rate limiting per user
- [ ] Webhook notifications

---

<div align="center">

**Made with ❤️ by the FileToLink Team**

[![GitHub stars](https://img.shields.io/github/stars/yourusername/filetolink-v8?style=social)](https://github.com/yourusername/filetolink-v8/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/filetolink-v8?style=social)](https://github.com/yourusername/filetolink-v8/network/members)

*If this project helps you, please give it a ⭐!*

</div>