# bot_tele/bot.py

import logging
import os
import sys
from threading import Thread

import google.generativeai as genai
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram import Update # this is the line you need to add
from flask import Flask, request, jsonify
# Add the 'bot_tele' directory to sys.path
# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (where 'bot_tele' folder is located)
parent_dir = os.path.dirname(current_dir)

# Add the parent directory to sys.path
sys.path.append(parent_dir)
from bot_tele.config import API_KEY, BOT_TOKEN, GENERATION_CONFIG
from bot_tele.handlers import commands
from bot_tele.handlers import message_handler
import base64
# Initialize Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Gemini API
try:
    genai.configure(api_key=API_KEY)
    logger.info("Google API key configured successfully.")
except Exception as e:
    logger.error(f"Error configuring Google API key: {e}", exc_info=True)
    print("Failed to configure Google API key. Please check your API key and try again.")
    exit()

# Create the model
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp", generation_config=GENERATION_CONFIG
)
logger.info("Gemini model initialized successfully.")

# --- Flask API Code (Integrated) ---
app = Flask(__name__)

# Use a dictionary for better clarity and to ensure thread safety if needed
received_messages = []

@app.route('/your-api-endpoint', methods=['POST'])
def receive_telegram_data():
    try:
        data = request.form.to_dict()  # Get the form data
        files = request.files  # Get the files

        user_id = data.get("user_id")
        user_name = data.get("user_name")
        chat_type = data.get("chat_type")
        message = data.get("formatted_message")
        game_winner = data.get("game_winner")
        previous_winner = data.get("previous_winner")

        file_data = None
        file_name = None
        mime_type = None

        if "file" in files:  # Check if a file was sent
            file = files["file"]
            file_data = file.read()
            file_name = file.filename
            mime_type = file.content_type

        received_data = {
            "user_id": user_id,
            "user_name": user_name,
            "chat_type": chat_type,
            "formatted_message": message,
            "game_winner": game_winner,
            "previous_winner": previous_winner,
        }
        if file_data:
            received_data["file"] = {
                "mimeType": mime_type,
                "data": base64.b64encode(file_data).decode("utf-8"),
                "file_name": file_name
            }


        logger.info(f"Data received from Telegram: {received_data}")
        received_messages.append(received_data)

        return jsonify({"status": "success"}), 200  # Removed "message" from the response
    except Exception as e:
        logger.error(f"Error processing Telegram data: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error processing data: {e}"}), 500


def run_flask_app():
    app.run(debug=True, use_reloader=False) # Use use_reloader=False to prevent conflict

def main() -> None:
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("save", commands.save_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.REPLY, lambda update, context: message_handler.handle_message(update, context, model)))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()