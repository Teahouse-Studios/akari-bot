import sys
from pathlib import Path

import openai

from config import Config

file = Path(__file__).resolve()
parent, root = file.parent, file.parents[2]
sys.path.append(str(root))

# Load your API key from an environment variable or secret management service
openai.api_key = Config('openai_api_key')
model = Config('nl2c_model')

while True:
    i = input('>> ')
    response = openai.Completion.create(
        model=model, prompt=f'{i}\n\n###\n\n', temperature=0, max_tokens=256, stop=['\n'])
    print(response['choices'][0]['text'])
