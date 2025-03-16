from typing import Dict, List, Tuple

import tiktoken
import openai

from core.builtins import Bot
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check
from ..formatting import INSTRUCTIONS, parse_markdown

api_base_url = Config("openai_api_url", cfg_type=str, table_name="module_ai")
api_key = Config("openai_api_key", secret=True, cfg_type=str, table_name="module_ai")

if api_key:
    client = openai.OpenAI(api_key=api_key, base_url=api_base_url)
else:
    client = None


def count_openai_token(model_name: str, text: str) -> int:
    enc = tiktoken.encoding_for_model(model_name)
    INSTRUCTIONS_LENGTH = len(enc.encode(INSTRUCTIONS))
    return len(enc.encode(text, allowed_special="all")) + INSTRUCTIONS_LENGTH


async def ask_chatgpt(msg: Bot.MessageSession,
                      question: str,
                      model_name: str,
                      max_tokens: int = 4096,
                      temperature: float = 1,
                      top_p: float = 1,
                      frequency_penalty: float = 0,
                      presence_penalty: float = 0) -> Tuple[List[Dict[str, str]], int]:
    if not client:
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": question}
        ],
        max_completion_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )

    res = response.choices[0].message.content
    tokens = count_openai_token(model_name, res)

    res = await check(res)
    resm = "".join(m["content"] for m in res)
    return parse_markdown(resm), tokens
