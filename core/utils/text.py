import sys
import datetime
from typing import TypeVar

T = TypeVar("T", str, bytes, bytearray)

if sys.version_info.minor > 8:  # PY39
    def remove_suffix(string: T, suffix: T) -> T:
        return string.removesuffix(suffix)

    def remove_prefix(string: T, prefix: T) -> T:
        return string.removeprefix(prefix)
else:
    def remove_suffix(string: T, suffix: T) -> T:
        return string[:-len(suffix)] if string.endswith(suffix) else string

    def remove_prefix(string: T, prefix: T) -> T:
        return string[len(prefix):] if string.startswith(prefix) else string


def parse_time_string(time_str):
    try:
        negative = False
        if time_str[0] == '+':
            time_str = time_str[1:]
        elif time_str[0] == '-':
            negative = True
            time_str = time_str[1:]
        tstr_split = time_str.split(':')
        hour = int(tstr_split[0])
        minute = 0
        if len(tstr_split) == 2:
            minute = int(tstr_split[1])
        if negative:
            hour = -hour
            minute = -minute
        return datetime.timedelta(hours=hour, minutes=minute)
    except ValueError:
        return datetime.timedelta()
