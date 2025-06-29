from datetime import timedelta
from typing import Any, Union


def convert2lst(elements: Union[str, list, tuple]) -> list:
    if isinstance(elements, str):
        return [elements]
    if isinstance(elements, tuple):
        return list(elements)
    return elements


def isfloat(num_str: Any) -> bool:
    """
    检查字符串是否符合float。
    """
    try:
        float(num_str)
        return True
    except ValueError:
        return False


def isint(num_str: Any) -> bool:
    """
    检查字符串是否符合int。
    """
    try:
        int(num_str)
        return True
    except ValueError:
        return False


def parse_time_string(time_str: str) -> timedelta:
    try:
        negative = False
        if time_str[0] == "+":
            time_str = time_str[1:]
        elif time_str[0] == "-":
            negative = True
            time_str = time_str[1:]
        tstr_split = time_str.split(":")
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


def remove_duplicate_space(text: str) -> str:
    """删除命令中间多余的空格。

    :param text: 字符串。
    :returns: 净化后的字符串。"""
    strip_display_space = text.split(" ")
    for _ in strip_display_space:
        if "" in strip_display_space:
            strip_display_space.remove("")
        else:
            break
    text = " ".join(strip_display_space)
    return text
