# pyro_client.py
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait, ChannelInvalid, ChannelPrivate, 
    ChatWriteForbidden, MessageIdInvalid
)
import secrets
import string
import json

from config import settings
from db import database
from utils.helpers import generate_links, format_file_size

# Global pyro client instance
pyro_client = None

async def start_pyro_client():
    """Initialize and start the Pyrogram client"""
    global pyro_client
    
    try:
        pyro_client = Client(
            "filetolink_bot",
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            bot_token=settings.BOT_TOKEN,
            workers=100,
            sleep_threshold=60
        )
        
        # Register handlers
        register_handlers(pyro_client)
        
        # Start the client
        await pyro_client.start()
        print("✅ Pyrogram client started successfully")
        
        # Get bot info
        bot_me = await pyro_client.get_me()
        print(f"🤖 Bot @{bot_me.username} is ready!")
        
    except Exception as e:
        print(f"❌ Failed to start Pyrogram client: {e}")
        raise

async def stop_pyro_client():
    """Stop the Pyrogram client"""
    global pyro_client
    if pyro_client and pyro_client.is_connected:
        await pyro_client.stop()
        print("✅ Pyrogram client stopped")

def generate_unique_code(length=8):
    """Generate a unique code for file identification"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

async def process_file_upload(message: Message, processing_msg: Message):
    """Background task to process file upload"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        # Generate unique identifiers
        file_id = str(message.id)
        unique_code = generate_unique_code()
        
        # Forward file to private channel with proper peer resolution
        try:
            # Resolve the channel to ensure valid peer
            try:
                channel_chat = await pyro_client.get_chat(settings.PRIVATE_CHANNEL_ID)
            except Exception as e:
                await processing_msg.edit_text("❌ Error: Cannot resolve channel. Bot may not have access.")
                print(f"Failed to resolve channel chat: {e}")
                return
            
            # Now forward using the resolved chat
            forwarded_msg = await message.forward(channel_chat.id)
            channel_message_id = forwarded_msg.id
        except ChannelInvalid:
            await processing_msg.edit_text("❌ Error: Invalid channel. Please check the channel ID.")
            print("Channel forwarding error: ChannelInvalid")
            return
        except ChannelPrivate:
            await processing_msg.edit_text("❌ Error: Bot does not have access to the private channel.")
            print("Channel forwarding error: ChannelPrivate")
            return
        except ChatWriteForbidden:
            await processing_msg.edit_text("❌ Error: Bot cannot send messages in this channel.")
            print("Channel forwarding error: ChatWriteForbidden")
            return
        except FloodWait as e:
            await processing_msg.edit_text(f"⚠️ Rate limited. Please wait {e.x} seconds.")
            await asyncio.sleep(e.x)
            # Retry after flood wait
            forwarded_msg = await message.forward(settings.PRIVATE_CHANNEL_ID)
            channel_message_id = forwarded_msg.id
        
        # Get file information
        file = None
        file_type = "unknown"
        
        if message.document:
            file = message.document
            file_type = "document"
        elif message.video:
            file = message.video
            file_type = "video"
        elif message.audio:
            file = message.audio
            file_type = "audio"
        elif message.photo:
            file = message.photo
            file_type = "photo"
        
        file_name = getattr(file, "file_name", "Unknown") if file else "Unknown"
        file_size = getattr(file, "file_size", 0) if file else 0
        mime_type = getattr(file, "mime_type", "application/octet-stream") if file else "application/octet-stream"
        
        # Prepare file metadata
        file_data = {
            "file_id": file_id,
            "unique_code": unique_code,
            "channel_id": settings.PRIVATE_CHANNEL_ID,
            "message_id": channel_message_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "mime_type": mime_type,
            "user_id": user_id,
            "user_name": user_name,
            "upload_date": datetime.utcnow(),
            "download_count": 0,
            "last_downloaded": None
        }
        
        # Save to database
        try:
            files_collection = database.get_collection("files")
            await files_collection.insert_one(file_data)
            
            # Clear any cached data for this file
            cache_key = f"file:{file_id}:{unique_code}"
            await database.cache_delete(cache_key)
            
        except Exception as e:
            await processing_msg.edit_text("❌ Error saving file metadata to database.")
            print(f"Database error: {e}")
            return
        
        # Generate download links
        links = generate_links(file_id, unique_code)
        
        # Send success message to user
        response_text = f"""
✅ **File Uploaded Successfully!**

📁 **File Name:** `{file_name}`
📊 **File Size:** {format_file_size(file_size)}
🔗 **Unique Code:** `{unique_code}`

**Download Links:**
🌐 **Direct Link:** {links['render_link']}
🚀 **CDN Link:** {links['cloudflare_link']}
🤖 **Bot Link:** {links['bot_link']}

💡 *You can use any of these links to download your file.*
        """
        
        await processing_msg.edit_text(response_text, disable_web_page_preview=True)
        
    except Exception as e:
        print(f"Error in background file processing: {e}")
        try:
            await processing_msg.edit_text("❌ An unexpected error occurred while processing your file.")
        except:
            pass

def register_handlers(client: Client):
    """Register all message handlers"""
    
    @client.on_message(filters.document | filters.video | filters.audio | filters.photo)
    async def handle_file_upload(client: Client, message: Message):
        """Handle file uploads from users with background processing"""
        try:
            # Check if message is from a user (not channel/group)
            if not message.from_user:
                return
            
            # Send immediate processing message
            processing_msg = await message.reply_text("⏳ Processing your file...")
            
            # Start background task for file processing
            asyncio.create_task(process_file_upload(message, processing_msg))
            
        except Exception as e:
            print(f"Error handling file upload: {e}")
            try:
                await message.reply_text("❌ An error occurred while starting file processing.")
            except:
                pass

    @client.on_message(filters.command("start"))
    async def start_handler(client: Client, message: Message):
        """Handle /start command with unique code"""
        try:
            if len(message.command) > 1:
                unique_code = message.command[1]
                
                # Find file by unique code
                files_collection = database.get_collection("files")
                file_data = await files_collection.find_one({"unique_code": unique_code})
                
                if file_data:
                    # Update download stats
                    await files_collection.update_one(
                        {"_id": file_data["_id"]},
                        {
                            "$inc": {"download_count": 1},
                            "$set": {"last_downloaded": datetime.utcnow()}
                        }
                    )
                    
                    # Clear cache for this file
                    cache_key = f"file:{file_data['file_id']}:{unique_code}"
                    await database.cache_delete(cache_key)
                    
                    # Send file to user
                    try:
                        await client.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=file_data["channel_id"],
                            message_id=file_data["message_id"]
                        )
                    except FloodWait as e:
                        await message.reply_text(f"⚠️ Please wait {e.x} seconds and try again.")
                    except Exception as e:
                        await message.reply_text("❌ Error sending file. Please try using the direct download links.")
                else:
                    await message.reply_text("❌ File not found. The link may be invalid or expired.")
            else:
                # Regular start command
                welcome_text = """
🤖 **Welcome to FileToLink Bot v8.0!**

**How to use:**
1. Send me any file (document, video, audio, photo)
2. I'll upload it and generate multiple download links
3. Share the links with anyone!

**Features:**
• Fast direct streaming with Redis caching
• Multiple download options
• No file size limits (Telegram limits apply)
• Permanent file storage
• Background processing for fast responses

🔧 **Ready to upload!** Send me a file now.
                """
                await message.reply_text(welcome_text)
                
        except Exception as e:
            print(f"Error in start handler: {e}")
            await message.reply_text("❌ An error occurred. Please try again.")

    @client.on_message(filters.command("stats"))
    async def stats_handler(client: Client, message: Message):
        """Show user statistics"""
        try:
            user_id = message.from_user.id
            
            files_collection = database.get_collection("files")
            
            # Get user's file stats
            user_files = await files_collection.count_documents({"user_id": user_id})
            
            # Get total downloads for user
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": None, "total_downloads": {"$sum": "$download_count"}}}
            ]
            result = await files_collection.aggregate(pipeline).to_list(length=1)
            total_downloads = result[0]["total_downloads"] if result else 0
            
            stats_text = f"""
📊 **Your Statistics**

👤 **User ID:** `{user_id}`
📁 **Files Uploaded:** {user_files}
📥 **Total Downloads:** {total_downloads}

💡 Keep uploading files!
            """
            
            await message.reply_text(stats_text)
            
        except Exception as e:
            print(f"Error in stats handler: {e}")
            await message.reply_text("❌ Error retrieving statistics.")

# Export functions for external use
async def get_pyro_client():
    """Get the pyro client instance"""
    return pyro_client
