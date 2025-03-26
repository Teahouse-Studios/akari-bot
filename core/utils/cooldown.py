from collections import defaultdict
from datetime import datetime

from core.builtins import MessageSession

_cd_lst = defaultdict(lambda: defaultdict(dict))


def clear_cd_list():
    now = datetime.now().timestamp()

    for target in list(_cd_lst.keys()):
        target_data = _cd_lst[target]

        for sender in list(target_data.keys()):
            sender_data = target_data[sender]

            if isinstance(sender_data, dict):
                if "timestamp" in sender_data and (now - sender_data["timestamp"] >= sender_data["delay"]):
                    del target_data[sender]
                    continue
            elif isinstance(sender_data, str):
                for cd in list(sender_data.keys()):
                    cd_data = sender_data[cd]

                    if "timestamp" in cd_data and (now - cd_data["timestamp"] >= cd_data["delay"]):
                        del sender_data[cd]

                if not sender_data:
                    del target_data[sender]

        if not target_data:
            del _cd_lst[target]


class CoolDown:
    """
    冷却事件构造器。

    :param key: 冷却事件名称。
    :param msg: 消息会话。
    :param delay: 冷却时间。
    :param whole_target: 是否应用至全对话。（默认为False）
    """

    def __init__(self, key: str, msg: MessageSession, delay: float, whole_target: bool = False):
        self.key = key
        self.msg = msg
        self.delay = delay
        self.whole_target = whole_target
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_cd_dict(self):
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            return target_dict.setdefault(self.key, {"timestamp": 0.0, "delay": self.delay})
        sender_dict = target_dict.setdefault(self.sender_id, {})
        return sender_dict.setdefault(self.key, {"timestamp": 0.0, "delay": self.delay})

    def check(self) -> float:
        """
        检查冷却事件剩余冷却时间。

        :return: 剩余的冷却时间。
        """
        if self.target_id not in _cd_lst:
            self._get_cd_dict()
            return 0
        target_dict = _cd_lst[self.target_id]
        if self.whole_target:
            ts = target_dict.get(self.key, {}).get("timestamp", 0.0)
            delay = target_dict.get(self.key, {}).get("delay", 0.0)
        else:
            sender_dict = target_dict.get(self.sender_id, {})
            ts = sender_dict.get(self.key, {}).get("timestamp", 0.0)
            delay = sender_dict.get(self.key, {}).get("delay", 0.0)

        if (d := datetime.now().timestamp() - ts) > delay:
            return 0
        return delay - d

    def reset(self):
        """
        重置冷却事件。
        """
        cooldown_dict = self._get_cd_dict()
        cooldown_dict["timestamp"] = datetime.now().timestamp()
