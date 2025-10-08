import os
import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler,
    filters
)
from telegram.request import HTTPXRequest
import aiohttp
import aiofiles
from datetime import datetime
from typing import Dict, Any

from config import settings
from db import get_database
from utils.helpers import generate_unique_code, generate_links, format_size, sanitize_filename

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application = None
        
    async def initialize(self):
        """Initialize the bot application"""
        try:
            if not settings.TELEGRAM_BOT_TOKEN:
                logger.warning("No Telegram bot token configured")
                return False
                
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            self.application = (
                Application.builder()
                .token(settings.TELEGRAM_BOT_TOKEN)
                .request(request)
                .build()
            )
            
            # Add handlers
            self.add_handlers()
            
            # Initialize the application (required for v20+ webhooks)
            await self.application.initialize()
            
            logger.info("Telegram bot initialized successfully")
            
            # Log storage channel status
            if settings.PRIVATE_CHANNEL_ID:
                logger.info(f"Private storage channel configured: {settings.PRIVATE_CHANNEL_ID}")
            else:
                logger.warning("No private channel configured - files will use file_id only")
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            return False
    
    def add_handlers(self):
        """Add message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_handler))
        self.application.add_handler(CommandHandler("admin", self.admin_handler))
        self.application.add_handler(CommandHandler("help", self.help_handler))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.file_handler))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.video_handler))
        self.application.add_handler(MessageHandler(filters.AUDIO, self.audio_handler))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        args = context.args
        
        if args:
            # Handle file access via unique code
            unique_code = args[0]
            await self.send_file_via_code(update, context, unique_code)
            return
        
        welcome_text = """
🤖 <b>Welcome to FileToLink Bot!</b>

<b>How to use:</b>
1. Send me any file (document, photo, video, audio)
2. I'll generate 3 download links for you:
   - 🚀 <b>Cloudflare CDN</b> (Super Fast)
   - 🌐 <b>Direct Link</b> (Normal Speed)
   - 🤖 <b>Bot Access</b> (Private)

<b>Features:</b>
• Support for large files
• Fast download links
• Secure file sharing
• No registration required

<b>Just send me a file to get started!</b>
        """
        
        keyboard = []
        if user.id in settings.TELEGRAM_ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")])
        
        keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def help_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📖 <b>FileToLink Bot Help</b>

<b>Commands:</b>
/start - Start the bot and see welcome message
/help - Show this help message
/admin - Admin panel (admins only)

<b>How to use:</b>
1. Send any file (document, image, video, audio)
2. Get instant download links
3. Share links with others

<b>Supported file types:</b>
• Documents (PDF, Word, Text, etc.)
• Images (JPG, PNG, GIF, etc.)
• Videos (MP4, AVI, MOV, etc.)
• Audio (MP3, WAV, OGG, etc.)
• Archives (ZIP, RAR, etc.)

<b>Need help?</b> Contact the administrator.
        """
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def file_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document files"""
        await self.process_upload(update, context, update.message.document)
    
    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo files"""
        # Get the largest photo size
        photo = update.message.photo[-1]
        await self.process_upload(update, context, photo, is_photo=True)
    
    async def video_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video files"""
        await self.process_upload(update, context, update.message.video)
    
    async def audio_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio files"""
        await self.process_upload(update, context, update.message.audio)
    
    async def process_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_obj, is_photo=False):
        """Process file upload and store in channel"""
        user = update.effective_user
        message = update.message
        
        try:
            # Send processing message
            processing_msg = await message.reply_text("🔄 Processing your file...")
            
            # Get file information
            if is_photo:
                file_id = file_obj.file_id
                file_name = f"photo_{file_id}.jpg"
                file_size = file_obj.file_size
                mime_type = "image/jpeg"
            else:
                file_id = file_obj.file_id
                # Fix: Handle None filename and add file extension based on mime type
                base_file_name = getattr(file_obj, 'file_name', None)
                if not base_file_name:
                    # Try to determine extension from mime type
                    mime_type = getattr(file_obj, 'mime_type', None) or 'application/octet-stream'
                    extension = ''
                    if mime_type:
                        if 'video' in mime_type:
                            extension = '.mp4'
                        elif 'audio' in mime_type:
                            extension = '.mp3'
                        elif 'image' in mime_type:
                            extension = '.jpg'
                        else:
                            extension = '.file'
                    file_name = f'file_{file_id}{extension}'
                else:
                    file_name = base_file_name
                file_size = file_obj.file_size
                mime_type = getattr(file_obj, 'mime_type', None) or 'application/octet-stream'
            
            # Sanitize filename
            safe_filename = sanitize_filename(file_name)
            
            # Check file size
            if file_size and file_size > settings.MAX_FILE_SIZE:
                await processing_msg.edit_text(f"❌ File too large. Maximum size is {format_size(settings.MAX_FILE_SIZE)}.")
                return
            
            # Generate unique identifiers
            unique_code = generate_unique_code()
            internal_file_id = generate_unique_code(16)
            
            # Store file in private channel if configured
            storage_message_id = None
            if settings.PRIVATE_CHANNEL_ID:
                try:
                    # Forward/copy the file to storage channel
                    storage_message_id = await self.store_file_in_channel(message, is_photo)
                    logger.info(f"✅ File stored in channel with message_id: {storage_message_id}")
                except Exception as channel_error:
                    logger.error(f"❌ Failed to store in channel: {channel_error}", exc_info=True)
                    # Continue without channel storage - will use file_id only
            else:
                logger.warning("No PRIVATE_CHANNEL_ID configured - skipping channel storage")
            
            # Store in database
            db = get_database()
            file_data = {
                "file_id": internal_file_id,
                "unique_code": unique_code,
                "original_name": safe_filename,
                "file_path": f"channel:{storage_message_id}" if storage_message_id else None,
                "file_size": file_size or 0,
                "file_hash": "",
                "uploader_id": str(user.id),
                "upload_time": datetime.utcnow(),
                "mime_type": mime_type,
                "download_count": 0,
                "telegram_file_id": file_id,
                "storage_message_id": storage_message_id,
                "storage_channel_id": settings.PRIVATE_CHANNEL_ID if storage_message_id else None
            }
            
            await db.files.insert_one(file_data)
            logger.info(f"✅ File metadata stored in database: {internal_file_id}")
            
            # Generate links
            links = generate_links(internal_file_id, unique_code)
            
            # Escape filename for safe display
            escaped_filename = html.escape(safe_filename)
            
            # Send success message with links using HTML formatting
            success_text = f"""
✅ <b>File uploaded successfully!</b>

📁 <b>File:</b> <code>{escaped_filename}</code>
📦 <b>Size:</b> {format_size(file_size) if file_size else "Unknown"}

<b>Download Links:</b>
🚀 <b>CDN Link:</b> <code>{links['cloudflare']}</code>
🌐 <b>Direct Link:</b> <code>{links['render']}</code>
🤖 <b>Bot Link:</b> <code>{links['bot']}</code>

<b>Share securely!</b> ⚡
            """
            
            keyboard = [
                [InlineKeyboardButton("🚀 CDN Link", url=links['cloudflare'])],
                [InlineKeyboardButton("🌐 Direct Link", url=links['render'])],
            ]
            
            if user.id in settings.TELEGRAM_ADMIN_IDS:
                keyboard.append([InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{internal_file_id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                success_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            try:
                await processing_msg.edit_text("❌ An error occurred while processing your file.")
            except:
                await message.reply_text("❌ An error occurred while processing your file.")
    
    async def store_file_in_channel(self, message, is_photo=False):
        """Store file in private storage channel"""
        try:
            if not settings.PRIVATE_CHANNEL_ID:
                logger.warning("No storage channel configured")
                return None
            
            logger.info(f"Storing file in channel: {settings.PRIVATE_CHANNEL_ID}")
            
            # Copy the message to storage channel
            if is_photo:
                sent_message = await self.application.bot.send_photo(
                    chat_id=settings.PRIVATE_CHANNEL_ID,
                    photo=message.photo[-1].file_id,
                    caption=f"Uploaded by: {message.from_user.id}\nTime: {datetime.utcnow().isoformat()}"
                )
            elif message.document:
                sent_message = await self.application.bot.send_document(
                    chat_id=settings.PRIVATE_CHANNEL_ID,
                    document=message.document.file_id,
                    caption=f"Uploaded by: {message.from_user.id}\nTime: {datetime.utcnow().isoformat()}"
                )
            elif message.video:
                sent_message = await self.application.bot.send_video(
                    chat_id=settings.PRIVATE_CHANNEL_ID,
                    video=message.video.file_id,
                    caption=f"Uploaded by: {message.from_user.id}\nTime: {datetime.utcnow().isoformat()}"
                )
            elif message.audio:
                sent_message = await self.application.bot.send_audio(
                    chat_id=settings.PRIVATE_CHANNEL_ID,
                    audio=message.audio.file_id,
                    caption=f"Uploaded by: {message.from_user.id}\nTime: {datetime.utcnow().isoformat()}"
                )
            else:
                logger.warning("Unknown message type for channel storage")
                return None
            
            return sent_message.message_id
            
        except Exception as e:
            logger.error(f"Error storing in channel: {e}", exc_info=True)
            raise
    
    async def send_file_via_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, unique_code: str):
        """Send file when user uses bot link with code"""
        db = get_database()
        
        file_data = await db.files.find_one({"unique_code": unique_code})
        if not file_data:
            await update.message.reply_text("❌ File not found or link expired.")
            return
        
        # Update download count
        await db.files.update_one(
            {"unique_code": unique_code},
            {"$inc": {"download_count": 1}}
        )
        
        # Send file back to user
        try:
            file_name = file_data["original_name"]
            escaped_filename = html.escape(file_name)
            
            # Check if file is stored in channel
            if file_data.get("storage_message_id") and file_data.get("storage_channel_id"):
                # Copy file from storage channel
                try:
                    await self.application.bot.copy_message(
                        chat_id=update.effective_chat.id,
                        from_chat_id=file_data["storage_channel_id"],
                        message_id=file_data["storage_message_id"],
                        caption=f"📁 {file_name}\n📦 {format_size(file_data['file_size'])}"
                    )
                    logger.info(f"✅ File sent from channel storage")
                    return
                except Exception as copy_error:
                    logger.error(f"❌ Failed to copy from channel: {copy_error}")
                    # Fall back to link
            
            # Fallback: Send download link
            links = generate_links(file_data["file_id"], unique_code)
            await update.message.reply_text(
                f"📁 <b>File:</b> {escaped_filename}\n"
                f"📦 <b>Size:</b> {format_size(file_data['file_size'])}\n\n"
                f"📥 <b>Download:</b> {links['cloudflare']}",
                parse_mode='HTML'
            )
                
        except Exception as e:
            logger.error(f"Send file error: {str(e)}", exc_info=True)
            await update.message.reply_text("❌ Error sending file.")
    
    async def admin_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel command"""
        user = update.effective_user
        
        if user.id not in settings.TELEGRAM_ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return
        
        await self.show_admin_panel(update, context)
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel"""
        db = get_database()
        
        try:
            # Get stats
            total_files = await db.files.count_documents({})
            total_users = len(await db.files.distinct("uploader_id"))
            
            storage_pipeline = [
                {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
            ]
            total_storage_result = await db.files.aggregate(storage_pipeline).to_list(length=1)
            storage_size = total_storage_result[0]["total_size"] if total_storage_result else 0
            
            # Count files in channel vs file_id only
            channel_files = await db.files.count_documents({"storage_message_id": {"$exists": True, "$ne": None}})
            
            # Add timestamp to ensure message is always different when refreshing
            current_time = datetime.utcnow().strftime("%H:%M:%S UTC")
            
            storage_status = "✅ Channel" if settings.PRIVATE_CHANNEL_ID else "⚠️ File ID Only"
            
            admin_text = f"""
🏠 <b>Admin Panel</b>

📊 <b>Statistics:</b>
• Total Files: <code>{total_files}</code>
• Channel Stored: <code>{channel_files}</code>
• Total Users: <code>{total_users}</code>
• Storage Used: <code>{format_size(storage_size)}</code>
• Storage Mode: <code>{storage_status}</code>

⚡ <b>Quick Actions:</b>

<i>Last updated: {current_time}</i>
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 System Stats", callback_data="system_stats")],
                [InlineKeyboardButton("👥 User Management", callback_data="user_manage")],
                [InlineKeyboardButton("📁 File Management", callback_data="file_manage")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(
                        admin_text,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                except Exception as edit_error:
                    # Handle the "message is not modified" error gracefully
                    error_msg = str(edit_error).lower()
                    if "message is not modified" in error_msg or "message content and reply markup are exactly the same" in error_msg:
                        await update.callback_query.answer("✅ Stats are up to date!", show_alert=False)
                    else:
                        raise edit_error
            else:
                await update.message.reply_text(
                    admin_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Admin panel error: {e}", exc_info=True)
            error_msg = "❌ Error loading admin panel"
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(error_msg)
                except:
                    await update.callback_query.answer(error_msg, show_alert=True)
            else:
                await update.message.reply_text(error_msg)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin_panel":
            if query.from_user.id in settings.TELEGRAM_ADMIN_IDS:
                await self.show_admin_panel(update, context)
            else:
                await query.edit_message_text("❌ Admin access required.")
        
        elif data == "admin_refresh":
            await self.show_admin_panel(update, context)
        
        elif data.startswith("delete_"):
            file_id = data.split("_")[1]
            await self.delete_file(update, context, file_id)
        
        elif data == "help":
            await self.help_handler(update, context)
    
    async def delete_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
        """Delete a file"""
        db = get_database()
        
        try:
            file_data = await db.files.find_one({"file_id": file_id})
            if file_data:
                # Delete from channel if stored there
                if file_data.get("storage_message_id") and file_data.get("storage_channel_id"):
                    try:
                        await self.application.bot.delete_message(
                            chat_id=file_data["storage_channel_id"],
                            message_id=file_data["storage_message_id"]
                        )
                        logger.info(f"✅ Deleted file from channel: {file_data['storage_message_id']}")
                    except Exception as del_error:
                        logger.error(f"❌ Failed to delete from channel: {del_error}")
                
                # Delete database record
                await db.files.delete_one({"file_id": file_id})
                
                await update.callback_query.edit_message_text("✅ File deleted successfully.")
            else:
                await update.callback_query.edit_message_text("❌ File not found.")
        except Exception as e:
            logger.error(f"Delete file error: {e}", exc_info=True)
            await update.callback_query.edit_message_text("❌ Error deleting file.")
    
    async def set_webhook(self, url: str):
        """Set webhook for Telegram bot"""
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("No Telegram bot token configured, skipping webhook setup")
            return
        
        webhook_url = f"{url}/webhook"
        try:
            await self.application.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)

# Global bot instance
telegram_bot = TelegramBot()
