from collections import defaultdict
from datetime import datetime

from core.builtins import MessageSession

_cd_lst = defaultdict(lambda: defaultdict(dict))


class CoolDown:
    """
    冷却事件构造器。

    :param key: 冷却事件名称。
    :param msg: 消息会话。
    :param all: 是否应用至全对话。（默认为False）
    """

    def __init__(self, key: str, msg: MessageSession, whole_target: bool = False):
        self.key = key
        self.msg = msg
        self.whole_target = whole_target
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_cd_dict(self):
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            return target_dict.setdefault(self.key, {"_timestamp": 0.0})
        sender_dict = target_dict.setdefault(self.sender_id, {})
        return sender_dict.setdefault(self.key, {"_timestamp": 0.0})

    def add(self):
        """
        添加冷却事件。
        """
        cooldown_dict = self._get_cd_dict()
        cooldown_dict["_timestamp"] = datetime.now().timestamp()

    def check(self, delay: float) -> float:
        """
        检查冷却事件剩余冷却时间。

        :param delay: 设定的冷却时间。
        :return: 剩余的冷却时间。
        """
        if self.key not in _cd_lst:
            return 0
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            ts = target_dict.get(self.key, {}).get("_timestamp", 0.0)
        else:
            sender_dict = target_dict.get(self.sender_id, {})
            ts = sender_dict.get(self.key, {}).get("_timestamp", 0.0)

        if (d := (datetime.now().timestamp() - ts)) > delay:
            return 0
        return d

    def reset(self):
        """
        重置冷却事件。
        """
        self.add()
