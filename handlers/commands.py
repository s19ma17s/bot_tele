# your_bot/handlers/commands.py
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"مرحباً {user.mention_html()}! اقدر اساعدك ازاي",
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
    await update.message.reply_text("فقط اكتب رسالتك وأرسلها لي!")