from datetime import datetime

from core.elements import MessageSession


class MessageTaskManager:
    _list = {}

    @staticmethod
    def add_task(session: MessageSession, flag, all_=False, reply=None):
        sender = session.target.senderId
        task_type = 'reply' if reply is not None else 'wait'
        if all_:
            sender = 'all'
        if session.target.targetId in MessageTaskManager._list:
            if sender in MessageTaskManager._list[session.target.targetId]:
                if MessageTaskManager._list[session.target.targetId][sender]['active']:
                    MessageTaskManager._list[session.target.targetId][sender]['active'] = False
                    MessageTaskManager._list[session.target.targetId][sender]['flag'].set()

        MessageTaskManager._list.update(
            {session.target.targetId: {sender: {'flag': flag, 'active': True,
                                                'type': task_type, 'reply': reply, 'ts': datetime.now().timestamp(),
                                                'original_session': session}}})

    @staticmethod
    def get_result(session: MessageSession):
        if 'result' in MessageTaskManager._list[session.target.targetId][session.target.senderId]:
            return MessageTaskManager._list[session.target.targetId][session.target.senderId]['result']
        else:
            return False

    @staticmethod
    def get():
        return MessageTaskManager._list

    @staticmethod
    def check(session: MessageSession):
        for target in MessageTaskManager._list:
            for sender in MessageTaskManager._list[target]:
                if MessageTaskManager._list[target][sender]['active']:
                    if datetime.now().timestamp() - MessageTaskManager._list[target][sender]['ts'] > 3600:
                        MessageTaskManager._list[target][sender]['active'] = False
                        MessageTaskManager._list[target][sender]['flag'].set()  # no result = cancel
        if session.target.targetId in MessageTaskManager._list:
            sender = None
            if session.target.senderId in MessageTaskManager._list[session.target.targetId]:
                sender = session.target.senderId
            if 'all' in MessageTaskManager._list[session.target.targetId]:
                sender = 'all'
            if sender is not None:
                get_ = MessageTaskManager._list[session.target.targetId][sender]
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
