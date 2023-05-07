import openai
import os

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

openai.api_key = os.getenv('OPENAI_API_KEY')

# print(openai.Engine.list())

def print_lines(text, max_line_length=120):
    lines = []
    line = ""
    for word in text.split():
        if len(line + word) > max_line_length:
            lines.append(line)
            line = ""
        line += word + " "
    lines.append(line)

    for line in lines:
        print(line)

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

def message_versions(user_message):
    engine = ChatEngine()
    chat = Chat(engine, message_versions_prompt.format(user_message, ""))
    answer = chat.get_answer("")
    return answer

print(message_versions(""""""))
