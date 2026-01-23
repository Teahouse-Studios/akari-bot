import re
from collections.abc import Iterable as IterableABC
from datetime import timedelta
from typing import Any, Iterable, Generator

import orjson


def convert_list(v: Any) -> list:
    """将其他类型转为列表。"""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if is_iterable(v):
        return list(v)
    return [v]


def is_iterable(obj: Any) -> bool:
    """判断对象是否是字符串以外的可迭代对象。"""
    return isinstance(obj, IterableABC) and not isinstance(obj, (str, bytes))


def is_json_serializable(obj: Any) -> bool:
    """检查对象是否可以被 JSON 序列化。"""
    try:
        orjson.dumps(obj)
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def chunk_list(iterable: Iterable[Any],
               chunk_size: int,
               reverse: bool = False) -> Generator[list[Any], None, None]:
    """将可迭代对象分块，返回生成器。"""
    if isinstance(iterable, (str, bytes)):
        raise TypeError("Type str is not supported")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if reverse:
        iterable = reversed(list(iterable))

    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def unique_list(iterable: Iterable[Any], reverse: bool = False) -> list[Any]:
    """在不破坏顺序下去重可迭代对象。"""
    if isinstance(iterable, (str, bytes)):
        raise TypeError("Type str is not supported")

    if reverse:
        iterable = reversed(list(iterable))

    seen = set()
    result = []
    for x in iterable:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def flatten_list(nested_iterable: Iterable[Any]) -> list[Any]:
    """将嵌套可迭代对象扁平化。"""
    if isinstance(nested_iterable, dict):
        raise TypeError("Type dict is not supported, use flatten_dict instead")

    flat_list = []
    for item in nested_iterable:
        if is_iterable(item):
            flat_list.extend(flatten_list(item))
        else:
            flat_list.append(item)
    return flat_list


def flatten_dict(nested_dict: dict[str, Any],
                 parent_key: str = "",
                 sep: str = ".") -> dict[str, Any]:
    """将嵌套字典扁平化。"""
    flat_dict = {}
    for k, v in nested_dict.items():
        flat_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            flat_dict.update(flatten_dict(v, flat_key, sep))
        else:
            flat_dict[flat_key] = v
    return flat_dict


def unflatten_dict(flat_dict: dict[str, Any], sep: str = ".") -> dict[str, Any]:
    """将扁平化字典还原。"""
    nested_dict: dict[str, Any] = {}
    for flat_key, value in flat_dict.items():
        keys = flat_key.split(sep)
        d = nested_dict
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value
    return nested_dict


def is_float(obj: Any) -> bool:
    """检查对象是否符合 `float` 类型。"""
    try:
        float(str(obj))
        return True
    except ValueError:
        return False


def is_int(obj: Any) -> bool:
    """检查对象是否符合 `int` 类型。"""
    try:
        if isinstance(obj, float):
            return obj.is_integer()
        int(str(obj))
        return True
    except ValueError:
        return False


def camel_to_snake(text: str, abbr_map: dict[str, str] | None = None) -> str:
    """驼峰命名转蛇形命名。"""
    if abbr_map:
        for k, v in abbr_map.items():
            text = text.replace(k, v)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()


def snake_to_camel(text: str,
                   upper: bool = True,
                   abbr_map: dict[str, str] | None = None) -> str:
    """蛇形命名转驼峰命名。

    :param upper: 是否转为大驼峰。（默认True）"""
    if abbr_map:
        for k, v in abbr_map.items():
            text = text.replace(v, k)
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
