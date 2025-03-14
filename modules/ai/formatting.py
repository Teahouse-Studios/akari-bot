import re
from typing import Dict, List

import orjson as json

from core.utils.http import get_url, post_url

INSTRUCTIONS = """You are a helpful assistant. You are the chat mode of AkariBot (Chinese: 小可), a chat bot created by Teahouse Studios (Chinese: 茶馆工作室)

Provide informative, logical, and engaging answers with details to cover multiple aspects of the question. Use emojis when appropriate for added interest.

If the user asks for help, tell them to type "~help".

Use LaTeX to output math, physics or chemistry expressions whenever possible, and surround the expression with dollar signs `$`, e.g. $E=mc^2$.

Refrain from answering any questions related to politics, geopolitics, political figures, politicians, political events or political ideologies. Decline to answer immediately and tell the user that the question is inappropriate."""


def parse_markdown(md: str) -> List[Dict[str, str]]:
    regex = r"```[\s\S]*?\n```|\$\$[\s\S]*?\$\$|\$.*?\$|\\\[[\s\S]*?\\\]|[^`$\n]+"

    blocks = []
    for match in re.finditer(regex, md):
        content = match.group(0)

        if content.startswith("```"):
            block = "code"
            try:
                language, code = re.match(r"```(.*)\n([\s\S]*?)\n```", content).groups()
            except AttributeError:
                raise ValueError("Code block is missing language or code.")
            content = {"language": language, "code": code}
        elif content.startswith("$$") and content.endswith("$$"):
            block = "latex"
            content = content[2:-2].strip()
        elif content.startswith("$") and content.endswith("$"):
            block = "latex"
            content = content[1:-1].strip()
        elif content.startswith("\\[") and content.endswith("\\]"):
            block = "latex"
            content = content[2:-2].strip()
        else:
            block = "text"

        blocks.append({"type": block, "content": content})

    return blocks


async def generate_latex(formula: str):
    resp = await post_url(
        url="https://wikimedia.org/api/rest_v1/media/math/check/inline-tex",
        data=json.dumps({"q": formula}),
        headers={"content-type": "application/json"},
        fmt="headers",
    )
    if resp:
        location = resp.get("x-resource-location")
        if not location:
            raise ValueError("Cannot get LaTeX resource location")

    return await get_url(
        url=f"https://wikimedia.org/api/rest_v1/media/math/render/png/{location}",
        fmt="content",
    )


async def generate_code_snippet(code: str, language: str):
    return await post_url(
        url="https://sourcecodeshots.com/api/image",
        data=json.dumps(
            {
                "code": code,
                "settings": {
                    "language": language,
                    "theme": "night-owl",
                },
            }
        ),
        headers={"content-type": "application/json"},
        fmt="content",
    )
