import re

from core.config import config
from ff3 import FF3Cipher

from core.utils.text import random_string

def decrypt_string(text):
    key = config('ff3_key', random_string(32), secret=True)
    tweak = config('ff3_tweak', random_string(14), secret=True)
    c = FF3Cipher.withCustomAlphabet(
        key, tweak, "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
    d = []
    for i in range(0, len(text), 28):
        d.append(text[i:i + 28])
    dec_text = ''.join([c.decrypt(i) for i in d])
    if m := re.match(r'^.{2}:(.*?):.{2}.*?$', dec_text):
        return m.group(1)
    return False
