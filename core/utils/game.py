from datetime import datetime, timedelta
from typing import Any, Dict, Union

from core.types import MessageSession

playstate_lst: Dict[Union[str, MessageSession], Dict[Union[str, MessageSession], Dict[str, Dict[str, Any]]]] = {}


class PlayState:

    def __init__(self, game: str, msg: Union[MessageSession, str], all: bool = False, timeout: int = 3600):
        self.game = game
        self.msg = msg
        self.all = all
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id
        timeout = timeout if timeout > 0 else 3600
        self.timeout = timedelta(seconds=timeout)

    def enable(self):
        timeout = (datetime.now() + self.timeout).timestamp()
        if self.target_id not in playstate_lst:
            playstate_lst[self.target_id] = {}
        if self.game not in playstate_lst[self.target_id]:
            playstate_lst[self.target_id][self.game] = {'_status': False, '_timeout': timeout}

        if self.all:
            playstate_lst[self.target_id][self.game] = {'_status': True, '_timeout': timeout}
        else:
            if self.sender_id not in playstate_lst[self.target_id]:
                playstate_lst[self.target_id][self.sender_id] = {}
            playstate_lst[self.target_id][self.sender_id][self.game] = {'_status': True, '_timeout': timeout}

    def disable(self):
        if self.target_id not in playstate_lst:
            return
        if self.all:
            playstate_lst[self.target_id][self.game]['_status'] = False
        else:
            if self.sender_id not in playstate_lst[self.target_id]:
                return
            playstate_lst[self.target_id][self.sender_id][self.game]['_status'] = False

    def update(self, **kwargs):
        timeout = (datetime.now() + self.timeout).timestamp()
        target_dict = playstate_lst.setdefault(self.target_id, {})
        if self.all:
            game_dict = target_dict.setdefault(self.game, {'_status': False, '_timeout': timeout})
            game_dict.update(kwargs)
        else:
            sender_dict = target_dict.setdefault(self.sender_id, {})
            game_dict = sender_dict.setdefault(self.game, {'_status': False, '_timeout': timeout})
            game_dict.update(kwargs)

    def get(self, key: str) -> Union[Any, None]:
        if self.target_id not in playstate_lst:
            return None
        if self.all:
            return playstate_lst[self.target_id].get(self.game, {}).get(key, None)
        else:
            return playstate_lst[self.target_id].get(self.sender_id, {}).get(self.game, {}).get(key, None)

    def check(self) -> Union[bool, None]:
        if self.target_id not in playstate_lst:
            return False
        timeout = self.get(key='_timeout')
        if timeout and datetime.now().timestamp() - timeout >= 0:
            self.disable()
            return False
        else:
            self.get(key='_status')
