# bot_tele/handlers/message_handler.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot_tele.utils.telegram_utils import (
    handle_file,
    handle_photo,
    get_or_create_chat_session,
    send_long_message,
    save_book_info
)
from bot_tele.utils.api_utils import send_data_to_api
import httpx
import os
import sqlite3
logger = logging.getLogger(__name__)
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploaded_files", "files.db")  # ملف قاعدة البيانات

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, model) -> None:
    user = update.message.from_user
    chat = update.message.chat
    user_input = None
    uploaded_file = None
    try:
        if context.user_data.get("pending_file"):
            await save_book_info(update, context)
            return None
        if update.message.chat.type != "private":
            # First, check if the message is a reply or contains a mention
            if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
                user_input = update.message.text
            elif update.message.text and update.message.entities:
                mentioned = False
                for entity in update.message.entities:
                    if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
                        user_input = update.message.text[entity.offset:entity.offset + entity.length + 1:].strip()
                        mentioned = True
                        break
                if not mentioned:
                    return  # Ignore messages without mention in groups
            else:
                return # Ignore all other messages (including media) if not a reply or mention


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
            await process_message(update, context, model, user_input=user_input, uploaded_file=uploaded_file, user_id=user.id, user_name=user.first_name, chat_id=update.message.chat.id, chat_type=chat.type, chat_title=chat.title if chat.type != "private" else None)
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again later.")
    
async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, model, user_input=None, uploaded_file=None, chat_id=None, user_id=None, user_name=None, chat_type=None, chat_title=None):
        try:
            chat_session = await get_or_create_chat_session(update, context, model)
            user = update.message.from_user
            # Send typing action always before processing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

            parts = []
            if user_input:
                parts.append({"text": user_input})
            
            if uploaded_file:
                if not user_input:
                    parts.append({"text": "The user sent a file."})
                parts.append({
                    "inline_data": {
                        "mime_type": uploaded_file["mimeType"],
                        "data": uploaded_file["data"]
                    }
                })
            # Prepare API payload
            full_name = f"{user.first_name} {user.last_name}".strip()
            formatted_message = f"{full_name}: {user_input}" if user_input else f"{full_name} sent a file."
            
            api_data = {
                "user_id": user_id,
                "user_name": full_name,
                "chat_type": chat_type,
                "formatted_message": formatted_message
            }
            # Send data to API and get response
            api_response = await send_data_to_api(api_data, uploaded_file)

            # Get response from Gemini
            response = chat_session.send_message({"parts": parts})
            gemini_response = response.text
            
            if "civil_law/civil_law_4th_year.pdf" in gemini_response:
                file_name = 'civil_law/civil_law_4th_year.pdf'
                file_url = f'http://127.0.0.1:5000/get_file?file_name={file_name}'  # رابط واجهة برمجة التطبيقات للحصول على الملف
                async with httpx.AsyncClient() as client:
                    response = await client.get(file_url)
                    response.raise_for_status()
                    await update.message.reply_document(document=response.content, filename=file_name.split("/")[-1]) # ارسال الملف للمستخدم
                    
                await send_long_message(update, context, gemini_response)
            elif "ممكن الملفات اللي حملتها" in gemini_response:
                file_info = load_file_info(user.id)
                if file_info:
                   await update.message.reply_text("هذه هي الملفات التي قمت بتحميلها:")
                   for file in file_info:
                         # Use the mega_url from the database if it is present
                        if file.get("mega_url"):
                            file_url = file["mega_url"]
                            async with httpx.AsyncClient() as client:
                                response = await client.get(file_url)
                                response.raise_for_status()
                                await update.message.reply_document(document=response.content, filename=file["original_name"])
                        else:
                            file_name = file["stored_name"]
                            file_url = f'http://127.0.0.1:5000/get_file?file_name={file_name}'
                            async with httpx.AsyncClient() as client:
                                response = await client.get(file_url)
                                response.raise_for_status()
                                await update.message.reply_document(document=response.content, filename=file["original_name"])
                else:
                    await update.message.reply_text("لم تقم بتحميل اي ملفات حتى الان.")
            elif "ابحث عن كتاب" in gemini_response:
                
                book_name_start = gemini_response.find("ابحث عن كتاب") + len("ابحث عن كتاب")
                book_name_end = gemini_response.find("للفرقة")
                book_name = gemini_response[book_name_start:book_name_end].strip()
                book_grade_start = gemini_response.find("للفرقة") + len("للفرقة")
                book_grade = gemini_response[book_grade_start:].strip()
                
                found_files = load_file_info()
                found_files_filtered = []
                if found_files:
                     for file in found_files:
                        if (file["book_name"] and book_name.lower() in file["book_name"].lower()) and (file["book_grade"] and book_grade.lower() in file["book_grade"].lower()):
                           found_files_filtered.append(file)

                if found_files_filtered:
                    await update.message.reply_text("هذه هي الكتب التي وجدتها:")
                    for file in found_files_filtered:
                        # Use the mega_url from the database if it is present
                        if file.get("mega_url"):
                            file_url = file["mega_url"]
                            async with httpx.AsyncClient() as client:
                                response = await client.get(file_url)
                                response.raise_for_status()
                                await update.message.reply_document(document=response.content, filename=file["original_name"])
                        else:
                            file_name = file["stored_name"]
                            file_url = f'http://127.0.0.1:5000/get_file?file_name={file_name}'
                            async with httpx.AsyncClient() as client:
                                response = await client.get(file_url)
                                response.raise_for_status()
                                await update.message.reply_document(document=response.content, filename=file["original_name"])
                else:
                    await update.message.reply_text("لم أجد أي كتب تطابق بحثك.")
            elif api_response:
                await update.message.reply_text(api_response)
            
            else:
                await send_long_message(update, context, gemini_response)


        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            if "update" in locals() and hasattr(update, 'message'):
                await update.message.reply_text("An error occurred. Please try again later.")
    
def load_file_info(user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM files WHERE user_id = ?",(user_id,))
    else:
        cursor.execute("SELECT * FROM files")
    files_data = cursor.fetchall()
    conn.close()
    file_info = []
    if files_data:
        for row in files_data:
           file_info.append({
               "id": row[0],
               "original_name": row[1],
               "stored_name": row[2],
               "user_id": row[3],
               "user_name": row[4],
               "mime_type": row[5],
               "timestamp": row[6],
               "book_name": row[7],
               "book_grade": row[8],
                "mega_url": row[9]
           })

    return file_info
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn