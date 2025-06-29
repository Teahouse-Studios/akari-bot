import io
from typing import List, Tuple

from openai import AsyncOpenAI
from PIL import Image as PILImage

from core.builtins import I18NContext, Image, Plain
from core.config import Config
from core.dirty_check import check
from core.logger import Logger
from .formatting import parse_markdown, generate_code_snippet, generate_latex, generate_md_table
from .setting import INSTRUCTIONS

max_tokens = Config("llm_max_tokens", 4096, table_name="module_ai")
temperature = Config("llm_temperature", 1, cfg_type=float, table_name="module_ai")
top_p = Config("llm_top_p", 1, cfg_type=float, table_name="module_ai")
frequency_penalty = Config("llm_frequency_penalty", 0, cfg_type=float, table_name="module_ai")
presence_penalty = Config("llm_presence_penalty", 0, cfg_type=float, table_name="module_ai")


async def ask_llm(prompt: str,
                  model_name: str,
                  api_url: str,
                  api_key: str) -> Tuple[List, int, int]:
    client = AsyncOpenAI(base_url=api_url, api_key=api_key)
    completion = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )

    if "reasoning_content" in completion.choices[0].message.model_extra:
        reasoning = completion.choices[0].message.model_extra["reasoning_content"]
        Logger.info(f"Thought: {reasoning}")
    res = completion.choices[0].message.content
    Logger.info(res)
    input_tokens = completion.usage.prompt_tokens
    output_tokens = completion.usage.completion_tokens

    res = await check(res)
    resm = "".join(m["content"] for m in res)
    blocks = parse_markdown(resm)

    chain = []
    for block in blocks:
        if block["type"] == "text":
            chain.append(Plain(block["content"]))
        elif block["type"] == "latex":
            content = block["content"]
            try:
                path = generate_latex(content)
                chain.append(Image(path))
            except Exception:
                chain.append(I18NContext("ai.message.text2img.error", text=content))
        elif block["type"] == "code":
            content = block["content"]["code"]
            try:
                content = await generate_code_snippet(content, block["content"]["language"])
                img = PILImage.open(io.BytesIO(content))
                chain.append(Image(img))
            except Exception:
                chain.append(I18NContext("ai.message.text2img.error", text=content))
        elif block["type"] == "table":
            content = block["content"]
            try:
                path_lst = await generate_md_table(content)
                for path in path_lst:
                    chain.append(Image(path))
            except Exception:
                chain.append(I18NContext("ai.message.text2img.error", text=content))

    return chain, input_tokens, output_tokens
