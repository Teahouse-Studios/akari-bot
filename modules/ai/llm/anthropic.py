from typing import Dict, List, Tuple

import anthropic

from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check
from core.logger import Logger
from ..formatting import parse_markdown
from ..models import INSTRUCTIONS

api_base_url = Config("anthropic_api_url", cfg_type=str, table_name="module_ai")
api_key = Config("anthropic_api_key", secret=True, cfg_type=str, table_name="module_ai")

if api_key:
    client = anthropic.Anthropic(api_key=api_key, base_url=api_base_url)
else:
    client = None

INSTRUCTIONS_LENGTH = len(INSTRUCTIONS)


def count_claude_token(text: str) -> int:
    return len(text) + INSTRUCTIONS_LENGTH


async def ask_claude(prompt: str,
                     model_name: str,
                     max_tokens: int = 4096,
                     temperature: float = 1,
                     top_p: float = 1) -> Tuple[List[Dict[str, str]], int]:
    if not client:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    model_name = model_name.lstrip("!")  # 去除超级用户标记

    response = client.messages.create(
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        system=INSTRUCTIONS,
        messages=[{"role": "user", "content": prompt}]
    )

    res = response.content[0].text
    Logger.info(res)
    tokens = count_claude_token(res)

    res = await check(res)
    resm = "".join(m["content"] for m in res)
    return parse_markdown(resm), tokens
