import logging
import google.generativeai as genai
import base64
import io
import mimetypes
import os
from PIL import Image
from telegram import Update, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import httpx
import json
from flask import Flask, request, jsonify
from threading import Thread
import asyncio
from telegram.constants import ChatAction
import traceback

# استبدل هذا بالمفتاح الفعلي لواجهة برمجة التطبيقات (API) الخاصة بك ورمز البوت
API_KEY = "AIzaSyBf243RgEB3k9YLQZy3MTEcqROHml9qEd4"  # استبدل بمفتاح واجهة برمجة التطبيقات الخاص بك من جوجل
BOT_TOKEN = "7728767686:AAG6_DBhD-3Mj4wRzJCp9CUNWzLuRhq-mXE"  # استبدل برمز البوت الخاص بك من تيليجرام

# تهيئة التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة مفتاح واجهة برمجة التطبيقات (API) لجوجل
try:
    genai.configure(api_key=API_KEY)
    logger.info("تم التهيئة والربط بنجاح.")
except Exception as e:
    logger.error(f"مشكله في السيلفر: {e}", exc_info=True)
    print("مشكله في السيلفر اسف علي الخطأ")
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

# --- كود واجهة برمجة تطبيقات Flask (مدمج) ---
app = Flask(__name__)

# استخدام قاموس لتوضيح أفضل ولضمان سلامة مؤشرات الترابط إذا لزم الأمر
received_messages = []

@app.route('/your-api-endpoint', methods=['POST'])
def receive_telegram_data():
    try:
        data = request.form.to_dict()  # الحصول على بيانات النموذج
        files = request.files  # الحصول على الملفات

        user_id = data.get("user_id")
        user_name = data.get("user_name")
        chat_type = data.get("chat_type")
        message = data.get("formatted_message")
        game_winner = data.get("game_winner")
        previous_winner = data.get("previous_winner")

        file_data = None
        file_name = None
        mime_type = None

        if "file" in files:  # التحقق مما إذا كان قد تم إرسال ملف
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


        logger.info(f"تم استلام البيانات من تيليجرام: {received_data}")
        received_messages.append(received_data)

        return jsonify({"status": "success"}), 200  # تم حذف "message" من الرد
    except Exception as e:
        logger.error(f"خطأ في معالجة بيانات تيليجرام: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"خطأ في معالجة البيانات: {e}"}), 500


def run_flask_app():
    app.run(debug=True, use_reloader=False, host='0.0.0.0') # استخدام use_reloader=False لمنع التعارض وتغيير host إلى 0.0.0.0

# --- كود بوت تيليجرام ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"مرحباً {user.mention_html()}! اقدر اساعدك ازاي",
        reply_markup=ForceReply(selective=True),
    )

    if update.message.chat.type != "private":
        chat_id = update.message.chat.id
        context.chat_data[chat_id] = {
            "chat_session": model.start_chat(history=[]),
            "game_winner": None
        }
    else:
        context.user_data['chat_session'] = model.start_chat(history=[])

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("اكتب رسلتك وابعتهالي")

# تعليمات النظام (تم تخزينها كثابت)
system_instructions = """
انت شخص مصري اسمه Yumi AI، ودورك الأساسي إنك تساعد الناس والطلاب في أي حاجة يحتاجوها بأسلوب خفيف الظل، واضح، ومنظم. كل كلامك بيكون باللهجة المصرية، وبتحب تستخدم الإيموجي عشان تضيف طاقة إيجابية وردود لطيفة.  

### INSTRUCTIONS ###
1. اتكلم باللهجة المصرية دايمًا وبأسلوب عصري وحضاري يناسب الجيل الجديد.  
2. لما تشرح، خلي الأسلوب بسيط ومنظم، ووضح الأفكار بطريقة سهلة ومرحة باستخدام إيموجي خفيفة (🌟، 😄، ✌️).  
3. لو حد سألك عن مطورك، الإجابة هي: *"تم تطويري من S.M.A.S"*.  
4. متقولش أي حاجة عن الطريقة اللي اتعملت بيها أو أي تفاصيل تقنية.  
5. لو حد طلب العناصر أو النقاط فقط، قدمها مباشرة بدون أي شرح إضافي.  
6. مش بتقول "يا عم الحج"، لأنك عصري وبتتكلم بأسلوب يناسب كل الأجيال.  
7. لو حد طلب شرح، خلي الشرح بسيط، مضحك شوية، ومن غير ما تبين إنك بتكلم طفل.  

### القواعد ###
- متزودش في الشرح أكتر من المطلوب.  
- متقولش إنك بتشرح كأنك بتكلم حد صغير.  
- خلي الكلام دايمًا إيجابي ولطيف، وضيف إيموجي تناسب الموقف.  

### ماذا تفعل ###
- قدم المساعدة بأسلوب لطيف ومرح (😄).  
- استخدم الإيموجي عشان تضيف شوية بهجة للكلام.  
- لو حد سألك عن مطورك: *"تم تطويري من S.M.A.S"* هي الإجابة الرسمية.  

### ماذا لا تفعل ###
- متتكلمش بطريقة قديمة زي "يا عم الحج".  
- متطلبش من المستخدم يوضح إلا لو هو طلب منك ده.  
- متدخلش في تفاصيل تقنية عن طريقة تطويرك.  

### Few-Shot Example ###

**مستخدم:** "إيه العناصر الرئيسية في دورة الماء؟"  
**Yumi:** "العناصر الرئيسية هي:  
1. التبخر 🌞.  
2. التكثف 🌧️.  
3. الهطول ☔.  
4. الجريان السطحي 🌊."

**مستخدم:** "مين عملك؟"  
**Yumi:** "تم تطويري من S.M.A.S. 😊"

**مستخدم:** "ممكن تشرحلي قانون نيوتن الأول؟"  
**Yumi:** "أكيد! 😄 قانون نيوتن الأول بيقول:  
'الجسم يفضل زي ما هو، سواء ثابت أو بيتحرك في خط مستقيم، إلا لو قوة خارجية أثرت عليه.'  
يعني ببساطة: لو الكورة ساكنة مش هتتحرك إلا لو حد زقها، ولو بتتحرك مش هتوقف إلا لو حاجة زي الاحتكاك أو مقاومة الهوا وقفتها ✌️."

</system_prompt>

"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
           await process_message(update, context, user_input=user_input, uploaded_file=uploaded_file, user_id=user.id, user_name=user.first_name, chat_id=update.message.chat.id, chat_type=chat.type, chat_title=chat.title if chat.type != "private" else None)
    except Exception as e:
         logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
         await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")


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
    
async def get_or_create_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if update.message.chat.type != "private":
        chat_data = context.chat_data.get(chat_id)
        if not chat_data:
             # إضافة تعليمات النظام كجزء من سجل المحادثة الأولي
            chat_session = model.start_chat(history=[{"parts": [{"text": system_instructions}], "role": "user"}])
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
            chat_session = model.start_chat(history=[{"parts": [{"text": system_instructions}], "role": "user"}])
            context.user_data['chat_session'] = chat_session
        
        return chat_session

async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """تقسيم وإرسال الرسائل الطويلة."""
    max_length = 4096
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        await update.message.reply_text(chunk)

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input=None, uploaded_file=None, chat_id=None, user_id=None, user_name=None, chat_type=None, chat_title=None):
    try:
        chat_session = await get_or_create_chat_session(update, context)
        user = update.message.from_user

        # إرسال إجراء الكتابة دائمًا قبل المعالجة
        try:
             await asyncio.wait_for(context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING), timeout=10) # استخدام wait_for مع مهلة زمنية
        except asyncio.TimeoutError:
            logger.error(f"تجاوزت المهلة الزمنية أثناء محاولة إرسال send_chat_action", exc_info=True)
             # يمكنك هنا اختيار إرسال رسالة للمستخدم تخبره بوجود مشكلة أو محاولة إرسال الإجراء مرة أخرى
        
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
           logger.warning("لا يوجد محتوى لإرساله إلى Gemini.")


    except Exception as e:
        logger.error(f"حدث خطأ في معالجة الرسالة: {e}", exc_info=True)
        if "update" in locals() and hasattr(update, 'message'):
           await update.message.reply_text("حدث خطأ. يرجى المحاولة مرة أخرى لاحقًا.")


async def send_data_to_api(data, uploaded_file, update):
    try:
        files = {}
        if uploaded_file:
             file_data = base64.b64decode(uploaded_file["data"])
             files["file"] = (uploaded_file.get("file_name", "file"), io.BytesIO(file_data), uploaded_file["mimeType"])
        
        async with httpx.AsyncClient() as client:
            # زيادة المهلة الزمنية هنا إلى 30 ثانية
            response = await client.post('http://127.0.0.1:5000/your-api-endpoint', data=data, files=files, timeout=300)
            response.raise_for_status()
            logger.info(f"تم إرسال البيانات إلى واجهة برمجة التطبيقات بنجاح. الرد: {response.status_code}")
            if response.headers.get("Content-Type") == "application/json":
                return response.json().get("message")  # إرجاع الرسالة بشكل صحيح
            return None # إرجاع None إذا لم تكن هناك رسالة
    except httpx.HTTPError as e:
        logger.error(f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. خطأ HTTP: {e}", exc_info=True)
        return None # إرجاع None بدلاً من رسالة الخطأ
    except Exception as e:
        logger.error(f"فشل إرسال البيانات إلى واجهة برمجة التطبيقات. حدث خطأ: {e}", exc_info=True)
        return None # إرجاع None بدلاً من رسالة الخطأ

def main() -> None:
    # بدء Flask في مؤشر ترابط منفصل
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.REPLY, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
