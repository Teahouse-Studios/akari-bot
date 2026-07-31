import re

from ff3 import FF3Cipher

from core.config.base import CoreSecretConfig


def decrypt_string(text):
    key = CoreSecretConfig.ff3_key
    tweak = CoreSecretConfig.ff3_tweak
    c = FF3Cipher.withCustomAlphabet(
        key,
        tweak,
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
    )
    d = []
    for i in range(0, len(text), 28):
        d.append(text[i : i + 28])
    dec_text = "".join([c.decrypt(i) for i in d])
    if m := re.match(r"^.{2}:(.*?):.{2}.*?$", dec_text):
        return m.group(1)
    return False
