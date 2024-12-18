# your_bot/handlers/message_handler.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils.telegram_utils import (
    handle_file,
    handle_photo,
    get_or_create_chat_session,
    send_long_message
)
from utils.api_utils import send_data_to_api
import asyncio

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, model=None) -> None:
    user = update.message.from_user
    chat = update.message.chat
    user_input = None
    uploaded_file = None
    try:
        if update.message.chat.type != "private":
            # أولاً، تحقق مما إذا كانت الرسالة ردًا أو تتضمن إشارة
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
                    return  # تجاهل الرسائل بدون إشارة في المجموعات
            else:
                return # تجاهل جميع الرسائل الأخرى (بما في ذلك الوسائط) إذا لم تكن ردًا أو إشارة

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
           await process_message(update, context, model=model, user_input=user_input, uploaded_file=uploaded_file, user_id=user.id, user_name=user.first_name, chat_id=update.message.chat.id, chat_type=chat.type, chat_title=chat.title if chat.type != "private" else None)
    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
        await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")
    
async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, model=None, user_input=None, uploaded_file=None, chat_id=None, user_id=None, user_name=None, chat_type=None, chat_title=None):
    try:
        chat_session = await get_or_create_chat_session(update, context, model)
        user = update.message.from_user

        # إرسال إجراء الكتابة دائمًا قبل المعالجة
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


        # تجهيز حمولة واجهة برمجة التطبيقات (API)
        full_name = f"{user.first_name} {user.last_name}".strip()
        formatted_message = f"{full_name}: {user_input}" if user_input else f"{full_name} أرسل ملفًا."

        api_data = {
            "user_id": user_id,
            "user_name": full_name,
            "chat_type": chat_type,
            "formatted_message": formatted_message
        }

        # إرسال البيانات إلى واجهة برمجة التطبيقات والحصول على الرد
        api_response = await send_data_to_api(api_data, uploaded_file, update)

        # تعليق: إذا كان هناك رد من واجهة برمجة التطبيقات، قم بمعالجته أولًا
        if api_response:
            await update.message.reply_text(api_response)
        
        if parts:
            response = chat_session.send_message({"parts": parts})
            bot_response = response.text
            # إرسال الرد مرة أخرى إلى تيليجرام باستخدام الدالة الجديدة
            await send_long_message(update, context, bot_response)
        else:
             logger.warning("لا يوجد محتوى لإرساله إلى Yumi AI")

        # قم بانتظار مدة قصيرة بعد استجابة البوت
        await asyncio.sleep(0.3)
        
    except Exception as e:
         logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
         if "update" in locals() and hasattr(update, 'message'):
            await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")