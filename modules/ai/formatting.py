import re
from typing import Dict, List

import matplotlib.pyplot as plt
import orjson as json

from core.utils.cache import random_cache_path
from core.utils.http import post_url
from core.utils.image_table import ImageTable, image_table_render


def parse_markdown(md: str) -> List[Dict[str, str]]:
    code_block_pattern = r"```(\w+)?\n([\s\S]*?)\n```"  # 代码块
    block_latex_pattern = r"\$\$([\s\S]*?)\$\$"  # 块级 LaTeX
    inline_latex_pattern = r"(?<!\$)`?\$([^\n\$]+?)\$`?(?!\$)"  # 行内 LaTeX
    table_pattern = r"(?:\|.*\|\n)+\|(?:[-:| ]+)\|\n(?:\|.*\|\n)+"  # Markdown 表格
    # 先分块
    text_split_pattern = r"(```[\s\S]*?```|\$\$[\s\S]*?\$\$|\$[^\n\$]+?\$|(?:\|.*\|\n)+\|(?:[-:| ]+)\|\n(?:\|.*\|\n)+)"

    blocks = []
    last_end = 0

    for match in re.finditer(text_split_pattern, md):
        start, end = match.span()
        content = match.group(0)

        if start > last_end:
            blocks.append({"type": "text", "content": md[last_end:start]})

        if content.startswith("```"):
            code_match = re.match(code_block_pattern, content)
            if code_match:
                language = code_match.group(1)
                code = code_match.group(2).strip()

                if language:
                    blocks.append({"type": "code", "content": {"language": language, "code": code}})
                else:
                    blocks.append({"type": "text", "content": f"```\n{code}\n```"})

        elif content.startswith("$$"):
            latex_match = re.match(block_latex_pattern, content)
            if latex_match:
                blocks.append({"type": "latex", "content": latex_match.group(1).strip()})

        elif content.startswith("$"):
            latex_match = re.match(inline_latex_pattern, content)
            if latex_match:
                blocks.append({"type": "latex", "content": latex_match.group(1).strip()})

        elif re.match(table_pattern, content):
            blocks.append({"type": "table", "content": content.strip()})

        last_end = end

    if last_end < len(md):
        blocks.append({"type": "text", "content": md[last_end:]})

    return blocks


def generate_latex(formula: str):
    fig, ax = plt.subplots()
    text = ax.text(0.5, 0.5, f"${formula}$", fontsize=20, ha="center", va="center")
    ax.set_axis_off()

    fig.canvas.draw()
    bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())

    width, height = bbox.width / fig.dpi, bbox.height / fig.dpi
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(width, height))
    ax.text(0.5, 0.5, f"${formula}$", fontsize=20, ha="center", va="center")
    ax.set_axis_off()

    path = f"{random_cache_path()}.png"
    plt.savefig(path, dpi=300, bbox_inches="tight", transparent=True, pad_inches=0.1)
    plt.close()

    return path


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


async def generate_md_table(table: str):
    lines = table.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("Invalid Markdown table format.")

    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    data = []

    for line in lines[2:]:
        row = [cell.strip() for cell in line.split("|") if cell.strip()]
        if row:
            data.append(row)

    if not data:
        raise ValueError("No data found in Markdown table.")

    image_table = ImageTable(data=data, headers=headers)
    imgs = await image_table_render(image_table)
    if imgs:
        img_lst = []
        for img in imgs:
            img_lst.append(img)
        return img_lst
    raise RuntimeError("Generation failed.")
