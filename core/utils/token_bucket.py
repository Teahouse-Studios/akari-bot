from datetime import datetime


class TokenBucket:
    def __init__(self, capacity: int, refill_interval: int):
        self.capacity = capacity
        self.rate = capacity / float(refill_interval) if refill_interval > 0 else capacity
        self.tokens = float(capacity)
        self.ts = datetime.now().timestamp()

    def consume(self, amount: int = 1) -> bool:
        now = datetime.now().timestamp()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
        self.ts = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def peek(self) -> float:
        now = datetime.now().timestamp()
        return min(self.capacity, self.tokens + (now - self.ts) * self.rate)
