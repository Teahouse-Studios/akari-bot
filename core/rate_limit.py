import time
from typing import Literal, Self, List

from attr import define


@define
class Usage:
    sender_id: str
    time: int


@define
class RateLimiter:
    limit: int
    '''Maximum number of usage in the period'''

    period_s: int
    '''Period in seconds'''

    usages: List[Usage]

    limit_type: Literal['sender', 'target'] = 'target'

    def clean(self):
        now = time.time()
        for i in self.usages:
            if i.time + self.period_s < now:
                self.usages.remove(i)
            else:
                break

    def check(self, sender_id: str) -> bool:
        '''
        Check if the sender is rate limited. If so, it will return True and also add a
        usage to the rate limiter.
        '''
        self.clean()
        check_list = self.usages if self.limit_type == 'target' else [
            i for i in self.usages if i.sender_id == sender_id]
        if len(check_list) >= self.limit:
            return True
        self.usages.append(Usage(sender_id=sender_id, time=int(time.time())))
        return False

    def reset(self):
        self.usages = []

    @classmethod
    def check_multiple(cls, rate_limiters: list[Self], user_id: str) -> bool:
        return any(i.check(user_id) for i in rate_limiters)
