from datetime import datetime

from core.logger import Logger
from core.types import MessageSession


class MessageTaskManager:
    _list = {}

    @classmethod
    def add_task(cls, session: MessageSession, flag, all_=False, reply=None):
        sender = session.target.senderId
        task_type = 'reply' if reply is not None else 'wait'
        if all_:
            sender = 'all'

        if session.target.targetId not in cls._list:
            cls._list[session.target.targetId] = {}
        if sender not in cls._list[session.target.targetId]:
            cls._list[session.target.targetId][sender] = {}
        cls._list[session.target.targetId][sender][session] = {session: {
            'flag': flag, 'active': True, 'type': task_type, 'reply': reply, 'ts': datetime.now().timestamp()}}
        Logger.debug(cls._list)

    @classmethod
    def get_result(cls, session: MessageSession):
        if 'result' in cls._list[session.target.targetId][session.target.senderId][session]:
            return cls._list[session.target.targetId][session.target.senderId][session]['result']
        else:
            return None

    @classmethod
    def get(cls):
        return cls._list

    @classmethod
    async def bg_check(cls):
        for target in cls._list:
            for sender in cls._list[target]:
                for session in cls._list[target][sender]:
                    if cls._list[target][sender][session]['active']:
                        if datetime.now().timestamp() - cls._list[target][sender][session]['ts'] > 3600:
                            cls._list[target][sender][session]['active'] = False
                            cls._list[target][sender][session]['flag'].set()  # no result = cancel

    @classmethod
    async def check(cls, session: MessageSession):
        if session.target.targetId in cls._list:
            senders = []
            if session.target.senderId in cls._list[session.target.targetId]:
                senders.append(session.target.senderId)
            if 'all' in cls._list[session.target.targetId]:
                senders.append('all')
            if senders is not None:
                for sender in senders:
                    for s in cls._list[session.target.targetId][sender]:
                        get_ = cls._list[session.target.targetId][sender][s]
                        if get_['type'] == 'wait':
                            get_['result'] = session
                            get_['active'] = False
                            get_['flag'].set()
                        elif get_['type'] == 'reply':
                            if isinstance(get_['reply'], list):
                                for reply in get_['reply']:
                                    if reply == s.target.replyId:
                                        get_['result'] = session
                                        get_['active'] = False
                                        get_['flag'].set()
                                        break
                            else:
                                if get_['reply'] == s.target.replyId:
                                    get_['result'] = session
                                    get_['active'] = False
                                    get_['flag'].set()


__all__ = ['MessageTaskManager']
