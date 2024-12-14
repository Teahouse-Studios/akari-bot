from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Optional

from core.builtins import MessageSession
from core.logger import Logger

_ps_lst = defaultdict(lambda: defaultdict(dict))
GAME_EXPIRED = 3600


class PlayState:
    """
    游戏事件构造器。

    :param game: 游戏事件名称。
    :param msg: 消息会话。
    :param all: 是否应用至全对话。（默认为False）
    """

    def __init__(self, game: str, msg: MessageSession, whole_target: bool = False):
        self.game = game
        self.msg = msg
        self.whole_target = whole_target
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_ps_dict(self):
        target_dict = _ps_lst[self.target_id]
        if self.whole_target:
            return target_dict.setdefault(
                self.game, {"_status": False, "_timestamp": 0.0}
            )
        sender_dict = target_dict.setdefault(self.sender_id, {})
        return sender_dict.setdefault(self.game, {"_status": False, "_timestamp": 0.0})

    def enable(self) -> None:
        """
        开启游戏事件。
        """
        playstate_dict = self._get_ps_dict()
        playstate_dict["_status"] = True
        playstate_dict["_timestamp"] = datetime.now().timestamp()
        if self.whole_target:
            Logger.info(f"[{self.target_id}]: Enabled {self.game} by {self.sender_id}.")
        else:
            Logger.info(f"[{self.sender_id}]: Enabled {self.game} at {self.target_id}.")

    def disable(self, _auto=False) -> None:
        """
        关闭游戏事件。
        """
        if self.target_id not in _ps_lst:
            return
        target_dict = _ps_lst[self.target_id]
        if self.whole_target:
            game_dict = target_dict.get(self.game)
            if game_dict:
                game_dict["_status"] = False
        else:
            sender_dict = target_dict.get(self.sender_id)
            if sender_dict:
                game_dict = sender_dict.get(self.game)
                if game_dict:
                    game_dict["_status"] = False
        if _auto:
            if self.whole_target:
                Logger.info(f"[{self.target_id}]: Disabled {self.game} automatically.")
            else:
                Logger.info(
                    f"[{self.sender_id}]: Disabled {self.game} at {self.target_id} automatically."
                )
        else:
            if self.whole_target:
                Logger.info(
                    f"[{self.target_id}]: Disabled {self.game} by {self.sender_id}."
                )
            else:
                Logger.info(
                    f"[{self.sender_id}]: Disabled {self.game} at {self.target_id}."
                )

    def update(self, **kwargs: Dict[str, Any]) -> None:
        """
        更新游戏事件中需要的值。

        :param kwargs: 键值对。
        """
        playstate_dict = self._get_ps_dict()
        playstate_dict.update(kwargs)
        if self.whole_target:
            Logger.debug(f"[{self.game}]: Updated {str(kwargs)} at {self.target_id}.")
        else:
            Logger.debug(
                f"[{self.game}]: Updated {str(kwargs)} at {self.sender_id} ({self.target_id})."
            )

    def check(self) -> bool:
        """
        检查游戏事件状态，若超过时间则自动关闭。
        """
        if self.target_id not in _ps_lst:
            return False
        target_dict = _ps_lst[self.target_id]
        if self.whole_target:
            status = target_dict.get(self.game, {}).get("_status", False)
            ts = target_dict.get(self.game, {}).get("_timestamp", 0.0)
        else:
            sender_dict = target_dict.get(self.sender_id, {})
            status = sender_dict.get(self.game, {}).get("_status", False)
            ts = sender_dict.get(self.game, {}).get("_timestamp", 0.0)
        if datetime.now().timestamp() - ts >= GAME_EXPIRED:
            self.disable(_auto=True)
        return status

    def get(self, key: str) -> Optional[Any]:
        """
        获取游戏事件中需要的值。

        :param key: 键名。
        :return: 值。
        """
        if self.target_id not in _ps_lst:
            return None
        target_dict = _ps_lst[self.target_id]
        if self.whole_target:
            return target_dict.get(self.game, {}).get(key, None)
        sender_dict = target_dict.get(self.sender_id, {})
        return sender_dict.get(self.game, {}).get(key, None)
