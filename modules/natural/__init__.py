import os
import openai
from core.builtins import Bot
from core.component import module
from config import Config

n = module('natural', alias=['nl2c'], developers=['Dianliang233'], desc='{natural.help}')

# Load your API key from an environment variable or secret management service
openai.api_key = Config('openai_api_key')
model = Config('nl2c_model')

@n.handle('<text> {{natural.help}}')
async def _(msg: Bot.MessageSession):
    i = msg.parsed_msg['<text>']
    response = openai.Completion.create(
            model=model, prompt=f'{i}\n\n###\n\n', temperature=0, max_tokens=256, stop=['\n'])
    await msg.finish(response['choices'][0]['text'])
