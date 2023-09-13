import datetime

from core.types import MessageSession
from typing import Union


cd_lst = {}


class CoolDown:

    def __init__(self, k, msg: Union[MessageSession, str]):
        self.k = k
        self.msg = msg
        self.sender_id = self.msg
        if isinstance(self.sender_id, MessageSession):
            self.sender_id = self.sender_id.target.sender_id

    def add(self):
        if self.k not in cd_lst:
            cd_lst[self.k] = {}
        cd_lst[self.k][self.sender_id] = datetime.datetime.now().timestamp()

    def check(self, delay):
        if self.k not in cd_lst:
            return 0
        if self.sender_id in cd_lst[self.k]:
            if (d := (datetime.datetime.now().timestamp() - cd_lst[self.k][self.sender_id])) > delay:
                return 0
            else:
                return d
        else:
            return 0

    def reset(self):
        if self.k in cd_lst:
            if self.sender_id in cd_lst[self.k]:
                cd_lst[self.k].pop(self.sender_id)
        self.add()
