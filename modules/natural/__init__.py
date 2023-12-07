import openai

from config import Config
from core.builtins import Bot
from core.component import module

n = module('natural', alias='nl2c', developers=['Dianliang233'], desc='{natural.help}', required_superuser=True)

# Load your API key from an environment variable or secret management service
openai.api_key = Config('openai_api_key')
model = Config('nl2c_model')


@n.command('<text> {{natural.help}}')
async def _(msg: Bot.MessageSession, text: str):
    response = openai.Completion.create(
        model=model, prompt=f'{text}\n\n###\n\n', temperature=0, max_tokens=256, stop=['\n'])
    await msg.finish(response['choices'][0]['text'])
