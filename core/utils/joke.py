import random
import re
from datetime import datetime

from config import Config


shuffle_list = ['shuffle']


def joke(text: str):
    current_date = datetime.now().date()
    enable_joke = Config('enable_joke', cfg_type=bool)
#    joke_type = Config('joke_type', cfg_type=str)

    if enable_joke or (enable_joke is None and (current_date.month == 4 and current_date.day == 1)):
        return shuffle_joke(text)
    return text


def shuffle_joke(text: str) -> str:
    shuffle_rate = Config('shuffle_rate', 0.1, (float, int))

    urls = re.finditer(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
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
        parts[i] = ''.join(text_list)
    return ''.join(parts)


__all__ = ['joke', 'shuffle_joke']
