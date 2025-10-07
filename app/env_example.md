# Environment Variables Template
# Copy to .env and fill in your actual values

# =============================================================================
# SERVER CONFIGURATION
# =============================================================================
PORT=8000
HOST=0.0.0.0
DEBUG=False

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# MongoDB Atlas connection string or local MongoDB
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=filetolinkv5

# =============================================================================
# TELEGRAM BOT CONFIGURATION
# =============================================================================
# Get from @BotFather on Telegram
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789
BOT_USERNAME=your_bot_username

# Private channel ID for file storage (create a private channel and add your bot)
# Forward a message from the channel to @userinfobot to get the ID
CHANNEL_ID=-1001234567890

# Webhook URL (automatically built if not provided)
WEBHOOK_URL=https://filetolinkv5.onrender.com/webhook/your_bot_token_suffix

# =============================================================================
# ADMIN CONFIGURATION
# =============================================================================
# Super admin user ID (get from @userinfobot)
SUPER_ADMIN_ID=123456789

# Additional admin user IDs (comma-separated)
ADMIN_USER_IDS=987654321,555666777

# Web admin panel secret (change this!)
WEB_ADMIN_SECRET=your_super_secure_admin_password_here

# =============================================================================
# FILE CONFIGURATION
# =============================================================================
# Maximum file size in bytes (2GB = 2147483648)
MAX_FILE_SIZE=2147483648

# Allowed file extensions (comma-separated)
ALLOWED_EXTENSIONS=jpg,jpeg,png,gif,bmp,webp,mp4,avi,mov,mkv,wmv,flv,mp3,wav,ogg,m4a,flac,aac,pdf,doc,docx,txt,rtf,xls,xlsx,csv,ppt,pptx,zip,rar,7z,tar,gz

# Upload directory for temporary files
UPLOAD_DIR=./uploads

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
# Secret key for JWT tokens and encryption (generate a strong one!)
SECRET_KEY=your_super_secret_key_min_32_chars_random_string_here

# Rate limiting per minute per IP
RATE_LIMIT_PER_MINUTE=60

# =============================================================================
# URL CONFIGURATION
# =============================================================================
# Your deployed backend URL
BASE_URL=https://filetolinkv5.onrender.com

# Your Cloudflare Worker URL (replace 'username' with your CF username)
CLOUDFLARE_URL=https://filetolinkv5.username.workers.dev

# =============================================================================
# CORS AND SECURITY
# =============================================================================
# Allowed CORS origins (comma-separated, use * for all)
CORS_ORIGINS=*

# Allowed hosts (comma-separated, use * for all)
ALLOWED_HOSTS=*

# =============================================================================
# FEATURE FLAGS
# =============================================================================
# Enable automatic file deletion after TTL
ENABLE_FILE_TTL=False
FILE_TTL_DAYS=30

# Enable download analytics
ENABLE_ANALYTICS=True

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================
# Cache TTL in seconds (1 hour = 3600)
CACHE_TTL=3600

# =============================================================================
# EXAMPLE CONFIGURATION FOR DEVELOPMENT
# =============================================================================
# For local development, you can use these example values:
# 
# PORT=8000
# DEBUG=True
# MONGODB_URL=mongodb://localhost:27017
# BOT_TOKEN=123456789:replace_with_real_token
# BOT_USERNAME=your_test_bot
# CHANNEL_ID=-1001234567890
# SUPER_ADMIN_ID=123456789
# SECRET_KEY=dev_secret_key_not_for_production_use_only
# BASE_URL=http://localhost:8000
# CLOUDFLARE_URL=http://localhost:8000

# =============================================================================
# SECURITY NOTES
# =============================================================================
# 1. Never commit this file with real values to version control
# 2. Use strong passwords and tokens
# 3. Regularly rotate your secret keys
# 4. Use environment-specific configurations
# 5. Enable HTTPS in production (handled by Render/Cloudflare)
# 6. Monitor your logs for suspicious activity
# 7. Keep your dependencies updated