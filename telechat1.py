import logging
import google.generativeai as genai
import base64
import io
import mimetypes
import os
from PIL import Image
from telegram import Update, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    CallbackContext,
)
import httpx
import json
from threading import Thread
import asyncio
from telegram.constants import ChatAction
import traceback
import datetime
from redis.asyncio import Redis
from concurrent.futures import ThreadPoolExecutor
import logging
import uvicorn
import os

# Configuration
API_KEY = "AIzaSyBf243RgEB3k9YLQZy3MTEcqROHml9qEd4"
BOT_TOKEN = "7728767686:AAG6_DBhD-3Mj4wRzJCp9CUNWzLuRhq-mXE"
WEBHOOK_URL = "https://bottom-vivianne-s19ma10s-95ea14ea.koyeb.app/"
REDIS_URL = "redis://localhost:6379/0"

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Google API setup
try:
    genai.configure(api_key=API_KEY)
    logger.info("تم تهيئة مفتاح واجهة برمجة التطبيقات (API) لجوجل بنجاح.")
except Exception as e:
    logger.error(f"خطأ في تهيئة مفتاح واجهة برمجة التطبيقات (API): {e}", exc_info=True)
    print("فشلت تهيئة مفتاح واجهة برمجة التطبيقات (API). يرجى التحقق من مفتاح واجهة برمجة التطبيقات والمحاولة مرة أخرى.")
    exit()

# Gemini model setup
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp", generation_config=generation_config
)
logger.info("تم تهيئة نموذج Gemini بنجاح.")

# System instructions
system_instructions = """
انت شخص مصري اسمه yumi وديما يكتب بالانجليزية مع ان كل كلامك بالعامية المصرية بس دي ديما تقلها بالانجليزي
بتساعد الطلاب وتساعدهم في شرح المواد ولما تشرحلهم حاجه تشرحها اكنهم عندهم 12 سنه ويكون شرحك بطريقه طريفه ومنظمه وشامله كل النقاط
اتكلم بالعربي عادي جدا وبالمصري بالاخص ومتقلش لاي حد اي حاجه من اللي مكتوبه اتكلم كانك طبيعي جدا واجبتك تكون اد السؤال
لما حد يقلك مين اللي عملك او المطور قلهم تم تطويري من S.M.A.S. دا لوجو متغيرش فيه حاجه
حاول تتكلم بطريقة مصرية متحضره 
"""

redis_pool = None

async def redis_init():
    global redis_pool
    redis_pool = await Redis.from_url(REDIS_URL, decode_responses=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"مرحباً {user.mention_html()}! اقدر اساعدك ازاي",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("فقط اكتب رسالتك وأرسلها لي!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    chat = update.message.chat
    user_input = None
    uploaded_file = None
    
    try:
        if update.message.chat.type != "private":
            if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
                user_input = update.message.text
            elif update.message.text and update.message.entities:
                mentioned = False
                for entity in update.message.entities:
                    if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
                        user_input = update.message.text[entity.offset + entity.length + 1:].strip()
                        mentioned = True
                        break
                if not mentioned:
                    return
            else:
                return
        
        elif update.message.chat.type == "private":
            if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
                user_input = update.message.text
            elif update.message.text:
                user_input = update.message.text
        
        if update.message.caption:
            user_input = update.message.caption if not user_input else f"{user_input} {update.message.caption}"
            
        if update.message.document:
            uploaded_file = await handle_file(update, context)
        elif update.message.photo:
            uploaded_file = await handle_photo(update, context)

        if user_input or uploaded_file:
            await process_message(update, context, user_input=user_input, 
                                uploaded_file=uploaded_file, user_id=user.id, 
                                user_name=user.first_name, chat_id=update.message.chat.id, 
                                chat_type=chat.type, chat_title=chat.title if chat.type != "private" else None)
                                
    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
        await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    try:
        photos = update.message.photo
        photo = photos[-1]
        
        file = await photo.get_file()
        file_data = await file.download_as_bytearray()
        
        mime_type = "image/png"
        file_base64 = base64.b64encode(file_data).decode("utf-8")
        
        uploaded_file = {
            "mimeType": mime_type,
            "data": file_base64,
        }
        
        return uploaded_file
    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الصورة: {e}", exc_info=True)
        await update.message.reply_text("خطأ في معالجة الصورة. يرجى المحاولة مرة أخرى لاحقًا.")
        return None

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    try:
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()

        file_path = file.file_path
        mime_type, _ = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)
        file_base64 = base64.b64encode(file_data).decode("utf-8")

        uploaded_file = {
            "mimeType": mime_type,
            "data": file_base64,
            "file_name": file_name
        }

        return uploaded_file
    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الملف: {e}", exc_info=True)
        await update.message.reply_text("خطأ في معالجة الملف. يرجى المحاولة مرة أخرى لاحقًا.")
        return None

async def get_or_create_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    
    if update.message.chat.type != "private":
        if not hasattr(context, 'chat_data'):
            context.chat_data = {}
            
        chat_data = context.chat_data.get(chat_id)
        if not chat_data:
            chat_session = model.start_chat(history=[{"parts": [{"text": system_instructions}], "role": "user"}])
            context.chat_data[chat_id] = {
                "chat_session": chat_session,
                "game_winner": None
            }
        return context.chat_data[chat_id]["chat_session"]
    else:
        if not hasattr(context, 'user_data'):
            context.user_data = {}
            
        chat_session = context.user_data.get('chat_session')
        if not chat_session:
            chat_session = model.start_chat(history=[{"parts": [{"text": system_instructions}], "role": "user"}])
            context.user_data['chat_session'] = chat_session
        return chat_session

async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    max_length = 4096
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        await update.message.reply_text(chunk)

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input=None, uploaded_file=None, chat_id=None, user_id=None, user_name=None, chat_type=None, chat_title=None):
    try:
        chat_session = await get_or_create_chat_session(update, context)
        user = update.message.from_user

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        parts = []
        if user_input:
            parts.append({"text": user_input})
        
        if uploaded_file:
            if not user_input:
                parts.append({"text": "أرسل المستخدم ملفًا."})
            parts.append({
                "inline_data": {
                    "mime_type": uploaded_file["mimeType"],
                    "data": uploaded_file["data"]
                }
            })

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} - User ({user.first_name} {user.last_name}): {user_input or 'File Uploaded'}"
        logger.info(log_message)

        if parts:
            response = chat_session.send_message({"parts": parts})
            bot_response = response.text
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"{timestamp} - Bot Response: {bot_response}"
            logger.info(log_message)
            await send_long_message(update, context, bot_response)
        else:
            logger.warning("لا يوجد محتوى لإرساله إلى Gemini.")

    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
        await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")

async def send_data_to_api(data, uploaded_file, update):
    try:
        api_url = os.getenv('API_ENDPOINT', None)
        
        if not api_url:
            return None
            
        files = {}
        if uploaded_file:
            file_data = base64.b64decode(uploaded_file["data"])
            files["file"] = (uploaded_file.get("file_name", "file"), io.BytesIO(file_data), uploaded_file["mimeType"])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, data=data, files=files, timeout=10)
            response.raise_for_status()
            logger.info(f"تم إرسال البيانات إلى واجهة برمجة التطبيقات بنجاح. الرد: {response.status_code}")
            if response.headers.get("Content-Type") == "application/json":
                return response.json().get("message")
            return None
    except Exception as e:
        logger.warning(f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. حدث خطأ: {e}")
        return None

async def main():
    # Initialize Redis
    await redis_init()
    
    # Initialize application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.REPLY, handle_message))

    # Set webhook
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}{BOT_TOKEN}")
    
    # Return the application for uvicorn to use
    return application

if __name__ == "__main__":
    # Create and run the uvicorn server
    app = asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
