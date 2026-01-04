import random
from typing import Sequence, MutableSequence, TypeVar

T = TypeVar("T")


class Random:
    def __init__(self, seed=0):
        random.seed(seed)

    @classmethod
    def random(cls) -> float:
        return random.random()

    @classmethod
    def randint(cls, a: int, b: int) -> int:
        return random.randint(a, b)

    @classmethod
    def uniform(cls, a: float, b: float) -> float:
        return random.uniform(a, b)

    @classmethod
    def randrange(cls, start: int, stop: int | None = None, step: int = 1) -> int:
        return random.randrange(start, stop, step)

    @classmethod
    def randbits(cls, k: int) -> int:
        return random.getrandbits(k)

    @classmethod
    def randbytes(cls, n: int) -> bytes:
        return random.randbytes(n)

    @classmethod
    def choice(cls, seq: Sequence[T]) -> T:
        return random.choice(seq)

    @classmethod
    def choices(cls, population: Sequence[T], k: int = 1) -> list[T]:
        return random.choices(population, k=k)

    @classmethod
    def sample(cls, population: Sequence[T], k: int) -> list[T]:
        return random.sample(population, k)

    @classmethod
    def shuffle(cls, seq: MutableSequence[T]) -> MutableSequence[T]:
        random.shuffle(seq)
        return seq
