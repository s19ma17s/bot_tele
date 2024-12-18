# bot_tele/utils/api_utils.py

import logging
import base64
import io
import httpx
from bot_tele.config import FLASK_API_ENDPOINT

logger = logging.getLogger(__name__)


async def send_data_to_api(data, uploaded_file):
    try:
        files = {}
        if uploaded_file:
             file_data = base64.b64decode(uploaded_file["data"])
             files["file"] = (uploaded_file.get("file_name", "file"), io.BytesIO(file_data), uploaded_file["mimeType"])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(FLASK_API_ENDPOINT, data=data, files=files, timeout=10)
            response.raise_for_status()
            logger.info(f"Data sent to API successfully. Response: {response.status_code}")
            if response.headers.get("Content-Type") == "application/json":
                return response.json().get("message")  # Return the message correctly
            return None # Return None if there is no message
    except httpx.HTTPError as e:
        logger.error(f"Failed to send data to API. HTTP Error: {e}", exc_info=True)
        return f"Failed to send data to API. HTTP Error: {e}"
    except Exception as e:
        logger.error(f"Failed to send data to API. Error: {e}", exc_info=True)
        return f"Failed to send data to API. Error: {e}"