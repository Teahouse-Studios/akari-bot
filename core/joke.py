import random
from datetime import datetime

from core.config import Config
from core.utils.http import url_pattern


def check_apr_fools() -> bool:
    current_date = datetime.now().date()
    enable_joke = Config("enable_joke", True, cfg_type=bool)

    return enable_joke and (current_date.month == 4 and current_date.day == 1)


def joke(text: str) -> str:
    if check_apr_fools():
        # 这里可能会增加使用不同玩笑方法的区分，但现在不太想做XD
        return shuffle_joke(text)
    return text


def shuffle_joke(text: str) -> str:
    shuffle_rate = Config("shuffle_rate", 0.1, (float, int))

    urls = url_pattern.finditer(text)
    url_positions = [(url.start(), url.end()) for url in urls]

    parts = []
    start = 0
    for start_pos, end_pos in url_positions:
        if start < start_pos:
            parts.append(text[start:start_pos])
        parts.append(text[start_pos:end_pos])
        start = end_pos
    if start < len(text):
        parts.append(text[start:])

    for i in range(0, len(parts), 2):
        text_list = list(parts[i])
        for j in range(len(text_list) - 1):
            if random.random() <= shuffle_rate:
                text_list[j], text_list[j + 1] = text_list[j + 1], text_list[j]
        parts[i] = "".join(text_list)
    return "".join(parts)
