import time

from core.builtins.session.internal import MessageSession
from core.utils.container import ExpiringTempDict

_cd_dict = ExpiringTempDict()


class CoolDown:
    """
    冷却事件构造器。
    :param key: 冷却事件名称
    :param msg: 消息会话
    :param delay: 冷却时间（秒）
    :param whole_target: 是否应用至全对话（默认为 False）
    """

    def __init__(self, key: str, msg: MessageSession, delay: float, whole_target: bool = False):
        self.key = key
        self.msg = msg
        self.delay = delay
        self.whole_target = whole_target
        self.target_id = self.msg.session_info.target_id
        self.sender_id = self.msg.session_info.sender_id

    def _get_cd_dict(self) -> ExpiringTempDict:
        """
        获取或创建冷却事件字典。
        对于单个发送者，返回 sender_id -> key 的结构。
        对于 whole_target，返回 target_id -> key 的结构。
        """
        target_dict = _cd_dict[self.target_id]

        if self.whole_target:
            if self.key not in target_dict:
                target_dict[self.key] = ExpiringTempDict(exp=self.delay)
            return target_dict[self.key]

        sender_dict = target_dict[self.sender_id]
        if self.key not in sender_dict:
            sender_dict[self.key] = ExpiringTempDict(exp=self.delay)
        return sender_dict[self.key]

    def check(self) -> float:
        """
        检查冷却事件剩余时间。
        :return: 剩余冷却时间（秒），0 表示已可用
        """
        cd_instance = self._get_cd_dict()
        elapsed = time.time() - cd_instance.ts
        remaining = cd_instance.exp - elapsed
        return max(remaining, 0)

    def reset(self):
        """
        重置冷却事件。
        """
        cd_instance = self._get_cd_dict()
        cd_instance.refresh()
