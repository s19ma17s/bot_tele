# my_bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FLASK_API_ENDPOINT = os.getenv("FLASK_API_ENDPOINT", "http://127.0.0.1:5000/your-api-endpoint")


# Add any other configuration parameters here
GENERATION_CONFIG = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

GOOGLE_API_KEY = API_KEY
