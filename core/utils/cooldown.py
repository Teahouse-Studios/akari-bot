import datetime
from typing import Dict

from core.builtins import MessageSession

_cd_lst: Dict[str, Dict[MessageSession, float]] = {}


class CoolDown:

    def __init__(self, key: str, msg: MessageSession, whole_target: bool = False):
        self.key = key
        self.msg = msg
        self.whole_target = whole_target
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_cd_dict(self):
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            return target_dict.setdefault(self.key, {'_timestamp': 0.0})
        else:
            sender_dict = target_dict.setdefault(self.sender_id, {})
            return sender_dict.setdefault(self.key, {'_timestamp': 0.0})

    def add(self):
        '''
        添加冷却事件。
        '''
        if self.key not in _cd_lst:
            _cd_lst[self.key] = {}
        _cd_lst[self.key][self.sender_id] = datetime.datetime.now().timestamp()

    def check(self, delay: int) -> float:
        '''
        检查冷却事件剩余冷却时间。
        '''
        if self.key not in _cd_lst:
            return 0
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            ts = target_dict.get(self.key, {}).get('_timestamp', 0.0)
        else:
            return 0

    def reset(self):
        '''
        重置冷却事件。
        '''
        if self.key in _cd_lst:
            if self.sender_id in _cd_lst[self.key]:
                _cd_lst[self.key].pop(self.sender_id)
        self.add()
