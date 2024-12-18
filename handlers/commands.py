# bot_tele/handlers/commands.py
from telegram import Update, ForceReply, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
   user = update.effective_user
   await update.message.reply_html(
       rf"Hello {user.mention_html()}! How can I help you?",
       reply_markup=ForceReply(selective=True),
   )

   if update.message.chat.type != "private":
       chat_id = update.message.chat.id
       context.chat_data[chat_id] = {
           "chat_session": None,  # Initialize later in message handler
           "game_winner": None
       }
   else:
       context.user_data['chat_session'] = None  # Initialize later in message handler

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
   await update.message.reply_text("Just write your message and send it to me!")

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if update.message.chat.type != "private":
       await update.message.reply_text("هذا الأمر متاح فقط في المحادثات الخاصة.")
       return None
    context.user_data["save_file"] = True
    reply_keyboard = [['الغاء']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    await update.message.reply_text(
           "يرجى إرسال الملف الذي تريد حفظه.",
           reply_markup=markup
       )
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if update.message.chat.type != "private":
        await update.message.reply_text("هذا الأمر متاح فقط في المحادثات الخاصة.")
        return None
    user_input = update.message.text[len("/search "):].strip()
    if not user_input:
        await update.message.reply_text("يرجى إدخال اسم الكتاب والفرقة الدراسية (مثال: كتاب القانون المدني للفرقة الرابعة)")
        return
    context.user_data["search_book"] = user_input
    await update.message.reply_text("جاري البحث عن الكتب.")