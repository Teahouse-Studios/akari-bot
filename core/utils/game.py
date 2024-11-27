from collections import defaultdict
from datetime import datetime
from typing import Any, Optional, Union

from core.logger import Logger
from core.builtins import MessageSession

playstate_lst = defaultdict(lambda: defaultdict(dict))
GAME_EXPIRED = 3600


class PlayState:
    def __init__(self, game: str, msg: Union[MessageSession, str], all: bool = False):
        self.game = game
        self.msg = msg
        self.all = all
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def _get_game_dict(self):
        target_dict = playstate_lst[self.target_id]
        if self.all:
            return target_dict.setdefault(self.game, {'_status': False, '_timestamp': 0.0})
        else:
            sender_dict = target_dict.setdefault(self.sender_id, {})
            return sender_dict.setdefault(self.game, {'_status': False, '_timestamp': 0.0})

    def enable(self) -> None:
        game_dict = self._get_game_dict()
        game_dict['_status'] = True
        game_dict['_timestamp'] = datetime.now().timestamp()
        if self.all:
            Logger.info(f'[{self.target_id}]: Enabled {self.game} by {self.sender_id}.')
        else:
            Logger.info(f'[{self.sender_id}]: Enabled {self.game} at {self.target_id}.')

    def disable(self, auto=False) -> None:
        if self.target_id not in playstate_lst:
            return
        target_dict = playstate_lst[self.target_id]
        if self.all:
            game_dict = target_dict.get(self.game)
            if game_dict:
                game_dict['_status'] = False
        else:
            sender_dict = target_dict.get(self.sender_id)
            if sender_dict:
                game_dict = sender_dict.get(self.game)
                if game_dict:
                    game_dict['_status'] = False
        if auto:
            if self.all:
                Logger.info(f'[{self.target_id}]: Disabled {self.game} automatically.')
            else:
                Logger.info(f'[{self.sender_id}]: Disabled {self.game} at {self.target_id} automatically.')
        else:
            if self.all:
                Logger.info(f'[{self.target_id}]: Disabled {self.game} by {self.sender_id}.')
            else:
                Logger.info(f'[{self.sender_id}]: Disabled {self.game} at {self.target_id}.')

    def update(self, **kwargs) -> None:
        game_dict = self._get_game_dict()
        game_dict.update(kwargs)
        if self.all:
            Logger.debug(f'[{self.game}]: Updated {str(kwargs)} at {self.target_id}.')
        else:
            Logger.debug(f'[{self.game}]: Updated {str(kwargs)} at {self.sender_id} ({self.target_id}).')

    def check(self) -> bool:
        if self.target_id not in playstate_lst:
            return False
        target_dict = playstate_lst[self.target_id]
        if self.all:
            status = target_dict.get(self.game, {}).get('_status', False)
            ts = target_dict.get(self.game, {}).get('_timestamp', 0.0)
        else:
            sender_dict = target_dict.get(self.sender_id, {})
            status = sender_dict.get(self.game, {}).get('_status', False)
            ts = sender_dict.get(self.game, {}).get('_timestamp', 0.0)
        if datetime.now().timestamp() - ts >= GAME_EXPIRED:
            self.disable(auto=True)
        return status

    def get(self, key: str) -> Optional[Any]:
        if self.target_id not in playstate_lst:
            return None
        target_dict = playstate_lst[self.target_id]
        if self.all:
            return target_dict.get(self.game, {}).get(key, None)
        else:
            sender_dict = target_dict.get(self.sender_id, {})
            return sender_dict.get(self.game, {}).get(key, None)
