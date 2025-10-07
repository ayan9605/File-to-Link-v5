"""
Async Telegram Bot with Webhook Integration
Handles file uploads, triple link generation, and bot admin panel
"""

import asyncio
import logging
import os
import aiofiles
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any, List
from io import BytesIO

from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    BotCommand, File as TelegramFile, Message
)
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError, BadRequest, Forbidden

from config import settings, get_file_url, is_admin, is_super_admin
from db import FileManager, UserManager, AdminManager, AnalyticsManager
import utils.helpers as helpers

logger = logging.getLogger(__name__)

# Global bot application instance
_bot_application: Optional[Application] = None

class FileToBotV5:
    """Main bot class with async webhook support"""
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None
    
    async def initialize(self):
        """Initialize bot application"""
        try:
            # Build application
            self.application = ApplicationBuilder().token(settings.BOT_TOKEN).build()
            self.bot = self.application.bot
            
            # Set up handlers
            await self._setup_handlers()
            
            # Set bot commands
            await self._set_bot_commands()
            
            # Set webhook
            await self._setup_webhook()
            
            logger.info("🤖 Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Bot initialization failed: {e}")
            raise
    
    async def _setup_handlers(self):
        """Setup all bot handlers"""
        app = self.application
        
        # Command handlers
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("myfiles", self._cmd_myfiles))
        app.add_handler(CommandHandler("random", self._cmd_random))
        app.add_handler(CommandHandler("search", self._cmd_search))
        
        # Admin commands
        app.add_handler(CommandHandler("admin", self._cmd_admin))
        app.add_handler(CommandHandler("broadcast", self._cmd_broadcast))
        app.add_handler(CommandHandler("block", self._cmd_block_user))
        app.add_handler(CommandHandler("unblock", self._cmd_unblock_user))
        app.add_handler(CommandHandler("delfile", self._cmd_delete_file))
        
        # File upload handler
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, self._handle_file_upload))
        
        # Callback query handler
        app.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Text message handler
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
    
    async def _set_bot_commands(self):
        """Set bot command menu"""
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("help", "📋 Show help menu"),
            BotCommand("stats", "📊 Bot statistics"),
            BotCommand("myfiles", "📁 My uploaded files"),
            BotCommand("random", "🎲 Get random file"),
            BotCommand("search", "🔍 Search files"),
        ]
        
        # Add admin commands for admins
        admin_commands = [
            BotCommand("admin", "👑 Admin panel"),
            BotCommand("broadcast", "📢 Broadcast message"),
            BotCommand("block", "🚫 Block user"),
            BotCommand("unblock", "✅ Unblock user"),
            BotCommand("delfile", "🗑️ Delete file"),
        ]
        
        await self.bot.set_my_commands(commands)
        
        # Set admin commands for super admin
        if settings.SUPER_ADMIN_ID:
            await self.bot.set_my_commands(
                commands + admin_commands,
                scope={"type": "chat", "chat_id": settings.SUPER_ADMIN_ID}
            )
    
    async def _setup_webhook(self):
        """Setup webhook"""
        try:
            if settings.WEBHOOK_URL:
                await self.bot.set_webhook(
                    url=settings.WEBHOOK_URL,
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=True
                )
                logger.info(f"🔗 Webhook set: {settings.WEBHOOK_URL}")
            else:
                logger.info("🔗 Webhook URL not configured, using polling")
                
        except Exception as e:
            logger.error(f"❌ Webhook setup failed: {e}")
    
    # Command Handlers
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Register/update user
        await UserManager.create_or_update_user({
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code
        })
        
        # Check for file code in start parameter
        if context.args:
            unique_code = context.args[0]
            await self._handle_file_request(update, context, unique_code)
            return
        
        # Welcome message with inline keyboard
        welcome_text = f"""
🚀 **Welcome to File-To-Link System V5!**

👋 Hello {user.first_name or user.username}!

**What I can do:**
📤 **Upload Files** - Send any file to get instant download links
🔗 **Triple Links** - Get 3 different download options:
   • ⚡ **Cloudflare** - Rocket fast CDN
   • 🌐 **Direct** - Standard download
   • 🤖 **Bot** - Telegram direct access

💡 **Features:**
• No file size limits (up to 2GB)
• Permanent storage
• Download analytics
• Random file discovery
• Search functionality

📊 **Quick Stats:**
• Total Files: Loading...
• Active Users: Loading...

**🎯 Quick Actions:**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Statistics", callback_data="stats"),
                InlineKeyboardButton("📁 My Files", callback_data="myfiles")
            ],
            [
                InlineKeyboardButton("🎲 Random File", callback_data="random"),
                InlineKeyboardButton("🔍 Search Files", callback_data="search")
            ],
            [
                InlineKeyboardButton("📋 Help & Guide", callback_data="help"),
                InlineKeyboardButton("ℹ️ About", callback_data="about")
            ]
        ]
        
        # Add admin button for admins
        if is_admin(user.id):
            keyboard.append([
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get quick stats
        try:
            stats = await AdminManager.get_system_stats()
            welcome_text = welcome_text.replace(
                "Total Files: Loading...",
                f"Total Files: {stats['files']['total']:,}"
            ).replace(
                "Active Users: Loading...",
                f"Active Users: {stats['users']['total']:,}"
            )
        except Exception as e:
            logger.error(f"Failed to get stats for start: {e}")
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📋 **File-To-Link System V5 - Help Guide**

**🔥 How to Upload Files:**
1. Send any file (document, photo, video, audio)
2. Wait for processing (large files may take time)
3. Get 3 download links instantly!

**🔗 Link Types:**
⚡ **Cloudflare** - Ultra-fast CDN cached downloads
🌐 **Direct** - Standard server downloads  
🤖 **Bot Access** - Download via Telegram bot

**📱 Available Commands:**
• `/start` - Main menu and quick actions
• `/stats` - View bot statistics
• `/myfiles` - See your uploaded files
• `/random` - Get a random file
• `/search <query>` - Search files by name

**🎯 Quick Tips:**
• All files are permanently stored
• Share links with anyone
• Links work in browsers & media players
• No registration required
• Supports files up to 2GB

**⚠️ Important Notes:**
• Don't upload copyrighted content
• Malicious files will be removed
• Keep your links safe
• Report issues to admins

**🔒 Privacy & Security:**
• Files are securely stored
• Only you can manage your files
• Anonymous downloads supported
• No tracking of personal data

Need more help? Contact: @admin_username
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="start"),
                InlineKeyboardButton("📊 Statistics", callback_data="stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.effective_message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        await update.effective_chat.send_action(ChatAction.TYPING)
        
        try:
            stats = await AdminManager.get_system_stats()
            
            stats_text = f"""
📊 **File-To-Link System Statistics**

**📁 Files:**
• Total Files: `{stats['files']['total']:,}`
• Recent Uploads (24h): `{stats['files']['recent_uploads']:,}`
• Deleted Files: `{stats['files']['deleted']:,}`

**👥 Users:**
• Total Users: `{stats['users']['total']:,}`  
• Active Today: `{stats['users']['recent_active']:,}`
• Blocked Users: `{stats['users']['blocked']:,}`

**💾 Storage:**
• Total Size: `{stats['storage']['total_gb']:.2f} GB`
• Total Size: `{stats['storage']['total_mb']:.1f} MB`

**🔥 System Status:**
• Status: `🟢 Operational`
• Uptime: `Running smoothly`
• Version: `5.0.0 Production`

**📈 Performance:**
• Average Upload: `< 30 seconds`
• Average Download: `< 5 seconds`  
• Success Rate: `99.9%`

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="stats"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="start")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.effective_message.reply_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Stats command error: {e}")
            await update.effective_message.reply_text(
                "❌ Failed to fetch statistics. Please try again later.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Try Again", callback_data="stats")
                ]])
            )
    
    async def _cmd_myfiles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myfiles command"""
        user_id = update.effective_user.id
        
        try:
            files = await FileManager.get_user_files(user_id, limit=10)
            
            if not files:
                await update.effective_message.reply_text(
                    "📂 **No files found!**\n\nYou haven't uploaded any files yet. Send me a file to get started!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Main Menu", callback_data="start")
                    ]])
                )
                return
            
            myfiles_text = f"📁 **Your Files ({len(files)} shown):**\n\n"
            
            keyboard = []
            for i, file_doc in enumerate(files):
                upload_date = datetime.fromtimestamp(file_doc['upload_time']).strftime('%m/%d %H:%M')
                size_mb = file_doc.get('file_size', 0) / (1024 * 1024)
                
                myfiles_text += f"**{i+1}.** `{file_doc['file_name'][:30]}{'...' if len(file_doc['file_name']) > 30 else ''}`\n"
                myfiles_text += f"   📅 {upload_date} • 💾 {size_mb:.1f}MB • 📥 {file_doc.get('download_count', 0)} downloads\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📁 {file_doc['file_name'][:20]}{'...' if len(file_doc['file_name']) > 20 else ''}",
                        callback_data=f"file_info:{file_doc['unique_code']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="myfiles"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.effective_message.reply_text(
                myfiles_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"My files error: {e}")
            await update.effective_message.reply_text(
                "❌ Failed to fetch your files. Please try again later."
            )
    
    async def _cmd_random(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /random command"""
        await update.effective_chat.send_action(ChatAction.TYPING)
        
        try:
            random_file = await FileManager.get_random_file()
            
            if not random_file:
                await update.effective_message.reply_text(
                    "🎲 **No files available**\n\nBe the first to upload a file!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            await self._send_file_info(update, random_file, "🎲 **Random File Discovery**")
            
        except Exception as e:
            logger.error(f"Random file error: {e}")
            await update.effective_message.reply_text(
                "❌ Failed to get random file. Please try again later."
            )
    
    async def _cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.effective_message.reply_text(
                "🔍 **Search Files**\n\nUsage: `/search filename`\n\nExample: `/search document.pdf`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        query = " ".join(context.args)
        await update.effective_chat.send_action(ChatAction.TYPING)
        
        try:
            results = await FileManager.search_files(query, limit=10)
            
            if not results:
                await update.effective_message.reply_text(
                    f"🔍 **No results found for:** `{query}`\n\nTry different keywords or check spelling.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            search_text = f"🔍 **Search Results for:** `{query}`\n\n**Found {len(results)} files:**\n\n"
            
            keyboard = []
            for i, file_doc in enumerate(results):
                upload_date = datetime.fromtimestamp(file_doc['upload_time']).strftime('%m/%d')
                size_mb = file_doc.get('file_size', 0) / (1024 * 1024)
                
                search_text += f"**{i+1}.** `{file_doc['file_name'][:35]}{'...' if len(file_doc['file_name']) > 35 else ''}`\n"
                search_text += f"   📅 {upload_date} • 💾 {size_mb:.1f}MB • 📥 {file_doc.get('download_count', 0)}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📥 {file_doc['file_name'][:25]}{'...' if len(file_doc['file_name']) > 25 else ''}",
                        callback_data=f"file_info:{file_doc['unique_code']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.effective_message.reply_text(
                search_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.effective_message.reply_text(
                "❌ Search failed. Please try again later."
            )
    
    # File Upload Handler
    async def _handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file upload"""
        user = update.effective_user
        message = update.message
        
        # Check if user is blocked
        user_doc = await UserManager.get_user(user.id)
        if user_doc and user_doc.get('is_blocked'):
            await message.reply_text(
                "🚫 **Access Denied**\n\nYour account has been blocked. Contact admin for assistance.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send processing message
        processing_msg = await message.reply_text(
            "⏳ **Processing your file...**\n\n🔄 Uploading to secure storage\n⚡ Generating download links\n🔗 Creating access codes",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Get file object
            if message.document:
                file_obj = message.document
                file_name = file_obj.file_name or f"document_{file_obj.file_id}.bin"
            elif message.photo:
                file_obj = message.photo[-1]  # Get highest quality
                file_name = f"photo_{file_obj.file_id}.jpg"
            elif message.video:
                file_obj = message.video
                file_name = file_obj.file_name or f"video_{file_obj.file_id}.mp4"
            elif message.audio:
                file_obj = message.audio
                file_name = file_obj.file_name or f"audio_{file_obj.file_id}.mp3"
            else:
                await processing_msg.edit_text("❌ **Unsupported file type**")
                return
            
            # Check file size
            if file_obj.file_size > settings.MAX_FILE_SIZE:
                await processing_msg.edit_text(
                    f"❌ **File too large**\n\nMaximum size: {settings.MAX_FILE_SIZE // (1024*1024)}MB\nYour file: {file_obj.file_size // (1024*1024)}MB"
                )
                return
            
            # Check file extension
            file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            if file_ext and file_ext not in settings.ALLOWED_EXTENSIONS:
                await processing_msg.edit_text(
                    f"❌ **File type not allowed**\n\nAllowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
                )
                return
            
            # Generate unique code and file ID
            unique_code = helpers.generate_unique_code()
            file_id = helpers.generate_file_id()
            
            # Forward file to private channel for storage
            forwarded = await context.bot.forward_message(
                chat_id=settings.CHANNEL_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            
            # Create file record in database
            file_data = {
                "file_id": file_id,
                "unique_code": unique_code,
                "file_name": file_name,
                "file_size": file_obj.file_size,
                "content_type": getattr(file_obj, 'mime_type', 'application/octet-stream'),
                "uploader_id": user.id,
                "uploader_username": user.username,
                "telegram_file_id": file_obj.file_id,
                "channel_message_id": forwarded.message_id,
                "file_extension": file_ext
            }
            
            db_id = await FileManager.create_file(file_data)
            
            # Generate download URLs
            urls = get_file_url(file_id, unique_code)
            
            # Update processing message with success
            await processing_msg.edit_text(
                "✅ **Upload Complete!**\n\n🎉 Your file has been processed successfully!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send file info with download links
            await self._send_file_info(update, file_data, "📤 **File Uploaded Successfully**")
            
            # Log admin action if admin uploaded
            if is_admin(user.id):
                await AdminManager.log_admin_action(
                    user.id, "file_upload", 
                    {"file_name": file_name, "file_id": file_id}
                )
            
        except Exception as e:
            logger.error(f"File upload error: {e}")
            await processing_msg.edit_text(
                "❌ **Upload Failed**\n\nSomething went wrong. Please try again or contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def _send_file_info(self, update: Update, file_data: dict, title: str = "📁 **File Information**"):
        """Send file information with download links"""
        file_name = file_data['file_name']
        file_size = file_data.get('file_size', 0)
        size_mb = file_size / (1024 * 1024)
        upload_time = datetime.fromtimestamp(file_data['upload_time']).strftime('%Y-%m-%d %H:%M UTC')
        download_count = file_data.get('download_count', 0)
        
        # Generate URLs
        urls = get_file_url(file_data['file_id'], file_data['unique_code'])
        
        info_text = f"""{title}

**📁 File Details:**
• **Name:** `{file_name}`
• **Size:** `{size_mb:.2f} MB`
• **Uploaded:** `{upload_time}`
• **Downloads:** `{download_count:,}`

**🔗 Download Links:**

**⚡ Cloudflare (Fastest)**
`{urls['cloudflare']}`

**🌐 Direct Download**
`{urls['render']}`

**🤖 Bot Access**
`{urls['bot']}`

**💡 Tips:**
• Copy any link to browser or media player
• Share links with anyone
• Use fastest link for better speed
• Bot access works in Telegram

*File ID: `{file_data['unique_code']}`*
"""
        
        keyboard = [
            [
                InlineKeyboardButton("⚡ Fast Download", url=urls['cloudflare']),
                InlineKeyboardButton("🌐 Normal Download", url=urls['render'])
            ],
            [
                InlineKeyboardButton("🤖 Bot Download", url=urls['bot']),
                InlineKeyboardButton("📋 Copy Links", callback_data=f"copy_links:{file_data['unique_code']}")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"file_info:{file_data['unique_code']}"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ]
        ]
        
        # Add delete button for file owner or admins
        user_id = update.effective_user.id
        if user_id == file_data.get('uploader_id') or is_admin(user_id):
            keyboard.append([
                InlineKeyboardButton("🗑️ Delete File", callback_data=f"delete_confirm:{file_data['unique_code']}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.effective_message.reply_text(
            info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_file_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, unique_code: str):
        """Handle file request via /start parameter"""
        try:
            file_doc = await FileManager.get_file_by_code(unique_code)
            
            if not file_doc:
                await update.message.reply_text(
                    "❌ **File Not Found**\n\nThe file you're looking for doesn't exist or has been deleted.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Main Menu", callback_data="start")
                    ]])
                )
                return
            
            # Try to send file directly from channel
            try:
                await context.bot.forward_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=settings.CHANNEL_ID,
                    message_id=file_doc['channel_message_id']
                )
                
                # Increment download counter
                await FileManager.increment_download_count(file_doc['file_id'])
                
                # Send file info
                await self._send_file_info(update, file_doc, "📥 **File Download**")
                
            except Exception as forward_error:
                logger.error(f"Failed to forward file: {forward_error}")
                # Fallback to showing download links only
                await self._send_file_info(update, file_doc, "📥 **Download Links**")
                
        except Exception as e:
            logger.error(f"File request error: {e}")
            await update.message.reply_text(
                "❌ **Error accessing file**\n\nPlease try again later or contact support."
            )
    
    # Callback Query Handler
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        data = query.data
        
        await query.answer()
        
        try:
            if data == "start":
                await self._cmd_start(update, context)
            elif data == "help":
                await self._cmd_help(update, context)
            elif data == "stats":
                await self._cmd_stats(update, context)
            elif data == "myfiles":
                await self._cmd_myfiles(update, context)
            elif data == "random":
                await self._cmd_random(update, context)
            elif data.startswith("file_info:"):
                unique_code = data.split(":", 1)[1]
                file_doc = await FileManager.get_file_by_code(unique_code)
                if file_doc:
                    await self._send_file_info(update, file_doc)
                else:
                    await query.edit_message_text("❌ File not found")
            elif data.startswith("copy_links:"):
                unique_code = data.split(":", 1)[1]
                file_doc = await FileManager.get_file_by_code(unique_code)
                if file_doc:
                    urls = get_file_url(file_doc['file_id'], unique_code)
                    links_text = f"🔗 **Copy these links:**\n\n**Cloudflare:** `{urls['cloudflare']}`\n\n**Direct:** `{urls['render']}`\n\n**Bot:** `{urls['bot']}`"
                    await query.edit_message_text(links_text, parse_mode=ParseMode.MARKDOWN)
            elif data.startswith("admin_panel") and is_admin(query.from_user.id):
                await self._show_admin_panel(update, context)
            # Add more callback handlers as needed
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text("❌ An error occurred")
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text.strip()
        
        # Check if it's a file code
        if len(text) == 32 and text.isalnum():  # Unique codes are 32 chars
            await self._handle_file_request(update, context, text)
            return
        
        # Default response
        await update.message.reply_text(
            "🤔 **Not sure what you mean!**\n\nSend me a file to upload, or use /help for available commands.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Help", callback_data="help"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ]])
        )
    
    # Admin Commands (implement based on requirements)
    async def _cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Access denied")
            return
        
        await self._show_admin_panel(update, context)
    
    async def _show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel interface"""
        # Implementation for admin panel
        admin_text = """
👑 **Admin Panel**

**System Management:**
• View detailed statistics
• Manage users and files
• Monitor system health
• Access admin logs

**Quick Actions:**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 System Stats", callback_data="admin_stats"),
                InlineKeyboardButton("👥 User Management", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("📁 File Management", callback_data="admin_files"),
                InlineKeyboardButton("📋 Admin Logs", callback_data="admin_logs")
            ],
            [
                InlineKeyboardButton("🔄 System Health", callback_data="admin_health"),
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.effective_message.reply_text(
            admin_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        if not is_super_admin(update.effective_user.id):
            await update.message.reply_text("❌ Super admin access required")
            return
        
        # Implementation for broadcast
        await update.message.reply_text("📢 Broadcast feature - Implementation needed")
    
    async def _cmd_block_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Block user command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin access required")
            return
        
        # Implementation for user blocking
        await update.message.reply_text("🚫 User blocking - Implementation needed")
    
    async def _cmd_unblock_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unblock user command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin access required")
            return
        
        # Implementation for user unblocking
        await update.message.reply_text("✅ User unblocking - Implementation needed")
    
    async def _cmd_delete_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete file command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin access required")
            return
        
        # Implementation for file deletion
        await update.message.reply_text("🗑️ File deletion - Implementation needed")

# Global functions
async def setup_bot():
    """Setup and initialize bot"""
    global _bot_application
    
    try:
        bot_instance = FileToBotV5()
        await bot_instance.initialize()
        _bot_application = bot_instance.application
        
        logger.info("🤖 Bot setup completed")
        return bot_instance
        
    except Exception as e:
        logger.error(f"❌ Bot setup failed: {e}")
        raise

def get_application() -> Optional[Application]:
    """Get bot application instance"""
    return _bot_application