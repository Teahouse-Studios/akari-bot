from core.elements import MessageSession


class MessageTaskManager:
    _list = {}

    @staticmethod
    def add_task(session: MessageSession, flag, all_=False, reply=None):
        sender = session.target.senderId
        task_type = 'reply' if reply is not None else 'wait'
        if all_:
            sender = 'all'

        MessageTaskManager._list.update(
            {session.target.targetId: {sender: {'flag': flag, 'active': True, 'type': task_type, 'reply': reply}}})

    @staticmethod
    def get_result(session: MessageSession):
        return MessageTaskManager._list[session.target.targetId][session.target.senderId]['result']

    @staticmethod
    def get():
        return MessageTaskManager._list

    @staticmethod
    def check(session: MessageSession):
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
