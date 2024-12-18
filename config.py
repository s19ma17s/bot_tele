# bot_tele/config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FLASK_API_ENDPOINT = os.getenv("FLASK_API_ENDPOINT", "http://localhost:5000/your-api-endpoint")

 # Mega Configuration
MEGA_USER = os.getenv("MEGA_USER")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD")
MEGA_FOLDER_NAME = os.getenv("MEGA_FOLDER_NAME", "uploaded_files")
# Add any other configuration parameters here
GENERATION_CONFIG = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}