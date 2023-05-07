from telegram.ext import Updater, MessageHandler, CommandHandler,  Filters
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

    def __init__(self, engine, system_message, user_messages = []):
        self.engine = engine
        self.messages.append({"role": "system", "content": system_message})
        self.messages.extend([{"role": "user", "content": message} for message in user_messages])

    def get_answer(self, user_message):
        self.messages.append({"role": "user", "content": user_message})
        response = openai.ChatCompletion.create(
            model=self.engine.model,
            messages=self.messages,
            temperature=self.engine.temp,
        )
        answer = response.choices[0].message["content"]
        self.messages.append({"role": "assistant", "content": answer})
        return answer

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

PORT = int(os.environ.get('PORT', 5000))
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')

def start(update, context):
    update.message.reply_text('Hello, this is a bot to help you with your conversation skills. Please type /help to get started.')

def help(update, context):
    update.message.reply_text('This is a bot to help you with your conversation skills. Please type /start to get started.')

def test_echo(update, context):
    update.message.reply_text(update.message.text)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def fix_tone(update, context):
    message_versions_prompt = """
    You are a Conversation Improvement robot.Your main goal is, \
    to support the truth seeking conversation style, \
    your secondary goals is to try formulate messages in a  \
    way that don't creates side conversations if possible, \
    and replace thems definitions with more precise ones if necessary. \
    Your message examples should be in the same language as user message. \
    Take user message embrased with three backquotes, \
    and create 3 different versions of this message.

    Your output format is:
    Restate version: <restate, localized version of the message>

    Polite version: <polite, localized version of the message>

    Validate version: <validate, localized version of the message>

    {1}

    User message: ```{0}```
    """

    engine = ChatEngine()
    user_message = update.message.text
    chat = Chat(engine, message_versions_prompt.format(user_message, ""))
    answer = chat.get_answer("")
    update.message.reply_text(answer)

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("fix", fix_tone))

    dp.add_handler(MessageHandler(Filters.text, test_echo))

    dp.add_error_handler(error)

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=TELEGRAM_TOKEN)

    updater.bot.setWebhook('https://tg-multipurpose-bot.herokuapp.com/' + TELEGRAM_TOKEN)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
