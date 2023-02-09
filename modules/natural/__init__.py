import os
import openai
from core.builtins import Bot
from core.component import on_command
from config import Config

n = on_command('summary', developers=['Dianliang233'], desc='使用 InstructGPT 生成合并转发信息的聊天记录摘要。', required_superuser=True)

# Load your API key from an environment variable or secret management service
openai.api_key = Config('openai_api_key')

response = openai.Completion.create(model="text-davinci-003", prompt="Say this is a test", temperature=0, max_tokens=7)
