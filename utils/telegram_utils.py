# bot_tele/utils/telegram_utils.py
import logging
import mimetypes
import os
import base64
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from bot_tele.constants import get_system_instructions
import io
import datetime
import sqlite3
import httpx

logger = logging.getLogger(__name__)
FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploaded_files")  # المجلد لتخزين الملفات المرفوعة
DB_FILE = os.path.join(FILES_DIR, "files.db")  # ملف قاعدة البيانات

# Function to connect to the database
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

# Function to create tables if they dont exist
def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT,
            stored_name TEXT,
            user_id INTEGER,
            user_name TEXT,
            mime_type TEXT,
            timestamp TEXT,
            book_name TEXT,
            book_grade TEXT
        )
    """)
    conn.commit()
    conn.close()

# setup database at start
setup_database()
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    # Get the largest available photo size
    try:
       photos = update.message.photo
       photo = photos[-1]  # Use the last (largest) photo
       
       file = await photo.get_file()
       file_data = await file.download_as_bytearray()
       
       file_path = io.BytesIO(file_data)
       mime_type = "image/png"  # Photos sent from Telegram are usually png
       file_base64 = base64.b64encode(file_data).decode("utf-8")
       
       uploaded_file = {
           "mimeType": mime_type,
           "data": file_base64,
       }
       
       return uploaded_file
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await update.message.reply_text("Error processing the photo. Please try again later.")
        return None

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    try:
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()

        file_path = file.file_path
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Extract the file name from file_path
        file_name = os.path.basename(file_path)
        
        file_base64 = base64.b64encode(file_data).decode("utf-8")

        # Create the file's path
        os.makedirs(FILES_DIR, exist_ok=True)
        
        user = update.message.from_user
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_file_name = f"{user.id}_{timestamp}_{file_name}"
        new_file_path = os.path.join(FILES_DIR, new_file_name)

        # Save the file to disk
        with open(new_file_path, "wb") as f:
            f.write(file_data)

        if context.user_data.get("save_file"):
            del context.user_data["save_file"]
            # Ask the user for book info
            context.user_data["pending_file"] = {
                "original_name": file_name,
                "stored_name": new_file_name,
                "user_id": user.id,
                "user_name": user.first_name,
                "mime_type": mime_type,
                "timestamp": timestamp,
                "file_base64": file_base64
            }

            reply_keyboard = [['الغاء']]
            markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

            await update.message.reply_text(
                "يرجى إدخال اسم الكتاب والفرقة الدراسية (مثال: كتاب المدني للفرقة الرابعة)",
                reply_markup=markup
            )
        
            return None
        else:
            uploaded_file = {
                "mimeType": mime_type,
                "data": file_base64,
                "file_name": file_name
            }
            return uploaded_file
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        await update.message.reply_text("Error processing the file. Please try again later.")
        return None
    

async def save_book_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_info = update.message.text
    if book_info == "الغاء":
       del context.user_data["pending_file"]
       await update.message.reply_text("تم الغاء عملية الحفظ.", reply_markup=ReplyKeyboardRemove())
       return None
    try:
        pending_file = context.user_data.get("pending_file")

        if pending_file:

            book_name = None
            book_grade = None
            if "كتاب" in book_info:
                book_name_start = book_info.find("كتاب") + len("كتاب")
                book_name_end = book_info.find("للفرقة")
                if book_name_end == -1:
                    book_name = book_info[book_name_start:].strip()
                else:
                    book_name = book_info[book_name_start:book_name_end].strip()
                if "للفرقة" in book_info:
                    book_grade_start = book_info.find("للفرقة") + len("للفرقة")
                    book_grade = book_info[book_grade_start:].strip()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO files (original_name, stored_name, user_id, user_name, mime_type, timestamp, book_name, book_grade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pending_file["original_name"], pending_file["stored_name"], pending_file["user_id"], pending_file["user_name"], pending_file["mime_type"], pending_file["timestamp"], book_name, book_grade))
            conn.commit()
            conn.close()
            del context.user_data["pending_file"]
            await update.message.reply_text("تم حفظ الملف بنجاح!",reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("حدث خطأ. حاول مره اخري",reply_markup=ReplyKeyboardRemove())
    except Exception as e:
         logger.error(f"Error while saving file info: {e}", exc_info=True)
         await update.message.reply_text("حدث خطأ اثناء حفظ معلومات الملف",reply_markup=ReplyKeyboardRemove())


async def get_or_create_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE, model):
    chat_id = update.message.chat.id
    if update.message.chat.type != "private":
        chat_data = context.chat_data.get(chat_id)
        if not chat_data:
            # Add system instructions as part of initial conversation history
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
            # Add system instructions as part of initial conversation history
            chat_session = model.start_chat(history=[{"parts": [{"text": get_system_instructions()}], "role": "user"}])
            context.user_data['chat_session'] = chat_session
        
        return chat_session

async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Split and send long messages."""
    max_length = 4096
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        await update.message.reply_text(chunk)

 