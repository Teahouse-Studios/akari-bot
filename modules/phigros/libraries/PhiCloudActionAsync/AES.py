# ----------------------- 导入 -----------------------
from base64 import b64decode

from Crypto.Cipher.AES import new, MODE_CBC, block_size
from Crypto.Util.Padding import unpad, pad

# ---------------------- 定义 ----------------------

aes_key = b64decode("6Jaa0qVAJZuXkZCLiOa/Ax5tIZVu+taKUN1V1nqwkks=")
aes_iv = b64decode("Kk/wisgNYwcAV8WVGMgyUw==")


def encrypt(data: bytes):
    """
    AES CBC 加密

    参数:
        data (bytes): 要加密的数据

    返回:
        (bytes): 加密后的数据
    """
    data = pad(data, block_size)
    return new(aes_key, MODE_CBC, aes_iv).encrypt(data)


def decrypt(data: bytes):
    """
    AES CBC 解密

    参数:
        data (bytes): 要解密的数据

    返回:
        (bytes): 解密后的数据
    """
    data = new(aes_key, MODE_CBC, aes_iv).decrypt(data)
    return unpad(data, block_size)
