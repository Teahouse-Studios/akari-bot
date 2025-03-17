from typing import Dict, List, Tuple

import orjson as json

from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check
from core.logger import Logger
from core.utils.http import post_url
from ..formatting import parse_markdown
from ..models import INSTRUCTIONS

api_base_url = Config("deepseek_api_url", cfg_type=str, table_name="module_ai", get_url=True)
api_base_url = api_base_url if api_base_url else "https://api.deepseek.com/v1/"
api_url = f"{api_base_url}chat/completions"
api_key = Config("deepseek_api_key", secret=True, cfg_type=str, table_name="module_ai")

if api_key:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
else:
    headers = None


async def ask_deepseek(prompt: str,
                       model_name: str,
                       max_tokens: int = 4096,
                       temperature: float = 1,
                       top_p: float = 1,
                       frequency_penalty: float = 0,
                       presence_penalty: float = 0) -> Tuple[List[Dict[str, str]], int]:
    if not headers:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    model_name = model_name.lstrip("!")  # 去除超级用户标记

    payload = {
        "model": model_name,
        "messages": [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": prompt}],
        "frequency_penalty": float(frequency_penalty),
        "presence_penalty": float(presence_penalty),
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_tokens": max_tokens
    }

    resp = await post_url(api_url,
                          data=json.dumps(payload),
                          headers=headers,
                          fmt="json",
                          timeout=60,
                          attempt=1)
    if resp:
        res = resp["choices"][0]["message"]["content"]
        thought = resp["choices"][0]["message"].get("reasoning_content")
        if thought:
            Logger.info(f"Thought: {thought}")
        tokens = int(resp["usage"]["total_tokens"])

        res = await check(res)
        resm = "".join(m["content"] for m in res)
        return parse_markdown(resm), tokens
