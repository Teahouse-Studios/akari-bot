import re
from datetime import timedelta
from typing import Dict, Optional


def camel_to_snake(text: str, abbr_map: Optional[Dict[str, str]] = None) -> str:
    """驼峰命名转蛇形命名。"""
    text = re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()
    if abbr_map:
        for k, v in abbr_map.items():
            text = text.replace(k, v.lower())
    return text


def snake_to_camel(text: str,
                   upper: bool = True,
                   abbr_map: Optional[Dict[str, str]] = None) -> str:
    """蛇形命名转驼峰命名。

    :param upper: 是否转为大驼峰。（默认True）"""
    if abbr_map:
        for k, v in abbr_map.items():
            text = text.replace(v.lower(), k)
    words = text.split("_")
    if upper:
        return "".join(w.title() for w in words)
    return words[0].lower() + "".join(w.title() for w in words[1:])


def normalize_space(text: str) -> str:
    """删除字符串首尾的空格，以及中间多余的空格。"""
    words = text.split()
    return " ".join(words)


def truncate_text(text: str,
                  length: int,
                  suffix: str = "...") -> str:
    """按长度截断字符串。

    :param length: 允许的字符串长度。
    :param suffix: 截断后添加的后缀。
    """
    count = 0
    result = []

    for char in text:
        count += 1 if ord(char) < 0x7F else 2

        if count > length:
            return "".join(result) + suffix
        result.append(char)

    return text


def parse_time_string(text: str) -> timedelta:
    """将 UTC 偏移量字符串转为 timedelta。"""
    try:
        negative = False
        if text[0] == "+":
            text = text[1:]
        elif text[0] == "-":
            negative = True
            text = text[1:]
        tstr_split = text.split(":")
        hour = int(tstr_split[0])
        minute = 0
        if len(tstr_split) == 2:
            minute = int(tstr_split[1])
        if negative:
            hour = -hour
            minute = -minute
        return timedelta(hours=hour, minutes=minute)
    except Exception:
        return timedelta()


def generate_progress_bar(current: float,
                          total: float,
                          length: int = 10,
                          fill: str = "█",
                          empty: str = "░",
                          show_number: bool = False,
                          show_percent: bool = True,
                          precision: int = 1) -> str:
    """生成静态文本进度条。

    :param current: 当前进度。
    :param total: 目标数字。
    :param length: 进度条长度
    :param fill: 填充字符。
    :param empty: 空白字符。
    :param show_percent: 是否显示百分比。
    :param show_number: 是否显示数字形式 current/total。
    :param precision: 百分比小数点精度。
    :returns: 类似 `[███████░░░] 75.0%` 的文本进度条。
    """
    if total == 0:
        percent = 0
    else:
        percent = current / total

    filled_length = int(round(length * percent))
    bar = fill * filled_length + empty * (length - filled_length)

    display = f"[{bar}]"

    bar_info = []
    if show_number:
        bar_info.append(f"{current}/{total}")
    if show_percent:
        pct_text = f"{percent * 100:.{precision}f}%"
        bar_info.append(pct_text)

    if bar_info:
        display += " " + " ".join(bar_info)

    return display
