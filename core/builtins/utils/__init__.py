import random
import re
from datetime import datetime

from config import Config
from core.types import PrivateAssets, Secret


confirm_command = [i for i in Config('confirm_command', ['是', '对', '對', 'yes', 'Yes', 'YES', 'y', 'Y']) if i.strip()]
command_prefix = [i for i in Config('command_prefix', ['~', '～']) if i.strip()]  # 消息前缀


class EnableDirtyWordCheck:
    status = False


def shuffle_joke(text: str):
    current_date = datetime.now().date()
    shuffle_rate = Config('shuffle_rate', 0.1, (float, int))
    have_fun = Config('???', cfg_type=bool)

    if have_fun or have_fun is None and (current_date.month == 4 and current_date.day == 1):
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
    else:
        return text


__all__ = ["confirm_command", "command_prefix", "shuffle_joke", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
