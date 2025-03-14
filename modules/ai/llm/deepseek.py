from typing import Dict, List, Tuple

import orjson as json

from core.builtins import Bot
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check
from core.logger import Logger
from core.utils.http import post_url
from ..formatting import INSTRUCTIONS, parse_markdown

api_key = Config("ai_deepseek_api_key", secret=True, cfg_type=str)
api_url = "https://api.deepseek.com/v1/chat/completions"
model_name = "deepseek-chat"

if api_key:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
else:
    headers = None


async def ask_deepseek(msg: Bot.MessageSession, question: str) -> Tuple[List[Dict[str, str]], int]:
    if not headers:
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))

    payload = {
        "model": model_name,
        "messages": [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": question}],
        "temperature": 0.7,
        "top_p": 0.9
    }
    try:
        resp = await post_url(api_url,
                              data=json.dumps(payload),
                              headers=headers,
                              fmt="json",
                              timeout=60,
                              attempt=1)
        if resp:
            res = resp["choices"][0]["message"]["content"]
            tokens = int(resp["usage"]["total_tokens"])

            res = await check(res)
            resm = "".join(m["content"] for m in res)
            return parse_markdown(resm), tokens

    except Exception as e:
        Logger.error(f"DeepSeek LLM Error: {e}")
        raise RuntimeError(str(e))
