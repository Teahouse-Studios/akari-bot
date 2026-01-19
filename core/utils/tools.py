from collections.abc import Iterable as IterableABC
from typing import Any, Iterable, Generator

import orjson

from .format import *


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
