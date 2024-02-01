import datetime

from core.types import MessageSession
from typing import Dict, Union


_cd_lst: Dict[str, Dict[Union[MessageSession, str], int]] = {}


class CoolDown:

    def __init__(self, key: str, msg: Union[MessageSession, str], all=False):
        self.key = key
        self.msg = msg
        self.sender_id = self.msg
        if isinstance(self.sender_id, MessageSession):
            if all:
                self.sender_id = self.msg.target.target_id
            else:
                self.sender_id = self.sender_id.target.sender_id

    def add(self):
        if self.key not in _cd_lst:
            _cd_lst[self.key] = {}
        _cd_lst[self.key][self.sender_id] = datetime.datetime.now().timestamp()

    def check(self, delay: int):
        if self.key not in _cd_lst:
            return 0
        if self.sender_id in _cd_lst[self.key]:
            if (d := (datetime.datetime.now().timestamp() - _cd_lst[self.key][self.sender_id])) > delay:
                return 0
            else:
                return d
        else:
            return 0

    def reset(self):
        if self.key in _cd_lst:
            if self.sender_id in _cd_lst[self.key]:
                _cd_lst[self.key].pop(self.sender_id)
        self.add()
