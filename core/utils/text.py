import random
import re
from datetime import timedelta
from typing import TypeVar

from ff3 import FF3Cipher

from core.config import Config, isint, isfloat

T = TypeVar("T", str, bytes, bytearray)


def parse_time_string(time_str: str) -> timedelta:
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
        return timedelta(hours=hour, minutes=minute)
    except Exception:
        return timedelta()


def random_string(length: int) -> str:
    return ''.join(random.choices("0123456789ABCDEF", k=length))


def decrypt_string(text):
    key = Config('ff3_key', random_string(32))
    tweak = Config('ff3_tweak', random_string(14))
    c = FF3Cipher.withCustomAlphabet(
        key, tweak, "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
    d = []
    for i in range(0, len(text), 28):
        d.append(text[i:i + 28])
    dec_text = ''.join([c.decrypt(i) for i in d])
    if m := re.match(r'^.{2}:(.*?):.{2}.*?$', dec_text):
        return m.group(1)
    return False


__all__ = ["parse_time_string", "random_string", "decrypt_string", "isint", "isfloat"]
