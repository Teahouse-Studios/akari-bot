from typing import Dict, List, Tuple

import anthropic

from core.builtins import Bot
from core.config import Config
from core.dirty_check import check
from core.constants.exceptions import ConfigValueError, NoReportException
from core.logger import Logger
from ..formatting import INSTRUCTIONS, parse_markdown

api_key = Config("ai_claude_api_key", secret=True, cfg_type=str)
if api_key:
    client = anthropic.Anthropic(api_key=api_key)
else:
    client = None

INSTRUCTIONS_LENGTH = len(INSTRUCTIONS)
SPECIAL_TOKEN_LENGTH = 109


def count_claude_token(text: str) -> int:
    return len(text) + SPECIAL_TOKEN_LENGTH + INSTRUCTIONS_LENGTH


async def ask_claude(msg: Bot.MessageSession, question: str) -> Tuple[List[Dict[str, str]], int]:
    if not client:
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))

    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            temperature=0.7,
            system=INSTRUCTIONS,
            messages=[{"role": "user", "content": question}]
        )
    except anthropic.APIError as e:
        Logger.error(f"Claude LLM Error: {e}")
        if "rate_limit_exceeded" in str(e):
            raise NoReportException(msg.locale.t("ask.message.rate_limit_exceeded"))
        raise RuntimeError(str(e))

    res = response.content[0].text
    tokens = count_claude_token(res)

    res = await check(res)
    resm = "".join(m["content"] for m in res)
    return parse_markdown(resm), tokens
