from core.types import MessageSession
from typing import Dict, Union

playstate_lst: Dict[str, Dict[Union[MessageSession, str], Dict[str, Union[int, Dict[str, int]]]]] = {}

class PlayState:

    def __init__(self, game: str, msg: Union[MessageSession, str]):
        self.game = game
        self.msg = msg
        self.sender_id = self.msg
        if isinstance(self.sender_id, MessageSession):
            self.sender_id = self.sender_id.target.sender_id

    def enable(self):
        if self.sender_id not in playstate_lst:
            playstate_lst[self.sender_id] = {}
        if self.game not in playstate_lst[self.sender_id]:
            playstate_lst[self.sender_id][self.game] = {'status': True}
        else:
            playstate_lst[self.sender_id][self.game]['status'] = True

    def disable(self):
        if self.sender_id not in playstate_lst:
            playstate_lst[self.sender_id] = {}
        if self.game not in playstate_lst[self.sender_id]:
            playstate_lst[self.sender_id][self.game] = {'status': False}
        else:
            playstate_lst[self.sender_id][self.game]['status'] = False

    def update(self, **kwargs):
        if self.sender_id not in playstate_lst:
            playstate_lst[self.sender_id] = {}
        if self.game not in playstate_lst[self.sender_id]:
            playstate_lst[self.sender_id][self.game] = {'status': False, **kwargs}
        else:
            playstate_lst[self.sender_id][self.game].update(kwargs)

    def check(self, key: str = 'status'):
        if self.sender_id not in playstate_lst:
            return False
        if self.game in playstate_lst[self.sender_id]:
            return playstate_lst[self.sender_id][self.game].get(key, False)
        else:
            return False
