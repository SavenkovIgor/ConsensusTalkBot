
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import logging
import os
import openai

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

class ChatEngine:
    model = ""
    temp = 0

    def __init__(self, model="gpt-3.5-turbo", temp=0):
        self.model = model
        self.temp = temp

class Chat:
    messages: list = []
    engine: ChatEngine

    def __init__(self, engine):
        self.engine = engine

    def add_system_message(self, system_message):
        self.messages.append({"role": "system", "content": system_message})

    def add_assistant_message(self, assistant_message):
        self.messages.append({"role": "assistant", "content": assistant_message})

    def add_message(self, user_message):
        self.messages.append({"role": "user", "content": user_message})

    def get_completion(self):
        return openai.ChatCompletion.create(
            model=self.engine.model,
            messages=self.messages,
            temperature=self.engine.temp,
        )

    def clear_messages(self):
        self.messages = []


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')

PORT = int(os.environ.get('PORT', 5000))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hello, {user.mention_html()}!\nthis is a bot to help you with your conversation skills",
        reply_markup=ForceReply(selective=True)
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Available commands:\n/fix - fix your tone\n/start - start the bot\n/help - get help')

async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Sorry, I did not understand that command.')

def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

async def fix_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_versions_prompt = """
    You are a Conversation Improvement robot.Your main goal is, \
    to support the truth seeking conversation style.

    You should take user message and rewrite it, few times according to this rules: \
    - Rewritten message must not move topic away from the main topic. \
    - Rewritten message terms can be replaced with more precise ones if necessary. \
    - Your answer should be in the user's language. \

    Take user message and create 3 different versions of this message: \

    Your output format should be:
    Restate version: <restate, localized version of the message>

    Polite version: <polite, localized version of the message>

    Validate version: <validate, localized version of the message>
    """

    engine = ChatEngine()
    user_message = update.message.text
    chat = Chat(engine)
    chat.add_system_message(message_versions_prompt)
    chat.add_message(user_message)
    answer = chat.get_completion().choices[0].message["content"]
    chat.clear_messages()
    await update.message.reply_text(answer)


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("fix", fix_tone))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all))

    application.add_error_handler(error)

    # application.run_webhook(port=PORT, url_path=TELEGRAM_TOKEN, webhook_url='https://tg-multipurpose-bot.herokuapp.com/' + TELEGRAM_TOKEN)
    application.run_polling()

if __name__ == '__main__':
    main()
