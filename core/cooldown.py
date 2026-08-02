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
    :param whole_target: 是否应用至整个场景（默认为 False）
    """

    def __init__(self, key: str, msg: MessageSession, delay: float, whole_target: bool = False):
        self.key = key
        self.msg = msg
        self.delay = delay
        self.whole_target = whole_target
        # 场景维度按消息通道划分：仅共享 union 而通道号不同的场景是不同的现实场景，
        # 不应共用一份冷却。用户维度只按 union，同一个人换平台账号仍受同一份冷却约束。
        self.channel_key = self.msg.session_info.channel_key
        self.sender_union_id = self.msg.session_info.sender_union_id

    def _get_cd_dict(self) -> ExpiringTempDict:
        """
        获取或创建冷却事件字典。
        对于单个用户，返回 sender_union_id -> key 的结构。
        对于 whole_target，返回 channel_key -> key 的结构。
        """
        target_dict = _cd_dict[self.channel_key]

        # 这些容器嵌在 _cd_dict 之下，清理由根容器递归下来，不必各自登记为根
        if self.whole_target:
            if self.key not in target_dict:
                target_dict[self.key] = ExpiringTempDict(exp=self.delay, root=False)
            return target_dict[self.key]

        sender_dict = target_dict[self.sender_union_id]
        if self.key not in sender_dict:
            sender_dict[self.key] = ExpiringTempDict(exp=self.delay, root=False)
        return sender_dict[self.key]

    def check(self) -> float:
        """
        检查冷却事件剩余时间。
        :return: 剩余冷却时间（秒），0 表示已可用
        """
        cd_instance = self._get_cd_dict()
        if cd_instance:
            remaining = cd_instance.exp - (time.time() - cd_instance.ts)
        else:
            remaining = 0
        return remaining

    def reset(self):
        """
        重置冷却事件。
        """
        cd_instance = self._get_cd_dict()
        cd_instance.refresh()
