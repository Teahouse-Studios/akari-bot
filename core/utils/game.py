from collections import defaultdict
from datetime import datetime
from typing import Any

from core.builtins import MessageSession
from core.logger import Logger

_ps_lst = defaultdict(lambda: defaultdict(dict))
"""
目前 _ps_lst 的结构如下：
`{target_id: {game: {_status: bool, _timestamp: float}}`
"""
GAME_EXPIRED = 3600
"""游戏事件的过期时间。"""


def clear_ps_list():
    now = datetime.now().timestamp()

    for target in list(_ps_lst.keys()):
        target_data = _ps_lst[target]

        for game in list(target_data.keys()):
            game_data = target_data[game]
            if "_timestamp" in game_data and (now - game_data["_timestamp"] >= GAME_EXPIRED):
                del target_data[game]
                continue

            if not game_data:
                del target_data[game]

        if not target_data:
            del _ps_lst[target]


class PlayState:
    """
    游戏事件构造器。

    :param game: 游戏事件名称。
    :param msg: 消息会话。
    """

    def __init__(self, game: str, msg: MessageSession):
        self.game = game
        self.msg = msg
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_ps_dict(self):
        target_dict = _ps_lst[self.target_id]
        return target_dict.setdefault(
            self.game, {"_status": False, "_timestamp": 0.0}
        )

    def enable(self) -> None:
        """
        开启游戏事件。
        """
        playstate_dict = self._get_ps_dict()
        playstate_dict["_status"] = True
        playstate_dict["_timestamp"] = datetime.now().timestamp()
        Logger.info(f"[{self.target_id}]: Enabled {self.game} by {self.sender_id}.")

    def disable(self) -> None:
        """
        关闭游戏事件。
        """
        if self.target_id not in _ps_lst:
            return
        target_dict = _ps_lst[self.target_id]
        game_dict = target_dict.get(self.game)
        if game_dict and game_dict.get("_status"):
            game_dict["_status"] = False
            Logger.info(
                f"[{self.target_id}]: Disabled {self.game} by {self.sender_id}."
            )

    def update(self, **kwargs) -> None:
        """
        更新游戏事件中需要的值。

        :param kwargs: 键值对。
        """
        playstate_dict = self._get_ps_dict()
        playstate_dict.update(kwargs)
        Logger.debug(f"[{self.game}]: Updated {str(kwargs)} at {self.target_id}.")

    def check(self) -> bool:
        """
        检查游戏事件状态。
        """
        if self.target_id not in _ps_lst:
            return False
        status = self.get("_status", False)
        return status

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取游戏事件中需要的值。

        :param key: 键名。
        :param default: 默认值。
        :return: 值。
        """
        if self.target_id not in _ps_lst:
            return None
        target_dict = _ps_lst[self.target_id]
        return target_dict.get(self.game, {}).get(key, default)
