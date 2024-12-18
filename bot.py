import logging
import google.generativeai as genai
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from threading import Thread
from config import BOT_TOKEN, GOOGLE_API_KEY
from handlers import commands, message_handler
from flask_api import run_flask_app

# تهيئة التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة مفتاح واجهة برمجة التطبيقات (API) لجوجل
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("تم تهيئة مفتاح واجهة برمجة التطبيقات (API) لجوجل بنجاح.")
except Exception as e:
    logger.error(f"خطأ في تهيئة مفتاح واجهة برمجة التطبيقات (API): {e}", exc_info=True)
    print("فشلت تهيئة مفتاح واجهة برمجة التطبيقات (API). يرجى التحقق من مفتاح واجهة برمجة التطبيقات والمحاولة مرة أخرى.")
    exit()

# إنشاء النموذج
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


def main() -> None:
    # بدء Flask في مؤشر ترابط منفصل
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.REPLY, lambda update, context: message_handler.handle_message(update, context, model)))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()