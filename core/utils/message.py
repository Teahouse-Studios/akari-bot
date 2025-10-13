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
    检查字符串是否符合 `float`。
    """
    try:
        float(num_str)
        return True
    except ValueError:
        return False


def isint(num_str: Any) -> bool:
    """
    检查字符串是否符合 `int`。
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


def generate_progress_bar(current: float, 
                 total: float, 
                 length: int = 10,
                 fill: str = "█",
                 empty: str = "░",
                 show_number: bool = False,
                 show_percent: bool = True,
                 precision: int = 1):
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
        pct_text = f"{percent*100:.{precision}f}%"
        bar_info.append(pct_text)

    if bar_info:
        display += " " + " ".join(bar_info)

    return display
