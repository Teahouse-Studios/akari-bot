from datetime import datetime

from core.logger import Logger
from core.types import MessageSession


class MessageTaskManager:
    _list = {}
    _callback_list = {}

    @classmethod
    def add_task(cls, session: MessageSession, flag, all_=False, reply=None):
        sender = session.target.sender_id
        task_type = 'reply' if reply is not None else 'wait'
        if all_:
            sender = 'all'

        if session.target.target_id not in cls._list:
            cls._list[session.target.target_id] = {}
        if sender not in cls._list[session.target.target_id]:
            cls._list[session.target.target_id][sender] = {}
        cls._list[session.target.target_id][sender][session] = {
            'flag': flag, 'active': True, 'type': task_type, 'reply': reply, 'ts': datetime.now().timestamp()}
        Logger.debug(cls._list)

    @classmethod
    def add_callback(cls, message_id, callback):
        cls._callback_list[message_id] = {'callback': callback, 'ts': datetime.now().timestamp()}

    @classmethod
    def get_result(cls, session: MessageSession):
        if 'result' in cls._list[session.target.target_id][session.target.sender_id][session]:
            return cls._list[session.target.target_id][session.target.sender_id][session]['result']
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
        for message_id in cls._callback_list:
            if datetime.now().timestamp() - cls._callback_list[message_id]['ts'] > 3600:
                del cls._callback_list[message_id]

    @classmethod
    async def check(cls, session: MessageSession):
        if session.target.target_id in cls._list:
            senders = []
            if session.target.sender_id in cls._list[session.target.target_id]:
                senders.append(session.target.sender_id)
            if 'all' in cls._list[session.target.target_id]:
                senders.append('all')
            if senders is not None:
                for sender in senders:
                    for s in cls._list[session.target.target_id][sender]:
                        get_ = cls._list[session.target.target_id][sender][s]
                        if get_['type'] == 'wait':
                            get_['result'] = session
                            get_['active'] = False
                            get_['flag'].set()
                        elif get_['type'] == 'reply':
                            if isinstance(get_['reply'], list):
                                for reply in get_['reply']:
                                    if reply == session.target.reply_id:
                                        get_['result'] = session
                                        get_['active'] = False
                                        get_['flag'].set()
                                        break
                            else:
                                if get_['reply'] == session.target.reply_id:
                                    get_['result'] = session
                                    get_['active'] = False
                                    get_['flag'].set()
        if session.target.reply_id in cls._callback_list:
            await cls._callback_list[session.target.reply_id]['callback'](session)


__all__ = ['MessageTaskManager']
