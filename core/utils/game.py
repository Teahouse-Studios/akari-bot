from collections.abc import Iterator
from contextlib import contextmanager
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
        # 按消息通道而非 union 建键：同一 union 下通道号不同的场景是不同的现实场景，
        # 各自的对局互不相干，并作一处会让一边开局把另一边也带进游戏中。
        self.channel_key = self.msg.session_info.channel_key
        self.sender_union_id = self.msg.session_info.sender_union_id
        self._generation = None

    def _get_ps_dict(self) -> ExpiringTempDict:
        target_dict = _ps_dict[self.channel_key]
        return target_dict[self.game]

    def enable(self) -> None:
        """开启游戏事件。"""
        playstate_dict = self._get_ps_dict()
        self._generation = object()
        playstate_dict["_status"] = True
        playstate_dict["_generation"] = self._generation
        playstate_dict.refresh()
        Logger.info(f"[{self.channel_key}]: Enabled {self.game} by {self.sender_union_id}.")

    def disable(self) -> None:
        """关闭游戏事件。"""
        if self.channel_key not in _ps_dict:
            return
        playstate_dict = _ps_dict[self.channel_key].get(self.game)
        if playstate_dict and playstate_dict.get("_status"):
            playstate_dict["_status"] = False
            playstate_dict["_generation"] = None
            Logger.info(f"[{self.channel_key}]: Disabled {self.game} by {self.sender_union_id}.")

    @contextmanager
    def running(self) -> Iterator["PlayState"]:
        """在当前调用存活期间维护游戏状态，并只清理它开启的这一局。"""
        self.enable()
        try:
            yield self
        finally:
            playstate_dict = self._get_ps_dict()
            if playstate_dict.get("_generation") is self._generation:
                self.disable()

    def update(self, **kwargs) -> None:
        """更新游戏事件中需要的值。"""
        playstate_dict = self._get_ps_dict()
        for k, v in kwargs.items():
            playstate_dict[k] = v
        Logger.debug(f"[{self.game}]: Updated {kwargs} at {self.channel_key}.")

    def check(self) -> bool:
        """检查游戏事件状态。"""
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
