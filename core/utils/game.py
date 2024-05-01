from core.types import MessageSession
from typing import Dict, Union

playstate_lst: Dict[str, Dict[Union[MessageSession, str], Dict[str, Union[int, Dict[str, int]]]]] = {}

class PlayState:

    def __init__(self, game: str, msg: Union[MessageSession, str], all: bool = False):
        self.game = game
        self.msg = msg
        self.all = all
        self.target_id = self.msg.target.target_id
        self.sender_id = self.msg.target.sender_id

    def enable(self):
        if self.all:
            playstate_lst[self.target_id][self.game]['status'] = True
        else:
            playstate_lst[self.target_id][self.sender_id][self.game]['status'] = True
            
    def disable(self):
        if self.all:
            playstate_lst[self.target_id][self.game]['status'] = False
        else:
            playstate_lst[self.target_id][self.sender_id][self.game]['status'] = False
        
    def update(self, **kwargs):
        target_dict = playstate_lst.setdefault(self.target_id, {})
        if self.all:
            game_dict = target_dict.setdefault(self.game, {'status': False})
            game_dict.update(kwargs)
        else:
            sender_dict = target_dict.setdefault(self.sender_id, {})
            game_dict = sender_dict.setdefault(self.game, {'status': False})
            game_dict.update(kwargs)

    def check(self, key: str = 'status'):
        try:
            if self.all:
                return playstate_lst[self.target_id][self.game][key]
            else:
                return playstate_lst[self.target_id][self.sender_id][self.game][key]
        except:
            return False
