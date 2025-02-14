from collections import defaultdict
from datetime import datetime

from core.builtins import MessageSession

_cd_lst = defaultdict(lambda: defaultdict(dict))


def clear_cd_list():
    now = datetime.now().timestamp()

    for target in list(_cd_lst.keys()):
        target_data = _cd_lst[target]

        for key in list(target_data.keys()):
            key_data = target_data[key]
            if "timestamp" in key_data and (now - key_data["timestamp"] >= key_data["delay"]):
                del target_data[key]
                continue

        if not target_data:
            del _cd_lst[target]


class CoolDown:
    """
    冷却事件构造器。

    :param key: 冷却事件名称。
    :param msg: 消息会话。
    :param delay: 冷却时间。
    """

    def __init__(self, key: str, msg: MessageSession, delay: float):
        self.key = key
        self.msg = msg
        self.delay = delay
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_cd_dict(self):
        target_dict = _cd_lst[self.target_id]
        return target_dict.setdefault(self.key, {"timestamp": 0.0, "delay": self.delay})

    def check(self) -> float:
        """
        检查冷却事件剩余冷却时间。

        :return: 剩余的冷却时间。
        """
        if self.target_id not in _cd_lst:
            self.reset()
            return 0
        target_dict = _cd_lst[self.target_id]
        ts = target_dict.get(self.key, {}).get("timestamp", 0.0)
        delay = target_dict.get(self.key, {}).get("delay", 0.0)

        if (d := datetime.now().timestamp() - ts) > delay:
            return 0
        return delay - d

    def reset(self):
        """
        重置冷却事件。
        """
        cooldown_dict = self._get_cd_dict()
        cooldown_dict["timestamp"] = datetime.now().timestamp()
