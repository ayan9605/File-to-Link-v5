# pyro_client.py
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait, ChannelInvalid, ChannelPrivate,
    ChatWriteForbidden, MessageIdInvalid, PeerIdInvalid
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
    """Initialize and start the Pyrogram client with channel access fix"""
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

        # Start the client
        await pyro_client.start()
        print("✅ Pyrogram client started successfully")

        # Optional: Join via invite link (uncomment and set if needed)
        # CHANNEL_INVITE_LINK = "https://t.me/+YOUR_INVITE_HASH"  # Set in config.py if needed
        # if hasattr(settings, "CHANNEL_INVITE_LINK") and settings.CHANNEL_INVITE_LINK:
        #     try:
        #         await pyro_client.join_chat(settings.CHANNEL_INVITE_LINK)
        #         print("✅ Joined private channel via invite link")
        #     except Exception as e:
        #         print(f"⚠️ Failed to join via invite: {e}")

        # Try to resolve the private channel to warm up peer cache
        try:
            chat = await pyro_client.get_chat(settings.PRIVATE_CHANNEL_ID)
            print(f"📌 Channel resolved at startup: {chat.title} ({chat.id})")
        except PeerIdInvalid:
            print("⚠️ PeerIdInvalid: Bot has not accessed the channel. Ensure it was added and restarted after.")
        except ChannelInvalid:
            print("❌ ChannelInvalid: The channel ID is incorrect or the channel is deleted.")
        except ChannelPrivate:
            print("❌ ChannelPrivate: Bot does not have access rights.")
        except Exception as e:
            print(f"⚠️ Could not resolve channel: {e}. Proceeding with fallback.")

        # Register message handlers
        register_handlers(pyro_client)

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

        # Forward file to private channel with intelligent fallback
        try:
            # First attempt: Try to resolve the peer via get_chat
            try:
                channel_chat = await pyro_client.get_chat(settings.PRIVATE_CHANNEL_ID)
                forward_dest = channel_chat.id
                print(f"🎯 Forwarding to resolved channel: {channel_chat.title}")
            except (PeerIdInvalid, ChannelInvalid, ChannelPrivate, ChatWriteForbidden) as e:
                print(f"⚠️ Peer resolution failed: {e}. Falling back to raw channel ID.")
                forward_dest = settings.PRIVATE_CHANNEL_ID
            except Exception as e:
                print(f"⚠️ Unexpected error during peer resolution: {e}. Using raw ID.")
                forward_dest = settings.PRIVATE_CHANNEL_ID

            # Perform the forwarding
            forwarded_msg = await message.forward(forward_dest)
            channel_message_id = forwarded_msg.id

        except ChannelInvalid:
            await processing_msg.edit_text("❌ The channel is invalid or deleted. Please check the configuration.")
            print("Channel forwarding error: ChannelInvalid")
            return
        except ChannelPrivate:
            await processing_msg.edit_text("❌ Bot does not have access to the private channel.")
            print("Channel forwarding error: ChannelPrivate")
            return
        except ChatWriteForbidden:
            await processing_msg.edit_text("❌ Bot cannot send messages in this channel.")
            print("Channel forwarding error: ChatWriteForbidden")
            return
        except FloodWait as e:
            wait_time = e.x if isinstance(e.x, int) else 30
            await processing_msg.edit_text(f"⚠️ Rate limited. Please wait {wait_time} seconds.")
            await asyncio.sleep(wait_time)
            # Retry with fallback
            forwarded_msg = await message.forward(settings.PRIVATE_CHANNEL_ID)
            channel_message_id = forwarded_msg.id
        except Exception as e:
            await processing_msg.edit_text(f"❌ Failed to forward file: {str(e)}")
            print(f"Unexpected forwarding error: {e}")
            return

        # Detect file type and metadata
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
            file = message.photo[-1]  # Use highest quality
            file_type = "photo"

        file_name = getattr(file, "file_name", "Unknown") if file else "Unknown"
        file_size = getattr(file, "file_size", 0) if file else 0
        mime_type = getattr(file, "mime_type", "application/octet-stream")

        # Prepare metadata for database
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
            cache_key = f"file:{file_id}:{unique_code}"
            await database.cache_delete(cache_key)
        except Exception as e:
            await processing_msg.edit_text("❌ Failed to save file metadata.")
            print(f"Database error: {e}")
            return

        # Generate download links
        links = generate_links(file_id, unique_code)

        # Send success message
        response_text = f"""
✅ **File Uploaded Successfully!**

📁 **File Name:** `{file_name}`
📊 **File Size:** {format_file_size(file_size)}
🔗 **Unique Code:** `{unique_code}`

**Download Links:**
🌐 **Direct Link:** {links['render_link']}
🚀 **CDN Link:** {links['cloudflare_link']}
🤖 **Bot Link:** {links['bot_link']}

💡 Use any link to download your file.
        """
        await processing_msg.edit_text(response_text, disable_web_page_preview=True)

    except Exception as e:
        print(f"Error in background file processing: {e}")
        try:
            await processing_msg.edit_text("❌ An error occurred while processing your file.")
        except:
            pass

def register_handlers(client: Client):
    """Register all message handlers"""
    @client.on_message(filters.document | filters.video | filters.audio | filters.photo)
    async def handle_file_upload(client: Client, message: Message):
        try:
            if not message.from_user:
                return
            processing_msg = await message.reply_text("⏳ Processing your file...")
            asyncio.create_task(process_file_upload(message, processing_msg))
        except Exception as e:
            print(f"Error handling upload: {e}")

    @client.on_message(filters.command("start"))
    async def start_handler(client: Client, message: Message):
        try:
            if len(message.command) > 1:
                unique_code = message.command[1]
                file_data = await database.get_collection("files").find_one({"unique_code": unique_code})
                if file_data:
                    await database.get_collection("files").update_one(
                        {"_id": file_data["_id"]},
                        {"$inc": {"download_count": 1}, "$set": {"last_downloaded": datetime.utcnow()}}
                    )
                    cache_key = f"file:{file_data['file_id']}:{unique_code}"
                    await database.cache_delete(cache_key)
                    try:
                        await client.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=file_data["channel_id"],
                            message_id=file_data["message_id"]
                        )
                    except FloodWait as e:
                        wait_time = e.x
                        await message.reply_text(f"⚠️ Wait {wait_time} seconds.")
                    except Exception:
                        await message.reply_text("❌ Error sending file.")
                else:
                    await message.reply_text("❌ File not found.")
            else:
                welcome_text = """
🤖 **Welcome to FileToLink Bot v8.0!**
Send me a file and I'll generate download links!
                """
                await message.reply_text(welcome_text)
        except Exception as e:
            print(f"Error in start: {e}")

    @client.on_message(filters.command("stats"))
    async def stats_handler(client: Client, message: Message):
        try:
            user_id = message.from_user.id
            user_files = await database.get_collection("files").count_documents({"user_id": user_id})
            total_downloads = await database.get_collection("files").aggregate([
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": None, "total": {"$sum": "$download_count"}}}
            ]).to_list(length=1)
            total = total_downloads[0]["total"] if total_downloads else 0
            await message.reply_text(f"📊 Files: {user_files}, Downloads: {total}")
        except Exception as e:
            print(f"Error in stats: {e}")

async def get_pyro_client():
    """Export client for external use"""
    return pyro_client
