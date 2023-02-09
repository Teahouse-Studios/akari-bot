import os
import openai
from core.builtins import Bot
from core.component import on_command
from config import Config

n = on_command('natural', alias=['nl2c'], developers=['Dianliang233'], desc='使用 InstructGPT 把自然语言转换成小可命令。', required_superuser=True)

# Load your API key from an environment variable or secret management service
openai.api_key = Config('openai_api_key')
model = Config('nl2c_model')

@n.handle('<text> {使用 InstructGPT 把自然语言转换成小可命令。}')
async def _(msg: Bot.MessageSession):
    i = msg.parsed_msg['<text>']
    response = openai.Completion.create(
            model=model, prompt=f'{i}\n\n###\n\n', temperature=0, max_tokens=256, stop=['\n'])
    await msg.finish(response['choices'][0]['text'])
