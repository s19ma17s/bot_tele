# your_bot/utils/telegram_utils.py
import logging
import mimetypes
import os
import base64
from telegram import Update
from telegram.ext import ContextTypes
from constants import get_system_instructions
import io

logger = logging.getLogger(__name__)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    # الحصول على أكبر حجم صورة متاح
    try:
       photos = update.message.photo
       photo = photos[-1]  # استخدام آخر (أكبر) صورة
       
       file = await photo.get_file()
       file_data = await file.download_as_bytearray()
       
       file_path = io.BytesIO(file_data)
       mime_type = "image/png"  # الصور المرسلة من التليجرام تكون png غالبًا
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
       
       # استخراج اسم الملف من file_path
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
    
async def get_or_create_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE, model=None):
    chat_id = update.message.chat.id
    if update.message.chat.type != "private":
        chat_data = context.chat_data.get(chat_id)
        if not chat_data:
             # إضافة تعليمات النظام كجزء من سجل المحادثة الأولي
            chat_session = model.start_chat(history=[{"parts": [{"text": get_system_instructions()}], "role": "user"}])
            context.chat_data[chat_id] = {
                "chat_session": chat_session,
                "game_winner": None
            }
        chat_data = context.chat_data[chat_id]
        return chat_data["chat_session"]
    else:
        chat_session = context.user_data.get('chat_session')
        if not chat_session:
             # إضافة تعليمات النظام كجزء من سجل المحادثة الأولي
            chat_session = model.start_chat(history=[{"parts": [{"text": get_system_instructions()}], "role": "user"}])
            context.user_data['chat_session'] = chat_session
        
        return chat_session

async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """تقسيم وإرسال الرسائل الطويلة."""
    max_length = 4096
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        await update.message.reply_text(chunk)