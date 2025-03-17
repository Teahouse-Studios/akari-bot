from typing import Dict, List, Tuple

from google import genai
from google.genai import types

from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check
from ..formatting import parse_markdown
from ..models import INSTRUCTIONS

gemini_api_key = Config("google_gemini_api_key", secret=True, cfg_type=str, table_name="module_ai")

if gemini_api_key:
    client = genai.Client(api_key=gemini_api_key)
else:
    client = None

INSTRUCTIONS_LENGTH = len(INSTRUCTIONS)


def count_gemini_token(text: str) -> int:
    return len(text) + INSTRUCTIONS_LENGTH


async def ask_gemini(prompt: str,
                     model_name: str,
                     max_tokens: int = 4096,
                     temperature: float = 1,
                     top_p: float = 1,
                     frequency_penalty: float = 0,
                     presence_penalty: float = 0) -> Tuple[List[Dict[str, str]], int]:
    if not client:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    model_name = model_name.lstrip("!")  # 去除超级用户标记

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCTIONS,
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty
        )
    )

    res = response.text
    tokens = count_gemini_token(res)

    res = await check(res)
    resm = "".join(m["content"] for m in res)
    return parse_markdown(resm), tokens
