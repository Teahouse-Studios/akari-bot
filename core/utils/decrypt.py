import re

from ff3 import FF3Cipher

from core.config import Config


def decrypt_string(text):
    key = Config("ff3_key", "25FDA29B045EE0034966792BAD5AF1C0", secret=True)
    tweak = Config("ff3_tweak", "1E915EC4922E78", secret=True)
    c = FF3Cipher.withCustomAlphabet(
        key,
        tweak,
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~",
    )
    d = []
    for i in range(0, len(text), 28):
        d.append(text[i: i + 28])
    dec_text = "".join([c.decrypt(i) for i in d])
    if m := re.match(r"^.{2}:(.*?):.{2}.*?$", dec_text):
        return m.group(1)
    return False
