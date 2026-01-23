from typing import Any
from core.builtins.session.internal import MessageSession
from core.logger import Logger
from core.utils.container import ExpiringTempDict

GAME_EXPIRED = 3600  # 游戏事件过期时间（秒）

_ps_dict = ExpiringTempDict(exp=GAME_EXPIRED)


class PlayState:
    """
    游戏事件构造器。

    :param game: 游戏事件名称。
    :param msg: 消息会话。
    """

    def __init__(self, game: str, msg: MessageSession):
        self.game = game
        self.msg = msg
        self.target_id = self.msg.session_info.target_id
        self.sender_id = self.msg.session_info.sender_id

    def _get_ps_dict(self) -> ExpiringTempDict:
        """
        获取目标的游戏事件字典，如果不存在则自动创建。
        """
        target_dict = _ps_dict[self.target_id]
        return target_dict[self.game]

    def enable(self) -> None:
        """
        开启游戏事件。
        """
        playstate_dict = self._get_ps_dict()
        playstate_dict["_status"] = True
        playstate_dict.refresh()
        Logger.info(f"[{self.target_id}]: Enabled {self.game} by {self.sender_id}.")

    def disable(self) -> None:
        """
        关闭游戏事件。
        """
        if self.target_id not in _ps_dict:
            return
        playstate_dict = _ps_dict[self.target_id].get(self.game)
        if playstate_dict and playstate_dict.get("_status"):
            playstate_dict["_status"] = False
            Logger.info(
                f"[{self.target_id}]: Disabled {self.game} by {self.sender_id}."
            )

    def update(self, **kwargs) -> None:
        """
        更新游戏事件中需要的值。
        """
        playstate_dict = self._get_ps_dict()
        for k, v in kwargs.items():
            playstate_dict[k] = v
        Logger.debug(f"[{self.game}]: Updated {kwargs} at {self.target_id}.")

    def check(self) -> bool:
        """
        检查游戏事件状态。
        """
        playstate_dict = self._get_ps_dict()
        return playstate_dict.get("_status", False)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取游戏事件中需要的值。

        :param key: 键名。
        :param default: 默认值。
        """
        playstate_dict = self._get_ps_dict()
        return playstate_dict.get(key, default)
