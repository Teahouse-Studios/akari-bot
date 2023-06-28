from datetime import datetime

from core.types import MessageSession


class MessageTaskManager:
    _list = {}

    @classmethod
    def add_task(cls, session: MessageSession, flag, all_=False, reply=None):
        sender = session.target.senderId
        task_type = 'reply' if reply is not None else 'wait'
        if all_:
            sender = 'all'
        if session.target.targetId in cls._list:
            if sender in cls._list[session.target.targetId]:
                if cls._list[session.target.targetId][sender]['active']:
                    cls._list[session.target.targetId][sender]['active'] = False
                    cls._list[session.target.targetId][sender]['flag'].set()

        cls._list.update(
            {session.target.targetId: {sender: {'flag': flag, 'active': True,
                                                'type': task_type, 'reply': reply, 'ts': datetime.now().timestamp(),
                                                'original_session': session}}})

    @classmethod
    def get_result(cls, session: MessageSession):
        if 'result' in cls._list[session.target.targetId][session.target.senderId]:
            return cls._list[session.target.targetId][session.target.senderId]['result']
        else:
            return None

    @classmethod
    def get(cls):
        return cls._list

    @classmethod
    def check(cls, session: MessageSession):
        for target in cls._list:
            for sender in cls._list[target]:
                if cls._list[target][sender]['active']:
                    if datetime.now().timestamp() - cls._list[target][sender]['ts'] > 3600:
                        cls._list[target][sender]['active'] = False
                        cls._list[target][sender]['flag'].set()  # no result = cancel
        if session.target.targetId in cls._list:
            sender = None
            if session.target.senderId in cls._list[session.target.targetId]:
                sender = session.target.senderId
            if 'all' in cls._list[session.target.targetId]:
                sender = 'all'
            if sender is not None:
                get_ = cls._list[session.target.targetId][sender]
                if get_['type'] == 'wait':
                    get_['result'] = session
                    get_['active'] = False
                    get_['flag'].set()
                elif get_['type'] == 'reply':
                    if isinstance(get_['reply'], list):
                        for reply in get_['reply']:
                            if reply == session.target.replyId:
                                get_['result'] = session
                                get_['active'] = False
                                get_['flag'].set()
                                break
                    else:
                        if get_['reply'] == session.target.replyId:
                            get_['result'] = session
                            get_['active'] = False
                            get_['flag'].set()


__all__ = ['MessageTaskManager']
