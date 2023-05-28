
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import logging
import os, sys, argparse, csv
import openai
import requests as req

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

class PromptsLib:
    csv_file: str = 'prompts.csv'
    prompts: dict = {}

    def download_csv(self):
        # https://github.com/f/awesome-chatgpt-prompts/blob/main/prompts.csv
        url = 'https://raw.githubusercontent.com/f/awesome-chatgpt-prompts/main/prompts.csv'
        r = req.get(url, allow_redirects=True)

        if r.status_code == 200:
            open(self.csv_file, 'wb').write(r.content)
        else:
            print('Error downloading prompts.csv')

    def load_prompts(self):
        with open(self.csv_file, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                self.prompts[row['act']] = row['prompt']

        self.load_local_prompts()

    def load_local_prompts(self):
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
        self.prompts['Tone editor'] = message_versions_prompt

    def actors(self) -> list:
        return list(self.prompts.keys())

    def prompt(self, act: str) -> str:
        return self.prompts[act]

class ChatEngine:
    model: str
    temp: float

    def __init__(self, model: str = "gpt-3.5-turbo", temp: float = 0):
        self.model = model
        self.temp = temp

class Chat:
    messages: list = []
    engine: ChatEngine

    def __init__(self, engine: ChatEngine):
        self.engine = engine

    def add_system_message(self, system_message: str) -> None:
        self.messages.append({"role": "system", "content": system_message})

    def add_assistant_message(self, assistant_message: str) -> None:
        self.messages.append({"role": "assistant", "content": assistant_message})

    def add_message(self, user_message: str) -> None:
        self.messages.append({"role": "user", "content": user_message})

    def get_completion(self) -> openai.ChatCompletion:
        return openai.ChatCompletion.create(
            model=self.engine.model,
            messages=self.messages,
            temperature=self.engine.temp,
        )

    def has_messages(self) -> bool:
        return len(self.messages) > 0

    def clear_messages(self) -> None:
        self.messages = []


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN')
openai.api_key   = os.getenv('OPENAI_API_KEY')
allow_users_list = os.getenv('ALLOW_USERS_LIST').split(',')

PORT = int(os.environ.get('PORT', 5000))

chat = Chat(ChatEngine())
prompts = PromptsLib()
prompts.load_prompts()


def check_user(user_name: str) -> bool:
    result: bool = user_name in allow_users_list
    if not result:
        logger.info(f'User {user_name} is not allowed to use this bot')
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    user = update.effective_user
    start_msg: str = f"""
    Hello, {user.mention_html()}!
    This is a chat bot with different roles.
    Available commands:
    /start - restart the conversation
    /list - list all available roles
    /role role_name - set your role
    /no_role - act as a regular chatGPT bot
    /clear - clear your role and restart the conversation
    """
    start_msg = start_msg.replace('    ', '')
    await update.message.reply_html(start_msg, reply_markup = ForceReply(selective=True))

async def role_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    await update.message.reply_text('Available roles: \n' + '\n'.join(prompts.actors()))

async def role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    user_message = update.message.text
    user_message = user_message.replace('/role ', '').strip()

    if user_message not in prompts.actors():
        await update.message.reply_text('Role not found')
        return

    chat.clear_messages()
    role_prompt = prompts.prompt(user_message)
    chat.add_system_message(role_prompt)
    await update.message.reply_text('Role start prompt is:' + '\n' + role_prompt)

    answer = chat.get_completion().choices[0].message["content"]
    await update.message.reply_text(answer)

async def no_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    chat.clear_messages()
    chat.add_system_message('Act as a regular chatGPT bot')
    await update.message.reply_text('GPT-3 chatbot mode activated')

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    chat.clear_messages()
    await update.message.reply_text('Chat cleared')

async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_user(update.effective_user.username):
        await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return

    user_message: str = update.message.text
    answer: str = ''

    if chat.has_messages():
        chat.add_message(user_message)
        answer = chat.get_completion().choices[0].message["content"]
    else:
        answer = 'Please set your role first'

    await update.message.reply_text(answer)

def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument('--download-prompts', action='store_true', help='Downloads prompts.csv')

    args = args.parse_args()

    if args.download_prompts:
        Prompts.download_csv()

    if len(sys.argv) == 1:
        logger.info('Starting telegram bot')
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("list", role_list))
        app.add_handler(CommandHandler("role", role))
        app.add_handler(CommandHandler("no_role", no_role))
        app.add_handler(CommandHandler("clear", clear))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all))

        app.add_error_handler(error)

        app.run_polling()

if __name__ == '__main__':
    main()
