"""
机器人内置的随机生成工具。在配置文件中将`use_secrets_random`设为`true`时使用`secrets`库，否则默认使用`random`库。

请在模块中使用此库进行随机生成，避免导入`random`或`secrets`库。
"""
import random
import secrets
from typing import Sequence, List, MutableSequence, Optional, TypeVar

from core.config import Config

INF = 2**53
T = TypeVar("T")


class Random:
    """随机生成工具。"""
    use_secrets = Config("use_secrets_random", False)

    @classmethod
    def random(cls) -> float:
        """
        返回0到1之间的随机浮点数。

        :return: 随机浮点数。
        """
        if cls.use_secrets:
            return secrets.randbelow(INF) / INF
        return random.random()

    @classmethod
    def randint(cls, a: int, b: int) -> int:
        """
        返回[a, b]范围内的随机整数。

        :param a: 下界。
        :param b: 上界。
        :return: 符合条件的随机整数。
        """
        if cls.use_secrets:
            return secrets.randbelow(b - a + 1) + a
        return random.randint(a, b)

    @classmethod
    def uniform(cls, a: float, b: float) -> float:
        """
        返回[a, b]范围内的随机浮点数。

        :param a: 下界。
        :param b: 上界。
        :return: 符合条件的随机浮点数。
        """
        if cls.use_secrets:
            return a + (b - a) * secrets.randbelow(INF) / INF
        return random.uniform(a, b)

    @classmethod
    def randrange(cls, start: int, stop: Optional[int] = None, step: int = 1) -> int:
        """
        返回范围内的随机整数，类似于`range`。

        :param start: 开始值。
        :param stop: 结束值，不包含在范围内。
        :param step: 递增次数。
        :return: 符合条件的随机整数。
        """
        if cls.use_secrets:
            if not stop:
                stop = start
                start = 0
            width = stop - start
            if step == 1 and width > 0:
                return start + secrets.randbelow(width)
            n = (width + step - 1) // step
            return start + step * secrets.randbelow(n)
        return random.randrange(start, stop, step)

    @classmethod
    def randbits(cls, k: int) -> int:
        """
        返回k字节长度的随机整数。

        :param k: 字节长度。
        :return: 符合条件的随机整数。
        """
        if cls.use_secrets:
            return secrets.randbits(k)
        return random.getrandbits(k)

    @classmethod
    def randbytes(cls, n: int) -> bytes:
        """
        生成n个随机字节。

        :param n: 字节数量。
        :return: 符合条件的随机字节。
        """
        if cls.use_secrets:
            return secrets.token_bytes(n)
        return random.randbytes(n)

    @classmethod
    def choice(cls, seq: Sequence[T]) -> T:
        """
        从序列中随机选择一个元素。

        :param seq: 给定序列。
        :return: 序列内的随机元素。
        """
        if cls.use_secrets:
            return secrets.choice(seq)
        return random.choice(seq)

    @classmethod
    def choices(cls, population: Sequence[T], k: int = 1) -> List[T]:
        """
        从总体中选择k个元素，允许重复。

        :param population: 给定序列。
        :param k: 选择的元素个数。
        :return: 序列内符合条件的随机元素列表。
        """
        if cls.use_secrets:
            return [secrets.choice(population) for _ in range(k)]
        return random.choices(population, k=k)

    @classmethod
    def sample(cls, population: Sequence[T], k: int) -> List[T]:
        """
        从总体中选择k个不重复元素。

        :param population: 给定序列。
        :param k: 选择的元素个数。
        :return: 序列内符合条件的随机元素列表。
        """
        if cls.use_secrets:
            if k > len(population):
                raise ValueError("Sample larger than population or is negative")
            selected = []
            pool = list(population)
            for _ in range(k):
                idx = secrets.randbelow(len(pool))
                selected.append(pool.pop(idx))
            return selected
        return random.sample(population, k)

    @classmethod
    def shuffle(cls, seq: MutableSequence[T]) -> MutableSequence[T]:
        """
        随机打乱序列。

        :param seq: 给定序列。
        :return: 重新打乱后的序列。
        """
        if cls.use_secrets:
            for i in reversed(range(1, len(seq))):
                j = secrets.randbelow(i + 1)
                seq[i], seq[j] = seq[j], seq[i]
        else:
            random.shuffle(seq)
        return seq
