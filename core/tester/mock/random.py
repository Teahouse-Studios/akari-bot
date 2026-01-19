import random as pyrandom
from typing import Sequence, MutableSequence, TypeVar

T = TypeVar("T")


class Random:
    def __init__(self, seed=0):
        pyrandom.seed(seed)

    @classmethod
    def random(cls) -> float:
        return pyrandom.random()

    @classmethod
    def randint(cls, a: int, b: int) -> int:
        return pyrandom.randint(a, b)

    @classmethod
    def uniform(cls, a: float, b: float) -> float:
        return pyrandom.uniform(a, b)

    @classmethod
    def randrange(cls, start: int, stop: int | None = None, step: int = 1) -> int:
        return pyrandom.randrange(start, stop, step)

    @classmethod
    def randbits(cls, k: int) -> int:
        return pyrandom.getrandbits(k)

    @classmethod
    def randbytes(cls, n: int) -> bytes:
        return pyrandom.randbytes(n)

    @classmethod
    def choice(cls, seq: Sequence[T]) -> T:
        return pyrandom.choice(seq)

    @classmethod
    def choices(cls, population: Sequence[T], k: int = 1) -> list[T]:
        return pyrandom.choices(population, k=k)

    @classmethod
    def sample(cls, population: Sequence[T], k: int) -> list[T]:
        return pyrandom.sample(population, k)

    @classmethod
    def shuffle(cls, seq: MutableSequence[T]) -> MutableSequence[T]:
        pyrandom.shuffle(seq)
        return seq
