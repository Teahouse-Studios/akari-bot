from typing import Any, Sequence, List, MutableSequence, Optional, TypeVar
import random
import secrets

from core.config import Config

INF = 2 ** 53
T = TypeVar('T')


class Random:
    use_secrets = Config('use_secrets_random', False)

    @classmethod
    def random(cls) -> float:
        """返回0到1之间的随机浮点数"""
        if cls.use_secrets:
            return secrets.randbelow(INF) / INF
        else:
            return random.random()

    @classmethod
    def randint(cls, a: int, b: int) -> int:
        """返回[a, b]范围内的随机整数"""
        if cls.use_secrets:
            return secrets.randbelow(b - a + 1) + a
        else:
            return random.randint(a, b)

    @classmethod
    def uniform(cls, a: float, b: float) -> float:
        """返回[a, b]范围内的随机浮点数"""
        if cls.use_secrets:
            return a + (b - a) * secrets.randbelow(INF) / INF
        else:
            return random.uniform(a, b)

    @classmethod
    def randrange(cls, start: int, stop: Optional[int] = None, step: int = 1) -> int:
        """返回范围内的随机整数，类似于range"""
        if cls.use_secrets:
            if not stop:
                stop = start
                start = 0
            width = stop - start
            if step == 1 and width > 0:
                return start + secrets.randbelow(width)
            n = (width + step - 1) // step
            return start + step * secrets.randbelow(n)
        else:
            return random.randrange(start, stop, step)

    @classmethod
    def randbits(cls, k: int) -> int:
        """返回k比特长度的随机整数"""
        if cls.use_secrets:
            return secrets.randbits(k)
        else:
            return random.getrandbits(k)

    @classmethod
    def randbytes(cls, n: int) -> bytes:
        """生成n个随机字节"""
        if cls.use_secrets:
            return secrets.token_bytes(n)
        else:
            return random.randbytes(n)

    @classmethod
    def choice(cls, seq: Sequence[T]) -> T:
        """从序列中随机选择一个元素"""
        if cls.use_secrets:
            return secrets.choice(seq)
        else:
            return random.choice(seq)

    @classmethod
    def choices(cls, population: Sequence[T], weights: Optional[Sequence[float]] = None, k: int = 1) -> List[T]:
        """从总体中选择k个元素，允许重复"""
        if cls.use_secrets:
            return [secrets.choice(population) for _ in range(k)]
        else:
            return random.choices(population, weights=weights, k=k)

    @classmethod
    def sample(cls, population: Sequence[T], k: int) -> List[T]:
        """从总体中选择k个不重复元素"""
        if cls.use_secrets:
            if k > len(population):
                raise ValueError("Sample larger than population or is negative")
            selected = []
            pool = list(population)
            for _ in range(k):
                idx = secrets.randbelow(len(pool))
                selected.append(pool.pop(idx))
            return selected
        else:
            return random.sample(population, k)

    @classmethod
    def shuffle(cls, seq: MutableSequence[T]) -> MutableSequence[T]:
        """随机打乱序列"""
        if cls.use_secrets:
            for i in reversed(range(1, len(seq))):
                j = secrets.randbelow(i + 1)
                seq[i], seq[j] = seq[j], seq[i]
        else:
            random.shuffle(seq)
        return seq
