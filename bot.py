
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import logging
import os, sys, argparse, csv
import openai
import requests as req

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

class PromptsCollection:
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

    def roles(self) -> list:
        return list(self.prompts.keys())

    def role_prompt(self, role: str) -> str:
        return self.prompts[role]

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

openai.api_key = os.getenv('OPENAI_API_KEY')

class ConsensusTalkBot:
    logger: logging.Logger
    bot: Application
    allow_users_list: list[str] = os.getenv('ALLOW_USERS_LIST').split(',')
    prompts = PromptsCollection()
    chat: Chat = Chat(ChatEngine())

    def __init__(self, logger: logging.Logger, token: str) -> None:
        self.logger = logger
        self.prompts.load_prompts()

        self.bot = Application.builder().token(token).build()

        self.bot.add_handler(CommandHandler("start", self.start))
        self.bot.add_handler(CommandHandler("list", self.role_list))
        self.bot.add_handler(CommandHandler("role", self.role))
        self.bot.add_handler(CommandHandler("no_role", self.no_role))
        self.bot.add_handler(CommandHandler("clear", self.clear))

        self.bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.catch_all))
        self.bot.add_error_handler(self.error)

    def start_bot(self):
        self.logger.info('Starting telegram bot')
        self.bot.run_polling()

    async def check_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        user_name: str = update.effective_user.username
        result: bool = user_name in self.allow_users_list
        if not result:
            await update.message.reply_text('Sorry, you are not allowed to use this bot')
        return result

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        start_msg: str = f"""
        Hello, {update.effective_user.mention_html()}!
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

    async def role_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        await update.message.reply_text('Available roles: \n' + '\n'.join(self.prompts.roles()))

    async def role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        requested_role = update.message.text
        requested_role = requested_role.replace('/role ', '').strip()

        if requested_role not in self.prompts.roles():
            await update.message.reply_text('Role not found')
            return

        self.chat.clear_messages()
        role_prompt = self.prompts.role_prompt(requested_role)
        self.chat.add_system_message(role_prompt)
        await update.message.reply_text('Role start prompt is:' + '\n' + role_prompt)

        answer = self.chat.get_completion().choices[0].message["content"]
        await update.message.reply_text(answer)

    async def no_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        self.chat.clear_messages()
        self.chat.add_system_message('Act as a regular chatGPT bot')
        await update.message.reply_text('GPT-3 chatbot mode activated')

    async def catch_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        user_message: str = update.message.text
        answer: str = ''

        if self.chat.has_messages():
            self.chat.add_message(user_message)
            answer = self.chat.get_completion().choices[0].message["content"]
        else:
            answer = 'Please set your role first'

        await update.message.reply_text(answer)

    async def clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.check_user(update, context):
            return

        self.chat.clear_messages()
        await update.message.reply_text('Chat cleared')

    def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument('--download-prompts', action='store_true', help='Downloads prompts.csv')

    args = args.parse_args()

    if args.download_prompts:
        PromptsCollection().download_csv()

    if len(sys.argv) == 1:
        bot = ConsensusTalkBot(logger, os.getenv('TELEGRAM_TOKEN'))
        bot.start_bot()

if __name__ == '__main__':
    main()
