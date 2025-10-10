from fastapi.responses import RedirectResponse
import httpx # httpx may not be needed here anymore but good to keep for other requests

@router.get("/dl/{file_id}")
async def download_file(file_id: str, code: str, request: Request, response: Response):
    db = get_database()
    file_data = await db.files.find_one({"file_id": file_id, "unique_code": code})
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")

    # --- REDIRECT LOGIC ---
    if file_data.get("telegram_file_id") and telegram_bot.application:
        try:
            bot = telegram_bot.application.bot
            
            # 1. Get the temporary file object from Telegram
            telegram_file = await bot.get_file(file_data["telegram_file_id"])
            
            # 2. Construct the full, temporary CDN URL
            cdn_url = telegram_file.file_path
            if not cdn_url:
                raise HTTPException(status_code=404, detail="Could not retrieve file path from Telegram")

            # 3. Increment download counter (Note: This tracks link generation, not successful downloads)
            await db.files.update_one(
                {"file_id": file_id},
                {"$inc": {"download_count": 1}}
            )

            # 4. Send a 307 Temporary Redirect response to the user's browser
            logger.info(f"Redirecting user to Telegram CDN for file_id: {file_id}")
            return RedirectResponse(url=cdn_url, status_code=307)

        except Exception as e:
            # This can happen if the file is deleted from the channel or if Telegram API has issues
            logger.error(f"Failed to get file from Telegram for redirect: {e}")
            raise HTTPException(status_code=500, detail="Could not retrieve file from storage. It may have been deleted or the link has expired.")

    # --- LOCAL FILE FALLBACK (No changes needed here) ---
    local_path = file_data.get("file_path")
    if not local_path or not os.path.exists(local_path):
        raise HTTPException(status_code=410, detail="File no longer available")

    async def file_stream():
        async with aiofiles.open(local_path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{file_data["original_name"]}"',
        "Content-Type": file_data.get("mime_type", "application/octet-stream"),
        "Content-Length": str(os.path.getsize(local_path)),
    }
    return StreamingResponse(file_stream(), headers=headers)
