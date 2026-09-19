import time

from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.http import url_pattern
from core.utils.random import Random


def shuffle_joke(text: str) -> str:
    """按配置概率打乱文本以制造愚人节玩笑，URL 片段原样保留。

    仅在愚人节（4 月 1 日）且 ``enable_joke`` 开启时生效，否则原样返回。
    """
    current_time = time.localtime()
    if not (CoreConfig.enable_joke and current_time.tm_mon == 4 and current_time.tm_mday == 1):
        return text

    shuffle_rate = CoreConfig.shuffle_rate
    Logger.info(f"Raw: {text}")

    if url_pattern.fullmatch(text):
        return text

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
            if Random.random() <= shuffle_rate:
                text_list[j], text_list[j + 1] = text_list[j + 1], text_list[j]
        parts[i] = "".join(text_list)
    return "".join(parts)
