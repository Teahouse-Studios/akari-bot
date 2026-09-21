"""机器人内置的随机生成工具。``Random`` 由 ``use_secrets_random`` 配置选择后端，
``SecureRandom`` 始终使用 ``secrets``，用于密码、令牌和绑定口令等安全凭据。
"""

import base64
import random as pyrandom
import secrets
from typing import MutableSequence, Sequence, TypeVar

from core.config.base import CoreConfig

INF = 2**53
T = TypeVar("T")


class _RandomBackend:
    @staticmethod
    def random() -> float:
        return pyrandom.random()

    @staticmethod
    def randint(a: int, b: int) -> int:
        return pyrandom.randint(a, b)

    @staticmethod
    def uniform(a: float, b: float) -> float:
        return pyrandom.uniform(a, b)

    @staticmethod
    def randrange(start: int, stop: int | None = None, step: int = 1) -> int:
        return pyrandom.randrange(start, stop, step)

    @staticmethod
    def randbits(k: int) -> int:
        return pyrandom.getrandbits(k)

    @staticmethod
    def randbytes(n: int) -> bytes:
        return pyrandom.randbytes(n)

    @staticmethod
    def choice(seq: Sequence[T]) -> T:
        return pyrandom.choice(seq)

    @staticmethod
    def choices(population: Sequence[T], k: int = 1) -> list[T]:
        return pyrandom.choices(population, k=k)

    @staticmethod
    def sample(population: Sequence[T], k: int) -> list[T]:
        return pyrandom.sample(population, k)

    @staticmethod
    def shuffle(seq: MutableSequence[T]) -> MutableSequence[T]:
        pyrandom.shuffle(seq)
        return seq

    @staticmethod
    def randstr(length: int, chars: str) -> str:
        return "".join(pyrandom.choice(chars) for _ in range(length))

    @staticmethod
    def token_urlsafe(nbytes: int | None = None) -> str:
        random_bytes = pyrandom.randbytes(32 if nbytes is None else nbytes)
        return base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii")


class _SecretsBackend:
    @staticmethod
    def random() -> float:
        return secrets.randbelow(INF) / INF

    @staticmethod
    def randint(a: int, b: int) -> int:
        return secrets.randbelow(b - a + 1) + a

    @staticmethod
    def uniform(a: float, b: float) -> float:
        return a + (b - a) * secrets.randbelow(INF) / INF

    @staticmethod
    def randrange(start: int, stop: int | None = None, step: int = 1) -> int:
        if not stop:
            stop = start
            start = 0
        width = stop - start
        if step == 1 and width > 0:
            return start + secrets.randbelow(width)
        n = (width + step - 1) // step
        return start + step * secrets.randbelow(n)

    @staticmethod
    def randbits(k: int) -> int:
        return secrets.randbits(k)

    @staticmethod
    def randbytes(n: int) -> bytes:
        return secrets.token_bytes(n)

    @staticmethod
    def choice(seq: Sequence[T]) -> T:
        return secrets.choice(seq)

    @staticmethod
    def choices(population: Sequence[T], k: int = 1) -> list[T]:
        return [secrets.choice(population) for _ in range(k)]

    @staticmethod
    def sample(population: Sequence[T], k: int) -> list[T]:
        if k > len(population):
            raise ValueError("Sample larger than population or is negative")
        selected = []
        pool = list(population)
        for _ in range(k):
            idx = secrets.randbelow(len(pool))
            selected.append(pool.pop(idx))
        return selected

    @staticmethod
    def shuffle(seq: MutableSequence[T]) -> MutableSequence[T]:
        for i in reversed(range(1, len(seq))):
            j = secrets.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    @staticmethod
    def randstr(length: int, chars: str) -> str:
        return "".join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def token_urlsafe(nbytes: int | None = None) -> str:
        return secrets.token_urlsafe(nbytes)


class Random:
    """随机生成工具。"""

    use_secrets = CoreConfig.use_secrets_random
    _backend = _SecretsBackend() if use_secrets else _RandomBackend()

    @classmethod
    def random(cls) -> float:
        """
        返回0到1之间的随机浮点数。

        :return: 随机浮点数。
        """
        return cls._backend.random()

    @classmethod
    def randint(cls, a: int, b: int) -> int:
        """
        返回[a, b]范围内的随机整数。

        :param a: 下界。
        :param b: 上界。
        :return: 符合条件的随机整数。
        """
        return cls._backend.randint(a, b)

    @classmethod
    def uniform(cls, a: float, b: float) -> float:
        """
        返回[a, b]范围内的随机浮点数。

        :param a: 下界。
        :param b: 上界。
        :return: 符合条件的随机浮点数。
        """
        return cls._backend.uniform(a, b)

    @classmethod
    def randrange(cls, start: int, stop: int | None = None, step: int = 1) -> int:
        """
        返回范围内的随机整数，类似于`range`。

        :param start: 开始值。
        :param stop: 结束值，不包含在范围内。
        :param step: 递增次数。
        :return: 符合条件的随机整数。
        """
        return cls._backend.randrange(start, stop, step)

    @classmethod
    def randbits(cls, k: int) -> int:
        """
        返回k字节长度的随机整数。

        :param k: 字节长度。
        :return: 符合条件的随机整数。
        """
        return cls._backend.randbits(k)

    @classmethod
    def randbytes(cls, n: int) -> bytes:
        """
        生成n个随机字节。

        :param n: 字节数量。
        :return: 符合条件的随机字节。
        """
        return cls._backend.randbytes(n)

    @classmethod
    def choice(cls, seq: Sequence[T]) -> T:
        """
        从序列中随机选择一个元素。

        :param seq: 给定序列。
        :return: 序列内的随机元素。
        """
        return cls._backend.choice(seq)

    @classmethod
    def choices(cls, population: Sequence[T], k: int = 1) -> list[T]:
        """
        从总体中选择k个元素，允许重复。

        :param population: 给定序列。
        :param k: 选择的元素个数。
        :return: 序列内符合条件的随机元素列表。
        """
        return cls._backend.choices(population, k)

    @classmethod
    def sample(cls, population: Sequence[T], k: int) -> list[T]:
        """
        从总体中选择k个不重复元素。

        :param population: 给定序列。
        :param k: 选择的元素个数。
        :return: 序列内符合条件的随机元素列表。
        """
        return cls._backend.sample(population, k)

    @classmethod
    def shuffle(cls, seq: MutableSequence[T]) -> MutableSequence[T]:
        """
        随机打乱序列。

        :param seq: 给定序列。
        :return: 重新打乱后的序列。
        """
        return cls._backend.shuffle(seq)

    @classmethod
    def randstr(cls, length: int, chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") -> str:
        """
        生成指定长度的随机字符串。

        :param length: 字符串长度。
        :param chars: 可选的字符集，默认为大小写字母和数字。
        :return: 随机生成的字符串。
        """
        return cls._backend.randstr(length, chars)

    @classmethod
    def token_urlsafe(cls, nbytes: int | None = None) -> str:
        """生成适合用于 URL 的随机文本 token。"""
        return cls._backend.token_urlsafe(nbytes)


class SecureRandom(Random):
    """始终使用 ``secrets`` 后端的安全随机工具。"""

    use_secrets = True
    _backend = _SecretsBackend()
