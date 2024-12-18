# your_bot/utils/api_utils.py
import logging
import base64
import io
import httpx
from config import FLASK_API_ENDPOINT

logger = logging.getLogger(__name__)


async def send_data_to_api(data, uploaded_file, update):
    try:
        files = {}
        if uploaded_file:
             file_data = base64.b64decode(uploaded_file["data"])
             files["file"] = (uploaded_file.get("file_name", "file"), io.BytesIO(file_data), uploaded_file["mimeType"])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(FLASK_API_ENDPOINT, data=data, files=files, timeout=10)
            response.raise_for_status()
            logger.info(f"تم إرسال البيانات إلى واجهة برمجة التطبيقات بنجاح. الرد: {response.status_code}")
            if response.headers.get("Content-Type") == "application/json":
                return response.json().get("message")  # إرجاع الرسالة بشكل صحيح
            return None # إرجاع None إذا لم تكن هناك رسالة
    except httpx.HTTPError as e:
        logger.error(f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. خطأ HTTP: {e}", exc_info=True)
        return f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. خطأ HTTP: {e}"
    except Exception as e:
        logger.error(f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. حدث خطأ: {e}", exc_info=True)
        return f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. حدث خطأ: {e}"
