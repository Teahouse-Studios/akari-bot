import time
from typing import Union


class TokenBucket:
    def __init__(self, capacity: int, refill_interval: int):
        self.capacity = capacity
        self.rate = capacity / float(refill_interval) if refill_interval > 0 else capacity
        self.tokens = float(capacity)
        self.ts = time.time()

    def _refill(self):
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
        self.ts = now

    def consume(self, amount: int = 1) -> bool:
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
        self.ts = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def peek(self) -> float:
        now = time.time()
        return min(self.capacity, self.tokens + (now - self.ts) * self.rate)

    def wait_time(self, amount: int = 1) -> float:
        self._refill()
        if self.tokens >= amount:
            return 0.0
        return (amount - self.tokens) / self.rate

    def refill(self, amount: Union[int, float] = 1):
        self._refill()
        self.tokens = min(self.capacity, self.tokens + amount)

    def __repr__(self):
        return f"TokenBucket(capacity={self.capacity}, tokens={self.peek():.2f}, rate={self.rate:.2f}/s)"

    def __bool__(self):
        return self.peek() > 0
